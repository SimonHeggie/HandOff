"""Font identity and explicit font-file delivery; no system installation."""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import tempfile

FONT_EXTENSIONS = {'.ttf', '.otf', '.ttc', '.woff', '.woff2', '.pfb'}
FONTS_API_VERSION = 1


def system_font_directory(system=None):
    system = system or platform.system()
    if system == 'Windows':
        return str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts')
    return '/System/Library/Fonts' if system == 'Darwin' else '/usr/share/fonts'


def user_font_directory(system=None):
    """Standard per-user font destination; needs no administrator privileges."""
    system=system or platform.system()
    if system=='Windows':
        return str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))/'Microsoft'/'Windows'/'Fonts')
    if system=='Darwin':return str(Path.home()/'Library'/'Fonts')
    return str(Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local'/'share')))/'fonts')


def _guessed_family(name):
    name = re.sub(r'(?i)(?:[-_ ](?:bolditalic|boldoblique|semibold|regular|medium|italic|oblique|bold))+$', '', name)
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name.replace('_',' ').replace('-',' ')).strip() or 'sans-serif'


@lru_cache(maxsize=1024)
def _font_names(path, size, modified):
    """Read OpenType name records without a font-processing dependency."""
    try:
        with Path(path).open('rb') as f:
            header = f.read(12)
            if header[:2]==b'\x80\x01':
                try:
                    from .builtin_font import pfb_names
                except ImportError:
                    from builtin_font import pfb_names
                length=struct.unpack_from('<I',header,2)[0]
                if length>size-6 or length>1_000_000:raise ValueError('Invalid PFB header')
                f.seek(6)
                return pfb_names(f.read(length))
            origin = 0
            if header[:4] == b'ttcf':
                origin = struct.unpack('>I', f.read(4))[0]
                f.seek(origin); header = f.read(12)
            if header[:4] not in (b'\0\1\0\0', b'OTTO', b'true'):
                raise ValueError('Not an SFNT font')
            count = struct.unpack_from('>H', header, 4)[0]
            if count > 256:
                raise ValueError('Invalid font table count')
            table = None
            for _ in range(count):
                tag, _, offset, length = struct.unpack('>4sIII', f.read(16))
                if tag == b'name':
                    table = offset, length
            if table is None or table[1] > 2_000_000 or sum(table) > size:
                raise ValueError('Font name table unavailable')
            f.seek(table[0]); data = f.read(table[1])
        _, count, start = struct.unpack_from('>HHH', data)
        names = {}
        for i in range(min(count, 4096)):
            plat, encoding, language, name_id, length, offset = struct.unpack_from('>HHHHHH', data, 6 + 12*i)
            if name_id not in (1, 2, 4, 6, 13, 14, 16, 17):
                continue
            raw = data[start+offset:start+offset+length]
            value = raw.decode('utf-16-be' if plat in (0,3) else 'mac_roman', errors='replace').strip('\0 ')
            priority = (language in (0, 0x409), plat in (0,3))
            if value and (name_id not in names or priority > names[name_id][0]):
                names[name_id] = priority, value
        return {'family': names.get(16, names.get(1, (None, '')))[1],
                'style': names.get(17, names.get(2, (None, 'Regular')))[1],
                'postscript': names.get(6,(None,''))[1],
                'license': names.get(13, (None, ''))[1],
                'license_url': names.get(14, (None, ''))[1]}
    except (OSError, ValueError, struct.error):
        return {'family': _guessed_family(Path(path).stem), 'style': 'Regular'}


def font_names(path):
    p = Path(path)
    s = p.stat()
    return dict(_font_names(str(p), s.st_size, s.st_mtime_ns))


