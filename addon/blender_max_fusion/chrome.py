# SPDX-License-Identifier: GPL-3.0-or-later
"""Original interactive chrome, measured against the installed 3ds Max 2027 UI.

All artwork is drawn from basic geometry/text. No reference icons are embedded.
Surfaces live in Image Editor areas identified by role; no image datablocks
are created, so saved files carry no extension data beyond the workspace.
"""
from .localization import tr as _tr
import math
import time
import bpy
from .localization import blf
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from bpy_extras import view3d_utils
from . import runtime, surfaces

PREFIX = '.BSM.'
_handles = []
_generation = 0
_windows = set()
_shader = None
_roles = {}
_view_hits = {}
_view_hover = {}
EDITOR_ROLES = {'Slate', 'Compact', 'Curve', 'Dope', 'UV', 'Render', 'Scene'}
SURFACES = {'Toolbar', 'Command', 'Timeline', 'Ribbon', 'Sidebar', 'Explorer'} | EDITOR_ROLES


def role(area_or_space):
    """Studio role of an Image Editor area ('' for ordinary editors)."""
    area = area_or_space if isinstance(area_or_space, bpy.types.Area) else None
    if area is None:
        space = area_or_space
        image = getattr(space, 'image', None)
        return image.name[len(PREFIX):].split('.')[0] if image and image.name.startswith(PREFIX) else ''
    found = _roles.get(area.as_pointer())
    if found:
        return found
    space = area.spaces.active
    image = getattr(space, 'image', None)
    if image and image.name.startswith(PREFIX):
        return image.name[len(PREFIX):].split('.')[0]
    return ''


def _scale():
    return surfaces.scale()


def _uniform():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


def rect(x, y, w, h, color):
    shader = _uniform()
    batch = batch_for_shader(shader, 'TRIS', {'pos': [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]}, indices=[(0, 1, 2), (0, 2, 3)])
    shader.bind()
    shader.uniform_float('color', color)
    batch.draw(shader)


def polygon(points, color):
    shader = _uniform()
    batch = batch_for_shader(shader, 'TRIS', {'pos': points}, indices=[(0, i, i+1) for i in range(1, len(points)-1)])
    shader.bind()
    shader.uniform_float('color', color)
    batch.draw(shader)


def line(points, color, width=1):
    shader = _uniform()
    batch = batch_for_shader(shader, 'LINES', {'pos': points})
    shader.bind()
    shader.uniform_float('color', color)
    gpu.state.line_width_set(width)
    batch.draw(shader)


def text(value, x, y, size=11, color=(.80, .80, .80, 1)):
    f = surfaces.font()
    blf.size(f, size*_scale())
    blf.position(f, x, y, 0)
    blf.color(f, *color)
    blf.draw(f, value)


def text_width(value, size=10):
    f = surfaces.font()
    blf.size(f, size*_scale())
    return blf.dimensions(f, value)[0]


def draw_image():
    context = bpy.context
    image = getattr(context.space_data, 'image', None)
    if runtime.is_active() and image is not None and image.type == 'RENDER_RESULT':
        # Blender's render window is an Image Editor; title it like Max's Rendered Frame Window.
        from . import editor_host
        editor_host.sync_title(context.window, editor_host.render_title(context))
    if not runtime.in_workspace(context):
        return
    kind = role(context.area)
    if not kind:
        return
    gpu.state.blend_set('ALPHA')
    rect(0, 0, context.region.width, context.region.height, surfaces.BG)
    if kind == 'Toolbar':
        surfaces.toolbar(context)
    elif kind == 'Command':
        surfaces.command(context)
    elif kind == 'Timeline':
        surfaces.timeline(context)
    elif kind == 'Ribbon':
        surfaces.ribbon(context)
    elif kind == 'Sidebar':
        surfaces.strip(context)
    elif kind == 'Explorer':
        surfaces.explorer(context)
    elif kind in EDITOR_ROLES:
        from . import editor_host
        editor_host.draw(context, kind)
    gpu.state.line_width_set(1)
    gpu.state.blend_set('NONE')


def _primary(context):
    return runtime.in_workspace(context) and context.workspace.get('bsm_primary_workspace')


# Home grid and ortho grids ------------------------------------------------------
GRID_MINOR = (.29, .29, .29, .75)
GRID_MAJOR = (.36, .36, .36, .9)
AXIS_VIEWS = {'Top': (0, 1, 2), 'Bottom': (0, 1, 2), 'Front': (0, 2, 1), 'Back': (0, 2, 1), 'Left': (1, 2, 0), 'Right': (1, 2, 0)}


def draw_grid():
    context = bpy.context
    if (not _primary(context) or context.space_data.type != 'VIEW_3D' or not context.window_manager.bsm.finite_grid
            or not context.space_data.overlay.show_overlays):  # the Max grid is a guide: Shift+Alt+Z and ActiveShade hide it
        return
    from .operators import view_name
    r3d = context.region_data
    spacing = max(1e-4, context.window_manager.bsm.grid_spacing)
    name = view_name(r3d)
    minor, major, axes = [], [], []
    if r3d.view_perspective == 'ORTHO' and name in AXIS_VIEWS:
        a, b, n = AXIS_VIEWS[name]
        region = context.region
        corners = [view3d_utils.region_2d_to_location_3d(region, r3d, (x, y), Vector((0, 0, 0)))
                   for x, y in ((0, 0), (region.width, 0), (0, region.height), (region.width, region.height))]
        low_a, high_a = min(c[a] for c in corners), max(c[a] for c in corners)
        low_b, high_b = min(c[b] for c in corners), max(c[b] for c in corners)
        pixels = region.width/max(1e-6, high_a-low_a)
        while spacing*pixels < 9:
            spacing *= 10
        while spacing*pixels > 90 and spacing > 1e-3:
            spacing /= 10

        def point(u, v):
            p = [0., 0., 0.]
            p[a], p[b] = u, v
            return tuple(p)
        i0, i1 = math.floor(low_a/spacing), math.ceil(high_a/spacing)
        j0, j1 = math.floor(low_b/spacing), math.ceil(high_b/spacing)
        if (i1-i0)+(j1-j0) > 1200:
            return
        for i in range(i0, i1+1):
            target = axes if i == 0 else (major if i % 10 == 0 else minor)
            target.extend([point(i*spacing, low_b), point(i*spacing, high_b)])
        for j in range(j0, j1+1):
            target = axes if j == 0 else (major if j % 10 == 0 else minor)
            target.extend([point(low_a, j*spacing), point(high_a, j*spacing)])
        axis_colors = ((.08, .08, .08, 1),)
    else:
        limit = 40
        for k in range(-limit, limit+1):
            if k == 0:
                continue
            target = major if k % 10 == 0 else minor
            target.extend([(-limit*spacing, k*spacing, 0), (limit*spacing, k*spacing, 0), (k*spacing, -limit*spacing, 0), (k*spacing, limit*spacing, 0)])
        axis_colors = None
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.depth_mask_set(False)
    if minor:
        line(minor, GRID_MINOR)
    if major:
        line(major, GRID_MAJOR)
    if axis_colors:
        if axes:
            line(axes, axis_colors[0], 1.5)
    else:
        limit = 40*spacing
        line([(-limit, 0, 0), (limit, 0, 0)], (.72, .31, .31, 1))
        line([(0, -limit, 0), (0, limit, 0)], (.26, .58, .29, 1))
    gpu.state.line_width_set(1)
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('NONE')


