"""Automatic linked SVG fallbacks through real PNG8/16 and EXR32 caches."""
import os,sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]

def run():
 import bpy,numpy as np
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from psd_worker import assemble_psd,write_blender_image
 from disabled_layers import transparent_cache
 from psd_tools import PSDImage
 from psd_tools.constants import Tag,Resource,SheetColorType
 from test_svg_instances import artwork
 from svg_export import encode_svg
 from xml.etree import ElementTree as E
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 for depth,fmt in ((8,'PSD'),(16,'PSD'),(32,'PSB')):
  objects=[artwork('Master',gradient=True),artwork('Linked copy',(1,0,0,1,60,0),gradient=True)]
  for i,obj in enumerate(objects):
   obj['source_metadata']=dict(object_id=f'object-{depth}-{i}',data_id='shared-data',object_name=obj['name'],scene_name='Fixture')
   for drawing in obj['layers']:
    for stroke in drawing['strokes']:
     for stop in stroke['fill_gradient']['stops']:stop['linear']=[.2,.4,3.5]
  source=output/f'source-{depth}.svg';source.write_text(encode_svg(128,64,objects))
  source.with_suffix('.vectors.json').write_text(json.dumps(dict(width=128,height=64,objects=objects)))
  cache=output/(f'cache-{depth}'+('.exr' if depth==32 else '.png'))
  if depth==32:write_blender_image(cache,np.zeros((64,128,4),np.float32),32,fmt='EXR')
  else:transparent_cache(cache,(128,64),depth)
  dest=output/(f'Automatic-{depth}bit.'+fmt.lower())
  job=dict(format=fmt,dest=str(dest),depth=depth,extension=cache.suffix,hierarchy='GROUPS',overwrite=True,
   psd_compression='AUTO',psd_link_svg_fallbacks=False,psd_target='PHOTOCRAFT')
  assemble_psd(job,[(dict(name='Shine.overlay',collection_path='FX/Shine',
      collection_colors=['NO_COLOR','NO_COLOR'],vector_svg=str(source)),cache)])
  doc=PSDImage.open(dest);parts=[n for n in doc.descendants() if n.kind=='smartobject']
  assert len(parts)==1 and doc.depth==depth
  assert doc.version==(2 if fmt=='PSB' else 1)
  assert parts[0].sheet_color==SheetColorType.GRAY
  pixels=parts[0].numpy();assert pixels[...,3].max()>0
  if depth==32:assert pixels[...,2].max()>2
  if depth==32 and os.environ.get('OCIO'):
   assert not doc.image_resources.get_data(Resource.ICC_PROFILE)
  else:assert doc.image_resources.get_data(Resource.ICC_PROFILE)
  assert all(r['representation']=='LINKED_SMART_OBJECT' and r['target']=='PSD' for r in job['_publication'])
  links=doc.tagged_blocks.get_data(Tag.LINKED_LAYER_EXTERNAL);assert len(links)==1
  path=output/links[0].linked_file[b'relPath'].value;root=E.parse(path).getroot()
  assert len(list(root.iter('{http://www.w3.org/2000/svg}use')))==1
  print('AUTO_SVG_LINK_DEPTH_PASS',depth,fmt,dest,flush=True)
 print('AUTO_SVG_LINK_NATIVE_PASS: default automatic links, one shared source layer, PNG8/16, EXR32/HDR, PSD/PSB, Grey and ICC policy',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
