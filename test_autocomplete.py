import runpy
import tkinter as tk
import unittest


class AutocompleteTests(unittest.TestCase):
    def test_live_typing_selection_and_manual_id(self):
        ns = runpy.run_path('v3_editor')
        root = tk.Tk()
        self.addCleanup(root.destroy)
        variable = tk.StringVar()
        picker = ns['CulturePicker'](root, variable)
        picker.pack()
        root.update()
        picker.focus_force()
        root.update()
        picker.insert(0, 'f')
        root.update()
        suggestions = picker.suggestions
        self.assertTrue(suggestions.popup.winfo_viewable())
        self.assertEqual(root.focus_get(), picker)
        self.assertIn('25 (french)', suggestions.list.get(0, 'end'))
        self.assertIn('4 (flemish)', suggestions.list.get(0, 'end'))
        picker.insert('end', 'renc')
        root.update()
        self.assertEqual(variable.get(), 'frenc')
        self.assertEqual(suggestions.list.get(0, 'end'), ('25 (french)',))
        picker.event_generate('<Return>')
        root.update()
        self.assertEqual(variable.get(), '25 (french)')
        self.assertFalse(suggestions.popup.winfo_viewable())
        variable.set('999')
        root.update()
        self.assertEqual(suggestions.list.get(0), '999 (pending)')
        picker.event_generate('<Escape>')
        root.update()
        self.assertEqual(variable.get(), '999')
        self.assertFalse(suggestions.popup.winfo_viewable())


if __name__ == '__main__':
    unittest.main()
