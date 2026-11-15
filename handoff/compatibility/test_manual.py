"""Regression checks for the XML-derived, paginated user manual."""
import re
import unittest
from pathlib import Path
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
DOC=ROOT.parent/'manual'
EXPECTED={'MANUAL.html','groups.html','psd.html','vectors.html','tags.html',
          'tags-operations.html','tags-spine.html','generator.html',
          'exr-suffixes.html','openexr.html','sources.html'}

class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=set();self.hrefs=[]
    def handle_starttag(self, tag, attrs):
        data=dict(attrs)
        if data.get('id'):self.ids.add(data['id'])
        if tag=='a' and data.get('href'):self.hrefs.append(data['href'])

class ManualTests(unittest.TestCase):
    def test_topics_and_links(self):
        self.assertEqual(EXPECTED,{p.name for p in DOC.glob('*.html')})
        parsed={}
        for file in EXPECTED:
            data=(DOC/file).read_text(encoding='utf-8')
            self.assertNotIn('—',data,file)
            self.assertNotIn('For the first test, create',data,file)
            self.assertNotIn('Hatshepsut',data,file)
            parser=HTMLLinks();parser.feed(data);parsed[file]=parser
        for filename, parser in parsed.items():
            for ref in parser.hrefs:
                if ref.startswith(('http:','https:','mailto:')):continue
                page, _, anchor=ref.partition('#');page=page or filename
                self.assertIn(page,parsed,(filename,ref))
                if anchor:self.assertIn(anchor,parsed[page].ids,(filename,ref))

    def test_comparison_stays_xml_order(self):
        xml=ET.parse(ROOT/'tags.xml').getroot()
        ids=[b.get('id') for b in sorted(xml.findall('./behaviors/behavior'),key=lambda x:int(x.get('rank')))]
        html=(DOC/'tags.html').read_text(encoding='utf-8')
        self.assertIn('Spine PSD',html)
        self.assertIn('Photoshop Generator',html)
        self.assertIn('OCA / Krita',html)
        matrix=html.split('<div class="table-wrap tag-quick">',1)[1].split('</table>',1)[0]
        actual=re.findall(r'<a href="(?:tags-operations|generator|tags-spine|exr-suffixes)\.html#tag-([^"]+)">',matrix)
        self.assertEqual(ids,actual)
        self.assertEqual(len(actual),26)

    def test_blend_mappings_and_section(self):
        self.assertEqual(len(ET.parse(ROOT/'blend_modes.xml').getroot().findall('./modes/mode')),111)
        html=(DOC/'exr-suffixes.html').read_text()
        self.assertIn('Blend-mode compatibility',html)
        self.assertIn('Additional blend modes (91)',html)
        self.assertIn('dot-separated naming pattern',html)
        self.assertNotIn('No standard EXR tags',html)

if __name__=='__main__':unittest.main()
