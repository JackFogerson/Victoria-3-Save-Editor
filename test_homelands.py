from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch
from state_homelands import resolve_state, history_states, homelands, replace_homelands
from homeland_tab import HomelandTab

HISTORY = '''STATES = {
 "s:STATE_MINSK" = {
  create_state = { country = c:RUS owned_provinces = { x123 } }
  add_homeland = cu:russian # keep comment
  add_homeland = cu:byelorussian
 }
 s:STATE_OTHER = { add_homeland = cu:dutch }
}
'''
SAVE = '''states={
 database={
 0={ nested={ region="STATE_WRONG" } region="STATE_MINSK" }
 42={ region="STATE_OTHER" }
 99={ region="STATE_MINSK" }
 }
}
'''


class HomelandTests(unittest.TestCase):
    def test_exact_save_mapping_and_split_states(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.txt'
            path.write_text(SAVE)
            self.assertEqual(resolve_state(path, '0'), 'STATE_MINSK')
            self.assertEqual(resolve_state(path, '42'), 'STATE_OTHER')
            self.assertEqual(resolve_state(path, '99'), 'STATE_MINSK')
            with self.assertRaises(ValueError):
                resolve_state(path, '100')
            with self.assertRaises(ValueError):
                resolve_state(path, '')

    def test_add_remove_clear_preserves_other_content(self):
        source = HISTORY.replace('\n', '\r\n')
        changed = replace_homelands(source, 'STATE_MINSK', ['byelorussian', 'north_german', 'north_german'])
        self.assertEqual(homelands(history_states(changed)['STATE_MINSK']), ['byelorussian', 'north_german'])
        self.assertIn('# keep comment', changed)
        self.assertIn('create_state = { country = c:RUS owned_provinces = { x123 } }', changed)
        self.assertIn('s:STATE_OTHER = { add_homeland = cu:dutch }', changed)
        self.assertNotIn('\n', changed.replace('\r\n', ''))
        cleared = replace_homelands(changed, 'STATE_MINSK', [])
        self.assertEqual(homelands(history_states(cleared)['STATE_MINSK']), [])
        self.assertEqual(replace_homelands(source, 'STATE_MINSK', ['russian', 'byelorussian']), source)

    def test_ui_load_add_remove_save_and_context_guard(self):
        root = tk.Tk(); root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            save = Path(folder) / 'save.txt'; save.write_text(SAVE)
            history = Path(folder) / 'states.txt'
            original = b'\xef\xbb\xbf' + HISTORY.encode()
            history.write_bytes(original)
            editor = Mock(file_path=tk.StringVar(value=str(save)), state_id=tk.StringVar(value='0'))
            tab = HomelandTab(ttk.Notebook(root), editor, {'0': 'north german'})
            tab.mode.set('New-game history')
            tab.path.set(str(history)); tab.load()
            self.assertEqual(tab.region, 'STATE_MINSK')
            tab.query.set('0'); tab.add(); tab.add()
            self.assertEqual(tab.current.count('north_german'), 1)
            tab.list.selection_set(0); tab.remove()
            editor.state_id.set('42')
            with patch('homeland_tab.messagebox.showerror') as error:
                tab.save(); error.assert_called_once()
            self.assertEqual(history.read_bytes(), original)
            editor.state_id.set('0'); tab.save()
            self.assertEqual(homelands(history_states(history.read_text(encoding='utf-8-sig'))['STATE_MINSK']), ['byelorussian', 'north_german'])
            self.assertTrue(history.read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertEqual(list(Path(folder).glob('*.bak')), [])


if __name__ == '__main__':
    unittest.main()
