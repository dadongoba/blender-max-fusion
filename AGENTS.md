# Repository workflow

When asked to install or update this Blender plugin, read and follow
[`skills/install-blender-max-fusion/SKILL.md`](skills/install-blender-max-fusion/SKILL.md).
That skill and its scripts are the installation entry point. No desktop automation is required.

The runtime extension is in `addon/blender_max_fusion/`. Keep upstream copyright and
license notices intact. Do not commit user preferences, startup files, credentials,
cache directories or personal project files.

Validate changes with `python -m unittest discover -s tests` and
`python scripts/build.py`. GPU-backed interactive activation cannot be verified in
Blender background mode; describe verification limits accurately.
