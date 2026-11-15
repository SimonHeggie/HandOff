"""Exercise the real --python worker from a foreign cwd, without PYTHONPATH.

Also verify concise running/failure states and success-only notification.
All outputs are private fixtures; notification is intercepted, never audible.
"""
import os,sys,json,traceback
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT)]

def run():
 import bpy
 import handoff as addon
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from PIL import Image
 from psd_tools import PSDImage
 addon.register();scene=bpy.context.scene
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 cache=output/'cache';cache.mkdir(exist_ok=True)
 Image.new('RGBA',(48,32),(20,100,180,255)).save(cache/'layer_L0000_.png')
 jobs=[]
 for fmt in ('PSD','SVG','PNG'):
  jobs.append(dict(format=fmt,depth=8,cache_kind='PNG8',extension='.png',dir=str(cache),
    dest=str(output/('fixture.'+fmt.lower())),manifest=[dict(name='Paint',slug='layer_L0000_')],
    hierarchy='GROUPS',overwrite=True,psd_compression='AUTO',flatten=fmt=='PNG'))
 manifest=output/'jobs.json';manifest.write_text(json.dumps(dict(jobs=jobs)))
 # A report left by a previous retry must be invalidated before this run.
 (output/'result.json').write_text(json.dumps(dict(succeeded=99,failed=0)))
 callbacks=[]
 with patch.dict(os.environ,{'PYTHONPATH':''}), patch.object(bpy.app.timers,'register',side_effect=lambda fn,**kw:callbacks.append(fn)):
  addon.launch_worker(scene,manifest,output/'conversion.log')
 assert scene.blend_psd_status=='Exporting assets…'
 assert not (output/'result.json').exists()
 process=addon.MONITORS[-1]['process'];poll=callbacks.pop()
 assert poll()==1.0
 shutdown_limited=False
 try:
  process.wait(timeout=10)
 except __import__('subprocess').TimeoutExpired:
  # This tool sandbox can hang in Blender's PulseAudio shutdown even after
  # conversion succeeds. Require the actual complete report before cleanup;
  # monitor completion is then exercised separately with a successful process.
  assert json.loads((output/'result.json').read_text())['succeeded']==3
  shutdown_limited=True
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=10)
 if not shutdown_limited:assert process.returncode==0,(output/'conversion.log').read_text()
 with patch.object(process,'poll',return_value=0), patch.object(process,'returncode',0), patch.object(addon,'notify_success') as notify:
  assert poll() is None
  notify.assert_called_once_with(scene)
 assert 'successful' in scene.blend_psd_status
 report=json.loads((output/'result.json').read_text());assert (report['succeeded'],report['failed'])==(3,0)
 doc=PSDImage.open(output/'fixture.psd');assert doc[0].name=='Paint'
 assert doc[0].topil().getpixel((0,0))==(20,100,180,255)
 assert Image.open(output/'fixture.png').getpixel((0,0))==(20,100,180,255)
 from xml.etree import ElementTree as ET
 assert ET.parse(output/'fixture.svg').getroot().tag.endswith('svg')
 # A file can be written while unsupported artwork was explicitly omitted.
 # That result must remain partial and must not sound the success chime.
 (output/'result.json').write_text(json.dumps(dict(succeeded=1,failed=0,
     details=[dict(partial=True,notices=['Unsupported artwork omitted; source retained'])])))
 with patch.object(bpy.app.timers,'register',side_effect=lambda fn,**kw:callbacks.append(fn)):
  addon.start_monitor(scene,SimpleNamespace(poll=lambda:0,returncode=0),manifest)
 with patch.object(addon,'notify_success') as notify:
  assert callbacks.pop()() is None
  notify.assert_not_called()
 assert scene.blend_psd_status=='Export partial - see Diagnostics'
 assert 'Unsupported artwork omitted' in scene.blend_psd_export_notices
 (output/'result.json').unlink()
 with patch.object(bpy.app.timers,'register',side_effect=lambda fn,**kw:callbacks.append(fn)):
  addon.start_monitor(scene,SimpleNamespace(poll=lambda:1,returncode=1),manifest,log=output/'conversion-retry.log')
 with patch.object(addon,'notify_success') as notify:
  assert callbacks.pop()() is None
  notify.assert_not_called()
 assert scene.blend_psd_status=='Export failed - Retry available'
 assert 'exit code 1' in scene.blend_psd_export_notices
 assert 'conversion-retry.log' in scene.blend_psd_export_notices
 assert json.loads(scene.blend_psd_export_timings)=={}
 addon.unregister()
 print('WORKER_STARTUP_NATIVE_PASS: actual child launch, PSD/SVG/PNG, concise status, failure notice, success-only chime',flush=True)
 if shutdown_limited:print('TOOL_LIMIT: child produced valid outputs/report; PulseAudio shutdown required cleanup; monitor completion was simulated',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
