# SPDX-License-Identifier: GPL-3.0-or-later
"""Creation gestures, region selection and property popups on actual Blender data."""
from .localization import tr as _tr
import random
import bpy
import gpu
from bpy.props import EnumProperty, StringProperty
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from bpy_extras import view3d_utils
from . import operators, runtime

# Max assigns each new object a random color from a fixed set of saturated hues.
MAX_COLORS = ((.53, .89, .11), (.11, .69, .89), (.89, .11, .53), (.89, .65, .11), (.40, .11, .89), (.11, .89, .53),
              (.89, .35, .11), (.65, .11, .89), (.11, .35, .89), (.53, .11, .89), (.89, .11, .11), (.11, .89, .89))


def next_random_color(state):
    state.next_color = (*random.choice(MAX_COLORS), 1.)


def _ray(context, event):
    region = context.region
    xy = (event.mouse_x-region.x, event.mouse_y-region.y)
    return (view3d_utils.region_2d_to_origin_3d(region, context.region_data, xy),
            view3d_utils.region_2d_to_vector_3d(region, context.region_data, xy), xy)


def _plane_hit(origin, direction, point, normal):
    denominator = direction.dot(normal)
    if abs(denominator) < 1e-8:
        return None
    return origin+direction*((point-origin).dot(normal)/denominator)


def construction_plane(context, event):
    """Home grid (world XY) in perspective; the view plane in Top/Front/Left; a surface with AutoGrid."""
    r3d = context.region_data
    origin, direction, xy = _ray(context, event)
    if context.window_manager.bsm.autogrid:
        from .commands import object_under_mouse
        obj, location, normal = object_under_mouse(context, context.region, r3d, xy)
        if obj is not None and normal is not None:
            n = normal.normalized()
            u = Vector((1, 0, 0)) - n*n.x
            if u.length < 1e-3:
                u = Vector((0, 1, 0)) - n*n.y
            u.normalize()
            return location, u, n.cross(u), n
    if r3d.view_perspective == 'ORTHO' and operators.view_name(r3d) in {'Top', 'Bottom', 'Front', 'Back', 'Left', 'Right'}:
        rotation = r3d.view_rotation
        u = (rotation@Vector((1, 0, 0)))
        v = (rotation@Vector((0, 1, 0)))
        u = Vector(tuple(round(c) for c in u))
        v = Vector(tuple(round(c) for c in v))
        return Vector((0, 0, 0)), u, v, u.cross(v)
    return Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


STAGES = {'BOX': ('BASE', 'HEIGHT'), 'PYRAMID': ('BASE', 'HEIGHT'), 'PLANE': ('BASE',), 'SPHERE': ('RADIUS',),
          'GEOSPHERE': ('RADIUS',), 'TEAPOT': ('RADIUS',), 'CYLINDER': ('RADIUS', 'HEIGHT'), 'CONE': ('RADIUS', 'HEIGHT', 'RADIUS2'),
          'TUBE': ('RADIUS', 'RADIUS2', 'HEIGHT'), 'TORUS': ('RADIUS', 'RADIUS2'),
          'CHAMFER_BOX': ('BASE', 'HEIGHT'), 'CHAMFER_CYL': ('RADIUS', 'HEIGHT'), 'CAPSULE': ('RADIUS', 'HEIGHT')}
BASES = {'CHAMFER_BOX': 'BOX', 'CHAMFER_CYL': 'CYLINDER', 'CAPSULE': 'CYLINDER'}
RADIUS_ATTR = {'SPHERE': 'radius', 'GEOSPHERE': 'radius', 'TEAPOT': 'radius', 'CYLINDER': 'radius',
               'CONE': 'radius1', 'TUBE': 'radius1', 'TORUS': 'radius1'}


