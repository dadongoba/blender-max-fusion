# SPDX-License-Identifier: GPL-3.0-or-later
"""3ds Max transform gizmos for Select and Move, Rotate and Scale in Object mode.

The gizmos are drawn in screen space at Max's fixed on-screen size, in the reference
coordinate system's orientation, with DefaultUI.clrx colours: Transform Gizmo X/Y/Z,
Active Transform Gizmo (yellow), Rotation Gizmo Contour and Screen Space Gizmo.
Hovering a handle turns it yellow; the last handle used stays yellow and is the axis
constraint for dragging the object itself, as in Max. Dragging a handle runs Blender's
own Move, Rotate, Trackball or Scale with the matching axis or plane constraint.
"""
from .localization import tr as _tr
import math

from .localization import blf
import bpy
import gpu
from bpy.props import StringProperty
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_line_plane

from . import runtime

# DefaultUI.clrx, Gizmos category.
AXIS_COLORS = ((.784, 0., 0.), (0., .612, 0.), (0., 0., .765))
ACTIVE = (1., 1., 0.)
CONTOUR = (.388, .388, .388)
SCREEN = (.667, .667, .667)
INACTIVE_AXIS = (.4, .4, .4)
# On-screen sizes in layout units (surfaces.scale()), measured on Max 2027.
MOVE_LENGTH, ROTATE_RADIUS, ROTATE_SCREEN, SCALE_LENGTH = 88., 59., 79., 87.
MOVE_PLANE = .36  # plane corner size, a fraction of the move axis
PICK = 6.  # handle pick distance
TOOLS = {'bsm.max_move': 'MOVE', 'bsm.max_rotate': 'ROTATE', 'bsm.max_scale': 'SCALE'}
BLENDER_TOOLS = {'bsm.max_move': 'builtin.move', 'bsm.max_rotate': 'builtin.rotate', 'bsm.max_scale': 'builtin.scale'}
AXES = {'X': (0,), 'Y': (1,), 'Z': (2,), 'XY': (0, 1), 'YZ': (1, 2), 'ZX': (2, 0), 'XYZ': (0, 1, 2)}
PAIRS = ((0, 1, 'XY'), (1, 2, 'YZ'), (2, 0, 'ZX'))
LABELS = ('x', 'y', 'Z')  # Max's gizmo labels

active = {'MOVE': 'XY', 'ROTATE': 'Z', 'SCALE': 'XYZ'}  # last handle used, drawn yellow
PLANE_CYCLE = ('XY', 'YZ', 'ZX')
SIZE_STEP, SIZE_LIMITS = 1.1, (.3, 4.)
size = 1.  # Transform Gizmo Size Down/Up (- and =)
_hover = {}  # region pointer -> handle under the mouse


def set_constraint(axis):
    """F5, F6, F7 (X, Y, Z) and F8 (plane cycle): Max's axis constraints, shared by the
    Move, Rotate and Scale gizmos and used when the object itself is dragged."""
    if axis == 'PLANE':
        current = active['MOVE']
        plane = PLANE_CYCLE[(PLANE_CYCLE.index(current)+1) % 3] if current in PLANE_CYCLE else PLANE_CYCLE[0]
        active['MOVE'] = active['SCALE'] = plane
    else:
        active['MOVE'] = active['ROTATE'] = active['SCALE'] = axis


def resize_gizmo(direction):
    global size
    size = min(SIZE_LIMITS[1], max(SIZE_LIMITS[0], size*SIZE_STEP**direction))
_draw_handle = None
_tool_registered = False


def _ui_scale():
    from .surfaces import scale
    return scale()


def kind(context):
    """MOVE, ROTATE or SCALE while a Max transform tool is active in Object mode."""
    if not runtime.is_active() or context.mode != 'OBJECT' or context.workspace is None:
        return None
    tool = context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
    return TOOLS.get(tool.idname) if tool else None


