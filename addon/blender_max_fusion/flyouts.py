# SPDX-License-Identifier: GPL-3.0-or-later
"""Toolbar flyouts, stack/explorer context menus, ribbon panels and small dialogs."""
from .localization import tr as _tr
import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty
from . import runtime
from .operators import Active, viewport_override


def _item(layout, label, op=None, **props):
    if op is None:
        row = layout.row()
        row.enabled = False
        row.operator('bsm.unavailable', text=_tr(label))
        return
    button = layout.operator(op, text=_tr(label))
    for key, value in props.items():
        setattr(button, key, value)


def _choice(layout, label, owner, attr, value, current=None):
    current = getattr(owner, attr) if current is None else current
    button = layout.operator('bsm.set_state', text=_tr(label), icon='RADIOBUT_ON' if current == value else 'RADIOBUT_OFF')
    button.attr, button.value = attr, value


class BSM_OT_unavailable(bpy.types.Operator):
    bl_idname = 'bsm.unavailable'
    bl_label = 'Not available in Blender'
    bl_description = 'This 3ds Max command has no Blender equivalent'

    @classmethod
    def poll(cls, context):
        return False

    def execute(self, context):
        return {'CANCELLED'}


class BSM_OT_set_state(Active, bpy.types.Operator):
    bl_idname = 'bsm.set_state'
    bl_label = 'Set Option'
    attr: StringProperty()
    value: StringProperty()

    @classmethod
    def description(cls, context, properties):
        return properties.value or cls.bl_label

    def execute(self, context):
        state = context.window_manager.bsm
        setattr(state, self.attr, self.value)
        if self.attr == 'selection_filter':
            runtime.apply_selection_filter(context)
        elif self.attr == 'ref_coord':
            runtime.sync_reference(context)
        elif self.attr == 'region_type':
            from .operators import REGION_TOOLS
            tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
            if tool and tool.idname.startswith('builtin.select'):
                with context.temp_override(**viewport_override(context)):
                    bpy.ops.wm.tool_set_by_id(name=REGION_TOOLS[self.value])
        runtime.redraw()
        return {'FINISHED'}


class BSM_MT_selection_filter(bpy.types.Menu):
    bl_label = 'Selection Filter'

    def draw(self, context):
        state = context.window_manager.bsm
        for value, label in (('ALL', 'All'), ('GEOMETRY', 'Geometry'), ('SHAPES', 'Shapes'), ('LIGHTS', 'Lights'),
                             ('CAMERAS', 'Cameras'), ('HELPERS', 'Helpers'), ('WARPS', 'Warps')):
            _choice(self.layout, label, state, 'selection_filter', value)
        _item(self.layout, 'Combos...')
        _choice(self.layout, 'Bone', state, 'selection_filter', 'BONE')
        _item(self.layout, 'IK Chain Object')
        _item(self.layout, 'Point')
        _item(self.layout, 'CAT Bone')


class BSM_MT_region_flyout(bpy.types.Menu):
    bl_label = 'Selection Region'

    def draw(self, context):
        state = context.window_manager.bsm
        for value, label in (('RECT', 'Rectangular Selection Region'), ('CIRCLE', 'Circular Selection Region'),
                             ('FENCE', 'Fence Selection Region'), ('LASSO', 'Lasso Selection Region'), ('PAINT', 'Paint Selection Region')):
            _choice(self.layout, label, state, 'region_type', value)
        self.layout.separator()
        self.layout.prop(state, 'window_selection', text=_tr('Window (off: Crossing)'))


class BSM_MT_scale_flyout(bpy.types.Menu):
    bl_label = 'Scale'

    def draw(self, context):
        for label in ('Select and Uniform Scale', 'Select and Non-uniform Scale', 'Select and Squash'):
            _item(self.layout, label, 'bsm.tool', tool='SCALE')


class BSM_MT_ref_coord(bpy.types.Menu):
    bl_label = 'Reference Coordinate System'

    def draw(self, context):
        state = context.window_manager.bsm
        for value, label in (('VIEW', 'View'), ('SCREEN', 'Screen'), ('WORLD', 'World'), ('PARENT', 'Parent'), ('LOCAL', 'Local'),
                             ('GIMBAL', 'Gimbal'), ('GRID', 'Grid'), ('WORKING', 'Working'), ('LOCAL_ALIGNED', 'Local Aligned')):
            _choice(self.layout, label, state, 'ref_coord', value)
        _item(self.layout, 'Pick', 'bsm.pick_object', purpose='REF_PICK')