# Viewport labels, ViewCube and active border ------------------------------------
# Face name, outward normal and two in-face axes (right, up as seen from outside).
CUBE_FACES = (('TOP', Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0))),
              ('BOTTOM', Vector((0, 0, -1)), Vector((1, 0, 0)), Vector((0, -1, 0))),
              ('FRONT', Vector((0, -1, 0)), Vector((1, 0, 0)), Vector((0, 0, 1))),
              ('BACK', Vector((0, 1, 0)), Vector((-1, 0, 0)), Vector((0, 0, 1))),
              ('RIGHT', Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
              ('LEFT', Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))))


def _shading_labels(space):
    shading = space.shading
    preset = {'MATERIAL': 'High Quality', 'RENDERED': 'ActiveShade'}.get(shading.type, 'Standard')
    if shading.type == 'WIREFRAME':
        style = 'Wireframe Override' if shading.show_xray_wireframe else 'Hidden Line'
    elif shading.type == 'SOLID':
        style = 'Flat Color' if shading.light == 'FLAT' else ('Clay' if shading.color_type == 'SINGLE' else 'Default Shading')
    else:
        style = 'Default Shading'
    if space.overlay.show_wireframes and shading.type != 'WIREFRAME':
        style += ' + Edged Faces'
    return preset, style


def draw_view():
    context = bpy.context
    if not _primary(context) or context.space_data.type != 'VIEW_3D' or context.region_data is None:
        return
    from .operators import view_name, _active_region
    from . import max_menus
    region, r3d, space = context.region, context.region_data, context.space_data
    w, h = region.width, region.height
    u = _scale()
    key = region.as_pointer()
    hits = []
    hover = _view_hover.get(key)
    gpu.state.blend_set('ALPHA')
    quad = bool(space.region_quadviews)
    active = _active_region[0] == key or (not quad)
    if active:
        border = surfaces.AUTO_KEY if context.scene.tool_settings.use_keyframe_insert_auto else (.486, .416, .173, 1)
        line([(1, 1), (w-1, 1), (w-1, 1), (w-1, h-1), (w-1, h-1), (1, h-1), (1, h-1), (1, 1)], border, 2)
    else:
        line([(0, 0), (w, 0), (w, 0), (w, h), (w, h), (0, h), (0, h), (0, 0)], (.196, .196, .196, 1), 1)
    label_color = (.784, .784, .784, 1)
    preset, style = _shading_labels(space)
    x = 7*u
    for value, menu in (('+', max_menus.LABEL_MENUS.get('PLUS')), (view_name(r3d)+' ▾', max_menus.LABEL_MENUS.get('POV')),
                        (preset+' ▾', max_menus.LABEL_MENUS.get('PRESET')), (style+' ▾', max_menus.LABEL_MENUS.get('SHADING'))):
        width = text_width(value, 10)
        if hover == ('LABEL', menu):
            rect(x-3*u, h-19*u, width+6*u, 16*u, (.30, .45, .62, .8))
        text(value, x, h-15*u, 10, label_color)
        hits.append((x-3*u, h-20*u, width+6*u, 18*u, ('LABEL', menu)))
        x += width+14*u
    if context.window_manager.bsm.show_viewcube:
        hits += _viewcube(context, w, h, u, hover)
    q = r3d.view_rotation.inverted()
    origin = Vector((22*u, 24*u))
    for axis, label, color in ((Vector((1, 0, 0)), 'x', (.76, .30, .30, 1)), (Vector((0, 1, 0)), 'y', (.35, .70, .35, 1)), (Vector((0, 0, 1)), 'z', (.35, .58, .85, 1))):
        projected = q@axis
        end = origin+Vector((projected.x, projected.y))*15*u
        line([tuple(origin), tuple(end)], color, 1.5)
        text(label, end.x+1, end.y+1, 7, color)
    _view_hits[key] = hits
    gpu.state.line_width_set(1)
    gpu.state.blend_set('NONE')


