"""Pixel/metadata fidelity for exporter optimisations, independent of timing."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from psd_tools import PSDImage
from raster_bounds import crop_rgba
from psd_worker import assemble_psd, merge_layers
from merge_groups import over
from test_color_management import filtered_png16
from export_performance import profile_export, timed


class ExportPerformance(unittest.TestCase):
    def test_crop_preserves_hidden_rgb_fractional_alpha_and_hdr(self):
        for depth in (8,16,32):
            array=np.zeros((7,11,4),np.float32)
            array[3,5]=[.23,.42,.66,1/65535]
            array[1,2]=[.9,0,0,0]  # Hidden RGB is meaningful editable data.
            if depth==32:array[4,7]=[-.2,3.5,.7,.75]
            cropped,left,top=crop_rgba(array)
            restored=np.zeros_like(array);restored[top:top+cropped.shape[0],left:left+cropped.shape[1]]=cropped
            np.testing.assert_array_equal(restored,array)
            self.assertEqual((left,top),(2,1))

    def test_blank_crop_remains_an_editable_one_pixel_layer(self):
        cropped,left,top=crop_rgba(np.zeros((7,9,4),np.float32))
        self.assertEqual((cropped.shape,left,top),((1,1,4),0,0))

    def test_native_psd_offsets_masks_and_16bit_values(self):
        for depth in (8,16):
            with tempfile.TemporaryDirectory() as folder:
                folder=Path(folder);source=folder/'in.png';dest=folder/'out.psd'
                array=np.zeros((9,13,4),np.uint16 if depth==16 else np.uint8)
                maximum=np.iinfo(array.dtype).max
                array[2:5,4:8]=[maximum//3,maximum//2,maximum,maximum//4]
                if depth==16:filtered_png16(source,array,4)
                else:Image.fromarray(array,'RGBA').save(source)
                job=dict(dest=str(dest),depth=depth,format='PSD',extension='.png',hierarchy='FLAT',overwrite=True)
                assemble_psd(job,[({'name':'Paint.multiply'},source)])
                doc=PSDImage.open(dest);layer=doc[0]
                self.assertEqual(layer.bbox,(4,2,8,5));self.assertEqual(layer.name,'Paint')
                expected=array.astype(np.float32)/maximum
                restored=np.zeros_like(expected);pixels=layer.numpy().copy()
                if layer.has_mask():pixels[...,3:4]=layer.numpy('mask')
                restored[2:5,4:8]=pixels
                np.testing.assert_allclose(restored,expected,atol=1/maximum)
                if depth==8:
                    self.assertEqual(layer.mask.bbox,(4,2,8,5))
                    self.assertEqual(layer.mask.background_color,0)

    def test_streaming_matches_previous_compositing_exactly_all_modes(self):
        modes=['normal','multiply','screen','add','overlay','darken','lighten']
        rng=np.random.default_rng(42);arrays=[rng.random((9,13,4),dtype=np.float32) for _ in modes]
        inputs=[({'name':'Paint.'+mode},Path(str(i)+'.png')) for i,mode in enumerate(modes)]
        expected=np.zeros_like(arrays[0])
        for array,mode in reversed(list(zip(arrays,modes))):expected=over(expected,array,mode)
        calls=[]
        def read(path,source_depth):calls.append(str(path));return arrays[int(path.stem)].copy()
        with patch('psd_worker.read_rgba',side_effect=read):actual=merge_layers(inputs)
        np.testing.assert_array_equal(actual,expected)
        self.assertEqual(calls,[str(i)+'.png' for i in reversed(range(len(modes)))])

    def test_timings_record_success_and_failure_without_changing_results(self):
        @timed('part')
        def work(fail):
            if fail:raise ValueError('expected')
            return 17
        @profile_export
        def export(job):return work(job.get('fail'))
        job={};self.assertEqual(export(job),17)
        self.assertEqual(job['_performance']['stages']['part']['calls'],1)
        self.assertGreaterEqual(job['_performance']['total_seconds'],job['_performance']['stages']['part']['seconds'])
        job={'fail':True}
        with self.assertRaisesRegex(ValueError,'expected'):export(job)
        self.assertIn('total_seconds',job['_performance'])

    def test_psd32_crop_round_trip_keeps_hdr_negative_and_tiny_alpha(self):
        with tempfile.TemporaryDirectory() as folder:
            pixels=np.zeros((9,13,4),np.float32)
            pixels[2:5,4:8]=[-.25,4.5,.23,1e-7]
            job=dict(dest=str(Path(folder)/'HDR.psd'),format='PSD',depth=32,extension='.exr',
                     hierarchy='FLAT',overwrite=True,psd_compression='ZIP')
            with patch('psd_worker.read_rgba',return_value=pixels):
                assemble_psd(job,[({'name':'HDR'},Path(folder)/'input.exr')])
            doc=PSDImage.open(job['dest']);self.assertEqual(doc[0].bbox,(4,2,8,5))
            np.testing.assert_array_equal(doc[0].numpy(),pixels[2:5,4:8])

    def test_all_compression_choices_keep_document_and_layer_pixels(self):
        from psd_tools.constants import Compression
        rng=np.random.default_rng(59)
        for depth in (8,16,32):
            pixels=rng.random((9,13,4),dtype=np.float32)
            if depth==32:pixels[...,:3]=pixels[...,:3]*4-1
            reference=None
            for codec in ('RLE','ZIP','ZIP_WITH_PREDICTION','RAW'):
                with self.subTest(depth=depth,codec=codec):
                    doc=PSDImage.new('RGB',(13,9),depth=depth,compression=Compression[codec])
                    doc.create_pixel_layer_from_array(pixels,compression=Compression[codec])
                    stream=io.BytesIO();doc.save(stream);stream.seek(0);loaded=PSDImage.open(stream)
                    if reference is None:reference=loaded[0].numpy()
                    else:np.testing.assert_array_equal(loaded[0].numpy(),reference)

    def test_worker_keeps_portable_preview_and_selected_layer_compression(self):
        from psd_tools.constants import Compression
        for fmt in ('PSD','PSB'):
            for depth in (8,16,32):
                with self.subTest(format=fmt,depth=depth), tempfile.TemporaryDirectory() as folder:
                    folder=Path(folder);source=folder/'source.png'
                    pixels=np.zeros((9,13,4),np.float32);pixels[2:7,3:9]=[.25,.5,.75,1]
                    Image.fromarray((pixels*255).astype('uint8'),'RGBA').save(source)
                    dest=folder/('portable.'+fmt.lower())
                    job=dict(dest=str(dest),format=fmt,depth=depth,hierarchy='FLAT',overwrite=True,
                             extension='.exr' if depth==32 else '.png',psd_compression='AUTO')
                    with patch('psd_worker.read_rgba',return_value=pixels):
                        assemble_psd(job,[({'name':'Paint'},source)])
                    doc=PSDImage.open(dest)
                    self.assertEqual(doc.depth,depth)
                    self.assertEqual(doc._record.image_data.compression,Compression.RLE)
                    self.assertTrue(all(channel.compression==Compression.ZIP for channel in doc[0]._channels))
                    np.testing.assert_allclose(doc.numpy('color')[4,5],[.25,.5,.75],atol=1/255)
                    self.assertGreater(doc[0].numpy()[2,2,-1],.99)