class BSM_OT_draw_primitive(operators.Active, bpy.types.Operator):
    bl_idname = 'bsm.draw_primitive'
    bl_label = 'Create Object'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}
    kind: StringProperty()

    def invoke(self, context, event):
        from . import surfaces
        state = context.window_manager.bsm
        self.previous = list(context.selected_objects)
        self.previous_active = context.view_layer.objects.active
        if self.previous_active and self.previous_active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.origin, self.u, self.v, self.n = construction_plane(context, event)
        ray_origin, direction, xy = _ray(context, event)
        anchor = _plane_hit(ray_origin, direction, self.origin, self.n)
        if anchor is None:
            return {'CANCELLED'}
        self.anchor = anchor
        self.start = (event.mouse_x, event.mouse_y)
        self.base = surfaces.creation_method(state, BASES.get(self.kind, self.kind))
        self.stages = STAGES.get(self.kind, ('POINT',))
        self.stage = 0
        self.basis = Matrix((self.u, self.v, self.n)).transposed().to_4x4()
        self.center = anchor.copy()
        self.obj = None
        self.dragged = False
        self.height_start = None
        try:
            self._create(context, anchor)
        except RuntimeError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        context.window_manager.bsm.prompt = 'Drag to define the base; release, then move to set the next dimension'
        return {'RUNNING_MODAL'}

    def _matrix(self, location):
        matrix = self.basis.copy()
        matrix.translation = location
        return matrix

    def _create(self, context, location):
        kind = self.kind
        if kind in BASES or kind in STAGES:
            from . import params
            base = BASES.get(kind, kind)
            values = {}
            for attr in ('length', 'width', 'height', 'depth', 'radius', 'radius1', 'radius2'):
                if attr in params.DEFAULTS[base]:
                    values[attr] = .001
            if base == 'TUBE':
                values['radius2'] = .001
            state = context.window_manager.bsm
            for attr, value in params.DEFAULTS[base].items():
                if attr not in values and hasattr(state.next_prim, attr) and state.next_prim.kind == '':
                    values[attr] = getattr(state.next_prim, attr)
            self.obj = operators.create_object(context, kind, self._matrix(location))
            prim = self.obj.bsm_prim
            for attr, value in values.items():
                setattr(prim, attr, value)
        else:
            self.obj = operators.create_object(context, kind, self._matrix(location), size=.001)
        self.obj.color = context.window_manager.bsm.next_color

    def _point(self, context, event):
        origin, direction, xy = _ray(context, event)
        return _plane_hit(origin, direction, self.origin, self.n) or self.anchor

    def _height(self, context, event):
        origin, direction, xy = _ray(context, event)
        view = context.region_data.view_rotation@Vector((0, 0, -1))
        side = view-self.n*view.dot(self.n)
        if side.length > .05:
            hit = _plane_hit(origin, direction, self.center, side.normalized())
            if hit is not None:
                return (hit-self.center).dot(self.n)
        pixels = event.mouse_y-self.height_start
        return pixels*context.region_data.view_distance/max(200, context.region.height)

    def _update(self, context, event):
        prim = getattr(self.obj, 'bsm_prim', None)
        stage = self.stages[self.stage]
        point = self._point(context, event)
        delta = point-self.anchor
        du, dv = delta.dot(self.u), delta.dot(self.v)
        kind = BASES.get(self.kind, self.kind)
        if stage == 'BASE':
            square = self.base in {'CUBE', 'SQUARE'} or (kind == 'PYRAMID' and self.base == 'CENTER')
            if square:
                size = max(abs(du), abs(dv))*2
                width = length = max(.001, size)
                self.center = self.anchor.copy()
            else:
                width, length = max(.001, abs(du)), max(.001, abs(dv))
                self.center = self.anchor+self.u*(du/2)+self.v*(dv/2)
            if kind == 'PYRAMID':
                prim.width, prim.depth = width, length
            else:
                prim.width, prim.length = width, length
            if kind == 'BOX' and self.base == 'CUBE':
                prim.height = width
            self.obj.matrix_world = self._matrix(self.center)
        elif stage == 'RADIUS':
            if self.base in {'EDGE', 'DIAMETER'}:
                self.center = (self.anchor+point)/2
                radius = delta.length/2
            else:
                self.center = self.anchor.copy()
                radius = delta.length
            if prim is not None:
                setattr(prim, RADIUS_ATTR.get(kind, 'radius'), max(.001, radius))
                if kind == 'TUBE':
                    prim.radius2 = max(.001, radius)
            self.obj.matrix_world = self._matrix(self.center)
        elif stage == 'HEIGHT':
            prim.height = self._height(context, event) or .001
            if self.kind == 'CAPSULE':
                self.obj.modifiers['Fillet'].width = min(prim.radius*.98, abs(prim.height)/2*.98)
        elif stage == 'RADIUS2':
            radius = (point-self.center).length
            if kind == 'TORUS':
                radius = abs(radius-prim.radius1)
            prim.radius2 = max(0., radius)
        elif stage == 'POINT':
            size = delta.length
            if self.kind in operators.TARGETED:
                target = next((c.target for c in self.obj.constraints if c.type == 'TRACK_TO'), None)
                if target and size > .01:
                    target.location = point
            elif self.kind in operators.SHAPES or self.kind in {'DUMMY', 'POINT', 'ARROW', 'COMPASS', 'GRID', 'TEXT', 'TEXTPLUS'}:
                self._resize(context, max(.001, size), point)

    def _resize(self, context, size, point):
        obj = self.obj
        if obj.type == 'EMPTY':
            obj.empty_display_size = size
        elif obj.type == 'FONT':
            obj.data.size = size
        elif obj.type == 'CURVE':
            old = obj.data
            if self.kind == 'RECTANGLE':
                delta = point-self.anchor
                du, dv = abs(delta.dot(self.u))/2, abs(delta.dot(self.v))/2
                obj.data = operators._poly([[(-du, -dv, 0), (du, -dv, 0), (du, dv, 0), (-du, dv, 0)]], True, old.name)
                obj.matrix_world = self._matrix((self.anchor+point)/2)
            elif self.kind == 'LINE':
                local = self.basis.to_3x3().inverted()@(point-self.anchor)
                obj.data = operators._poly([[(0, 0, 0), tuple(local)]], False, old.name)
            else:
                obj.data = operators.shape_data(self.kind, old.name, size)
            if old.users == 0:
                bpy.data.curves.remove(old)
        elif obj.type == 'MESH':
            obj.scale = (size, size, 1)

    def modal(self, context, event):
        if not runtime.is_active() or (event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS'):
            self.cancel(context)
            return {'CANCELLED'}
        if event.type == 'MOUSEMOVE':
            if abs(event.mouse_x-self.start[0])+abs(event.mouse_y-self.start[1]) > 3:
                self.dragged = True
            if self.stage < len(self.stages):
                if self.stages[self.stage] == 'HEIGHT' and self.height_start is None:
                    self.height_start = event.mouse_y
                self._update(context, event)
            runtime.redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if self.stage == 0 and event.value == 'RELEASE':
                if not self.dragged and self.stages != ('POINT',):
                    # Max needs a drag; a plain click creates nothing.
                    self.cancel(context)
                    return {'CANCELLED'}
                if self.obj.type == 'MESH' and self.stages == ('POINT',):
                    self.obj.scale = (1, 1, 1)
                self.stage += 1
                self.height_start = event.mouse_y
                if self.stage >= len(self.stages):
                    return self.finish(context)
                context.window_manager.bsm.prompt = 'Move the mouse to set the next dimension; click to finish'
            elif self.stage > 0 and event.value == 'PRESS':
                self.stage += 1
                self.height_start = event.mouse_y
                if self.stage >= len(self.stages):
                    return self.finish(context)
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def finish(self, context):
        state = context.window_manager.bsm
        state.created_this_session = self.obj.name
        state.prompt = ''
        self.obj['bsm_primitive'] = self.kind
        next_random_color(state)
        runtime.redraw()
        return {'FINISHED'}

    def cancel(self, context):
        obj = getattr(self, 'obj', None)
        if obj is not None and obj.name in bpy.data.objects:
            data = obj.data
            extra = [c.target for c in obj.constraints if c.type == 'TRACK_TO' and c.target]
            bpy.data.objects.remove(obj, do_unlink=True)
            for target in extra:
                bpy.data.objects.remove(target, do_unlink=True)
            if data is not None and data.users == 0:
                name = data.name
                for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
                    if name in collection and collection[name] == data:
                        collection.remove(data)
                        break
        for obj in self.previous:
            if obj.name in context.view_layer.objects:
                obj.select_set(True)
        if self.previous_active and self.previous_active.name in context.view_layer.objects:
            context.view_layer.objects.active = self.previous_active
        context.window_manager.bsm.prompt = ''
        runtime.redraw()


# Region selection with Max semantics: Window/Crossing, Ctrl adds, Alt removes.
_overlay = None
_shader = None


def _draw_overlay():
    global _shader
    if _overlay is None or bpy.context.region.as_pointer() != _overlay[0]:
        return
    _, kind, points = _overlay
    if len(points) < 2:
        return
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    if kind == 'RECT':
        (x0, y0), (x1, y1) = points[0], points[-1]
        outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    elif kind in {'CIRCLE', 'PAINT'}:
        from math import cos, sin, pi
        (cx, cy), (x1, y1) = points[0], points[-1]
        radius = ((x1-cx)**2+(y1-cy)**2)**.5 if kind == 'CIRCLE' else 14
        if kind == 'PAINT':
            cx, cy = points[-1]
        outline = [(cx+radius*cos(2*pi*i/48), cy+radius*sin(2*pi*i/48)) for i in range(49)]
    else:
        outline = list(points)+[points[0]]
    segments = []
    for a, b in zip(outline, outline[1:]):
        steps = max(1, int(((b[0]-a[0])**2+(b[1]-a[1])**2)**.5/4))
        for i in range(0, steps, 2):
            t0, t1 = i/steps, min(1, (i+1)/steps)
            segments += [(a[0]+(b[0]-a[0])*t0, a[1]+(b[1]-a[1])*t0), (a[0]+(b[0]-a[0])*t1, a[1]+(b[1]-a[1])*t1)]
    batch = batch_for_shader(_shader, 'LINES', {'pos': segments})
    gpu.state.blend_set('ALPHA')
    _shader.bind()
    _shader.uniform_float('color', (1, 1, 1, .9))
    batch.draw(_shader)
    gpu.state.blend_set('NONE')


def _inside_polygon(point, polygon):
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:]+polygon[:1]):
        if (y0 > y) != (y1 > y) and x < (x1-x0)*(y-y0)/(y1-y0+1e-12)+x0:
            inside = not inside
    return inside


