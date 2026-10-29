---
name: install-blender-max-fusion
description: Install, update, or diagnose this repository's Blender Max Fusion extension with Blender, Max and Maya modes and Simplified Chinese translation. Use when asked to install this plugin from a Git checkout; supports Blender 5.2.x.
---

# Install Blender Max Fusion

The extension source, translations and dependencies are bundled in this repository. Do not install separate BsMax, Blender Max or Maya Workflow Kit copies; their classes may conflict. Installation needs no desktop automation, admin privileges or pip packages.

1. Resolve the repository root relative to this file (`../..`). If this skill was installed separately, find an existing checkout or clone `https://github.com/dadongoba/blender-max-fusion.git` into a user-writable directory. Use Python 3.11+ or Blender's bundled Python.
2. Find the intended Blender executable. Run `python scripts/install.py --blender "<executable>" --dry-run` from the repository. The installer queries Blender itself for its user directory and enforces Blender 5.2.x. Never guess a versioned AppData path. If multiple Blender installations exist, use the user's selected one.
3. Check whether Blender is already running with process tools. Never kill it or replace an unsaved session. If running, install with `--no-launch` and report that activation remains pending until the user closes Blender. Otherwise run `python scripts/install.py --blender "<executable>"`. Add `--language zh` when Chinese is requested; the default preserves the existing interface language. `--language en` requests English. Explain that choosing a language changes Blender's global UI preference.
4. The normal installer starts Blender through its CLI and enables the extension in an interactive GPU session. Do not use `--background` for activation: the embedded Max tools create GPU shaders. Poll the reported `fusion-install-result.json` for up to 90 seconds and require `"ok": true` before reporting successful activation. A launched process or copied files alone are not proof. If it fails, read the reported traceback, fix a concrete cause, and retry at most once; otherwise report the exact blocker and backup location.
5. If files were copied with `--no-launch`, after Blender is closed activate using `"<blender>" --python "<repo>/scripts/enable_in_blender.py" -- --language keep`, then inspect the same result file. Existing plugin files are backed up under Blender's `fusion-backups`; startup files and projects are never overwritten. Activation saves user preferences and may disable conflicting legacy plugin IDs through the extension's migration code.

Report the installed path, backup path if any, activation status, and language. Keep visual acceptance separate: CLI success does not establish flicker-free mode switching. Useful checks after activation are Blender Modeling → Max → Maya → Blender and Blender Modeling → Maya → Max → Blender; each should return to Modeling.

For manual installation or rollback, read the repository's `README.md`. An offline extension ZIP can be built with `python scripts/build.py`.