def _viewcube(context, w, h, u, hover):
    r3d = context.region_data
    size = 40*u
    cx, cy = w-62*u, h-66*u
    rotation = r3d.view_rotation.inverted()
    hits = []
    # Compass ring on the ground plane under the cube.
    ring = []
    for i in range(48):
        p = rotation@Vector((1.55*math.cos(2*math.pi*i/48), 1.55*math.sin(2*math.pi*i/48), -1))
        ring.append((cx+p.x*size*.62, cy+p.y*size*.62))
    segments = [pt for a, b in zip(ring, ring[1:]+ring[:1]) for pt in (a, b)]
    line(segments, (.45, .45, .45, .8), 1.5)
    for letter, direction in (('N', (0, 1.85)), ('S', (0, -1.85)), ('E', (1.85, 0)), ('W', (-1.85, 0))):
        p = rotation@Vector((direction[0], direction[1], -1))
        text(letter, cx+p.x*size*.62-3*u, cy+p.y*size*.62-3*u, 7, (.55, .55, .55, 1))
    faces = []
    for name, normal, a, b in CUBE_FACES:
        view_normal = rotation@normal
        if view_normal.z <= 1e-4:
            continue
        corners = [rotation@(normal+a*sa+b*sb) for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        points = [(cx+c.x*size*.5, cy+c.y*size*.5) for c in corners]
        faces.append((view_normal.z, name, normal, a, b, points))
    faces.sort(key=lambda f: f[0])
    for depth, name, normal, a, b, points in faces:
        shade = .45+.35*depth
        color = (shade, shade, shade, .95)
        if hover and hover[0] == 'CUBE' and hover[1] == name:
            color = (.38, .58, .82, .95)
        polygon(points, color)
        outline = [pt for p, q in zip(points, points[1:]+points[:1]) for pt in (p, q)]
        line(outline, (.18, .18, .18, 1), 1)
        if depth > .35:
            center = (sum(p[0] for p in points)/4, sum(p[1] for p in points)/4)
            label = name if depth > .6 else name[0]
            tw = text_width(label, 6)
            text(label, center[0]-tw/2, center[1]-2*u, 6, (.12, .12, .12, 1))
        hits.append(('POLY', points, ('CUBE', name, normal, a, b)))
    # Home icon above the cube.
    hx, hy = cx-size*.95, cy+size*.85
    color = (.38, .58, .82, 1) if hover == ('HOME',) else (.70, .70, .70, 1)
    polygon([(hx, hy+5*u), (hx+5*u, hy+9*u), (hx+10*u, hy+5*u)], color)
    rect(hx+2*u, hy, 6*u, 5*u, color)
    hits.append((hx-2*u, hy-2*u, 14*u, 13*u, ('HOME',)))
    return hits


def _inside(point, polygon_points):
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(polygon_points, polygon_points[1:]+polygon_points[:1]):
        if (y0 > y) != (y1 > y) and x < (x1-x0)*(y-y0)/(y1-y0+1e-12)+x0:
            inside = not inside
    return inside


def view_hit(region, x, y):
    for hit in reversed(_view_hits.get(region.as_pointer(), ())):
        if hit[0] == 'POLY':
            if _inside((x, y), hit[1]):
                return hit[2]
        else:
            hx, hy, hw, hh, action = hit
            if hx <= x < hx+hw and hy <= y < hy+hh:
                return action
    return None


_animations = {}


def animate_view(area, region, rotation, perspective=None, distance=None):
    """Smoothly rotate a viewport like the ViewCube's transition."""
    r3d = region.data
    start = r3d.view_rotation.copy()
    key = region.as_pointer()
    steps = 10
    _animations[key] = 0

    def tick():
        try:
            step = _animations.get(key)
            if step is None:
                return None
            step += 1
            _animations[key] = step
            t = step/steps
            t = t*t*(3-2*t)
            r3d.view_rotation = start.slerp(rotation, t)
            area.tag_redraw()
            if step >= steps:
                if perspective:
                    r3d.view_perspective = perspective
                _animations.pop(key, None)
                return None
            return .016
        except ReferenceError:
            _animations.pop(key, None)
            return None
    bpy.app.timers.register(tick, first_interval=.0)


def cube_action(context, area, region, action, point):
    from .commands import record_view, _home_rotation
    record_view(context, area)
    r3d = region.data
    if action[0] == 'HOME':
        with context.temp_override(window=context.window, area=area, region=region):
            bpy.ops.view3d.view_all(center=False)
        animate_view(area, region, _home_rotation(), 'PERSP')
        return
    normal, a, b = action[2], action[3], action[4]
    hit = next((h for h in _view_hits.get(region.as_pointer(), ()) if h[0] == 'POLY' and h[2][1] == action[1]), None)
    direction = normal.copy()
    if hit:
        # Max splits each face 3×3: centre → face view, edges/corners → 45° views.
        p0, p1, p2, p3 = (Vector(p) for p in hit[1])
        ex, ey = p1-p0, p3-p0
        rel = Vector(point)-p0
        det = ex.x*ey.y-ex.y*ey.x
        if abs(det) > 1e-6:
            s = (rel.x*ey.y-rel.y*ey.x)/det*2-1
            t = (ex.x*rel.y-ex.y*rel.x)/det*2-1
            if abs(s) > .55:
                direction += a*math.copysign(1, s)
            if abs(t) > .55:
                direction += b*math.copysign(1, t)
    direction.normalize()
    if abs(direction.z) > .999:
        from .operators import VIEW_ROTATIONS
        rotation = VIEW_ROTATIONS['TOP' if direction.z > 0 else 'BOTTOM']
    else:
        rotation = _look_rotation(direction)
    animate_view(area, region, rotation, r3d.view_perspective if r3d.view_perspective != 'CAMERA' else 'PERSP')


def _look_rotation(direction):
    """View rotation whose -Z looks along -direction with world Z up."""
    z = direction.normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    y = z.cross(x)
    from mathutils import Matrix
    return Matrix((x, y, z)).transposed().to_quaternion()


# Header replacements -------------------------------------------------------------
_original_image_header = bpy.types.IMAGE_HT_header.draw
_original_properties_header = bpy.types.PROPERTIES_HT_header.draw


def draw_topbar(self, context):
    if context.region.alignment == 'RIGHT':
        row = self.layout.row(align=True)
        row.label(text=_tr('Workspaces: Default'))
        pass  # the unified callback draws all three destinations
        pass
    else:
        from .ui import draw_menus
        draw_menus(self, context)


def draw_image_header(self, context):
    if not role(context.area):
        _original_image_header(self, context)


def draw_properties_header(self, context):
    if not context.workspace.get('bsm_primary_workspace'):
        _original_properties_header(self, context)


def draw_status(self, context):
    l = self.layout
    l.template_reports_banner()
    l.template_running_jobs()
    l.separator_spacer()
    l.label(text=_tr('Blender Max'))


class BSM_OT_explorer_search(bpy.types.Operator):
    bl_idname = 'bsm.explorer_search'
    bl_label = 'Find'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        context.window_manager.bsm.explorer_scroll = 0
        runtime.redraw()
        return {'FINISHED'}

    def draw(self, context):
        self.layout.prop(context.window_manager.bsm, 'explorer_search', text=_tr('Name'))


def _area_at(screen, x, y):
    for area in screen.areas:
        if area.x <= x < area.x+area.width and area.y <= y < area.y+area.height:
            region = next((r for r in area.regions if r.type == 'WINDOW' and r.x <= x < r.x+r.width and r.y <= y < r.y+r.height), None)
            return area, region
    return None, None


def _tooltip_timer(area_ptr):
    def tick():
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.as_pointer() == area_ptr:
                    area.tag_redraw()
        return None
    return tick


def _commit(context, edit):
    owner, attr, index = edit['owner'], edit['attr'], edit['index']
    original = surfaces.read(owner, attr, index)
    value = edit['value']
    if isinstance(original, bool):
        value = value.strip().lower() in {'1', 'true', 'yes', 'on'}
    elif isinstance(original, (int, float)):
        value = _number(context, owner, attr, value, original)
        if isinstance(original, int):
            value = int(round(value))
    if index >= 0:
        getattr(owner, attr)[index] = value
    else:
        setattr(owner, attr, value)
    state = context.window_manager.bsm
    if owner == state and attr == 'new_set_name' and value:
        from .toolbar import create_set
        objects = [o for o in context.view_layer.objects if o.select_get()]
        if objects:
            create_set(context, value, objects)
        state.new_set_name = ''
    _after_edit(context, owner)


def _number(context, owner, attr, text, original):
    text = text.strip()
    try:
        value = float(eval(text, {'__builtins__': {}}, {'pi': math.pi})) if text else float(original)
        if surfaces.is_angle(owner, attr):
            value = math.radians(value)
        return value
    except Exception:
        units = context.scene.unit_settings
        category = 'LENGTH' if surfaces.is_length(owner, attr) else ('ROTATION' if surfaces.is_angle(owner, attr) else 'NONE')
        try:
            value = bpy.utils.units.to_value(units.system if category != 'NONE' else 'NONE', category, text)
            return value/units.scale_length if category == 'LENGTH' else value
        except ValueError:
            return float(original)


def _after_edit(context, owner):
    if isinstance(owner, bpy.types.ID) or isinstance(getattr(owner, 'id_data', None), bpy.types.ID):
        bpy.ops.ed.undo_push(message='Max Field Edit')
    from . import params
    if isinstance(owner, params.BSM_PrimitiveParams) and isinstance(owner.id_data, bpy.types.Object):
        sync_instances(owner.id_data)
    if context.window.workspace.get('bsm_editor_kind') in {'Slate', 'Compact'}:
        from . import material_ui
        material_ui.request_preview(material_ui.current_material(context))


def sync_instances(obj):
    """Instances share their base object in Max: copy parameters to every user of the mesh."""
    from . import params
    if obj.data is None or obj.data.users < 2:
        return
    for other in bpy.data.objects:
        if other is obj or other.data != obj.data or not other.bsm_prim.kind:
            continue
        for attr in params.DEFAULTS.get(obj.bsm_prim.kind, {}):
            if getattr(other.bsm_prim, attr) != getattr(obj.bsm_prim, attr):
                setattr(other.bsm_prim, attr, getattr(obj.bsm_prim, attr))


def _spin_step(owner, attr):
    rna = surfaces.rna_property(owner, attr)
    if rna is None or rna.type == 'INT':
        return 1., 1.
    step = max(1e-4, rna.step/100.)
    if surfaces.is_angle(owner, attr):
        step = math.radians(1) if rna.subtype in {'ANGLE', 'EULER'} else 1.
    return step, step*10


class BSM_OT_chrome_events(bpy.types.Operator):
    bl_idname = 'bsm.chrome_events'
    bl_label = 'Blender Max Interface Events'
    generation = 0
    pointer = 0
    edit = None
    spin = None
    drag = None
    scrubbing = None
    menu_click = None
    size = None

    def invoke(self, context, event):
        self.pointer = context.window.as_pointer()
        self.size = (context.window.width, context.window.height)
        if self.pointer in _windows:
            return {'CANCELLED'}
        self.generation = _generation
        _windows.add(self.pointer)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not runtime.is_active() or self.generation != _generation:
            if self.generation == _generation:
                _windows.discard(self.pointer)
            # Pass the event on: after a file load the new handler, not this one, owns it.
            return {'FINISHED', 'PASS_THROUGH'}
        editor_kind = context.window.workspace.get('bsm_editor_kind')
        if not context.window.workspace.get('bsm_primary_workspace') and not editor_kind:
            return {'PASS_THROUGH'}
        if event.type == 'MOUSEMOVE':
            if self.pointer in _grow_pending:
                _try_grow(context.window)
            elif (context.window.width, context.window.height) != self.size:
                check_timeline(context.window)
            self.size = (context.window.width, context.window.height)
        if self.edit is not None:
            result = self.edit_event(context, event)
            if result is not None:
                return result
        if self.spin is not None:
            return self.spin_event(context, event)
        if self.drag is not None:
            return self.drag_event(context, event)
        if editor_kind:
            from . import editor_host
            result = editor_host.active_event(context, event)
            if result is not None:
                return result
            editor_area, editor_region = _area_at(context.window.screen, event.mouse_x, event.mouse_y)
            if editor_region:
                with context.temp_override(window=context.window, area=editor_area, region=editor_region):
                    result = editor_host.handle_event(context, event, editor_area, editor_region, (event.mouse_x-editor_region.x)/_scale(), (event.mouse_y-editor_region.y)/_scale(), editor_kind)
                if result is not None:
                    return result
        if self.scrubbing:
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.scrubbing = None
            elif event.type == 'MOUSEMOVE':
                area, region, slider = self.scrubbing
                try:
                    surfaces.scrub(context, area, (event.mouse_x-region.x)/_scale(), slider)
                except ReferenceError:
                    self.scrubbing = None
            return {'RUNNING_MODAL'}
        state = context.window_manager.bsm
        area, region = _area_at(context.window.screen, event.mouse_x, event.mouse_y)
        if area is None or region is None:
            return {'PASS_THROUGH'}
        x, y = event.mouse_x-region.x, event.mouse_y-region.y
        u = _scale()
        kind = 'Timeline' if area.ui_type == 'TIMELINE' else role(area)
        if event.type == 'MOUSEMOVE':
            self.hover(context, area, region, kind, x, y)
            return {'PASS_THROUGH'}
        if event.value == 'RELEASE' and event.type not in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'}:
            # Hotkeys (N, S, A...) run their operator directly; show the result on the bars.
            runtime.redraw()
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:
            click, self.menu_click = self.menu_click, None
            if click is not None and event.value == 'RELEASE' and event.type == click['button']:
                # Max menus open on a click and stay open. Opened on the press, Blender
                # would pick the item under the cursor on this release and close.
                if click['region'] == region.as_pointer() and click['still'](area, region, x, y):
                    with context.temp_override(window=context.window, area=area, region=region):
                        try:
                            click['open'](context)
                        except RuntimeError as error:
                            self.report({'WARNING'}, str(error).split('\n')[0])
                    runtime.redraw()
                return {'RUNNING_MODAL'}
        if area.type == 'VIEW_3D':
            return self.viewport_event(context, event, area, region, x, y)
        if event.value == 'PRESS' and event.type not in {'ESC', 'RET', 'NUMPAD_ENTER'} and not state.active_creation:
            from . import keymap
            if keymap.run_anywhere(context, event):
                runtime.redraw()
                return {'RUNNING_MODAL'}
        if state.active_creation and event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            state.active_creation = ''
            runtime.redraw()
            return {'RUNNING_MODAL'}
        if kind not in SURFACES:
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = 1 if event.type == 'WHEELDOWNMOUSE' else -1
            if kind == 'Command':
                key = (area.as_pointer(), state.tab)
                surfaces._scroll[key] = max(0., surfaces._scroll.get(key, 0.)+step*30)
                area.tag_redraw()
            elif kind == 'Explorer':
                rows = len(surfaces.explorer_rows(context))
                state.explorer_scroll = max(0, min(max(0, rows-1), state.explorer_scroll+step))
                area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.value != 'PRESS' or event.type not in {'LEFTMOUSE', 'RIGHTMOUSE'}:
            return {'PASS_THROUGH'} if event.type not in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'} else {'RUNNING_MODAL'}
        surfaces._mods.update(ctrl=event.ctrl, shift=event.shift, alt=event.alt)
        hit = surfaces.lookup(area, x/u, y/u)
        override = dict(window=context.window, area=area, region=region)
        secondary = event.type == 'RIGHTMOUSE'
        if hit is None:
            if kind == 'Command' and not secondary:
                key = (area.as_pointer(), state.tab)
                self.drag = dict(type='PAN', key=key, start=y, value=surfaces._scroll.get(key, 0.), area=area.as_pointer())
                context.window.cursor_modal_set('HAND')
            return {'RUNNING_MODAL'}
        action = hit[4]
        if action[0] == 'RMB' and not secondary:
            action = action[1]
        if action[0] == 'FIELD' and not secondary:
            owner, attr, index = action[1:]
            try:
                value = surfaces.read(owner, attr, index)
            except (ReferenceError, AttributeError):
                return {'RUNNING_MODAL'}
            text_value = surfaces.format_value(owner, attr, value) if isinstance(value, float) and surfaces.is_angle(owner, attr) else (
                f'{value:.4f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value))
            self.edit = dict(owner=owner, attr=attr, index=index, value=text_value, cursor=len(text_value), all=True,
                             original=value, area=area.as_pointer())
            surfaces._editing = self.edit
            area.tag_redraw()
            return {'RUNNING_MODAL'}
        if action[0] == 'SPIN':
            owner, attr, index = action[1:]
            try:
                value = surfaces.read(owner, attr, index)
            except (ReferenceError, AttributeError):
                return {'RUNNING_MODAL'}
            if secondary:
                rna = surfaces.rna_property(owner, attr)
                low = rna.hard_min if rna is not None and hasattr(rna, 'hard_min') else 0
                reset = max(0, low) if isinstance(value, (int, float)) else value
                self._set(owner, attr, index, type(value)(reset))
                _after_edit(context, owner)
                runtime.redraw()
                return {'RUNNING_MODAL'}
            hx, hy, hw, hh = hit[:4]
            self.spin = dict(owner=owner, attr=attr, index=index, start=event.mouse_y, original=value, moved=False,
                             upper=y/u >= hy+hh/2)
            return {'RUNNING_MODAL'}
        if action[0] in {'SCRUB', 'SCRUB_SLIDER'} and not secondary:
            slider = action[0] == 'SCRUB_SLIDER'
            surfaces.scrub(context, area, x/u, slider)
            self.scrubbing = (area, region, slider)
            return {'RUNNING_MODAL'}
        if action[0] in {'TRACK_KEY', 'TRACKBAR'}:
            from . import trackbar
            frame = action[1] if action[0] == 'TRACK_KEY' else surfaces.frame_at(area, x/u)
            if secondary:
                # Max's track bar menu, opened on the click like the other menus.
                def open_menu(ctx, frame=frame):
                    trackbar.menu_frame[0] = frame
                    if action[0] == 'TRACK_KEY' and frame not in trackbar.selected:
                        trackbar.selected.clear()
                        trackbar.selected.add(frame)
                    bpy.ops.wm.call_menu(name='BSM_MT_trackbar')
                self.menu_click = dict(button=event.type, region=region.as_pointer(),
                                       still=lambda a, r, mx, my: a.as_pointer() == area.as_pointer(), open=open_menu)
                return {'RUNNING_MODAL'}
            if action[0] == 'TRACK_KEY':
                # Click selects a key (Ctrl adds or removes); dragging moves the selected keys in time.
                if event.ctrl:
                    trackbar.selected.symmetric_difference_update({frame})
                elif frame not in trackbar.selected:
                    trackbar.selected.clear()
                    trackbar.selected.add(frame)
                frames = set(trackbar.selected)
                self.drag = dict(type='TRACK_KEYS', area=area.as_pointer(), region_x=region.x, start=x/u, frames=frames,
                                 snapshot=trackbar.snapshot(context, frames), delta=0)
            else:
                # Empty track bar: drag a frame range to select keys, as in Max.
                if not event.ctrl:
                    trackbar.selected.clear()
                self.drag = dict(type='TRACK_SELECT', area=area.as_pointer(), region_x=region.x, first=frame)
                surfaces._timeline[('select', area.as_pointer())] = (frame, frame)
            runtime.redraw()
            return {'RUNNING_MODAL'}
        if action[0] == 'STACK' and not secondary:
            self.drag = dict(type='STACK', obj=action[1], name=action[2], start=event.mouse_y, moved=False, area=area.as_pointer(),
                             action=action, rows=list(surfaces._stack_layout.get(area.as_pointer(), ())))
            return {'RUNNING_MODAL'}
        if surfaces.opens_menu(hit[4], secondary):
            rect, chosen = hit[:4], hit[4]
            self.menu_click = dict(button=event.type, region=region.as_pointer(),
                                   still=lambda a, r, mx, my: (surfaces.lookup(a, mx/u, my/u) or (None,))[:4] == rect,
                                   open=lambda ctx: surfaces.dispatch(ctx, chosen, secondary))
            return {'RUNNING_MODAL'}
        with context.temp_override(**override):
            try:
                surfaces.dispatch(context, hit[4], secondary)
            except RuntimeError as error:
                self.report({'WARNING'}, str(error).split('\n')[0])
        runtime.redraw()
        return {'RUNNING_MODAL'}

    def track_event(self, context, event, drag, u):
        from . import trackbar
        area = next((a for a in context.window.screen.areas if a.as_pointer() == drag['area']), None)
        if area is None:
            self.drag = None
            return {'RUNNING_MODAL'}
        x = (event.mouse_x-drag['region_x'])/u
        if drag['type'] == 'TRACK_SELECT':
            frame = surfaces.frame_at(area, x)
            if event.type == 'MOUSEMOVE' and frame is not None:
                surfaces._timeline[('select', drag['area'])] = (drag['first'], frame)
                area.tag_redraw()
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                low, high = sorted(surfaces._timeline.pop(('select', drag['area']), (drag['first'], drag['first'])))
                trackbar.selected.update(f for f in trackbar.track_keys(context) if low <= f <= high)
                self.drag = None
                runtime.redraw()
            elif event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
                surfaces._timeline.pop(('select', drag['area']), None)
                self.drag = None
                runtime.redraw()
            return {'RUNNING_MODAL'}
        geometry = surfaces._timeline.get(drag['area'])
        if event.type == 'MOUSEMOVE' and geometry:
            left, width = geometry['track']
            delta = round((x-drag['start'])/(width/geometry['span']))
            if delta != drag['delta']:
                drag['delta'] = delta
                trackbar.move(drag['snapshot'], delta)
                trackbar.selected.clear()
                trackbar.selected.update(f+delta for f in drag['frames'])
                runtime.redraw()
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if drag['delta']:
                bpy.ops.ed.undo_push(message='Move Keys')
            self.drag = None
        elif event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            trackbar.move(drag['snapshot'], 0)
            trackbar.selected.clear()
            trackbar.selected.update(drag['frames'])
            self.drag = None
            runtime.redraw()
        return {'RUNNING_MODAL'}

    def hover(self, context, area, region, kind, x, y):
        u = _scale()
        if area.type == 'VIEW_3D':
            if context.window.workspace.get('bsm_primary_workspace') and not context.selected_objects and region.data:
                # Max shows the cursor's position on the home grid in the status bar coordinates.
                origin = view3d_utils.region_2d_to_origin_3d(region, region.data, (x, y))
                ray = view3d_utils.region_2d_to_vector_3d(region, region.data, (x, y))
                if abs(ray.z) > 1e-6 and (origin.z/-ray.z > 0 or region.data.is_orthographic_side_view):
                    point = origin+ray*(-origin.z/ray.z)
                    if surfaces._cursor[0] is None or (point-Vector(surfaces._cursor[0])).length > 1e-4:
                        surfaces._cursor[0] = tuple(point)
                        for other in context.window.screen.areas:
                            if role(other) == 'Timeline':
                                other.tag_redraw()
            if context.window.workspace.get('bsm_primary_workspace'):
                runtime.sync_reference(context, region)
                from . import max_gizmo
                max_gizmo.hover(context, area, region, x, y)
                target = view_hit(region, x, y)
                key = region.as_pointer()
                normalized = (target[0], target[1]) if target and target[0] in {'CUBE', 'LABEL'} else (target if target else None)
                if _view_hover.get(key) != normalized:
                    _view_hover[key] = normalized
                    area.tag_redraw()
            return
        if kind not in SURFACES:
            return
        key = area.as_pointer()
        surfaces._hover[key] = (x/u, y/u)
        target = surfaces.hover_target(area, x/u, y/u)
        previous = surfaces._hover_since.get(key)
        if previous is None or previous[0] != target:
            surfaces._hover_since[key] = (target, time.monotonic())
            area.tag_redraw()
            if target is not None:
                bpy.app.timers.register(_tooltip_timer(key), first_interval=.6)
        elif kind in EDITOR_ROLES:
            area.tag_redraw()

    def viewport_event(self, context, event, area, region, x, y):
        from .operators import set_active_region, _active_region
        from .commands import record_view
        state = context.window_manager.bsm
        primary = context.window.workspace.get('bsm_primary_workspace')
        if event.value == 'PRESS' and event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'} and _active_region[0] != region.as_pointer():
            set_active_region(region)
            runtime.sync_reference(context, region)
            runtime.redraw()
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.value in {'PRESS', 'NOTHING'}:
            record_view(context, area)
            return {'PASS_THROUGH'}
        if state.active_creation and event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            state.active_creation = ''
            runtime.redraw()
            return {'RUNNING_MODAL'}
        if not primary or event.type != 'LEFTMOUSE' or event.value != 'PRESS':
            return {'PASS_THROUGH'}
        override = dict(window=context.window, area=area, region=region)
        target = view_hit(region, x, y)
        if target is not None:
            if target[0] == 'LABEL' and target[1]:
                self.menu_click = dict(button=event.type, region=region.as_pointer(),
                                       still=lambda a, r, mx, my: view_hit(r, mx, my) == target,
                                       open=lambda ctx: bpy.ops.wm.call_menu(name=target[1]))
            elif target[0] in {'CUBE', 'HOME'}:
                self.drag = dict(type='CUBE', start=(event.mouse_x, event.mouse_y), target=target, area=area.as_pointer(),
                                 region=region.as_pointer(), point=(x, y))
            return {'RUNNING_MODAL'}
        if state.active_creation:
            with context.temp_override(**override):
                bpy.ops.bsm.draw_primitive('INVOKE_DEFAULT', kind=state.active_creation)
            return {'RUNNING_MODAL'}
        from . import max_gizmo
        result = max_gizmo.press(context, event, area, region, x, y)
        if result is not None:
            return result
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
        if tool and tool.idname.startswith('builtin.select') and context.mode in {'OBJECT', 'EDIT_MESH'}:
            with context.temp_override(**override):
                bpy.ops.bsm.select_region('INVOKE_DEFAULT', add=event.ctrl, subtract=event.alt)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def drag_event(self, context, event):
        drag = self.drag
        u = _scale()
        if drag['type'] in {'TRACK_KEYS', 'TRACK_SELECT'}:
            return self.track_event(context, event, drag, u)
        if drag['type'] == 'PAN':
            if event.type == 'MOUSEMOVE':
                surfaces._scroll[drag['key']] = max(0., drag['value']+(event.mouse_y-drag['start']-0)/u)
                runtime.redraw()
            elif event.type in {'LEFTMOUSE', 'ESC'} and event.value in {'RELEASE', 'PRESS'}:
                context.window.cursor_modal_restore()
                self.drag = None
            return {'RUNNING_MODAL'}
        if drag['type'] == 'CUBE':
            if event.type == 'MOUSEMOVE' and abs(event.mouse_x-drag['start'][0])+abs(event.mouse_y-drag['start'][1]) > 4:
                self.drag = None
                area = next((a for a in context.window.screen.areas if a.as_pointer() == drag['area']), None)
                region = next((r for r in area.regions if r.as_pointer() == drag['region']), None) if area else None
                if region:
                    with context.temp_override(window=context.window, area=area, region=region):
                        bpy.ops.view3d.rotate('INVOKE_DEFAULT')
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.drag = None
                area = next((a for a in context.window.screen.areas if a.as_pointer() == drag['area']), None)
                region = next((r for r in area.regions if r.as_pointer() == drag['region']), None) if area else None
                if region:
                    cube_action(context, area, region, drag['target'], drag['point'])
            return {'RUNNING_MODAL'}
        if drag['type'] == 'STACK':
            if event.type == 'MOUSEMOVE':
                if abs(event.mouse_y-drag['start']) > 5:
                    drag['moved'] = True
                    context.window.cursor_modal_set('MOVE_Y')
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.drag = None
                context.window.cursor_modal_restore()
                if not drag['moved'] or not drag['name']:
                    surfaces.dispatch(context, drag['action'])
                    return {'RUNNING_MODAL'}
                area = next((a for a in context.window.screen.areas if a.as_pointer() == drag['area']), None)
                region = next((r for r in area.regions if r.type == 'WINDOW'), None) if area else None
                if region is None:
                    return {'RUNNING_MODAL'}
                y = (event.mouse_y-region.y)/u
                rows = [r for r in drag['rows'] if r[1] == 'MOD']
                if not rows:
                    return {'RUNNING_MODAL'}
                nearest = min(rows, key=lambda r: abs(r[0]+8-y))
                obj = bpy.data.objects.get(drag['obj'])
                if obj and nearest[2] in obj.modifiers and nearest[2] != drag['name']:
                    target = list(obj.modifiers).index(obj.modifiers[nearest[2]])
                    bpy.ops.bsm.stack_action(action='MOVE_TO', modifier=drag['name'], index=target)
                runtime.redraw()
                return {'RUNNING_MODAL'}
            if event.type == 'ESC':
                self.drag = None
                context.window.cursor_modal_restore()
            return {'RUNNING_MODAL'}
        self.drag = None
        return {'RUNNING_MODAL'}

    @staticmethod
    def _set(owner, attr, index, value):
        if index >= 0:
            getattr(owner, attr)[index] = value
        else:
            setattr(owner, attr, value)

    def spin_event(self, context, event):
        spin = self.spin
        owner, attr, index = spin['owner'], spin['attr'], spin['index']
        state = context.window_manager.bsm
        per_pixel, click = _spin_step(owner, attr)
        original = spin['original']
        if event.type == 'MOUSEMOVE':
            dy = event.mouse_y-spin['start']
            if abs(dy) > 2:
                spin['moved'] = True
            if spin['moved']:
                factor = 10 if event.ctrl else (.1 if event.alt else 1)
                if isinstance(original, int):
                    value = original+int(dy/3*factor)
                else:
                    value = original+dy*per_pixel*factor
                    if state.spinner_snap:
                        snap = state.spinner_snap_value*(math.radians(1) if surfaces.is_angle(owner, attr) else 1)
                        value = round(value/snap)*snap
                try:
                    self._set(owner, attr, index, value)
                except (TypeError, ValueError, ReferenceError):
                    pass
                runtime.redraw()
            return {'RUNNING_MODAL'}
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            try:
                self._set(owner, attr, index, original)
            except ReferenceError:
                pass
            self.spin = None
            runtime.redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if not spin['moved']:
                delta = (1 if isinstance(original, int) else click)*(1 if spin['upper'] else -1)
                if state.spinner_snap and not isinstance(original, int):
                    delta = math.copysign(state.spinner_snap_value, delta)
                try:
                    self._set(owner, attr, index, type(original)(original+delta))
                except (TypeError, ValueError, ReferenceError):
                    pass
            self.spin = None
            _after_edit(context, owner)
            runtime.redraw()
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}

    def edit_event(self, context, event):
        edit = self.edit
        if event.type == 'MOUSEMOVE' or event.value != 'PRESS':
            return {'RUNNING_MODAL'} if event.type != 'MOUSEMOVE' else None
        value, cursor = edit['value'], edit['cursor']

        def finish(commit=True):
            self.edit = None
            surfaces._editing = None
            if commit:
                try:
                    _commit(context, edit)
                except (ValueError, TypeError, AttributeError, ReferenceError) as error:
                    self.report({'WARNING'}, str(error))
            runtime.redraw()
        if event.type in {'RET', 'NUMPAD_ENTER', 'TAB'}:
            finish()
            return {'RUNNING_MODAL'}
        if event.type == 'ESC':
            finish(False)
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:
            finish()
            return None
        if event.ctrl and event.type in {'A', 'C', 'V', 'X'}:
            if event.type == 'A':
                edit['all'] = True
            elif event.type == 'C':
                context.window_manager.clipboard = value
            elif event.type == 'X':
                context.window_manager.clipboard = value
                edit['value'], edit['cursor'], edit['all'] = '', 0, False
            else:
                paste = context.window_manager.clipboard.splitlines()[0] if context.window_manager.clipboard else ''
                if edit['all']:
                    value, cursor = '', 0
                edit['value'] = value[:cursor]+paste+value[cursor:]
                edit['cursor'] = cursor+len(paste)
                edit['all'] = False
            runtime.redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'BACK_SPACE':
            if edit['all']:
                edit['value'], edit['cursor'] = '', 0
            elif cursor:
                edit['value'] = value[:cursor-1]+value[cursor:]
                edit['cursor'] = cursor-1
            edit['all'] = False
        elif event.type == 'DEL':
            if edit['all']:
                edit['value'], edit['cursor'] = '', 0
            else:
                edit['value'] = value[:cursor]+value[cursor+1:]
            edit['all'] = False
        elif event.type == 'LEFT_ARROW':
            edit['cursor'] = 0 if edit['all'] else max(0, cursor-1)
            edit['all'] = False
        elif event.type == 'RIGHT_ARROW':
            edit['cursor'] = len(value) if edit['all'] else min(len(value), cursor+1)
            edit['all'] = False
        elif event.type == 'HOME':
            edit['cursor'], edit['all'] = 0, False
        elif event.type == 'END':
            edit['cursor'], edit['all'] = len(value), False
        elif event.unicode and not event.ctrl and not event.alt:
            if edit['all']:
                value, cursor = '', 0
            edit['value'] = value[:cursor]+event.unicode+value[cursor:]
            edit['cursor'] = cursor+len(event.unicode)
            edit['all'] = False
        runtime.redraw()
        return {'RUNNING_MODAL'}


def register_mode():
    if bpy.app.background:
        return
    _windows.intersection_update(w.as_pointer() for w in bpy.context.window_manager.windows)
    if not _handles:
        _handles.append((bpy.types.SpaceImageEditor, bpy.types.SpaceImageEditor.draw_handler_add(draw_image, (), 'WINDOW', 'POST_PIXEL')))
        _handles.append((bpy.types.SpaceView3D, bpy.types.SpaceView3D.draw_handler_add(draw_grid, (), 'WINDOW', 'POST_VIEW')))
        from . import object_icons
        _handles.append((bpy.types.SpaceView3D, bpy.types.SpaceView3D.draw_handler_add(object_icons.draw, (), 'WINDOW', 'POST_VIEW')))
        _handles.append((bpy.types.SpaceView3D, bpy.types.SpaceView3D.draw_handler_add(draw_view, (), 'WINDOW', 'POST_PIXEL')))
    for window in bpy.context.window_manager.windows:
        if window.as_pointer() in _windows:
            continue
        with bpy.context.temp_override(window=window):
            bpy.ops.bsm.chrome_events('INVOKE_DEFAULT')


def _restore_extras():
    """Outside Max mode Blender draws lights, cameras and empties again in the Max workspace."""
    for workspace in bpy.data.workspaces:
        if not workspace.get('bsm_primary_workspace'):
            continue
        for screen in workspace.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.overlay.show_extras = True


def restart_events():
    """Opening a file removes every window's modal handlers, so the event handler that
    makes the Max chrome clickable was gone while its window still counted as handled:
    menus, labels and buttons ignored clicks in the loaded scene. Forget the handled
    windows so register_mode() starts the handler again; a handler that did survive
    ends at its next event because the generation moved on."""
    global _generation
    _generation += 1
    _windows.clear()


def unregister_mode():
    global _generation
    _generation += 1
    _windows.clear()
    _restore_extras()
    for cls, handle in reversed(_handles):
        cls.draw_handler_remove(handle, 'WINDOW')
    _handles.clear()
    _view_hits.clear()
    _view_hover.clear()
    surfaces.clear()
    from . import editor_host, icons, quad
    editor_host.clear()
    icons.clear()
    quad.close()


def _remove_legacy_images():
    for image in list(bpy.data.images):
        if image.name.startswith(PREFIX) and image.users == 0:
            bpy.data.images.remove(image)


def prepare_workspace(window):
    """Bind surface roles to areas by position; set the 3ds Max viewport defaults once."""
    if not window.workspace.get('bsm_primary_workspace'):
        return
    if window.workspace.name in runtime.OLD_WORKSPACE_NAMES:
        window.workspace.name = runtime.WORKSPACE_NAME
    screen = window.screen
    areas = screen.areas
    first_layout = window.workspace.get('bsm_layout_version', 0) < 4
    for area in areas:
        if area.type == 'PROPERTIES' or area.ui_type == 'TIMELINE':
            area.type = 'IMAGE_EDITOR'
    image_areas = [a for a in areas if a.type == 'IMAGE_EDITOR']
    horizontal = sorted((a for a in image_areas if a.width > a.height*3), key=lambda a: -a.y)
    vertical = sorted((a for a in image_areas if a.height > a.width*2), key=lambda a: a.x)
    for area, name in list(zip(horizontal, ('Toolbar', 'Ribbon', 'Timeline')))+list(zip(vertical, ('Sidebar', 'Explorer', 'Command'))):
        _roles[area.as_pointer()] = name
        space = area.spaces.active
        space.image = None
        space.show_region_header = False
        space.show_region_toolbar = False
        space.show_region_ui = False
        space.show_gizmo = False
        if hasattr(space, 'show_region_tool_header'):
            space.show_region_tool_header = False
    _remove_legacy_images()
    for area in areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            if first_layout:
                space.region_3d.view_location = space.region_3d.view_rotation@Vector((0, 2.3, 0))
                space.region_3d.view_distance = 149 if window.workspace.get('bsm_layout_version', 0) < 3 else space.region_3d.view_distance
                space.shading.color_type = 'OBJECT'
                space.shading.wireframe_color_type = 'OBJECT'
            space.show_region_header = False
            space.show_region_tool_header = False
            space.show_region_toolbar = False
            space.show_region_ui = False
            space.show_gizmo_tool = True
            space.show_gizmo_navigate = False
            space.overlay.show_text = False
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_ortho_grid = False
            # Lights look as in Max: object_icons draws them (and cameras and empties, which
            # the same Blender overlay draws) instead of Blender's extras overlay.
            space.overlay.show_extras = False
    # Migrate the initial perspective once; preserve subsequent user navigation.
    if not window.workspace.get('bsm_axis_view_v1'):
        from .commands import _home_rotation
        for view_area in areas:
            if view_area.type == 'VIEW_3D':
                view_space = view_area.spaces.active
                if view_space.region_3d.view_perspective == 'PERSP':
                    view_space.region_3d.view_rotation = _home_rotation()
        window.workspace['bsm_axis_view_v1'] = True
    timeline = next((a for a in areas if _roles.get(a.as_pointer()) == 'Timeline'), None)
    off = timeline is not None and abs(timeline.height-surfaces.TIMELINE_HEIGHT*_scale()) > 4
    if window.workspace.get('bsm_layout_version', 0) < 5 or off:
        # Max has no status line under its time controls: hide Blender's, and give the
        # bottom panel Max's height for the time slider, track bar and status lines.
        screen.show_statusbar = False
        _grow_pending.add(window.as_pointer())
        bpy.app.timers.register(lambda: _try_grow(window), first_interval=.01)
    runtime.redraw()
    window.workspace['bsm_layout_version'] = 5


_grow_pending = set()
_ACTIVE_REGION_OFFSET = []  # offset of bScreen.active_region, found once per session
KNOWN_ACTIVE_REGION_OFFSETS = {(5, 0): 496}


def _active_region_slot(screen):
    """The screen's active-region pointer, or None when it cannot be identified safely.

    Blender resizes areas only while the mouse is on an area edge, where the screen has no
    active region (screen.area_move's poll). Clearing the pointer for the duration of the
    resize lets the bottom panel take Max's height at once, without moving the cursor. The
    field is located by its value: it must hold one of this screen's own region pointers."""
    import ctypes
    import sys
    regions = {r.as_pointer() for a in screen.areas for r in a.regions}
    base = screen.as_pointer()
    if not _ACTIVE_REGION_OFFSET:
        if sys.platform == 'win32':
            # ReadProcessMemory fails instead of crashing if the scan meets unmapped memory.
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.ReadProcessMemory.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
            buffer, read = (ctypes.c_ubyte*1024)(), ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(kernel32.GetCurrentProcess(), base, buffer, 1024, ctypes.byref(read)):
                return None
            data = bytes(buffer[:read.value])
            hits = [o for o in range(0, len(data)-7, 8) if int.from_bytes(data[o:o+8], 'little') in regions]
        else:
            hits = [KNOWN_ACTIVE_REGION_OFFSETS[bpy.app.version[:2]]] if bpy.app.version[:2] in KNOWN_ACTIVE_REGION_OFFSETS else []
        if len(hits) != 1:
            return None
        _ACTIVE_REGION_OFFSET.append(hits[0])
    slot = ctypes.c_uint64.from_address(base+_ACTIVE_REGION_OFFSET[0])
    return slot if slot.value in regions else None


def _timeline_delta(window):
    area = next((a for a in window.screen.areas if _roles.get(a.as_pointer()) == 'Timeline'), None)
    return area, (int(surfaces.TIMELINE_HEIGHT*_scale())-area.height if area else 0)


def _try_grow(window):
    """Give the bottom panel Max's height: at once when the screen allows area resizing,
    otherwise for the length of the resize with the active region cleared, or, as a last
    resort, when the mouse next crosses an area edge. The cursor is never moved."""
    try:
        if not runtime.is_active() or not window.workspace.get('bsm_primary_workspace'):
            _grow_pending.discard(window.as_pointer())
            return None
        screen = window.screen
        with bpy.context.temp_override(window=window, screen=screen):
            allowed = bpy.ops.screen.area_move.poll()
        slot = None
        if not allowed:
            try:
                slot = _active_region_slot(screen)
            except (OSError, ValueError, AttributeError):
                slot = None
            if slot is None:
                return None
        saved = slot.value if slot is not None else 0
        if slot is not None:
            slot.value = 0
        try:
            with bpy.context.temp_override(window=window, screen=screen):
                allowed = bpy.ops.screen.area_move.poll()
            if allowed:
                _grow_pending.discard(window.as_pointer())
                _grow_timeline(window)
        finally:
            if slot is not None:
                slot.value = saved  # area_move frees no regions: the pointer is still valid
    except ReferenceError:
        _grow_pending.clear()
    return None


def _grow_timeline(window):
    """Max's bottom panel holds the time slider, track bar and two status lines."""
    try:
        area, delta = _timeline_delta(window)
        if abs(delta) > 2:
            with bpy.context.temp_override(window=window, screen=window.screen, area=area):
                bpy.ops.screen.area_move(x=area.x+area.width//2, y=area.y+area.height, delta=delta)
    except (ReferenceError, RuntimeError):
        pass  # the window closed, or the screen has no room to grow the panel
    runtime.redraw()
    return None


def check_timeline(window):
    """Blender scales areas with the window: after a resize, restore Max's panel height."""
    try:
        if window.workspace.get('bsm_primary_workspace') and abs(_timeline_delta(window)[1]) > 2:
            _grow_pending.add(window.as_pointer())
            _try_grow(window)
    except ReferenceError:
        pass


CLASSES = (BSM_OT_explorer_search, BSM_OT_chrome_events)