class BSM_MT_pivot_center(bpy.types.Menu):
    bl_label = 'Transform Center'

    def draw(self, context):
        ts = context.scene.tool_settings
        for value, label in (('INDIVIDUAL_ORIGINS', 'Use Pivot Point Center'), ('BOUNDING_BOX_CENTER', 'Use Selection Center'),
                             ('CURSOR', 'Use Transform Coordinate Center')):
            button = self.layout.operator('wm.context_set_enum', text=_tr(label), icon='RADIOBUT_ON' if ts.transform_pivot_point == value else 'RADIOBUT_OFF')
            button.data_path, button.value = 'scene.tool_settings.transform_pivot_point', value


class BSM_MT_align_flyout(bpy.types.Menu):
    bl_label = 'Align'

    def draw(self, context):
        l = self.layout
        _item(l, 'Align...', 'bsm.max_command', command='ALIGN')
        _item(l, 'Quick Align', 'bsm.max_command', command='QUICK_ALIGN')
        _item(l, 'Normal Align...')
        _item(l, 'Place Highlight...')
        _item(l, 'Align Camera')
        _item(l, 'Align to View...', 'bsm.max_command', command='ALIGN_TO_VIEW')


class BSM_MT_material_flyout(bpy.types.Menu):
    bl_label = 'Material Editor'

    def draw(self, context):
        _item(self.layout, 'Compact Material Editor...', 'bsm.editor', kind='COMPACT')
        _item(self.layout, 'Slate Material Editor...', 'bsm.editor', kind='MATERIAL')


class BSM_MT_render_flyout(bpy.types.Menu):
    bl_label = 'Render'

    def draw(self, context):
        state = context.window_manager.bsm
        for value, label in (('PRODUCTION', 'Render Production'), ('ITERATIVE', 'Render Iterative'), ('ACTIVESHADE', 'ActiveShade')):
            _choice(self.layout, label, state, 'render_mode', value)
        _item(self.layout, 'Render in Autodesk A360')


class BSM_MT_subcategories(bpy.types.Menu):
    bl_label = 'Object Category'

    def draw(self, context):
        from .surfaces import CREATE, subcategory
        state = context.window_manager.bsm
        for name, _ in CREATE[state.category]:
            _choice(self.layout, name, state, 'subcategory', name, subcategory(state))


def _modifier_labels():
    from . import max_menus
    labels = []

    def walk(items):
        for item in items:
            if isinstance(item, max_menus.Sub):
                walk(item.items)
            elif isinstance(item, max_menus.Item) and item.op == 'bsm.max_modifier':
                labels.append((item.props or {}).get('name', item.label))
    for label, items in max_menus.MAIN:
        if label == 'Modifiers':
            walk(items)
    return sorted(set(labels), key=str.casefold)


class BSM_MT_modifier_list(bpy.types.Menu):
    bl_label = 'Modifier List'

    def draw(self, context):
        from .commands import modifier_available
        labels = _modifier_labels()
        selection = [n for n in labels if n.endswith('Select') or n.startswith('Select By')]
        world = [n for n in labels if '(WSM)' in n]
        rest = [n for n in labels if n not in selection and n not in world]
        row = self.layout.row()
        for title, names in (('SELECTION MODIFIERS', selection), ('WORLD-SPACE MODIFIERS', world), ('OBJECT-SPACE MODIFIERS', rest)):
            for start in range(0, len(names), 34):
                column = row.column()
                column.label(text=_tr(title if start == 0 else ''))
                for name in names[start:start+34]:
                    if modifier_available(name):
                        column.operator('bsm.max_modifier', text=name).name = name
                    else:
                        sub = column.row()
                        sub.enabled = False
                        sub.operator('bsm.unavailable', text=name)


class BSM_MT_modifier_sets(bpy.types.Menu):
    bl_label = 'Configure Modifier Sets'

    def draw(self, context):
        state = context.window_manager.bsm
        self.layout.prop(state, 'show_mod_buttons', text=_tr('Show Buttons'))
        _item(self.layout, 'Configure Modifier Sets...')
        _item(self.layout, 'Show All Sets in List')


