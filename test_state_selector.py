from pathlib import Path
import os
import tempfile
import tkinter as tk
from unittest.mock import Mock, patch
import unittest
import runpy
from state_selector import StateSelector, newest_save, state_labels


class StateSelectorTests(unittest.TestCase):
    def test_newest_save_ignores_backups(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            for name, timestamp in [('old.v3', 100), ('new.v3', 200), ('old.v3.bak', 300), ('scratch.txt', 400)]:
                path = root / name; path.write_text('test'); os.utime(path, (timestamp, timestamp))
            self.assertEqual(newest_save(root).name, 'new.v3')
            with patch('state_selector.newest_save', return_value=root / 'new.v3'):
                self.assertEqual(newest_save(root).name, 'new.v3')

    def test_name_and_id_search_keep_numeric_state_for_all_tabs(self):
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        editor = Mock(state_id=tk.StringVar(), file_path=tk.StringVar())
        picker = StateSelector(root, editor)
        picker.labels = {'0': '0 (Minsk)', '42': '42 (Wyoming)'}
        picker.display.set('mins'); picker.refresh()
        self.assertEqual(tuple(picker['values']), ('0 (Minsk)',))
        self.assertEqual(editor.state_id.get(), '')
        picker.display.set('0 (Minsk)')
        self.assertEqual(editor.state_id.get(), '0')
        editor.state_id.set('42')
        self.assertEqual(picker.display.get(), '42 (Wyoming)')

    def test_reads_save_ids_not_map_region_ids(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'test.v3'
            path.write_text('states={\n database={\n0={\n region="STATE_MINSK"\n}\n42={\n region="STATE_WYOMING"\n}\n}\n}\n')
            self.assertEqual(state_labels(path), {'0': '0 (Minsk)', '42': '42 (Wyoming)'})

    def test_startup_uses_newest_file(self):
        ns = runpy.run_path('v3_editor')
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        with patch.dict(ns['Victoria3SaveEditor'].__init__.__globals__, {'newest_save': lambda folder: Path('chosen.v3')}):
            editor = ns['Victoria3SaveEditor'](root)
            self.assertEqual(editor.file_path.get(), 'chosen.v3')


if __name__ == '__main__': unittest.main()
