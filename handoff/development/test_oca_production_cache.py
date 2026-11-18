"""Non-destructive full-resolution production-cache trim/reconstruction check.

Usage: Blender's bundled python3.13 this.py jobs.json output-directory
No scene or original render cache is changed.
"""
import copy,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from pillow_loader import ensure_pillow
ensure_pillow()
import numpy as np
from PIL import Image
from psd_worker import assemble
from oca_project import nodes
from oca_validation import validate

def run():
 source=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
 job=next(j for j in json.loads(source.read_text())['jobs'] if j['format']=='OCA')
 entry=next(e for e in job['manifest'] if e['name']=='ForeArm_R')
 cached=next(Path(job['dir']).glob(entry['slug']+'*.png'))
 local=out/'cache';local.mkdir(exist_ok=True);shutil.copy2(cached,local/cached.name)
 image=Image.open(local/cached.name).convert('RGBA');box=image.getchannel('A').getbbox();assert box
 job=copy.deepcopy(job);job.update(dir=str(local),manifest=[entry],oca_layout='PROJECT',overwrite=True)
 job.pop('oca_frames',None);job.pop('oca_range',None)
 entry=job['manifest'][0];entry.update(vector_svg='',vector_reason='Existing full-resolution rendered cache')
 results=[];reconstructed=[]
 for trim in (False,True):
  job['dest']=str(out/('Trimmed.oca' if trim else 'Full.oca'))
  job['oca_options'].update(trimWhitespace=trim,padding=0,scale=100,writeJson=False,writeTemplate=False)
  path=Path(assemble(job));document=json.loads(path.read_text());validate(document,path.parent)
  layer=next(n for n in nodes(document['layers']) if n['frames']);cel=layer['frames'][0]
  asset=Image.open(path.parent/cel['fileName']).convert('RGBA');w,h=asset.size
  expected=(box[2]-box[0],box[3]-box[1]) if trim else image.size
  assert asset.size==expected,(asset.size,expected)
  left,top=cel['position'][0]-w/2,cel['position'][1]-h/2
  assert left.is_integer() and top.is_integer()
  canvas=Image.new('RGBA',image.size);canvas.paste(asset,(int(left),int(top)))
  actual=np.asarray(canvas);original=np.asarray(image)
  np.testing.assert_array_equal(actual[...,3],original[...,3])
  np.testing.assert_array_equal(actual[original[...,3]>0],original[original[...,3]>0])
  reconstructed.append(actual)
  results.append(dict(trim=trim,physical_size=asset.size,centre=cel['position'],document=str(path)))
 np.testing.assert_array_equal(reconstructed[0][...,3],reconstructed[1][...,3])
 report=dict(source_cache=str(cached),source_size=image.size,alpha_bounds=box,checks=results,visible_pixels_identical=True)
 (out/'result.json').write_text(json.dumps(report,indent=2));print('PRODUCTION_CROP_PASS',json.dumps(report))
if __name__=='__main__':run()
