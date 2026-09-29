import csv
from pathlib import Path


def validate_csv(
    file_path: str | Path,
    expected_columns: list[str],
    primary_key: str,
    required_columns: set[str],
    unique_columns: tuple[str, ...] = (),
) -> int:
    """Validate CSV shape, required values, and key uniqueness before loading."""
    path = Path(file_path)
    seen_values = {column: set() for column in (primary_key, *unique_columns)}

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"{path.name} columns must be {expected_columns}; "
                f"found {reader.fieldnames}."
            )

        row_count = 0
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"{path.name}:{row_number} has extra fields.")

            missing = [
                column
                for column in required_columns
                if row.get(column) is None or not row[column].strip()
            ]
            if missing:
                raise ValueError(
                    f"{path.name}:{row_number} is missing required values: "
                    f"{', '.join(sorted(missing))}."
                )

            for column, values in seen_values.items():
                value = row.get(column, "").strip()
                if not value:
                    continue
                if value in values:
                    raise ValueError(
                        f"{path.name}:{row_number} duplicates {column}={value!r}."
                    )
                values.add(value)
            row_count += 1

    return row_count