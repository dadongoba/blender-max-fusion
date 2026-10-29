# SPDX-License-Identifier: GPL-3.0-or-later
"""Material and animation workflows implemented with Blender's native data.

These controls edit Blender shaders and action slots. They do not emulate or
import proprietary material types, animation controllers, or renderer plugins.
"""
from .localization import tr as _tr

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from . import runtime


def _editable_objects(context):
    return [obj for obj in context.selected_objects if obj.is_editable]


def _material_objects(context):
    return [obj for obj in _editable_objects(context)
            if getattr(obj, "data", None) is not None
            and hasattr(obj.data, "materials") and obj.data.is_editable]


def _assign_material(obj, material):
    index = next((i for i, slot in enumerate(obj.material_slots)
                  if slot.material == material), -1)
    if index < 0:
        obj.data.materials.append(material)
        index = len(obj.material_slots) - 1
    obj.active_material_index = index
    if obj.type == 'MESH':
        if obj.mode == 'EDIT':
            import bmesh
            mesh = bmesh.from_edit_mesh(obj.data)
            for face in mesh.faces:
                if face.select:
                    face.material_index = index
            bmesh.update_edit_mesh(obj.data)
        else:
            for polygon in obj.data.polygons:
                polygon.material_index = index


class _ActiveOperator:
    @classmethod
    def poll(cls, context):
        return runtime.is_active()


class BSM_OT_material_new(_ActiveOperator, bpy.types.Operator):
    bl_idname = "bsm.material_new"
    bl_label = "New Material"
    bl_description = "Create a Blender Principled material and assign it to the active object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objects = _material_objects(context)
        obj = context.view_layer.objects.active
        if obj not in objects:
            self.report({'WARNING'}, "Select an editable object that supports materials")
            return {'CANCELLED'}
        material = bpy.data.materials.new("Max Material")
        material.use_nodes = True
        _assign_material(obj, material)
        return {'FINISHED'}


class BSM_OT_material_assign(_ActiveOperator, bpy.types.Operator):
    bl_idname = "bsm.material_assign"
    bl_label = "Assign Material to Selection"
    bl_description = "Assign the active material to selected objects, or selected faces in Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}
    material_name: StringProperty(name="Material")

    def execute(self, context):
        material = (bpy.data.materials.get(self.material_name) if self.material_name
                    else getattr(context.view_layer.objects.active, 'active_material', None))
        objects = _material_objects(context)
        if not material or not objects:
            self.report({'WARNING'}, "Choose a material and select editable objects")
            return {'CANCELLED'}
        for obj in objects:
            _assign_material(obj, material)
        self.report({'INFO'}, f"Assigned {material.name} to {len(objects)} object(s)")
        return {'FINISHED'}


class BSM_OT_material_duplicate(_ActiveOperator, bpy.types.Operator):
    bl_idname = "bsm.material_duplicate"
    bl_label = "Duplicate Material"
    bl_description = "Make an independent copy of the active material in its current slot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj not in _material_objects(context) or not obj.active_material:
            self.report({'WARNING'}, "Select an object with a material")
            return {'CANCELLED'}
        obj.active_material = obj.active_material.copy()
        return {'FINISHED'}


class BSM_OT_material_remove_slot(_ActiveOperator, bpy.types.Operator):
    bl_idname = "bsm.material_remove_slot"
    bl_label = "Remove Material Slot"
    bl_description = "Remove the active material slot; keep the material datablock"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj not in _material_objects(context) or not obj.material_slots or obj.mode != 'OBJECT':
            self.report({'WARNING'}, "Select an object with material slots in Object Mode")
            return {'CANCELLED'}
        obj.data.materials.pop(index=obj.active_material_index)
        return {'FINISHED'}


def _rotation_path(obj):
    if obj.rotation_mode == 'QUATERNION':
        return 'rotation_quaternion'
    if obj.rotation_mode == 'AXIS_ANGLE':
        return 'rotation_axis_angle'
    return 'rotation_euler'


def _transform_targets(context):
    if context.mode == 'POSE':
        return list(context.selected_pose_bones or [])
    state = getattr(context.window_manager, 'bsm', None)
    named = bpy.data.collections.get(state.key_set) if state and state.key_set else None
    if named is not None:  # the selection set chosen beside Auto/Set Key
        return [obj for obj in named.all_objects if obj.is_editable]
    return _editable_objects(context)


