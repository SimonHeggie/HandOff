"""Inkscape/SVG clones for intentional, compatible GP datablock sharing.

Capture identity before detaching Blender data. Validate the generated SVG
geometry and paint before substituting a reference; never merge lookalikes.
"""
import hashlib
import json
import math
import re
from xml.etree import ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'
XLINK = '{http://www.w3.org/1999/xlink}'
KEY = 'data-layered-instance-key'
CONFIG = 'data-layered-instance-config'
BASIS = 'data-layered-instance-basis'
SOURCE = 'data-layered-instance-source'
ET.register_namespace('xlink', XLINK[1:-1])
ET.register_namespace('', SVG[1:-1])
ET.register_namespace('inkscape', INK[1:-1])
NUMBER = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
TOKEN = re.compile(r'[MLCZ]|' + NUMBER)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _basis(points):
    if len(points) < 3:
        return None
    p = points[0]
    # Topological indices stay the same under scale/rotation/reflection;
    # choosing the furthest point could choose a different vertex per object.
    q, r = points[len(points)//3], points[2*len(points)//3]
    area = lambda a,b: (a[0]-p[0])*(b[1]-p[1]) - (a[1]-p[1])*(b[0]-p[0])
    if abs(area(q,r)) <= 1e-6:
        q = next((v for v in points[1:] if math.hypot(v[0]-p[0],v[1]-p[1]) > 1e-5), p)
        r = next((v for v in points[1:] if abs(area(q,v)) > 1e-6), p)
    matrix = [q[0]-p[0], q[1]-p[1], r[0]-p[0], r[1]-p[1], p[0], p[1]]
    return matrix if abs(matrix[0]*matrix[3]-matrix[1]*matrix[2]) > 1e-6 else None


def instance_metadata(artwork, obj, source_file, frame):
    """Only called while original Blender object/datablock identities exist."""
    obj = getattr(obj, 'original', obj)
    data = obj.data
    if getattr(data, 'users', 1) < 2 or 'layers' not in artwork:
        return None
    if artwork.get('expanded_stroke') or any(stroke.get('pressure') for layer in artwork['layers'] for stroke in layer['strokes']):
        return None  # Preserve live pressure effects as independent vectors.
    points = [point['co'] for layer in artwork['layers'] for stroke in layer['strokes'] for point in stroke['points']]
    matrix = _basis(points)
    if matrix is None:
        return None
    materials = []
    for slot in getattr(obj, 'material_slots', ()):
        material = slot.material
        library = getattr(material, 'library', None)
        materials.append([getattr(material, 'name_full', ''), getattr(library, 'filepath', ''), getattr(slot, 'link', '')])
    # Object/collection-dependent modifiers cannot be represented by a shared
    # evaluated source merely because their current output happens to match.
    for modifier in getattr(obj, 'modifiers', ()):
        if not modifier.show_render:
            continue
        for prop in modifier.bl_rna.properties:
            if prop.identifier == 'rna_type':
                continue
            if prop.type == 'POINTER' and getattr(modifier, prop.identifier, None) is not None:
                return None
            if prop.type == 'COLLECTION' and len(getattr(modifier, prop.identifier, ())):
                return None
    modifiers = [{key: value for key,value in row.items() if key != 'name'} for row in artwork.get('modifiers', [])]
    library = getattr(data, 'library', None)
    identity=([getattr(library,'filepath',''),data.name_full,data.get('_asset_parts_id')]
              if library else data.get('_asset_parts_id') or [str(source_file),data.name_full])
    return dict(key=_digest([identity,int(frame)]),
                config=_digest([materials, modifiers]), basis=matrix)


def multiply(a, b):
    return [a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5]]


def inverse(a):
    det = a[0]*a[3]-a[1]*a[2]
    if abs(det) < 1e-12:
        raise ValueError('Singular instance transform')
    return [a[3]/det, -a[1]/det, -a[2]/det, a[0]/det,
            (a[2]*a[5]-a[3]*a[4])/det, (a[1]*a[4]-a[0]*a[5])/det]


def _close(a, b, tolerance=.002):
    return len(a) == len(b) and all(math.isfinite(x) and math.isfinite(y) and abs(x-y) <= tolerance for x,y in zip(a,b))


def _path(value):
    if TOKEN.sub('', value).replace(',', '').strip():
        return None
    tokens = TOKEN.findall(value)
    return ([v if v in ('M','L','C','Z') else None for v in tokens],
            [float(v) for v in tokens if v not in ('M','L','C','Z')])


def _points(values, transform):
    if len(values) % 2:
        return []
    a,b,c,d,e,f = transform
    result = []
    for x,y in zip(values[::2], values[1::2]):
        result.extend((a*x+c*y+e, b*x+d*y+f))
    return result


