from pathlib import Path
import tempfile
import unittest
from shortage_estimator import estimate, write_report, confident_index


class ShortageTests(unittest.TestCase):
    def test_consensus_tolerates_stale_caches_but_rejects_ambiguity(self):
        self.assertEqual(confident_index([(635, '7'), (11, '4')], 671), '7')
        self.assertEqual(confident_index([(727, '8'), (1, '4')], 886), '8')
        self.assertIsNone(confident_index([(80, '7'), (70, '4')], 100))
        self.assertIsNone(confident_index([(8, '7'), (0, '4')], 10))
        self.assertIsNone(confident_index([(40, '7'), (0, '4')], 100))
        self.assertEqual(confident_index([(1, '12'), (0, '4')], 1), '12')
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
            # Empty subsistence capacity must not increase ordinary vacancies.
            save.write_text(save.read_text().replace('building_manager={\n database={', 'building_manager={\n database={\n6={\n building=building_subsistence_farm\n state=42\n levels=100\n production_methods={ "test_pm" }\n}\n'))
            with_subsistence = estimate(save, root)
            self.assertEqual(with_subsistence['rows'], result['rows'])
            save.write_bytes(original)
            write_report(result, root / 'report.json')
            self.assertTrue((root / 'report.md').is_file())
            self.assertEqual(save.read_bytes(), original)


if __name__ == '__main__': unittest.main()
