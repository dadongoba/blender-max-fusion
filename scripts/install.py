#!/usr/bin/env python3
"""Install the checkout into Blender's user extension directory (Python 3.11+)."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'addon' / 'blender_max_fusion'


def find_blender(explicit=None):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f'Blender executable not found: {path}')
        return path
    candidates = []
    if shutil.which('blender'):
        candidates.append(Path(shutil.which('blender')))
    if sys.platform == 'win32':
        candidates += list(Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')).glob('Blender Foundation/Blender */blender.exe'))
    elif sys.platform == 'darwin':
        candidates += list(Path('/Applications').glob('Blender*.app/Contents/MacOS/Blender'))
    if len(set(candidates)) != 1:
        raise RuntimeError('Specify --blender /path/to/blender; zero or multiple installations found.')
    return candidates[0].resolve()


def query_blender(blender):
    expr = "import bpy,json; print('FUSION_INFO='+json.dumps({'version':list(bpy.app.version),'user':bpy.utils.resource_path('USER')}))"
    result = subprocess.run([str(blender), '--background', '--factory-startup', '--python-expr', expr],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
    for line in result.stdout.splitlines():
        if line.startswith('FUSION_INFO=') and result.returncode == 0:
            return json.loads(line.split('=', 1)[1])
    raise RuntimeError('Could not query Blender user directory: ' + result.stdout[-1000:] + result.stderr[-1000:])


def install_files(source, user_root):
    """Stage then rename; keep any previous version outside extension discovery."""
    source, user_root = Path(source).resolve(), Path(user_root).resolve()
    destination = user_root / 'extensions' / 'user_default' / 'blender_max_fusion'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source == destination:
        raise RuntimeError('Source and destination must be different.')
    stage = Path(tempfile.mkdtemp(prefix='.fusion-stage-', dir=destination.parent))
    backup = None
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', '*.blend1', '*.blend2'))
        if destination.exists():
            backup_root = user_root / 'fusion-backups'
            backup_root.mkdir(exist_ok=True)
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = backup_root / ('blender_max_fusion-' + stamp)
            destination.rename(backup)
        try:
            stage.rename(destination)
        except Exception:
            if backup is not None:
                backup.rename(destination)
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination, backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', help='Explicit Blender executable path')
    parser.add_argument('--language', choices=['keep', 'zh', 'en'], default='keep')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-launch', action='store_true', help='Copy files only; activate later after closing Blender')
    args = parser.parse_args()
    manifest = tomllib.loads((SOURCE / 'blender_manifest.toml').read_text(encoding='utf-8'))
    blender = find_blender(args.blender)
    info = query_blender(blender)
    if tuple(info['version'][:2]) != (5, 2):
        raise RuntimeError('This preview supports Blender 5.2.x only.')
    user_root = Path(info['user'])
    print(json.dumps({'blender': str(blender), 'user': str(user_root), 'version': manifest['version'],
                      'language': args.language, 'dry_run': args.dry_run}, ensure_ascii=False))
    if args.dry_run:
        return
    destination, backup = install_files(SOURCE, user_root)
    print('INSTALLED:', destination)
    if backup:
        print('BACKUP:', backup)
    if args.no_launch:
        print('Activation pending. Close Blender, then run the activation command in README.md.')
        return
    # CLI launch only: GPU-backed tools cannot be activated in --background mode.
    log = user_root / 'fusion-install-result.json'
    if log.exists():
        log.unlink()
    subprocess.Popen([str(blender), '--python', str(ROOT / 'scripts' / 'enable_in_blender.py'),
                      '--', '--language', args.language, '--result', str(log)])
    print('BLENDER_STARTED. Check activation result:', log)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('INSTALL_FAILED:', exc, file=sys.stderr)
        sys.exit(1)
