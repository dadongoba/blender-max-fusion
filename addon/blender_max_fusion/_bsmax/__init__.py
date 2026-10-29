# SPDX-License-Identifier: GPL-3.0-or-later
"""Embedded BsMax tool backend. Host owns preferences, UI and keymap lifecycle."""
from types import SimpleNamespace
_ready = False
def preferences():
    return SimpleNamespace(side_panel='NONE', floatmenus='BLENDER', viowport='3DSMAX',
        keymaps='NONE', navigation='NONE', navigation_3d='NONE', navigation_2d='NONE',
        affect_theme=False, experimental=False, nevil_stuff=False,
        geonode_pirimitve=False, blender_transform_type=False, view_undo=False,
        menu_scale=1.0, menu_auto_scale=False)
def register():
    global _ready
    if _ready: return
    from .bsmax import register_bsmax
    from .primitive import register_primitives
    from .tools import register_tools
    p = preferences()
    register_bsmax()
    register_primitives(p)
    register_tools(p)
    _ready = True
def unregister():
    global _ready
    if not _ready: return
    from .bsmax import unregister_bsmax
    from .primitive import unregister_primitives
    from .tools import unregister_tools
    unregister_tools()
    unregister_primitives()
    unregister_bsmax()
    _ready = False
