# SPDX-License-Identifier: GPL-3.0-or-later
"""Max's time controls under the viewports: track bar keys, Create Key, time tags,
key sets, default tangents and the viewport navigation controls that Blender lacks.

The track bar shows the keys of the selected objects, filtered like Max's track bar
(All Keys, All Transform Keys, Current Transform). Key frames are whole frames, as in
Max's default Snap to Frames.
"""
from .localization import tr as _tr
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from . import runtime
from .editors import _action_fcurves
from .operators import Active, viewport_override

selected = set()  # frames of the selected track bar keys
menu_frame = [0]  # frame under the cursor when the track bar menu opened


def kind_of(curve):
    path = curve.data_path.rsplit('.', 1)[-1]
    if path == 'location':
        return 'LOCATION'
    if path.startswith('rotation'):
        return 'ROTATION'
    return 'SCALE' if path == 'scale' else 'OTHER'


def _shown(curve, filter):
    kind = kind_of(curve)
    return filter == 'ALL' or (filter == 'TRANSFORM' and kind != 'OTHER') or kind == filter


def track_keys(context):
    """{frame: kinds} for the selected objects' keys that the track bar filter shows."""
    filter = context.window_manager.bsm.track_filter
    keys = {}
    for obj in context.selected_objects:
        for curve in _action_fcurves(obj):
            if _shown(curve, filter):
                for point in curve.keyframe_points:
                    keys.setdefault(int(round(point.co.x)), set()).add(kind_of(curve))
    return keys


def _points(context, frames):
    filter = context.window_manager.bsm.track_filter
    found = []
    for obj in context.selected_objects:
        if not obj.is_editable:
            continue
        for curve in _action_fcurves(obj):
            if _shown(curve, filter) and not curve.lock:
                found += [(obj, curve, p) for p in curve.keyframe_points if int(round(p.co.x)) in frames]
    return found


def snapshot(context, frames):
    """The keys to drag. Blender can reallocate or re-sort a curve's keys while they move,
    so each key is found again by its current time and value rather than kept by reference."""
    return [dict(obj=obj, curve=curve, value=p.co.y, x=p.co.x, left=p.handle_left.x, right=p.handle_right.x, now=p.co.x)
            for obj, curve, p in _points(context, frames)]


def move(entries, delta):
    """Offset the snapshot keys by delta frames from where they started."""
    for curve in {e['curve'] for e in entries}:
        taken = set()
        for entry in (e for e in entries if e['curve'] == curve):
            point = next((p for i, p in enumerate(curve.keyframe_points) if i not in taken
                          and abs(p.co.x-entry['now']) < 1e-4 and abs(p.co.y-entry['value']) < 1e-6), None)
            if point is None:
                continue
            taken.add(list(curve.keyframe_points).index(point))
            shift = entry['x']+delta-point.co.x
            point.co.x += shift
            point.handle_left.x += shift
            point.handle_right.x += shift
            entry['now'] = point.co.x
        curve.update()
    for obj in {e['obj'] for e in entries}:
        obj.update_tag(refresh={'TIME'})
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)


def delete(context, frames):
    entries = _points(context, frames)
    for curve in {c for _, c, _ in entries}:
        for point in reversed([p for _, c, p in entries if c == curve]):
            curve.keyframe_points.remove(point, fast=True)
        curve.update()
    for obj in {o for o, _, _ in entries}:
        obj.update_tag(refresh={'TIME'})
    selected.difference_update(frames)
    return len(entries)


class BSM_OT_trackbar(Active, bpy.types.Operator):
    bl_idname = 'bsm.trackbar'
    bl_label = 'Track Bar'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=(('DELETE', 'Delete Selected Keys', ''), ('GOTO', 'Goto Time', ''),
                                ('SELECT_ALL', 'Select All Keys', ''), ('SELECT_NONE', 'Select None', '')))

    def execute(self, context):
        if self.action == 'DELETE':
            if not delete(context, set(selected)):
                self.report({'WARNING'}, 'Select keys on the track bar first')
                return {'CANCELLED'}
        elif self.action == 'GOTO':
            context.scene.frame_set(menu_frame[0])
        elif self.action == 'SELECT_ALL':
            selected.update(track_keys(context))
        else:
            selected.clear()
        runtime.redraw()
        return {'FINISHED'}


class BSM_MT_trackbar_filter(bpy.types.Menu):
    bl_label = 'Filter'

    def draw(self, context):
        self.layout.props_enum(context.window_manager.bsm, 'track_filter')