def compatible(master, candidate, transform):
    """Check actual serialized paths, gradients and widths in camera pixels."""
    left = [e for e in master.iter() if e.tag not in (SVG+'title',SVG+'desc',SVG+'metadata')]
    right = [e for e in candidate.iter() if e.tag not in (SVG+'title',SVG+'desc',SVG+'metadata')]
    if len(left) != len(right):
        return False
    ids_a = {node.get('id'): str(i) for i,node in enumerate(left) if node.get('id')}
    ids_b = {node.get('id'): str(i) for i,node in enumerate(right) if node.get('id')}
    ignored = {'id', KEY, CONFIG, BASIS, SOURCE, INK+'label', INK+'highlight-color',
               'data-handoff-object', 'data-handoff-bounds', 'data-handoff-source-geometry', 'data-handoff-modifiers'}
    a,b,c,d,_,_ = transform
    scale = math.hypot(a,b)
    similarity = (abs(a*c+b*d) < 1e-5 * max(1,scale**2) and
                  abs(a*a+b*b-c*c-d*d) < 1e-5 * max(1,scale**2))
    def references(value, ids):
        def replace(match):
            if match[1] not in ids:
                raise ValueError('External paint reference')
            return 'url(#' + ids[match[1]] + ')'
        return re.sub(r'url\(#([^)]*)\)', replace, value)
    try:
        for x,y in zip(left,right):
            if x.tag != y.tag or (x.text or '').strip() != (y.text or '').strip():
                return False
            ax = {k:v for k,v in x.attrib.items() if k not in ignored and not k.startswith('data-asset-')}
            ay = {k:v for k,v in y.attrib.items() if k not in ignored and not k.startswith('data-asset-')}
            if ax.keys() != ay.keys():
                return False
            for key,value in ax.items():
                target = ay[key]
                if key == 'd':
                    p,q = _path(value),_path(target)
                    if p is None or q is None or p[0] != q[0] or not _close(_points(p[1],transform),q[1]):
                        return False
                elif key == 'gradientTransform':
                    if not value.startswith('matrix(') or not target.startswith('matrix('):
                        return False
                    m = [float(v) for v in re.findall(NUMBER,value)]
                    n = [float(v) for v in re.findall(NUMBER,target)]
                    if len(m) != 6 or len(n) != 6 or not _close(multiply(transform,m),n):
                        return False
                elif key == 'stroke-width':
                    if not similarity or not _close([float(value)*scale],[float(target)]):
                        return False
                elif key == 'transform':
                    return False  # GP paths are already projected; keep unknown transforms independent.
                elif references(value,ids_a) != references(target,ids_b):
                    return False
    except (ValueError, TypeError, OverflowError):
        return False
    return True


def link_instances(root, logger=None):
    """Replace compatible linked objects in place, retaining paint order/labels.

    The first visible occurrence remains the editable original. Later objects
    become real SVG/Inkscape clones, with both SVG2 and SVG1.1 references.
    """
    masters = {}
    changed = 0
    parents = {child: parent for parent in root.iter() for child in parent}
    for element in list(root.iter()):
        family = element.get(KEY)
        if not family or element.tag != SVG+'g':
            continue
        try:
            basis = json.loads(element.get(BASIS, 'null'))
            if not isinstance(basis,list) or len(basis) != 6:
                continue
            key = (family, element.get(CONFIG))
            options = masters.setdefault(key, [])
            match = None
            for master, original_basis in options:
                transform = multiply(basis,inverse(original_basis))
                if compatible(master,element,transform):
                    match = master,transform
                    break
            if match is None:
                options.append((element,basis))
                continue
            master,transform = match
            attrs = dict(element.attrib)
            attrs.pop('opacity',None);attrs.pop('style',None)
            attrs['href'] = '#'+master.get('id')
            attrs[XLINK+'href'] = attrs['href']
            attrs[SOURCE] = master.get('id')
            attrs['transform'] = 'matrix(' + ' '.join(format(v,'.12g') for v in transform) + ')'
            clone = ET.Element(SVG+'use',attrs)
            parent = parents[element];index = list(parent).index(element)
            parent.remove(element);parent.insert(index,clone);changed += 1
        except (ValueError, TypeError, ArithmeticError):
            continue
    count = sum(node.tag == SVG+'use' and node.get(KEY) is not None for node in root.iter())
    if count:
        root.set('data-layered-clones',str(count))
    if logger and changed:
        logger('SVG linked GP data:', changed, 'clone(s); edit the original to update shared artwork')
    return changed