def _pivot(context, objects):
    pivot = context.scene.tool_settings.transform_pivot_point
    active_obj = context.view_layer.objects.active
    if pivot == 'CURSOR':
        return context.scene.cursor.location.copy()
    if pivot in {'ACTIVE_ELEMENT', 'INDIVIDUAL_ORIGINS'} and active_obj in objects:
        return active_obj.matrix_world.translation.copy()
    points = [o.matrix_world.translation for o in objects]
    if pivot == 'BOUNDING_BOX_CENTER':
        return Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
    return sum(points, Vector())/len(points)


def _basis(context, r3d):
    """Gizmo axes in the reference coordinate system (Blender's transform orientation)."""
    slot = context.scene.transform_orientation_slots[0]
    active_obj = context.view_layer.objects.active
    if slot.custom_orientation:
        return slot.custom_orientation.matrix.copy()
    if slot.type in {'LOCAL', 'NORMAL', 'GIMBAL'} and active_obj is not None:
        return active_obj.matrix_world.to_quaternion().to_matrix()
    if slot.type == 'VIEW':
        return r3d.view_rotation.to_matrix()
    if slot.type == 'CURSOR':
        return context.scene.cursor.matrix.to_3x3().normalized()
    if slot.type == 'PARENT' and active_obj is not None and active_obj.parent is not None:
        return active_obj.parent.matrix_world.to_quaternion().to_matrix()
    return Matrix.Identity(3)


def frame(context, region):
    """Pivot, axes and screen scale of the gizmo in this region, or None."""
    r3d = region.data
    if r3d is None:
        return None
    objects = [o for o in context.selected_objects if o.visible_get()]
    if not objects:
        return None
    center = _pivot(context, objects)
    p = location_3d_to_region_2d(region, r3d, center)
    if p is None:
        return None
    side = location_3d_to_region_2d(region, r3d, center+r3d.view_rotation@Vector((1, 0, 0)))
    if side is None or (side-p).length < 1e-6:
        return None
    basis = _basis(context, r3d)
    if r3d.is_perspective:
        to_eye = (r3d.view_matrix.inverted().translation-center).normalized()
    else:
        to_eye = r3d.view_rotation@Vector((0, 0, 1))
    return dict(center=center, axes=[basis.col[i].normalized() for i in range(3)], p=p,
                world_per_px=1/(side-p).length, to_eye=to_eye, region=region, r3d=r3d, u=_ui_scale()*size)


def _proj(f, point):
    return location_3d_to_region_2d(f['region'], f['r3d'], point)


def _world(f, length):
    """World length of an on-screen length (layout units) at the pivot."""
    return length*f['u']*f['world_per_px']


# Drawing --------------------------------------------------------------------------------
_shaders = {}


def _shader(name):
    if name not in _shaders:
        _shaders[name] = gpu.shader.from_builtin(name)
    return _shaders[name]


def _lines(points, color, width, closed=False, alpha=1.):
    points = [p for p in points if p is not None]
    if len(points) < 2:
        return
    if closed:
        points = points+[points[0]]
    shader = _shader('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_STRIP', {'pos': [(p.x, p.y, 0) for p in points]})
    shader.bind()
    shader.uniform_float('viewportSize', gpu.state.viewport_get()[2:])
    shader.uniform_float('lineWidth', width)
    shader.uniform_float('color', (*color, alpha))
    batch.draw(shader)


def _fill(points, color, alpha=1.):
    points = [p for p in points if p is not None]
    if len(points) < 3:
        return
    shader = _shader('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRI_FAN', {'pos': [(p.x, p.y) for p in points]})
    shader.bind()
    shader.uniform_float('color', (*color, alpha))
    batch.draw(shader)


def _label(text, point, color, size):
    if point is None:
        return
    from .surfaces import font
    fid = font(True)
    blf.size(fid, size)
    w, h = blf.dimensions(fid, text)
    blf.position(fid, point.x-w/2, point.y-h/2, 0)
    blf.color(fid, *color, 1.)
    blf.draw(fid, text)


def _circle2d(center, radius, steps=72):
    return [center+Vector((radius*math.cos(i*2*math.pi/steps), radius*math.sin(i*2*math.pi/steps))) for i in range(steps)]


