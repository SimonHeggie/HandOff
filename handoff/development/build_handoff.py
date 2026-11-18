"""Build the local handoff package; no GitHub, installation or version changes."""
import hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from branding import NAME,VERSION


def main():
    destination=ROOT/'dist';destination.mkdir(exist_ok=True)
    archive=destination/(NAME+'-'+VERSION+'-local.zip')
    allowed={'.py','.md','.html','.xml','.csv','.txt','.icc','.otf','.ttf','.pfb','.whl','.json','.wav'}
    folders={'assets','compatibility','development','manual','pillow','profiles','vendor'}
    excluded={'.backups','.build','dist','.git','.agents','.codex','.aws','__pycache__','validation'}
    files=[]
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        parts=path.relative_to(ROOT).parts
        if any(p in excluded or 'results' in p for p in parts[:-1]):continue
        if len(parts)>1 and parts[0] not in folders:continue
        if path.suffix not in allowed and path.name not in ('LICENSE','.gitignore'):continue
        files.append(path)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in sorted(files):output.write(path,Path('handoff')/path.relative_to(ROOT))
    assert archive.stat().st_size < 50*1024*1024, 'Package exceeds 50 MiB'
    with zipfile.ZipFile(archive) as content:
        assert content.testzip() is None
        for name in ('__init__.py','branding.py','package_compat.py','oca_vectors.py','psd_worker.py','builtin_font.py','compatibility/tags.xml','manual/MANUAL.html'):
            assert 'handoff/'+name in content.namelist(),name
        assert len([n for n in content.namelist() if n.endswith('.whl')])==6
    report=dict(path=str(archive),bytes=archive.stat().st_size,mib=archive.stat().st_size/1024**2,
                sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files),package='handoff')
    (destination/'package-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
