from pathlib import Path
import tempfile
import unittest
from save_resources import load_resources, save_resources

SOURCE = '''states={
 database={
10={
 region="STATE_TEST"
 land=0.25
 arable_land=25
 unrelated={ nested={ 1 2 } }
}
11={
 region="STATE_TEST"
 land=0.75
 arable_land=75
}
 }
}
state_region_manager={
 database={
5={
 template=STATE_TEST
 arable_land=100
 persistent_resources={
  region=STATE_TEST
  resources={ { type="building_wheat_farm" } { type="building_iron_mine" amount=20 } { type="building_oil_rig" undiscovered_amount=10 depletion=2 } }
 }
 traits={ keep_me }
}
 }
}
'''


class SaveResourceTests(unittest.TestCase):
    def test_ownerless_historical_state_does_not_split_current_state(self):
        source = SOURCE.replace(' land=0.25', ' country=11').replace(' arable_land=25', ' arable_land=100')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'test.v3'; path.write_text(source)
            loaded = load_resources(path, '10')
            self.assertEqual(set(loaded['states']), {'10'})
            old_historical = '11={\n region="STATE_TEST"\n land=0.75\n arable_land=75\n}'
            save_resources(loaded, dict(loaded['values'], arable_land='200'))
            self.assertIn('arable_land=200', load_resources(path, '10')['states']['10'][2])
            self.assertIn(old_historical, path.read_text())
            with self.assertRaisesRegex(ValueError, 'inactive'): load_resources(path, '11')

    def test_whole_state_omits_land_share(self):
        source = SOURCE.replace(' land=0.25\n', '').replace('11={\n region="STATE_TEST"\n land=0.75\n arable_land=75\n}\n', '')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'test.v3'; path.write_text(source)
            loaded = load_resources(path, '10')
            values = dict(loaded['values'], arable_land='200')
            save_resources(loaded, values)
            self.assertIn('arable_land=200', load_resources(path, '10')['states']['10'][2])

    def test_roundtrip_split_land_conversion_and_stale_guard(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'test.v3'; path.write_bytes(SOURCE.encode())
            loaded = load_resources(path, '10')
            self.assertEqual(loaded['undiscovered'], {'building_oil_rig': 10})
            values = {'arable_land': '200', 'arable_resources': ['building_tea_plantation'], 'capped_resources': {'building_iron_mine': '35', 'building_oil_rig': '10'}, 'discover_resources': ['building_oil_rig']}
            backup = save_resources(loaded, values)
            self.assertIsNone(backup)
            fresh = load_resources(path, '10')
            self.assertEqual(fresh['values'], {k:v for k,v in values.items() if k != 'discover_resources'})
            self.assertEqual(fresh['undiscovered'], {})
            self.assertIn('arable_land=50', fresh['states']['10'][2])
            self.assertIn('arable_land=150', fresh['states']['11'][2])
            self.assertIn('depletion=2', path.read_text())
            self.assertIn('unrelated={ nested={ 1 2 } }', path.read_text())
            with self.assertRaises(ValueError): save_resources(loaded, values)
