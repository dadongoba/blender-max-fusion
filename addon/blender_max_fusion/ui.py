# SPDX-License-Identifier: GPL-3.0-or-later
"""Session state, the 3ds Max menu bar and the Scene Explorer menus."""
from .localization import tr as _tr
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty
from . import runtime, params


def _changed(name):
    return lambda self, context: runtime.on_state(context, name)


class BSM_State(bpy.types.PropertyGroup):
    explorer_search: StringProperty(name='Search Scene', update=lambda self, context: runtime.redraw())
    explorer_scroll: IntProperty(default=0, min=0)
    explorer_filter: EnumProperty(name='Display', options={'ENUM_FLAG'}, items=tuple((k, k.title(), '') for k in (
        'MESH', 'CURVE', 'LIGHT', 'CAMERA', 'EMPTY', 'FIELD', 'GROUP', 'XREF', 'ARMATURE', 'CONTAINER', 'FROZEN', 'HIDDEN')),
        default={'MESH', 'CURVE', 'LIGHT', 'CAMERA', 'EMPTY', 'FIELD', 'GROUP', 'XREF', 'ARMATURE', 'CONTAINER', 'FROZEN', 'HIDDEN'})
    tool_search: StringProperty(name='Search All Objects')
    finite_grid: BoolProperty(name='Show Home Grid', default=True)
    grid_spacing: FloatProperty(name='Grid Spacing', default=1., min=1e-4, subtype='DISTANCE', unit='LENGTH')
    next_name: StringProperty(name='Name')
    next_color: FloatVectorProperty(name='Object Color', subtype='COLOR', size=4, min=0, max=1, default=(.53, .89, .11, 1))
    tab: EnumProperty(name='Command Panel', items=(
        ('CREATE', 'Create', 'Create objects', 'ADD', 0),
        ('MODIFY', 'Modify', 'Modifier stack and mesh tools', 'MODIFIER', 1),
        ('HIERARCHY', 'Hierarchy', 'Pivots and linking', 'OUTLINER', 2),
        ('MOTION', 'Motion', 'Controllers, keys and motion paths', 'ANIM', 3),
        ('DISPLAY', 'Display', 'Visibility and viewport display', 'HIDE_OFF', 4),
        ('UTILITIES', 'Utilities', 'Scene and object utilities', 'TOOL_SETTINGS', 5),
        ('MATERIAL', 'Material', 'Material assignment and shader controls', 'MATERIAL', 6)), default='CREATE')
    category: EnumProperty(name='Category', items=tuple((x, n, '') for x, n in (
        ('GEOMETRY', 'Geometry'), ('SHAPES', 'Shapes'), ('LIGHTS', 'Lights'), ('CAMERAS', 'Cameras'),
        ('HELPERS', 'Helpers'), ('SPACEWARPS', 'Space Warps'), ('SYSTEMS', 'Systems'))), default='GEOMETRY')
    subcategory: StringProperty(name='Object Category')
    autogrid: BoolProperty(name='AutoGrid')
    active_creation: StringProperty(name='Creation Tool')
    created_this_session: StringProperty()
    next_prim: PointerProperty(type=params.BSM_PrimitiveParams)
    keyboard_location: FloatVectorProperty(name='Keyboard Entry', subtype='TRANSLATION', unit='LENGTH', size=3)
    active_modifier: StringProperty(name='Selected Modifier')
    stack_context: StringProperty()
    stack_pinned: StringProperty(name='Pin Stack')
    stack_expanded: BoolProperty(name='Show Sub-object Levels', default=True)
    show_end_result: BoolProperty(name='Show End Result', default=True)
    show_mod_buttons: BoolProperty(name='Show Buttons')
    last_material_editor: EnumProperty(name='Material Editor', items=(('MATERIAL', 'Slate', ''), ('COMPACT', 'Compact', '')), default='MATERIAL')
    component: IntProperty(default=0, min=0, max=5)
    material_id: IntProperty(name='Material ID', default=1, min=1, max=65535)
    selection_locked: BoolProperty(default=False)
    region_type: EnumProperty(name='Selection Region', items=tuple((k, k.title(), '') for k in ('RECT', 'CIRCLE', 'FENCE', 'LASSO', 'PAINT')))
    window_selection: BoolProperty(name='Window/Crossing', description='On: objects must be fully inside the region (Window); off: Crossing')
    selection_filter: EnumProperty(name='Selection Filter', update=_changed('selection_filter'), items=tuple((k, k.title(), '') for k in (
        'ALL', 'GEOMETRY', 'SHAPES', 'LIGHTS', 'CAMERAS', 'HELPERS', 'WARPS', 'BONE')))
    ref_coord: EnumProperty(name='Reference Coordinate System', update=_changed('ref_coord'), items=tuple((k, k.replace('_', ' ').title(), '') for k in (
        'VIEW', 'SCREEN', 'WORLD', 'PARENT', 'LOCAL', 'GIMBAL', 'GRID', 'WORKING', 'LOCAL_ALIGNED', 'PICK')))
    ref_pick: StringProperty()
    manipulate: BoolProperty(name='Select and Manipulate', update=_changed('manipulate'))
    keyboard_override: BoolProperty(name='Keyboard Shortcut Override', default=True, update=_changed('keyboard_override'),
                                    description='On: 3ds Max shortcuts; off: Blender shortcuts')
    snap_mode: EnumProperty(name='Snaps', items=(('2D', '2D', ''), ('2.5D', '2.5D', ''), ('3D', '3D', '')), default='3D')
    spinner_snap: BoolProperty(name='Spinner Snap')
    spinner_snap_value: FloatProperty(name='Spinner Snap', default=1., min=1e-4)
    new_set_name: StringProperty(name='Named Selection Sets')
    ribbon_visible: BoolProperty(name='Show Ribbon', default=True, update=lambda self, context: runtime.redraw())
    ribbon_tab: EnumProperty(items=tuple((k, k.replace('_', ' ').title(), '') for k in ('MODELING', 'FREEFORM', 'SELECTION', 'OBJECT_PAINT', 'POPULATE')))
    render_mode: EnumProperty(items=(('PRODUCTION', 'Render Production', ''), ('ITERATIVE', 'Render Iterative', ''), ('ACTIVESHADE', 'ActiveShade', '')))
    pick_mode: StringProperty()
    hierarchy_tab: EnumProperty(items=(('PIVOT', 'Pivot', ''), ('IK', 'IK', ''), ('LINK', 'Link Info', '')))
    motion_tab: EnumProperty(items=(('PARAMETERS', 'Parameters', ''), ('PATHS', 'Motion Paths', '')))
    hide_frozen: BoolProperty(name='Hide Frozen Objects')
    freeze_gray: BoolProperty(name='Show Frozen in Gray', default=True)
    utility: StringProperty()
    offset_mode: BoolProperty(name='Offset Mode Transform Type-In')
    offset_vector: FloatVectorProperty(name='Offset', size=3)
    key_filter: EnumProperty(name='Key Filters', options={'ENUM_FLAG'}, items=(('LOCATION', 'Position', ''), ('ROTATION', 'Rotation', ''), ('SCALE', 'Scale', '')),
                             default={'LOCATION', 'ROTATION', 'SCALE'})
    prompt: StringProperty()
    # Time controls and track bar of Max's status panel.
    key_mode: BoolProperty(name='Key Mode Toggle', description='Previous and Next Frame jump between keys of the selection')
    set_key_mode: BoolProperty(name='Set Key Mode', description='Pose freely, then commit keys with the Set Keys button (K)',
                               update=_changed('set_key_mode'))
    key_set: StringProperty(name='Key Selection Set', description='Named selection set keyed by Set Keys; empty keys the selection')
    track_filter: EnumProperty(name='Track Bar Filter', items=(
        ('ALL', 'All Keys', ''), ('TRANSFORM', 'All Transform Keys', ''), ('LOCATION', 'Current Transform: Position', ''),
        ('ROTATION', 'Current Transform: Rotation', ''), ('SCALE', 'Current Transform: Scale', '')), default='ALL',
        update=lambda self, context: runtime.redraw())
    track_numbers: BoolProperty(name='Show Frame Numbers', default=True, update=lambda self, context: runtime.redraw())
    cursor_coords: FloatVectorProperty(name='Cursor Position', size=3)
    cursor_valid: BoolProperty()
    show_viewcube: BoolProperty(name='Show the ViewCube', default=True)
    shade_selected: BoolProperty()


