from pathlib import Path
import tempfile
import unittest
from shortage_estimator import estimate, write_report


class ShortageTests(unittest.TestCase):
    def test_unemployed_workers_do_not_fill_building_vacancies(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            methods = root / 'common/production_methods'
            methods.mkdir(parents=True)
            (methods / 'test.txt').write_text('test_pm={ building_modifiers={ level_scaled={ building_employment_shopkeepers_add=10 } } }')
            sections = {
                'country_manager': ['1={\n definition="TEST"\n}'],
                'states': ['42={\n country=1\n region="STATE_TEST"\n population_workforce_by_profession={ 15 12=10 }\n population_employable_qualifications={ 15 12=0 }\n}'],
                'pops': ['0={\n type=shopkeepers\n workforce=9\n location=42\n workplace=5\n}', '1={\n type=shopkeepers\n workforce=1\n location=42\n}'],
                'building_manager': ['5={\n state=42\n levels=1\n production_methods={ "test_pm" }\n}']}
            save = root / 'save.v3'
            save.write_text(''.join(name + '={\n database={\n' + '\n'.join(blocks) + '\n }\n}\n' for name, blocks in sections.items()))
            original = save.read_bytes()
            result = estimate(save, root)
            self.assertEqual(result['profession_indices']['shopkeepers'], '12')
            self.assertEqual(result['rows'][0]['estimated_shortage'], 1)
            self.assertEqual(result['rows'][0]['estimated_vacancies'], 1)
            self.assertEqual(result['warnings'], {})
            write_report(result, root / 'report.json')
            self.assertTrue((root / 'report.md').is_file())
            self.assertEqual(save.read_bytes(), original)


if __name__ == '__main__': unittest.main()
