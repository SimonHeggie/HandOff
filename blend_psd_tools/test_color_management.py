"""Blender-free colour fidelity and PSD metadata regression tests."""
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np
from png16_pixels import read_png16_rgba


def filtered_png16(path, values, mode):
    height, width, channels = values.shape
    raw = np.asarray(values, dtype='>u2').tobytes()
    stride, bpp = width*channels*2, channels*2
    previous = bytearray(stride)
    buffer = bytearray()
    for y in range(height):
        row = raw[y*stride:(y+1)*stride]
        filtered = bytearray(stride)
        for x, val in enumerate(row):
            a = row[x-bpp] if x >= bpp else 0
            b = previous[x]
            c = previous[x-bpp] if x >= bpp else 0
            if mode == 0: pred = 0
            elif mode == 1: pred = a
            elif mode == 2: pred = b
            elif mode == 3: pred = (a+b)//2
            else:
                p=a+b-c; da,db,dc=abs(p-a),abs(p-b),abs(p-c)
                pred=a if da<=db and da<=dc else b if db<=dc else c
            filtered[x] = (val-pred)&255
        buffer.append(mode)
        buffer.extend(filtered)
        previous=bytearray(row)
    def chunk(name, value):
        return struct.pack('>I',len(value))+name+value+struct.pack('>I',zlib.crc32(name+value))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,16,6 if channels==4 else 2,0,0,0))+chunk(b'IDAT',zlib.compress(buffer))+chunk(b'IEND',b''))


class TestColorManagement(unittest.TestCase):
    def test_png16_keeps_original_encoded_samples_all_filters(self):
        values=np.array([[[0,65535,32768,12345], [32767,256,9999,65535], [13,207,999,2222]],
                         [[65535,100,40000,0], [65534,512,32766,65535], [1111,987,1717,4444]]], dtype=np.uint16)
        with tempfile.TemporaryDirectory() as folder:
            for mode in range(5):
                path=Path(folder)/f'filter{mode}.png'
                filtered_png16(path,values,mode)
                got=read_png16_rgba(path)
                np.testing.assert_array_equal(np.rint(got*65535).astype('uint16'), values)

    def test_png16_rgb_creates_opaque_alpha(self):
        values=np.array([[[1,100,65000],[65535,0,32100]]],dtype=np.uint16)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'rgb.png';filtered_png16(path,values,4)
            got=read_png16_rgba(path)
            self.assertEqual(got.shape,(1,2,4))
            np.testing.assert_array_equal(np.rint(got[...,:3]*65535).astype('uint16'),values)
            self.assertTrue(np.all(got[...,3]==1))

    def test_psd16_icc_and_layer_sample_roundtrip(self):
        from psd_worker import assemble_psd
        from psd_tools import PSDImage
        from psd_tools.constants import Resource,SheetColorType
        arr=np.array([[[0,65535,32768,65535],[20000,40000,60000,32767]]],dtype=np.uint16)
        with tempfile.TemporaryDirectory() as folder:
            png=Path(folder)/'pixels.png';filtered_png16(png,arr,4)
            dst=Path(folder)/'test.psd'
            job=dict(dest=str(dst),format='PSD',depth=16,extension='.png',overwrite=True,
                     tag_profile='PASSTHROUGH',hierarchy='GROUPS',flatten=False)
            assemble_psd(job,[({'name':'Leaf','collection_path':'Col','collection_colors':['BLUE']},png)])
            out=PSDImage.open(dst)
            icc=out.image_resources.get_data(Resource.ICC_PROFILE)
            self.assertTrue(icc and icc[36:40]==b'acsp')
            self.assertEqual(out.depth,16)
            self.assertEqual(out[0].sheet_color,SheetColorType.BLUE)
            self.assertEqual(out[0][0].sheet_color,SheetColorType.BLUE)
            recovered=out[0][0].numpy()
            np.testing.assert_allclose(recovered,np.array(arr,np.float32)/65535,atol=1/65535)

    def test_psd32_has_linear_profile_and_unclipped_hdr(self):
        from psd_tools import PSDImage
        from psd_tools.constants import Resource, SheetColorType
        from psd_color_profiles import attach_document_profile
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'hdr.psd'
            psd=PSDImage.new('RGB',(2,1),depth=32)
            source=np.array([[[3.,.5,.25,1.],[.12,1.2,0.,.65]]],dtype=np.float32)
            psd.create_pixel_layer_from_array(source,name='HDR')
            old=os.environ.pop('OCIO',None)
            try: attach_document_profile(psd,32,{'extension':'.exr'})
            finally:
                if old is not None: os.environ['OCIO']=old
            psd.save(out)
            psd2=PSDImage.open(out)
            self.assertEqual(psd2.depth,32)
            self.assertTrue(psd2.image_resources.get_data(Resource.ICC_PROFILE))
            np.testing.assert_allclose(psd2[0].numpy(),source,atol=2e-6)

    def test_ungroup_and_merge_inherit_collection_colors(self):
        from PIL import Image
        from psd_worker import assemble_psd
        from psd_tools import PSDImage
        from psd_tools.constants import SheetColorType
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pixel.png'; Image.new('RGBA',(3,3),(155,40,222,255)).save(path)
            a={'name':'Leaf1','collection_path':'Outer/Hidden.ungroup','collection_colors':['GREEN','RED']}
            b={'name':'Leaf2','collection_path':'Outer/Merge.merge','collection_colors':['GREEN','YELLOW']}
            dst=Path(folder)/'color.psd'
            assemble_psd(dict(dest=str(dst),format='PSD',depth=8,extension='.png',overwrite=True,
                              tag_profile='PASSTHROUGH',hierarchy='GROUPS',flatten=False),[(a,path),(b,path)])
            doc=PSDImage.open(dst)
            self.assertEqual(doc[0].sheet_color,SheetColorType.GREEN)
            self.assertEqual(doc[0][0].sheet_color,SheetColorType.YELLOW)
            self.assertEqual(doc[0][1].sheet_color,SheetColorType.RED)

if __name__=='__main__': unittest.main()
