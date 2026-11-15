import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from font_delivery import font_names, resolve_font, write_font_output, system_font_directory, user_font_directory


def font_bytes(family='Company Type', style='Regular'):
    strings = [family.encode('utf-16-be'), style.encode('utf-16-be')]
    records = b''
    at = 0
    for name_id, value in zip((1,2),strings):
        records += struct.pack('>6H',3,1,0x409,name_id,len(value),at); at += len(value)
    names = struct.pack('>3H',0,2,30) + records + b''.join(strings)
    return (struct.pack('>4s4H',b'\0\1\0\0',1,0,0,0) +
            struct.pack('>4s3I',b'name',0,28,len(names)) + names)


class FontDeliveryTests(unittest.TestCase):
    def test_font_identity_comes_from_file_not_filename(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'WrongFilename.ttf';p.write_bytes(font_bytes('Company Family','Semibold'))
            self.assertEqual(font_names(p)['family'],'Company Family')
            self.assertEqual(resolve_font(dict(name='Renamed',file=str(p)),lookup=False)['style'],'Semibold')
            resolved=resolve_font(dict(name='Bfont renamed real font',file=str(p)),lookup=False)
            self.assertFalse(resolved['substituted'])
            self.assertNotIn('notice',resolved)

    def test_used_font_copies_are_exact_and_never_copy_projects_or_clear_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'font.ttf';source.write_bytes(font_bytes())
            dest=p/'deliver'/'Shot.fonts.json';dest.parent.mkdir()
            keep=dest.parent/'important.blend';keep.write_bytes(b'original project')
            job=dict(dest=str(dest),fonts=[dict(name='Font',file=str(source))],text_objects=[dict(name='Title',text='Hello')])
            write_font_output(job,logger=lambda *a:None)
            data=json.loads(dest.read_text());copy=dest.parent/data['fonts'][0]['file']
            self.assertEqual(copy.read_bytes(),source.read_bytes())
            self.assertEqual(keep.read_bytes(),b'original project')
            self.assertEqual({x.suffix for x in copy.parent.iterdir()},{'.ttf'})
            bad=dict(job,fonts=[dict(name='bad',file=str(keep))])
            with self.assertRaises(ValueError):write_font_output(bad,logger=lambda *a:None)
            self.assertEqual(keep.read_bytes(),b'original project')

    def test_system_font_field_defaults_and_custom_folder_lookup(self):
        self.assertEqual(system_font_directory('Linux'),'/usr/share/fonts')
        self.assertEqual(system_font_directory('Darwin'),'/System/Library/Fonts')
        self.assertTrue(system_font_directory('Windows').endswith('Fonts'))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Brand.ttf';p.write_bytes(font_bytes('Brand'))
            result=resolve_font(dict(name='Brand',file='/missing/Brand.ttf'),d)
            self.assertEqual(result['family'],'Brand')
            self.assertFalse(result['substituted'])

    def test_user_font_destination_needs_no_system_folder_write(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'XDG_DATA_HOME':d,'LOCALAPPDATA':d}):
            folder=Path(user_font_directory('Linux'));folder.mkdir()
            (folder/'write-check').write_bytes(b'writable')
            self.assertEqual(folder,Path(d)/'fonts')
            self.assertEqual(Path(user_font_directory('Windows')),Path(d)/'Microsoft'/'Windows'/'Fonts')
            self.assertTrue(user_font_directory('Darwin').endswith('/Library/Fonts'))

    def test_builtin_never_substitutes_a_system_sans_font(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'NotoSans-Regular.ttf').write_bytes(font_bytes('Noto Sans'))
            result=resolve_font(dict(name='Bfont Regular',file='<builtin>',builtin_binary=str(Path(d)/'missing-blender')),d)
            self.assertEqual(result['family'],'Bfont')
            self.assertFalse(result['substituted'])
            self.assertFalse(result['file'])
            self.assertIn('Exact Bfont unavailable',result['notice'])

    def test_cancel_during_delivery_keeps_source_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'font.ttf';source.write_bytes(font_bytes());before=source.read_bytes()
            with patch('font_delivery.os.replace',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    write_font_output(dict(dest=str(p/'Shot.fonts.json'),fonts=[dict(name='Font',file=str(source))]))
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse(list(p.rglob('.handoff-font-*')))