def resolve_font(record, directory='', lookup=True):
    original = record.get('name', '')
    source = record.get('file', '')
    builtin = bool(record.get('builtin')) or source == '<builtin>' or (not source and original.lower().startswith('bfont'))
    path = Path(source) if source and not source.startswith('<') else None
    substituted = False
    if (path is None or not path.is_file()) and lookup and directory:
        folder = Path(directory)
        if not builtin and folder.is_dir():
            filename = Path(source).name if source else ''
            for candidate in folder.rglob('*'):
                if candidate.is_file() and candidate.suffix.lower() in FONT_EXTENSIONS:
                    if candidate.name == filename or font_names(candidate)['family'].casefold() == _guessed_family(original).casefold():
                        path = candidate; break
    exists = path is not None and path.is_file() and path.suffix.lower() in FONT_EXTENSIONS
    result = font_names(path) if exists else {'family':'Bfont' if builtin else _guessed_family(Path(source).stem or original), 'style':'Regular'}
    result.update(source_name=original, file=str(path.resolve()) if exists else '', substituted=substituted)
    if builtin:
        result['builtin']=True
        if not exists:
            binary=record.get('builtin_binary','')
            if not binary:
                try:
                    import bpy
                    binary=bpy.app.binary_path
                except ImportError:pass
            try:
                try:
                    from .builtin_font import embedded_bfont,pfb_names
                except ImportError:
                    from builtin_font import embedded_bfont,pfb_names
                data=embedded_bfont(binary)
                result.update(pfb_names(data[6:6+struct.unpack_from('<I',data,2)[0]]),builtin_binary=binary)
            except (OSError,ValueError) as exc:
                result['notice']='Exact Bfont unavailable: '+str(exc)
    elif not exists:
        result['notice'] = 'Font file unavailable: ' + (source or original)
    return result


def font_record(font, cache=None):
    if font is None:
        return {'name':'Bfont', 'file':'<builtin>'}
    name, path = font.name, str(getattr(font, 'filepath', ''))
    if path=='<builtin>':
        import bpy
        binary=bpy.app.binary_path
        if cache is not None:
            try:
                from .builtin_font import cache_bfont
            except ImportError:
                from builtin_font import cache_bfont
            try:path=str(cache_bfont(binary,cache))
            except (OSError,ValueError):pass  # Font delivery reports the unavailable original.
        return dict(name=name,file=path,builtin=True,builtin_binary=binary)
    packed = getattr(font, 'packed_file', None)
    if packed is not None and cache is not None:
        data = bytes(packed.data)
        extension = Path(path).suffix.lower()
        if extension not in FONT_EXTENSIONS:
            raise ValueError('Packed font has an unsupported format: ' + name)
        p = Path(cache)/'fonts'/ (hashlib.sha256(data).hexdigest()[:20] + extension)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data); path = str(p)
    elif path and not path.startswith('<'):
        try:
            import bpy
            path = bpy.path.abspath(path, library=font.library)
        except ImportError:
            pass
    return {'name':name, 'file':path}


def capture_font_job(sources, cache, dest, *, directory, lookup=True, node_name='', export_index=0):
    """Read fonts and text properties only; never pack/unpack or save a project."""
    seen, records, objects = set(), [], []
    for scene, view_layer in sources:
        try:
            from .svg_export import _camera_visible_objects
        except ImportError:
            from svg_export import _camera_visible_objects
        eligible = {o.name for o in _camera_visible_objects(view_layer)} if view_layer is not None else None
        for obj in view_layer.objects if view_layer is not None else scene.objects:
            if obj.type != 'FONT' or (eligible is not None and (obj.name not in eligible or obj.hide_render or not getattr(obj,'visible_camera',True))):
                continue
            identity = (scene.name, obj.name)
            if identity in seen:
                continue
            seen.add(identity)
            roles = {}
            used = {'regular'}
            for char in obj.data.body_format:
                if char.use_bold or char.use_italic:
                    used.add(('bold' if char.use_bold else '') + ('italic' if char.use_italic else ''))
            for role, attr in (('regular','font'),('bold','font_bold'),('italic','font_italic'),('bolditalic','font_bold_italic')):
                if role not in used:
                    continue
                f = getattr(obj.data, attr, None)
                if f is None:
                    continue
                record = font_record(f, cache)
                key = next((i for i,r in enumerate(records) if r == record), None)
                if key is None:
                    key = len(records); records.append(record)
                roles[role] = key
            objects.append(dict(scene=scene.name, name=obj.name, text=obj.data.body,
                                size=obj.data.size, align_x=obj.data.align_x, align_y=obj.data.align_y,
                                collections=[c.name for c in obj.users_collection], fonts=roles))
    return dict(format='FONTS', dest=str(dest), node_name=node_name, export_index=export_index,
                font_directory=str(directory), use_font_directory=bool(lookup), fonts=records,
                text_objects=objects, manifest=[], cache_kind='FONTS', depth=8, extension='', dir=str(cache))


