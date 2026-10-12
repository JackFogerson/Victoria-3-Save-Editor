import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch
from culture_definitions import definitions
from state_resources import scan_regions, resource_values, replace_resources
from state_resource_tab import StateResourceTab

SOURCE = '''STATE_NEW_YORK = {
 id = 267
 provinces = { "x123" }
 traits = { "unchanged" }
 arable_land = 120
 arable_resources = { "building_wheat_farm" }
 capped_resources = { building_iron_mine = 45 }
 resource = { type = "building_oil_rig" undiscovered_amount = 20 }
}
STATE_OTHER = { id = 1 }
'''


class StateResourceTests(unittest.TestCase):
    def test_edit_fields_and_preserve_unrelated_text(self):
        source = SOURCE.replace('\n', '\r\n')
        changed = replace_resources(source, 'STATE_NEW_YORK', {
            'arable_land': '200', 'arable_resources': [],
            'capped_resources': {'building_coal_mine': '50'}})
        values = resource_values(definitions(changed)['STATE_NEW_YORK'])
        self.assertEqual(values, {'arable_land': '200', 'arable_resources': [], 'capped_resources': {'building_coal_mine': '50'}})
        self.assertIn('resource = { type = "building_oil_rig" undiscovered_amount = 20 }', changed)
        self.assertTrue(changed.endswith('STATE_OTHER = { id = 1 }\r\n'))
        self.assertNotIn('\n', changed.replace('\r\n', ''))
        added = replace_resources(SOURCE, 'STATE_OTHER', {'arable_land': '5', 'capped_resources': {}, 'arable_resources': ['building_wheat_farm']})
        self.assertEqual(resource_values(definitions(added)['STATE_OTHER'])['arable_land'], '5')
        for bad in ('-1', '1.5', 'x'):
            with self.assertRaises(ValueError): replace_resources(SOURCE, 'STATE_OTHER', {'arable_land': bad})

    def test_ui_map_id_update_remove_and_backup(self):
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'region.txt'
            original = b'\xef\xbb\xbf' + SOURCE.encode()
            path.write_bytes(original)
            regions, arable, capped = scan_regions(folder)
            self.assertEqual(regions['STATE_NEW_YORK'][1], '267')
            self.assertEqual(capped, ['building_iron_mine'])
            editor = Mock(state_id=tk.StringVar(value='267'), file_path=tk.StringVar())
            tab = StateResourceTab(ttk.Notebook(root), editor)
            tab.folder.set(folder); tab.mode.set('Map Region ID'); tab.load()
            self.assertEqual(tab.region, 'STATE_NEW_YORK')
            tab.land.set('250')
            tab.queries['capped_resources'].set('building_iron_mine'); tab.level.set('60'); tab.add('capped_resources')
            tab.queries['arable_resources'].set('building_rice_farm'); tab.add('arable_resources')
            tab.lists['arable_resources'].selection_set(0); tab.remove('arable_resources')
            editor.state_id.set('1')
            with patch('state_resource_tab.messagebox.showerror') as error:
                tab.save(); error.assert_called_once()
            self.assertEqual(path.read_bytes(), original)
            editor.state_id.set('267'); tab.save()
            self.assertEqual(resource_values(definitions(path.read_text(encoding='utf-8-sig'))['STATE_NEW_YORK']), {
                'arable_land': '250', 'arable_resources': ['building_rice_farm'], 'capped_resources': {'building_iron_mine': '60'}})
            self.assertEqual(next(Path(folder).glob('*.bak')).read_bytes(), original)


if __name__ == '__main__': unittest.main()