def draw_switch(self, context):
    if context.region and context.region.alignment != 'RIGHT':
        return
    row = self.layout.row(align=True)
    row.operator('bsm.environment', text=_tr('Blender'), depress=not runtime.is_active()).mode = 'BLENDER'
    row.operator('bsm.environment', text=_tr('Max Fusion'), depress=runtime.is_active()).mode = 'STUDIO'


def draw_view_header(self, context):
    layout = self.layout
    row = layout.row(align=True)
    for tool, icon, label in (('SELECT', 'RESTRICT_SELECT_OFF', 'Q'), ('MOVE', 'ORIENTATION_GLOBAL', 'W'),
                              ('ROTATE', 'DRIVER_ROTATIONAL_DIFFERENCE', 'E'), ('SCALE', 'FULLSCREEN_ENTER', 'R')):
        row.operator('bsm.tool', text=_tr(label), icon=icon).tool = tool
    layout.separator_spacer()
    layout.prop(context.space_data.shading, 'type', text=_tr(''), expand=True, icon_only=True)


def draw_time_header(self, context):
    if context.area.ui_type != 'TIMELINE':
        _original_time_header(self, context)
        return
    scene = context.scene
    layout = self.layout
    layout.prop(scene, 'frame_current', text=_tr('Time'))
    row = layout.row(align=True)
    row.prop(scene, 'frame_start', text=_tr('Start'))
    row.prop(scene, 'frame_end', text=_tr('End'))
    layout.prop(scene.tool_settings, 'use_keyframe_insert_auto', text=_tr('Auto Key'), icon='REC', toggle=True)
    layout.operator('bsm.keyframe', text=_tr('Set Keys'), icon='KEY_HLT')