def write_font_output(job, *, logger=print):
    """Atomic individual font copies and a JSON manifest; never delete a folder."""
    dest = Path(job['dest'])
    assets = dest.with_suffix('')
    assets.mkdir(parents=True, exist_ok=True)
    fonts, unresolved = [], []
    for record in job['fonts']:
        resolved = resolve_font(record, job.get('font_directory',''), job.get('use_font_directory',True))
        source = Path(resolved['file']) if resolved['file'] else None
        data=None
        if source is None and resolved.get('builtin_binary'):
            try:
                from .builtin_font import embedded_bfont
            except ImportError:
                from builtin_font import embedded_bfont
            data=embedded_bfont(resolved['builtin_binary'])
        if source is None and data is None:
            unresolved.append(resolved); fonts.append(resolved); continue
        data = source.read_bytes() if data is None else data
        digest = hashlib.sha256(data).hexdigest()
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', resolved['family'] + '-' + resolved['style'])
        target = assets/(name + '-' + digest[:10] + (source.suffix.lower() if source else '.pfb'))
        if target.exists() and target.read_bytes() != data:
            raise FileExistsError('Refusing to replace an unrelated font file: ' + str(target))
        # Never overwrite or remove a source font, even if a destination is
        # configured beside it. Existing unrelated files are never cleaned.
        if source is None or source.resolve() != target.resolve():
            fd, temp = tempfile.mkstemp(prefix='.compio-font-', dir=assets)
            try:
                with os.fdopen(fd,'wb') as f: f.write(data)
                os.replace(temp, target)
            finally:
                Path(temp).unlink(missing_ok=True)
        resolved.update(file=str(target.relative_to(dest.parent)), sha256=digest)
        try:
            from .builtin_font import compatible_bfont
        except ImportError:
            from builtin_font import compatible_bfont
        compatible=compatible_bfont(data)
        if compatible is not None:
            converted_hash=hashlib.sha256(compatible).hexdigest()
            converted=assets/(name+'-'+converted_hash[:10]+'.otf')
            if converted.exists() and converted.read_bytes()!=compatible:
                raise FileExistsError('Refusing to replace an unrelated font file: '+str(converted))
            fd,temp=tempfile.mkstemp(prefix='.compio-font-',dir=assets)
            try:
                with os.fdopen(fd,'wb') as f:f.write(compatible)
                os.replace(temp,converted)
            finally:Path(temp).unlink(missing_ok=True)
            resolved.update(compatible_file=str(converted.relative_to(dest.parent)),
                            compatible_sha256=converted_hash,compatible_format='OpenType/CFF')
        fonts.append(resolved)
        logger(f'{LOG_PREFIX} FONT:', resolved['family'], '|', resolved.get('notice','copied'), '|', target)
    result = dict(version=1, complete=not unresolved, fonts=fonts,
                  text_objects=job.get('text_objects', []), unresolved=unresolved)
    fd, temp = tempfile.mkstemp(prefix='.compio-font-manifest-', dir=dest.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False)
        os.replace(temp,dest)
    finally:
        Path(temp).unlink(missing_ok=True)
    if unresolved:
        raise ValueError('Font files unavailable; inspect ' + str(dest))
    return str(dest)