def _pick_select(context, obj, add, subtract):
    """A click on an object: Ctrl adds it, Alt removes it, a plain click selects only it."""
    if subtract:
        obj.select_set(False)
        return
    if not add:
        for other in context.selected_objects:
            other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class BSM_OT_select_region(operators.Active, bpy.types.Operator):
    bl_idname = 'bsm.select_region'
    bl_label = 'Select Object'
    bl_options = {'REGISTER', 'UNDO'}
    add: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    subtract: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})

    _handle = None

    def invoke(self, context, event):
        region = context.region
        self.start = (event.mouse_x-region.x, event.mouse_y-region.y)
        self.points = [self.start]
        self.dragging = False
        self.ctrl, self.alt = self.add or event.ctrl, self.subtract or event.alt
        self.mode = 'ADD' if self.ctrl else ('SUB' if self.alt else 'SET')
        self.kind = context.window_manager.bsm.region_type
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _set_overlay(self, context, on):
        global _overlay
        cls = type(self)
        if on and cls._handle is None:
            cls._handle = bpy.types.SpaceView3D.draw_handler_add(_draw_overlay, (), 'WINDOW', 'POST_PIXEL')
        _overlay = (context.region.as_pointer(), self.kind, self.points) if on else None
        if not on and cls._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(cls._handle, 'WINDOW')
            cls._handle = None
        context.area.tag_redraw()

    def modal(self, context, event):
        region = context.region
        xy = (event.mouse_x-region.x, event.mouse_y-region.y)
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._set_overlay(context, False)
            return {'CANCELLED'}
        if event.type == 'MOUSEMOVE':
            if not self.dragging and abs(xy[0]-self.start[0])+abs(xy[1]-self.start[1]) > 4:
                self.dragging = True
            if self.dragging:
                if self.kind in {'LASSO', 'FENCE', 'PAINT'}:
                    self.points.append(xy)
                    if self.kind == 'PAINT':
                        self._paint(context, xy)
                else:
                    self.points[1:] = [xy]
                self._set_overlay(context, True)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._set_overlay(context, False)
            if self.dragging:
                self._region(context)
            else:
                self._click(context, self.start)
            from .commands import promote_groups
            if context.mode == 'OBJECT':
                promote_groups(context)
            runtime.redraw()
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def _click(self, context, xy):
        level = context.window_manager.bsm.component
        if context.mode == 'EDIT_MESH' and level == 3:
            bpy.ops.mesh.loop_select('INVOKE_DEFAULT', extend=self.ctrl, deselect=self.alt)
            import bmesh
            obj = context.edit_object
            bm = bmesh.from_edit_mesh(obj.data)
            for edge in bm.edges:
                if edge.select and not edge.is_boundary:
                    edge.select_set(False)
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data)
            return
        if context.mode == 'EDIT_MESH' and level == 5:
            if not self.ctrl and not self.alt:
                bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_linked_pick('INVOKE_DEFAULT', deselect=self.alt)
            return
        if context.mode == 'OBJECT':
            # Lights, cameras and empties are drawn by Blender Max (object_icons), not by
            # Blender's overlay, so Blender's click selection cannot see them.
            from . import object_icons
            obj = object_icons.pick(context, context.region, xy)
            if obj is not None:
                _pick_select(context, obj, self.ctrl, self.alt)
                return
        bpy.ops.view3d.select(extend=self.ctrl, deselect=self.alt, deselect_all=not (self.ctrl or self.alt), location=(int(xy[0]), int(xy[1])))

    def _inside(self):
        """Whether a region point lies in the dragged rectangle, circle, fence or lasso."""
        (x0, y0), (x1, y1) = self.start, self.points[-1]
        radius = ((x1-x0)**2+(y1-y0)**2)**.5

        def inside(p):
            if self.kind == 'RECT':
                return min(x0, x1) <= p[0] <= max(x0, x1) and min(y0, y1) <= p[1] <= max(y0, y1)
            if self.kind == 'CIRCLE':
                return (p[0]-x0)**2+(p[1]-y0)**2 <= radius*radius
            return _inside_polygon(p, self.points)
        return inside

    def _paint(self, context, xy):
        bpy.ops.view3d.select_circle(x=int(xy[0]), y=int(xy[1]), radius=14, wait_for_input=False,
                                     mode='SUB' if self.alt else 'ADD')

    def _region(self, context):
        state = context.window_manager.bsm
        if self.kind == 'PAINT':
            return
        window = state.window_selection and context.mode == 'OBJECT'
        if not window:
            if self.kind == 'RECT':
                (x0, y0), (x1, y1) = self.start, self.points[-1]
                bpy.ops.view3d.select_box(xmin=int(min(x0, x1)), xmax=int(max(x0, x1)), ymin=int(min(y0, y1)), ymax=int(max(y0, y1)),
                                          wait_for_input=False, mode=self.mode)
            elif self.kind == 'CIRCLE':
                (cx, cy), (x1, y1) = self.start, self.points[-1]
                if self.mode == 'SET':
                    bpy.ops.object.select_all(action='DESELECT') if context.mode == 'OBJECT' else bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.view3d.select_circle(x=int(cx), y=int(cy), radius=int(((x1-cx)**2+(y1-cy)**2)**.5), wait_for_input=False,
                                             mode='SUB' if self.mode == 'SUB' else 'ADD')
            else:
                path = [{'name': '', 'loc': (float(x), float(y)), 'time': 0.} for x, y in self.points]
                bpy.ops.view3d.select_lasso(path=path, mode=self.mode)
            if context.mode == 'OBJECT':
                # Crossing: Blender's region selection cannot see the icons Blender Max draws.
                from . import object_icons
                for obj in object_icons.inside(context, context.region, self._inside()):
                    obj.select_set(self.mode != 'SUB')
                chosen = [o for o in context.visible_objects if o.select_get()]
                if chosen and context.view_layer.objects.active not in chosen:
                    context.view_layer.objects.active = chosen[0]
            return
        region, r3d = context.region, context.region_data
        inside = self._inside()
        for obj in context.visible_objects:
            if obj.hide_select:
                continue
            corners = [obj.matrix_world@Vector(c) for c in obj.bound_box] if obj.type not in {'EMPTY', 'LIGHT', 'CAMERA'} else [obj.matrix_world.translation]
            projected = [view3d_utils.location_3d_to_region_2d(region, r3d, c) for c in corners]
            enclosed = all(p is not None and inside(p) for p in projected)
            if self.mode == 'SET':
                obj.select_set(enclosed)
            elif enclosed:
                obj.select_set(self.mode == 'ADD')
        chosen = [o for o in context.visible_objects if o.select_get()]
        if chosen and context.view_layer.objects.active not in chosen:
            context.view_layer.objects.active = chosen[0]


