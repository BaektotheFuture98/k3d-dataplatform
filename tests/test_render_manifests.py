"""Checks for the file renderer; never contacts Kubernetes or starts workloads."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render-manifests.py"


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE_PATH.is_file(), "Manifest renderer is not implemented yet")
        spec = importlib.util.spec_from_file_location("render_manifests", MODULE_PATH)
        self.renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.renderer)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.values = self.root / "images.env"
        self.output = self.root / "rendered"

    def test_missing_image_rejects_entire_render_without_partial_output(self):
        (self.source / "one.yaml").write_text("image: __SPARK_IMAGE__\n")
        (self.source / "two.yaml").write_text("image: __COLLECTOR_IMAGE__\n")
        self.values.write_text("SPARK_IMAGE=docker.io/acme/spark:4.1.2\n")
        with self.assertRaisesRegex(ValueError, "COLLECTOR_IMAGE"):
            self.renderer.render(self.source, self.values, self.output)
        self.assertFalse(self.output.exists())

    def test_replaces_image_and_preserves_unrelated_shell_and_secret_references(self):
        original = "image: __SPARK_IMAGE__\ncommand: ['echo', '$HOME']\nsecretName: postgres-credentials\n"
        (self.source / "spark.yaml").write_text(original)
        self.values.write_text("SPARK_IMAGE=docker.io/acme/spark:4.1.2\n")
        self.renderer.render(self.source, self.values, self.output)
        self.assertEqual(
            (self.output / "spark.yaml").read_text(),
            "image: docker.io/acme/spark:4.1.2\ncommand: ['echo', '$HOME']\nsecretName: postgres-credentials\n",
        )
        self.assertEqual((self.source / "spark.yaml").read_text(), original)

    def test_existing_output_is_preserved(self):
        (self.source / "one.yaml").write_text("kind: Service\n")
        self.values.write_text("")
        self.output.mkdir()
        sentinel = self.output / "user.yaml"
        sentinel.write_text("keep\n")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.renderer.render(self.source, self.values, self.output)
        self.assertEqual(sentinel.read_text(), "keep\n")

    def test_source_output_overlap_is_rejected(self):
        self.values.write_text("")
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.renderer.render(self.source, self.values, self.source / "rendered")

    def test_image_value_cannot_inject_yaml_or_shell_expansion(self):
        for value in ("docker.io/acme/spark:4.1.2 another: value", "$(touch /tmp/unwanted)", "docker.io/acme/spark:latest", "__SPARK_IMAGE__"):
            with self.subTest(value=value):
                self.values.write_text("SPARK_IMAGE=" + value + "\n")
                with self.assertRaises(ValueError):
                    self.renderer.load_values(self.values)

    def test_empty_scaffold_files_are_skipped_and_nested_files_are_preserved(self):
        (self.source / "empty.yaml").write_text("")
        (self.source / "nested").mkdir()
        (self.source / "nested" / "service.yaml").write_text("kind: Service\n")
        self.values.write_text("")
        self.assertEqual(self.renderer.render(self.source, self.values, self.output), 1)
        self.assertFalse((self.output / "empty.yaml").exists())
        self.assertEqual((self.output / "nested" / "service.yaml").read_text(), "kind: Service\n")

    def test_airflow_chart_repository_and_tag_are_derived_from_one_full_image(self):
        (self.source / "values.yaml").write_text("defaultAirflowRepository: __AIRFLOW_REPOSITORY__\ndefaultAirflowTag: __AIRFLOW_TAG__\n")
        self.values.write_text("AIRFLOW_IMAGE=docker.io/acme/airflow:3.0.2-kubernetes-10.24.0\n")
        self.renderer.render(self.source, self.values, self.output)
        self.assertEqual(
            (self.output / "values.yaml").read_text(),
            "defaultAirflowRepository: docker.io/acme/airflow\ndefaultAirflowTag: 3.0.2-kubernetes-10.24.0\n",
        )

    def test_airflow_digest_is_rejected_until_chart_digest_mapping_is_supported(self):
        self.values.write_text("AIRFLOW_IMAGE=docker.io/acme/airflow@sha256:" + "a" * 64 + "\n")
        with self.assertRaisesRegex(ValueError, "Airflow.*tag"):
            self.renderer.load_values(self.values)

    def test_catalog_double_underscore_env_name_is_not_an_image_token(self):
        source = "env:\n  - name: CATALOG_S3_PATH__STYLE__ACCESS\n    value: 'true'\nimage: __SPARK_IMAGE__\n"
        (self.source / "catalog.yaml").write_text(source)
        self.values.write_text("SPARK_IMAGE=docker.io/acme/spark:4.1.2\n")
        self.renderer.render(self.source, self.values, self.output)
        self.assertEqual(
            (self.output / "catalog.yaml").read_text(),
            source.replace("__SPARK_IMAGE__", "docker.io/acme/spark:4.1.2"),
        )


if __name__ == "__main__":
    unittest.main()
