"""Build an offline Blender extension ZIP from this checkout."""
from pathlib import Path
import tomllib
import zipfile

root = Path(__file__).resolve().parents[1]
source = root / 'addon' / 'blender_max_fusion'
manifest = tomllib.loads((source / 'blender_manifest.toml').read_text(encoding='utf-8'))
output = root / 'dist' / f"blender_max_fusion-{manifest['version']}.zip"
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.blend1', '.blend2'}:
            archive.write(path, path.relative_to(source).as_posix())
print(output)