class BSM_OT_surface_color(operators.Active, bpy.types.Operator):
    bl_idname = 'bsm.surface_color'
    bl_label = 'Object Color'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=240)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        obj = context.view_layer.objects.active
        state = context.window_manager.bsm
        self.layout.label(text=_tr('Object Color'))
        if obj and obj.type == 'LIGHT':
            self.layout.prop(obj.data, 'color', text=_tr(''))
        self.layout.prop(obj if obj else state, 'color' if obj else 'next_color', text=_tr(''))
        self.layout.prop(state, 'next_color', text=_tr('Next new object'))


class BSM_OT_surface_properties(operators.Active, bpy.types.Operator):
    bl_idname = 'bsm.surface_properties'
    bl_label = 'Modifier Parameters'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=360)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        obj = context.view_layer.objects.active
        mod = obj.modifiers.get(context.window_manager.bsm.active_modifier) if obj else None
        if mod is None:
            self.layout.label(text=_tr('Select a modifier in the stack'))
            return
        self.layout.label(text=mod.name)
        for p in mod.bl_rna.properties:
            if p.identifier not in {'rna_type', 'name', 'type', 'is_override_data_editable', 'persistent_uid', 'is_active', 'use_pin_to_last'} and not p.is_readonly:
                self.layout.prop(mod, p.identifier)


