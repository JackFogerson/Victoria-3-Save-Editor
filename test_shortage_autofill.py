import runpy
import tempfile
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import patch


class AutofillTests(unittest.TestCase):
    def test_missing_profession_skipped_while_other_changes_apply(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.txt'
            path.write_text('1={\nlocation=253\ntype=clerks\nworkforce=10\n}\n')
            self.editor.file_path.set(str(path)); self.editor.state_id.set('253')
            self.editor.job_inputs['clerks'].set('5')
            self.editor.job_inputs['officers'].set('146')
            with patch.object(self.ns['messagebox'], 'showinfo') as info, patch.object(self.ns['messagebox'], 'showerror') as error:
                self.editor.process_file()
                error.assert_not_called()
                self.assertIn('officers', info.call_args.args[1])
            self.assertIn('workforce=15', path.read_text())

    def test_autofill_leaves_absent_professions_zero(self):
        result = {'state_names': {'253': 'STATE_LIBERIA'}, 'warnings': {}, 'unmapped_professions': [],
                  'states_without_qualification_cache': [], 'workforce_pop_jobs': {'253': ['clerks']},
                  'rows': [{'state_id': '253', 'profession': 'officers', 'estimated_shortage': 146},
                           {'state_id': '253', 'profession': 'clerks', 'estimated_shortage': 5}]}
        self.editor.shortage_autofill.fill(result, '253')
        self.assertEqual(self.editor.job_inputs['officers'].get(), '0')
        self.assertEqual(self.editor.job_inputs['clerks'].get(), '5')
        self.assertIn('officers (146)', self.editor.shortage_autofill.status.get())

    def test_incomplete_estimate_explains_reason_and_does_not_fill(self):
        controller = self.editor.shortage_autofill
        result = {'state_names': {'253': 'STATE_LIBERIA'}, 'warnings': {},
                  'unmapped_professions': ['laborers'], 'states_without_qualification_cache': [], 'rows': []}
        self.editor.job_inputs['laborers'].set('12')
        controller.fill(result, '253')
        self.assertIn('cached workforce totals', controller.status.get())
        self.assertIn('laborers', controller.status.get())
        self.assertEqual(self.editor.job_inputs['laborers'].get(), '12')
        result['unmapped_professions'] = []
        result['warnings'] = {'253': ['Unknown production method: mod_pm']}
        controller.fill(result, '253')
        self.assertIn('mod_pm', controller.status.get())

    def test_unknown_method_does_not_block_supported_shortages(self):
        result={'state_names':{'1':'STATE_TEST'},'warnings':{'1':['Skipped building 9: unknown mod method']},'unmapped_professions':['officers'], 'states_without_qualification_cache':[], 'rows':[{'state_id':'1','profession':'clerks','estimated_shortage':23}]}
        self.editor.job_inputs['officers'].set('17')
        self.editor.shortage_autofill.fill(result,'1')
        self.assertEqual(self.editor.job_inputs['clerks'].get(),'23')
        self.assertEqual(self.editor.job_inputs['officers'].get(),'17')
        self.assertIn('partial estimate',self.editor.shortage_autofill.status.get())

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