_original_time_header = bpy.types.DOPESHEET_HT_header.draw


def draw_menus(self, context):
    from . import max_menus
    for idname, label in max_menus.MAIN_MENUS:
        self.layout.menu(idname, text=_tr(label))


# Scene Explorer menu bar (Select / Display / Edit).
class BSM_MT_edit(bpy.types.Menu):
    bl_label = 'Edit'

    def draw(self, context):
        l = self.layout
        l.operator('ed.undo', text=_tr('Undo'))
        l.operator('ed.redo', text=_tr('Redo'))
        l.separator()
        l.operator('bsm.scene_rename', text=_tr('Rename...'))
        l.operator('bsm.max_command', text=_tr('Delete')).command = 'DELETE'
        l.separator()
        l.operator('bsm.max_command', text=_tr('Group...')).command = 'GROUP'
        l.operator('bsm.max_command', text=_tr('Ungroup')).command = 'UNGROUP'
        l.operator('bsm.toolbar_action', text=_tr('Unlink Selected')).action = 'UNLINK'


class BSM_MT_selection(bpy.types.Menu):
    bl_label = 'Select'

    def draw(self, context):
        l = self.layout
        for action, label in (('SELECT', 'Select All'), ('DESELECT', 'Select None'), ('INVERT', 'Select Invert')):
            l.operator('object.select_all', text=_tr(label)).action = action
        l.separator()
        l.operator('object.select_hierarchy', text=_tr('Select Children')).direction = 'CHILD'
        l.operator('bsm.max_command', text=_tr('Select Instances')).command = 'SELECT_INSTANCES'
        l.operator('bsm.max_command', text=_tr('Select Dependents')).command = 'SELECT_SIMILAR'
        l.separator()
        l.operator('bsm.explorer_search', text=_tr('Find...'))


class BSM_MT_display(bpy.types.Menu):
    bl_label = 'Display'

    def draw(self, context):
        l = self.layout
        l.operator('bsm.explorer_branches', text=_tr('Expand All')).expand = True
        l.operator('bsm.explorer_branches', text=_tr('Collapse All')).expand = False
        l.separator()
        l.operator('object.hide_view_set', text=_tr('Hide Selected')).unselected = False
        l.operator('object.hide_view_set', text=_tr('Hide Unselected')).unselected = True
        l.operator('object.hide_view_clear', text=_tr('Unhide All'))


CLASSES = (BSM_State, BSM_MT_edit, BSM_MT_selection, BSM_MT_display)
