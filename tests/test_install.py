import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fusion_installer', ROOT / 'scripts' / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_update_preserves_backup_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'module.py').write_text('version=1')
            (source / '__pycache__').mkdir()
            (source / '__pycache__' / 'module.pyc').write_bytes(b'cache')
            user = root / 'user'
            user.mkdir()
            startup = user / 'startup.blend'
            startup.write_bytes(b'user scene')
            destination, backup = installer.install_files(source, user)
            self.assertIsNone(backup)
            self.assertFalse((destination / '__pycache__').exists())
            (source / 'module.py').write_text('version=2')
            destination, backup = installer.install_files(source, user)
            self.assertEqual((destination / 'module.py').read_text(), 'version=2')
            self.assertEqual((backup / 'module.py').read_text(), 'version=1')
            self.assertEqual(startup.read_bytes(), b'user scene')

    def test_bundled_payload(self):
        source = ROOT / 'addon' / 'blender_max_fusion'
        manifest = tomllib.loads((source / 'blender_manifest.toml').read_text(encoding='utf-8'))
        self.assertEqual(manifest['id'], 'blender_max_fusion')
        catalog = json.loads((source / 'zh_CN.json').read_text(encoding='utf-8'))
        self.assertGreater(len(catalog), 400)
        self.assertTrue(all(isinstance(k, str) and isinstance(v, str) and v for k, v in catalog.items()))
        for name in ['workspace.blend', 'editor_workspace.blend', '_maya/app_template/Maya_Workflow_Kit/startup.blend', 'LICENSE']:
            self.assertTrue((source / name).is_file(), name)

    def test_python_sources_compile(self):
        for path in (ROOT / 'addon').rglob('*.py'):
            compile(path.read_bytes(), str(path), 'exec')


if __name__ == '__main__':
    unittest.main()
