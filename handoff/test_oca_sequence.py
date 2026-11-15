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
