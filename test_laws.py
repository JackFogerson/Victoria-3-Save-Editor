from pathlib import Path
from decimal import Decimal
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from law_editor import law_values, replace_law, scan_laws, institution_base, validate_effect
from law_tab import LawTab

SOURCE = '''law_test = {
 group = lawgroup_test
 modifier = {
  country_authority_add = 100 # keep comment
  country_test_bool = yes
 }
 on_activate = { if = { limit = { always = yes } set_variable = { name = test value = 1 } } }
 ai_will_do = { always = yes }
}
law_other = { group = lawgroup_test }
'''


class LawTests(unittest.TestCase):
    def test_mod_replacement_definition_keeps_prefix_and_other_content(self):
        source = SOURCE.replace('law_test =', 'REPLACE_OR_CREATE:law_test =')
        values = law_values(source, 'law_test')
        values['institution_modifier']['state_education_access_wealth_add'] = '0.07'
        changed = replace_law(source, 'law_test', values)
        self.assertTrue(changed.startswith('REPLACE_OR_CREATE:law_test ='))
        self.assertEqual(law_values(changed, 'law_test'), values)
        self.assertTrue(changed.endswith('law_other = { group = lawgroup_test }\n'))

    def test_numeric_values_use_game_compatible_decimal_notation(self):
        for value, expected in [('.25', '0.25'), ('-.2', '-0.2'), ('1e-3', '0.001'), ('+2', '2')]:
            self.assertEqual(validate_effect('state_pop_qualifications_mult', value), expected)
            values = law_values(SOURCE, 'law_test')
            values['modifier']['state_pop_qualifications_mult'] = value
            changed = replace_law(SOURCE, 'law_test', values)
            self.assertEqual(law_values(changed, 'law_test')['modifier']['state_pop_qualifications_mult'], expected)

    def test_institution_effects_are_separate_and_preserve_base(self):
        source = SOURCE + '\nlaw_welfare = { institution = institution_social_security institution_modifier = { building_minimum_wage_mult = 0.1 # keep\n } }\n'
        values = law_values(source, 'law_welfare')
        self.assertEqual(values['modifier'], {})
        values['institution_modifier']['state_welfare_payments_add'] = '0.1'
        values['institution_modifier']['building_minimum_wage_mult'] = '0.2'
        changed = replace_law(source, 'law_welfare', values)
        self.assertEqual(law_values(changed, 'law_welfare'), values)
        self.assertTrue(changed.startswith(SOURCE))
        self.assertIn('# keep', changed)
        values['institution_modifier'].pop('building_minimum_wage_mult')
        self.assertEqual(law_values(replace_law(changed, 'law_welfare', values), 'law_welfare'), values)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            common = Path(folder)
            (common / 'laws').mkdir(); (common / 'institutions').mkdir()
            (common / 'laws' / 'test.txt').write_text(source)
            base = common / 'institutions' / 'test.txt'
            base.write_text('institution_social_security = { modifier = { state_welfare_payments_add = 0.2 } }')
            self.assertEqual(institution_base(common / 'laws', source, 'law_welfare'), ('institution_social_security', {'state_welfare_payments_add': '0.2'}))
            self.assertIn('building_minimum_wage_mult', scan_laws(common / 'laws')[1])
            root = tk.Tk(); root.withdraw()
            try:
                with patch('law_tab.DEFAULT_LAWS', common / 'laws'):
                    tab = LawTab(ttk.Notebook(root))
                tab.query.set('law_welfare'); tab.select_law()
                self.assertEqual(tab.scope.get(), 'Institution effects per level')
                self.assertIn('state_welfare_payments_add', tab.tree.get_children())
                self.assertEqual(tab.active_modifiers()['state_welfare_payments_add'], '0.2')
                tab.effect.set('state_welfare_payments_add'); tab.value.set('0.1'); tab.add(); tab.save()
                self.assertEqual(law_values((common / 'laws' / 'test.txt').read_text(), 'law_welfare')['institution_modifier']['state_welfare_payments_add'], '-0.1')
                self.assertEqual(tab.active_modifiers()['state_welfare_payments_add'], '0.1')
                tab.tree.selection_set('state_welfare_payments_add'); tab.remove(); tab.save()
                self.assertEqual(Decimal(tab.active_modifiers()['state_welfare_payments_add']), 0)
                self.assertIn('0.2', base.read_text())
            finally:
                root.destroy()

    def test_edit_add_remove_and_preserve_scripts_and_other_laws(self):
        original = SOURCE.replace('\n', '\r\n')
        values = law_values(original, 'law_test')
        values['modifier'] = {'country_authority_add': '250', 'country_new_mult': '0.1'}
        changed = replace_law(original, 'law_test', values)
        self.assertEqual(law_values(changed, 'law_test'), values)
        self.assertIn('# keep comment', changed)
        self.assertIn('ai_will_do = { always = yes }', changed)
        self.assertTrue(changed.endswith('law_other = { group = lawgroup_test }\r\n'))
        self.assertNotIn('\n', changed.replace('\r\n', ''))
        empty = law_values(SOURCE, 'law_other')
        empty['modifier']['country_authority_add'] = '5'
        self.assertEqual(law_values(replace_law(SOURCE, 'law_other', empty), 'law_other')['modifier'], empty['modifier'])

    def test_script_validation(self):
        values = law_values(SOURCE, 'law_test')
        values['on_deactivate'] = '\n remove_modifier = test\n'
        self.assertEqual(law_values(replace_law(SOURCE, 'law_test', values), 'law_test'), values)
        values['on_activate'] = '} injected = { '
        with self.assertRaises(ValueError): replace_law(SOURCE, 'law_test', values)

    def test_tab_select_update_and_backup(self):
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        with patch('law_tab.DEFAULT_LAWS', Path('missing-laws-fixture')):
            tab = LawTab(ttk.Notebook(root))
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'laws.txt'; path.write_bytes(b'\xef\xbb\xbf' + SOURCE.encode())
            original = path.read_bytes()
            tab.folder.set(folder); tab.load_folder()
            self.assertEqual(len(tab.labels), 2)
            tab.query.set('law_test'); tab.select_law()
            tab.effect.set('country_authority_add'); tab.value.set('300'); tab.add(); tab.save()
            self.assertEqual(law_values(path.read_text(encoding='utf-8-sig'), 'law_test')['modifier']['country_authority_add'], '300')
            self.assertEqual(list(Path(folder).glob('*.bak')), [])
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))


if __name__ == '__main__': unittest.main()