def _hull(points):
    points = sorted(set((round(p.x, 3), round(p.y, 3)) for p in points if p is not None))
    if len(points) < 3:
        return [Vector(p) for p in points]

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [Vector(p) for p in lower[:-1]+upper[:-1]]


def _perpendiculars(d):
    other = Vector((0, 0, 1)) if abs(d.z) < .9 else Vector((1, 0, 0))
    e1 = d.cross(other).normalized()
    return e1, d.cross(e1).normalized()


def _cone(f, base, tip, radius, color):
    """A shaded Max arrowhead: the cone's silhouette, and its darker base when it faces the eye."""
    d = (tip-base).normalized()
    e1, e2 = _perpendiculars(d)
    rim = [base+radius*(math.cos(a)*e1+math.sin(a)*e2) for a in (i*2*math.pi/16 for i in range(16))]
    hull = _hull([_proj(f, p) for p in rim]+[_proj(f, tip)])
    _fill(hull, color)
    if d.dot(f['to_eye']) < 0:
        _fill([_proj(f, p) for p in rim], tuple(c*.35 for c in color))
    _lines(hull, tuple(c*.7 for c in color), 1., closed=True)


def _color(index, lit):
    return ACTIVE if lit else AXIS_COLORS[index]


def _shown(kind_, hover):
    """The handle drawn yellow: the one under the mouse, else the last one used."""
    return hover if hover else active[kind_]


def draw_move(f, hover):
    u, c, axes = f['u'], f['center'], f['axes']
    shown = _shown('MOVE', hover)
    lit_axes = set(AXES.get(shown, ())) if shown != 'XYZ' else set()
    length = _world(f, MOVE_LENGTH)
    width = max(1., 1.25*u)
    s = MOVE_PLANE*length
    # Plane corners: each half takes the colour of the axis it leaves from.
    for a, b, plane in PAIRS:
        corner = c+s*axes[a]+s*axes[b]
        lit = shown == plane
        if hover == plane:
            _fill([_proj(f, c), _proj(f, c+s*axes[a]), _proj(f, corner), _proj(f, c+s*axes[b])], ACTIVE, .3)
        _lines([_proj(f, c+s*axes[a]), _proj(f, corner)], _color(a, lit), width)
        _lines([_proj(f, c+s*axes[b]), _proj(f, corner)], _color(b, lit), width)
    for i, d in enumerate(axes):
        lit = i in lit_axes
        _lines([_proj(f, c), _proj(f, c+.72*length*d)], _color(i, lit), width)
        _cone(f, c+.7*length*d, c+length*d, .055*length, AXIS_COLORS[i])
        _label(LABELS[i], _proj(f, c+1.12*length*d), _color(i, lit), 7.5*u)
    half, p = 5.5*u, f['p']
    _lines([p+Vector((-half, -half)), p+Vector((half, -half)), p+Vector((half, half)), p+Vector((-half, half))],
           ACTIVE if hover == 'VIEW' else SCREEN, max(1., u), closed=True)


def _ring(f, normal_index, radius):
    """The eye-facing half of the ring around one axis, as runs of screen points."""
    c, axes = f['center'], f['axes']
    e1, e2 = axes[(normal_index+1) % 3], axes[(normal_index+2) % 3]
    runs, run = [], []
    for i in range(97):
        t = i*2*math.pi/96
        offset = radius*(math.cos(t)*e1+math.sin(t)*e2)
        point = _proj(f, c+offset) if offset.normalized().dot(f['to_eye']) >= -.02 else None
        if point is not None:
            run.append(point)
            continue
        if len(run) > 1:
            runs.append(run)
        run = []
    if len(run) > 1:
        runs.append(run)
    return runs


