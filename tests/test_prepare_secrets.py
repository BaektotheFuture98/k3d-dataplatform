"""Pure formatting tests with fixture strings; no real secrets or API requests."""
import importlib.util
import unittest
from pathlib import Path


class SecretFormattingTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "configs" / "prepare-secrets.py"
        self.assertTrue(path.exists(), "Secret preparation helper is not implemented")
        spec = importlib.util.spec_from_file_location("prepare_secrets", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_airflow_password_is_url_encoded_without_changing_database_contract(self):
        self.assertEqual(
            self.module.airflow_fields("fixture:@/?# %"),
            {"connection": "postgresql://airflow_user:fixture%3A%40%2F%3F%23%20%25@postgres:5432/airflow_meta"},
        )

    def test_neo4j_chart_and_connector_password_fields_remain_consistent(self):
        self.assertEqual(
            self.module.neo4j_fields("fixture-password"),
            {"NEO4J_AUTH": "neo4j/fixture-password", "neo4j-password": "fixture-password"},
        )

    def test_empty_password_is_rejected(self):
        for factory in (self.module.airflow_fields, self.module.neo4j_fields):
            with self.assertRaises(ValueError):
                factory("")


if __name__ == "__main__":
    unittest.main()
