from pathlib import Path
import tempfile
import unittest
from decimal import Decimal
from settlement_checklist import load_catalog, checklist
from batch_states import load_batch
from test_batch_states import fixture

class SettlementTests(unittest.TestCase):
    def test_built_levels_not_capacity_or_zero_levels(self):
        text=fixture()+'''building_manager={
 database={
1={
 state=1
 building=building_logging_camp
 levels=2
}
2={
 state=1
 building=building_iron_mine
 levels=0
}
3={
 state=2
 building=building_iron_mine
 levels=4
}
4={
 state=1
 building=building_iron_mine
 levels=5
 active=no
}
 }
}
'''
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p=Path(folder)/'save.v3'; p.write_text(text)
            snapshot=load_batch(p)
            catalog={'buildings':{'building_logging_camp':'wood','building_iron_mine':'mine'},'regions':{'STATE_1':{'wood':'x1','mine':'x2'}},'names':{'HUB_NAME_STATE_1_wood':'Forest Town'},'warnings':[]}
            rows={r[0]:r for r in checklist(snapshot,'1',catalog)}
            self.assertEqual(rows['Wood'][1:3],('Forest Town','Building present'))
            self.assertEqual(rows['Mine'][2],'Missing building')
            self.assertEqual(rows['Port'][2],'Not available')
            snapshot['building_data_present']=False
            self.assertEqual(checklist(snapshot,'1',catalog)[2][2],'Unknown')

    def test_growth_guide_does_not_claim_a_maximum(self):
        from settlement_checklist import growth_notes
        catalog={'buildings':{'building_iron_mine':'mine'}, 'regions':{'STATE_TEST':{'mine':'x1'}}, 'mesh_levels':{'building_iron_mine':'50'}, 'visual_sol':{'MID_SOL':'10','RICH_SOL':'20'}}
        snapshot={'states':{'1':{'region':'STATE_TEST'}},'buildings':{'1':{'building_iron_mine':Decimal(12)}}}
        note=growth_notes(snapshot,'1',catalog)
        self.assertIn('above 20',note)
        self.assertIn('12 built, 50 levels per mesh',note)
        self.assertIn('NOT the level needed',note)
        self.assertNotIn('Port:',note)

    def test_mod_replacement_and_localized_name(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            base=Path(folder)/'game'; mod=Path(folder)/'mod'
            for root in (base,mod):
                for part in ('common/buildings','map_data/state_regions','localization/english','common/defines'): (root/part).mkdir(parents=True)
            (base/'common/buildings/base.txt').write_text('building_test={ city_type=city }')
            (mod/'common/buildings/override.txt').write_text('REPLACE:building_test={ city_type=wood }')
            (base/'map_data/state_regions/states.txt').write_text('STATE_TEST={ city=x1 wood=x2 }')
            (base/'localization/english/hubs.yml').write_text(' HUB_NAME_STATE_TEST_wood:0 "Old name"')
            (mod/'localization/english/hubs.yml').write_text(' HUB_NAME_STATE_TEST_wood: "New name"')
            (base/'common/defines/graphics.txt').write_text('NCities={ MID_SOL=10 RICH_SOL=20 }')
            (mod/'common/defines/override.txt').write_text('NCities={ RICH_SOL=25 }')
            catalog=load_catalog(base,[mod])
            self.assertEqual(catalog['visual_sol'],{'MID_SOL':'10','RICH_SOL':'25'})
            self.assertEqual(catalog['buildings']['building_test'],'wood')
            self.assertEqual(catalog['names']['HUB_NAME_STATE_TEST_wood'],'New name')
            self.assertEqual(catalog['warnings'],[])

if __name__=='__main__': unittest.main()
