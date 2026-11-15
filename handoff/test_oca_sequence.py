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

    def test_incomplete_sequence_does_not_replace_existing_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);destination=root/'Animation.oca';destination.write_text('existing artwork')
            with self.assertRaisesRegex(ValueError,'incomplete'):
                assemble(dict(format='OCA',dest=str(destination),overwrite=True,
                    oca_range=[1,3,1],oca_frames=[dict(frame=1),dict(frame=3)]))
            self.assertEqual(destination.read_text(),'existing artwork')
