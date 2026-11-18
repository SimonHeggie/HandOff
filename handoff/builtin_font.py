"""Read Blender's exact embedded Bfont resource without accessing process memory.

Blender embeds release/datafiles/bfont.pfb verbatim with data_to_c_simple:
https://github.com/blender/blender/blob/main/source/blender/editors/datafiles/CMakeLists.txt
Only a bounded, complete PFB stream with Bfont's own identity is accepted.
"""
from functools import lru_cache
import hashlib
import json
import mmap
from pathlib import Path
import re
import struct

SIGNATURE = b'%!PS-AdobeFont-1.0: Bfont '


def pfb_names(header):
    def value(key, default=''):
        match=re.search(rb'/' + key + rb'\s+\(((?:\\.|[^\\)])*)\)',header)
        return (re.sub(rb'\\([\\()])',rb'\1',match[1]).decode('latin-1') if match else default)
    style=value(b'Weight','Regular')
    angle=re.search(rb'/ItalicAngle\s+(-?[\d.]+)',header)
    if angle and float(angle[1]) and not re.search('italic|oblique',style,re.I):style+=' Italic'
    return dict(family=value(b'FamilyName',value(b'FullName','Bfont')),
                style=style,copyright=value(b'Notice'))


@lru_cache(maxsize=4)
def _embedded(binary, size, modified):
    with Path(binary).open('rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        search=0;found=[]
        while True:
            signature=data.find(SIGNATURE,search)
            if signature<0:break
            search=signature+len(SIGNATURE);start=signature-6;pos=start;types=[]
            if start<0:continue
            try:
                for _ in range(16):
                    if pos+2>len(data) or data[pos]!=0x80:break
                    kind=data[pos+1]
                    if kind==3:
                        if types[:2]==[1,2] and types[-1]==1:
                            raw=bytes(data[start:pos+2])
                            header=raw[6:6+struct.unpack_from('<I',raw,2)[0]]
                            if pfb_names(header)['family']=='Bfont':found.append(raw)
                        break
                    if kind not in (1,2) or pos+6>len(data):break
                    length=struct.unpack_from('<I',data,pos+2)[0]
                    if not length or pos+6+length>len(data) or pos+6+length-start>2_000_000:break
                    types.append(kind);pos+=6+length
            except (ValueError,struct.error):continue
        unique=set(found)
        if len(unique)!=1:
            raise ValueError('Exact embedded Bfont resource could not be identified in this Blender binary')
        return unique.pop()


def embedded_bfont(binary):
    p=Path(binary);stat=p.stat()
    return _embedded(str(p),stat.st_size,stat.st_mtime_ns)


def cache_bfont(binary, folder):
    data=embedded_bfont(binary)
    path=Path(folder)/'fonts'/('Bfont-'+hashlib.sha256(data).hexdigest()[:20]+'.pfb')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.is_file() or path.read_bytes()!=data:path.write_bytes(data)
    return path


def compatible_bfont(data):
    """Return the verified OpenType counterpart only for its exact source font.

    Modern HarfBuzz/Pango readers do not accept Type 1. The optional asset
    retains the original cubic outlines and advances, not a substitute face.
    FontTools is used only by the developer build/verification script.
    """
    if not data.startswith(b'\x80\x01'):return None
    folder=Path(__file__).parent/'vendor'/'fonts'
    metadata=json.loads((folder/'Bfont-Regular.json').read_text())
    if hashlib.sha256(data).hexdigest()!=metadata['source_sha256']:return None
    converted=(folder/'Bfont-Regular.otf').read_bytes()
    if hashlib.sha256(converted).hexdigest()!=metadata['otf_sha256']:
        raise ValueError('The Bfont OpenType compatibility asset failed its checksum')
    return converted
