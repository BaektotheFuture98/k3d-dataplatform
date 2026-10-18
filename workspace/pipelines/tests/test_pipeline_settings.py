import os
import unittest
from unittest.mock import patch

from pipeline_runtime.settings import BronzeSettings, SemanticSettings


class PipelineSettingsTests(unittest.TestCase):
    def test_environment_overrides_tables_and_checkpoint(self):
        with patch.dict(os.environ, {
            'BRONZE_TABLE': 'lakehouse.test_scope.bronze',
            'SILVER_TABLE': 'lakehouse.test_scope.silver',
            'CHECKPOINT_URI': 's3a://warehouse/platform-validation/test/checkpoint',
            'MAX_FILES_PER_MICRO_BATCH': '7',
        }, clear=True):
            settings = BronzeSettings()
        self.assertEqual(settings.bronze_table, 'lakehouse.test_scope.bronze')
        self.assertEqual(settings.silver_table, 'lakehouse.test_scope.silver')
        self.assertEqual(settings.max_files_per_micro_batch, 7)

    def test_rejects_invalid_table_checkpoint_and_batch_limit(self):
        for values in [
            {'BRONZE_TABLE': 'bronze; DROP TABLE gold'},
            {'CHECKPOINT_URI': 's3://warehouse/checkpoint'},
            {'CHECKPOINT_URI': 's3a://warehouse/a path'},
            {'CHECKPOINT_URI': 's3a://user:password@warehouse/path'},
            {'MAX_FILES_PER_MICRO_BATCH': '0'},
            {'TRIGGER_INTERVAL': ''},
        ]:
            with self.subTest(values=values), patch.dict(os.environ, values, clear=True):
                with self.assertRaises(ValueError):
                    BronzeSettings()

    def test_semantic_settings_require_key_model_and_ontology_version(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                SemanticSettings()
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-secret-do-not-log',
            'SEMANTIC_LLM_MODEL': 'test-model', 'ONT_VERSION': 'v1',
            'SEMANTIC_BATCH_SIZE': '101',
        }, clear=True):
            with self.assertRaises(ValueError) as failure:
                SemanticSettings()
            self.assertNotIn('test-secret-do-not-log', str(failure.exception))

    def test_semantic_table_overrides_and_secret_repr(self):
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-secret-do-not-log',
            'SEMANTIC_LLM_MODEL': 'test-model', 'ONT_VERSION': 'v1',
            'GOLD_TABLE': 'lakehouse.test_scope.gold',
            'BATCH_JOB_TABLE': 'lakehouse.test_scope.jobs',
        }, clear=True):
            settings = SemanticSettings()
        self.assertEqual(settings.gold_table, 'lakehouse.test_scope.gold')
        self.assertEqual(settings.batch_job_table, 'lakehouse.test_scope.jobs')
        self.assertNotIn('test-secret-do-not-log', repr(settings))


if __name__ == '__main__':
    unittest.main()