def _paths(target, channels):
    if channels == 'FILTERED':
        chosen = bpy.context.window_manager.bsm.key_filter
        return [p for c in ('LOCATION', 'ROTATION', 'SCALE') if c in chosen for p in _paths(target, c)]
    paths = []
    if channels in {'ALL', 'LOCATION'}:
        paths.append('location')
    if channels in {'ALL', 'ROTATION'}:
        paths.append(_rotation_path(target))
    if channels in {'ALL', 'SCALE'}:
        paths.append('scale')
    return paths


class BSM_OT_keyframe(_ActiveOperator, bpy.types.Operator):
    bl_idname = "bsm.keyframe"
    bl_label = "Set Transform Keys"
    bl_description = "Insert Blender transform keys for selected objects or pose bones at the current frame"
    bl_options = {'REGISTER', 'UNDO'}
    channels: EnumProperty(name="Channels", items=(
        ('ALL', 'Position / Rotation / Scale', ''),
        ('LOCATION', 'Position', ''), ('ROTATION', 'Rotation', ''),
        ('SCALE', 'Scale', ''), ('FILTERED', 'Key Filters', 'Channels chosen in Key Filters')), default='ALL')
    delete: BoolProperty(name="Delete Keys", default=False)

    def execute(self, context):
        targets = _transform_targets(context)
        if not targets:
            self.report({'WARNING'}, "Select editable objects or pose bones")
            return {'CANCELLED'}
        count = 0
        for target in targets:
            for path in _paths(target, self.channels):
                try:
                    if self.delete:
                        ok = target.keyframe_delete(data_path=path, frame=context.scene.frame_current)
                    else:
                        ok = target.keyframe_insert(data_path=path, frame=context.scene.frame_current,
                                                   group=getattr(target, 'name', 'Transforms'))
                    count += bool(ok)
                except (RuntimeError, TypeError) as error:
                    # Linked or fully locked targets cannot always receive keys.
                    self.report({'WARNING'}, str(error))
        if not count:
            self.report({'WARNING'}, "No matching keys removed" if self.delete else "No keys inserted")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{'Removed' if self.delete else 'Keyed'} {count} transform channel group(s)")
        return {'FINISHED'}


def _action_fcurves(obj):
    """Return curves of this object's active slot, including Blender 5 actions."""
    animation = obj.animation_data
    if not animation or not animation.action:
        return []
    action = animation.action
    slot = getattr(animation, 'action_slot', None)
    if getattr(action, 'is_action_layered', False):
        curves = []
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, 'channelbags', []):
                    if slot is not None and bag.slot_handle == slot.handle:
                        curves.extend(bag.fcurves)
        return curves
    return list(getattr(action, 'fcurves', []))


class BSM_OT_key_interpolation(_ActiveOperator, bpy.types.Operator):
    bl_idname = "bsm.key_interpolation"
    bl_label = "Set Key Interpolation"
    bl_description = "Set interpolation on keys at the current frame for selected objects or selected pose bones"
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(name="Interpolation", items=(
        ('BEZIER', 'Bezier', ''), ('LINEAR', 'Linear', ''),
        ('CONSTANT', 'Constant', '')), default='BEZIER')

    def execute(self, context):
        frame = context.scene.frame_current
        count = 0
        if context.mode == 'POSE':
            objects = [context.view_layer.objects.active] if context.view_layer.objects.active else []
            prefixes = tuple(bone.path_from_id() + '.' for bone in context.selected_pose_bones or [])
        else:
            objects = _editable_objects(context)
            prefixes = None
        for obj in objects:
            for curve in _action_fcurves(obj):
                if prefixes is not None and not curve.data_path.startswith(prefixes):
                    continue
                for point in curve.keyframe_points:
                    if abs(point.co.x - frame) < 0.0001:
                        point.interpolation = self.mode
                        count += 1
                curve.update()
            obj.update_tag()
        if not count:
            self.report({'WARNING'}, "No keys on the current frame")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Updated {count} key(s)")
        return {'FINISHED'}


