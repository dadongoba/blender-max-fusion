# Blender Max Fusion

[简体中文](README.md) · GPL-3.0-or-later · Blender **5.2.x** · Integration preview

Switch between Blender, Max-style and Maya-style workflows in one Blender instance. Source, bundled dependencies, Simplified Chinese translations and an AI installation skill are included. Do not install separate copies of the bundled workflow plugins.

## Install with an AI assistant

```bash
git clone https://github.com/dadongoba/blender-max-fusion.git
cd blender-max-fusion
```

Open the checkout in an AI coding assistant and ask:

> Read AGENTS.md and skills/install-blender-max-fusion/SKILL.md, install this plugin into my Blender, and verify activation. Check the Blender version and running processes first. Preserve my interface language.

The skill can also be installed as a personal skill. A standalone skill folder still needs a full checkout containing the addon and scripts.

## CLI install

Requires Python 3.11+ (Blender's bundled Python works) and Blender 5.2.x. Save and close Blender first.

```bash
python scripts/install.py --blender "/path/to/blender" --dry-run
python scripts/install.py --blender "/path/to/blender"
```

Add `--language zh` for Simplified Chinese or `--language en` for English. These options change Blender's global UI language; the default preserves it. The installer backs up the previous version and starts Blender using its CLI to activate the extension. Read the reported `fusion-install-result.json`; only `"ok": true` confirms activation. GPU-backed tools require interactive activation, so do not add `--background`.

If Blender must stay open, use `--no-launch` to stage the files. After closing Blender, activate with:

```bash
"/path/to/blender" --python "/path/to/checkout/scripts/enable_in_blender.py" -- --language keep
```

No mouse, keyboard or desktop UI automation is used. Activation saves preferences and disables conflicting legacy workflow plugin IDs; it does not delete their files. The plugin starts in Blender mode by default.

## Manual ZIP / updates / rollback

Run `python scripts/build.py`, then use Blender Preferences → Get Extensions → Install from Disk to install the ZIP under `dist/`. Close Blender before `git pull --ff-only` and rerun the installer to update. Prior versions are preserved under the reported `fusion-backups` directory. To roll back, close Blender, move the current addon directory aside, and copy the desired backup back to its original extension location. Startup files and user projects are not replaced.

## Scope and verification

Windows + Blender 5.2 is the primary environment. Linux and macOS path discovery is implemented but interactive acceptance is pending. Chinese translation covers the included catalog plus Blender's native translations; unmatched strings remain English. Max mode applies empty-scene, 0–100 frame and 30fps defaults to a pristine factory scene.

Run `python -m unittest discover -s tests` and `python scripts/build.py`. Background logic checks do not prove visual smoothness. In interactive Blender, verify Modeling → Max → Maya → Blender and Modeling → Maya → Max → Blender both restore Modeling.

See [third-party credits](addon/blender_max_fusion/THIRD_PARTY.md) and [licenses](addon/blender_max_fusion/licenses). This is an independent integration, not an Autodesk product.
