from .localization import tr as _tr
# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.app.handlers import persistent
_mode='BLENDER'
_pending=None
_busy=False
_originals={}
# One return destination per window for the whole Blender -> Max/Maya -> Blender trip.
# Mode-local snapshots can see the previous mode while workspace activation is queued.
_blender_workspaces={}

def _remember_blender_workspaces():
    from . import _maya
    for window in bpy.context.window_manager.windows:
        workspace=window.workspace
        if (workspace is not None and not workspace.get('bsm_workspace')
                and not workspace.get('bsm_editor_kind') and not workspace.get('bsm_native_kind')
                and not _maya.switch.is_maya_workspace(workspace)):
            _blender_workspaces.setdefault(window.as_pointer(),workspace)

def _restore_blender_workspaces():
    if _mode!='BLENDER': return None
    waiting=False
    live={window.as_pointer():window for window in bpy.context.window_manager.windows}
    for ptr,workspace in list(_blender_workspaces.items()):
        window=live.get(ptr)
        try:
            valid=workspace in list(bpy.data.workspaces)
        except ReferenceError:
            valid=False
        if window is None or not valid:
            _blender_workspaces.pop(ptr,None)
        elif window.workspace!=workspace:
            window.workspace=workspace
            waiting=True
        else:
            _blender_workspaces.pop(ptr,None)
    return .05 if waiting else None

def _queue_blender_restore():
    # Assign even if the visible workspace still matches: another mode may have
    # queued a different destination which has not reached the event loop yet.
    for window in bpy.context.window_manager.windows:
        workspace=_blender_workspaces.get(window.as_pointer())
        try:
            if workspace is not None and workspace in list(bpy.data.workspaces):
                window.workspace=workspace
        except ReferenceError:
            pass
    # Keep the snapshot until Blender has actually activated the destination.
    if not bpy.app.timers.is_registered(_restore_blender_workspaces):
        bpy.app.timers.register(_restore_blender_workspaces,first_interval=.05)
def _sync_return_workspaces(mode):
    """Never let a cross-mode handoff store the other mode as Blender's destination."""
    from . import runtime,_maya
    switch=_maya.switch
    for window in bpy.context.window_manager.windows:
        target=_blender_workspaces.get(window.as_pointer())
        try:
            if target is None or target not in list(bpy.data.workspaces):
                continue
            if mode=='MAX':
                runtime._previous_workspace[window.as_pointer()]=target.name
            elif mode=='MAYA':
                # append_activate queues activation, so window.workspace may still
                # be Max here. Update the Maya datablocks rather than that window.
                for workspace in bpy.data.workspaces:
                    if switch.is_maya_workspace(workspace):
                        key=(switch.PREV_KEY if switch.PREV_KEY in workspace
                             else switch.BLENDER_PREV_KEY)
                        workspace[key]=target.name
        except ReferenceError:
            continue

def set_mode(mode,layout=True):
    global _mode,_busy
    if _busy: return
    from . import runtime,_maya
    if mode not in {'BLENDER','MAX','MAYA'}: raise ValueError(mode)
    if (_mode==mode and runtime.is_active()==(mode=='MAX')
            and _maya.switch.is_on()==(mode=='MAYA')):
        return  # Selecting the current destination never toggles or rebuilds it.
    if layout and _mode=='BLENDER' and mode!='BLENDER':
        _remember_blender_workspaces()
    _busy=True
    try:
        # Release mode hooks, but on Max <-> Maya handoffs activate only the
        # final workspace. Returning via Blender queues an unwanted extra screen.
        old_mode=_mode
        exit_layout=layout and mode=='BLENDER'
        if runtime.is_active(): _originals['max_set'](False,layout=exit_layout)
        if _maya.switch.is_on(): _originals['maya_set'](False,layout=exit_layout)
        _mode='BLENDER'
        if mode=='MAX': _originals['max_set'](True,layout=layout)
        elif mode=='MAYA': _originals['maya_set'](True,layout=layout)
        _mode=mode
        if layout and mode!='BLENDER':
            _sync_return_workspaces(mode)
            # The old temporary workspace can be removed once the destination
            # has become visible; never delete a screen still drawn by a window.
            if old_mode=='MAX':
                runtime._schedule_workspace_cleanup()
            elif old_mode=='MAYA':
                switch=_maya.switch
                windows=list(bpy.context.window_manager.windows)
                if windows:
                    for workspace in list(bpy.data.workspaces):
                        if switch.PREV_KEY in workspace:
                            switch._delete_later(windows[0],workspace.name,
                                                 list(workspace.get(switch.MASK_KEY,())))
    except Exception:
        try:
            if runtime.is_active(): _originals['max_set'](False,layout=layout)
            if _maya.switch.is_on(): _originals['maya_set'](False,layout=layout)
        finally: _mode='BLENDER'
        raise
    finally:
        if layout and _mode=='BLENDER':
            _queue_blender_restore()
        _busy=False
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas: area.tag_redraw()
def apply_pending():
    global _pending
    target,_pending=_pending,None
    if target is not None:
        try: set_mode(*target)
        except Exception as error:
            import traceback
            traceback.print_exc()
            def message(self,context,_error=str(error)): self.layout.label(text=_tr(_error))
            bpy.context.window_manager.popup_menu(message,title='Workflow switch failed',icon='ERROR')
    return None
