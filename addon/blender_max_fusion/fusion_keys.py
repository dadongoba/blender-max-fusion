# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility diagnostics for the native BlenderMax keymap owner."""
import bpy
report={}
class BSM_OT_fusion_subobject(bpy.types.Operator):
    bl_idname='bsm.fusion_subobject'
    bl_label='Fusion Sub-object Level'
    level:bpy.props.IntProperty(default=0,min=0,max=5)
    def execute(self,context): return bpy.ops.bsm.component(level=self.level)
CLASSES=(BSM_OT_fusion_subobject,)
def __getattr__(name):
    from . import keymap
    if name=='_items': return keymap._owned_items
    if name=='_registered': return bool(keymap._owned_items)
    raise AttributeError(name)
def register_mode():
    from . import keymap
    keymap.register_mode()
    report.update(registered=len(keymap._owned_items),scheme='BlenderMax native',skipped=[])
def unregister_mode():
    from . import keymap
    keymap.unregister_mode()
def set_enabled(on):
    from . import keymap
    keymap.set_enabled(on)