class BSM_MT_trackbar_configure(bpy.types.Menu):
    bl_label = 'Configure'

    def draw(self, context):
        self.layout.prop(context.window_manager.bsm, 'track_numbers')
        self.layout.prop(context.window_manager.bsm, 'key_mode', text=_tr('Key Mode (Previous/Next Key)'))


class BSM_MT_trackbar(bpy.types.Menu):
    bl_label = 'Track Bar'

    def draw(self, context):
        layout = self.layout
        layout.operator('bsm.editor', text=_tr('Key Properties...')).kind = 'GRAPH'
        layout.separator()
        row = layout.row()
        row.enabled = bool(selected)
        row.operator('bsm.trackbar', text=_tr('Delete Selected Keys')).action = 'DELETE'
        layout.operator('bsm.trackbar', text=_tr('Select All Keys')).action = 'SELECT_ALL'
        layout.separator()
        layout.menu('BSM_MT_trackbar_filter')
        layout.operator('bsm.trackbar', text=_tr(f'Goto Time ({menu_frame[0]})')).action = 'GOTO'
        layout.menu('BSM_MT_trackbar_configure')


class BSM_OT_create_key(Active, bpy.types.Operator):
    """Max's Create Key dialog: key the pose of one frame at another frame."""
    bl_idname = 'bsm.create_key'
    bl_label = 'Create Key'
    bl_options = {'REGISTER', 'UNDO'}
    source: IntProperty(name='Source Time')
    destination: IntProperty(name='Destination Time')
    position: BoolProperty(name='Position', default=True)
    rotation: BoolProperty(name='Rotation', default=True)
    scale: BoolProperty(name='Scale', default=True)

    def invoke(self, context, event):
        self.source = self.destination = context.scene.frame_current
        return context.window_manager.invoke_props_dialog(self, width=260)

    def execute(self, context):
        from .editors import _transform_targets, _paths
        channels = [c for c, on in (('LOCATION', self.position), ('ROTATION', self.rotation), ('SCALE', self.scale)) if on]
        targets = _transform_targets(context)
        if not targets or not channels:
            self.report({'WARNING'}, 'Select objects and at least one transform')
            return {'CANCELLED'}
        scene, count = context.scene, 0
        for target in targets:
            obj = target.id_data
            curves = {(c.data_path, c.array_index): c for c in _action_fcurves(obj)}
            prefix = f'pose.bones["{target.name}"].' if target != obj else ''
            for channel in channels:
                for path in _paths(target, channel):
                    value = list(getattr(target, path))
                    for i in range(len(value)):
                        curve = curves.get((prefix+path, i))
                        if curve is not None:
                            value[i] = curve.evaluate(self.source)
                    setattr(target, path, value)
                    count += bool(target.keyframe_insert(data_path=path, frame=self.destination))
        scene.frame_set(scene.frame_current)  # back to the animated pose of the current frame
        self.report({'INFO'}, f'Created {count} key(s) at frame {self.destination}')
        return {'FINISHED'}


class BSM_OT_time_tag(Active, bpy.types.Operator):
    bl_idname = 'bsm.time_tag'
    bl_label = 'Time Tag'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=(('ADD', 'Add Tag', ''), ('EDIT', 'Edit Tag', ''), ('DELETE', 'Delete Tag', ''), ('GOTO', 'Go to Tag', '')))
    name: StringProperty(name='Tag Name')
    frame: IntProperty()

    def invoke(self, context, event):
        scene = context.scene
        if self.action in {'ADD', 'EDIT'}:
            tag = self._at_current(scene)
            if self.action == 'EDIT' and tag is None:
                self.report({'WARNING'}, 'No time tag at the current frame')
                return {'CANCELLED'}
            self.name = tag.name if self.action == 'EDIT' else f'Tag {len(scene.timeline_markers)+1}'
            return context.window_manager.invoke_props_dialog(self, width=260)
        return self.execute(context)

    def _at_current(self, scene):
        return next((m for m in scene.timeline_markers if m.frame == scene.frame_current), None)

    def execute(self, context):
        scene = context.scene
        if self.action == 'ADD':
            scene.timeline_markers.new(self.name or 'Tag', frame=scene.frame_current)
        elif self.action == 'EDIT':
            tag = self._at_current(scene)
            if tag is not None:
                tag.name = self.name
        elif self.action == 'DELETE':
            tag = self._at_current(scene)
            if tag is None:
                return {'CANCELLED'}
            scene.timeline_markers.remove(tag)
        else:
            scene.frame_set(self.frame)
        runtime.redraw()
        return {'FINISHED'}


