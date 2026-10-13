from pathlib import Path
import tempfile
import unittest
from culture_save import apply_culture_goods, update_goods
from test_mass_migration import SAVE


class CultureSaveTests(unittest.TestCase):
    def test_updates_only_culture_lists_and_preserves_backup(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'
            path.write_bytes(SAVE.encode())
            backup = apply_culture_goods(path, {'french': {'obsessions': ['coffee'], 'taboos': ['fish']}})
            self.assertEqual(backup.read_bytes(), SAVE.encode())
            self.assertIn(b'obsessions={ coffee }', path.read_bytes())
            self.assertIn(b'taboos={ fish }', path.read_bytes())
            self.assertIn(b'state=99 origin=1', path.read_bytes())
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                apply_culture_goods(path, {'missing': {'obsessions': [], 'taboos': []}})
            self.assertEqual(path.read_bytes(), before)

    def test_clearing_and_replacing_preserves_crlf(self):
        text = '1={\r\n type=yankee\r\n obsessions={ liquor }\r\n taboos={ wine }\r\n}\r\n'
        changed = update_goods(text, {'obsessions': [], 'taboos': ['fish']})
        self.assertIn('obsessions={  }', changed)
        self.assertIn('taboos={ fish }', changed)
        self.assertNotIn('\n', changed.replace('\r\n', ''))
