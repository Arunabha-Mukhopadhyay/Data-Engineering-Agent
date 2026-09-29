import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from utils.data_quality import validate_csv
from utils.etl_tools import ETLTools


class ETLTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.session = Mock()
        self.tools = ETLTools(self.root, self.session)

    @staticmethod
    def response(payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def test_extract_follows_pages_writes_csv_and_redacts_url_query(self):
        self.session.get.side_effect = [
            self.response(
                {
                    "results": [{"name": "one"}],
                    "next": "https://api.test/page/2?token=secret",
                }
            ),
            self.response({"results": [{"name": "two"}], "next": None}),
        ]

        message = self.tools.extract_load(
            "https://api.test/page/1?token=secret",
            "data/extract",
            "csv",
        )

        output = pd.read_csv(self.root / "data/extract/extracted_data.csv")
        run_record = json.loads(
            (self.root / "logs/etl_runs.jsonl").read_text().strip()
        )
        self.assertEqual(output["name"].tolist(), ["one", "two"])
        self.assertIn("2 page(s)", message)
        self.assertEqual(run_record["records"], 2)
        self.assertNotIn("secret", json.dumps(run_record))
        self.assertEqual(self.session.get.call_args.kwargs["timeout"], 30)

    def test_extract_rejects_malformed_results_and_logs_failure(self):
        self.session.get.return_value = self.response({"items": []})

        with self.assertRaisesRegex(ValueError, "results"):
            self.tools.extract_load("https://api.test", "output", "csv")

        run_record = json.loads(
            (self.root / "logs/etl_runs.jsonl").read_text().strip()
        )
        self.assertEqual(run_record["status"], "failed")

    def test_extract_rejects_repeated_pagination_url(self):
        self.session.get.return_value = self.response(
            {"results": [], "next": "https://api.test"}
        )

        with self.assertRaisesRegex(ValueError, "repeated URL"):
            self.tools.extract_load("https://api.test", "output", "csv")

    def test_transform_applies_allowlisted_operations(self):
        source = self.root / "rides.csv"
        pd.DataFrame(
            {"fare": [10, 20, 30], "status": ["completed", "cancelled", "completed"]}
        ).to_csv(source, index=False)

        self.tools.transform_load(
            str(source),
            "transformed",
            "csv",
            [
                {"op": "filter", "column": "fare", "operator": "gte", "value": 20},
                {"op": "select", "columns": ["fare"]},
            ],
        )

        output = pd.read_csv(self.root / "transformed/transformed_data.csv")
        self.assertEqual(output["fare"].tolist(), [20, 30])

    def test_transform_rejects_unknown_operations(self):
        with self.assertRaisesRegex(ValueError, "Unsupported transformation"):
            ETLTools._apply_operation(pd.DataFrame({"fare": [1]}), {"op": "execute"})

    def test_csv_quality_checks_required_values_and_unique_keys(self):
        source = self.root / "users.csv"
        source.write_text("user_id,email\n1,a@example.com\n2,b@example.com\n")

        count = validate_csv(
            source,
            ["user_id", "email"],
            "user_id",
            {"user_id", "email"},
            ("email",),
        )
        self.assertEqual(count, 2)

        source.write_text("user_id,email\n1,a@example.com\n1,b@example.com\n")
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_csv(
                source,
                ["user_id", "email"],
                "user_id",
                {"user_id", "email"},
            )

    def test_sample_database_csvs_pass_quality_checks(self):
        data_dir = Path(__file__).resolve().parent.parent / "data"
        tables = [
            (
                "users.csv",
                ["user_id", "first_name", "last_name", "email", "phone", "city", "province", "user_type", "signup_date", "is_active"],
                {"user_id", "first_name", "last_name", "email", "user_type"},
                ("email",),
            ),
            (
                "vehicles.csv",
                ["vehicle_id", "driver_id", "make", "model", "year", "license_plate", "color", "is_active"],
                {"vehicle_id", "driver_id"},
                ("license_plate",),
            ),
            (
                "rides.csv",
                ["ride_id", "rider_id", "driver_id", "requested_at", "pickup_time", "dropoff_time", "pickup_latitude", "pickup_longitude", "dropoff_latitude", "dropoff_longitude", "distance_km", "fare", "surge_multiplier", "status", "cancellation_reason"],
                {"ride_id", "rider_id", "driver_id"},
                (),
            ),
            (
                "payments.csv",
                ["payment_id", "ride_id", "user_id", "amount", "payment_method", "payment_status", "transaction_id", "payment_time"],
                {"payment_id", "ride_id", "user_id"},
                ("transaction_id",),
            ),
            (
                "ratings.csv",
                ["rating_id", "ride_id", "rider_id", "driver_id", "rating", "comment", "rated_at"],
                {"rating_id", "ride_id", "rider_id", "driver_id"},
                (),
            ),
        ]

        counts = [
            validate_csv(
                data_dir / filename,
                columns,
                columns[0],
                required,
                unique,
            )
            for filename, columns, required, unique in tables
        ]
        self.assertTrue(all(count > 0 for count in counts))


if __name__ == "__main__":
    unittest.main()