"""Build an isolated Bluik Plus compatibility test copy; never edit its source.

python stage.py /path/to/bluik_plus /tmp/bluik-oca13/runtime/bluik_plus
New importer implementation lives alongside this script for durable review.
"""
import difflib,hashlib,json,shutil,sys
from pathlib import Path


def stage(source,target):
 source=Path(source).resolve();target=Path(target).resolve()
 if target.exists():raise FileExistsError('Refusing to overwrite '+str(target))
 if target.is_relative_to(source):raise ValueError('Test copy must be outside source')
 shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 changes={}
 def edit(name,transform):
  original=(source/name).read_text();updated=transform(original)
  if updated==original:return
  (target/name).write_text(updated)
  changes[name]=dict(sha256=hashlib.sha256((source/name).read_bytes()).hexdigest(),patch=''.join(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),fromfile='a/'+name,tofile='b/'+name)))
 # Blender removed bgl. Keep the old GPU path for old Blender, use native float
 # image pixels for this helper when bgl is unavailable.
 if '\nimport bgl\n' in (source/'dublf/image.py').read_text():
  edit('dublf/image.py',lambda s:s.replace('import bgl','try:\n    import bgl\nexcept ImportError:\n    bgl = None').replace('def gl_copy(image):','def gl_copy(image):\n    if bgl is None:\n        width,height=image.size\n        values=np.empty(width*height*4,np.float32)\n        image.pixels.foreach_get(values)\n        return values.reshape(height,width,4)'))
 # Route only standard 1.3 documents through the additive implementation.
 # Existing legacy and pivot/transform prototype paths remain intact.
 edit('oca.py',lambda s:(s if 'from . import oca13_import' in s else s.replace('    def import_oca(self, context):\n','    def import_oca(self, context):\n        from . import oca13_import\n        if oca13_import.try_import(self,context):\n            return\n',1)).replace('            print(f"ERROR during OCA import: {exc}")','            context.preferences.edit.use_enter_edit_mode = editmode\n            self.report({"ERROR"}, str(exc))\n            return {"CANCELLED"}'))
 if 'from bluik import dublf' in (source/'preferences.py').read_text():
  edit('preferences.py',lambda s:s.replace('from bluik import dublf','from . import dublf'))
 for name in ('oca13_import.py','oca_shaders.py'):
  shutil.copy2(Path(__file__).with_name(name),target/name)
 edit('eevee_optimise.py',lambda s:s.replace("    scene.render.engine = 'BLENDER_EEVEE_NEXT'  # Ensure engine is correct","    try:\n        scene.render.engine = 'BLENDER_EEVEE'\n    except TypeError:\n        scene.render.engine = 'BLENDER_EEVEE_NEXT'"))
 digest=hashlib.sha256((source/'oca.py').read_bytes()).hexdigest()[:12]
 evidence=Path(__file__).with_name('source-patches-'+digest+'.json')
 evidence.write_text(json.dumps(dict(source=str(source),target=str(target),changes=changes),indent=2))
 return target

if __name__=='__main__':print(stage(*sys.argv[1:3]))
