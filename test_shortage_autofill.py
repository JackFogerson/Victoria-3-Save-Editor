import runpy
import tempfile
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import patch


class AutofillTests(unittest.TestCase):
    def setUp(self):
        self.ns = runpy.run_path('v3_editor')
        self.root = tk.Tk(); self.root.withdraw()
        self.editor = self.ns['Victoria3SaveEditor'](self.root)
        self.addCleanup(self.root.destroy)

    def test_fill_shortfall_clear_next_state_and_keep_manual_override(self):
        controller = self.editor.shortage_autofill
        result = {'state_names': {'0': 'STATE_MINSK', '75': 'STATE_ALABAMA'},
                  'warnings': {}, 'unmapped_professions': [], 'states_without_qualification_cache': [],
                  'rows': [{'state_id': '0', 'profession': 'clergymen', 'estimated_shortage': 188}]}
        controller.fill(result, '0')
        self.assertEqual(self.editor.job_inputs['clergymen'].get(), '188')
        self.editor.state_id.set('75')
        self.assertTrue(all(v.get() == '0' for v in self.editor.job_inputs.values()))
        controller.fill(result, '75')
        self.assertIn('no estimated', controller.status.get())
        controller.enabled.set(False)
        self.editor.job_inputs['clergymen'].set('7')
        self.editor.state_id.set('0')
        self.assertEqual(self.editor.job_inputs['clergymen'].get(), '7')

    def test_background_result_uses_latest_state(self):
        controller = self.editor.shortage_autofill
        self.editor.state_id.set('75')
        result = {'state_names': {'75': 'STATE_ALABAMA'}, 'warnings': {},
                  'unmapped_professions': [], 'states_without_qualification_cache': [], 'rows': []}
        controller.results.put(('key', controller.revision, result, None))
        with patch.object(controller, 'key', return_value='key'):
            controller.poll()
        self.assertIn('Alabama', controller.status.get())
        self.editor.job_inputs['farmers'].set('17')
        controller.results.put(('key', controller.revision - 1, result, None))
        with patch.object(controller, 'key', return_value='key'):
            controller.poll()
        self.assertEqual(self.editor.job_inputs['farmers'].get(), '17')

    def test_small_addition_distributed_exactly(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.txt'
            source = ''.join(f'{i}={{\nlocation=0\ntype=clergymen\nworkforce=10\n}}\n' for i in range(3))
            path.write_text(source)
            self.editor.file_path.set(str(path))
            self.editor.state_id.set('0')
            self.editor.job_inputs['clergymen'].set('1')
            with patch.object(self.ns['messagebox'], 'showinfo'), patch.object(self.ns['messagebox'], 'showerror') as errors:
                self.editor.process_file()
                errors.assert_not_called()
            self.assertEqual(path.read_text().count('workforce=11'), 1)
            self.assertEqual(path.read_text().count('workforce=10'), 2)


if __name__ == '__main__': unittest.main()
