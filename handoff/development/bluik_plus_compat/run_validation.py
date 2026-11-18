"""Reproduce native HandOff -> isolated Bluik Plus -> render/reopen validation.

Neither installed Bluik sources nor Blender preferences are changed. Generated
projects and caches go in the requested empty results directory outside source.
"""
import argparse,json,os,signal,subprocess,tempfile,time
from pathlib import Path
from stage import stage


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--blender',required=True);parser.add_argument('--bluik-source',required=True)
 parser.add_argument('--results',default=None);args=parser.parse_args()
 output=Path(args.results).resolve() if args.results else Path(tempfile.mkdtemp(prefix='handoff-bluik-'))
 if output.exists() and any(output.iterdir()):raise ValueError('Choose an empty results directory')
 output.mkdir(parents=True,exist_ok=True);root=Path(__file__).resolve().parents[2]
 runtime=stage(args.bluik_source,output/'runtime/bluik_plus')
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',BLUIK_SOURCE=str(runtime))
 for key,name in (('BLENDER_USER_CONFIG','config'),('BLENDER_USER_SCRIPTS','scripts'),('BLENDER_USER_EXTENSIONS','extensions'),('LAYERED_EXPORT_CACHE','pillow')):env[key]=str(output/'.runtime'/name)
 results=[]
 def case(name,script,marker,extras=None,blend=None):
  local=dict(env,HANDOFF_TEST_OUTPUT=str(output/name),LAYERED_TEST_OUTPUT=str(output/name),BLUIK_TEST_OUTPUT=str(output/name),LAYERED_EXPORT_JOB_ROOT=str(output/(name+'-jobs')))
  local.update(extras or {});log=output/(name+'.log')
  cmd=[args.blender,'--disable-autoexec','-b']
  cmd += [str(blend)] if blend else ['--factory-startup']
  cmd += ['-noaudio','--python-exit-code','1','--python',str(root/script)]
  started=time.monotonic();passed_at=None;bounded=False
  with log.open('w') as stream:
   process=subprocess.Popen(cmd,cwd=root,env=local,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
   while process.poll() is None:
    now=time.monotonic();passed=marker in log.read_text(errors='replace')
    if passed and passed_at is None:passed_at=now
    if now-started>100 or (passed_at is not None and now-passed_at>3):
     bounded=True;os.killpg(process.pid,signal.SIGTERM)
     try:process.wait(timeout=2)
     except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
     break
    time.sleep(.2)
  result=dict(case=name,functional_pass=marker in log.read_text(errors='replace'),clean_shutdown=process.returncode==0 and not bounded,returncode=process.returncode,log=str(log))
  results.append(result);(output/'process-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(result),flush=True)
  if not result['functional_pass']:raise RuntimeError('Native test failed: '+str(log))
 shared=output/'shared-export/exports/Shared.oca/Shared.oca'
 authored=output/'authored-export/exports/Authored.oca/Authored.oca'
 case('shared-export','development/test_oca_shared_layers_blender.py','OCA_SHARED_LAYERS_NATIVE_PASS')
 case('shared-import','development/bluik_plus_compat/test_import_blender.py','BLUIK_IMPORT_NATIVE_PASS',dict(BLUIK_TEST_DOCUMENT=str(shared),BLUIK_ASSERT_CLONES='1',BLUIK_TEST_EDIT='1'))
 case('authored-export','development/test_oca_authoring_blender.py','OCA_AUTHORING_NATIVE_PASS',dict(HANDOFF_NESTED_SOURCE=str(shared)))
 case('authored-import','development/bluik_plus_compat/test_import_blender.py','BLUIK_IMPORT_NATIVE_PASS',dict(BLUIK_TEST_DOCUMENT=str(authored),BLUIK_ASSERT_CLONES='1',BLUIK_TEST_TIME='1'))
 case('reopen','development/bluik_plus_compat/test_reopen_blender.py','BLUIK_REOPEN_PASS',blend=output/'authored-import/imported.blend')
 print('Results:',output,flush=True)
 return int(any(not r['clean_shutdown'] for r in results))

if __name__=='__main__':raise SystemExit(main())