class BSM_MT_time_tags(bpy.types.Menu):
    bl_label = 'Time Tags'

    def draw(self, context):
        layout, scene = self.layout, context.scene
        layout.operator('bsm.time_tag', text=_tr('Add Tag')).action = 'ADD'
        here = any(m.frame == scene.frame_current for m in scene.timeline_markers)
        for action, label in (('EDIT', 'Edit Tag...'), ('DELETE', 'Delete Tag')):
            row = layout.row()
            row.enabled = here
            row.operator('bsm.time_tag', text=_tr(label)).action = action
        if scene.timeline_markers:
            layout.separator()
        for tag in sorted(scene.timeline_markers, key=lambda m: m.frame):
            item = layout.operator('bsm.time_tag', text=f'{tag.name} ({tag.frame})')
            item.action, item.frame = 'GOTO', tag.frame


class BSM_OT_key_set(Active, bpy.types.Operator):
    bl_idname = 'bsm.key_set'
    bl_label = 'Key Selection Set'
    name: StringProperty()

    def execute(self, context):
        context.window_manager.bsm.key_set = self.name
        runtime.redraw()
        return {'FINISHED'}


class BSM_MT_key_sets(bpy.types.Menu):
    bl_label = 'Selection Sets'

    def draw(self, context):
        self.layout.operator('bsm.key_set', text=_tr('Selected')).name = ''
        for group in (c for c in bpy.data.collections if c.get('bsm_selection_set')):
            self.layout.operator('bsm.key_set', text=group.name).name = group.name


# Max's Default In/Out Tangents for New Keys, mapped to Blender's new-keyframe preferences.
TANGENTS = (('AUTO', 'Auto', 'BEZIER', 'AUTO_CLAMPED'), ('SPLINE', 'Spline', 'BEZIER', 'AUTO'),
            ('FAST', 'Fast', None, None), ('SLOW', 'Slow', None, None), ('STEP', 'Step', 'CONSTANT', None),
            ('LINEAR', 'Linear', 'LINEAR', None), ('SMOOTH', 'Smooth', 'BEZIER', 'AUTO_CLAMPED'),
            ('CUSTOM', 'Custom', 'BEZIER', 'FREE'))


def current_tangent(context):
    edit = context.preferences.edit
    for ident, label, interpolation, handles in TANGENTS:
        if interpolation == edit.keyframe_new_interpolation_type and handles in {None, edit.keyframe_new_handle_type}:
            return ident
    return 'AUTO'


class BSM_OT_default_tangent(Active, bpy.types.Operator):
    bl_idname = 'bsm.default_tangent'
    bl_label = 'Default In/Out Tangents for New Keys'
    bl_description = "Sets Blender's interpolation and handle type for new keys (Preferences > Animation)"
    tangent: EnumProperty(items=tuple((t[0], t[1], '') for t in TANGENTS))

    def execute(self, context):
        ident, label, interpolation, handles = next(t for t in TANGENTS if t[0] == self.tangent)
        if interpolation is None:
            self.report({'WARNING'}, f'{label} tangents have no Blender equivalent')
            return {'CANCELLED'}
        edit = context.preferences.edit
        edit.keyframe_new_interpolation_type = interpolation
        if handles:
            edit.keyframe_new_handle_type = handles
        runtime.redraw()
        return {'FINISHED'}


class BSM_MT_default_tangents(bpy.types.Menu):
    bl_label = 'Default In/Out Tangents'

    def draw(self, context):
        current = current_tangent(context)
        for ident, label, interpolation, handles in TANGENTS:
            row = self.layout.row()
            row.enabled = interpolation is not None
            row.operator('bsm.default_tangent', text=_tr(label), icon='RADIOBUT_ON' if ident == current else 'RADIOBUT_OFF').tangent = ident


def isolated(context):
    return any(a.type == 'VIEW_3D' and a.spaces.active.local_view is not None for a in context.screen.areas)


class BSM_OT_isolate_toggle(Active, bpy.types.Operator):
    bl_idname = 'bsm.isolate_toggle'
    bl_label = 'Isolate Selection Toggle'
    bl_description = 'Show only the selection in the active viewport, or end isolation (Alt+Q)'

    def execute(self, context):
        return bpy.ops.bsm.max_command(command='END_ISOLATE' if isolated(context) else 'ISOLATE')


