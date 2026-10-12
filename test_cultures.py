import runpy
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch


editor_module = runpy.run_path(str(Path(__file__).with_name('v3_editor')))


class CultureTests(unittest.TestCase):
    def test_names_labels_and_manual_ids(self):
        parse = editor_module['culture_id_from_input']
        for value, expected in [('NORTH GERMAN', '0'), ('0 (north german)', '0'),
                                ('999 (pending)', '999'), ('999', '999'),
                                ('custom_culture', 'custom_culture')]:
            self.assertEqual(parse(value), expected)
        self.assertEqual(editor_module['culture_label']('999'), '999 (pending)')
        with self.assertRaises(ValueError):
            parse('unknown culture name')

    def test_picker_and_save_mapping(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = editor_module['Victoria3SaveEditor'](root)
        editor.add_culture_row('0')
        row = editor.culture_rows[0]
        pickers = [child for child in row['frame'].winfo_children()
                   if isinstance(child, editor_module['CulturePicker'])]
        self.assertEqual(row['tgt_var'].get(), '0 (north german)')
        row['new_var'].set('GERMAN')
        pickers[1].refresh_results()
        self.assertEqual(tuple(pickers[1]['values']), ('0 (north german)', '311 (east german)'))
        row['new_var'].set('999')
        pickers[1].refresh_results()
        self.assertIn('999 (pending)', pickers[1]['values'])
        pickers[1].format_selection()
        self.assertEqual(row['new_var'].get(), '999 (pending)')
        editor.file_path.set(str(Path(__file__)))
        editor.state_id.set('42')
        with patch.object(editor, 'stream_edit_save') as write, patch.object(editor_module['messagebox'], 'showinfo'):
            editor.process_file()
            self.assertEqual(write.call_args.args[3], {'0': '999'})
        lines = '1={\nlocation=42\ntype=laborers\nculture=0\n}\n'.splitlines(True)
        result = ''.join(editor.modify_pop_block(lines, '42', {}, {'0': '999'}, {}))
        self.assertIn('culture=999\n', result)
        self.assertNotIn('(pending)', result)


if __name__ == '__main__':
    unittest.main()
