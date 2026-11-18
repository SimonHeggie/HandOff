"""Reproduce native OCA checks without changing production Blender preferences.

Usage: python3 development/run_oca_controls.py --blender /path/to/blender
Functional assertions and natural process shutdown are reported separately.
The runner returns nonzero if either fails; it never masks a shutdown failure.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--results', default=str(Path(tempfile.gettempdir())/'handoff-oca-validation'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.results).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for key, folder in (('BLENDER_USER_CONFIG', 'config'), ('BLENDER_USER_SCRIPTS', 'scripts'),
                        ('BLENDER_USER_EXTENSIONS', 'extensions'), ('LAYERED_EXPORT_CACHE', 'pillow')):
        env[key] = str(output / '.runtime' / folder)
    cases = [
        ('startup-control', ['--python-expr', "print('BASELINE_EXIT_CONTROL', flush=True)"], 'BASELINE_EXIT_CONTROL'),
        ('controls', ['--python', str(root/'development/test_oca_controls_blender.py')], 'OCA_SEVEN_CONTROLS_NATIVE_PASS'),
        ('precision', ['--python', str(root/'development/test_oca_precision_blender.py')], 'OCA_NATIVE_PRECISION_PASS'),
        ('sequence', ['--python', str(root/'development/test_oca_animation_blender.py')], 'OCA_ANIMATION_NATIVE_PASS'),
    ]
    results = []
    for name, command, marker in cases:
        log = output / (name+'.log')
        env['LAYERED_EXPORT_JOB_ROOT'] = str(output/(name+'-jobs'))
        env['LAYERED_TEST_OUTPUT'] = str(output/name)
        arguments = [str(Path(args.blender).resolve()), '--factory-startup', '--disable-autoexec',
                     '-b', '-noaudio', '--python-exit-code', '1', *command]
        started = time.monotonic(); finished_at = None; timed_out = False
        with log.open('w') as stream:
            process = subprocess.Popen(arguments, cwd=root, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            while process.poll() is None:
                now = time.monotonic()
                if marker in log.read_text(errors='replace') and finished_at is None:
                    finished_at = now
                if now-started > 60 or (finished_at is not None and now-finished_at > 5):
                    timed_out = True
                    os.killpg(process.pid, signal.SIGTERM)
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait()
                    break
                time.sleep(.2)
        entry = dict(case=name, functional_assertions_passed=marker in log.read_text(errors='replace'),
                     clean_shutdown=process.returncode == 0 and not timed_out,
                     returncode=process.returncode, timed_out=timed_out, log=str(log), command=arguments)
        results.append(entry)
        print(json.dumps(entry), flush=True)
        (output/'process-results.json').write_text(json.dumps(results, indent=2))
    return int(any(not r['functional_assertions_passed'] or not r['clean_shutdown'] for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
