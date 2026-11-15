"""Exercise last-render reuse through actual writers and document readers."""
import tempfile
import unittest
import json
import os
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image
from disabled_layers import transparent_cache, held_path
from psd_worker import assemble, find_inputs, read_rgba
from psd_tools import PSDImage

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'


class DisabledLayers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache'; self.cache.mkdir()
        self.entry = dict(name='Combined', slug='L0_', source_identity='source-uuid', collection_path='Body')

    def job(self, fmt='PSD', depth=8):
        transparent_cache(self.cache/'L0_0001.png', (16,12), depth)
        return dict(format=fmt, depth=depth, cache_kind='PNG'+str(depth), extension='.png',
                    dir=str(self.cache), dest=str(self.root/('Art.'+fmt.lower())),
                    source_file='/test/Project.blend', source_scene='Scene', node_name='Output',
                    cache_history_root=str(self.root/'history'),
                    manifest=[dict(self.entry)], hierarchy='GROUPS', overwrite=True, canvas_size=[16,12])

    def disabled(self, job):
        job['manifest'][0].update(render_disabled=True, render_was_disabled=True, disabled_sources=['Scene/Combined'])
        (self.cache/'L0_0001.png').unlink(missing_ok=True)
        return job

    def test_new_hidden_psd_placeholder_at_8_and_16_bits(self):
        for depth in (8,16):
            with self.subTest(depth=depth):
                job = self.disabled(self.job(depth=depth))
                Path(job['dest']).unlink(missing_ok=True)
                assemble(job)
                doc = PSDImage.open(job['dest']); layer = doc[0][0]
                self.assertEqual(doc.depth, depth)
                self.assertFalse(layer.visible)
                alpha = layer.numpy('mask') if layer.has_mask() else layer.numpy('alpha')
                self.assertEqual(alpha.max(), 0)
                self.assertTrue(any('hidden blank PSD' in s for s in job['_notices']))

    def test_missing_enabled_image_still_fails(self):
        job=self.disabled(self.job());job['manifest'].append(dict(name='Enabled',slug='missing'))
        with self.assertRaisesRegex(FileNotFoundError,'Enabled'):find_inputs(job)

    def test_disabled_ignores_stale_pixels_and_vector_candidate(self):
        job=self.job();job['manifest'][0].update(render_disabled=True, render_was_disabled=True, vector_svg='old.svg')
        Image.new('RGBA',(16,12),'red').save(self.cache/'L0_0001.png')
        entry,path=find_inputs(job)[0]
        self.assertEqual(read_rgba(path)[...,-1].max(),0)
        self.assertEqual(entry['vector_svg'],'')

    def test_all_disabled_flattened_new_output_transparent(self):
        job=self.disabled(self.job('PNG'));job['flatten']=True;assemble(job)
        self.assertEqual(np.asarray(Image.open(job['dest']))[...,-1].max(),0)

    def test_depth_16_placeholder_is_native_png16(self):
        job=self.disabled(self.job(depth=16));_,path=find_inputs(job)[0]
        self.assertEqual(path.read_bytes()[24],16)
        self.assertEqual(read_rgba(path,16).shape,(12,16,4))

    def donor(self, job, name, color='red', timestamp=100, **entry_changes):
        root = self.root/'history'/('blend_psd_render_'+name);folder=root/'png8';folder.mkdir(parents=True)
        previous=dict(job,dir=str(folder),manifest=[dict(job['manifest'][0],render_disabled=False,render_was_disabled=False,**entry_changes)])
        file=folder/'L0_0001.png';Image.new('RGBA',(16,12),color).save(file);os.utime(file,(timestamp,timestamp))
        (root/'jobs.json').write_text(json.dumps({'jobs':[previous]}))
        return file,previous

    def test_latest_compatible_image_reused_in_psd_svg_and_flattened_png(self):
        job=self.job();self.donor(job,'old','red',100);file,_=self.donor(job,'new','blue',200)
        original=file.read_bytes();self.disabled(job)
        for fmt in ('PSD','SVG','PNG'):
            with self.subTest(fmt=fmt):
                job.update(format=fmt,dest=str(self.root/('Art.'+fmt.lower())),flatten=fmt=='PNG')
                assemble(job)
                self.assertEqual(held_path(job,job['manifest'][0]).read_bytes(),original)
                self.assertTrue(any('last rendered image' in s for s in job['_notices']))
                if fmt=='PSD':
                    layer=PSDImage.open(job['dest'])[0][0];self.assertTrue(layer.visible)
                    np.testing.assert_allclose(layer.numpy()[0,0,:3],[0,0,1])
                elif fmt=='SVG':
                    root=ET.parse(job['dest']).getroot()
                    group=next(n for n in root.iter(SVG+'g') if n.get(INK+'label')=='Combined')
                    self.assertIsNone(group.get('display'))
                    self.assertEqual(len(list(root.iter(SVG+'image'))),1)
                else:self.assertEqual(Image.open(job['dest']).getpixel((0,0)),(0,0,255,255))

    def test_held_copy_survives_original_cache_cleanup_without_freshening_mtime(self):
        job=self.job();self.donor(job,'old','red',123);self.disabled(job)
        first=find_inputs(job)[0][1]
        self.assertEqual(int(first.stat().st_mtime),123)
        shutil.rmtree(self.root/'history')
        self.assertEqual(find_inputs(job)[0][1].read_bytes(),first.read_bytes())
        self.assertEqual(int(first.stat().st_mtime),123)

    def test_new_cache_can_reuse_legacy_history_root(self):
        job=self.job();file,_=self.donor(job,'legacy-root','blue',123)
        job['cache_history_roots']=[str(self.root/'new-history'),str(self.root/'history')]
        self.disabled(job);entry,path=find_inputs(job)[0]
        self.assertFalse(entry['render_placeholder'])
        self.assertEqual(path.read_bytes(),file.read_bytes())

    def test_wrong_source_project_color_settings_and_size_are_rejected(self):
        for change in ('source','project','color','size','depth'):
            with self.subTest(change=change):
                shutil.rmtree(self.root/'history',ignore_errors=True)
                job=self.job();file,previous=self.donor(job,'wrong')
                if change=='source':previous['manifest'][0]['source_identity']='unrelated'
                if change=='project':previous['source_file']='/another/Project.blend'
                if change=='color':previous['save_as_render']=False
                if change=='size':Image.new('RGBA',(8,8),'red').save(file)
                if change=='depth':previous['cache_kind']='PNG16'
                (file.parent.parent/'jobs.json').write_text(json.dumps({'jobs':[previous]}))
                self.disabled(job);entry,_=find_inputs(job)[0]
                self.assertTrue(entry['render_placeholder'])

    def test_legacy_jobs_require_exact_destination_and_unique_source(self):
        job=self.job();file,previous=self.donor(job,'legacy')
        previous.pop('source_file');previous.pop('source_scene');previous['manifest'][0].pop('source_identity')
        previous['manifest'][0]['source_view_layer']='Combined';job['manifest'][0]['source_view_layer']='Combined'
        (file.parent.parent/'jobs.json').write_text(json.dumps({'jobs':[previous]}))
        self.disabled(job);entry,path=find_inputs(job)[0]
        self.assertFalse(entry['render_placeholder']);self.assertEqual(path.read_bytes(),file.read_bytes())
        path.unlink();previous['dest']='different.psd'
        (file.parent.parent/'jobs.json').write_text(json.dumps({'jobs':[previous]}))
        self.assertTrue(find_inputs(job)[0][0]['render_placeholder'])
        previous['dest']=job['dest'];previous['manifest'].append(dict(previous['manifest'][0],slug='ambiguous'))
        (file.parent.parent/'jobs.json').write_text(json.dumps({'jobs':[previous]}))
        self.assertTrue(find_inputs(job)[0][0]['render_placeholder'])

    def test_corrupt_latest_image_falls_back_to_older_valid_render(self):
        job=self.job();valid,_=self.donor(job,'valid','red',100)
        corrupt,_=self.donor(job,'corrupt','blue',200)
        data=bytearray(corrupt.read_bytes());data[29]^=255;corrupt.write_bytes(data)
        os.utime(corrupt,(200,200));self.disabled(job)
        entry,path=find_inputs(job)[0]
        self.assertFalse(entry['render_placeholder'])
        self.assertEqual(path.read_bytes(),valid.read_bytes())

    def test_retry_can_hold_image_from_the_selected_render(self):
        job=self.job();Image.new('RGBA',(16,12),'green').save(self.cache/'L0_0001.png')
        job['manifest'][0].update(render_disabled=True,render_was_disabled=False)
        entry,path=find_inputs(job)[0]
        self.assertFalse(entry['render_placeholder'])
        self.assertEqual(Image.open(path).getpixel((0,0)),(0,128,0,255))

    def test_flattened_overlay_darken_and_lighten_keep_held_background(self):
        for mode,expected in [('overlay',(.25,.375,.125)),('darken',(.25,.25,.25)),('lighten',(.5,.75,.25))]:
            with self.subTest(mode=mode):
                # Neutral background and RGB foreground, with exact PNG sample
                # expectations calculated using the standard blend equations.
                shutil.rmtree(self.root/'history',ignore_errors=True)
                job=self.job('PNG');self.donor(job,'background',(64,64,64,255),100)
                self.disabled(job);Image.new('RGBA',(16,12),(128,192,64,255)).save(self.cache/'front.png')
                job['manifest'].insert(0,dict(name='Front.'+mode,slug='front'))
                job['flatten']=True;assemble(job)
                pixel=np.asarray(Image.open(job['dest']))[0,0,:3]/255
                np.testing.assert_allclose(pixel,expected,atol=.008)


if __name__=='__main__':unittest.main()