def request(mode,layout=True):
    global _pending
    _pending=(mode,layout)
    if not bpy.app.timers.is_registered(apply_pending): bpy.app.timers.register(apply_pending,first_interval=.01)
class WORKFLOW_OT_mode(bpy.types.Operator):
    bl_idname='workflow.switch_mode'
    bl_label='Switch Workflow'
    mode:bpy.props.EnumProperty(items=[(n,n.title(),'') for n in ('BLENDER','MAX','MAYA')])
    def execute(self,context): request(self.mode); return {'FINISHED'}
def draw_switch(self,context):
    if context.region and context.region.alignment!='RIGHT': return
    row=self.layout.row(align=True)
    for mode,label in (('BLENDER','Blender'),('MAX','Max'),('MAYA','Maya')):
        row.operator('workflow.switch_mode',text=_tr(label),depress=_mode==mode).mode=mode
@persistent
def loaded(_):
    _blender_workspaces.clear()  # workspace references belong to the previous file
    if _mode!='BLENDER':
        # File loading needs layout reconciliation even when the mode name is unchanged.
        target=_mode
        set_mode('BLENDER',layout=False)
        request(target)
def register():
    from . import runtime,_maya
    _originals.update(max_set=runtime.set_active,max_request=runtime.request,
                      maya_set=_maya.switch.set_mode,maya_request=_maya.switch.request)
    runtime.set_active=lambda on,layout=True: set_mode('MAX' if on else 'BLENDER',layout)
    runtime.request=lambda on: request('MAX' if on else 'BLENDER')
    _maya.switch.set_mode=lambda on,layout=True: set_mode('MAYA' if on else 'BLENDER',layout)
    _maya.switch.request=lambda on,layout=True: request('MAYA' if on else 'BLENDER',layout)
    bpy.utils.register_class(WORKFLOW_OT_mode)
    bpy.types.TOPBAR_HT_upper_bar.append(draw_switch)
    bpy.app.handlers.load_post.append(loaded)
def unregister():
    global _pending
    from . import runtime,_maya
    _pending=None
    if bpy.app.timers.is_registered(apply_pending): bpy.app.timers.unregister(apply_pending)
    if _originals:
        set_mode('BLENDER')
        runtime.set_active=_originals['max_set']; runtime.request=_originals['max_request']
        _maya.switch.set_mode=_originals['maya_set']; _maya.switch.request=_originals['maya_request']
        _originals.clear()
    if bpy.app.timers.is_registered(_restore_blender_workspaces):
        bpy.app.timers.unregister(_restore_blender_workspaces)
    _blender_workspaces.clear()
    if loaded in bpy.app.handlers.load_post: bpy.app.handlers.load_post.remove(loaded)
    bpy.types.TOPBAR_HT_upper_bar.remove(draw_switch)
    bpy.utils.unregister_class(WORKFLOW_OT_mode)
