from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mass_migration import signature
from save_io import commit_save
import os


class SaveIOTests(unittest.TestCase):
    def test_retry_replaces_once_and_preserves_original_backup(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path, temp, backup = [Path(folder) / name for name in ('save.v3', 'edit.tmp', 'save.bak')]
            path.write_bytes(b'original'); temp.write_bytes(b'edited')
            replace = os.replace
            calls = []
            def locked_then_replace(a, b):
                calls.append(1)
                if len(calls) == 1: raise PermissionError('locked')
                replace(a, b)
            with patch('save_io.os.replace', side_effect=locked_then_replace), patch('save_io.time.sleep'):
                commit_save(temp, path, signature(path), backup)
            self.assertEqual(path.read_bytes(), b'edited')
            self.assertEqual(backup.read_bytes(), b'original')
            self.assertEqual(len(calls), 2)

    def test_external_change_during_retry_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path, temp, backup = [Path(folder) / name for name in ('save.v3', 'edit.tmp', 'save.bak')]
            path.write_bytes(b'original'); temp.write_bytes(b'edited')
            with patch('save_io.os.replace', side_effect=PermissionError), patch('save_io.time.sleep', side_effect=lambda _: path.write_bytes(b'new game save')):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    commit_save(temp, path, signature(path), backup)
            self.assertEqual(path.read_bytes(), b'new game save')