class BSM_OT_auto_key_toggle(Active, bpy.types.Operator):
    bl_idname = 'bsm.auto_key_toggle'
    bl_label = 'Toggle Auto Key Mode'
    bl_description = 'Record transforms as keys while Auto Key is on (N)'

    def execute(self, context):
        settings = context.scene.tool_settings
        settings.use_keyframe_insert_auto = not settings.use_keyframe_insert_auto
        if settings.use_keyframe_insert_auto:
            context.window_manager.bsm.set_key_mode = False  # Max: Auto Key and Set Key exclude each other
        runtime.redraw()
        return {'FINISHED'}


class BSM_OT_step_frame(Active, bpy.types.Operator):
    bl_idname = 'bsm.step_frame'
    bl_label = 'Previous/Next Frame'
    bl_description = 'One frame back or forward; with Key Mode on, the previous or next key of the selection'
    direction: IntProperty(default=1)

    def execute(self, context):
        scene = context.scene
        if context.window_manager.bsm.key_mode:
            frames = sorted(track_keys(context))
            if self.direction > 0:
                target = next((f for f in frames if f > scene.frame_current), None)
            else:
                target = next((f for f in reversed(frames) if f < scene.frame_current), None)
            if target is None:
                return {'CANCELLED'}
            scene.frame_set(target)
        else:
            scene.frame_set(max(scene.frame_start, min(scene.frame_end, scene.frame_current+self.direction)))
        runtime.redraw()
        return {'FINISHED'}


class BSM_OT_view_navigation(Active, bpy.types.Operator):
    """Max viewport controls without a direct Blender operator."""
    bl_idname = 'bsm.view_navigation'
    bl_label = 'Viewport Navigation'
    kind: EnumProperty(items=(('ZOOM_ALL', 'Zoom All', 'Zoom every viewport together'),
                              ('FOV', 'Field-of-View', 'Change the perspective field of view'),
                              ('EXTENTS', 'Zoom Extents', 'Frame all objects in the active viewport'),
                              ('EXTENTS_ALL_SELECTED', 'Zoom Extents All Selected', 'Frame the selection in every viewport'),
                              ('WALK', 'Walk Through', ''), ('ORBIT_SELECTED', 'Orbit Selected', ''),
                              ('ORBIT_POINT', 'Orbit Point of Interest', '')))

    def invoke(self, context, event):
        from .commands import record_view
        override = viewport_override(context)
        record_view(context, override['area'])
        space, r3d = override['area'].spaces.active, override['region'].data
        with context.temp_override(**override):
            if self.kind == 'EXTENTS':
                bpy.ops.view3d.view_all(center=False)
            elif self.kind == 'EXTENTS_ALL_SELECTED':
                bpy.ops.view3d.view_selected(use_all_regions=True)
            elif self.kind == 'WALK':
                bpy.ops.view3d.walk('INVOKE_DEFAULT')
            elif self.kind in {'ORBIT_SELECTED', 'ORBIT_POINT'}:
                # Blender reads these orbit preferences when the orbit starts.
                inputs = context.preferences.inputs
                attr = 'use_rotate_around_active' if self.kind == 'ORBIT_SELECTED' else 'use_mouse_depth_navigate'
                before = getattr(inputs, attr)
                setattr(inputs, attr, True)
                try:
                    bpy.ops.view3d.rotate('INVOKE_DEFAULT')
                finally:
                    setattr(inputs, attr, before)
            elif self.kind == 'FOV' and r3d.view_perspective == 'ORTHO':
                bpy.ops.view3d.zoom_border('INVOKE_DEFAULT')  # Max shows Zoom Region in orthographic views
            else:
                self.views = [a.spaces.active.region_3d for a in context.screen.areas if a.type == 'VIEW_3D']
                self.views += [q for a in context.screen.areas if a.type == 'VIEW_3D' for q in a.spaces.active.region_quadviews]
                self.distances = [v.view_distance for v in self.views]
                camera = context.scene.camera if r3d.view_perspective == 'CAMERA' else None
                self.lens_owner = camera.data if camera is not None and camera.type == 'CAMERA' else space
                self.lens = self.lens_owner.lens
                self.start = None  # Max: click the button, then drag in a viewport
                context.window.cursor_modal_set('SCROLL_Y')
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.start is None:
            self.start = event.mouse_y
        elif event.type == 'MOUSEMOVE' and self.start is not None:
            factor = math.exp((event.mouse_y-self.start)*-.006)
            if self.kind == 'ZOOM_ALL':
                for view, distance in zip(self.views, self.distances):
                    view.view_distance = distance*factor
            else:
                self.lens_owner.lens = min(5000., max(1., self.lens/factor))
            runtime.redraw()
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.start is not None:
            context.window.cursor_modal_restore()
            return {'FINISHED'}
        elif event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            for view, distance in zip(self.views, self.distances):
                view.view_distance = distance
            self.lens_owner.lens = self.lens
            context.window.cursor_modal_restore()
            runtime.redraw()
            return {'CANCELLED'}
        elif event.type not in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'LEFTMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


