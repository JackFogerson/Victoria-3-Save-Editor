from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from law_editor import law_values, replace_law, scan_laws
from law_tab import LawTab

SOURCE = '''law_test = {
 group = lawgroup_test
 modifier = {
  country_authority_add = 100 # keep comment
  country_test_bool = yes
 }
 on_activate = { if = { limit = { always = yes } set_variable = { name = test value = 1 } } }
 ai_will_do = { always = yes }
}
law_other = { group = lawgroup_test }
'''


class LawTests(unittest.TestCase):
    def test_edit_add_remove_and_preserve_scripts_and_other_laws(self):
        original = SOURCE.replace('\n', '\r\n')
        values = law_values(original, 'law_test')
        values['modifier'] = {'country_authority_add': '250', 'country_new_mult': '0.1'}
        changed = replace_law(original, 'law_test', values)
        self.assertEqual(law_values(changed, 'law_test'), values)
        self.assertIn('# keep comment', changed)
        self.assertIn('ai_will_do = { always = yes }', changed)
        self.assertTrue(changed.endswith('law_other = { group = lawgroup_test }\r\n'))
        self.assertNotIn('\n', changed.replace('\r\n', ''))
        empty = law_values(SOURCE, 'law_other')
        empty['modifier']['country_authority_add'] = '5'
        self.assertEqual(law_values(replace_law(SOURCE, 'law_other', empty), 'law_other')['modifier'], empty['modifier'])

    def test_script_validation(self):
        values = law_values(SOURCE, 'law_test')
        values['on_deactivate'] = '\n remove_modifier = test\n'
        self.assertEqual(law_values(replace_law(SOURCE, 'law_test', values), 'law_test'), values)
        values['on_activate'] = '} injected = { '
        with self.assertRaises(ValueError): replace_law(SOURCE, 'law_test', values)

    def test_tab_select_update_and_backup(self):
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        with patch('law_tab.DEFAULT_LAWS', Path('missing-laws-fixture')):
            tab = LawTab(ttk.Notebook(root))
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'laws.txt'; path.write_bytes(b'\xef\xbb\xbf' + SOURCE.encode())
            original = path.read_bytes()
            tab.folder.set(folder); tab.load_folder()
            self.assertEqual(len(tab.labels), 2)
            tab.query.set('law_test'); tab.select_law()
            tab.effect.set('country_authority_add'); tab.value.set('300'); tab.add(); tab.save()
            self.assertEqual(law_values(path.read_text(encoding='utf-8-sig'), 'law_test')['modifier']['country_authority_add'], '300')
            self.assertEqual(next(Path(folder).glob('*.bak')).read_bytes(), original)
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))


if __name__ == '__main__': unittest.main()
