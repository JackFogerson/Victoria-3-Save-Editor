import tempfile
from pathlib import Path
import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch

from culture_definitions import attributes, catalog, definitions, replace_attributes, save_changes
from culture_tab import CultureDefinitionTab


SAMPLE = '''# ignored { comment
north_german = {
 color = rgb { 1 2 3 }
 religion = protestant # keep me
 language = language_germanophone
 obsessions = { meat coffee } # trailing comment
 names = { "a } # b" other }
}
dutch = {
 religion = catholic
 language = language_dutch
 taboos = { wine # this is not a good
 }
}
'''


class DefinitionTests(unittest.TestCase):
    def test_catalog_ignores_comments_and_preserves_order(self):
        data = catalog(SAMPLE)
        self.assertEqual(data['cultures'], ['north_german', 'dutch'])
        self.assertEqual(data['goods'], ['coffee', 'meat', 'wine'])
        self.assertEqual(data['religions'], ['catholic', 'protestant'])

    def test_edit_only_selected_fields(self):
        original = SAMPLE.replace('\n', '\r\n')
        changed = replace_attributes(original, 'north_german', {
            'religion': 'catholic', 'language': 'language_dutch',
            'obsessions': [], 'taboos': ['wine', 'meat']})
        self.assertEqual(attributes(definitions(changed)['north_german']), {
            'religion': 'catholic', 'language': 'language_dutch',
            'obsessions': [], 'taboos': ['wine', 'meat']})
        self.assertEqual(changed[changed.index('dutch ='):], original[original.index('dutch ='):])
        self.assertIn('# keep me\r\n', changed)
        self.assertIn('names = { "a } # b" other }', changed)
        self.assertNotIn('\n', changed.replace('\r\n', ''))
        with self.assertRaises(ValueError):
            replace_attributes(SAMPLE, 'dutch', {'religion': 'bad\ninjection=yes'})
        with self.assertRaises(ValueError):
            definitions('broken = {')

    def test_backup_and_external_change_protection(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'cultures.txt'
            original = b'\xef\xbb\xbf' + SAMPLE.encode()
            path.write_bytes(original)
            backup = save_changes(path, original, b'updated')
            self.assertIsNone(backup)
            self.assertEqual(path.read_bytes(), b'updated')
            with self.assertRaises(ValueError):
                save_changes(path, original, b'overwrite')
            self.assertEqual(path.read_bytes(), b'updated')

    def test_tab_load_edit_save(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        notebook = ttk.Notebook(root)
        with patch('culture_tab.DEFAULT_CULTURE_FILE', Path('nonexistent-culture-test.txt')):
            tab = CultureDefinitionTab(notebook, {'0': 'north german'})
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'cultures.txt'
            original = b'\xef\xbb\xbf' + SAMPLE.encode()
            path.write_bytes(original)
            tab.path.set(str(path))
            tab.load_file()
            tab.selection.set('0')
            tab.load_culture()
            self.assertEqual(tab.loaded_culture, 'north_german')
            self.assertEqual(tab.fields['religion'].get(), 'protestant')
            self.assertEqual(tab.goods_lists['obsessions'].get(0, 'end'), tab.goods_lists['taboos'].get(0, 'end'))
            tab.fields['religion'].set('catholic')
            tab.goods_lists['obsessions'].selection_clear(0, 'end')
            tab.save()
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            data = attributes(definitions(path.read_text(encoding='utf-8-sig'))['north_german'])
            self.assertEqual(data['religion'], 'catholic')
            self.assertEqual(data['obsessions'], [])
            self.assertEqual(len(list(Path(folder).glob('*.bak'))), 0)
            self.assertFalse(tab.dirty())


if __name__ == '__main__':
    unittest.main()
