# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender Max: original, reversible studio workflow extension."""
import bpy
__version__ = '0.3.1'
from bpy.props import PointerProperty
from . import max_gizmo
from . import (preferences, params, operators, editors, ui, runtime, chrome, toolbar, interactions, commands, flyouts, quad,
               max_menus, material_ui, animation_ui, utility_editors, scene_ui, trackbar)

CLASSES = (preferences.CLASSES+ui.CLASSES+operators.CLASSES+editors.CLASSES+chrome.CLASSES+toolbar.CLASSES
           +interactions.CLASSES+commands.CLASSES+flyouts.CLASSES+quad.CLASSES+tuple(max_menus.CLASSES)
           +material_ui.CLASSES+animation_ui.CLASSES+utility_editors.CLASSES+scene_ui.CLASSES+trackbar.CLASSES)
from . import fusion_keys
CLASSES += max_gizmo.CLASSES + fusion_keys.CLASSES
_registered = []

# Blender Max was Blender Studio Max (extension id blender_studio_max) up to 0.5.1.
LEGACY_IDS = ('blender_studio_max', 'blender_max', 'BsMax_for_BlenderMax', 'BsMax', 'BsMax-master', 'allset')
MIGRATED_PREFERENCES = ('enabled_mode', 'studio_colors', 'splash_image', 'last_material_editor')


def _take_legacy():
    from .migration import disable_legacy
    return disable_legacy(__package__,LEGACY_IDS,MIGRATED_PREFERENCES)


def _give_legacy(values):
    prefs = runtime.preferences()
    if not values or prefs is None:
        return
    for name, value in values.items():
        try:
            setattr(prefs, name, value)
        except (AttributeError, TypeError, ValueError):
            pass
    print('Blender Max: preferences migrated from Blender Studio Max')


def register():
    try:
        from . import localization
        localization.register()
        legacy = _take_legacy()
        from . import _maya, _bsmax
        _maya.preferences.register()
        _maya.switch.register()
        _bsmax.register()
        params.register()
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            _registered.append(cls)
        bpy.types.WindowManager.bsm = PointerProperty(type=ui.BSM_State)
        material_ui.register_data()
        pass  # unified top bar owns all mode switches
        max_gizmo.register_tool()
        if legacy: legacy['enabled_mode']=False
        _give_legacy(legacy)  # before runtime.register(), which reads the startup mode
        runtime.register()
        from . import unified_controller
        unified_controller.register()
        startup=runtime.preferences().startup_mode
        if startup!='BLENDER': unified_controller.request(startup)
    except Exception:
        unregister()
        raise


def unregister():
    from . import unified_controller
    unified_controller.unregister()
    from .migration import unregister_tools
    unregister_tools(max_gizmo)
    runtime.unregister()
    material_ui.unregister_data()
    try:
        bpy.types.TOPBAR_HT_upper_bar.remove(ui.draw_switch)
    except (ValueError, RuntimeError):
        pass
    if hasattr(bpy.types.WindowManager, 'bsm'):
        del bpy.types.WindowManager.bsm
    for cls in reversed(_registered):
        # Gizmo and GizmoGroup classes have no is_registered: try them too.
        if getattr(cls, 'is_registered', True):
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError:
                pass
    _registered.clear()
    params.unregister()
    from . import _bsmax
    _bsmax.unregister()
    from . import _maya
    _maya.switch.unregister()
    _maya.preferences.unregister()
    from . import localization
    localization.unregister()