class BSM_MT_stack_context(bpy.types.Menu):
    bl_label = 'Modifier Stack'

    def draw(self, context):
        state = context.window_manager.bsm
        name = state.stack_context
        l = self.layout

        def act(label, action, enabled=True):
            row = l.row()
            row.enabled = enabled
            button = row.operator('bsm.stack_action', text=_tr(label))
            button.action, button.modifier = action, name
        modifier = bool(name)
        act('Rename', 'RENAME', modifier)
        act('Delete', 'DELETE', modifier)
        l.separator()
        act('Cut', 'CUT', modifier)
        act('Copy', 'COPY', modifier)
        act('Paste', 'PASTE', bool(_clipboard))
        l.separator()
        act('Make Unique', 'MAKE_UNIQUE')
        act('Collapse To', 'COLLAPSE_TO', modifier)
        act('Collapse All', 'COLLAPSE_ALL')
        l.separator()
        act('On', 'ON', modifier)
        act('Off in Viewport', 'OFF_VIEWPORT', modifier)
        act('Off in Renderer', 'OFF_RENDER', modifier)
        l.separator()
        act('Move Up', 'MOVE_UP', modifier)
        act('Move Down', 'MOVE_DOWN', modifier)
        if not modifier:
            l.separator()
            act('Convert to: Editable Poly', 'CONVERT_POLY')
            act('Convert to: Editable Mesh', 'CONVERT_POLY')
            act('Convert to: Editable Spline', 'CONVERT_SPLINE')


_clipboard = []


class BSM_OT_stack_action(Active, bpy.types.Operator):
    bl_idname = 'bsm.stack_action'
    bl_label = 'Modifier Stack Action'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=tuple((a, a.replace('_', ' ').title(), '') for a in (
        'RENAME', 'DELETE', 'CUT', 'COPY', 'PASTE', 'MAKE_UNIQUE', 'COLLAPSE_TO', 'COLLAPSE_ALL', 'ON', 'OFF_VIEWPORT',
        'OFF_RENDER', 'MOVE_UP', 'MOVE_DOWN', 'MOVE_TO', 'CONVERT_POLY', 'CONVERT_SPLINE')))
    modifier: StringProperty()
    index: IntProperty(default=-1)
    new_name: StringProperty(name='Name')

    def invoke(self, context, event):
        if self.action == 'RENAME':
            self.new_name = self.modifier
            return context.window_manager.invoke_props_dialog(self, width=260, title='Rename Modifier')
        return self.execute(context)

    def execute(self, context):
        from . import params
        state = context.window_manager.bsm
        obj = bpy.data.objects.get(state.stack_pinned) if state.stack_pinned else context.view_layer.objects.active
        if obj is None:
            return {'CANCELLED'}
        mod = obj.modifiers.get(self.modifier)
        a = self.action
        override = dict(viewport_override(context), active_object=obj, object=obj)
        if a == 'RENAME' and mod:
            mod.name = self.new_name
            state.active_modifier = mod.name
        elif a in {'DELETE', 'CUT'} and mod:
            if a == 'CUT':
                _copy(mod)
            obj.modifiers.remove(mod)
            state.active_modifier = ''
        elif a == 'COPY' and mod:
            _copy(mod)
        elif a == 'PASTE' and _clipboard:
            kind, values = _clipboard[0]
            new = obj.modifiers.new(values.get('name', kind.title()), kind)
            if new:
                for key, value in values.items():
                    try:
                        setattr(new, key, value)
                    except (AttributeError, TypeError, ValueError):
                        pass
                state.active_modifier = new.name
        elif a == 'MAKE_UNIQUE':
            if obj.data is not None and obj.data.users > 1:
                obj.data = obj.data.copy()
        elif a == 'COLLAPSE_TO' and mod:
            names = [m.name for m in obj.modifiers]
            if obj.mode != 'OBJECT':
                self.report({'WARNING'}, 'Return to the top level first')
                return {'CANCELLED'}
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            with context.temp_override(**override):
                for name in names[:names.index(mod.name)+1]:
                    bpy.ops.object.modifier_apply(modifier=name)
            params.collapse(obj)
            state.active_modifier = ''
        elif a in {'COLLAPSE_ALL', 'CONVERT_POLY', 'CONVERT_SPLINE'}:
            targets = [o for o in context.view_layer.objects if o.select_get()] or [obj]
            if context.mode != 'OBJECT':
                with context.temp_override(**override):
                    bpy.ops.object.mode_set(mode='OBJECT')
            for target in targets:
                if target.data is not None and target.data.users > 1:
                    target.data = target.data.copy()
                params.collapse(target)
            with context.temp_override(**dict(override, selected_objects=targets, selected_editable_objects=targets)):
                bpy.ops.object.convert(target='CURVE' if a == 'CONVERT_SPLINE' else 'MESH')
            state.active_modifier = ''
        elif a == 'ON' and mod:
            mod.show_viewport = mod.show_render = True
        elif a == 'OFF_VIEWPORT' and mod:
            mod.show_viewport = False
        elif a == 'OFF_RENDER' and mod:
            mod.show_render = False
        elif a in {'MOVE_UP', 'MOVE_DOWN', 'MOVE_TO'} and mod:
            index = list(obj.modifiers).index(mod)
            target = self.index if a == 'MOVE_TO' else index+(1 if a == 'MOVE_UP' else -1)
            target = max(0, min(len(obj.modifiers)-1, target))
            with context.temp_override(**override):
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=target)
        else:
            return {'CANCELLED'}
        runtime.redraw()
        return {'FINISHED'}


