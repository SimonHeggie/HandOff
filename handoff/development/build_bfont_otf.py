"""Developer-only Bfont conversion; FontTools is a build dependency, never an add-on runtime dependency.

Usage: python build_bfont_otf.py original.pfb Bfont-Regular.otf
Every original cubic outline and advance is verified after serialisation.
"""
from pathlib import Path
from fontTools.t1Lib import T1Font
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.agl import toUnicode
from fontTools.ttLib import TTFont
import math,json,hashlib
import sys
source=Path(sys.argv[1]);p=Path(sys.argv[2]).resolve().parent
p.mkdir(parents=True,exist_ok=True)
f=T1Font(str(source));g=f.getGlyphSet();order=['.notdef']+[name for name in g if name!='.notdef']
assert f.font['FontMatrix']==[.001,0,0,.001,0,0]
chars={};metrics={};boxes=[];cmap={}
for name in order:
 glyph=g[name];bounds=BoundsPen(g);glyph.draw(bounds);pen=T2CharStringPen(glyph.width,g,roundTolerance=0);glyph.draw(pen)
 chars[name]=pen.getCharString();metrics[name]=(round(glyph.width),math.floor(bounds.bounds[0]) if bounds.bounds else 0)
 assert glyph.width==round(glyph.width)
 if bounds.bounds:boxes.append(bounds.bounds)
 text=toUnicode(name)
 if len(text)==1:cmap[ord(text)]=name
bbox=[math.floor(min(b[0] for b in boxes)),math.floor(min(b[1] for b in boxes)),math.ceil(max(b[2] for b in boxes)),math.ceil(max(b[3] for b in boxes))]
fb=FontBuilder(1000,isTTF=False);fb.setupGlyphOrder(order);fb.setupCharacterMap(cmap)
fb.setupCFF('Bfont-Regular',dict(FullName='Bfont Regular',FamilyName='Bfont',Weight='Regular',FontBBox=bbox),chars,{})
fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=bbox[3],descent=bbox[1])
fb.setupNameTable(dict(familyName='Bfont',styleName='Regular',fullName='Bfont Regular',psName='Bfont-Regular',uniqueFontIdentifier='Bfont-original-a33954fdab',version='Version 001.001',description='Original Blender Bfont outlines and advances in OpenType/CFF format.'))
fb.setupOS2(sTypoAscender=bbox[3],sTypoDescender=bbox[1],usWinAscent=bbox[3],usWinDescent=-bbox[1],fsSelection=0x40,fsType=0)
fb.setupPost(underlinePosition=-100,underlineThickness=50)
fb.font['head'].created=fb.font['head'].modified=2082844800
out=Path(sys.argv[2]).resolve();fb.save(out)
otf=TTFont(out);output=otf.getGlyphSet()
for name in order:
 original=DecomposingRecordingPen(g);g[name].draw(original)
 converted=DecomposingRecordingPen(output);output[name].draw(converted)
 # CFF ends contours without repeating the starting point; normalise both
 # through the exact same drawing pen before comparing.
 assert original.value==converted.value,(name,original.value[:3],converted.value[:3])
 assert output[name].width==g[name].width
report=dict(source='https://github.com/blender/blender/blob/main/release/datafiles/bfont.pfb',conversion='Type 1 to OpenType/CFF; all glyph outlines and advance widths verified exactly',runtime_dependency='none',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),otf_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),glyphs=len(order),unicode_entries=len(cmap),bbox=bbox)
out.with_suffix('.json').write_text(json.dumps(report,indent=2));print(report)
