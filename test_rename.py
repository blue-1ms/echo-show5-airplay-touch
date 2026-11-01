"""Offline receiver rename safety and persistence checks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from test_discovery import server

class RenameTests(unittest.TestCase):
    source = '# general = { name = "Example"; };\ngeneral = { name = "Echo 2"; interpolation = "vernier"; };\nmetadata = { name = "Keep"; };'

    def test_changes_only_actual_name_and_escapes_strings(self):
        value = 'Room "A" \\ Studio'
        changed, name = server.renamed_config(self.source, value)
        self.assertEqual(name, value)
        self.assertIn('name = "Example"', changed)
        self.assertIn('name = "Keep"', changed)
        self.assertIn('interpolation = "vernier"', changed)
        self.assertEqual(server.renamed_config(changed, 'Echo 2')[0], self.source)

    def test_invalid_names_and_ambiguous_config_are_rejected(self):
        for value in ('', '   ', '%h', 'a\nb', 'x'*51, None, 42):
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.renamed_config(self.source, value)
        for config in ('# general = { name = "Example"; };', 'general={name="A";name="B";};'):
            with self.assertRaises(ValueError):
                server.renamed_config(config, 'Living Room')

    def test_persistent_success_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'shairport-sync.conf'
            config.write_text(self.source, encoding='utf-8')
            core = Mock()
            core.Get.return_value = 'Living Room'
            with patch.object(server, 'CONFIG_PATH', config), patch.object(server, 'restart_receiver') as restart, patch.object(server, 'interfaces', return_value=(core, None, None)):
                server.rename_receiver('Living Room')
                self.assertIn('name = "Living Room"', config.read_text())
                restart.assert_called_once()
                restart.reset_mock()
                server.rename_receiver('Living Room')
                restart.assert_not_called()
                restart.side_effect = RuntimeError('stop failed')
                with self.assertRaises(RuntimeError):
                    server.rename_receiver('Kitchen')
                self.assertIn('name = "Living Room"', config.read_text())
                self.assertTrue(config.with_suffix('.before-rename').exists())

if __name__ == '__main__':
    unittest.main()
