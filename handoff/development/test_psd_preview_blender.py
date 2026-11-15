"""Fresh portable PSD/PSB previews with ZIP channels, native 8/16/32-bit data."""
import os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]

def run():
 import numpy as np
 from pillow_loader import ensure_pillow
 ensure_pillow()
 from PIL import Image
 from psd_worker import assemble_psd,write_blender_image
 from psd_tools import PSDImage
 from psd_tools.constants import Compression
 from png16_pixels import read_png16_rgba
 from test_color_management import filtered_png16
 output=Path(os.environ['LAYERED_TEST_OUTPUT']);output.mkdir(parents=True,exist_ok=True)
 pixels=np.zeros((48,64,4),np.float32);pixels[8:40,12:52]=[.25,.5,.75,1]
 Image.fromarray((pixels*255).astype('uint8'),'RGBA').save(output/'source8.png')
 filtered_png16(output/'source16.png',(pixels*65535).astype('uint16'),0)
 write_blender_image(output/'source32.exr',pixels,32,fmt='EXR')
 for fmt in ('PSD','PSB'):
  for depth in (8,16,32):
   path=output/('portable'+str(depth)+'.'+fmt.lower())
   source=output/('source'+str(depth)+('.exr' if depth==32 else '.png'))
   job=dict(dest=str(path),depth=depth,format=fmt,extension=source.suffix,hierarchy='FLAT',
            overwrite=True,psd_compression='AUTO')
   assemble_psd(job,[({'name':'Artwork'},source)])
   doc=PSDImage.open(path)
   assert doc.depth==depth and doc._record.image_data.compression==Compression.RLE
   assert all(channel.compression==Compression.ZIP for channel in doc[0]._channels)
   assert np.allclose(doc.numpy('color')[24,32],[.25,.5,.75],atol=1/255)
 print('PSD_PORTABLE_PREVIEW_PASS: 8/16/32-bit PSD and PSB retain ZIP layers, RLE previews and pixels',flush=True)

if __name__=='__main__':
 try:run()
 except BaseException:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(1)
 sys.stdout.flush();sys.stderr.flush();os._exit(0)
