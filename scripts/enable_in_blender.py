"""Run with Blender --python; no desktop automation and no scene modification."""
import argparse
import json
from pathlib import Path
import sys
import traceback

import bpy


def activate():
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', choices=['keep', 'zh', 'en'], default='keep')
    parser.add_argument('--result')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    result = Path(args.result) if args.result else Path(bpy.utils.resource_path('USER')) / 'fusion-install-result.json'
    try:
        if bpy.app.background:
            raise RuntimeError('Activation needs an interactive GPU session; omit --background.')
        import addon_utils
        module = 'bl_ext.user_default.blender_max_fusion'
        repo = next((r for r in bpy.context.preferences.extensions.repos if r.module == 'user_default'), None)
        expected = Path(bpy.utils.resource_path('USER')) / 'extensions' / 'user_default'
        if repo is None:
            repo = bpy.context.preferences.extensions.repos.new(name='User Default', module='user_default',
                                                               custom_directory=str(expected))
        if Path(repo.directory).resolve() != expected.resolve():
            raise RuntimeError(f'Custom user_default repository: {repo.directory}. Install there explicitly before activation.')
        errors = []
        addon_utils.enable(module, default_set=True, persistent=True, handle_error=errors.append)
        if errors or not addon_utils.check(module)[1]:
            raise RuntimeError(f'Extension activation failed: {errors!r}')
        if args.language != 'keep':
            view = bpy.context.preferences.view
            view.language = 'zh_HANS' if args.language == 'zh' else 'en_US'
            view.use_translate_interface = args.language == 'zh'
            view.use_translate_tooltips = args.language == 'zh'
        bpy.ops.wm.save_userpref()
        report = {'ok': True, 'module': module, 'version': bpy.app.version_string,
                  'language': bpy.context.preferences.view.language}
    except Exception:
        report = {'ok': False, 'error': traceback.format_exc()}
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FUSION_ACTIVATION:', json.dumps(report, ensure_ascii=False))
    return None


bpy.app.timers.register(activate, first_interval=0.5)
