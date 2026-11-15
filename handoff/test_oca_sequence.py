import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from psd_worker import assemble


class OCASequence(unittest.TestCase):
    def test_negative_frames_are_resolved_exactly_and_exposures_use_frame_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);frames=[]
            for frame,color in ((-1,'red'),(0,'green'),(1,'blue')):
                folder=root/'cache';folder.mkdir(exist_ok=True)
                Image.new('RGBA',(4,3),color).save(folder/f'L0_{frame:04d}.png')
                frames.append(dict(format='OCA',frame=frame,cache_frame=frame,dir=str(folder),
                    extension='.png',depth=8,hierarchy='GROUPS',overwrite=True,
                    frame_rate=23.976,manifest=[dict(name='Part',slug='L0_',collection_path='Art')]))
            job=dict(frames[-1],dest=str(root/'Animation.oca'),oca_frames=frames,oca_range=[-1,1,1])
            assemble(job);document=json.loads((root/'Animation.oca').read_text())
            self.assertEqual((document['startTime'],document['endTime']),(-1,2))
            layer=document['layers'][0]['childLayers'][0]
            self.assertTrue(layer['animated']);self.assertEqual([f['frameNumber'] for f in layer['frames']],[-1,0,1])
            self.assertEqual([f['duration'] for f in layer['frames']],[1,1,1])
            self.assertEqual([Image.open(root/f['fileName']).getpixel((0,0)) for f in layer['frames']],
                [(255,0,0,255),(0,128,0,255),(0,0,255,255)])

    def test_trimmed_oca_uses_native_frame_bounds_and_unindexed_filename(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); cache = root / 'cache'; cache.mkdir()
            original = np.zeros((7, 9, 4), dtype=np.uint8)
            original[3:5, 4:7] = [30, 100, 240, 255]
            original[1, 2] = [20, 30, 40, 0]  # Preserve hidden RGB.
            Image.fromarray(original, 'RGBA').save(cache / 'Part_00000.png')
            job = dict(format='OCA', dir=str(cache), dest=str(root/'Character.oca'),
                       frame=0, depth=8, extension='.png', overwrite=True,
                       hierarchy='GROUPS', trim_empty_pixels=True,
                       manifest=[dict(name='Hood_FG', slug='Part_', collection_path='Headgear')])
            assemble(job)
            data = json.loads((root/'Character.oca').read_text())
            layer = data['layers'][0]['childLayers'][0]
            cel = layer['frames'][0]
            self.assertEqual(cel['fileName'], 'Character/Headgear/Hood_FG_00000.png')
            self.assertEqual((layer['width'],layer['height']), (9,7))
            self.assertEqual((cel['width'],cel['height']), (5,4))
            self.assertEqual(cel['position'], [4.5,3.0])
            with Image.open(root / cel['fileName']) as png:
                cropped = np.asarray(png.convert('RGBA'))
            reconstructed = np.zeros_like(original)
            reconstructed[1:5,2:7] = cropped
            np.testing.assert_array_equal(reconstructed, original)

    def test_oca_preserves_collection_colour_labels_on_groups_and_paint_layers(self):
        from collection_colors import source_collection_colors
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); cache=root/'cache';cache.mkdir()
            for slug in ('A_','B_'):
                Image.new('RGBA',(5,4),(10,50,90,255)).save(cache/(slug+'00000.png'))
            collections={k:SimpleNamespace(color_tag=v) for k,v in {
                'Costume':'COLOR_05', 'ForeArm_R':'COLOR_03',
                'Head':'NONE'}.items()}
            inputs=[dict(name='Arm', slug='A_', collection_path='Costume/ForeArm_R'),
                    dict(name='Head', slug='B_', collection_path='Costume/Head')]
            for entry in inputs:
                entry['collection_colors']=source_collection_colors(entry['collection_path'],collections)
            assemble(dict(format='OCA',dir=str(cache),dest=str(root/'Character.oca'),
                frame=0,depth=8,extension='.png',overwrite=True,hierarchy='GROUPS',
                manifest=inputs))
            data=json.loads((root/'Character.oca').read_text())
            costume=data['layers'][0]
            self.assertEqual(costume['name'],'Costume')
            self.assertEqual(costume['label'],5)  # Blender blue -> OCA label 5.
            forearm=next(c for c in costume['childLayers'] if c['name']=='ForeArm_R')
            self.assertEqual(forearm['label'],3)  # Yellow.
            self.assertEqual(forearm['childLayers'][0]['label'],3)
            head=next(c for c in costume['childLayers'] if c['name']=='Head')
            self.assertEqual(head['label'],-1) # Explicitly untagged collection.
            self.assertEqual(head['childLayers'][0]['label'],-1)

    def test_oca_animation_keeps_colour_labels_and_layer_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); cache=root/'cache';cache.mkdir();frames=[]
            for frame in (0,1):
                Image.new('RGBA',(5,4),(40+frame,30,20,255)).save(cache/f'A_{frame:05d}.png')
                Image.new('RGBA',(5,4),(20,80+frame,50,255)).save(cache/f'B_{frame:05d}.png')
                frames.append(dict(format='OCA',frame=frame,cache_frame=frame,dir=str(cache),
                    extension='.png',depth=8,hierarchy='GROUPS',overwrite=True,frame_rate=12,
                    manifest=[dict(name='Top',slug='A_',collection_path='Assets',collection_colors=['BLUE']),
                              dict(name='Bottom',slug='B_',collection_path='Assets',collection_colors=['BLUE'])]))
            assemble(dict(frames[-1],dest=str(root/'Frames.oca'),oca_frames=frames,oca_range=[0,1,1]))
            doc=json.loads((root/'Frames.oca').read_text())
            group=doc['layers'][0]
            self.assertEqual(group['label'],5)
            self.assertEqual([c['name'] for c in group['childLayers']],['Bottom','Top'])
            for child in group['childLayers']:
                self.assertEqual(child['label'],5)
                self.assertEqual(len(child['frames']),2)

    def test_duplicate_layer_names_are_disambiguated_without_order_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); cache=root/'cache';cache.mkdir()
            for slug,col in (('A_', 'red'), ('B_', 'blue')):
                Image.new('RGBA',(4,4),col).save(cache/(slug+'00000.png'))
            job=dict(format='OCA',dir=str(cache),dest=str(root/'Character.oca'),frame=0,
                     depth=8,extension='.png',overwrite=True,hierarchy='GROUPS',
                     manifest=[dict(name='Hood_FG',slug=slug,collection_path='Headgear')
                               for slug in ('A_','B_')])
            assemble(job)
            data=json.loads((root/'Character.oca').read_text())
            group=data['layers'][0]
            files=[f['fileName'] for l in group['childLayers'] for f in l['frames']]
            self.assertEqual(set(files), {
                'Character/Headgear/Hood_FG_00000.png',
                'Character/Headgear/Hood_FG-2_00000.png'})
            self.assertEqual(len(set(files)),2)
            self.assertTrue(all((root/path).is_file() for path in files))

    def test_animation_trim_bounds_change_per_frame_without_moving_layer(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'cache';cache.mkdir();frames=[];images=[]
            for frame, (left,top) in enumerate(((1,2),(5,1))):
                array=np.zeros((8,10,4),dtype=np.uint8)
                array[top:top+2,left:left+2]=[50,100+frame,140,255]
                Image.fromarray(array,'RGBA').save(cache/f'L0_{frame:04d}.png')
                images.append(array)
                frames.append(dict(format='OCA',frame=frame,cache_frame=frame,
                    dir=str(cache),extension='.png',depth=8,hierarchy='GROUPS',overwrite=True,
                    trim_empty_pixels=True,frame_rate=12,
                    manifest=[dict(name='Arm',slug='L0_',collection_path='Character')]))
            assemble(dict(frames[-1],dest=str(root/'Move.oca'),oca_frames=frames,oca_range=[0,1,1]))
            doc=json.loads((root/'Move.oca').read_text())
            layer=doc['layers'][0]['childLayers'][0]
            self.assertEqual((layer['width'],layer['height'],layer['position']), (10,8,[5,4]))
            self.assertEqual([f['position'] for f in layer['frames']], [[2,3],[6,2]])
            self.assertEqual([f['width'] for f in layer['frames']], [2,2])
            self.assertEqual([f['fileName'] for f in layer['frames']],
                             ['Move/Character/Arm_00000.png','Move/Character/Arm_00001.png'])
            for idx, cel in enumerate(layer['frames']):
                with Image.open(root/cel['fileName']) as img:
                    patch=np.asarray(img.convert('RGBA'))
                restored=np.zeros_like(images[idx]);x,y=(1,2) if idx==0 else (5,1)
                restored[y:y+2,x:x+2]=patch
                np.testing.assert_array_equal(restored,images[idx])

    def test_sequence_uses_current_trim_setting_not_stale_frame_snapshot(self):
        """Retried/current OCA options must override captured frame-job settings."""
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'cache'
            cache.mkdir()
            frames = []
            for frame in (0, 1):
                pixels = np.zeros((8, 10, 4), dtype=np.uint8)
                pixels[2:4, 5:7] = [180, 80 + frame, 45, 255]
                Image.fromarray(pixels, 'RGBA').save(cache / f'Part_{frame:05d}.png')
                frames.append(dict(format='OCA', frame=frame, cache_frame=frame,
                    dir=str(cache), extension='.png', depth=8, hierarchy='FLAT',
                    overwrite=True, trim_empty_pixels=False, frame_rate=12,
                    manifest=[dict(name='Arm', slug='Part_')]))
            # The final settings were refreshed (e.g. by Retry), but the
            # per-frame snapshots still carry the earlier false value.
            job = dict(frames[-1], dest=str(root / 'Sequence.oca'),
                trim_empty_pixels=True, oca_frames=frames, oca_range=[0, 1, 1])
            assemble(job)
            doc = json.loads((root / 'Sequence.oca').read_text())
            cels = doc['layers'][0]['frames']
            self.assertEqual([(c['width'], c['height'], c['position']) for c in cels],
                             [(2, 2, [6, 3]), (2, 2, [6, 3])])
            for cel in cels:
                with Image.open(root / cel['fileName']) as img:
                    self.assertEqual(img.size, (2, 2))

    def test_sequence_respects_current_trim_off_even_if_frames_had_it_on(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'cache'
            cache.mkdir()
            frames = []
            for frame in (0, 1):
                pixels = np.zeros((8, 10, 4), dtype=np.uint8)
                pixels[2:4, 5:7] = [180, 80 + frame, 45, 255]
                Image.fromarray(pixels, 'RGBA').save(cache / f'Part_{frame:05d}.png')
                frames.append(dict(format='OCA', frame=frame, cache_frame=frame,
                    dir=str(cache), extension='.png', depth=8, hierarchy='FLAT',
                    overwrite=True, trim_empty_pixels=True, frame_rate=12,
                    manifest=[dict(name='Arm', slug='Part_')]))
            job = dict(frames[-1], dest=str(root / 'Sequence.oca'),
                trim_empty_pixels=False, oca_frames=frames, oca_range=[0, 1, 1])
            assemble(job)
            doc = json.loads((root / 'Sequence.oca').read_text())
            cels = doc['layers'][0]['frames']
            self.assertEqual([(c['width'], c['height']) for c in cels],
                             [(10, 8), (10, 8)])
            for cel in cels:
                with Image.open(root / cel['fileName']) as img:
                    self.assertEqual(img.size, (10, 8))

    def test_trim_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'cache';cache.mkdir()
            image=Image.new('RGBA',(10,9));image.putpixel((5,4),(9,8,7,255))
            image.save(cache/'Part_00000.png')
            assemble(dict(format='OCA',dir=str(cache),dest=str(root/'Full.oca'),frame=0,
                depth=8,extension='.png',overwrite=True,hierarchy='FLAT',
                trim_empty_pixels=False,manifest=[dict(name='Part',slug='Part_')]))
            cel=json.loads((root/'Full.oca').read_text())['layers'][0]['frames'][0]
            self.assertEqual((cel['width'],cel['height'],cel['position']), (10,9,[5,4.5]))

    def test_16bit_oca_crop_preserves_exact_samples(self):
        import numpy as np
        from test_color_management import filtered_png16
        from png16_pixels import read_png16_rgba
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'cache';cache.mkdir()
            original=np.zeros((8,10,4),dtype=np.uint16)
            original[2:5,3:7]=[9123,30321,65535,20000]
            original[1,2]=[1,2,3,0]
            filtered_png16(cache/'Part_00000.png',original,4)
            assemble(dict(format='OCA',dir=str(cache),dest=str(root/'Hi.oca'),frame=0,
                depth=16,extension='.png',overwrite=True,hierarchy='FLAT',
                manifest=[dict(name='Part',slug='Part_')]))
            cel=json.loads((root/'Hi.oca').read_text())['layers'][0]['frames'][0]
            self.assertEqual((cel['width'],cel['height'],cel['position']), (5,4,[4.5,3]))
            restored=np.zeros_like(original)
            pixels=np.rint(read_png16_rgba(root/cel['fileName'])*65535).astype(np.uint16)
            restored[1:5,2:7]=pixels
            np.testing.assert_array_equal(restored,original)

    def test_incomplete_sequence_does_not_replace_existing_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);destination=root/'Animation.oca';destination.write_text('existing artwork')
            with self.assertRaisesRegex(ValueError,'incomplete'):
                assemble(dict(format='OCA',dest=str(destination),overwrite=True,
                    oca_range=[1,3,1],oca_frames=[dict(frame=1),dict(frame=3)]))
            self.assertEqual(destination.read_text(),'existing artwork')
