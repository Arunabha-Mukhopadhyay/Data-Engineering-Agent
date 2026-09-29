import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests


class ETLTools:
    supported_formats = {"csv", "json", "parquet"}

    def __init__(self, project_root=None, session=None, max_pages=1000):
        if max_pages < 1:
            raise ValueError("max_pages must be a positive integer.")
        self.project_root = Path(
            project_root or Path(__file__).resolve().parent.parent
        ).resolve()
        self.session = session or requests.Session()
        self.max_pages = max_pages

    def _record_run(self, record):
        log_path = self.project_root / "logs" / "etl_runs.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, default=str) + "\n")

    @staticmethod
    def _safe_source(url):
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{host}{parsed.path}"

    def extract_load(self, url: str, output_folder: str, format: str):
        output_format = format.lower()
        if output_format not in self.supported_formats:
            raise ValueError(
                f"Unsupported format: {format}. "
                f"Choose from {', '.join(sorted(self.supported_formats))}."
            )

        started_at = time.monotonic()
        run_record = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "source": self._safe_source(url),
            "output_format": output_format,
            "status": "failed",
        }

        try:
            current_url = url
            visited_urls = set()
            records = []
            page_count = 0

            while current_url:
                if current_url in visited_urls:
                    raise ValueError("API pagination returned a repeated URL.")
                visited_urls.add(current_url)

                response = self.session.get(current_url, timeout=30)
                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, dict):
                    raise ValueError("API response must be a JSON object.")
                page_records = payload.get("results")
                if not isinstance(page_records, list):
                    raise ValueError(
                        "API response must contain a list in the 'results' field."
                    )
                if not all(isinstance(record, dict) for record in page_records):
                    raise ValueError("Every item in 'results' must be a JSON object.")

                records.extend(page_records)
                page_count += 1
                next_url = payload.get("next")
                if next_url is not None and not isinstance(next_url, str):
                    raise ValueError("API pagination field 'next' must be a URL or null.")
                if next_url and page_count >= self.max_pages:
                    raise ValueError(
                        f"API pagination exceeded the {self.max_pages}-page limit."
                    )
                current_url = urljoin(current_url, next_url) if next_url else None

            output_path = Path(output_folder)
            if not output_path.is_absolute():
                output_path = self.project_root / output_path
            output_path.mkdir(parents=True, exist_ok=True)

            file_path = output_path / f"extracted_data.{output_format}"
            dataframe = pd.json_normalize(records)
            self._write_dataframe(dataframe, file_path, output_format)

            run_record.update(
                {
                    "status": "success",
                    "pages": page_count,
                    "records": len(records),
                    "output": str(file_path.relative_to(self.project_root))
                    if file_path.is_relative_to(self.project_root)
                    else str(file_path),
                    "duration_seconds": round(time.monotonic() - started_at, 3),
                }
            )
            self._record_run(run_record)
            return (
                f"Successfully extracted {len(records)} records across "
                f"{page_count} page(s) to {file_path}"
            )
        except Exception as error:
            run_record.update(
                {
                    "error_type": type(error).__name__,
                    "duration_seconds": round(time.monotonic() - started_at, 3),
                }
            )
            self._record_run(run_record)
            raise

    def transform_load_context(self, file_path: str):
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path

        file_extension = path.suffix.lower()
        if file_extension == ".csv":
            dataframe = pd.read_csv(path)
        elif file_extension == ".json":
            dataframe = pd.read_json(path, lines=True)
        elif file_extension == ".parquet":
            dataframe = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

        return str(dataframe.head(3))

    def transform_load(
        self,
        input_file_path: str,
        output_folder: str,
        output_format: str,
        operations: list[dict],
    ):
        output_format = output_format.lower()
        if output_format not in self.supported_formats:
            raise ValueError(f"Unsupported format: {output_format}")
        if not isinstance(operations, list) or len(operations) > 20:
            raise ValueError("Provide a list of at most 20 transformation operations.")

        input_path = Path(input_file_path)
        if not input_path.is_absolute():
            input_path = self.project_root / input_path
        extension = input_path.suffix.lower()
        if extension == ".csv":
            dataframe = pd.read_csv(input_path)
        elif extension == ".json":
            dataframe = pd.read_json(input_path, lines=True)
        elif extension == ".parquet":
            dataframe = pd.read_parquet(input_path)
        else:
            raise ValueError(f"Unsupported input format: {extension}")

        for operation in operations:
            if not isinstance(operation, dict):
                raise ValueError("Each transformation must be a JSON object.")
            dataframe = self._apply_operation(dataframe, operation)

        output_path = Path(output_folder)
        if not output_path.is_absolute():
            output_path = self.project_root / output_path
        output_path.mkdir(parents=True, exist_ok=True)
        file_path = output_path / f"transformed_data.{output_format}"

        self._write_dataframe(dataframe, file_path, output_format)

        self._record_run(
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "operation": "transform",
                "source": input_path.name,
                "status": "success",
                "records": len(dataframe),
                "output_format": output_format,
                "output": str(file_path),
            }
        )
        return f"Transformed {len(dataframe)} records and saved to {file_path}"

    @staticmethod
    def _write_dataframe(dataframe, file_path, output_format):
        if output_format == "csv":
            dataframe.to_csv(file_path, index=False)
        elif output_format == "json":
            dataframe.to_json(file_path, orient="records", lines=True)
        else:
            try:
                dataframe.to_parquet(file_path, index=False)
            except ImportError as error:
                raise ValueError(
                    "Parquet output requires pyarrow. Install it with `uv add pyarrow`."
                ) from error

    @staticmethod
    def _apply_operation(dataframe, operation):
        operation_name = operation.get("op")

        if operation_name == "filter":
            column = operation.get("column")
            comparator = operation.get("operator")
            value = operation.get("value")
            if column not in dataframe.columns:
                raise ValueError(f"Unknown filter column: {column}")

            if comparator == "eq":
                mask = dataframe[column] == value
            elif comparator == "ne":
                mask = dataframe[column] != value
            elif comparator == "gt":
                mask = dataframe[column] > value
            elif comparator == "gte":
                mask = dataframe[column] >= value
            elif comparator == "lt":
                mask = dataframe[column] < value
            elif comparator == "lte":
                mask = dataframe[column] <= value
            elif comparator == "contains":
                mask = dataframe[column].astype("string").str.contains(
                    str(value), case=False, regex=False, na=False
                )
            elif comparator in {"in", "not_in"}:
                if not isinstance(value, list):
                    raise ValueError("The 'in' filter requires a list value.")
                mask = dataframe[column].isin(value)
                if comparator == "not_in":
                    mask = ~mask
            elif comparator == "is_null":
                mask = dataframe[column].isna()
            elif comparator == "not_null":
                mask = dataframe[column].notna()
            else:
                raise ValueError(f"Unsupported filter operator: {comparator}")

            return dataframe.loc[mask.fillna(False)].copy()

        if operation_name == "select":
            columns = operation.get("columns")
            if not isinstance(columns, list) or not all(
                isinstance(column, str) for column in columns
            ):
                raise ValueError("Select operations require a list of column names.")
            missing = set(columns) - set(dataframe.columns)
            if missing:
                raise ValueError(f"Unknown columns in select: {sorted(missing)}")
            return dataframe[columns].copy()

        if operation_name == "sort":
            column = operation.get("column")
            if column not in dataframe.columns:
                raise ValueError(f"Unknown sort column: {column}")
            ascending = operation.get("ascending", True)
            if not isinstance(ascending, bool):
                raise ValueError("Sort 'ascending' must be true or false.")
            return dataframe.sort_values(column, ascending=ascending)

        if operation_name == "drop_duplicates":
            columns = operation.get("columns")
            if columns is not None:
                if not isinstance(columns, list) or not set(columns).issubset(
                    dataframe.columns
                ):
                    raise ValueError("Duplicate columns must exist in the input data.")
            return dataframe.drop_duplicates(subset=columns)

        if operation_name == "rename":
            mapping = operation.get("mapping")
            if not isinstance(mapping, dict) or not set(mapping).issubset(
                dataframe.columns
            ) or not all(isinstance(name, str) for name in mapping.values()):
                raise ValueError("Rename requires a mapping of existing columns to names.")
            renamed = dataframe.rename(columns=mapping)
            if not renamed.columns.is_unique:
                raise ValueError("Renaming would create duplicate column names.")
            return renamed

        if operation_name == "limit":
            rows = operation.get("rows")
            if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
                raise ValueError("Limit rows must be a non-negative integer.")
            return dataframe.head(rows)

        raise ValueError(f"Unsupported transformation: {operation_name}")