"""Quick Blender-free tests for Comp-IO Collection and PSD group handling.

Run: python3 test_compio_hierarchy.py
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from layer_stack import prepared_entries, build_stack, leaf_names
from group_blends import promoted_blend, effective_layer_mode
from collection_provenance import unique_distinct_authored_child, collection_index
from attribution_names import related_output_owner


def stack(paths):
    return build_stack(prepared_entries([(dict(name=name, collection_path=collection), None)
                                         for name, collection in paths], True))


def groups(branch):
    return [c for c in branch['children'] if c['kind'] == 'group']


class TestNames(unittest.TestCase):
    def test_sceptres_keep_plain_and_use_nearest_child_collection(self):
        tree = stack([('Flail_R', 'Sceptres_R/Flail'),
                      ('ForeArm_L', 'MainBody'),
                      ('Sceptres_R', 'Sceptres_R/Sceptres_R')])
        self.assertEqual([c['name'] for c in groups(tree)],
                         ['Sceptres_R-Flail', 'MainBody', 'Sceptres_R'])

    def test_authored_suffix_prevents_extra_b(self):
        tree = stack([('Flail_R', 'Sceptres_R-Flail/Flail'),
                      ('ForeArm_L', 'MainBody'),
                      ('Sceptres_R', 'Sceptres_R/Sceptres_R')])
        self.assertEqual([c['name'] for c in groups(tree)],
                         ['Sceptres_R-Flail', 'MainBody', 'Sceptres_R'])

    def test_headgear_retains_original_root_for_hood_disambiguation(self):
        tree = stack([('HeadBand', 'Headgear/Band'),
                      ('SnakeTail', 'Headgear/Snake/SnakeTail'),
                      ('UpperLashes','Hair/UpperLashes'),
                      ('Hood_FG', 'Headgear/Hood'),
                      ('Eyes_Base', 'Eye'),
                      ('Eyes_Shade', 'Eye'),
                      ('Head_Back', 'Headgear/Hood')])
        self.assertEqual([c['name'] for c in groups(tree)],
                         ['Headgear', 'Hair-UpperLashes', 'Headgear-Hood_FG',
                          'Eye', 'Headgear-Head_Back'])
        self.assertEqual(groups(groups(tree)[2])[0]['name'], 'Hood-Hood_FG')
        self.assertEqual(groups(groups(tree)[-1])[0]['name'], 'Hood-Head_Back')
        self.assertEqual(leaf_names(tree)[3][-3:],
                         ('Headgear-Hood_FG','Hood-Hood_FG','Hood_FG'))

    def test_mainbody_groups_all_get_content_names(self):
        tree = stack([('ForeArm_L','MainBody'),('Sceptres_L','Sceptres_L'),
                      ('ForeArm_R','MainBody'),('Sceptres_R','Sceptres_R'),
                      ('Head','MainBody'),('Dress','Dress'),
                      ('Neck','MainBody'),('Collar','Collar'),
                      ('Arms_Upper','MainBody')])
        self.assertEqual([g['name'] for g in groups(tree) if g['raw']=='MainBody'],
                         ['MainBody-ForeArm_L','MainBody-ForeArm_R',
                          'MainBody-Head','MainBody-Neck','MainBody-Arms_Upper'])

    def test_split_nested_collection_instances_are_both_named(self):
        # Distinct parent group instances contain disjoint pieces of Hood.
        tree = stack([('Hood_FG','Headgear/Hood'),
                      ('Intervening','Elsewhere'),
                      ('Head_Back','Headgear/Hood')])
        self.assertIn(('Headgear-Hood_FG','Hood-Hood_FG','Hood_FG'),leaf_names(tree))
        self.assertIn(('Headgear-Head_Back','Hood-Head_Back','Head_Back'),leaf_names(tree))

    def test_single_subcollection_root_describes_partial_artwork(self):
        tree = stack([('UpperLashes','Hair/UpperLashes'), ('Eyes_Base','Eye')])
        self.assertEqual(groups(tree)[0]['name'],'Hair-UpperLashes')
        # A complete multi-branch group stays compact.
        group = stack([('HeadBand','Headgear/Band'), ('SnakeTail','Headgear/Snake/SnakeTail')])
        self.assertEqual(groups(group)[0]['name'],'Headgear')

    def test_pixel_group_same_name_remains_unchanged(self):
        tree = stack([('SnakeTail','Headgear/Snake/SnakeTail'),
                      ('UpperLashes','Hair/UpperLashes'),
                      ('Collar','Collar')])
        self.assertIn(('Headgear','Snake','SnakeTail','SnakeTail'), leaf_names(tree))
        self.assertIn(('Hair-UpperLashes','UpperLashes','UpperLashes'),leaf_names(tree))
        self.assertIn(('Collar','Collar'),leaf_names(tree))

    def test_eye_group_contents_preserved(self):
        tree = stack([('Eyes_Reflect.add', 'Assets.ungroup/Eye/Membrane'),
                      ('Eyes_Shade.multiply', 'Assets.ungroup/Eye/Shade'),
                      ('Eyes_Base', 'Assets.ungroup/Eye')])
        self.assertEqual(leaf_names(tree), [
            ('Eye','Membrane','Eyes_Reflect'),
            ('Eye','Shade','Eyes_Shade'),
            ('Eye','Eyes_Base')])

    def test_collar_keeps_first(self):
        tree = stack([('Collar', 'Collar'), ('Neck','MainBody'),
                      ('Collar_BG','Collar')])
        self.assertEqual([g['name'] for g in groups(tree)],
                         ['Collar', 'MainBody', 'Collar-Collar_BG'])

    def test_same_name_under_different_parent_keeps_both(self):
        tree=stack([('A','Headgear/Hood'), ('B','Hair/Hood')])
        self.assertEqual(groups(groups(tree)[0])[0]['name'], 'Hood')
        self.assertEqual(groups(groups(tree)[1])[0]['name'], 'Hood')

    def test_repeated_indistinguishable_groups_has_only_one_suffix(self):
        tree=stack([('A','Root/Sub'),('middle','Other'),('A','Root/Sub')])
        names=[g['name'] for g in groups(tree)]
        self.assertEqual(names[0],'Root')
        self.assertTrue(names[-1].startswith('Root-'))


class FakeCollection:
    def __init__(self, name, enabled=True, child=None):
        self.collection=SimpleNamespace(name=name, hide_render=False,
                     objects=[SimpleNamespace(name=name+'_Mesh',type='MESH',hide_render=False,visible_camera=True)] if child is None else [])
        self.exclude=not enabled
        self.holdout=False
        self.indirect_only=False
        self.children=child or []


def source_view(name, included):
    branches = [FakeCollection('Shade', 'Shade' in included),
                FakeCollection('Membrane','Membrane' in included),
                FakeCollection('Membrane_Shade','Membrane_Shade' in included)]
    eye=FakeCollection('Eye', child=branches)
    assets=FakeCollection('Assets.ungroup',child=[eye])
    root=FakeCollection('Scene',child=[assets])
    return SimpleNamespace(name=name, layer_collection=root)


class TestNestedCollections(unittest.TestCase):
    def test_eye_branches_from_per_view_layer_inclusion(self):
        base=source_view('Eyes_Base', {'Membrane_Shade'})
        shade=source_view('Eyes_Shade', {'Shade'})
        reflect=source_view('Eyes_Reflect', {'Membrane','Membrane_Shade'})
        prefix='Assets.ungroup/Eye'
        self.assertEqual(unique_distinct_authored_child(reflect,prefix,[base,shade]),prefix+'/Membrane')
        self.assertEqual(unique_distinct_authored_child(shade,prefix,[base,reflect]),prefix+'/Shade')
        self.assertEqual(unique_distinct_authored_child(base,prefix,[shade,reflect]),'')


class TestPeerScoping(unittest.TestCase):
    def test_unrelated_source_view_layers_do_not_veto_eye_branches(self):
        shade = source_view('Eyes_Shade', {'Shade'})
        reflect = source_view('Eyes_Reflect', {'Membrane', 'Membrane_Shade'})
        base = source_view('Eyes_Base', {'Membrane_Shade'})
        unrelated = source_view('ForeArm_L', {'Shade', 'Membrane', 'Membrane_Shade'})
        prefix = 'Assets.ungroup/Eye'
        peer_data = [('Eyes_Shade.multiply',shade), ('Eyes_Base',base),
                     ('ForeArm_L',unrelated)]
        matching=[]
        for label, peer in peer_data:
            related, match = related_output_owner(prefix, label, peer.name,
                                                  collection_index(peer))
            if related:
                matching.append(peer)
        self.assertEqual([p.name for p in matching],['Eyes_Shade','Eyes_Base'])
        self.assertEqual(unique_distinct_authored_child(reflect, prefix, matching),
                         prefix + '/Membrane')
        self.assertEqual(unique_distinct_authored_child(shade, prefix, [reflect, base]),
                         prefix + '/Shade')


class TestGroupBlending(unittest.TestCase):
    def test_eye_modes_promoted_to_own_collection(self):
        tree=stack([('Eyes_Reflect.add','Eye/Membrane'),
                    ('Eyes_Shade.multiply','Eye/Shade'),
                    ('Eyes_Base','Eye')])
        eye=groups(tree)[0]
        self.assertIsNone(promoted_blend(eye))
        membrane,shade=groups(eye)
        self.assertEqual(promoted_blend(membrane),'add')
        self.assertEqual(promoted_blend(shade),'multiply')
        self.assertEqual(effective_layer_mode(membrane['children'][0]['item'],'add'),'normal')
        self.assertEqual(effective_layer_mode(shade['children'][0]['item'],'multiply'),'normal')

    def test_strict_majority_and_no_crossing_subgroup_boundaries(self):
        tree=stack([('A.multiply','Eye/Shade'),('B.multiply','Eye/Shade'),
                    ('C','Eye/Shade'),('D.add','Eye/Membrane')])
        eye=groups(tree)[0]
        self.assertIsNone(promoted_blend(eye))
        self.assertEqual(promoted_blend(groups(eye)[0]),'multiply')


class TestActualPSD(unittest.TestCase):
    def test_mixed_realistic_stack_survives_roundtrip(self):
        from PIL import Image
        from psd_worker import assemble_psd
        from psd_tools import PSDImage
        scene_layers = [
            ('Flail_R','Sceptres_R/Flail'),
            ('ForeArm_L','MainBody'),
            ('Sceptres_L','Sceptres_L'),
            ('ForeArm_R','MainBody'),
            ('Sceptres_R','Sceptres_R'),
            ('HeadBand','Headgear/Band'),
            ('SnakeTail','Headgear/Snake/SnakeTail'),
            ('UpperLashes','Hair/UpperLashes'),
            ('Head','MainBody'),
            ('Hood_FG','Headgear/Hood'),
            ('Eyes_Reflect.add','Eye/Membrane'),
            ('Eyes_Shade.multiply','Eye/Shade'),
            ('Eyes_Base','Eye'),
            ('Collar','Collar'),
            ('Neck','MainBody'),
            ('Torso','Dress'),
            ('Collar_BG','Collar'),
            ('Arms_Upper','MainBody'),
            ('Head_Back','Headgear/Hood'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            inputs=[]
            for i,(name,collection) in enumerate(scene_layers):
                png=folder/f'{i:03}.png'
                Image.new('RGBA',(8,8),(i*9 % 255,140,200,220)).save(png)
                inputs.append((dict(name=name,collection_path=collection),png))
            dest=folder/'complex.psd'
            assemble_psd(dict(dest=str(dest),depth=8,format='PSD',
                              extension='.png',overwrite=True,
                              tag_profile='PASSTHROUGH',hierarchy='GROUPS',
                              flatten=False), inputs)
            psd=PSDImage.open(dest)
            top={g.name:g for g in psd}
            self.assertIn('Headgear-Hood_FG', top)
            self.assertIn('Headgear-Head_Back', top)
            self.assertIn('MainBody-ForeArm_L', top)
            self.assertIn('MainBody-ForeArm_R', top)
            self.assertIn('MainBody-Arms_Upper', top)
            self.assertEqual(next(iter(top['Headgear-Hood_FG'])).name,'Hood-Hood_FG')
            eye=top['Eye']
            membrane=next(g for g in eye if g.name=='Membrane')
            shade=next(g for g in eye if g.name=='Shade')
            self.assertEqual(membrane.blend_mode.value,b'lddg')
            self.assertEqual(shade.blend_mode.value,b'mul ')
            self.assertEqual(membrane[0].blend_mode.value,b'norm')
            self.assertEqual(shade[0].blend_mode.value,b'norm')
            self.assertEqual(len([g for g in psd if g.name=='Eye']),1)
            self.assertEqual(next(iter(top['Headgear-Head_Back'])).name,'Hood-Head_Back')
            self.assertIn('Hair-UpperLashes',top)
            self.assertIn('Collar',top)
            self.assertEqual(len([g for g in psd if g.name=='Headgear-Hood_FG']),1)

    def test_psd_group_modes_survive_roundtrip(self):
        try:
            from PIL import Image
            from psd_worker import assemble_psd
            from psd_tools import PSDImage
        except ImportError as exc:
            self.skipTest('PSD test dependencies missing: '+str(exc))
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            paths=[]
            for i,(name,collection) in enumerate([
                    ('Eyes_Reflect.add','Eye/Membrane'),
                    ('Eyes_Shade.multiply','Eye/Shade'),
                    ('Eyes_Base','Eye')]):
                path=folder/f'{i}.png'
                Image.new('RGBA',(8,8),(255,50+i*30,30,200)).save(path)
                paths.append((dict(name=name,collection_path=collection),path))
            dest=folder/'test.psd'
            job=dict(dest=str(dest),depth=8,format='PSD',extension='.png',
                     overwrite=True,tag_profile='PASSTHROUGH',hierarchy='GROUPS',flatten=False)
            assemble_psd(job,paths)
            document=PSDImage.open(dest)
            eye=next(g for g in document if g.name=='Eye')
            self.assertEqual(next(c for c in eye if c.name=='Membrane').blend_mode.value,b'lddg')
            self.assertEqual(next(c for c in eye if c.name=='Shade').blend_mode.value,b'mul ')
            self.assertEqual(next(c for c in eye if c.name=='Membrane')[0].blend_mode.value,b'norm')
            self.assertEqual(next(c for c in eye if c.name=='Shade')[0].blend_mode.value,b'norm')



class TestMergeDirective(unittest.TestCase):
    def test_merge_group_becomes_pixel_in_original_order(self):
        import numpy as np
        from merge_groups import collapse_merged_groups
        tree = stack([('HeadBand','Headgear/Band.ungroup'),
                      ('SnakeTip','Headgear/Snake.merge'),
                      ('SnakeBase','Headgear/Snake.merge'),
                      ('Eyes_Base','Eye')])
        def load(item):
            rgba=np.zeros((2,2,4), dtype=np.float32)
            rgba[...,0] = 1 if item['entry']['name']=='SnakeTip' else 0
            rgba[...,1] = 1 if item['entry']['name']=='SnakeBase' else 0
            rgba[...,3] = .5 if item['entry']['name']=='SnakeTip' else 1
            return rgba
        collapse_merged_groups(tree, load, (2,2), logger=lambda *args:None)
        headgear=groups(tree)[0]
        self.assertEqual([c['name'] for c in headgear['children']], ['HeadBand','Snake'])
        merged=headgear['children'][1]
        self.assertEqual(merged['kind'], 'layer')
        self.assertEqual(merged['item']['pixels'][0,0,3], 1)
        np.testing.assert_allclose(merged['item']['pixels'][0,0,:3], [.5,.5,0],atol=1e-6)
        self.assertEqual(leaf_names(tree), [('Headgear','HeadBand'),('Headgear','Snake'),('Eye','Eyes_Base')])

    def test_single_layer_merge_keeps_group_name_and_blend(self):
        import numpy as np
        from merge_groups import collapse_merged_groups
        tree=stack([('SnakeTail.add', 'Headgear/SnakeTail.merge')])
        collapse_merged_groups(tree, lambda item: np.ones((1,1,4),np.float32), (1,1), logger=lambda *args:None)
        leaf=groups(tree)[0]['children'][0]
        self.assertEqual(leaf['name'],'SnakeTail')
        self.assertEqual(leaf['item']['mode'],'add')
        self.assertNotIn('merge', leaf['name'])

    def test_ignore_excludes_children_from_merge(self):
        import numpy as np
        from merge_groups import collapse_merged_groups
        tree=stack([('NotHere.ignore','Root.merge'),('A','Root.merge'),('B','Another')])
        collapse_merged_groups(tree,lambda item:np.ones((1,1,4),np.float32),(1,1),logger=lambda *args:None)
        self.assertEqual(leaf_names(tree), [('Root',),('Another','B')])

    def test_ungroup_promotes_child_with_merge(self):
        import numpy as np
        from merge_groups import collapse_merged_groups
        tree=stack([('A','Headgear/Outer.ungroup/Inner.merge'),('B','Headgear/Outer.ungroup/Inner.merge')])
        collapse_merged_groups(tree,lambda item:np.ones((1,1,4),np.float32),(1,1),logger=lambda *args:None)
        self.assertEqual(leaf_names(tree), [('Headgear','Inner')])

    def test_reference_child_is_excluded_from_merge_pixels(self):
        import numpy as np
        from merge_groups import collapse_merged_groups
        tree=stack([('Ref.ref','Group.merge'),('Visible','Group.merge')])
        def load(item):
            a=np.zeros((1,1,4),np.float32)
            a[...,0 if item['entry']['name']=='Ref.ref' else 1]=1
            a[...,3]=1
            return a
        collapse_merged_groups(tree,load,(1,1),logger=lambda *args:None)
        np.testing.assert_array_equal(tree['children'][0]['item']['pixels'][0,0,:3], [0,1,0])

class TestMergeFileOutputs(unittest.TestCase):
    def test_psd_and_oca_roundtrip_merged_group(self):
        import json
        import numpy as np
        from PIL import Image
        from psd_worker import assemble_psd, assemble_oca
        from psd_tools import PSDImage
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            inputs=[]
            for i,(name,path,rgba) in enumerate([
                ('SnakeTip','Headgear/SnakeTail.merge',(255,0,0,128)),
                ('SnakeBase','Headgear/SnakeTail.merge',(0,255,0,255)),
                ('Eyes_Base','Eye',(0,0,255,255)),
            ]):
                fn=root / f'{i}.png'
                Image.new('RGBA',(3,3),rgba).save(fn)
                inputs.append(({'name':name,'collection_path':path},fn))
            job={'dest':str(root/'merged.psd'),'format':'PSD','depth':8,'extension':'.png',
                 'hierarchy':'GROUPS','tag_profile':'PASSTHROUGH','overwrite':True,'flatten':False}
            assemble_psd(job,inputs)
            psd=PSDImage.open(job['dest'])
            self.assertEqual([x.name for x in psd], ['Eye','Headgear'])
            headgear=next(x for x in psd if x.name=='Headgear')
            self.assertEqual([x.name for x in headgear], ['SnakeTail'])
            layer=list(headgear)[0]
            self.assertFalse(layer.is_group())
            rgba=np.asarray(layer.topil())
            self.assertAlmostEqual(rgba[0,0,0],128,delta=3)
            self.assertAlmostEqual(rgba[0,0,1],127,delta=3)
            job.update(dest=str(root/'merged.oca'), format='OCA',frame=1)
            assemble_oca(job,inputs)
            obj=json.loads((root/'merged.oca').read_text())
            self.assertEqual(obj['layers'][1]['name'],'Headgear')
            self.assertEqual(len(obj['layers'][1]['childLayers']),1)
            merged=obj['layers'][1]['childLayers'][0]
            self.assertEqual(merged['name'],'SnakeTail')
            self.assertEqual(merged['type'],'paintlayer')
            actual=root/merged['frames'][0]['fileName']
            self.assertTrue(actual.exists())
            with Image.open(actual) as im:
                rgba=np.array(im)
                self.assertAlmostEqual(int(rgba[0,0,0]),128,delta=3)
                self.assertAlmostEqual(int(rgba[0,0,1]),127,delta=3)

class TestMergePreview(unittest.TestCase):
    def test_preview_shows_final_pixel_layer(self):
        from layer_stack import preview_merge_groups
        tree=stack([('SnakeTail','Headgear/SnakeTail.merge'),('Eyes_Base','Eye')])
        preview_merge_groups(tree)
        self.assertEqual(leaf_names(tree),[('Headgear-SnakeTail','SnakeTail'),('Eye','Eyes_Base')])
        self.assertTrue(groups(tree)[0]['children'][0]['merged_preview'])

class TestDirectiveConflict(unittest.TestCase):
    def test_merge_and_ungroup_same_collection_fails(self):
        with self.assertRaisesRegex(ValueError, 'both .merge and .ungroup'):
            stack([('A','Root.merge.ungroup')])

class TestMergeSingleLeafOutput(unittest.TestCase):
    def test_single_leaf_merge_suffix_is_not_reemitted(self):
        import numpy as np
        from PIL import Image
        from psd_worker import assemble_psd
        from psd_tools import PSDImage
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/'input.png'
            Image.new('RGBA',(2,2),(110,90,70,255)).save(src)
            job={'dest':str(root/'one.psd'),'format':'PSD','depth':8,'extension':'.png',
                 'hierarchy':'GROUPS','tag_profile':'PASSTHROUGH','overwrite':True,'flatten':False}
            assemble_psd(job,[({'name':'One.merge','collection_path':''},src)])
            self.assertEqual([x.name for x in PSDImage.open(job['dest'])],['One'])



class TestCollectionColors(unittest.TestCase):
    def test_untagged_child_stops_ungrouped_ancestor_colour_in_both_formats(self):
        from collection_colors import source_collection_colors
        from psd_worker import assemble_psd
        from svg_document import write_svg_document
        from PIL import Image
        from psd_tools import PSDImage
        from psd_tools.constants import SheetColorType
        from xml.etree import ElementTree as ET
        collections={'Assets.ungroup':SimpleNamespace(color_tag='COLOR_02'),
                     'Shine':SimpleNamespace(color_tag='NONE')}
        # A real theme must not turn NONE into the last tagged ancestor.
        colors=source_collection_colors('Assets.ungroup/Shine',collections,[(1,0,0)]*8)
        self.assertEqual(colors[-1],'NO_COLOR')
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);png=folder/'pixels.png';Image.new('RGBA',(4,4),'white').save(png)
            inputs=[(dict(name='Shine',collection_path='Assets.ungroup/Shine',collection_colors=colors),png)]
            job=dict(dest=str(folder/'art.psd'),format='PSD',depth=8,extension='.png',
                hierarchy='GROUPS',overwrite=True,psd_compression='AUTO')
            assemble_psd(job,inputs);doc=PSDImage.open(job['dest'])
            self.assertEqual(doc[0].sheet_color,SheetColorType.GRAY)
            self.assertEqual(doc[0][0].sheet_color,SheetColorType.GRAY)
            job['dest']=str(folder/'art.svg');write_svg_document(job,inputs,logger=lambda *args:None)
            root=ET.parse(job['dest']).getroot();ink='{http://www.inkscape.org/namespaces/inkscape}'
            self.assertTrue(all(g.get(ink+'highlight-color')=='#ffffff'
                for g in root.iter('{http://www.w3.org/2000/svg}g')))

    def test_source_tag_lookup_is_ordered_and_does_not_inherit(self):
        from collection_colors import source_collection_colors
        collections = {name: SimpleNamespace(color_tag=tag) for name, tag in [
            ('Assets.ungroup','NONE'), ('Eye','COLOR_04'),
            ('Membrane','COLOR_02'), ('Shade','NONE')]}
        self.assertEqual(source_collection_colors('Assets.ungroup/Eye/Membrane', collections),
                         ['NO_COLOR', 'GREEN', 'ORANGE'])
        self.assertEqual(source_collection_colors('Assets.ungroup/Eye/Shade', collections),
                         ['NO_COLOR', 'GREEN', 'NO_COLOR'])
        self.assertEqual(source_collection_colors('Missing/Eye', collections), ['', 'GREEN'])

    def test_all_eight_tags_have_supported_photoshop_labels(self):
        from collection_colors import BLENDER_TO_PSD
        from psd_tools.constants import SheetColorType
        self.assertEqual(len(BLENDER_TO_PSD), 8)
        for name in BLENDER_TO_PSD.values():
            self.assertIn(name, SheetColorType.__members__)

    def test_custom_theme_swatches_affect_mapping(self):
        from collection_colors import source_collection_colors
        swatches = [(0.31,0.52,0.91)] * 8
        collection={'Eye':SimpleNamespace(color_tag='COLOR_01')}
        self.assertEqual(source_collection_colors('Eye',collection,swatches),['BLUE'])

    def test_ungroup_and_collisions_keep_colours_on_correct_groups(self):
        from collection_colors import source_collection_colors
        labels={'Assets.ungroup':'NONE', 'Headgear':'COLOR_05',
                'Hood':'COLOR_02', 'Other':'COLOR_03'}
        entries=[]
        for name, path in [('Hood_FG','Assets.ungroup/Headgear/Hood'),
                           ('Divider','Other'), ('Head_Back','Assets.ungroup/Headgear/Hood')]:
            entries.append(({'name':name,'collection_path':path,
                             'collection_colors':source_collection_colors(
                                 path,{key:SimpleNamespace(color_tag=value)
                                       for key,value in labels.items()})},None))
        tree=build_stack(prepared_entries(entries, True))
        headgears=[g for g in groups(tree) if g['raw']=='Headgear']
        self.assertEqual(len(headgears),2)
        for g in headgears:
            self.assertEqual(g['sheet_color'],'BLUE')
            self.assertEqual(groups(g)[0]['sheet_color'],'ORANGE')
        self.assertEqual(next(g for g in groups(tree) if g['raw']=='Other')['sheet_color'],'YELLOW')

    def test_explicit_noncollection_groups_do_not_inherit_random_colours(self):
        tree=build_stack(prepared_entries([({'name':'Custom/Nested/Image',
            'collection_path':'Assets.ungroup/Eye',
            'collection_colors':['','GREEN']}, None)], True))
        self.assertEqual(groups(tree)[0]['sheet_color'],'')

    def test_merge_removes_coloured_group_and_keeps_coloured_parent(self):
        import numpy as np
        from merge_groups import collapse_merged_groups
        entries=[({'name':'A','collection_path':'Headgear/Snake.merge',
                   'collection_colors':['BLUE','ORANGE']},None)]
        tree=build_stack(prepared_entries(entries, True))
        collapse_merged_groups(tree, lambda item: np.ones((1,1,4),np.float32),
                               (1,1), logger=lambda *a:None)
        self.assertEqual(groups(tree)[0]['sheet_color'],'BLUE')
        self.assertEqual(groups(tree)[0]['children'][0]['kind'],'layer')

    def test_psb_group_colour_roundtrip(self):
        from PIL import Image
        from psd_tools import PSDImage
        from psd_tools.constants import SheetColorType
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            png=root/'art.png'
            Image.new('RGBA',(3,3),(10,20,30,255)).save(png)
            dest=root/'colour.psb'
            assemble_psd({'dest':str(dest),'format':'PSB','depth':8,'extension':'.png',
                          'overwrite':True,'tag_profile':'PASSTHROUGH',
                          'hierarchy':'GROUPS','flatten':False},
                          [({'name':'Art','collection_path':'Group',
                             'collection_colors':['ORANGE']},png)])
            psb=PSDImage.open(dest)
            self.assertEqual(psb.version,2)
            self.assertEqual(psb[0].sheet_color,SheetColorType.ORANGE)

    def test_psd_label_roundtrip_and_pixel_layers_inherited(self):
        from PIL import Image
        from psd_tools import PSDImage
        from psd_tools.constants import SheetColorType
        from psd_worker import assemble_psd
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            inputs=[]
            for i, (name,path,labels) in enumerate([
                ('Eyes_Reflect.add','Assets.ungroup/Eye/Membrane.ungroup',
                  ['', 'GREEN','RED']),
                ('Eyes_Shade.multiply','Assets.ungroup/Eye/Shade',
                  ['', 'GREEN','VIOLET']),
                ('Eyes_Base','Assets.ungroup/Eye',['','GREEN']),
            ]):
                png=folder/f'{i}.png'
                Image.new('RGBA',(4,4),(200,90,20,255)).save(png)
                inputs.append(({'name':name,'collection_path':path,
                                'collection_colors':labels},png))
            dest=folder/'colours.psd'
            assemble_psd({'dest':str(dest),'format':'PSD','depth':8,'extension':'.png',
                          'overwrite':True,'tag_profile':'PASSTHROUGH',
                          'hierarchy':'GROUPS','flatten':False},inputs)
            psd=PSDImage.open(dest)
            eye=next(g for g in psd if g.name=='Eye')
            self.assertEqual(eye.sheet_color, SheetColorType.GREEN)
            shade=next(g for g in eye if g.name=='Shade')
            self.assertEqual(shade.sheet_color, SheetColorType.VIOLET)
            self.assertEqual(shade[0].sheet_color, SheetColorType.VIOLET)
            self.assertEqual(next(g for g in eye if g.name=='Eyes_Reflect').sheet_color, SheetColorType.RED)
            self.assertEqual(eye[0].sheet_color, SheetColorType.GREEN)

if __name__ == '__main__':
    unittest.main(verbosity=2)
