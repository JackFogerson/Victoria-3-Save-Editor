from pathlib import Path
import tempfile
import unittest
from test_mass_migration import SAVE
from save_homelands import load_homelands, save_homelands


class SaveHomelandTests(unittest.TestCase):
    def test_add_remove_preserve_and_stale_guard(self):
        source = SAVE.replace('\ttype=french', '\ttype=french\n\tcore_states={ STATE_ORIGIN }')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'; path.write_bytes(source.encode())
            loaded = load_homelands(path, '20')
            self.assertEqual(loaded['current'], [])
            backup = save_homelands(loaded, ['french'])
            self.assertIsNone(backup)
            self.assertEqual(path.read_bytes(), source.replace('core_states={ STATE_ORIGIN }', 'core_states={ STATE_ORIGIN STATE_DESTINATION }').encode())
            with self.assertRaises(ValueError): save_homelands(loaded, [])
            fresh = load_homelands(path, '20')
            self.assertEqual(fresh['current'], ['french'])
            with self.assertRaises(ValueError): save_homelands(fresh, ['missing'])
            save_homelands(fresh, [])
            self.assertEqual(path.read_bytes(), source.encode())
