# SPDX-License-Identifier: GPL-3.0-or-later
"""Idempotent toolbar cleanup, including Blender's generic missing-tool error."""
import bpy

def unregister_tools(gizmo):
    # Restore native active tools while the old definitions still exist.
    gizmo.restore_blender_tools(bpy.context)
    if gizmo._draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(gizmo._draw_handle,'WINDOW')
        gizmo._draw_handle=None
    for tool in reversed(gizmo.WORKSPACE_TOOLS):
        if not hasattr(tool,'_bl_tool'): continue
        try:
            bpy.utils.unregister_tool(tool)
        except Exception as error:
            # Blender raises plain Exception when the tool definition is already absent.
            if not str(error).startswith('Unable to remove '): raise
    gizmo._tool_registered=False
    gizmo._hover.clear()

def disable_legacy(package, ids, preference_names):
    import sys, addon_utils
    def live(module):
        registered=getattr(module,'_registered',None)
        return any(registered) if isinstance(registered,(list,tuple)) else bool(registered)
    candidates=set(bpy.context.preferences.addons.keys())
    candidates.update(k for k,m in list(sys.modules.items())
                      if k.rsplit('.',1)[-1] in ids and live(m))
    values=None
    for key in sorted(candidates):
        if key==package or key.rsplit('.',1)[-1] not in ids: continue
        entry=bpy.context.preferences.addons.get(key)
        old=getattr(entry,'preferences',None)
        if old is not None and values is None:
            values={n:getattr(old,n) for n in preference_names if hasattr(old,n)}
        mod=sys.modules.get(key)
        gizmo=getattr(mod,'max_gizmo',None)
        if gizmo is not None:
            runtime=getattr(mod,'runtime',None)
            if runtime and runtime.is_active(): runtime.set_active(False)
            original=gizmo.unregister_tool
            gizmo.unregister_tool=lambda g=gizmo: unregister_tools(g)
        try:
            if mod and not getattr(mod,'__addon_enabled__',False) and live(mod):
                # A previous failed disable cleared the enabled flag but left classes live.
                mod.unregister()
            errors=[]
            addon_utils.disable(key,default_set=True,handle_error=errors.append)
            if errors: raise RuntimeError(f'Unable to clean up {key}: {errors!r}')
        finally:
            if gizmo is not None: gizmo.unregister_tool=original
    return values
