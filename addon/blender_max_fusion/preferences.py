from .localization import tr as _tr
# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import BoolProperty, StringProperty, EnumProperty


def _splash_changed(self, context):
    from . import runtime
    runtime.apply_splash(runtime.is_active())


from ._maya.preferences import ALLSET_AddonPreferences

class BSM_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    maya: bpy.props.PointerProperty(type=ALLSET_AddonPreferences)
    startup_mode: bpy.props.EnumProperty(name='Startup Workflow',items=[(n,n.title(),'') for n in ('BLENDER','MAX','MAYA')],default='BLENDER')
    enabled_mode: BoolProperty(name='Start in Blender Max', default=False)
    studio_colors: BoolProperty(name='Max gray colors', default=True,
        description='Temporarily apply original gray UI colors; restore the previous colors on exit')
    theme_backup: StringProperty(default='', options={'HIDDEN'})
    splash_image: StringProperty(name='Custom Splash Image', subtype='FILE_PATH', update=_splash_changed,
        description="PNG or JPEG shown as Blender's splash screen while Max mode is on. "
                    "Blender's own splash is 1000 x 500 px; the version number is drawn at the top right")
    last_material_editor: EnumProperty(name='Material Editor',items=(('MATERIAL','Slate',''),('COMPACT','Compact','')),default='MATERIAL')

    def draw(self,context):
        from . import unified_controller
        layout=self.layout
        layout.label(text=_tr('Unified Workflow 0.3.0 / Blender, Max and Maya'))
        row=layout.row(align=True)
        for mode in ('BLENDER','MAX','MAYA'):
            row.operator('workflow.switch_mode',text=_tr(mode.title()),depress=unified_controller._mode==mode).mode=mode
        layout.prop(self,'startup_mode')
        layout.prop(self,'studio_colors')
        box=layout.box(); box.label(text=_tr('Maya Options'))
        for name in ('select_through','preselect_highlight','select_priority'):
            box.prop(self.maya,name)
        layout.operator('bsm.shortcuts',text=_tr('Max Shortcut Reference'))



CLASSES=(BSM_Preferences,)
