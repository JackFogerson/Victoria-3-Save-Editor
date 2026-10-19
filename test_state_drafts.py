from pathlib import Path
import tempfile, unittest, runpy
from unittest.mock import patch
import tkinter as tk
from batch_states import load_batch, apply_batch
from state_drafts import rebase_drafts
from test_multi_state_workspace import full_fixture

class DraftTests(unittest.TestCase):
    def test_culture_save_rebases_offsets_and_keeps_both_changes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p=Path(folder)/'save.v3'; p.write_text(full_fixture())
            before=load_batch(p)
            p.write_text(p.read_text().replace('type=yankee','type=yankee\n obsessions={ coffee fruit }'))
            fresh=rebase_drafts(before,load_batch(p),['1','2'])
            apply_batch(fresh,{'1':{'homelands':['2'],'percentages':{'1':'20'}},'2':{'resources':{'arable_land':'25','arable_resources':['building_wheat_farm'],'capped_resources':{},'discover_resources':[]}}})
            result=load_batch(p)
            self.assertEqual(result['states']['1']['homelands'],['2'])
            self.assertEqual(result['states']['1']['cultures']['1'],360)
            self.assertIn('obsessions={ coffee fruit }',result['cultures']['1']['text'])
            self.assertIn('arable_land=25',result['state_records']['2'][2])

    def test_unrelated_region_metadata_does_not_block_resources(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p=Path(folder)/'save.v3'; p.write_text(full_fixture()); old=load_batch(p)
            p.write_text(p.read_text().replace('template=STATE_1', 'template=STATE_1\n unrelated_cache=99',1))
            fresh=load_batch(p)
            self.assertIs(rebase_drafts(old,fresh,['1']),fresh)
            p.write_text(p.read_text().replace('undiscovered_amount=5','undiscovered_amount=6',1))
            with self.assertRaisesRegex(ValueError,'Resources'): rebase_drafts(old,load_batch(p),['1'])

    def test_concurrent_state_change_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p=Path(folder)/'save.v3'; p.write_text(full_fixture()); before=load_batch(p)
            p.write_text(p.read_text().replace('workforce=100','workforce=101',1)); current=p.read_bytes()
            with self.assertRaisesRegex(ValueError,'State 1 changed'): rebase_drafts(before,load_batch(p),['1'])
            self.assertEqual(p.read_bytes(),current)

    def test_widget_drafts_survive_same_path_notice_and_refresh(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p=Path(folder)/'save.v3'; p.write_text(full_fixture())
            root=tk.Tk(); root.withdraw()
            try:
                cls=runpy.run_path('v3_editor')['Victoria3SaveEditor']
                with patch.object(cls,'select_latest_save'): editor=cls(root)
                editor.file_path.set(str(p)); ui=editor.multi_state
                ui.populate(load_batch(p)); ui.query.set('1'); ui.add()
                panels=ui.cards['1']
                panels['culture'].percentages['1'].set('-')  # unfinished input must survive too
                panels['homelands'].current_homelands=['2']
                panels['resources'].panel.land.set('37')
                editor.file_path.set(str(p))
                self.assertNotEqual(str(ui.apply_button['state']),'disabled')
                fresh=load_batch(p); ui.results.put(('refresh',str(p),fresh,None)); ui.poll()
                self.assertIs(ui.cards['1'],panels)
                self.assertEqual(panels['culture'].percentages['1'].get(),'-')
                self.assertEqual(panels['resources'].panel.land.get(),'37')
                self.assertEqual(panels['homelands'].current_homelands,['2'])
                with patch.object(ui,'refresh_drafts') as refresh, patch('multi_state_workspace.messagebox.askyesno') as prompt:
                    ui.load(); refresh.assert_called_once(); prompt.assert_not_called()
            finally: root.destroy()

if __name__=='__main__': unittest.main()
