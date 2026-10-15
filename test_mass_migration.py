from pathlib import Path
import tempfile
import unittest
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from mass_migration import index_save, create_migration, updated_records, field


SAVE = '''SAV0100test
date=1836.1.1
country_manager={
 database={
1={
	definition="FRA"
}
2={
	definition="GRE"
}
 }
}
states={
 database={
10={
	country=1
	region="STATE_ORIGIN"
}
20={
	country=2
	region="STATE_DESTINATION"
	pop_needs={ { goods={ 1=5 } } }
}
 }
}
cultures={
 database={
25={
	type=french
	random_seed=123
	migration={ { state=99 origin=1 date=1835.1.1 expiry_date=1837.1.1 active=yes } }
}
 }
}
unrelated={ data="keep this" }
'''


class MigrationTests(unittest.TestCase):
    def test_choices_load_automatically_and_all_three_fields_autocomplete(self):
        from migration_tab import MigrationTab
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'
            path.write_text(SAVE)
            root = tk.Tk()
            try:
                editor = SimpleNamespace(file_path=tk.StringVar(), state_id=tk.StringVar())
                notebook = ttk.Notebook(root); notebook.pack(fill='both', expand=True)
                tab = MigrationTab(notebook, editor, {'25': 'French'})
                root.update()
                editor.file_path.set(str(path))
                deadline = time.monotonic() + 10
                while tab.index is None and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertIsNotNone(tab.index)
                for key, query, expected in [('culture', 'fren', '25'), ('source', 'fra', '1'), ('destination', 'dest', '20')]:
                    picker = tab.pickers[key]
                    picker.focus_force(); root.update()
                    picker.insert(0, query); root.update()
                    suggestion = tab.suggestions[list(tab.pickers).index(key)]
                    self.assertTrue(suggestion.popup.winfo_viewable(), key)
                    self.assertEqual(suggestion.list.size(), 1)
                    picker.event_generate('<Return>'); root.update()
                    self.assertEqual(tab.resolve(key), expected)
                    tab.variables[key].set(expected); root.update()
                    self.assertEqual(tab.resolve(key), expected)
                # The newest-save refresh may write the same path again.
                editor.file_path.set(str(path))
                self.assertIsNone(tab.index)
                deadline = time.monotonic() + 10
                while tab.index is None and time.monotonic() < deadline:
                    root.update(); time.sleep(0.01)
                self.assertIsNotNone(tab.index)
            finally:
                root.destroy()

    def test_atomic_linked_records_without_backup_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'
            original = SAVE.replace('\n', '\r\n').encode()
            path.write_bytes(original)
            index = index_save(path)
            expiry = create_migration(index, '25', '1', '20', 366)
            self.assertEqual(expiry, '1837.1.1')
            self.assertEqual(list(Path(folder).iterdir()), [path])
            changed = path.read_bytes().decode()
            self.assertIn('\t\t\tdate=1837.1.1\r\n', changed)
            self.assertIn('\t\t\texpiry_date=1841.1.1\r\n', changed)
            self.assertIn('\t\tculture=25\r\n\t\tcountry=1', changed)
            self.assertIn('\t\t\tstate=20', changed)
            self.assertIn('state=99 origin=1', changed)
            self.assertTrue(changed.endswith('unrelated={ data="keep this" }\r\n'))
            self.assertNotIn('\n', changed.replace('\r\n', ''))
            new_index = index_save(path)
            self.assertTrue(new_index['states']['20']['occupied'])
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'already has'):
                create_migration(new_index, '25', '1', '20', 365)
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaisesRegex(ValueError, 'changed'):
                create_migration(index, '25', '1', '20', 365)

    def test_create_missing_list_and_validate_parameters(self):
        state = '20={\n country=2\n}\n'
        culture = '25={\n type=french\n}\n'
        state_new, culture_new, expiry = updated_records(state, culture, '25', '1', '20', '1836-01-01', 1461)
        self.assertEqual(expiry, '1840.1.1')
        self.assertIsNotNone(field(state_new, 'mass_migration'))
        self.assertIsNotNone(field(culture_new, 'migration'))
        for days in (0, -1, 36501):
            with self.assertRaises(ValueError): updated_records(state, culture, '25', '1', '20', '1836-01-01', days)
        with self.assertRaises(ValueError): updated_records(state, culture, '25 }', '1', '20', '1836-01-01', 365)

    def test_same_country_and_external_changes_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'; path.write_text(SAVE)
            index = index_save(path)
            with self.assertRaisesRegex(ValueError, 'another country'): create_migration(index, '25', '2', '20', 365)
            with path.open('a') as handle: handle.write('\n')
            with self.assertRaisesRegex(ValueError, 'changed'): create_migration(index, '25', '1', '20', 365)


if __name__ == '__main__': unittest.main()
