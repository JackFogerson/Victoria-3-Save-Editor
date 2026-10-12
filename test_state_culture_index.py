from pathlib import Path
import tempfile
import tkinter as tk
import runpy
import unittest
from state_culture_index import read_state_cultures


class StateCultureTests(unittest.TestCase):
    def test_index_includes_dependents_excludes_other_states_and_empty_pops(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'
            blocks = ['0={\nlocation=42\nculture=25\nworkforce=10\n}',
                      '1={\nlocation=42\nculture=999\ndependents=3\n}',
                      '2={\nlocation=43\nculture=1\nworkforce=10\n}',
                      '3={\nlocation=42\nculture=0\nworkforce=0\n}']
            path.write_text('pops={\n database={\n' + '\n'.join(blocks) + '\n}\n}\n')
            self.assertEqual(read_state_cultures(path), {'42': {'25', '999'}, '43': {'1'}})

    def test_filtered_sources_unrestricted_replacement(self):
        ns = runpy.run_path('v3_editor')
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        editor = ns['Victoria3SaveEditor'](root)
        editor.add_culture_row()
        editor.set_state_cultures({'25', '999'})
        for picker in editor.state_culture_pickers:
            picker.variable.set(''); picker.refresh_results()
            self.assertEqual(tuple(picker['values']), ('25 (french)', '999 (pending)'))
            picker.variable.set('ger'); picker.refresh_results()
            self.assertEqual(tuple(picker['values']), ())
        row = editor.culture_rows[0]
        destination = next(child for child in row['frame'].winfo_children() if isinstance(child, ns['CulturePicker']) and child.allowed_ids is None)
        destination.variable.set('ger'); destination.refresh_results()
        self.assertIn('1 (south german)', destination['values'])
        editor.state_id.set('43')
        self.assertEqual(editor.available_state_cultures, set())


if __name__ == '__main__': unittest.main()