class BSM_OT_navigation(operators.Active, bpy.types.Operator):
    bl_idname = 'bsm.navigation'
    bl_label = 'Navigate Viewport'
    kind: EnumProperty(items=(('PAN', 'Pan View', ''), ('ORBIT', 'Orbit', ''), ('ZOOM', 'Zoom', ''), ('ZOOM_ALL', 'Zoom All', ''),
                              ('EXTENTS_ALL', 'Zoom Extents All', ''), ('REGION', 'Zoom Region', '')))

    def execute(self, context):
        from .commands import record_view
        override = operators.viewport_override(context)
        record_view(context, override['area'])
        with context.temp_override(**override):
            if self.kind == 'PAN':
                bpy.ops.view3d.move('INVOKE_DEFAULT')
            elif self.kind == 'ORBIT':
                bpy.ops.view3d.rotate('INVOKE_DEFAULT')
            elif self.kind in {'ZOOM', 'ZOOM_ALL'}:
                bpy.ops.view3d.zoom('INVOKE_DEFAULT')
            elif self.kind == 'EXTENTS_ALL':
                bpy.ops.view3d.view_all(use_all_regions=True, center=False)
            else:
                bpy.ops.view3d.zoom_border('INVOKE_DEFAULT')
        return {'FINISHED'}