def draw_rotate(f, hover):
    u, p = f['u'], f['p']
    shown = _shown('ROTATE', hover)
    width = max(1., 1.3*u)
    if hover == 'FREE':
        _fill(_circle2d(p, ROTATE_RADIUS*u), ACTIVE, .12)
    _lines(_circle2d(p, ROTATE_RADIUS*u), CONTOUR, width, closed=True)
    _lines(_circle2d(p, ROTATE_SCREEN*u), ACTIVE if hover == 'VIEW' else SCREEN, width, closed=True)
    radius = _world(f, ROTATE_RADIUS)
    for i in range(3):
        for run in _ring(f, i, radius):
            _lines(run, _color(i, shown == 'XYZ'[i]), max(1., 1.6*u))
    # The small axis tripod at the centre: the active axis keeps its colour, the others are grey.
    for i, d in enumerate(f['axes']):
        color = AXIS_COLORS[i] if shown == 'XYZ'[i] else INACTIVE_AXIS
        _lines([p, _proj(f, f['center']+.22*radius*d)], color, max(1., u))
        _label(LABELS[i], _proj(f, f['center']+.34*radius*d), color, 7.5*u)


def _facing(f):
    """Max turns the scale gizmo's triangle toward the viewer: each axis points to the eye's side."""
    return [d if d.dot(f['to_eye']) >= 0 else -d for d in f['axes']]


def _scale_points(f):
    c, axes = f['center'], _facing(f)
    length = _world(f, SCALE_LENGTH)
    return length, [c+.48*length*d for d in axes], [c+.66*length*d for d in axes]


def draw_scale(f, hover):
    u, c, axes = f['u'], f['center'], _facing(f)
    shown = _shown('SCALE', hover)
    width = max(1., 1.25*u)
    length, inner, outer = _scale_points(f)
    uniform = shown == 'XYZ'
    if uniform:
        _fill([_proj(f, p) for p in inner], ACTIVE, .42 if hover == 'XYZ' else .32)
    for a, b, plane in PAIRS:
        lit = uniform or shown == plane
        if shown == plane:
            _fill([_proj(f, inner[a]), _proj(f, outer[a]), _proj(f, outer[b]), _proj(f, inner[b])], ACTIVE,
                  .32 if hover == plane else .22)
        for ring in (inner, outer):
            middle = (ring[a]+ring[b])/2
            _lines([_proj(f, ring[a]), _proj(f, middle)], _color(a, lit), width)
            _lines([_proj(f, middle), _proj(f, ring[b])], _color(b, lit), width)
    lit_axes = set(AXES.get(shown, ()))
    for i, d in enumerate(axes):
        _lines([_proj(f, c), _proj(f, inner[i])], _color(i, uniform), width)
        _lines([_proj(f, outer[i]), _proj(f, c+.92*length*d)], _color(i, shown == 'XYZ'[i]), width)
        _label(LABELS[i], _proj(f, c+length*d), ACTIVE if i in lit_axes else AXIS_COLORS[i], 7.5*u)


def draw():
    context = bpy.context
    kind_ = kind(context)
    space, region = context.space_data, context.region
    if kind_ is None or region is None or region.type != 'WINDOW' or not getattr(space, 'show_gizmo', True):
        return
    f = frame(context, region)
    if f is None:
        return
    gpu.state.blend_set('ALPHA')
    {'MOVE': draw_move, 'ROTATE': draw_rotate, 'SCALE': draw_scale}[kind_](f, _hover.get(region.as_pointer()))
    gpu.state.blend_set('NONE')


# Picking --------------------------------------------------------------------------------
def _segment_distance(m, a, b):
    if a is None or b is None:
        return math.inf
    ab = b-a
    t = 0. if ab.length_squared < 1e-9 else max(0., min(1., (m-a).dot(ab)/ab.length_squared))
    return (m-(a+t*ab)).length


def _inside(m, polygon):
    polygon = [p for p in polygon if p is not None]
    if len(polygon) < 3:
        return False
    inside = False
    for i, a in enumerate(polygon):
        b = polygon[i-1]
        if (a.y > m.y) != (b.y > m.y) and m.x < (b.x-a.x)*(m.y-a.y)/((b.y-a.y) or 1e-9)+a.x:
            inside = not inside
    return inside