def _flyout(name, label, items):
    """A viewport control flyout (right-click, like the main toolbar flyouts)."""
    def draw(self, context):
        for text, operator, props in items:
            button = self.layout.operator(operator, text=_tr(text))
            for key, value in props.items():
                setattr(button, key, value)
    return type(name, (bpy.types.Menu,), {'bl_label': label, 'draw': draw})


BSM_MT_extents_flyout = _flyout('BSM_MT_extents_flyout', 'Zoom Extents', (
    ('Zoom Extents Selected', 'bsm.frame_selected', {}), ('Zoom Extents', 'bsm.view_navigation', {'kind': 'EXTENTS'})))
BSM_MT_extents_all_flyout = _flyout('BSM_MT_extents_all_flyout', 'Zoom Extents All', (
    ('Zoom Extents All Selected', 'bsm.view_navigation', {'kind': 'EXTENTS_ALL_SELECTED'}),
    ('Zoom Extents All', 'bsm.navigation', {'kind': 'EXTENTS_ALL'})))
BSM_MT_fov_flyout = _flyout('BSM_MT_fov_flyout', 'Field-of-View', (
    ('Field-of-View', 'bsm.view_navigation', {'kind': 'FOV'}), ('Zoom Region', 'bsm.navigation', {'kind': 'REGION'})))
BSM_MT_pan_flyout = _flyout('BSM_MT_pan_flyout', 'Pan View', (
    ('Pan View', 'bsm.navigation', {'kind': 'PAN'}), ('Walk Through', 'bsm.view_navigation', {'kind': 'WALK'})))
BSM_MT_orbit_flyout = _flyout('BSM_MT_orbit_flyout', 'Orbit', (
    ('Orbit', 'bsm.navigation', {'kind': 'ORBIT'}), ('Orbit Selected', 'bsm.view_navigation', {'kind': 'ORBIT_SELECTED'}),
    ('Orbit Point of Interest', 'bsm.view_navigation', {'kind': 'ORBIT_POINT'})))


def safe_scene(context):
    """Max's Safe Scene Script Execution status: Blender's protection against auto-run scripts."""
    return not context.preferences.filepaths.use_scripts_auto_execute, int(bool(bpy.app.autoexec_fail))


class BSM_OT_safe_scene(Active, bpy.types.Operator):
    bl_idname = 'bsm.safe_scene'
    bl_label = 'Safe Scene Script Execution'
    bl_description = "Blender's protection against Python scripts embedded in scene files (Preferences > Save & Load)"

    def execute(self, context):
        if bpy.app.autoexec_fail:
            self.report({'WARNING'}, bpy.app.autoexec_fail_message or 'Scripts in this file were blocked')
        bpy.ops.screen.userpref_show(section='SAVE_LOAD')
        return {'FINISHED'}


CLASSES = (BSM_OT_trackbar, BSM_MT_trackbar_filter, BSM_MT_trackbar_configure, BSM_MT_trackbar, BSM_OT_create_key,
           BSM_OT_time_tag, BSM_MT_time_tags, BSM_OT_key_set, BSM_MT_key_sets, BSM_OT_default_tangent,
           BSM_MT_default_tangents, BSM_OT_view_navigation, BSM_MT_extents_flyout, BSM_MT_extents_all_flyout,
           BSM_MT_fov_flyout, BSM_MT_pan_flyout, BSM_MT_orbit_flyout, BSM_OT_safe_scene, BSM_OT_isolate_toggle,
           BSM_OT_auto_key_toggle, BSM_OT_step_frame)
