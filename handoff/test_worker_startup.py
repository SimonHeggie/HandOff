"""Execute the actual worker with isolated sys.path, like Blender --python."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from PIL import Image

class WorkerStartup(unittest.TestCase):
    def test_standalone_worker_bootstraps_before_helpers_and_writes_documents(self):
        worker=Path(__file__).parent/'psd_worker.py'
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);Image.new('RGBA',(12,8),(10,40,90,255)).save(folder/'layer_0.png')
            jobs=[dict(format=fmt,depth=8,extension='.png',cache_kind='PNG8',
                dir=str(folder),dest=str(folder/('art.'+fmt.lower())),
                manifest=[dict(name='Paint',slug='layer_0')],hierarchy='FLAT',
                overwrite=True,psd_compression='AUTO',flatten=fmt=='PNG') for fmt in ('PSD','SVG','PNG')]
            manifest=folder/'jobs.json';manifest.write_text(json.dumps(dict(jobs=jobs)))
            result=subprocess.run([sys.executable,'-I',str(worker),'--',str(manifest)],
                cwd=folder,capture_output=True,text=True,timeout=25)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads((folder/'result.json').read_text())
            self.assertEqual((report['succeeded'],report['failed']),(3,0))
            for job in jobs:self.assertGreater(Path(job['dest']).stat().st_size,16)
            self.assertEqual(Image.open(folder/'art.png').getpixel((0,0)),(10,40,90,255))