def pick(context, region, x, y):
    """The handle under a region point: X/Y/Z, XY/YZ/ZX, XYZ, VIEW or FREE, else None."""
    kind_ = kind(context)
    f = frame(context, region) if kind_ else None
    if f is None:
        return None
    m, u, c, axes = Vector((x, y)), f['u'], f['center'], f['axes']
    near = PICK*u
    if kind_ == 'MOVE':
        if (m-f['p']).length <= 8*u:
            return 'VIEW'
        length = _world(f, MOVE_LENGTH)
        distance, axis = min((_segment_distance(m, _proj(f, c+MOVE_PLANE*length*d), _proj(f, c+1.05*length*d)), 'XYZ'[i])
                             for i, d in enumerate(axes))
        if distance <= near:
            return axis
        s = MOVE_PLANE*length
        for a, b, plane in PAIRS:
            if _inside(m, [_proj(f, c), _proj(f, c+s*axes[a]), _proj(f, c+s*axes[a]+s*axes[b]), _proj(f, c+s*axes[b])]):
                return plane
        return None
    if kind_ == 'ROTATE':
        radius = _world(f, ROTATE_RADIUS)
        best = (math.inf, None)
        for i in range(3):
            for run in _ring(f, i, radius):
                for a, b in zip(run, run[1:]):
                    best = min(best, (_segment_distance(m, a, b), 'XYZ'[i]))
        if best[0] <= near:
            return best[1]
        distance = (m-f['p']).length
        if abs(distance-ROTATE_SCREEN*u) <= near:
            return 'VIEW'
        return 'FREE' if distance < ROTATE_RADIUS*u else None
    length, inner, outer = _scale_points(f)
    axes = _facing(f)
    if _inside(m, [_proj(f, p) for p in inner]):
        return 'XYZ'
    for a, b, plane in PAIRS:
        if _inside(m, [_proj(f, inner[a]), _proj(f, outer[a]), _proj(f, outer[b]), _proj(f, inner[b])]):
            return plane
    distance, axis = min((_segment_distance(m, _proj(f, outer[i]), _proj(f, c+1.02*length*d)), 'XYZ'[i])
                         for i, d in enumerate(axes))
    return axis if distance <= near else None


def hover(context, area, region, x, y):
    part = pick(context, region, x, y)
    key = region.as_pointer()
    if _hover.get(key) != part:
        _hover[key] = part
        area.tag_redraw()


# Interaction ----------------------------------------------------------------------------
def transform(context, kind_, part):
    """Blender's own transform with the handle's axis or plane constraint, following the mouse."""
    orient = context.scene.transform_orientation_slots[0].type
    axes = AXES.get(part, ())
    constraint = tuple(i in axes for i in range(3))
    if kind_ == 'MOVE':
        if part == 'VIEW' or part == 'XYZ' or not axes:
            return bpy.ops.transform.translate('INVOKE_DEFAULT', release_confirm=True)
        return bpy.ops.transform.translate('INVOKE_DEFAULT', constraint_axis=constraint, orient_type=orient, release_confirm=True)
    if kind_ == 'ROTATE':
        if part == 'FREE':
            return bpy.ops.transform.trackball('INVOKE_DEFAULT', release_confirm=True)
        if part not in {'X', 'Y', 'Z'}:
            return bpy.ops.transform.rotate('INVOKE_DEFAULT', orient_axis='Z', orient_type='VIEW', release_confirm=True)
        return bpy.ops.transform.rotate('INVOKE_DEFAULT', orient_axis=part, constraint_axis=constraint, orient_type=orient,
                                        release_confirm=True)
    return bpy.ops.bsm.max_scale('INVOKE_DEFAULT', part=part if axes else 'XYZ')


# Measured on Max 2027 (screen pixels): the uniform centre scales 1% per pixel of vertical
# mouse motion and ignores horizontal motion; an axis or plane handle follows the mouse on
# its plane and doubles at 100 px of travel at the pivot. Shrinking is the reciprocal of
# growing, so a drag never flattens or flips the object.
SCALE_PER_PIXEL = .01
SCALE_REFERENCE = 100.


