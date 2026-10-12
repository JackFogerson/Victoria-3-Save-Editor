import runpy
import tkinter as tk
import unittest


class AutocompleteTests(unittest.TestCase):
    def test_mouse_selection_after_popup_takes_focus(self):
        ns = runpy.run_path('v3_editor')
        root = tk.Tk()
        self.addCleanup(root.destroy)
        variable = tk.StringVar()
        picker = ns['CulturePicker'](root, variable)
        picker.pack()
        root.update()
        picker.focus_force()
        root.update()
        picker.insert(0, 'ger')
        root.update()
        suggestions = picker.suggestions
        results = suggestions.list.get(0, 'end')
        index = results.index('1 (south german)')
        # Reproduce Windows moving focus before dispatching the mouse press.
        suggestions.list.focus_force()
        root.update()
        self.assertEqual(variable.get(), 'ger')
        self.assertTrue(suggestions.popup.winfo_viewable())
        x, y, width, height = suggestions.list.bbox(index)
        suggestions.list.event_generate('<ButtonPress-1>', x=x + 3, y=y + height // 2)
        root.update()
        self.assertEqual(variable.get(), '1 (south german)')
        self.assertEqual(ns['culture_id_from_input'](variable.get()), '1')
        self.assertFalse(suggestions.popup.winfo_viewable())

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