def _copy(mod):
    values = {'name': mod.name}
    for p in mod.bl_rna.properties:
        if p.is_readonly or p.identifier in {'name', 'rna_type'} or p.type == 'COLLECTION':
            continue
        value = getattr(mod, p.identifier, None)
        if p.type == 'POINTER' and not isinstance(value, bpy.types.ID):
            continue
        values[p.identifier] = tuple(value) if getattr(p, 'array_length', 0) else value
    _clipboard[:] = [(mod.type, values)]


class BSM_MT_enum_choice(bpy.types.Menu):
    bl_label = 'Choose'

    def draw(self, context):
        from . import surfaces
        if surfaces._enum_owner:
            owner, attr = surfaces._enum_owner
            try:
                self.layout.prop(owner, attr, expand=True)
            except ReferenceError:
                pass


class BSM_MT_key_interpolation(bpy.types.Menu):
    bl_label = 'Key Tangents'

    def draw(self, context):
        for mode, label in (('BEZIER', 'Smooth'), ('LINEAR', 'Linear'), ('CONSTANT', 'Step')):
            self.layout.operator('bsm.key_interpolation', text=_tr(label)).mode = mode
        for label in ('Fast', 'Slow', 'Custom', 'Auto'):
            _item(self.layout, label)


class BSM_MT_key_filters(bpy.types.Menu):
    bl_label = 'Set Key Filters'

    def draw(self, context):
        state = context.window_manager.bsm
        self.layout.prop(state, 'key_filter', expand=True)
        for label in ('Modifiers', 'Object Parameters', 'Custom Attributes', 'Materials', 'Other'):
            _item(self.layout, label)


class BSM_MT_more_utilities(bpy.types.Menu):
    bl_label = 'Utilities'

    def draw(self, context):
        l = self.layout
        _item(l, 'Edit UVWs', 'bsm.editor', kind='UV')
        _item(l, 'Render Setup', 'bsm.editor', kind='RENDER')
        _item(l, 'Scene Explorer', 'bsm.editor', kind='SCENE')
        _item(l, 'Units Setup', 'bsm.max_command', command='UNITS_SETUP')
        _item(l, 'Summary Info', 'bsm.max_command', command='SUMMARY_INFO')
        _item(l, 'Shortcut Reference', 'bsm.shortcuts')
        l.separator()
        _item(l, 'Return to Blender', 'bsm.environment', mode='BLENDER')