def _scale_factor(amount):
    return 1+amount if amount >= 0 else 1/(1-amount)


class BSM_OT_max_scale(bpy.types.Operator):
    """Scale the selection like 3ds Max's Select and Scale: steady, pixel-based response
    instead of Blender's ratio to the distance from the pivot"""
    bl_idname = 'bsm.max_scale'
    bl_label = 'Select and Scale'
    bl_options = {'UNDO', 'BLOCKING'}

    part: StringProperty(default='XYZ', options={'SKIP_SAVE'})

    def invoke(self, context, event):
        region = context.region
        f = frame(context, region) if region is not None and context.area.type == 'VIEW_3D' else None
        objects = [o for o in context.selected_editable_objects if o.visible_get()]
        if f is None or not objects:
            return {'CANCELLED'}
        self.saved = [(o, o.location.copy(), o.scale.copy(), o.rotation_euler.copy(),
                       o.rotation_quaternion.copy(), tuple(o.rotation_axis_angle)) for o in objects]
        self.origin = (region.x, region.y)
        self.start = Vector((event.mouse_x-region.x, event.mouse_y-region.y))
        ids = AXES.get(self.part, (0, 1, 2))
        self.ids = ids if len(ids) < 3 else ()
        self.directions = [_facing(f)[i] for i in self.ids]
        self.unit = SCALE_REFERENCE*f['world_per_px']
        self.center = f['center']
        self.normal = None
        if self.ids:
            view = f['r3d'].view_rotation@Vector((0, 0, -1))
            if len(self.ids) == 1:
                others = [f['axes'][j] for j in range(3) if j != self.ids[0]]
                self.normal = max(others, key=lambda n: abs(n.dot(view)))
            else:
                self.normal = f['axes'][self.ids[0]].cross(f['axes'][self.ids[1]])
            if abs(self.normal.dot(view)) < .05:
                self.normal = None  # edge-on plane: follow the handle's screen direction
            self.hit_start = self._hit(region, self.start)
            tips = [_proj(f, self.center+d*self.unit) for d in self.directions]
            self.screen_directions = [(t-f['p']).normalized() for t in tips if t is not None and (t-f['p']).length > 1e-3]
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _hit(self, region, point):
        if self.normal is None:
            return None
        origin = region_2d_to_origin_3d(region, region.data, point)
        return intersect_line_plane(origin, origin+region_2d_to_vector_3d(region, region.data, point),
                                    self.center, self.normal)

    def _amount(self, context, point):
        if not self.ids:
            return (point.y-self.start.y)*SCALE_PER_PIXEL
        region = context.region
        hit = self._hit(region, point)
        if hit is not None and self.hit_start is not None:
            move = hit-self.hit_start
            return sum(move.dot(d) for d in self.directions)/len(self.directions)/self.unit
        # No usable plane: project the mouse motion on the handles' screen directions.
        move = point-self.start
        return sum(move.dot(d) for d in self.screen_directions)*SCALE_PER_PIXEL/len(self.directions)

    def _restore(self):
        for obj, location, scale, euler, quaternion, axis_angle in self.saved:
            obj.location, obj.scale = location, scale
            obj.rotation_euler, obj.rotation_quaternion, obj.rotation_axis_angle = euler, quaternion, axis_angle

    def _apply(self, context, amount):
        self._restore()
        factor = _scale_factor(amount)
        if abs(factor-1) < 1e-6:
            return
        if not self.ids:
            bpy.ops.transform.resize('EXEC_DEFAULT', False, value=(factor,)*3)
            return
        value = tuple(factor if i in self.ids else 1. for i in range(3))
        constraint = tuple(i in self.ids for i in range(3))
        bpy.ops.transform.resize('EXEC_DEFAULT', False, value=value, constraint_axis=constraint,
                                 orient_type=context.scene.transform_orientation_slots[0].type)

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            point = Vector((event.mouse_x-self.origin[0], event.mouse_y-self.origin[1]))
            self._apply(context, self._amount(context, point))
            return {'RUNNING_MODAL'}
        if (event.type == 'LEFTMOUSE' and event.value == 'RELEASE') or event.type in {'RET', 'NUMPAD_ENTER'}:
            return {'FINISHED'}
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._restore()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


