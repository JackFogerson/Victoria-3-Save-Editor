from pathlib import Path
import tempfile
import unittest
from mass_migration import index_save
from primary_cultures import culture_ids, read_country, save_primary_cultures
from test_mass_migration import SAVE


class PrimaryCultureTests(unittest.TestCase):
    def test_edit_only_selected_country_and_reject_stale_index(self):
        original = SAVE.replace('\tdefinition="FRA"', '\tdefinition="FRA"\n\tcultures={ 25 }').replace('\tdefinition="GRE"', '\tdefinition="GRE"\n\tcultures={ 25 }').replace('25={\n\ttype=french', '46={\n\ttype=greek\n}\n25={\n\ttype=french')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'save.v3'
            path.write_bytes(original.replace('\n', '\r\n').encode())
            before = path.read_bytes()
            index = index_save(path)
            self.assertEqual(culture_ids(read_country(index, '1')), ['25'])
            backup = save_primary_cultures(index, '1', ['25', '46', '25'])
            self.assertEqual(backup.read_bytes(), before)
            self.assertEqual(path.read_bytes(), before.replace(b'cultures={ 25 }', b'cultures={ 25 46 }', 1))
            with self.assertRaisesRegex(ValueError, 'changed'):
                save_primary_cultures(index, '1', ['25'])
            fresh = index_save(path)
            save_primary_cultures(fresh, '1', ['46'])
            self.assertEqual(path.read_bytes(), before.replace(b'cultures={ 25 }', b'cultures={ 46 }', 1))
            fresh = index_save(path)
            with self.assertRaisesRegex(ValueError, 'at least one'):
                save_primary_cultures(fresh, '1', [])
            with self.assertRaisesRegex(ValueError, 'selected save'):
                save_primary_cultures(fresh, '1', ['999'])

    def test_multiple_cultures_and_nested_field(self):
        self.assertEqual(culture_ids('1={ nested={ cultures={ 99 } } cultures={ 25 47 } }'), ['25', '47'])
        for text in ('1={}', '1={ cultures={ bad } }', '1={ cultures={25} cultures={47} }'):
            with self.assertRaises(ValueError):
                culture_ids(text)


if __name__ == '__main__':
    unittest.main()
