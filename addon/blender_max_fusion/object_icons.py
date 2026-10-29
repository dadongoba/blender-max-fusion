# SPDX-License-Identifier: GPL-3.0-or-later
"""Max-style light icons in the viewports.

Blender draws every light (and camera and empty) in its "extras" overlay, with its own
shapes and colours; there is no switch for lights alone, and hiding lights by type stops
them lighting the viewport. Max viewports therefore turn the extras overlay off and this
module draws lights as 3ds Max 2027 does: small yellow icons that turn white when
selected, the cones of selected spots and directs, area shapes and target lines.
Cameras and empties, which the same overlay drew, are drawn here as Blender draws them.
Rendering is unchanged: only the overlay is. Picking uses the same shapes.
"""
import math
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from bpy_extras import view3d_utils

# Colours measured from 3ds Max 2027's viewport (research/live-capture/lights): light icons,
# target lines, and the hotspot and falloff of a selected spot or direct light.
LIGHT = (1., .894, 0., 1.)
LIGHT_SELECTED = (1., 1., 1., 1.)
TARGET_LINE = (.25, .565, .784, 1.)
HOTSPOT = (.784, .722, .157, 1.)
FALLOFF = (.502, .471, .157, 1.)
ICON_PIXELS = 22  # light icon size on screen at UI scale 1, as Max shows them at default zoom
PICK_PIXELS = 7
TYPE_FLAGS = {'LIGHT': 'show_object_viewport_light', 'CAMERA': 'show_object_viewport_camera',
              'EMPTY': 'show_object_viewport_empty', 'SPEAKER': 'show_object_viewport_speaker',
              'LIGHT_PROBE': 'show_object_viewport_light_probe'}
SELECT_FLAGS = {'LIGHT': 'show_object_select_light', 'CAMERA': 'show_object_select_camera',
                'EMPTY': 'show_object_select_empty', 'SPEAKER': 'show_object_select_speaker',
                'LIGHT_PROBE': 'show_object_select_light_probe'}
_shader = []


def _uniform():
    if not _shader:
        _shader.append(gpu.shader.from_builtin('UNIFORM_COLOR'))
    return _shader[0]


def _lines(points, color, width=1.):
    if not points:
        return
    shader = _uniform()
    batch = batch_for_shader(shader, 'LINES', {'pos': points})
    shader.bind()
    shader.uniform_float('color', color)
    gpu.state.line_width_set(width)
    batch.draw(shader)


# Shapes -------------------------------------------------------------------------------
def _circle(radius, axis='Z', z=0., steps=24, center=(0., 0., 0.)):
    pts = []
    for i in range(steps):
        a, b = 2*math.pi*i/steps, 2*math.pi*(i+1)/steps
        for t in (a, b):
            c, s = radius*math.cos(t), radius*math.sin(t)
            p = {'Z': (c, s, z), 'Y': (c, z, s), 'X': (z, c, s)}[axis]
            pts.append((p[0]+center[0], p[1]+center[1], p[2]+center[2]))
    return pts


