from pathlib import Path
import tempfile, unittest, runpy
from unittest.mock import patch
import tkinter as tk
from batch_states import load_batch, apply_batch
from save_resources import resources_from_records
from test_batch_states import fixture


def full_fixture():
    text = 'date=1836.1.1\n' + fixture()
    for sid in range(1,7): text=text.replace(f'region="STATE_{sid}"',f'region="STATE_{sid}"\n country=2\n arable_land=10')
    text += 'country_manager={\n database={\n1={\n definition=FRA\n}\n2={\n definition=USA\n}\n }\n}\n'
    text += 'state_region_manager={\n database={\n'
    for sid in range(1,7):
        text += f'{sid}={{\n template=STATE_{sid}\n arable_land=10\n persistent_resources={{ resources={{ {{ type="building_wheat_farm" }} {{ type="building_oil_rig" undiscovered_amount=5 }} }} }}\n}}\n'
    return text+' }\n}\n'


class MultiStateTests(unittest.TestCase):
    def test_migrations_merge_with_homelands_resources_and_single_commit(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path=Path(folder)/'save.v3'; path.write_text(full_fixture())
            snapshot=load_batch(path)
            resource={'arable_land':'30','arable_resources':['building_wheat_farm'],'capped_resources':{'building_oil_rig':'5'},'discover_resources':['building_oil_rig']}
            plans={'1':{'resources':resource,'homelands':['2'],'migration':{'culture':'1','source':'1','days':365}},
                   '2':{'migration':{'culture':'1','source':'1','days':180}}}
            from save_io import commit_save
            with patch('batch_states.commit_save',wraps=commit_save) as commit:
                apply_batch(snapshot,plans); self.assertEqual(commit.call_count,1)
            fresh=load_batch(path)
            self.assertEqual(fresh['states']['1']['homelands'],['2'])
            self.assertIn('arable_land=30',fresh['state_records']['1'][2])
            for sid in ('1','2'): self.assertIn('mass_migration=',fresh['state_records'][sid][2])
            for sid in ('1','2'): self.assertIn('state='+sid, fresh['cultures']['1']['text'])
            self.assertNotIn('mass_migration=',fresh['state_records']['3'][2])
            self.assertEqual(list(Path(folder).iterdir()),[path])
            before=path.read_bytes()
            with self.assertRaises(ValueError): apply_batch(fresh,{'3':{'migration':{'culture':'1','source':'2','days':30}}})
            self.assertEqual(path.read_bytes(),before)

    def test_rebuilt_single_state_is_visible_after_scrolling(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path=Path(folder)/'save.v3'; path.write_text(full_fixture())
            root=tk.Tk()
            try:
                cls=runpy.run_path('v3_editor')['Victoria3SaveEditor']
                with patch.object(cls,'select_latest_save'): editor=cls(root)
                ui=editor.multi_state; snapshot=load_batch(path); ui.populate(snapshot)
                for sid in map(str,range(1,7)): ui.query.set(sid); ui.add()
                for section in ('culture','resources'):
                    page=ui.pages[section]; page.master.select(page); root.update()
                    ui.bodies[section].master.yview_moveto(1)
                ui.restore_ids=['1']; ui.populate(snapshot)
                for section in ('culture','resources'):
                    page=ui.pages[section]; page.master.select(page); root.update()
                    canvas=ui.bodies[section].master; card=ui.cards['1'][section]
                    self.assertGreaterEqual(card.winfo_rooty(),canvas.winfo_rooty())
                    self.assertLess(card.winfo_rooty(),canvas.winfo_rooty()+canvas.winfo_height())
            finally: root.destroy()

    def test_existing_tabs_show_six_independent_state_panels(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path=Path(folder)/'save.v3'; path.write_text(full_fixture())
            root=tk.Tk(); root.withdraw()
            try:
                cls=runpy.run_path('v3_editor')['Victoria3SaveEditor']
                with patch.object(cls,'select_latest_save'):
                    editor=cls(root)
                ui=editor.multi_state; ui.populate(load_batch(path))
                for sid in map(str,range(1,7)): ui.query.set(sid); ui.add()
                self.assertEqual(len(ui.cards),6)
                self.assertEqual(len(ui.bodies['migration'].winfo_children()),6)
                self.assertEqual(len(ui.bodies['resources'].winfo_children()),6)
                ui.cards['1']['migration'].enabled.set(True)
                ui.cards['1']['migration'].culture.set('1'); ui.cards['1']['migration'].source.set('1')
                ui.cards['2']['resources'].panel.land.set('42')
                ui.cards['3']['culture'].percentages['1'].set('20')
                plans=ui.plans()
                self.assertIn('migration',plans['1']); self.assertNotIn('migration',plans['2'])
                self.assertEqual(plans['2']['resources']['arable_land'],'42')
                self.assertNotIn('resources',plans['1'])
                self.assertEqual(plans['3']['percentages']['1'],'20')
                self.assertEqual(plans['4']['percentages']['1'],'0')
                root.update_idletasks()
            finally: root.destroy()

if __name__=='__main__': unittest.main()