class BSM_MT_explorer_context(bpy.types.Menu):
    bl_label = 'Scene Explorer'

    def draw(self, context):
        l = self.layout
        _item(l, 'Hide', 'object.hide_view_set', unselected=False)
        _item(l, 'Unhide All', 'object.hide_view_clear')
        _item(l, 'Freeze', 'bsm.toolbar_action', action='FREEZE')
        _item(l, 'Unfreeze All', 'bsm.toolbar_action', action='UNFREEZE')
        l.separator()
        _item(l, 'Rename', 'bsm.scene_rename')
        _item(l, 'Delete', 'bsm.max_command', command='DELETE')
        l.separator()
        _item(l, 'Select Children', 'object.select_hierarchy', direction='CHILD', extend=True)
        _item(l, 'Object Properties...', 'bsm.object_properties')


class BSM_MT_explorer_mode(bpy.types.Menu):
    bl_label = 'Scene Explorer'

    def draw(self, context):
        _item(self.layout, 'Open Scene Explorer', 'bsm.editor', kind='SCENE')
        _item(self.layout, 'Expand All', 'bsm.explorer_branches', expand=True)
        _item(self.layout, 'Collapse All', 'bsm.explorer_branches', expand=False)


class BSM_OT_explorer_branches(Active, bpy.types.Operator):
    bl_idname = 'bsm.explorer_branches'
    bl_label = 'Expand or Collapse All'
    expand: bpy.props.BoolProperty()

    def execute(self, context):
        from . import surfaces
        surfaces._collapsed.clear()
        if not self.expand:
            surfaces._collapsed.update(o.name for o in context.view_layer.objects if o.children)
        runtime.redraw()
        return {'FINISHED'}


class BSM_MT_ribbon_options(bpy.types.Menu):
    bl_label = 'Ribbon'

    def draw(self, context):
        _item(self.layout, 'Show Full Ribbon')
        _item(self.layout, 'Minimize to Panel Titles')
        self.layout.prop(context.window_manager.bsm, 'ribbon_visible', text=_tr('Show Ribbon'))


def _m(action):
    return ('bsm.mesh_action', {'action': action})


def _c(level):
    return ('bsm.component', {'level': level})