def _box(hx, hy, hz, center=(0., 0., 0.)):
    cx, cy, cz = center
    v = [(cx+x*hx, cy+y*hy, cz+z*hz) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    edges = ((0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7))
    return [v[i] for e in edges for i in e]


def octahedron(r=.5):
    """Max's Omni: a small diamond in all three planes."""
    tips = [(r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0)]
    pts = []
    for a, b in zip(tips, tips[1:]+tips[:1]):
        pts += [a, b, a, (0, 0, r), a, (0, 0, -r)]
    return pts


def globe(r=.5, steps=16):
    """Max's photometric and Arnold lights: a small wire globe (meridians and latitudes)."""
    pts = _circle(r, 'Z', 0, steps)+_circle(r*.84, 'Z', r*.55, steps)+_circle(r*.84, 'Z', -r*.55, steps)
    for i in range(4):
        a = math.pi*i/4
        c, s_ = math.cos(a), math.sin(a)
        ring = _circle(r, 'X', 0, steps)
        pts += [(y*-s_, y*c, z) for (_, y, z) in ring]
    return pts


def spot_icon(h=1.):
    """Max's spot: a cone with its tip behind the light and its round base toward where it
    shines (local -Z), with eight ribs."""
    r = .36*h
    base = [(r*math.cos(2*math.pi*i/8), r*math.sin(2*math.pi*i/8), -h/2) for i in range(8)]
    pts = [p for a, b in zip(base, base[1:]+base[:1]) for p in (a, b)]
    return pts+[p for v in base for p in ((0, 0, h/2), v)]


def direct_icon(h=1.):
    """Max's directional light: a tall box standing on a flat square plate facing where it shines."""
    pts = _box(.14*h, .14*h, .31*h, (0, 0, .2*h))
    top, bottom = .32*h, .26*h
    upper = [(x*top, y*top, -.11*h) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    lower = [(x*bottom, y*bottom, -.2*h) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for ring in (upper, lower):
        pts += [p for a, b in zip(ring, ring[1:]+ring[:1]) for p in (a, b)]
    pts += [p for a, b in zip(upper, lower) for p in (a, b)]
    return pts


def skylight_icon(r=.5):
    """Max's Skylight: a dome of two arcs over its base circle."""
    pts = _circle(r, 'Z', 0, 24)
    for axis in ('X', 'Y'):
        arc = _circle(r, axis, 0, 24)
        pts += [p for i in range(0, len(arc), 2) for p in arc[i:i+2] if min(arc[i][2], arc[i+1][2]) >= -1e-6]
    return pts


def kind(obj):
    """The Max light this Blender light stands for: recorded at creation, else by type."""
    tag = obj.get('bsm_light')
    if tag:
        return tag
    return {'POINT': 'OMNI', 'SPOT': 'FREE_SPOT', 'SUN': 'FREE_DIRECT', 'AREA': 'AREA'}.get(obj.data.type, 'OMNI')


def icon_shape(obj):
    k = kind(obj)
    if k in {'FREE_LIGHT', 'TARGET_LIGHT', 'AREA'}:
        return globe()
    if k in {'TARGET_SPOT', 'FREE_SPOT'}:
        return spot_icon()
    if k in {'TARGET_DIRECT', 'FREE_DIRECT', 'SUN_POSITIONER'}:
        return direct_icon()
    if k == 'SKYLIGHT':
        return skylight_icon()
    return octahedron()


def area_shape(light):
    """The emitting shape of an area light, in light space (world size)."""
    w = light.size
    h = light.size_y if light.shape in {'RECTANGLE', 'ELLIPSE'} else light.size
    if light.shape in {'DISK', 'ELLIPSE'}:
        return [(p[0]*w/2/.5, p[1]*h/2/.5, 0) for p in _circle(.5, 'Z', 0, 32)]
    return [(x*w/2, y*h/2, 0) for (x, y) in ((-1, -1), (1, -1), (1, -1), (1, 1), (1, 1), (-1, 1), (-1, 1), (-1, -1))]


def target_of(obj):
    for c in obj.constraints:
        if c.type in {'TRACK_TO', 'DAMPED_TRACK', 'LOCKED_TRACK'} and c.target is not None and not c.mute:
            return c.target
    return None


# Cameras and empties, as Blender draws them -------------------------------------------------
def camera_shape(obj, scene):
    frame = [Vector(v) for v in obj.data.view_frame(scene=scene)]
    pts = [p for a, b in zip(frame, frame[1:]+frame[:1]) for p in (a, b)]
    if obj.data.type == 'ORTHO':
        pts += [p for v in frame for p in (v, Vector((v.x, v.y, 0)))]
    else:
        pts += [p for v in frame for p in (Vector((0, 0, 0)), v)]
    top = max(frame, key=lambda v: v.y).y
    left, right = min(v.x for v in frame), max(v.x for v in frame)
    z = frame[0].z
    width = (right-left)*.35
    tri = [Vector((-width, top*1.1, z)), Vector((width, top*1.1, z)), Vector((0, top*1.1+width*.9, z))]
    pts += [p for a, b in zip(tri, tri[1:]+tri[:1]) for p in (a, b)]
    return [tuple(p) for p in pts]


def empty_shape(obj):
    s = obj.empty_display_size
    t = obj.empty_display_type
    if t == 'PLAIN_AXES':
        return [(-s, 0, 0), (s, 0, 0), (0, -s, 0), (0, s, 0), (0, 0, -s), (0, 0, s)]
    if t == 'ARROWS':
        return [(0, 0, 0), (s, 0, 0), (0, 0, 0), (0, s, 0), (0, 0, 0), (0, 0, s)]
    if t == 'SINGLE_ARROW':
        head = [(0, 0, s), (s*.08, 0, s*.8), (0, 0, s), (-s*.08, 0, s*.8), (0, 0, s), (0, s*.08, s*.8), (0, 0, s), (0, -s*.08, s*.8)]
        return [(0, 0, 0), (0, 0, s)]+head
    if t == 'CIRCLE':
        return _circle(s, 'Z', 0, 32)
    if t == 'CUBE':
        return _box(s, s, s)
    if t == 'SPHERE':
        return _circle(s, 'Z', 0, 32)+_circle(s, 'X', 0, 32)+_circle(s, 'Y', 0, 32)
    if t == 'CONE':
        base = _circle(s, 'Y', 0, 16)
        return base+[p for t_ in range(0, 16, 4) for p in ((s*math.cos(2*math.pi*t_/16), 0, s*math.sin(2*math.pi*t_/16)), (0, 2*s, 0))]
    return []


def simple_marker():
    return octahedron(.35)


# Drawing ---------------------------------------------------------------------------------
def ui_factor(context):
    """Pixels per UI unit, including the operating system's display scaling."""
    system = context.preferences.system
    return system.dpi/72 if getattr(system, 'dpi', 0) else system.ui_scale


def world_per_pixel(region, r3d, point):
    """World units covered by one pixel at a point, so icons keep a constant screen size."""
    p0 = view3d_utils.location_3d_to_region_2d(region, r3d, point)
    if p0 is None:
        return None
    right = r3d.view_rotation @ Vector((1, 0, 0))
    p1 = view3d_utils.location_3d_to_region_2d(region, r3d, point+right)
    if p1 is None:
        return None
    pixels = (p1-p0).length
    return 1/pixels if pixels > 1e-9 else None


def _icon_matrix(obj, size):
    """Object location and rotation (no scale), at a given world size."""
    loc, rot, _ = obj.matrix_world.decompose()
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Scale(size, 4)


def _transform(matrix, pts):
    return [tuple(matrix @ Vector(p)) for p in pts]


def visible(context, obj):
    space = context.space_data
    flag = TYPE_FLAGS.get(obj.type)
    if flag and not getattr(space, flag, True):
        return False
    try:
        return obj.visible_get(view_layer=context.view_layer, viewport=space)
    except TypeError:
        return obj.visible_get()


def light_targets(context):
    """Empties that a light aims at: Max draws a light's target as a small box in the light's colour."""
    return {t for o in context.view_layer.objects if o.type == 'LIGHT' for t in (target_of(o),) if t is not None}


def shapes(context, obj, region, r3d, ui, targets=frozenset()):
    """[(world points, colour)] for an object this module draws."""
    scene = context.scene
    selected = obj.select_get()
    active = obj == context.view_layer.objects.active
    theme = context.preferences.themes[0].view_3d
    out = []
    if obj.type == 'LIGHT':
        unit = world_per_pixel(region, r3d, obj.matrix_world.translation)
        if unit is None:
            return out
        size = ICON_PIXELS*ui*unit
        icon = _icon_matrix(obj, size)
        color = LIGHT_SELECTED if selected else LIGHT
        out.append((_transform(icon, icon_shape(obj)), color))
        light = obj.data
        loc, rot, _ = obj.matrix_world.decompose()
        frame = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
        if light.type == 'AREA':
            # Arnold's area light: its emitter outline and a line along where it shines.
            reach = .6*max(light.size, light.size_y if light.shape in {'RECTANGLE', 'ELLIPSE'} else light.size)
            out.append((_transform(obj.matrix_world, area_shape(light)+[(0, 0, 0), (0, 0, -reach)]), color))
        target = target_of(obj)
        if target is not None:
            out.append(([tuple(loc), tuple(target.matrix_world.translation)], TARGET_LINE))
        if selected and light.type in {'SPOT', 'SUN'}:
            length = (target.matrix_world.translation-loc).length if target is not None else 12*size
            out += cones(light, frame, length, size)
    elif obj.type == 'CAMERA':
        color = tuple(theme.object_active if active else theme.object_selected) if selected else tuple(theme.camera)
        out.append((_transform(obj.matrix_world, camera_shape(obj, scene)), color+(1.,) if len(color) == 3 else color))
    elif obj in targets:
        unit = world_per_pixel(region, r3d, obj.matrix_world.translation)
        if unit is not None:
            size = ICON_PIXELS*ui*unit
            out.append((_transform(_icon_matrix(obj, size), _box(.17, .17, .17)), LIGHT_SELECTED if selected else LIGHT))
    elif obj.type == 'EMPTY' and obj.empty_display_type != 'IMAGE':
        color = tuple(theme.object_active if active else theme.object_selected) if selected else tuple(theme.empty)
        out.append((_transform(obj.matrix_world, empty_shape(obj)), color+(1.,) if len(color) == 3 else color))
    elif obj.type in {'SPEAKER', 'LIGHT_PROBE'}:
        unit = world_per_pixel(region, r3d, obj.matrix_world.translation)
        if unit is not None:
            color = tuple(theme.object_selected) if selected else tuple(theme.wire)
            out.append((_transform(_icon_matrix(obj, ICON_PIXELS*ui*unit), simple_marker()), color+(1.,) if len(color) == 3 else color))
    return out


def cones(light, frame, length, size):
    """Hotspot and falloff of a selected spot (cones) or direct light (cylinders), as Max shows them."""
    out = []
    if light.type == 'SPOT':
        fall = light.spot_size/2
        hot = fall*(1-light.spot_blend)
        for angle, color in ((hot, HOTSPOT), (fall, FALLOFF)):
            r = length*math.tan(min(angle, math.radians(89)))
            ring = _circle(r, 'Z', -length, 48)
            spokes = [p for i in range(4) for p in ((0, 0, 0), (r*math.cos(i*math.pi/2), r*math.sin(i*math.pi/2), -length))]
            out.append((_transform(frame, ring+spokes), color))
    else:
        for r, color in ((4*size, HOTSPOT), (5.5*size, FALLOFF)):
            pts = _circle(r, 'Z', 0, 40)+_circle(r, 'Z', -length, 40)
            pts += [p for i in range(4) for p in ((r*math.cos(i*math.pi/2), r*math.sin(i*math.pi/2), 0), (r*math.cos(i*math.pi/2), r*math.sin(i*math.pi/2), -length))]
            out.append((_transform(frame, pts), color))
    return out


def drawn_objects(context):
    for obj in context.view_layer.objects:
        if obj.type in {'LIGHT', 'CAMERA', 'EMPTY', 'SPEAKER', 'LIGHT_PROBE'} and visible(context, obj):
            yield obj


def draw():
    context = bpy.context
    space = context.space_data
    if (space is None or space.type != 'VIEW_3D' or not space.overlay.show_overlays or space.overlay.show_extras
            or not _in_max_viewport(context)):
        return
    region, r3d = context.region, context.region_data
    if r3d is None:
        return
    ui = ui_factor(context)
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.depth_mask_set(False)
    targets = light_targets(context)
    for obj in drawn_objects(context):
        for pts, color in shapes(context, obj, region, r3d, ui, targets):
            _lines(pts, color, 1.5 if obj.type == 'LIGHT' else 1.)
    gpu.state.line_width_set(1)
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('NONE')


def _in_max_viewport(context):
    from . import runtime
    return runtime.in_workspace(context) and context.workspace.get('bsm_primary_workspace')


# Picking ------------------------------------------------------------------------------------
def _segment_distance(p, a, b):
    ab = b-a
    t = 0. if ab.length_squared < 1e-12 else max(0., min(1., (p-a).dot(ab)/ab.length_squared))
    return (a+ab*t-p).length


def projected(context, obj, region, r3d):
    """Screen segments of an object's icon (region pixels), without the cones."""
    ui = ui_factor(context)
    segs = []
    for pts, color in shapes(context, obj, region, r3d, ui, light_targets(context))[:3]:
        flat = [view3d_utils.location_3d_to_region_2d(region, r3d, Vector(p)) for p in pts]
        segs += [(a, b) for a, b in zip(flat[0::2], flat[1::2]) if a is not None and b is not None]
    return segs


def pick(context, region, xy, limit=None):
    """The drawn object whose icon lies under a region point, or None."""
    if region.data is None or not _extras_hidden(context, region):
        return None
    limit = (limit or PICK_PIXELS)*ui_factor(context)
    point = Vector(xy)
    best = None
    for obj in drawn_objects_for(context, region):
        if obj.hide_select or not _selectable_type(context, obj):
            continue
        origin = view3d_utils.location_3d_to_region_2d(region, region.data, obj.matrix_world.translation)
        distance = (origin-point).length if origin is not None else 1e9
        for a, b in projected(context, obj, region, region.data):
            distance = min(distance, _segment_distance(point, a, b))
        if distance <= limit and (best is None or distance < best[0]):
            best = (distance, obj)
    return best[1] if best else None


def inside(context, region, test, all_points=False):
    """Drawn objects whose icon points pass a region test (window: all of them; crossing: any)."""
    if region.data is None or not _extras_hidden(context, region):
        return []
    found = []
    for obj in drawn_objects_for(context, region):
        if obj.hide_select or not _selectable_type(context, obj):
            continue
        pts = [p for seg in projected(context, obj, region, region.data) for p in seg]
        origin = view3d_utils.location_3d_to_region_2d(region, region.data, obj.matrix_world.translation)
        if origin is not None:
            pts.append(origin)
        if pts and (all(test(p) for p in pts) if all_points else any(test(p) for p in pts)):
            found.append(obj)
    return found


def _area_of(context, region):
    windows = [context.window] if context.window else list(context.window_manager.windows)
    for window in windows:
        for area in window.screen.areas:
            if any(r == region for r in area.regions):
                return area
    return None


def _extras_hidden(context, region):
    area = _area_of(context, region)
    return area is not None and area.type == 'VIEW_3D' and not area.spaces.active.overlay.show_extras


def _selectable_type(context, obj):
    area = context.area if context.area and context.area.type == 'VIEW_3D' else None
    flag = SELECT_FLAGS.get(obj.type)
    return not (area and flag and not getattr(area.spaces.active, flag, True))


def drawn_objects_for(context, region):
    area = _area_of(context, region)
    if area is None:
        return []
    with context.temp_override(area=area, region=region, space_data=area.spaces.active):
        return list(drawn_objects(bpy.context))
