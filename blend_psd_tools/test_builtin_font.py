import json
from pathlib import Path
import struct
import tempfile
import unittest

from builtin_font import embedded_bfont
from font_delivery import font_names, write_font_output


def fixture_pfb():
    header=(b'%!PS-AdobeFont-1.0: Bfont 001.001\n/FamilyName (Bfont) def\n'
            b'/Weight (Regular) def\n/ItalicAngle 0 def\n')
    def segment(kind,data):return bytes((0x80,kind))+struct.pack('<I',len(data))+data
    return segment(1,header)+segment(2,b'original encrypted glyph data')+segment(1,b'cleartomark\n')+b'\x80\x03'


class BuiltinFontTests(unittest.TestCase):
    def test_exact_embedded_resource_delivery_and_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);raw=fixture_pfb();binary=p/'blender';binary.write_bytes(b'program prefix'+raw+b'other program data')
            before=binary.read_bytes()
            self.assertEqual(embedded_bfont(binary),raw)
            dest=p/'output'/'Shot.fonts.json'
            write_font_output(dict(dest=str(dest),fonts=[dict(name='Bfont Regular',file='<builtin>',builtin_binary=str(binary))]),logger=lambda *a:None)
            result=json.loads(dest.read_text());font=result['fonts'][0];copied=dest.parent/font['file']
            self.assertTrue(result['complete']);self.assertFalse(font['substituted'])
            self.assertNotIn('compatible_file',font,'A different font with the Bfont name must never receive the bundled counterpart')
            self.assertEqual(copied.suffix,'.pfb');self.assertEqual(copied.read_bytes(),raw)
            self.assertEqual(font_names(copied)['family'],'Bfont')
            self.assertEqual(font_names(copied)['style'],'Regular')
            self.assertEqual(binary.read_bytes(),before)

    def test_incomplete_resource_is_rejected_without_reading_past_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'blender';p.write_bytes(b'prefix'+fixture_pfb()[:-2])
            with self.assertRaisesRegex(ValueError,'could not be identified'):embedded_bfont(p)

    def test_competing_different_resources_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            raw=fixture_pfb();p=Path(d)/'blender';p.write_bytes(raw+raw.replace(b'glyph data',b'other data'))
            with self.assertRaisesRegex(ValueError,'could not be identified'):embedded_bfont(p)