def draw_materials(layout, context):
    """Compact material controls, shared by the command panel and editor popup."""
    row = layout.row(align=True)
    row.operator('bsm.editor', text=_tr('Node Editor'), icon='NODETREE').kind = 'MATERIAL'
    row.operator('bsm.editor', text=_tr('Compact'), icon='MATERIAL').kind = 'COMPACT'
    layout.label(text=_tr('Blender Principled materials'), icon='INFO')
    obj = context.view_layer.objects.active
    if not obj or not getattr(obj, 'data', None) or not hasattr(obj.data, 'materials'):
        layout.label(text=_tr('Select an object with material support.'))
        return
    row = layout.row()
    row.template_list('MATERIAL_UL_matslots', '', obj, 'material_slots',
                      obj, 'active_material_index', rows=3)
    col = row.column(align=True)
    col.operator('bsm.material_new', text=_tr(''), icon='ADD')
    remove = col.row()
    remove.enabled = obj.mode == 'OBJECT'
    remove.operator('bsm.material_remove_slot', text=_tr(''), icon='REMOVE')
    layout.template_ID(obj, 'active_material', new='bsm.material_new')
    material = obj.active_material
    if not material:
        return
    row = layout.row(align=True)
    row.operator('bsm.material_assign', text=_tr('Assign to Selection'), icon='CHECKMARK')
    row.operator('bsm.material_duplicate', text=_tr(''), icon='DUPLICATE')
    layout.prop(material, 'name', text=_tr('Name'))
    if material.use_nodes and material.node_tree:
        shader = next((node for node in material.node_tree.nodes
                       if node.type == 'BSDF_PRINCIPLED'), None)
        if shader:
            for name in ('Base Color', 'Metallic', 'Roughness', 'IOR', 'Alpha'):
                socket = shader.inputs.get(name)
                if socket and not socket.is_linked:
                    layout.prop(socket, 'default_value', text=name)
                elif socket:
                    layout.label(text=_tr(f'{name}: linked in Node Editor'), icon='LINKED')
        else:
            layout.label(text=_tr('Edit this shader in Node Editor.'))
    else:
        layout.prop(material, 'diffuse_color', text=_tr('Viewport Color'))
        layout.prop(material, 'metallic')
        layout.prop(material, 'roughness')
    layout.separator()
    layout.prop(material, 'diffuse_color', text=_tr('Viewport Color'))


def draw_animation(layout, context):
    scene = context.scene
    row = layout.row(align=True)
    row.prop(scene.tool_settings, 'use_keyframe_insert_auto', text=_tr('Auto Key'),
             icon='REC', toggle=True)
    row.prop(scene.tool_settings, 'auto_keying_mode', text=_tr(''))
    layout.label(text=_tr('Auto Key uses Blender keying rules.'), icon='INFO')
    row = layout.row(align=True)
    row.operator('bsm.keyframe', text=_tr('Set Keys'), icon='KEY_HLT')
    row.operator('bsm.keyframe', text=_tr('Delete Keys'), icon='KEY_DEHLT').delete = True
    layout.operator_menu_enum('bsm.keyframe', 'channels', text=_tr('Key Channels'))
    layout.operator_menu_enum('bsm.key_interpolation', 'mode', text=_tr('Current Key Interpolation'))
    row = layout.row(align=True)
    row.prop(scene, 'frame_start', text=_tr('Start'))
    row.prop(scene, 'frame_end', text=_tr('End'))
    layout.prop(scene, 'frame_current', text=_tr('Time'))
    row = layout.row(align=True)
    row.operator('screen.frame_jump', text=_tr(''), icon='REW').end = False
    row.operator('screen.keyframe_jump', text=_tr(''), icon='PREV_KEYFRAME').next = False
    row.operator('screen.animation_play', text=_tr(''), icon='PLAY_REVERSE').reverse = True
    row.operator('screen.animation_play', text=_tr(''), icon='PAUSE' if context.screen and context.screen.is_animation_playing else 'PLAY')
    row.operator('screen.keyframe_jump', text=_tr(''), icon='NEXT_KEYFRAME').next = True
    row.operator('screen.frame_jump', text=_tr(''), icon='FF').end = True
    row = layout.row(align=True)
    row.operator('bsm.editor', text=_tr('Curve Editor'), icon='GRAPH').kind = 'GRAPH'
    row.operator('bsm.editor', text=_tr('Dope Sheet'), icon='ACTION').kind = 'DOPESHEET'


CLASSES = (
    BSM_OT_material_new, BSM_OT_material_assign, BSM_OT_material_duplicate,
    BSM_OT_material_remove_slot, BSM_OT_keyframe, BSM_OT_key_interpolation,
)