def press(context, event, area, region, x, y):
    """Max Select and Move/Rotate/Scale: a handle transforms with its constraint; the object
    itself selects and transforms with the active (yellow) constraint; empty space selects
    with a region. Returns a modal result, or None when no Max transform tool is active."""
    kind_ = kind(context)
    if kind_ is None:
        return None
    override = dict(window=context.window, area=area, region=region)
    part = pick(context, region, x, y)
    if part is not None:
        if part in AXES:
            active[kind_] = part
        with context.temp_override(**override):
            transform(context, kind_, part)
        return {'RUNNING_MODAL'}
    from .commands import object_under_mouse
    hit = object_under_mouse(context, region, region.data, (x, y))
    obj = hit[0] if hit else None
    if obj is None or obj.hide_select or event.ctrl or event.alt:
        with context.temp_override(**override):
            bpy.ops.bsm.select_region('INVOKE_DEFAULT', add=event.ctrl, subtract=event.alt)
        return {'RUNNING_MODAL'}
    if not obj.select_get():
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
    context.view_layer.objects.active = obj
    with context.temp_override(**override):
        transform(context, kind_, active[kind_])
    return {'RUNNING_MODAL'}


# Tools ----------------------------------------------------------------------------------
_select = (("view3d.select", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {"properties": [("deselect_all", True)]}),)


class BSM_WST_max_move(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'bsm.max_move'
    bl_label = 'Select and Move'
    bl_description = 'Move with the 3ds Max move gizmo: axis arrows, plane corners and the view-plane square'
    bl_icon = 'ops.transform.translate'
    bl_keymap = _select


class BSM_WST_max_rotate(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'bsm.max_rotate'
    bl_label = 'Select and Rotate'
    bl_description = 'Rotate with the 3ds Max rotate gizmo: axis rings, the view ring and free rotation inside'
    bl_icon = 'ops.transform.rotate'
    bl_keymap = _select


class BSM_WST_max_scale(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'bsm.max_scale'
    bl_label = 'Select and Uniform Scale'
    bl_description = 'Scale with the 3ds Max scale gizmo: uniform centre, plane bands and axes'
    bl_icon = 'ops.transform.resize'
    bl_keymap = _select


WORKSPACE_TOOLS = (BSM_WST_max_move, BSM_WST_max_rotate, BSM_WST_max_scale)
CLASSES = (BSM_OT_max_scale,)


def register_tool():
    global _draw_handle, _tool_registered
    if not _tool_registered:
        previous = 'builtin.move'
        for tool in WORKSPACE_TOOLS:
            bpy.utils.register_tool(tool, after={previous})
            previous = tool.bl_idname
        _tool_registered = True
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')


def unregister_tool():
    """Safe to call when registration stopped part way: register() calls it on failure."""
    global _draw_handle, _tool_registered
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None
    if _tool_registered:
        for tool in reversed(WORKSPACE_TOOLS):
            try:
                bpy.utils.unregister_tool(tool)
            except (RuntimeError, ValueError, AttributeError):
                pass
        _tool_registered = False
    _hover.clear()


def restore_blender_tools(context):
    """Leaving Max mode: Blender's own Move, Rotate and Scale replace the Max tools,
    whose gizmos are Studio-only."""
    for window in context.window_manager.windows:
        tool = window.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
        area = next((a for a in window.screen.areas if a.type == 'VIEW_3D'), None)
        if tool is not None and tool.idname in BLENDER_TOOLS and area is not None:
            region = next(r for r in area.regions if r.type == 'WINDOW')
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.wm.tool_set_by_id(name=BLENDER_TOOLS[tool.idname])