RIBBON_ITEMS = {
    'Polygon Modeling': (('Vertex', _c(1)), ('Edge', _c(2)), ('Border', _c(3)), ('Polygon', _c(4)), ('Element', _c(5)),
                         ('Top Level', _c(0)), None, ('Collapse Stack', ('bsm.stack_action', {'action': 'COLLAPSE_ALL'})),
                         ('Convert to Poly', ('bsm.stack_action', {'action': 'CONVERT_POLY'})), ('Apply Edit Poly Mod', None),
                         ('Show End Result', ('wm.context_toggle', {'data_path': 'window_manager.bsm.show_end_result'}))),
    'Modify Selection': (('Grow', _m('GROW')), ('Shrink', _m('SHRINK')), ('Loop', _m('LOOP')), ('Ring', _m('RING')),
                         ('Similar', ('bsm.max_command', {'command': 'SELECT_SIMILAR'})), ('Fill', None), ('Step Loop', None)),
    'Edit': (('Preserve UVs', None), ('Repeat', _m('REPEAT')), ('QuickSlice', _m('SLICE')), ('SwiftLoop', _m('LOOPCUT')),
             ('NURMS', _m('NURMS')), ('Cut', _m('CUT')), ('P Connect', None), ('Constraints', None)),
    'Geometry (All)': (('Relax', _m('RELAX')), ('Create', _m('CREATE_FACE')), ('Attach', _m('ATTACH')), ('Detach', _m('DETACH')),
                       ('Collapse', _m('COLLAPSE')), ('Cap Poly', _m('CAP')), ('Quadrify All', _m('QUADRIFY')), ('Slice Plane', _m('SLICE'))),
    'Loops': (('Connect', _m('CONNECT_EDGES')), ('Insert Loop', _m('LOOPCUT')), ('Remove Loop', _m('DISSOLVE_EDGES')),
              ('Distance Connect', None), ('Flow Connect', None), ('Build End', None), ('Build Corner', None)),
    'Tris': (('Retriangulate', _m('RETRIANGULATE')), ('Turn', _m('TURN')), ('Quadrify', _m('QUADRIFY'))),
    'Subdivision': (('MeshSmooth', _m('MSMOOTH')), ('Tessellate', _m('TESSELLATE')), ('Use Displacement', None)),
    'Visibility': (('Hide Selected', _m('HIDE')), ('Hide Unselected', _m('HIDE_UNSELECTED')), ('Unhide All', _m('UNHIDE'))),
    'Align': (('Make Planar', _m('PLANAR')), ('X', _m('FLATTEN_X')), ('Y', _m('FLATTEN_Y')), ('Z', _m('FLATTEN_Z')),
              ('To View', None), ('To Grid', None)),
    'Properties': (('Hard', _m('CLEAR_SMOOTH')), ('Smooth', _m('AUTO_SMOOTH')), ('Smooth 30', _m('AUTO_SMOOTH')),
                   ('Set ID', _m('SET_ID')), ('Select ID', _m('SELECT_ID'))),
    'Vertices': (('Remove', _m('DISSOLVE_VERTS')), ('Break', _m('BREAK')), ('Extrude', _m('EXTRUDE_VERTS')), ('Weld', _m('WELD')),
                 ('Chamfer', _m('CHAMFER_VERTS')), ('Target Weld', _m('TARGET_WELD')), ('Connect', _m('CONNECT_VERTS'))),
    'Edges': (('Insert Vertex', _m('INSERT_VERTEX')), ('Remove', _m('DISSOLVE_EDGES')), ('Split', _m('SPLIT_EDGES')),
              ('Extrude', _m('EXTRUDE_EDGES')), ('Weld', _m('WELD')), ('Chamfer', _m('CHAMFER')), ('Target Weld', _m('TARGET_WELD')),
              ('Bridge', _m('BRIDGE')), ('Connect', _m('CONNECT_EDGES')), ('Create Shape', _m('CREATE_SHAPE'))),
    'Borders': (('Extrude', _m('EXTRUDE_EDGES')), ('Chamfer', _m('CHAMFER')), ('Cap', _m('CAP')), ('Bridge', _m('BRIDGE')),
                ('Connect', _m('CONNECT_EDGES'))),
    'Polygons': (('Extrude', _m('EXTRUDE')), ('Outline', _m('OUTLINE')), ('Bevel', _m('BEVEL_POLY')), ('Inset', _m('INSET')),
                 ('Bridge', _m('BRIDGE')), ('Flip', _m('FLIP')), ('Hinge', None), ('Extrude on Spline', None)),
    'Elements': (('Flip', _m('FLIP')), ('Retriangulate', _m('RETRIANGULATE'))),
    'PolyDraw': (('Drag', None), ('Conform', None), ('Step Build', None), ('Extend', None), ('Optimize', None), ('Strips', None)),
    'Paint Deform': (('Shift', ('bsm.sculpt', {'brush': 'GRAB'})), ('Push/Pull', ('bsm.sculpt', {'brush': 'DRAW'})),
                     ('Relax/Soften', ('bsm.sculpt', {'brush': 'SMOOTH'})), ('Smudge', ('bsm.sculpt', {'brush': 'SMUDGE'})),
                     ('Flatten', ('bsm.sculpt', {'brush': 'FLATTEN'})), ('Pinch/Spread', ('bsm.sculpt', {'brush': 'PINCH'}))),
    'Defaults': (('Freeform Defaults', None),),
    'Select': (('Select All', ('object.select_all', {'action': 'SELECT'})),
               ('Select None', ('object.select_all', {'action': 'DESELECT'})), ('Invert', ('object.select_all', {'action': 'INVERT'}))),
    'Stored Selections': (('Copy Store 1', None), ('Paste Store 1', None), ('Add', None), ('Subtract', None), ('Intersect', None)),
    'Sets': (('Manage Selection Sets...', ('bsm.manage_sets', {})),),
    'By Random': (('Select Random', ('object.select_random', {})),),
}


def _ribbon_class(title):
    from .surfaces import ribbon_menu
    items = RIBBON_ITEMS.get(title, ((f'{title} tools', None),))

    def draw(self, context):
        for entry in items:
            if entry is None:
                self.layout.separator()
                continue
            label, target = entry
            if target is None:
                _item(self.layout, label)
            else:
                _item(self.layout, label, target[0], **target[1])
    return type(ribbon_menu(title), (bpy.types.Menu,), {'bl_idname': ribbon_menu(title), 'bl_label': title, 'draw': draw})