class BSM_OT_place_surface(operators.Active, bpy.types.Operator):
    bl_idname = 'bsm.place_surface'
    bl_label = 'Select and Place'
    bl_description = 'Place selected objects on another visible mesh, aligned to its surface'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        return runtime.is_active() and bool(context.selected_objects) and context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            with context.temp_override(**operators.viewport_override(context)):
                bpy.ops.bsm.place_surface('INVOKE_DEFAULT')
            return {'FINISHED'}
        self.original = {obj: obj.matrix_world.copy() for obj in context.selected_objects if obj.is_editable}
        self.active = context.view_layer.objects.active
        if self.active not in self.original:
            self.active = next(iter(self.original), None)
        if self.active is None:
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        context.window_manager.bsm.pick_mode = 'PLACE'
        context.area.header_text_set('Place on a visible surface. Click to finish; Esc or right-click restores the original transform.')
        return {'RUNNING_MODAL'}

    def _end(self, context):
        context.window_manager.bsm.pick_mode = ''
        context.area.header_text_set(None)
        runtime.redraw()

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} or not runtime.is_active():
            for obj, matrix in self.original.items():
                try:
                    obj.matrix_world = matrix
                except ReferenceError:
                    pass
            self._end(context)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._end(context)
            return {'FINISHED'}
        if event.type == 'MOUSEMOVE':
            region = context.region
            xy = (event.mouse_x-region.x, event.mouse_y-region.y)
            if not (0 <= xy[0] < region.width and 0 <= xy[1] < region.height):
                return {'RUNNING_MODAL'}
            origin = view3d_utils.region_2d_to_origin_3d(region, context.region_data, xy)
            direction = view3d_utils.region_2d_to_vector_3d(region, context.region_data, xy)
            depsgraph = context.evaluated_depsgraph_get()
            nearest = None
            for obj in context.visible_objects:
                if obj in self.original or obj.type != 'MESH':
                    continue
                evaluated = obj.evaluated_get(depsgraph)
                inverse = obj.matrix_world.inverted_safe()
                hit, point, normal, _ = evaluated.ray_cast(inverse@origin, (inverse.to_3x3()@direction).normalized())
                if not hit:
                    continue
                world = obj.matrix_world@point
                distance = (world-origin).length
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, world, (inverse.transposed().to_3x3()@normal).normalized())
            if nearest:
                _, point, normal = nearest
                active_matrix = self.original[self.active]
                rotation = normal.to_track_quat('Z', 'Y')@active_matrix.to_quaternion().inverted()
                for obj, matrix in self.original.items():
                    transformed = rotation.to_matrix().to_4x4()@matrix
                    transformed.translation = point+rotation@(matrix.translation-active_matrix.translation)
                    obj.matrix_world = transformed
                runtime.redraw()
        return {'RUNNING_MODAL'}


class BSM_MT_orientation(bpy.types.Menu):
    bl_label = 'Reference Coordinate System'

    def draw(self, context):
        self.layout.menu('BSM_MT_ref_coord')


class BSM_MT_pivot(bpy.types.Menu):
    bl_label = 'Transform Center'

    def draw(self, context):
        self.layout.prop(context.scene.tool_settings, 'transform_pivot_point', expand=True)


class BSM_MT_snap(bpy.types.Menu):
    bl_label = 'Grid and Snap Settings'

    def draw(self, context):
        ts = context.scene.tool_settings
        self.layout.prop(ts, 'snap_elements', expand=True)
        self.layout.prop(ts, 'use_snap_rotate')
        self.layout.prop(ts, 'use_snap_scale')


class BSM_MT_categories(bpy.types.Menu):
    bl_label = 'Object Categories'

    def draw(self, context):
        self.layout.prop(context.window_manager.bsm, 'category', expand=True)


CLASSES = (BSM_OT_draw_primitive, BSM_OT_select_region, BSM_OT_surface_color, BSM_OT_surface_properties,
           BSM_MT_orientation, BSM_MT_pivot, BSM_MT_snap, BSM_MT_categories, BSM_OT_navigation, BSM_OT_place_surface)
