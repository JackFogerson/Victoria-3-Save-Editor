from decimal import Decimal
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk


class CulturePercentageTests(unittest.TestCase):
    def test_each_matching_pop_scales_across_jobs_and_religions(self):
        editor = runpy.run_path('v3_editor')['Victoria3SaveEditor']
        stats = {'groups': 0, 'before': 0, 'after': 0}
        for job, religion in [('laborers', 'catholic'), ('clergymen', 'sunni'), ('farmers', 'orthodox')]:
            lines = f'1={{\nlocation=42\ntype={job}\nreligion={religion}\nculture=25\nworkforce=100\ndependents=200\n}}\n'.splitlines(True)
            changed = ''.join(editor.scale_pop_block(lines, '42', '25', Decimal('1.1'), stats))
            self.assertIn('workforce=110\n', changed)
            self.assertIn('dependents=220\n', changed)
            self.assertIn(f'type={job}\n', changed)
            self.assertIn(f'religion={religion}\n', changed)
        self.assertEqual(stats, {'groups': 3, 'before': 900, 'after': 990})

    def test_scaling_workers_dependents_and_filters(self):
        editor = runpy.run_path('v3_editor')['Victoria3SaveEditor']
        lines = '1={\nlocation=42\ntype=laborers\nculture=25\nworkforce=100\ndependents=200\n}\n'.splitlines(True)
        stats = {'groups': 0, 'before': 0, 'after': 0}
        reduced = ''.join(editor.scale_pop_block(lines, '42', '25', Decimal('.1'), stats))
        self.assertIn('workforce=10\n', reduced)
        self.assertIn('dependents=20\n', reduced)
        self.assertEqual(stats, {'groups': 1, 'before': 300, 'after': 30})
        self.assertEqual(editor.scale_pop_block(lines, '43', '25', Decimal('2'), stats), lines)
        self.assertEqual(editor.scale_pop_block(lines, '42', '2', Decimal('2'), stats), lines)
        increased = ''.join(editor.scale_pop_block(lines, '42', '25', Decimal('1.1'), stats))
        self.assertIn('workforce=110\n', increased)
        self.assertIn('dependents=220\n', increased)

    def test_percentage_apply_is_independent_and_creates_backup(self):
        ns = runpy.run_path('v3_editor')
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        editor = ns['Victoria3SaveEditor'](root)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.txt'
            original = '1={\nlocation=42\ntype=laborers\nculture=25\nworkforce=100\ndependents=200\n}\n2={\nlocation=42\ntype=laborers\nculture=25\ndependents=50\n}\n'
            path.write_text(original)
            editor.file_path.set(str(path)); editor.state_id.set('42')
            editor.job_inputs['laborers'].set('999')
            editor.scale_culture.set('25 (french)'); editor.scale_percent.set('-90')
            with patch.object(ns['messagebox'], 'showerror') as errors:
                editor.apply_culture_percentage(); errors.assert_not_called()
            self.assertIn('workforce=10', path.read_text())
            self.assertIn('dependents=5\n', path.read_text())
            self.assertEqual(next(Path(folder).glob('*.bak')).read_text(), original)
            self.assertIn('350 to 35', editor.scale_status.get())
            before = path.read_bytes()
            for invalid in ('-101', 'NaN', 'Infinity', 'abc'):
                editor.scale_percent.set(invalid)
                with patch.object(ns['messagebox'], 'showerror') as errors:
                    editor.apply_culture_percentage(); errors.assert_called_once()
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__': unittest.main()