def _ribbon_classes():
    from .surfaces import RIBBON_PANELS, LEVEL_PANELS
    titles = {t for panels in RIBBON_PANELS.values() for t in panels if t} | set(LEVEL_PANELS.values())
    return tuple(_ribbon_class(t) for t in sorted(titles))


class BSM_OT_sculpt(Active, bpy.types.Operator):
    bl_idname = 'bsm.sculpt'
    bl_label = 'Paint Deform'
    brush: StringProperty()

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, 'Paint Deform needs an Editable Poly')
            return {'CANCELLED'}
        with context.temp_override(**viewport_override(context)):
            if obj.mode != 'SCULPT':
                bpy.ops.object.mode_set(mode='SCULPT')
            names = {'GRAB': 'builtin_brush.grab', 'DRAW': 'builtin_brush.draw', 'SMOOTH': 'builtin_brush.smooth',
                     'SMUDGE': 'builtin_brush.snake_hook', 'FLATTEN': 'builtin_brush.flatten', 'PINCH': 'builtin_brush.pinch'}
            try:
                bpy.ops.wm.tool_set_by_id(name=names[self.brush])
            except (RuntimeError, KeyError):
                pass
        return {'FINISHED'}


class BSM_OT_keyboard_create(Active, bpy.types.Operator):
    bl_idname = 'bsm.keyboard_create'
    bl_label = 'Create'
    bl_options = {'REGISTER', 'UNDO'}
    kind: StringProperty()

    def execute(self, context):
        from . import params
        from mathutils import Matrix, Vector
        state = context.window_manager.bsm
        if self.kind not in params.DEFAULTS:
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        values = {}
        for attr in params.DEFAULTS[self.kind]:
            if hasattr(state.next_prim, attr):
                values[attr] = getattr(state.next_prim, attr)
        obj = params.new_object(context, self.kind, Matrix.Translation(Vector(state.keyboard_location)), **values)
        obj.color = state.next_color
        from .interactions import next_random_color
        next_random_color(state)
        state.created_this_session = obj.name
        return {'FINISHED'}


class BSM_OT_time_configuration(Active, bpy.types.Operator):
    bl_idname = 'bsm.time_configuration'
    bl_label = 'Time Configuration'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=380)

    def draw(self, context):
        scene = context.scene
        l = self.layout
        l.label(text=_tr('Time Configuration'))
        box = l.box()
        box.label(text=_tr('Frame Rate'))
        row = box.row(align=True)
        for fps, label in ((30, 'NTSC'), (25, 'PAL'), (24, 'Film')):
            button = row.operator('wm.context_set_int', text=_tr(label), depress=scene.render.fps == fps and scene.render.fps_base == 1)
            button.data_path, button.value = 'scene.render.fps', fps
        box.prop(scene.render, 'fps', text=_tr('FPS'))
        box = l.box()
        box.label(text=_tr('Playback'))
        box.prop(scene, 'sync_mode', text=_tr('Real Time'))
        box = l.box()
        box.label(text=_tr('Animation'))
        row = box.row(align=True)
        row.prop(scene, 'frame_start', text=_tr('Start Time'))
        row.prop(scene, 'frame_end', text=_tr('End Time'))
        box.label(text=_tr(f'Length: {scene.frame_end-scene.frame_start}    Frame Count: {scene.frame_end-scene.frame_start+1}'))
        box.prop(scene, 'frame_current', text=_tr('Current Time'))

    def execute(self, context):
        return {'FINISHED'}


CLASSES = (BSM_OT_unavailable, BSM_OT_set_state, BSM_MT_selection_filter, BSM_MT_region_flyout, BSM_MT_scale_flyout,
           BSM_MT_ref_coord, BSM_MT_pivot_center, BSM_MT_align_flyout, BSM_MT_material_flyout, BSM_MT_render_flyout,
           BSM_MT_subcategories, BSM_MT_modifier_list, BSM_MT_modifier_sets, BSM_MT_stack_context, BSM_OT_stack_action,
           BSM_MT_enum_choice, BSM_MT_key_interpolation, BSM_MT_key_filters, BSM_MT_more_utilities, BSM_MT_explorer_context,
           BSM_MT_explorer_mode, BSM_OT_explorer_branches, BSM_MT_ribbon_options, BSM_OT_sculpt, BSM_OT_keyboard_create,
           BSM_OT_time_configuration) + _ribbon_classes()
