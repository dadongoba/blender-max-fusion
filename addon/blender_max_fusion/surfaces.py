# SPDX-License-Identifier: GPL-3.0-or-later
"""Reference-measured controls and hit targets for the studio surfaces.

Artwork is vector geometry. Buttons dispatch real Blender operators; editable
fields retain actual RNA owners rather than a separate imitation scene model.
Order, labels and rollouts follow the installed 3ds Max 2027 UI definitions
(DefaultUI.cuix, the Standard Primitive and Editable Poly dialog resources).
"""
from .localization import tr as _tr
import math
import time
import bpy
from .localization import blf
import gpu
import os
from pathlib import Path
from . import runtime

_targets = {}
_hover = {}
_hover_since = {}
_closed = set()
_opened = set()
_editing = None
_fonts = {}
_scroll = {}
_stack_layout = {}
_mods = {'ctrl': False, 'shift': False, 'alt': False}
BG = (.267, .267, .267, 1)
BUTTON = (.35, .35, .35, 1)
HOVER = (.42, .42, .42, 1)
TEXT = (.86, .86, .86, 1)
DIM = (.52, .52, .52, 1)
BLUE = (.373, .541, .757, 1)
AUTO_KEY = (1, 0, 0, 1)  # DefaultUI.clrx "Auto Key Button": button, time slider and active border
FIELD = (.20, .20, .20, 1)
ROLL = (.31, .31, .31, 1)
BODY = (.285, .285, .285, 1)
YELLOW = (.99, .92, .07, 1)
RED = (.85, .10, .10, 1)
CLOSED_BY_DEFAULT = {'Keyboard Entry', 'Soft Selection', 'Subdivision Surface', 'Polygon: Smoothing Groups',
                     'Email Notifications', 'Scripts', 'Assign Renderer'}  # the last three: Render Setup


def scale():
    return max(1.0, bpy.context.preferences.system.ui_scale)*1.25


_font_checked = {}


def font_alive(fid):
    """True while a loaded font still measures text. Opening a file makes Blender unload
    the fonts add-ons loaded with blf.load, and their ids then draw nothing."""
    blf.size(fid, 12)
    return blf.dimensions(fid, 'M')[0] > 0


def load_font(cache, key, path, fallback):
    """A cached blf font id, loaded again when Blender has unloaded it (checked at most
    twice a second; reset_fonts() clears the cache at once after a file load)."""
    fid = cache.get(key)
    now = time.monotonic()
    if fid is not None and now-_font_checked.get((id(cache), key), 0.) < .5:
        return fid
    _font_checked[(id(cache), key)] = now
    if fid is None or (fid != 0 and not font_alive(fid)):
        fid = cache[key] = blf.load(str(path)) if path.is_file() else fallback()
        if fid != 0 and not font_alive(fid):
            fid = cache[key] = 0  # Blender's own UI font always draws
    return fid


def font(bold=False):
    path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'/('segoeuib.ttf' if bold else 'segoeui.ttf')
    return load_font(_fonts, bold, path, lambda: 0)


def reset_fonts():
    """After a file load: forget font ids Blender has unloaded."""
    from . import quad
    _fonts.clear()
    quad._fonts.clear()
    _font_checked.clear()


def op(operator_name, **values): return ('OP', operator_name, values)
def menu(name): return op('wm.call_menu', name=name)
def prop(owner, attr, index=-1): return ('FIELD', owner, attr, index)
def toggle(owner, attr, index=-1): return ('TOGGLE', owner, attr, index)
def call(function, *args): return ('CALL', function, args)
def rmb(primary, secondary): return ('RMB', primary, secondary)


def rna_property(owner, attr):
    rna = getattr(owner, 'bl_rna', None)
    return rna.properties.get(attr) if rna else None


def format_value(owner, attr, value):
    """Display text like Max: units for lengths, degrees for angles."""
    rna = rna_property(owner, attr)
    if isinstance(value, bool):
        return 'On' if value else 'Off'
    if isinstance(value, float):
        if rna is not None and rna.subtype in {'DISTANCE', 'TRANSLATION'} or (rna is not None and getattr(rna, 'unit', '') == 'LENGTH'):
            units = bpy.context.scene.unit_settings
            if units.system != 'NONE':
                return bpy.utils.units.to_string(units.system, 'LENGTH', value*units.scale_length, precision=3, split_unit=False, compatible_unit=False)
        if rna is not None and (rna.subtype in {'ANGLE', 'EULER'} or getattr(rna, 'unit', '') == 'ROTATION'):
            from math import degrees
            value = degrees(value)
        return f'{value:.3f}'.rstrip('0').rstrip('.') if abs(value) < 1e6 else f'{value:.4g}'
    return str(value)


def is_angle(owner, attr):
    rna = rna_property(owner, attr)
    return rna is not None and (rna.subtype in {'ANGLE', 'EULER'} or getattr(rna, 'unit', '') == 'ROTATION')


def is_length(owner, attr):
    rna = rna_property(owner, attr)
    return rna is not None and (rna.subtype in {'DISTANCE', 'TRANSLATION'} or getattr(rna, 'unit', '') == 'LENGTH')


def read(owner, attr, index=-1):
    value = getattr(owner, attr)
    return value[index] if index >= 0 else value


class Canvas:
    def __init__(self, context):
        from . import chrome
        self.c = chrome
        self.context = context
        self.u = scale()
        self.w = context.region.width/self.u
        self.h = context.region.height/self.u
        self.key = context.area.as_pointer()
        self.oy = 0.
        self.clip = None
        _targets[self.key] = []

    def rect(self, x, y, w, h, color):
        self.c.rect(x*self.u, (y+self.oy)*self.u, w*self.u, h*self.u, color)

    def line(self, points, color=TEXT, width=1):
        self.c.line([(x*self.u, (y+self.oy)*self.u) for x, y in points], color, width*self.u)

    def text(self, value, x, y, size=10, color=TEXT, bold=False):
        f = font(bold)
        blf.size(f, size*self.u)
        blf.position(f, x*self.u, (y+self.oy)*self.u, 0)
        blf.color(f, *color)
        blf.draw(f, str(value))

    def text_width(self, value, size=9, bold=False):
        f = font(bold)
        blf.size(f, size*self.u)
        return blf.dimensions(f, str(value))[0]/self.u

    def text_right(self, value, x, y, size=9, color=TEXT):
        self.text(value, x-self.text_width(value, size), y, size, color)

    def icon(self, name, x, y, size=20, active=False, enabled=True):
        from . import icons
        try:
            icons.draw(name, x*self.u, (y+self.oy)*self.u, size*self.u, active=active, enabled=enabled)
        except KeyError:
            self.rect(x+size*.3, y+size*.3, size*.4, size*.4, DIM)

    def hit(self, x, y, w, h, action, label=''):
        y += self.oy
        if self.clip is not None:
            low, high = self.clip
            top, y = min(y+h, high), max(y, low)
            h = top-y
            if h <= 0:
                return
        _targets[self.key].append((x, y, w, h, action, label))

    def hovered(self, x, y, w, h):
        px, py = _hover.get(self.key, (-1, -1))
        return x <= px < x+w and y+self.oy <= py < y+self.oy+h

    def button(self, x, y, w, h, label='', action=None, icon=None, selected=False, flat=False, enabled=True, tip='', fill=None):
        hover = enabled and action is not None and self.hovered(x, y, w, h)
        if not flat or selected or hover or fill:
            self.rect(x, y, w, h, fill or (BLUE if selected else (HOVER if hover else BUTTON)))
        if icon:
            size = min(w-3, h-3, 22)
            self.icon(icon, x+(w-size)/2, y+(h-size)/2, size, False, enabled)
        if label:
            size = 9
            while size > 6 and self.text_width(label, size) > w-4:
                size -= .5
            tw = self.text_width(label, size)
            self.text(label, x+max(2, (w-tw)/2), y+(h-size)/2+1, size, TEXT if enabled else DIM)
        self.hit(x, y, w, h, action if enabled and action else ('NONE',), tip or label or icon or '')

    def dropdown(self, x, y, w, label, action, tip=''):
        self.rect(x, y, w, 16, (.34, .34, .34, 1))
        self.text(label, x+4, y+4, 9)
        self.c.polygon([(v*self.u, (z+self.oy)*self.u) for v, z in ((x+w-10, y+10), (x+w-4, y+10), (x+w-7, y+6))], TEXT)
        self.hit(x, y, w, 16, action, tip or label)

    def checkbox(self, x, y, label, owner=None, attr='', index=-1, enabled=True, value=None, action=None, size=9):
        if value is None and owner is not None:
            try:
                value = bool(read(owner, attr, index))
            except (AttributeError, ReferenceError, IndexError):
                return
        self.rect(x, y+1, 11, 11, (.18, .18, .18, 1))
        if value:
            color = TEXT if enabled else DIM
            self.c.polygon([(v*self.u, (z+self.oy)*self.u) for v, z in ((x+1.5, y+6.5), (x+3, y+8), (x+5, y+5.5), (x+5, y+3))], color)
            self.c.polygon([(v*self.u, (z+self.oy)*self.u) for v, z in ((x+5, y+3), (x+5, y+5.5), (x+9.5, y+11), (x+10.5, y+9.5))], color)
        self.text(label, x+15, y+2, size, TEXT if enabled else DIM)
        width = 15+self.text_width(label, size)
        self.hit(x, y, width, 13, (action or toggle(owner, attr, index)) if enabled else ('NONE',), label if enabled else f'{label} (not available in Blender)')

    def radio(self, x, y, label, selected, action, enabled=True, size=9):
        from math import cos, sin, pi
        points = [((x+5.5+5*cos(2*pi*i/16))*self.u, (y+6.5+5*sin(2*pi*i/16)+self.oy)*self.u) for i in range(16)]
        self.c.polygon(points, (.18, .18, .18, 1))
        if selected:
            self.c.polygon([((x+5.5+2.5*cos(2*pi*i/12))*self.u, (y+6.5+2.5*sin(2*pi*i/12)+self.oy)*self.u) for i in range(12)], TEXT if enabled else DIM)
        self.text(label, x+14, y+2, size, TEXT if enabled else DIM)
        self.hit(x, y, 14+self.text_width(label, size), 13, action if enabled else ('NONE',), label)

    def field(self, x, y, w, owner, attr, index=-1, label='', spinner=None, enabled=True):
        try:
            value = read(owner, attr, index)
        except (ReferenceError, AttributeError, IndexError, TypeError):
            return
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        spin = numeric if spinner is None else spinner
        editing = _editing and _editing.get('owner') == owner and _editing.get('attr') == attr and _editing.get('index') == index
        box = w-11 if spin else w
        if editing:
            text = _editing['value']
        else:
            text = format_value(owner, attr, value)
        self.rect(x, y, box, 16, BLUE if editing else FIELD)
        prefix = (label+' ') if label else ''
        self.text(prefix+text, x+4, y+4, 9, TEXT if enabled else DIM)
        if editing:
            caret = _editing.get('cursor', len(text))
            cx = x+4+self.text_width(prefix+text[:caret])
            if _editing.get('all'):
                self.rect(x+3+self.text_width(prefix), y+2, self.text_width(text)+2, 12, (.55, .70, .90, .45))
            self.rect(cx, y+2, 1, 12, TEXT)
        if enabled:
            self.hit(x, y, box, 16, prop(owner, attr, index), label or attr)
        if spin:
            sx = x+w-10
            self.rect(sx, y, 10, 16, (.25, .25, .25, 1))
            color = TEXT if enabled else DIM
            self.c.polygon([(v*self.u, (z+self.oy)*self.u) for v, z in ((sx+2, y+9.5), (sx+8, y+9.5), (sx+5, y+13.5))], color)
            self.c.polygon([(v*self.u, (z+self.oy)*self.u) for v, z in ((sx+2, y+6.5), (sx+8, y+6.5), (sx+5, y+2.5))], color)
            if enabled:
                self.hit(sx, y, 10, 16, ('SPIN', owner, attr, index), 'Drag to change; right-click resets')

    def param(self, y, owner, attr, label, enabled=True, lw=None):
        """A Max rollout row: right-aligned label then a spinner field."""
        split = lw or self.w*.50
        self.text_right(label, split, y+4, 9, TEXT if enabled else DIM)
        self.field(split+3, y, self.w-split-11, owner, attr, enabled=enabled)

    def rollout(self, title, y, body_height, key=None):
        key = key or (self.context.window_manager.bsm.tab, title)
        opened = key not in _closed and (title not in CLOSED_BY_DEFAULT or key in _opened)
        self.rect(4, y-17, self.w-8, 17, ROLL)
        self.text('▾' if opened else '▸', 7, y-12, 9)
        self.text(title, 17, y-12, 9, bold=True)
        self.hit(4, y-17, self.w-8, 17, ('ROLLOUT', key, title), title)
        if opened:
            self.rect(4, y-17-body_height, self.w-8, body_height, BODY)
        return y-17, opened

    def tooltip(self):
        """Draw a Max-style tooltip for a hit hovered longer than half a second."""
        pointer = _hover.get(self.key)
        since = _hover_since.get(self.key)
        if pointer is None or since is None or time.monotonic()-since[1] < .55:
            return
        hit = lookup_key(self.key, *pointer)
        if not hit or not hit[5]:
            return
        label = str(hit[5])
        if not label or label in {'Search All Objects'}:
            return
        tw = self.text_width(label, 9)+10
        x = min(pointer[0]+12, self.w-tw-2)
        y = pointer[1]-22 if pointer[1] > 26 else pointer[1]+14
        saved = self.oy
        self.oy = 0
        self.rect(x, y, tw, 16, (.12, .12, .12, .96))
        self.text(label, x+5, y+4, 9, (.95, .95, .95, 1))
        self.oy = saved


def lookup_key(key, x, y):
    for hit in reversed(_targets.get(key, ())):
        hx, hy, w, h, *_ = hit
        if hx <= x < hx+w and hy <= y < hy+h:
            return hit
    return None


def lookup(area, x, y):
    return lookup_key(area.as_pointer(), x, y)


def hover_target(area, x, y):
    hit = lookup(area, x, y)
    return None if hit is None else (round(hit[0]), round(hit[1]), str(hit[5]))


# Main toolbar: the 46 DefaultUI.cuix items in order. None is a separator.
REF_LABELS = {'VIEW': 'View', 'SCREEN': 'Screen', 'WORLD': 'World', 'PARENT': 'Parent', 'LOCAL': 'Local',
              'GIMBAL': 'Gimbal', 'GRID': 'Grid', 'WORKING': 'Working', 'LOCAL_ALIGNED': 'Local Aligned', 'PICK': 'Pick'}
FILTER_LABELS = {'ALL': 'All', 'GEOMETRY': 'Geometry', 'SHAPES': 'Shapes', 'LIGHTS': 'Lights', 'CAMERAS': 'Cameras',
                 'HELPERS': 'Helpers', 'WARPS': 'Warps', 'BONE': 'Bone'}
REGION_ICONS = {'RECT': 'box', 'CIRCLE': 'circle', 'FENCE': 'fence', 'LASSO': 'lasso', 'PAINT': 'paint_select'}
PIVOT_ICONS = {'INDIVIDUAL_ORIGINS': 'pivot', 'MEDIAN_POINT': 'selection_center', 'BOUNDING_BOX_CENTER': 'selection_center',
               'CURSOR': 'transform_center', 'ACTIVE_ELEMENT': 'pivot'}


def _tool_id(context):
    tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    return tool.idname if tool else ''


def _picking(context, purpose):
    return context.window_manager.bsm.pick_mode == purpose


def toolbar(context):
    c = Canvas(context)
    w, h = c.w, c.h
    c.rect(0, 0, w, h, BG)
    state = context.window_manager.bsm
    ts = context.scene.tool_settings
    y = max(0, (h-24)/2)
    tool = _tool_id(context)
    x = [4.]

    def gap():
        c.line([(x[0]+2, y+3), (x[0]+2, y+21)], (.20, .20, .20, 1))
        x[0] += 6

    def b(name, action, tip, selected=False, flyout=False, enabled=True, width=24):
        c.button(x[0], y, width, 24, icon=name, action=action, selected=selected, flat=True, enabled=enabled, tip=tip)
        if flyout:
            c.c.polygon([(v*c.u, z*c.u) for v, z in ((x[0]+width-1, y+1), (x[0]+width-1, y+5), (x[0]+width-5, y+1))], DIM)
        x[0] += width+1

    def drop(width, label, action, tip):
        c.dropdown(x[0], y+4, width, label, action, tip)
        x[0] += width+3

    b('undo', rmb(op('ed.undo'), menu('TOPBAR_MT_undo_history')), 'Undo')
    b('redo', rmb(op('ed.redo'), menu('TOPBAR_MT_undo_history')), 'Redo')
    gap()
    b('link', op('bsm.pick_object', purpose='LINK'), 'Select and Link', _picking(context, 'LINK'))
    b('unlink', op('bsm.toolbar_action', action='UNLINK'), 'Unlink Selection')
    b('bind', op('bsm.pick_object', purpose='BIND'), 'Bind to Space Warp', _picking(context, 'BIND'))
    gap()
    drop(52, FILTER_LABELS.get(state.selection_filter, 'All'), menu('BSM_MT_selection_filter'), 'Selection Filter')
    b('cursor', op('bsm.tool', tool='SELECT'), 'Select Object (Q)', tool.startswith('builtin.select'))
    b('select_list', op('bsm.select_from_scene'), 'Select by Name (H)')
    b(REGION_ICONS.get(state.region_type, 'box'), menu('BSM_MT_region_flyout'), 'Rectangular Selection Region', flyout=True)
    b('window_crossing', toggle(state, 'window_selection'), 'Window/Crossing (Shift+O)', state.window_selection)
    gap()
    typein = op('bsm.transform_typein')
    b('move', rmb(op('bsm.tool', tool='MOVE'), typein), 'Select and Move (W)', tool in {'builtin.move', 'bsm.max_move'})
    b('rotate', rmb(op('bsm.tool', tool='ROTATE'), typein), 'Select and Rotate (E)', tool in {'builtin.rotate', 'bsm.max_rotate'})
    b('scale', rmb(op('bsm.tool', tool='SCALE'), menu('BSM_MT_scale_flyout')), 'Select and Uniform Scale (R)', tool in {'builtin.scale', 'bsm.max_scale'}, flyout=True)
    b('select_place', op('bsm.place_surface'), 'Select and Place (Y)', _picking(context, 'PLACE'), flyout=True)
    drop(56, state.ref_pick if state.ref_coord == 'PICK' and state.ref_pick else REF_LABELS.get(state.ref_coord, 'View'), menu('BSM_MT_ref_coord'), 'Reference Coordinate System')
    b(PIVOT_ICONS.get(ts.transform_pivot_point, 'pivot'), menu('BSM_MT_pivot_center'), 'Use Pivot Point Center', flyout=True)
    gap()
    b('manipulate', toggle(state, 'manipulate'), 'Select and Manipulate', state.manipulate)
    b('keyboard_override', toggle(state, 'keyboard_override'), 'Keyboard Shortcut Override Toggle', state.keyboard_override)
    gap()
    snaps = rmb(toggle(ts, 'use_snap'), op('bsm.settings_popup', kind='SNAPS'))
    b({'2D': 'snap2', '2.5D': 'snap25'}.get(state.snap_mode, 'snap3'), snaps, 'Snaps Toggle (S)', ts.use_snap, flyout=True)
    b('snap_angle', rmb(toggle(ts, 'use_snap_rotate'), op('bsm.settings_popup', kind='SNAPS')), 'Angle Snap Toggle (A)', ts.use_snap_rotate)
    b('snap_percent', rmb(toggle(ts, 'use_snap_scale'), op('bsm.settings_popup', kind='SNAPS')), 'Percent Snap Toggle', ts.use_snap_scale)
    b('spinner_snap', rmb(toggle(state, 'spinner_snap'), op('bsm.settings_popup', kind='SNAPS')), 'Spinner Snap Toggle', state.spinner_snap)
    gap()
    b('manage_sets', op('bsm.manage_sets'), 'Manage Selection Sets...')
    if _editing and _editing.get('owner') == state and _editing.get('attr') == 'new_set_name':
        c.field(x[0], y+4, 116, state, 'new_set_name', spinner=False)
    else:
        c.rect(x[0], y+4, 116, 16, FIELD)
        c.text(state.new_set_name or 'Create Selection Set', x[0]+4, y+8, 9, TEXT if state.new_set_name else DIM)
        c.hit(x[0], y+4, 104, 16, prop(state, 'new_set_name'), 'Named Selection Sets')
        c.c.polygon([(v*c.u, z*c.u) for v, z in ((x[0]+106, y+14), (x[0]+112, y+14), (x[0]+109, y+10))], TEXT)
        c.hit(x[0]+104, y+4, 12, 16, menu('BSM_MT_selection_sets'), 'Named Selection Sets')
    x[0] += 119
    gap()
    b('mirror', op('bsm.mirror'), 'Mirror...')
    b('align', rmb(op('bsm.max_command', command='ALIGN'), menu('BSM_MT_align_flyout')), 'Align... (Alt+A)', _picking(context, 'ALIGN'), flyout=True)
    gap()
    b('explorer', op('bsm.editor', kind='SCENE'), 'Toggle Scene Explorer')
    b('layer_explorer', op('bsm.max_command', command='LAYER_EXPLORER'), 'Toggle Layer Explorer')
    gap()
    b('toggle_ribbon', toggle(state, 'ribbon_visible'), 'Toggle Ribbon', state.ribbon_visible)
    b('curve', op('bsm.editor', kind='GRAPH'), 'Curve Editor...')
    b('schematic', op('bsm.max_command', command='SCHEMATIC_VIEW'), 'Schematic View (Open)')
    gap()
    compact = state.last_material_editor == 'COMPACT'
    b('compact_material' if compact else 'material', rmb(op('bsm.editor', kind='MATERIAL_LAST'), menu('BSM_MT_material_flyout')),
      'Compact Material Editor (M)' if compact else 'Slate Material Editor (M)', flyout=True)
    gap()
    b('render_setup', op('bsm.editor', kind='RENDER'), 'Render Setup... (F10)')
    b('rendered_frame', op('render.view_show'), 'Rendered Frame Window')
    b({'ITERATIVE': 'render_iterative', 'ACTIVESHADE': 'activeshade'}.get(state.render_mode, 'render'),
      rmb(op('bsm.render_view'), menu('BSM_MT_render_flyout')), 'Render Production (Shift+Q)', flyout=True)
    # Projects / Autobackup toolbars that ship docked beside the main toolbar.
    if w-x[0] > 260:
        x[0] += 6
        folder = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else 'Untitled'
        label = folder if len(folder) < 24 else folder[:10]+'…'+folder[-12:]
        drop(150, label, menu('TOPBAR_MT_file_open_recent'), 'Project Folder')
        b('project_folder', op('wm.open_mainfile'), 'Open File...')
        b('project_set', op('bsm.max_command', command='CONFIGURE_PATHS'), 'Configure Project Paths...')
        b('project_new', op('wm.read_homefile', use_empty=False), 'New Scene')
        b('project_config', op('bsm.max_command', command='CONFIGURE_PATHS'), 'Project Settings')
        gap()
        paths = context.preferences.filepaths
        b('save', toggle(paths, 'use_auto_save_temporary_files'), 'Autobackup', paths.use_auto_save_temporary_files)
    c.line([(0, 0), (w, 0)], (.19, .19, .19, 1))
    c.tooltip()


# Arnold-equivalent render toolbar (MAXtoA.cuix order) docked at the far left.
STRIP = (('arv', op('render.view_show'), 'Arnold RenderView → Render Result'),
         ('arv_render', op('bsm.render_view'), 'Render in Arnold Render View → Render active view'),
         ('arv_ipr', op('bsm.toolbar_action', action='IPR'), 'IPR → Rendered viewport shading'),
         ('flow_render', None, 'Flow Render (cloud; not available)'),
         ('flow_monitor', None, 'Flow Render Monitor (not available)'),
         ('denoiser', op('bsm.toolbar_action', action='DENOISE'), 'Enable Denoiser(s)'),
         None,
         ('arnold_light', ('ARM', 'AREA'), 'Arnold Light → Area light'),
         ('arnold_procedural', op('wm.link'), 'Arnold Procedural → Link from .blend'),
         ('arnold_alembic', op('wm.alembic_import'), 'Arnold Alembic → Import Alembic'),
         ('arnold_volume', op('object.volume_import'), 'Arnold Volume → Import OpenVDB'),
         None,
         ('bake_geometry', op('bsm.max_command', command='SNAPSHOT'), 'Bake Selected Geometries → Snapshot mesh'),
         ('arnold_props', op('bsm.object_properties'), 'Add Arnold Properties Modifier → Object Properties'),
         None,
         ('aovs', op('bsm.toolbar_action', action='AOVS'), 'Arbitrary Output Variables (AOVs) → Render passes'),
         ('light_groups', op('bsm.toolbar_action', action='LIGHT_GROUPS'), 'AOV Light Group Manager → Light groups'),
         ('operator_graph', None, 'Operator Graph (not available)'))


def strip(context):
    c = Canvas(context)
    c.rect(0, 0, c.w, c.h, BG)
    y = c.h-4
    for item in STRIP:
        if item is None:
            y -= 6
            c.line([(5, y+3), (c.w-5, y+3)], (.20, .20, .20, 1))
            continue
        name, action, tip = item
        y -= 26
        if y < 2:
            break
        c.button((c.w-24)/2, y, 24, 24, icon=name, action=action, flat=True, enabled=action is not None, tip=tip)
    c.tooltip()


# Command Panel ------------------------------------------------------------
CREATE = {
    'GEOMETRY': (
        ('Standard Primitives', (('BOX', 'Box'), ('CONE', 'Cone'), ('SPHERE', 'Sphere'), ('GEOSPHERE', 'GeoSphere'),
                                 ('CYLINDER', 'Cylinder'), ('TUBE', 'Tube'), ('TORUS', 'Torus'), ('PYRAMID', 'Pyramid'),
                                 ('TEAPOT', 'Teapot'), ('PLANE', 'Plane'), ('TEXTPLUS', 'TextPlus'))),
        ('Extended Primitives', ((None, 'Hedra'), (None, 'Torus Knot'), ('CHAMFER_BOX', 'ChamferBox'), ('CHAMFER_CYL', 'ChamferCyl'),
                                 (None, 'OilTank'), ('CAPSULE', 'Capsule'), (None, 'Spindle'), (None, 'L-Ext'), (None, 'Gengon'),
                                 (None, 'C-Ext'), (None, 'RingWave'), (None, 'Hose'), (None, 'Prism'))),
        ('Compound Objects', ((None, 'Morph'), (None, 'Scatter'), (None, 'Conform'), (None, 'Connect'), (None, 'BlobMesh'),
                              (None, 'ShapeMerge'), ('BOOLEAN', 'Boolean'), (None, 'Terrain'), (None, 'Loft'), (None, 'Mesher'),
                              ('BOOLEAN', 'ProBoolean'), (None, 'ProCutter'))),
        ('Particle Systems', ((None, 'PF Source'), (None, 'Spray'), (None, 'Snow'), (None, 'Blizzard'), (None, 'PArray'),
                              (None, 'PCloud'), (None, 'Super Spray'))),
        ('Patch Grids', ((None, 'Quad Patch'), (None, 'Tri Patch'))),
        ('NURBS Surfaces', (('POINT_SURFACE', 'Point Surf'), ('CV_SURFACE', 'CV Surf'))),
    ),
    'SHAPES': (
        ('Splines', (('LINE', 'Line'), ('RECTANGLE', 'Rectangle'), ('CIRCLE', 'Circle'), ('ELLIPSE', 'Ellipse'), ('ARC', 'Arc'),
                     ('DONUT', 'Donut'), ('NGON', 'NGon'), ('STAR', 'Star'), ('TEXT', 'Text'), ('HELIX', 'Helix'),
                     (None, 'Egg'), (None, 'Section'), (None, 'Freehand'))),
        ('NURBS Curves', (('POINT_CURVE', 'Point Curve'), ('CV_CURVE', 'CV Curve'))),
        ('Extended Splines', ((None, 'WRectangle'), (None, 'Channel'), (None, 'Angle'), (None, 'Tee'), (None, 'Wide Flange'))),
    ),
    'LIGHTS': (
        ('Photometric', (('TARGET_LIGHT', 'Target Light'), ('FREE_LIGHT', 'Free Light'), ('SUN_POSITIONER', 'Sun Positioner'))),
        ('Standard', (('TARGET_SPOT', 'Target Spot'), ('FREE_SPOT', 'Free Spot'), ('TARGET_DIRECT', 'Target Direct'),
                      ('FREE_DIRECT', 'Free Direct'), ('OMNI', 'Omni'), ('SKYLIGHT', 'Skylight'))),
        ('Arnold', (('AREA', 'Arnold Light'),)),
    ),
    'CAMERAS': (('Standard', (('PHYSICAL_CAMERA', 'Physical'), ('TARGET_CAMERA', 'Target'), ('FREE_CAMERA', 'Free'))),),
    'HELPERS': (('Standard', (('DUMMY', 'Dummy'), (None, 'Container'), (None, 'Crowd'), (None, 'Delegate'), (None, 'ExposeTm'),
                              ('GRID', 'Grid'), ('POINT', 'Point'), (None, 'Protractor'), (None, 'Tape'), ('COMPASS', 'Compass'),
                              ('ARROW', 'Arrow'))),),
    'SPACEWARPS': (
        ('Forces', (('MOTOR', 'Motor'), ('PUSH', 'Push'), ('VORTEX', 'Vortex'), ('DRAG', 'Drag'), (None, 'PBomb'),
                    ('PATH_FOLLOW', 'Path Follow'), ('DISPLACE_WARP', 'Displace'), ('GRAVITY', 'Gravity'), ('WIND', 'Wind'))),
        ('Deflectors', ((None, 'POmniFlect'), (None, 'PDynaFlect'), (None, 'SOmniFlect'), (None, 'UOmniFlect'), (None, 'Deflector'))),
        ('Geometric/Deformable', ((None, 'FFD(Box)'), (None, 'FFD(Cyl)'), (None, 'Wave'), (None, 'Ripple'), (None, 'Displace'),
                                  (None, 'Conform'), (None, 'Bomb'))),
    ),
    'SYSTEMS': (('Standard', (('BONES', 'Bones'), (None, 'Ring Array'), (None, 'Biped'), (None, 'Sunlight'), (None, 'Daylight'))),),
}
CATEGORIES = (('GEOMETRY', 'geometry', 'Geometry'), ('SHAPES', 'shapes', 'Shapes'), ('LIGHTS', 'lights', 'Lights'),
              ('CAMERAS', 'cameras', 'Cameras'), ('HELPERS', 'helpers', 'Helpers'), ('SPACEWARPS', 'spacewarps', 'Space Warps'),
              ('SYSTEMS', 'systems', 'Systems'))
PARAMETRIC = {'BOX', 'CONE', 'SPHERE', 'GEOSPHERE', 'CYLINDER', 'TUBE', 'TORUS', 'PYRAMID', 'TEAPOT', 'PLANE'}


def subcategory(state):
    subs = CREATE[state.category]
    names = [name for name, _ in subs]
    return state.subcategory if state.subcategory in names else names[0]


def create_entries(state):
    if state.tool_search:
        needle = state.tool_search.casefold()
        return [(k, n) for subs in CREATE.values() for _, items in subs for k, n in items if needle in n.casefold()]
    return list(dict(CREATE[state.category])[subcategory(state)])


def command(context):
    c = Canvas(context)
    w, h = c.w, c.h
    state = context.window_manager.bsm
    obj = context.view_layer.objects.active
    if state.tab == 'MODIFY' and state.stack_pinned:
        obj = bpy.data.objects.get(state.stack_pinned) or obj
    c.rect(0, 0, w, h, BG)
    key = (c.key, state.tab)
    c.oy = _scroll.get(key, 0.)
    top = h-53
    c.clip = (0., top)
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(0, 0, int(context.region.width), int(top*c.u))
    y = top-2
    try:
        bottom = {'CREATE': _create, 'MODIFY': _modify, 'HIERARCHY': _hierarchy, 'MOTION': _motion,
                  'DISPLAY': _display, 'UTILITIES': _utilities}.get(state.tab, _create)(c, y, context, state, obj)
    finally:
        gpu.state.scissor_test_set(False)
    content = top-(bottom if bottom is not None else 0)
    _scroll[key] = max(0., min(c.oy, max(0., content-top+10)))
    c.oy, c.clip = 0., None
    c.rect(0, top, w, h-top, BG)
    # Keep the tabs clear of Blender's hidden-region arrows on the top and right edges.
    y = h-29
    step = min(25., (w-12)/6)
    for i, (tab, icon, tip) in enumerate((('CREATE', 'create', 'Create'), ('MODIFY', 'modify', 'Modify'),
                                          ('HIERARCHY', 'hierarchy', 'Hierarchy'), ('MOTION', 'motion', 'Motion'),
                                          ('DISPLAY', 'display', 'Display'), ('UTILITIES', 'utilities', 'Utilities'))):
        c.button(3+i*step, y, step-1, 24, icon=icon, action=('SET', state, 'tab', tab), flat=True, selected=state.tab == tab, tip=tip)
    c.field(4, y-21, w-8, state, 'tool_search', spinner=False)
    if not state.tool_search and not (_editing and _editing.get('attr') == 'tool_search'):
        c.rect(5, y-20, w-10, 14, FIELD)
        c.text('Search All Objects...', 8, y-17, 9, DIM)
    c.icon('search', w-20, y-20, 14)
    c.tooltip()


def _name_color(c, y, context, state, obj):
    y, opened = c.rollout('Name and Color', y, 25)
    if opened:
        c.field(9, y-20, c.w-38, obj if obj else state, 'name' if obj else 'next_name', spinner=False)
        color = obj.color if obj else state.next_color
        c.rect(c.w-24, y-20, 16, 16, tuple(color))
        c.hit(c.w-24, y-20, 16, 16, op('bsm.surface_color'), 'Object Color')
        y -= 25
    return y


def _create(c, y, context, state, obj):
    from . import params
    w = c.w
    for i, (key, icon, tip) in enumerate(CATEGORIES):
        c.button(4+i*19, y-20, 18, 20, icon=icon, action=('SET', state, 'category', key), flat=True, selected=state.category == key, tip=tip)
    y -= 42
    c.dropdown(4, y, w-8, subcategory(state), menu('BSM_MT_subcategories'))
    y -= 6
    entries = create_entries(state)
    height = 28+((len(entries)+1)//2)*20
    y, opened = c.rollout('Object Type', y, height)
    if opened:
        c.checkbox(w*.5-24, y-15, 'AutoGrid', state, 'autogrid')
        bw = (w-23)/2
        for i, (kind, label) in enumerate(entries):
            c.button(9+(i % 2)*(bw+5), y-37-(i//2)*20, bw, 17, label, ('ARM', kind) if kind else None,
                     selected=bool(kind) and state.active_creation == kind, enabled=kind is not None,
                     tip=label if kind else f'{label} (no Blender equivalent)')
        if not entries:
            c.text('No tools in this category', 10, y-36, 9, DIM)
        y -= height
    y -= 5
    y = _name_color(c, y, context, state, obj)
    kind = state.active_creation or (obj.bsm_prim.kind if obj and hasattr(obj, 'bsm_prim') else '')
    if kind not in PARAMETRIC:
        return _light_camera_params(c, y, context, obj) if obj else y
    methods = params.CREATION_METHODS.get(kind, ())
    current = creation_method(state, kind)
    y -= 5
    y, opened = c.rollout('Creation Method', y, 24)
    if opened:
        for i, (ident, label) in enumerate(methods):
            c.radio(14+i*(w-28)/max(1, len(methods)), y-18, label, current == ident, call(set_creation_method, kind, ident))
        y -= 24
    keyboard = params.KEYBOARD.get(kind, ())
    y -= 5
    y, opened = c.rollout('Keyboard Entry', y, 86+20*len(keyboard))
    if opened:
        for i, axis in enumerate('XYZ'):
            c.text_right(axis+':', w*.5, y-17-i*19, 9)
            c.field(w*.5+3, y-21-i*19, w*.5-11, state, 'keyboard_location', i)
        for j, (attr, label) in enumerate(keyboard):
            c.param(y-80-j*20, state.next_prim, attr, label)
        c.button(w*.3, y-82-20*len(keyboard), w*.4, 17, 'Create', op('bsm.keyboard_create', kind=kind))
        y -= 86+20*len(keyboard)
    target = obj if obj and getattr(obj, 'bsm_prim', None) and obj.bsm_prim.kind == kind and state.created_this_session == obj.name else None
    owner = target.bsm_prim if target else state.next_prim
    return _parameters(c, y-5, kind, owner)


def _parameters(c, y, kind, owner):
    from . import params
    rows = params.PARAMETERS.get(kind, ())
    height = 6+sum(16 if _row_kind(owner, attr) == 'BOOL' else (18 if _row_kind(owner, attr) != 'ENUM' else 18*len(_enum_items(owner, attr))+4) for attr, _ in rows)
    y, opened = c.rollout('Parameters', y, height+4, key=('PARAMS', kind))
    if not opened:
        return y
    y -= 4
    for attr, label in rows:
        kind_of = _row_kind(owner, attr)
        if kind_of == 'BOOL':
            y -= 16
            c.checkbox(c.w*.18, y, label.rstrip(':'), owner, attr)
        elif kind_of == 'ENUM':
            y -= 16
            c.text(label, 12, y+2, 9)
            for ident, name in _enum_items(owner, attr):
                y -= 18
                c.radio(c.w*.30, y+4, name, getattr(owner, attr) == ident, ('SET', owner, attr, ident))
            y -= 2
        else:
            y -= 18
            c.param(y, owner, attr, label)
    return y-8


def _row_kind(owner, attr):
    rna = rna_property(owner, attr)
    if rna is None:
        return 'NUM'
    return {'BOOLEAN': 'BOOL', 'ENUM': 'ENUM'}.get(rna.type, 'NUM')


def _enum_items(owner, attr):
    rna = rna_property(owner, attr)
    return [(e.identifier, e.name) for e in rna.enum_items] if rna is not None else []


_methods = {}


def creation_method(state, kind):
    from . import params
    methods = params.CREATION_METHODS.get(kind, ())
    default = methods[-1][0] if kind in {'BOX', 'PLANE'} else (methods[0][0] if methods else '')
    if kind in {'SPHERE', 'GEOSPHERE', 'CYLINDER', 'CONE', 'TUBE', 'TORUS', 'TEAPOT'} and len(methods) > 1:
        default = methods[1][0]
    return _methods.get(kind, default)


def set_creation_method(context, kind, ident):
    _methods[kind] = ident


def _light_camera_params(c, y, context, obj):
    w = c.w
    if obj.type == 'LIGHT':
        y -= 5
        y, opened = c.rollout('Intensity/Color/Attenuation', y, 66, key=('LIGHT', obj.name))
        if opened:
            c.param(y-22, obj.data, 'energy', 'Multiplier:')
            c.text_right('Color:', w*.5, y-38, 9)
            c.rect(w*.5+3, y-42, 30, 14, (*obj.data.color, 1))
            c.hit(w*.5+3, y-42, 30, 14, op('bsm.surface_color'), 'Light Color')
            c.checkbox(14, y-60, 'Cast Shadows', obj.data, 'use_shadow')
            y -= 66
    elif obj.type == 'CAMERA':
        y -= 5
        y, opened = c.rollout('Parameters', y, 86, key=('CAMERA', obj.name))
        if opened:
            c.param(y-22, obj.data, 'lens', 'Lens:')
            c.param(y-42, obj.data, 'angle', 'FOV:')
            c.checkbox(14, y-60, 'Orthographic Projection', value=obj.data.type == 'ORTHO',
                       action=('SET', obj.data, 'type', 'PERSP' if obj.data.type == 'ORTHO' else 'ORTHO'))
            c.param(y-82, obj.data, 'clip_start', 'Near Clip:')
            y -= 86
    elif obj.type == 'EMPTY':
        y -= 5
        y, opened = c.rollout('Parameters', y, 30, key=('EMPTY', obj.name))
        if opened:
            c.param(y-22, obj, 'empty_display_size', 'Size:')
            y -= 30
    return y


# Modify panel -------------------------------------------------------------
def base_label(obj):
    if obj is None:
        return ''
    prim = getattr(obj, 'bsm_prim', None)
    if prim is not None and prim.kind:
        from . import params
        return params.NAMES.get(prim.kind, prim.kind.title())
    return {'MESH': 'Editable Poly', 'CURVE': 'Editable Spline', 'SURFACE': 'NURBS Surface', 'FONT': 'Text',
            'LIGHT': {'POINT': 'Omni Light', 'SPOT': 'Spot Light', 'SUN': 'Direct Light', 'AREA': 'Area Light'}.get(getattr(obj.data, 'type', ''), 'Light'),
            'CAMERA': 'Physical Camera', 'EMPTY': {'CUBE': 'Dummy', 'PLAIN_AXES': 'Point'}.get(obj.empty_display_type, 'Helper'),
            'ARMATURE': 'Bone', 'LATTICE': 'FFD Lattice'}.get(obj.type, obj.type.title())


def editable_poly(obj):
    return obj is not None and obj.type == 'MESH' and not (getattr(obj, 'bsm_prim', None) and obj.bsm_prim.kind)


LEVELS = ((1, 'Vertex', 'vertex'), (2, 'Edge', 'edge'), (3, 'Border', 'border'), (4, 'Polygon', 'polygon'), (5, 'Element', 'element'))
STACK_ROW = 17


def stack_rows(obj, state):
    rows = [('MOD', mod.name, 0) for mod in reversed(obj.modifiers)] if obj else []
    if obj:
        rows.append(('BASE', '', 0))
        if editable_poly(obj) and state.stack_expanded:
            rows.extend(('LEVEL', label, level) for level, label, _ in LEVELS)
    return rows


def _modify(c, y, context, state, obj):
    w = c.w
    if obj is None:
        c.text('Select an object', 10, y-16, 9, DIM)
        return y-24
    c.field(5, y-17, w-30, obj, 'name', spinner=False)
    c.rect(w-22, y-17, 16, 16, tuple(obj.color))
    c.hit(w-22, y-17, 16, 16, op('bsm.surface_color'), 'Object Color')
    y -= 39
    c.dropdown(5, y, w-10, 'Modifier List', menu('BSM_MT_modifier_list'))
    if state.show_mod_buttons:
        names = ('Edit Poly', 'TurboSmooth', 'Shell', 'Symmetry', 'Bend', 'Taper', 'Twist', 'FFD 2x2x2')
        from .commands import modifier_available
        y -= 4
        for i, name in enumerate(names):
            bw = (w-16)/2
            c.button(5+(i % 2)*(bw+6), y-18-(i//2)*19, bw, 17, name, op('bsm.max_modifier', name=name), enabled=modifier_available(name))
        y -= 4+19*((len(names)+1)//2)
    y -= 4
    rows = stack_rows(obj, state)
    box_h = max(92, min(len(rows), 12)*STACK_ROW+6)
    c.rect(5, y-box_h, w-10, box_h, (.21, .21, .21, 1))
    selected_row = ('MOD', state.active_modifier) if state.active_modifier in obj.modifiers else ('BASE', '')
    level = state.component if context.mode == 'EDIT_MESH' else 0
    layout = _stack_layout[c.key] = []
    for i, (kind, name, lvl) in enumerate(rows[:12]):
        ry = y-3-(i+1)*STACK_ROW
        layout.append((ry+c.oy, kind, name))
        if kind == 'LEVEL':
            active = level == lvl
            if active:
                c.rect(24, ry, w-31, STACK_ROW-1, (.80, .70, .10, 1))
            c.text(name, 40, ry+4, 9, (.08, .08, .08, 1) if active else TEXT)
            c.hit(24, ry, w-31, STACK_ROW-1, op('bsm.component', level=lvl), name)
            continue
        is_selected = (kind, name) == selected_row
        if is_selected:
            c.rect(7, ry, w-14, STACK_ROW-1, BLUE)
        if kind == 'MOD':
            mod = obj.modifiers[name]
            on = mod.show_viewport
            c.icon('bulb_on' if on else 'bulb_off', 9, ry+1, 14)
            c.hit(8, ry, 16, STACK_ROW-1, call(toggle_modifier, obj.name, name), 'Turn modifier on/off')
            c.text(name, 28, ry+4, 9, TEXT if on else DIM)
        else:
            if editable_poly(obj):
                c.text('−' if state.stack_expanded else '+', 11, ry+4, 10)
                c.hit(8, ry, 14, STACK_ROW-1, toggle(state, 'stack_expanded'), 'Expand sub-object levels')
            c.text(base_label(obj), 28, ry+4, 9)
        c.hit(24 if kind == 'MOD' else 22, ry, w-31, STACK_ROW-1, rmb(('STACK', obj.name, name), call(stack_context, obj.name, name)), name or base_label(obj))
    y -= box_h+4
    mod = obj.modifiers.get(state.active_modifier)
    tools = (('pin', toggle_pin_action(state, obj), 'Pin Stack', bool(state.stack_pinned)),
             ('end_result', toggle(state, 'show_end_result'), 'Show end result on/off toggle', state.show_end_result),
             ('make_unique', op('bsm.stack_action', action='MAKE_UNIQUE', modifier=''), 'Make unique', False),
             ('remove_modifier', op('bsm.stack_action', action='DELETE', modifier=mod.name) if mod else None, 'Remove modifier from the stack', False),
             ('configure_sets', menu('BSM_MT_modifier_sets'), 'Configure Modifier Sets', False))
    for i, (icon, action, tip, on) in enumerate(tools):
        enabled = action is not None and not (icon == 'make_unique' and not (obj.data and obj.data.users > 1))
        c.button(5+i*24, y-20, 22, 20, icon=icon, action=action, selected=on, flat=True, enabled=enabled, tip=tip)
    y -= 26
    if mod:
        return _modifier_rollouts(c, y, context, obj, mod)
    if getattr(obj, 'bsm_prim', None) and obj.bsm_prim.kind:
        return _parameters(c, y, obj.bsm_prim.kind, obj.bsm_prim)
    if obj.type == 'MESH':
        return _editable_poly(c, y, context, state, obj)
    if obj.type == 'CURVE':
        return _editable_spline(c, y, obj)
    if obj.type == 'FONT':
        y, opened = c.rollout('Parameters', y, 88, key=('TEXT', obj.name))
        if opened:
            c.text('Text:', 12, y-16, 9)
            c.field(12, y-36, w-24, obj.data, 'body', spinner=False)
            c.param(y-56, obj.data, 'size', 'Size:')
            c.param(y-76, obj.data, 'space_character', 'Tracking:')
            y -= 88
        return y
    return _light_camera_params(c, y, context, obj)


def toggle_pin_action(state, obj):
    return ('SET', state, 'stack_pinned', '' if state.stack_pinned else obj.name)


def toggle_modifier(context, obj_name, mod_name):
    obj = bpy.data.objects.get(obj_name)
    mod = obj.modifiers.get(mod_name) if obj else None
    if mod:
        mod.show_viewport = mod.show_render = not mod.show_viewport


def stack_context(context, obj_name, mod_name):
    context.window_manager.bsm.stack_context = mod_name
    context.window_manager.bsm.active_modifier = mod_name
    bpy.ops.wm.call_menu(name='BSM_MT_stack_context')


MODIFIER_FIELDS = {
    'SUBSURF': (('levels', 'Iterations:'), ('render_levels', 'Render Iters:'), ('quality', 'Quality:'), ('use_limit_surface', 'Smooth Result')),
    'BEVEL': (('width', 'Amount:'), ('segments', 'Segments:'), ('profile', 'Tension:'), ('angle_limit', 'Angle:'), ('use_clamp_overlap', 'Limit Effect'), ('harden_normals', 'Smooth')),
    'SOLIDIFY': (('thickness', 'Amount:'), ('offset', 'Offset:'), ('use_even_offset', 'Even'), ('use_rim', 'Straighten Corners')),
    'MIRROR': (('use_axis', 'Mirror Axis'), ('use_bisect_axis', 'Slice Along Mirror'), ('use_mirror_merge', 'Weld Seam'), ('merge_threshold', 'Threshold:')),
    'ARRAY': (('count', 'Count:'), ('relative_offset_displace', 'Offset'), ('use_merge_vertices', 'Weld')),
    'SIMPLE_DEFORM': (('angle', 'Angle:'), ('factor', 'Amount:'), ('deform_axis', 'Axis'), ('use_limits', 'Limit Effect'), ('limits', 'Limits')),
    'SMOOTH': (('factor', 'Relax Value:'), ('iterations', 'Iterations:')),
    'DECIMATE': (('ratio', 'Vertex %:'),),
    'DISPLACE': (('strength', 'Strength:'), ('mid_level', 'Center:'), ('direction', 'Direction')),
    'WAVE': (('height', 'Amplitude:'), ('width', 'Wave Length:'), ('speed', 'Speed:'), ('time_offset', 'Phase:')),
    'CAST': (('factor', 'Percent:'),),
    'WELD': (('merge_threshold', 'Threshold:'),),
    'LATTICE': (('strength', 'Strength:'),),
    'WIREFRAME': (('thickness', 'Struts Radius:'), ('use_replace', 'Struts Only')),
    'BOOLEAN': (('operation', 'Operation'), ('solver', 'Solver')),
    'SHRINKWRAP': (('wrap_method', 'Projection'), ('offset', 'Standoff:')),
    'SCREW': (('angle', 'Degrees:'), ('steps', 'Segments:'), ('axis', 'Direction'), ('use_merge_vertices', 'Weld Core')),
    'REMESH': (('voxel_size', 'Voxel Size:'),),
    'TRIANGULATE': (('quad_method', 'Quad Method'),),
    'WEIGHTED_NORMAL': (('weight', 'Weight:'), ('mode', 'Weighting')),
}
OBJECT_SLOTS = {'BOOLEAN': 'object', 'LATTICE': 'object', 'CURVE': 'object', 'SHRINKWRAP': 'target', 'ARMATURE': 'object',
                'SURFACE_DEFORM': 'target', 'MIRROR': 'mirror_object', 'CAST': 'object', 'DATA_TRANSFER': 'object'}


def _modifier_rollouts(c, y, context, obj, mod):
    w = c.w
    fields = MODIFIER_FIELDS.get(mod.type)
    if fields is None:
        fields = tuple((p.identifier, p.name+':') for p in mod.bl_rna.properties
                       if p.type in {'INT', 'FLOAT', 'BOOLEAN'} and not p.is_readonly and p.identifier not in {'show_viewport', 'show_render',
                       'show_in_editmode', 'show_on_cage', 'show_expanded', 'use_pin_to_last', 'is_override_data_editable', 'use_apply_on_spline'}
                       and getattr(p, 'array_length', 0) == 0)[:8]
    rows = []
    for attr, label in fields:
        if not hasattr(mod, attr):
            continue
        rna = rna_property(mod, attr)
        if rna.type == 'ENUM':
            rows.append(('ENUM', attr, label, 18))
        elif getattr(rna, 'array_length', 0):
            rows.append(('ARRAY', attr, label, 20))
        elif rna.type == 'BOOLEAN':
            rows.append(('BOOL', attr, label, 16))
        else:
            rows.append(('NUM', attr, label, 19))
    slot = OBJECT_SLOTS.get(mod.type)
    height = sum(r[3] for r in rows)+(24 if slot else 0)+30
    y, opened = c.rollout('Parameters', y, height, key=('MOD', obj.name, mod.name))
    if not opened:
        return y
    y -= 4
    for kind, attr, label, rh in rows:
        y -= rh
        if kind == 'NUM':
            c.param(y, mod, attr, label)
        elif kind == 'BOOL':
            c.checkbox(w*.18, y, label, mod, attr)
        elif kind == 'ENUM':
            c.text_right(label+':' if not label.endswith(':') else label, w*.42, y+4, 9)
            current = dict(_enum_items(mod, attr)).get(getattr(mod, attr), str(getattr(mod, attr)))
            c.dropdown(w*.42+3, y, w*.58-11, current, call(enum_menu, mod, attr))
        else:
            c.text(label, 10, y+4, 9)
            length = rna_property(mod, attr).array_length
            fw = (w*.62-10)/length
            for i in range(length):
                value = getattr(mod, attr)[i]
                if isinstance(value, bool):
                    c.button(w*.38+i*fw, y, fw-2, 16, 'XYZ'[i] if length == 3 else str(i), toggle(mod, attr, i), selected=value)
                else:
                    c.field(w*.38+i*fw, y, fw-2, mod, attr, i, spinner=False)
    if slot:
        y -= 24
        target = getattr(mod, slot)
        c.text_right('Object:' if slot != 'target' else 'Target:', w*.42, y+5, 9)
        c.button(w*.42+3, y, w*.58-11, 18, target.name if target else 'Pick Object', op('bsm.pick_object', purpose='MOD_OBJECT', data=mod.name))
    y -= 10
    c.button(10, y-18, w-20, 18, 'More Parameters...', op('bsm.surface_properties'))
    return y-26


_enum_owner = None


def enum_menu(context, owner, attr):
    global _enum_owner
    _enum_owner = (owner, attr)
    bpy.ops.wm.call_menu(name='BSM_MT_enum_choice')


# Editable Poly rollouts: titles and buttons follow EPoly.dlo dialog resources.
EDIT = {
    1: ('Edit Vertices', (('Remove', 'DISSOLVE_VERTS'), ('Break', 'BREAK'), ('Extrude', 'EXTRUDE_VERTS'), ('Weld', 'WELD'),
                          ('Chamfer', 'CHAMFER_VERTS'), ('Target Weld', 'TARGET_WELD'), ('Connect', 'CONNECT_VERTS'),
                          ('Remove Isolated Vertices', 'DELETE_LOOSE'))),
    2: ('Edit Edges', (('Insert Vertex', 'INSERT_VERTEX'), ('Remove', 'DISSOLVE_EDGES'), ('Split', 'SPLIT_EDGES'),
                       ('Extrude', 'EXTRUDE_EDGES'), ('Weld', 'WELD'), ('Chamfer', 'CHAMFER'), ('Target Weld', 'TARGET_WELD'),
                       ('Bridge', 'BRIDGE'), ('Connect', 'CONNECT_EDGES'), ('Create Shape From Selection', 'CREATE_SHAPE'),
                       ('Turn', 'TURN'))),
    3: ('Edit Borders', (('Extrude', 'EXTRUDE_EDGES'), ('Insert Vertex', 'INSERT_VERTEX'), ('Chamfer', 'CHAMFER'), ('Cap', 'CAP'),
                         ('Bridge', 'BRIDGE'), ('Connect', 'CONNECT_EDGES'), ('Create Shape From Selection', 'CREATE_SHAPE'))),
    4: ('Edit Polygons', (('Insert Vertex', 'POKE'), ('Extrude', 'EXTRUDE'), ('Outline', 'OUTLINE'), ('Bevel', 'BEVEL_POLY'),
                          ('Inset', 'INSET'), ('Bridge', 'BRIDGE'), ('Flip', 'FLIP'), ('Hinge From Edge', None),
                          ('Extrude Along Spline', None), ('Edit Triangulation', None), ('Retriangulate', 'RETRIANGULATE'), ('Turn', None))),
    5: ('Edit Elements', (('Insert Vertex', 'POKE'), ('Flip', 'FLIP'), ('Edit Triangulation', None), ('Retriangulate', 'RETRIANGULATE'), ('Turn', None))),
}
GEOMETRY = (('Repeat Last', 'REPEAT'), ('Create', 'CREATE_FACE'), ('Collapse', 'COLLAPSE'), ('Attach', 'ATTACH'), ('Detach', 'DETACH'),
            ('Slice Plane', 'SLICE'), ('QuickSlice', 'SLICE'), ('Cut', 'CUT'), ('MSmooth', 'MSMOOTH'), ('Tessellate', 'TESSELLATE'),
            ('Make Planar', 'PLANAR'), ('X', 'FLATTEN_X'), ('Y', 'FLATTEN_Y'), ('Z', 'FLATTEN_Z'), ('View Align', None), ('Grid Align', None),
            ('Relax', 'RELAX'), ('Hide Selected', 'HIDE'), ('Unhide All', 'UNHIDE'), ('Hide Unselected', 'HIDE_UNSELECTED'),
            ('Delete Isolated Vertices', 'DELETE_LOOSE'))


def _selection_count(context, obj, level):
    if context.mode != 'EDIT_MESH' or level == 0:
        return 'Whole Object Selected'
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    if level == 1:
        return f'{sum(v.select for v in bm.verts)} Vertices Selected'
    if level in {2, 3}:
        return f'{sum(e.select for e in bm.edges)} Edges Selected'
    return f'{sum(f.select for f in bm.faces)} Polygons Selected'


def _buttons(c, y, items, columns=2, height=18):
    w = c.w
    bw = (w-14-(columns-1)*4)/columns
    rows = 0
    i = 0
    for label, action in items:
        if len(label) > 14 and columns > 1:
            if i % columns:
                i += 1
            c.button(7, y-(i//columns+1)*(height+2), w-14, height, label, op('bsm.mesh_action', action=action) if action else None, enabled=action is not None)
            i += columns
            continue
        c.button(7+(i % columns)*(bw+4), y-(i//columns+1)*(height+2), bw, height, label,
                 op('bsm.mesh_action', action=action) if action else None, enabled=action is not None)
        i += 1
    rows = (i+columns-1)//columns
    return rows*(height+2)


def _layout_height(items, columns=2, height=18):
    i = 0
    for label, _ in items:
        if len(label) > 14 and columns > 1:
            if i % columns:
                i += 1
            i += columns
        else:
            i += 1
    return ((i+columns-1)//columns)*(height+2)


def _editable_poly(c, y, context, state, obj):
    w = c.w
    level = state.component if context.mode == 'EDIT_MESH' else 0
    space = context.space_data
    y, opened = c.rollout('Selection', y, 140)
    if opened:
        for i, (lvl, label, icon) in enumerate(LEVELS):
            c.button(10+i*26, y-28, 24, 24, icon=icon, action=op('bsm.component', level=lvl), selected=level == lvl, flat=True, tip=f'{label} ({lvl})')
        c.checkbox(12, y-46, 'By Vertex', enabled=False, value=False)
        view = _viewport_space(context)
        c.checkbox(12, y-62, 'Ignore Backfacing', value=bool(view and not view.shading.show_xray),
                   action=call(toggle_backfacing))
        c.checkbox(12, y-78, 'By Angle:', enabled=False, value=False)
        bw = (w-24)/2
        for i, (label, action) in enumerate((('Shrink', 'SHRINK'), ('Grow', 'GROW'), ('Ring', 'RING'), ('Loop', 'LOOP'))):
            c.button(10+(i % 2)*(bw+4), y-98-(i//2)*20, bw, 18, label, op('bsm.mesh_action', action=action), enabled=level > 0)
        c.text(_selection_count(context, obj, level), 14, y-134, 9, DIM)
        y -= 140
    y -= 5
    ts = context.scene.tool_settings
    y, opened = c.rollout('Soft Selection', y, 50)
    if opened:
        c.checkbox(12, y-18, 'Use Soft Selection', ts, 'use_proportional_edit')
        c.param(y-40, ts, 'proportional_size', 'Falloff:')
        y -= 50
    if level:
        title, items = EDIT[level]
        height = _layout_height(items)+8
        y -= 5
        y, opened = c.rollout(title, y, height)
        if opened:
            _buttons(c, y-2, items)
            y -= height
    y -= 5
    height = _layout_height(GEOMETRY, 2)+8
    y, opened = c.rollout('Edit Geometry', y, height)
    if opened:
        _buttons(c, y-2, GEOMETRY, 2)
        y -= height
    if level in {4, 5}:
        y -= 5
        y, opened = c.rollout('Polygon: Material IDs', y, 50)
        if opened:
            c.param(y-22, state, 'material_id', 'Set ID:')
            bw = (w-24)/2
            c.button(10, y-44, bw, 18, 'Set ID', op('bsm.mesh_action', action='SET_ID'))
            c.button(14+bw, y-44, bw, 18, 'Select ID', op('bsm.mesh_action', action='SELECT_ID'))
            y -= 50
        y -= 5
        y, opened = c.rollout('Polygon: Smoothing Groups', y, 28)
        if opened:
            bw = (w-24)/2
            c.button(10, y-22, bw, 18, 'Auto Smooth', op('bsm.mesh_action', action='AUTO_SMOOTH'))
            c.button(14+bw, y-22, bw, 18, 'Clear All', op('bsm.mesh_action', action='CLEAR_SMOOTH'))
            y -= 28
    y -= 5
    nurms = obj.modifiers.get('NURMS')
    y, opened = c.rollout('Subdivision Surface', y, 50)
    if opened:
        c.checkbox(12, y-18, 'Use NURMS Subdivision', value=nurms is not None, action=op('bsm.mesh_action', action='NURMS'))
        if nurms:
            c.param(y-40, nurms, 'levels', 'Iterations:')
        y -= 50
    return y


def _viewport_space(context):
    try:
        from .operators import viewport_override
        return viewport_override(context)['area'].spaces.active
    except RuntimeError:
        return None


def toggle_backfacing(context):
    space = _viewport_space(context)
    if space:
        space.shading.show_xray = not space.shading.show_xray


def _editable_spline(c, y, obj):
    data = obj.data
    y, opened = c.rollout('Rendering', y, 64, key=('SPLINE', obj.name))
    if opened:
        c.checkbox(12, y-18, 'Enable In Viewport', value=data.bevel_depth > 0,
                   action=('SET', data, 'bevel_depth', 0. if data.bevel_depth > 0 else .02))
        c.param(y-40, data, 'bevel_depth', 'Thickness:')
        c.param(y-60, data, 'bevel_resolution', 'Sides:')
        y -= 64
    y -= 5
    y, opened = c.rollout('Interpolation', y, 28, key=('SPLINE_I', obj.name))
    if opened:
        c.param(y-22, data, 'resolution_u', 'Steps:')
        y -= 28
    return y


# Hierarchy ---------------------------------------------------------------
def _subtabs(c, y, state, attr, items):
    w = c.w
    bw = (w-10)/len(items)
    for i, (ident, label) in enumerate(items):
        c.button(5+i*bw, y-20, bw-2, 18, label, ('SET', state, attr, ident), selected=getattr(state, attr) == ident)
    return y-26


def _hierarchy(c, y, context, state, obj):
    w = c.w
    ts = context.scene.tool_settings
    y = _subtabs(c, y, state, 'hierarchy_tab', (('PIVOT', 'Pivot'), ('IK', 'IK'), ('LINK', 'Link Info')))
    if state.hierarchy_tab == 'PIVOT':
        y, opened = c.rollout('Adjust Pivot', y, 168)
        if opened:
            c.text('Move/Rotate/Scale:', 12, y-14, 9)
            c.button(12, y-36, w-24, 19, 'Affect Pivot Only', toggle(ts, 'use_transform_data_origin'), selected=ts.use_transform_data_origin)
            c.button(12, y-56, w-24, 19, 'Affect Object Only', None, enabled=False)
            c.button(12, y-76, w-24, 19, 'Affect Hierarchy Only', toggle(ts, 'use_transform_skip_children'), selected=ts.use_transform_skip_children)
            c.text('Alignment:', 12, y-92, 9)
            c.button(12, y-114, w-24, 19, 'Center to Object', op('bsm.toolbar_action', action='PIVOT'))
            c.button(12, y-134, w-24, 19, 'Align to World', op('bsm.toolbar_action', action='PIVOT_WORLD'))
            c.button(12, y-160, w-24, 19, 'Reset Pivot', op('bsm.toolbar_action', action='PIVOT_RESET'))
            y -= 168
        y -= 5
        y, opened = c.rollout('Working Pivot', y, 70)
        if opened:
            bw = (w-28)/2
            c.button(12, y-24, bw, 19, 'Edit Working Pivot', op('wm.tool_set_by_id', name='builtin.cursor'))
            c.button(16+bw, y-24, bw, 19, 'Use Working Pivot', ('SET', ts, 'transform_pivot_point', 'CURSOR'), selected=ts.transform_pivot_point == 'CURSOR')
            c.button(12, y-46, bw, 19, 'Align To View', op('bsm.toolbar_action', action='CURSOR_VIEW'))
            c.button(16+bw, y-46, bw, 19, 'Reset', op('view3d.snap_cursor_to_center'))
            c.button(12, y-66, w-24, 19, 'Place Pivot To: Surface', op('wm.tool_set_by_id', name='builtin.cursor'))
            y -= 70
        y -= 5
        y, opened = c.rollout('Adjust Transform', y, 76)
        if opened:
            c.button(12, y-24, w-24, 19, "Don't Affect Children", toggle(ts, 'use_transform_skip_children'), selected=ts.use_transform_skip_children)
            c.text('Reset:', 12, y-40, 9)
            bw = (w-28)/2
            c.button(12, y-62, bw, 19, 'Transform', op('object.transform_apply', location=False, rotation=True, scale=False))
            c.button(16+bw, y-62, bw, 19, 'Scale', op('object.transform_apply', location=False, rotation=False, scale=True))
            y -= 76
    elif state.hierarchy_tab == 'IK':
        y, opened = c.rollout('Inverse Kinematics', y, 70)
        if opened:
            for i, label in enumerate(('Interactive IK', 'Apply IK', 'Apply Only To Keys')):
                c.button(12, y-24-i*21, w-24, 19, label, None, enabled=False)
            y -= 70
    elif obj:
        y, opened = c.rollout('Locks', y, 84)
        if opened:
            for j, (attr, label) in enumerate((('lock_location', 'Move:'), ('lock_rotation', 'Rotate:'), ('lock_scale', 'Scale:'))):
                c.text(label, 12, y-20-j*24, 9)
                for i, axis in enumerate('XYZ'):
                    c.checkbox(62+i*30, y-22-j*24, axis, obj, attr, i)
            y -= 84
        y -= 5
        y, opened = c.rollout('Inherit', y, 84)
        if opened:
            for j, label in enumerate(('Move:', 'Rotate:', 'Scale:')):
                c.text(label, 12, y-20-j*24, 9, DIM)
                for i, axis in enumerate('XYZ'):
                    c.checkbox(62+i*30, y-22-j*24, axis, enabled=False, value=True)
            y -= 84
    return y


# Motion -------------------------------------------------------------------
ROTATION_CONTROLLERS = {'XYZ': 'Euler XYZ', 'XZY': 'Euler XZY', 'YXZ': 'Euler YXZ', 'YZX': 'Euler YZX', 'ZXY': 'Euler ZXY',
                        'ZYX': 'Euler ZYX', 'QUATERNION': 'TCB Rotation', 'AXIS_ANGLE': 'Axis Angle'}


def _motion(c, y, context, state, obj):
    w = c.w
    y = _subtabs(c, y, state, 'motion_tab', (('PARAMETERS', 'Parameters'), ('PATHS', 'Motion Paths')))
    if obj is None:
        c.text('Select an object', 10, y-16, 9, DIM)
        return y-24
    if state.motion_tab == 'PARAMETERS':
        y, opened = c.rollout('Assign Controller', y, 78)
        if opened:
            c.text('Transform : Position/Rotation/Scale', 12, y-16, 9)
            c.text('Position : Position XYZ', 24, y-34, 9)
            c.text('Rotation : '+ROTATION_CONTROLLERS.get(obj.rotation_mode, obj.rotation_mode), 24, y-52, 9)
            c.hit(20, y-56, w-30, 16, call(enum_menu, obj, 'rotation_mode'), 'Assign Rotation Controller')
            c.text('Scale : Bezier Scale', 24, y-70, 9)
            y -= 78
        y -= 5
        y, opened = c.rollout('PRS Parameters', y, 92)
        if opened:
            bw = (w-28)/3
            c.text('Create Key', 12, y-14, 9)
            c.text('Delete Key', 12, y-56, 9)
            for i, (channel, label) in enumerate((('LOCATION', 'Position'), ('ROTATION', 'Rotation'), ('SCALE', 'Scale'))):
                c.button(12+i*(bw+2), y-36, bw, 19, label, op('bsm.keyframe', channels=channel))
                c.button(12+i*(bw+2), y-78, bw, 19, label, op('bsm.keyframe', channels=channel, delete=True))
            y -= 92
        y -= 5
        y, opened = c.rollout('Key Info (Basic)', y, 112)
        if opened:
            c.param(y-22, context.scene, 'frame_current', 'Time:')
            for i, axis in enumerate('XYZ'):
                c.text_right(axis+' Value:', w*.5, y-40-i*20, 9)
                c.field(w*.5+3, y-44-i*20, w*.5-11, obj, 'location', i)
            c.button(12, y-106, w-24, 18, 'In/Out: Interpolation...', call(enum_menu_key, None))
            y -= 112
    else:
        path = obj.motion_path
        visual = obj.animation_visualization.motion_path
        y, opened = c.rollout('Motion Paths', y, 96)
        if opened:
            c.button(12, y-24, w-24, 19, 'Hide Motion Path' if path else 'Show Motion Path',
                     op('object.paths_clear', only_selected=True) if path else op('object.paths_calculate'), selected=bool(path))
            c.param(y-46, visual, 'frame_start', 'Start Time:')
            c.param(y-66, visual, 'frame_end', 'End Time:')
            c.param(y-86, visual, 'frame_step', 'Samples:')
            y -= 96
    return y


def enum_menu_key(context, _unused):
    bpy.ops.wm.call_menu(name='BSM_MT_key_interpolation')


MENU_OPERATORS = {'wm.call_menu', 'wm.call_menu_pie', 'wm.call_panel'}
MENU_CALLS = {stack_context, enum_menu, enum_menu_key}


def opens_menu(action, secondary=False):
    """True when a click on this control opens a Blender menu."""
    if action[0] == 'RMB':
        action = action[2 if secondary else 1]
    elif secondary:
        return False
    return (action[0] == 'OP' and action[1] in MENU_OPERATORS) or (action[0] == 'CALL' and action[1] in MENU_CALLS)


# Display ------------------------------------------------------------------
CATEGORY_FLAGS = (('Geometry', 'show_object_viewport_mesh'), ('Shapes', 'show_object_viewport_curve'),
                  ('Lights', 'show_object_viewport_light'), ('Cameras', 'show_object_viewport_camera'),
                  ('Helpers', 'show_object_viewport_empty'), ('Space Warps', None),
                  ('Particle Systems', None), ('Bone Objects', 'show_object_viewport_armature'))


def _display(c, y, context, state, obj):
    w = c.w
    space = _viewport_space(context)
    if space:
        y, opened = c.rollout('Display Color', y, 82)
        if opened:
            shading = space.shading
            c.text('Wireframe:', 12, y-16, 9)
            c.radio(20, y-32, 'Object Color', shading.wireframe_color_type == 'OBJECT', ('SET', shading, 'wireframe_color_type', 'OBJECT'))
            c.radio(w*.52, y-32, 'Material Color', shading.wireframe_color_type == 'MATERIAL', ('SET', shading, 'wireframe_color_type', 'MATERIAL'))
            c.text('Shaded:', 12, y-50, 9)
            c.radio(20, y-66, 'Object Color', shading.color_type == 'OBJECT', ('SET', shading, 'color_type', 'OBJECT'))
            c.radio(w*.52, y-66, 'Material Color', shading.color_type == 'MATERIAL', ('SET', shading, 'color_type', 'MATERIAL'))
            y -= 82
        y -= 5
        height = 16*((len(CATEGORY_FLAGS)+1)//2)+30
        y, opened = c.rollout('Hide by Category', y, height)
        if opened:
            for i, (label, attr) in enumerate(CATEGORY_FLAGS):
                if attr is None:
                    c.checkbox(12+(i % 2)*(w*.48), y-18-(i//2)*16, label, enabled=False, value=False)
                else:
                    c.checkbox(12+(i % 2)*(w*.48), y-18-(i//2)*16, label, value=not getattr(space, attr), action=call(flip, space, attr))
            bw = (w-28)/3
            for i, (label, value) in enumerate((('All', False), ('None', True), ('Invert', None))):
                c.button(12+i*(bw+2), y-height+4, bw, 17, label, call(set_categories, space, value))
            y -= height
    y -= 5
    y, opened = c.rollout('Hide', y, 98)
    if opened:
        bw = (w-28)/2
        rows = (('Hide Selected', op('object.hide_view_set', unselected=False)), ('Hide Unselected', op('object.hide_view_set', unselected=True)),
                ('Hide by Name...', op('bsm.select_from_scene', purpose='HIDE')), ('Hide by Hit', op('bsm.pick_object', purpose='HIDE_BY_HIT')),
                ('Unhide All', op('object.hide_view_clear')), ('Unhide by Name...', op('bsm.select_from_scene', purpose='UNHIDE')))
        for i, (label, action) in enumerate(rows):
            c.button(12+(i % 2)*(bw+4), y-22-(i//2)*21, bw, 19, label, action)
        c.checkbox(12, y-92, 'Hide Frozen Objects', state, 'hide_frozen')
        y -= 98
    y -= 5
    y, opened = c.rollout('Freeze', y, 92)
    if opened:
        bw = (w-28)/2
        rows = (('Freeze Selected', op('bsm.toolbar_action', action='FREEZE')), ('Freeze Unselected', op('bsm.toolbar_action', action='FREEZE_UNSELECTED')),
                ('Freeze by Name...', op('bsm.select_from_scene', purpose='FREEZE')), ('Freeze by Hit', op('bsm.pick_object', purpose='FREEZE_BY_HIT')),
                ('Unfreeze All', op('bsm.toolbar_action', action='UNFREEZE')), ('Unfreeze by Name...', op('bsm.select_from_scene', purpose='UNFREEZE')),
                ('Unfreeze by Hit', op('bsm.pick_object', purpose='UNFREEZE_BY_HIT')))
        for i, (label, action) in enumerate(rows):
            c.button(12+(i % 2)*(bw+4), y-22-(i//2)*21, bw, 19, label, action)
        y -= 92
    if obj:
        y -= 5
        rows = (('Display as Box', None), ('Backface Cull', None), ('Edges Only', 'show_wire'), ('Vertex Ticks', None),
                ('Trajectory', 'TRAJECTORY'), ('See-Through', None), ('Ignore Extents', None), ('Show Frozen in Gray', 'FROZEN_GRAY'),
                ('Never Degrade', None), ('Vertex Colors', 'VERTEX_COLORS'), ('Shaded', None))
        y, opened = c.rollout('Display Properties', y, 8+16*len(rows))
        if opened:
            for i, (label, attr) in enumerate(rows):
                x, ry = 12, y-18-i*16
                if label == 'Display as Box':
                    c.checkbox(x, ry, label, value=obj.display_type == 'BOUNDS', action=('SET', obj, 'display_type', 'TEXTURED' if obj.display_type == 'BOUNDS' else 'BOUNDS'))
                elif attr == 'show_wire':
                    c.checkbox(x, ry, label, obj, 'show_wire')
                elif attr == 'TRAJECTORY':
                    c.checkbox(x, ry, label, value=obj.motion_path is not None,
                               action=op('object.paths_clear', only_selected=True) if obj.motion_path else op('object.paths_calculate'))
                elif attr == 'FROZEN_GRAY':
                    c.checkbox(x, ry, label, state, 'freeze_gray')
                elif attr == 'VERTEX_COLORS' and space:
                    c.checkbox(x, ry, label, value=space.shading.color_type == 'VERTEX',
                               action=('SET', space.shading, 'color_type', 'OBJECT' if space.shading.color_type == 'VERTEX' else 'VERTEX'))
                else:
                    c.checkbox(x, ry, label, enabled=False, value=False)
            y -= 8+16*len(rows)
    if space:
        y -= 5
        y, opened = c.rollout('Link Display', y, 36)
        if opened:
            c.checkbox(12, y-18, 'Display Links', space.overlay, 'show_relationship_lines')
            c.checkbox(12, y-34, 'Link Replaces Object', enabled=False, value=False)
            y -= 36
    return y


def flip(context, owner, attr):
    setattr(owner, attr, not getattr(owner, attr))


def set_categories(context, space, value):
    for _, attr in CATEGORY_FLAGS:
        if attr:
            setattr(space, attr, (not getattr(space, attr)) if value is None else not value)


# Utilities ----------------------------------------------------------------
UTILITIES = (('Perspective Match', None), ('Collapse', 'COLLAPSE'), ('Color Clipboard', None), ('Measure', 'MEASURE'),
             ('Motion Capture', None), ('Reset XForm', 'RESET_XFORM'), ('MAXScript', 'MAXSCRIPT'), ('Flight Studio', None))


def _utilities(c, y, context, state, obj):
    w = c.w
    height = 52+21*len(UTILITIES)
    y, opened = c.rollout('Utilities', y, height)
    if opened:
        bw = (w-30)/2
        c.button(12, y-24, bw, 19, 'More...', menu('BSM_MT_more_utilities'))
        c.button(16+bw, y-24, bw-14, 19, 'Sets', None, enabled=False)
        c.button(w-24, y-24, 14, 19, icon='settings', action=None, enabled=False, flat=True)
        for i, (label, ident) in enumerate(UTILITIES):
            c.button(12, y-50-i*21, w-24, 19, label, ('SET', state, 'utility', ident) if ident else None,
                     selected=state.utility == ident, enabled=ident is not None)
        y -= height
    selected = [o for o in context.view_layer.objects if o.select_get()]
    if state.utility == 'COLLAPSE':
        y -= 5
        y, opened = c.rollout('Collapse', y, 74)
        if opened:
            c.text(f'Selected Count: {len(selected)}', 12, y-16, 9)
            c.text('Output Type: Modifier Stack Result', 12, y-34, 9, DIM)
            c.button(12, y-64, w-24, 19, 'Collapse Selected', op('bsm.stack_action', action='COLLAPSE_ALL', modifier=''))
            y -= 74
    elif state.utility == 'MEASURE':
        y -= 5
        y, opened = c.rollout('Measure', y, 98)
        if opened:
            info = measure(context, obj)
            c.text(obj.name if obj else 'No object', 12, y-16, 9, bold=True)
            for i, line in enumerate(info):
                c.text(line, 12, y-34-i*16, 9)
            y -= 98
    elif state.utility == 'RESET_XFORM':
        y -= 5
        y, opened = c.rollout('Reset Transform', y, 34)
        if opened:
            c.button(12, y-26, w-24, 19, 'Reset Selected', op('object.transform_apply', location=False, rotation=True, scale=True))
            y -= 34
    elif state.utility == 'MAXSCRIPT':
        y -= 5
        y, opened = c.rollout('MAXScript', y, 96)
        if opened:
            for i, (label, cmd) in enumerate((('Open Listener', 'LISTENER'), ('New Script', 'NEW_SCRIPT'),
                                              ('Open Script', 'OPEN_SCRIPT'), ('Run Script', 'RUN_SCRIPT'))):
                c.button(12, y-24-i*21, w-24, 19, label, op('bsm.max_command', command=cmd))
            y -= 96
    return y


def measure(context, obj):
    if obj is None or obj.type != 'MESH':
        return ['Select a mesh object'] if obj is None else [f'Dimensions: {obj.dimensions.x:.3f} x {obj.dimensions.y:.3f} x {obj.dimensions.z:.3f}']
    import bmesh
    bm = bmesh.new()
    bm.from_object(obj, context.evaluated_depsgraph_get())
    bm.transform(obj.matrix_world)
    area = sum(f.calc_area() for f in bm.faces)
    volume = bm.calc_volume(signed=False)
    from mathutils import Vector
    center = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
    bm.free()
    units = context.scene.unit_settings
    fmt = lambda v, kind='LENGTH': bpy.utils.units.to_string(units.system, kind, v, precision=3) if units.system != 'NONE' else f'{v:.3f}'
    d = obj.dimensions
    return [f'Surface Area: {fmt(area, "AREA")}', f'Volume: {fmt(volume, "VOLUME")}',
            f'Center of Mass: {center.x:.3f}, {center.y:.3f}, {center.z:.3f}', f'Dimensions: {d.x:.3f} x {d.y:.3f} x {d.z:.3f}']


# Time slider, track bar and status bar ----------------------------------------
# Measured on 3ds Max 2027 (layout units at the right edge R = width); colours from
# DefaultUI.clrx: Time slider Background, Trackbar Background/Text/Ticks/Cursor, Keys.
TRACKBAR_BG = (.165, .165, .165, 1)
TRACKBAR_TEXT = (.737, .737, .737, 1)
TRACKBAR_TICKS = (.392, .392, .392, 1)
TRACKBAR_CURSOR = (.992, .918, .071, 1)
TRACKBAR_SELECTED = (.208, .275, .341, 1)
KEY_COLORS = {'LOCATION': (.639, 0, 0, 1), 'ROTATION': (0, .478, 0, 1), 'SCALE': (0, 0, .788, 1), 'OTHER': (.55, .55, .55, 1)}
SET_KEY = (.227, .518, .243, 1)  # DefaultUI.clrx "Set Key Mode"
TIMELINE_HEIGHT = 96  # Max's bottom panel: time slider, track bar and two status lines
_timeline = {}  # area pointer -> slider and track bar geometry for scrubbing and key picking
_cursor = [None]  # world position under the mouse on the home grid, shown when nothing is selected


def _flyout_mark(c, x, y, w):
    c.c.polygon([(v*c.u, (z+c.oy)*c.u) for v, z in ((x+w-1, y+1), (x+w-1, y+5), (x+w-5, y+1))], DIM)


def timeline(context):
    from . import trackbar
    c = Canvas(context)
    w, h = c.w, c.h
    scene = context.scene
    state = context.window_manager.bsm
    settings = scene.tool_settings
    c.rect(0, 0, w, h, BG)
    start, end = scene.frame_start, scene.frame_end
    span = max(1, end-start)
    auto = settings.use_keyframe_insert_auto
    # Time slider: the "< frame / end >" thumb travels with its arrows; the background
    # turns red while Auto Key is on.
    sy, sh = h-18, 15
    sx, sw = 33, max(60, w-73)
    c.rect(sx, sy, sw, sh, AUTO_KEY if auto else BG)
    thumb, inner = 97, (sx+12, sw-24)
    tx = inner[0]+(scene.frame_current-start)/span*(inner[1]-thumb)
    c.hit(sx, sy, sw, sh, rmb(('SCRUB_SLIDER',), op('bsm.create_key')), 'Time Slider (right-click: Create Key)')
    c.rect(tx, sy, thumb, sh, (.36, .36, .36, 1))
    label = f'{scene.frame_current} / {end}'
    c.text(label, tx+thumb/2-c.text_width(label, 8)/2, sy+4, 8)
    c.button(tx-12, sy, 12, sh, '<', op('bsm.step_frame', direction=-1), tip='Previous Frame (,)')
    c.button(tx+thumb, sy, 12, sh, '>', op('bsm.step_frame', direction=1), tip='Next Frame (.)')
    # Track bar: keys of the selected objects, frame ruler and the current-frame cursor.
    ty, th = h-46, 26
    c.button(38, ty+4, 20, 18, icon='mini_curve', action=op('bsm.editor', kind='GRAPH', floating=True), flat=True,
             tip='Open Mini Curve Editor')
    bx, bw = 72, max(40, w-112)
    left, track = bx+8, max(1, bw-16)
    _timeline[c.key] = dict(slider=(inner[0], inner[1], thumb), track=(left, track), start=start, span=span)
    c.rect(bx, ty, bw, th, TRACKBAR_BG)
    c.hit(bx, ty, bw, th, ('TRACKBAR',), 'Track Bar')
    selecting = _timeline.get(('select', c.key))
    if selecting:
        a, b = sorted(selecting)
        c.rect(left+(a-start)/span*track, ty, max(1, (b-a)/span*track), th, TRACKBAR_SELECTED)
    per = track/span
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 5000) if s*per >= 34 or s == 5000)
    minor = 1 if per >= 4 else (step//5 or 1)
    frame = start-(start % minor)
    while frame <= end:
        if frame >= start:
            x = left+(frame-start)*per
            major = frame % step == 0
            c.line([(x, ty+th), (x, ty+th-(7 if major else 4))], TRACKBAR_TICKS)
            if major and state.track_numbers:
                text = str(frame)
                c.text(text, x-c.text_width(text, 8)/2, ty+5, 8, TRACKBAR_TEXT)
        frame += minor
    keys = trackbar.track_keys(context)
    key_w = max(3., min(8., per*.6))
    for frame, kinds in sorted(keys.items()):
        if start <= frame <= end:
            x = left+(frame-start)*per
            if frame in trackbar.selected:
                c.rect(x-key_w/2, ty+2, key_w, th-4, (1, 1, 1, 1))
            else:  # one band per animated transform, as Max splits mixed keys
                bands = [k for k in ('LOCATION', 'ROTATION', 'SCALE', 'OTHER') if k in kinds]
                band = (th-4)/len(bands)
                for i, kind in enumerate(bands):
                    c.rect(x-key_w/2, ty+th-2-(i+1)*band, key_w, band, KEY_COLORS[kind])
            c.hit(x-key_w/2-1, ty, key_w+2, th, ('TRACK_KEY', frame), f'Key at frame {frame}')
    x = left+(scene.frame_current-start)*per
    if bx <= x <= bx+bw:
        # Max's cursor: a see-through yellow box over the ticks and the frame number.
        gpu.state.blend_set('ALPHA')  # icons leave blending off
        text = str(scene.frame_current)
        cw = max(7., c.text_width(text, 8)+3)
        c.rect(x-cw/2, ty+5, cw, th-6, TRACKBAR_CURSOR[:3]+(.5,))
        c.text(text, x-c.text_width(text, 8)/2, ty+8, 8, (1, .97, .75, 1))
    # Status bar, left: MAXScript mini listener, selection count and prompt.
    c.rect(3, 22, 77, 19, (.93, .76, .76, 1))
    c.rect(3, 2, 77, 19, (.96, .96, .96, 1))
    c.text('Scripting Mini', 6, 7, 8, (.35, .35, .35, 1))
    c.hit(3, 2, 77, 39, op('bsm.max_command', command='LISTENER'), 'MAXScript Mini Listener')
    count = len(context.selected_objects)
    c.text(f'{count} Object{"s" if count != 1 else ""} Selected' if count else 'None Selected', 86, 27, 8)
    c.text(state.prompt or prompt(context), 86, 8, 8)
    R = w
    # Isolate, selection lock, absolute/offset mode, coordinates and grid.
    c.button(R-694, 23, 18, 18, icon='isolate_toggle', action=op('bsm.isolate_toggle'), flat=True,
             selected=trackbar.isolated(context), tip='Isolate Selection Toggle (Alt+Q)')
    c.button(R-673, 23, 18, 18, icon='selection_lock', action=op('bsm.select_lock'), flat=True,
             selected=state.selection_locked, tip='Selection Lock Toggle (Space)')
    c.button(R-652, 23, 18, 18, icon='abs_rel', action=toggle(state, 'offset_mode'), flat=True,
             selected=state.offset_mode, tip='Absolute Mode Transform Type-In (click for Offset Mode)')
    obj = context.view_layer.objects.active if context.selected_objects else None
    for i, (axis, lx) in enumerate((('X', R-632), ('Y', R-565), ('Z', R-500))):
        c.text(axis+':', lx, 27, 8)
        if obj is not None:
            owner, attr = (state, 'offset_vector') if state.offset_mode else (obj, 'location')
            c.field(lx+10, 24, 45, owner, attr, i, spinner=False)
        else:  # Max shows the cursor position on the grid, read-only
            c.rect(lx+10, 24, 45, 16, (.30, .30, .30, 1))
            value = _cursor[0][i] if _cursor[0] is not None else 0.
            c.text(format_value(scene.cursor, 'location', value), lx+13, 28, 8, DIM)
    c.text('Grid = '+format_value(state, 'grid_spacing', state.grid_spacing), R-435, 27, 8)
    # Safe Scene Script Execution and time tags.
    protected, blocked = trackbar.safe_scene(context)
    c.button(R-552, 3, 18, 17, icon='shield', action=op('bsm.safe_scene'), flat=True,
             tip='Safe Scene Script Execution (Blender: Auto Run Python Scripts is off)')
    c.text('Enabled:' if protected else 'Disabled:', R-530, 7, 8)
    c.c.polygon([(c.u*(R-487+3.5*math.cos(a*math.pi/8)), c.u*(11.5+3.5*math.sin(a*math.pi/8))) for a in range(16)],
                (.24, .78, .29, 1) if protected else (.85, .2, .2, 1))
    badge = str(blocked)
    c.c.polygon([(c.u*(R-474+6.5*math.cos(a*math.pi/10)), c.u*(11.5+6.5*math.sin(a*math.pi/10))) for a in range(20)], (.86, .86, .86, 1))
    c.text(badge, R-474-c.text_width(badge, 8)/2, 8, 8, (.2, .2, .2, 1))
    c.hit(R-481, 4, 14, 15, op('bsm.safe_scene'), f'{blocked} script execution(s) blocked in this scene')
    c.icon('tag_cube', R-458, 4, 15)
    c.text('Add Time Tag', R-440, 7, 8)
    c.hit(R-460, 2, 80, 19, menu('BSM_MT_time_tags'), 'Time Tags: add, edit, delete or go to a tag')
    # Animation playback, key mode, current frame and time configuration.
    playing = context.screen.is_animation_playing
    config = op('bsm.time_configuration')
    for i, (icon, action, tip) in enumerate((('first', op('screen.frame_jump', end=False), 'Go to Start (Home)'),
                                             ('previous', op('bsm.step_frame', direction=-1), 'Previous Frame (,)'),
                                             ('stop' if playing else 'play', op('screen.animation_play'), 'Play Animation (/)'),
                                             ('next', op('bsm.step_frame', direction=1), 'Next Frame (.)'),
                                             ('last', op('screen.frame_jump', end=True), 'Go to End (End)'))):
        c.button(R-352+i*19, 23, 18, 18, icon=icon, action=rmb(action, config), flat=True, tip=tip+' (right-click: Time Configuration)')
    c.button(R-352, 3, 18, 18, icon='key_mode', action=toggle(state, 'key_mode'), flat=True, selected=state.key_mode,
             tip='Key Mode Toggle: Previous/Next jump between keys')
    c.field(R-331, 4, 52, scene, 'frame_current')
    c.button(R-276, 3, 18, 18, icon='time_config', action=config, flat=True, tip='Time Configuration')
    # Keying: Set Keys, Auto Key, Set Key Mode, key selection set, default tangents, key filters.
    c.button(R-249, 3, 31, 38, icon='set_keys', action=op('bsm.keyframe', channels='FILTERED'), tip='Set Keys (K)')
    c.button(R-213, 23, 34, 17, 'Auto', op('bsm.auto_key_toggle'), fill=AUTO_KEY if auto else None, tip='Toggle Auto Key Mode (N)')
    c.button(R-213, 4, 34, 17, 'Set K.', toggle(state, 'set_key_mode'), fill=SET_KEY if state.set_key_mode else None,
             tip='Toggle Set Key Mode')
    c.dropdown(R-175, 24, 87, state.key_set or 'Selected', menu('BSM_MT_key_sets'), 'Selection Set for Set Keys')
    tangent = {'LINEAR': 'tan_linear', 'STEP': 'tan_step', 'CUSTOM': 'tan_custom'}.get(trackbar.current_tangent(context), 'tan_auto')
    c.button(R-174, 4, 17, 17, icon=tangent, action=menu('BSM_MT_default_tangents'), flat=True, tip='Default In/Out Tangents for New Keys')
    _flyout_mark(c, R-174, 4, 17)
    c.button(R-155, 4, 67, 17, 'Filters...', menu('BSM_MT_key_filters'), tip='Open Filters Dialog (Set Key Filters)')
    # Viewport navigation controls.
    nav = ((('zoom', op('bsm.navigation', kind='ZOOM'), 'Zoom', False),
            ('zoom_all', op('bsm.view_navigation', kind='ZOOM_ALL'), 'Zoom All', False),
            ('zoom_extents', rmb(op('bsm.frame_selected'), menu('BSM_MT_extents_flyout')), 'Zoom Extents Selected (Z)', True),
            ('zoom_extents_all', rmb(op('bsm.view_navigation', kind='EXTENTS_ALL_SELECTED'), menu('BSM_MT_extents_all_flyout')),
             'Zoom Extents All Selected', True)),
           (('fov', rmb(op('bsm.view_navigation', kind='FOV'), menu('BSM_MT_fov_flyout')), 'Field-of-View', True),
            ('pan', rmb(op('bsm.navigation', kind='PAN'), menu('BSM_MT_pan_flyout')), 'Pan View (Ctrl+P)', True),
            ('orbit', rmb(op('bsm.navigation', kind='ORBIT'), menu('BSM_MT_orbit_flyout')), 'Orbit (Ctrl+R)', True),
            ('maximize', op('bsm.quad_view'), 'Maximize Viewport Toggle (Alt+W)', False)))
    for row, buttons in enumerate(nav):
        for i, (icon, action, tip, flyout) in enumerate(buttons):
            x, y = R-78+i*19, 23 if row == 0 else 3
            c.button(x, y, 18, 18, icon=icon, action=action, flat=True, tip=tip+(' (right-click: more)' if flyout else ''))
            if flyout:
                _flyout_mark(c, x, y, 18)
    c.tooltip()


def prompt(context):
    state = context.window_manager.bsm
    if state.active_creation:
        return 'Click and drag to begin creation process'
    tool = _tool_id(context)
    move, rotate = 'Click and drag to select and move objects', 'Click and drag to select and rotate objects'
    scale = 'Click and drag to select and scale objects (uniformly)'
    return {'builtin.move': move, 'bsm.max_move': move, 'builtin.rotate': rotate, 'bsm.max_rotate': rotate,
            'builtin.scale': scale, 'bsm.max_scale': scale}.get(tool, 'Click or click-and-drag to select objects')


def frame_at(area, x, slider=False):
    """The frame under x (layout units) on the time slider or the track bar."""
    geometry = _timeline.get(area.as_pointer())
    if geometry is None:
        return None
    start, span = geometry['start'], geometry['span']
    if slider:
        left, width, thumb = geometry['slider']
        t = (x-left-thumb/2)/max(1, width-thumb)
    else:
        left, width = geometry['track']
        t = (x-left)/width
    return round(start+max(0., min(1., t))*span)


def scrub(context, area, x, slider=True):
    frame = frame_at(area, x, slider)
    if frame is not None:
        context.scene.frame_set(frame)
    runtime.redraw()


# Scene Explorer (docked) -----------------------------------------------------
EXPLORER_FILTERS = (('MESH', 'geometry', 'Display Geometry'), ('CURVE', 'shapes', 'Display Shapes'), ('LIGHT', 'lights', 'Display Lights'),
                    ('CAMERA', 'cameras', 'Display Cameras'), ('EMPTY', 'helpers', 'Display Helpers'), ('FIELD', 'spacewarps', 'Display Space Warps'),
                    ('GROUP', 'groups', 'Display Groups'), ('XREF', 'xrefs', 'Display Object XRefs'), ('ARMATURE', 'bones', 'Display Bone Objects'),
                    ('CONTAINER', 'containers', 'Display Containers'), ('FROZEN', 'frozen', 'Display Frozen Objects'), ('HIDDEN', 'hide', 'Display Hidden Objects'))
_collapsed = set()


def explorer_kind(obj):
    if obj.get('bsm_group'):
        return 'GROUP'
    if obj.library is not None or obj.override_library is not None:
        return 'XREF'
    if obj.field is not None and obj.field.type != 'NONE':
        return 'FIELD'
    return {'FONT': 'CURVE', 'SURFACE': 'MESH', 'META': 'MESH'}.get(obj.type, obj.type)


def explorer_rows(context):
    state = context.window_manager.bsm
    shown = set(state.explorer_filter)
    search = state.explorer_search.casefold()
    objects = list(context.view_layer.objects)

    def visible(obj):
        kind = explorer_kind(obj)
        if kind in {'MESH', 'CURVE', 'LIGHT', 'CAMERA', 'EMPTY', 'FIELD', 'GROUP', 'XREF', 'ARMATURE'} and kind not in shown:
            return False
        if obj.get('bsm_render_temp') or obj.hide_select and 'FROZEN' not in shown or obj.hide_get() and 'HIDDEN' not in shown:
            return False
        return not search or search in obj.name.casefold()
    rows = []
    if search:
        return [(o, 0, False) for o in sorted(objects, key=lambda o: o.name.casefold()) if visible(o)]

    def walk(obj, depth):
        children = sorted((c for c in obj.children if c.name in context.view_layer.objects), key=lambda o: o.name.casefold())
        if visible(obj):
            rows.append((obj, depth, bool(children)))
        if obj.name not in _collapsed:
            for child in children:
                walk(child, depth+1)
    for obj in sorted((o for o in objects if o.parent is None or o.parent.name not in context.view_layer.objects), key=lambda o: o.name.casefold()):
        walk(obj, 0)
    return rows


ROW = 18


def explorer(context):
    c = Canvas(context)
    w, h = c.w, c.h
    state = context.window_manager.bsm
    c.rect(0, 0, w, h, BG)
    for i, (label, name) in enumerate((('Select', 'BSM_MT_selection'), ('Display', 'BSM_MT_display'), ('Edit', 'BSM_MT_edit'))):
        c.button(6+i*48, h-22, 44, 18, label, menu(name), flat=True)
    c.field(24, h-42, w-30, state, 'explorer_search', spinner=False)
    if not state.explorer_search and not (_editing and _editing.get('attr') == 'explorer_search'):
        c.icon('search', w-22, h-41, 14)
    column = 20
    c.rect(0, 22, column, h-66, (.24, .24, .24, 1))
    shown = set(state.explorer_filter)
    fy = h-64
    for ident, icon, tip in EXPLORER_FILTERS:
        fy -= 17
        c.button(2, fy, 16, 16, icon=icon, action=call(toggle_filter, ident), selected=ident in shown, flat=True, tip=tip)
    for label, icon, value in (('Display All', 'display_all', 'ALL'), ('Display None', 'display_none', 'NONE'), ('Invert Display', 'display_invert', 'INVERT')):
        fy -= 17
        c.button(2, fy, 16, 16, icon=icon, action=call(set_filter, value), flat=True, tip=label)
    fy -= 20
    c.button(2, fy, 16, 16, icon='find_filter', action=op('bsm.explorer_search'), flat=True, tip='Find')
    c.rect(column, h-62, w-column, 17, (.31, .31, .31, 1))
    c.text('Name (Sorted Ascending)', column+18, h-57, 8)
    c.text('▴ Frozen', w-48, h-57, 8)
    rows = explorer_rows(context)
    start = min(state.explorer_scroll, max(0, len(rows)-1))
    y = h-64
    for obj, depth, has_children in rows[start:]:
        y -= ROW
        if y < 24:
            break
        selected = obj.select_get()
        if selected:
            c.rect(column, y, w-column, ROW-1, (.26, .38, .51, 1))
        x = column+3+depth*12
        if has_children:
            c.text('−' if obj.name not in _collapsed else '+', x-1, y+4, 9)
            c.hit(x-3, y, 10, ROW, call(toggle_branch, obj.name), 'Expand')
        hidden = obj.hide_get()
        c.icon('hide' if hidden else 'visible', x+8, y+2, 13)
        c.hit(x+8, y, 14, ROW, call(toggle_hidden, obj.name), 'Hide/Unhide')
        kind = explorer_kind(obj)
        icon = {'MESH': 'geometry', 'LIGHT': 'lights', 'CAMERA': 'cameras', 'CURVE': 'shapes', 'EMPTY': 'helpers', 'FIELD': 'spacewarps',
                'GROUP': 'groups', 'XREF': 'xrefs', 'ARMATURE': 'bones'}.get(kind, 'geometry')
        c.icon(icon, x+24, y+2, 13)
        max_chars = max(4, int((w-x-86)/5.6))
        label = obj.name if len(obj.name) <= max_chars else obj.name[:max_chars-1]+'…'
        frozen = obj.hide_select
        c.text(label, x+41, y+4, 9, DIM if hidden or frozen else TEXT)
        c.hit(x+24, y, w-x-62, ROW, rmb(('EXPLORER_ROW', obj.name), menu('BSM_MT_explorer_context')), obj.name)
        c.icon('frozen' if frozen else 'unlock', w-34, y+2, 13, enabled=frozen)
        c.hit(w-38, y, 22, ROW, call(toggle_frozen, obj.name), 'Freeze/Unfreeze')
    c.rect(0, 0, w, 22, (.23, .23, .23, 1))
    c.dropdown(4, 3, w-30, 'Default', menu('BSM_MT_explorer_mode'), 'Scene Explorer')
    c.tooltip()


def toggle_filter(context, ident):
    state = context.window_manager.bsm
    shown = set(state.explorer_filter)
    shown ^= {ident}
    state.explorer_filter = shown


def set_filter(context, value):
    state = context.window_manager.bsm
    every = {ident for ident, _, _ in EXPLORER_FILTERS}
    state.explorer_filter = every if value == 'ALL' else (set() if value == 'NONE' else every-set(state.explorer_filter))


def toggle_branch(context, name):
    _collapsed.symmetric_difference_update({name})


def toggle_hidden(context, name):
    obj = bpy.data.objects.get(name)
    if obj:
        obj.hide_set(not obj.hide_get())


def toggle_frozen(context, name):
    from .commands import freeze
    obj = bpy.data.objects.get(name)
    if obj:
        freeze(obj, not obj.hide_select)


def explorer_click(context, name):
    from .commands import promote_groups
    rows = [r[0] for r in explorer_rows(context)]
    obj = bpy.data.objects.get(name)
    if obj is None or obj.hide_select:
        return
    if _mods['shift'] and context.view_layer.objects.active in rows:
        a, b = rows.index(context.view_layer.objects.active), rows.index(obj)
        for other in rows[min(a, b):max(a, b)+1]:
            if not other.hide_select:
                other.select_set(True)
    elif _mods['ctrl']:
        obj.select_set(not obj.select_get())
    elif _mods['alt']:
        obj.select_set(False)
    else:
        for other in context.view_layer.objects:
            other.select_set(False)
        obj.select_set(True)
    if obj.select_get():
        context.view_layer.objects.active = obj
    promote_groups(context)


# Ribbon: minimized to panel titles like the default workspace.
RIBBON_TABS = (('MODELING', 'Modeling'), ('FREEFORM', 'Freeform'), ('SELECTION', 'Selection'), ('OBJECT_PAINT', 'Object Paint'), ('POPULATE', 'Populate'))
RIBBON_PANELS = {
    'MODELING': ('Polygon Modeling',),
    'MODELING_POLY': ('Polygon Modeling', 'Modify Selection', 'Edit', 'Geometry (All)', None, 'Loops', 'Tris', 'Subdivision', 'Visibility', 'Align', 'Properties'),
    'FREEFORM': ('PolyDraw', 'Paint Deform', 'Defaults'),
    'SELECTION': ('Select', 'Stored Selections', 'Sets', 'By Vertex', 'By Angle', 'By Normal', 'By Perspective', 'By Random', 'By Half', 'By Pivot Distance', 'By View', 'By Symmetry', 'By Numeric'),
    'OBJECT_PAINT': ('Paint Objects', 'Brush Settings'),
    'POPULATE': ('Define Flows', 'Define Idle Areas', 'Simulate', 'Display', 'Edit Selected'),
}
LEVEL_PANELS = {1: 'Vertices', 2: 'Edges', 3: 'Borders', 4: 'Polygons', 5: 'Elements'}


def ribbon_panels(context):
    state = context.window_manager.bsm
    if state.ribbon_tab == 'MODELING':
        obj = context.view_layer.objects.active
        if editable_poly(obj):
            level = state.component if context.mode == 'EDIT_MESH' else 0
            return [p if p else LEVEL_PANELS.get(level) for p in RIBBON_PANELS['MODELING_POLY'] if p or level]
    return list(RIBBON_PANELS[state.ribbon_tab])


def ribbon_menu(title):
    slug = '_'.join(''.join(ch if ch.isalnum() else ' ' for ch in title.lower()).split())
    return 'BSM_MT_ribbon_' + slug


def ribbon(context):
    c = Canvas(context)
    w, h = c.w, c.h
    state = context.window_manager.bsm
    c.rect(0, 0, w, h, BG)
    if not state.ribbon_visible:
        return
    x = 30
    for ident, label in RIBBON_TABS:
        tw = c.text_width(label)+28
        active = state.ribbon_tab == ident
        if active:
            c.rect(x, h-14, tw, 13, (.33, .33, .33, 1))
        c.text(label, x+14, h-11, 8, TEXT if active else DIM)
        c.hit(x, h-14, tw, 13, ('SET', state, 'ribbon_tab', ident), label)
        x += tw+4
    c.button(x+4, h-14, 20, 13, '▾', menu('BSM_MT_ribbon_options'), flat=True, tip='Ribbon display options')
    x = 30
    for title in ribbon_panels(context):
        tw = c.text_width(title)+18
        c.button(x, 1, tw, 13, title+' ▾', menu(ribbon_menu(title)), flat=True)
        x += tw+6
    c.tooltip()


def dispatch(context, action, secondary=False):
    from .operators import viewport_override
    kind = action[0]
    if kind == 'RMB':
        return dispatch(context, action[2] if secondary else action[1])
    if secondary:
        return None
    if kind in {'MAT', 'ANIM', 'UTIL', 'SCENE'}:
        from . import editor_host
        return editor_host.dispatch(context, action)
    if kind == 'NONE':
        return None
    if kind == 'OP':
        name, values = action[1:]
        group, method = name.split('.')
        override = {} if name.startswith(('wm.', 'bsm.', 'ed.', 'screen.', 'render.', 'marker.')) else viewport_override(context)
        with context.temp_override(**override):
            return getattr(getattr(bpy.ops, group), method)('INVOKE_DEFAULT', **values)
    if kind == 'CALL':
        result = action[1](context, *action[2])
        bpy.ops.ed.undo_push(message='Max Action')
        runtime.redraw()
        return result
    if kind == 'SET':
        setattr(action[1], action[2], action[3])
    elif kind == 'TOGGLE':
        owner, attr, index = action[1:]
        if index < 0:
            setattr(owner, attr, not getattr(owner, attr))
        else:
            getattr(owner, attr)[index] = not getattr(owner, attr)[index]
    elif kind == 'ARM':
        state = context.window_manager.bsm
        state.active_creation = '' if state.active_creation == action[1] else action[1]
        from . import params
        if state.active_creation in params.DEFAULTS:
            state.next_prim.kind = ''
            for attr, value in params.DEFAULTS[state.active_creation].items():
                try:
                    setattr(state.next_prim, attr, value)
                except (AttributeError, TypeError):
                    pass
    elif kind == 'ROLLOUT':
        key, title = action[1], action[2]
        opened = key not in _closed and (title not in CLOSED_BY_DEFAULT or key in _opened)
        if opened:
            _closed.add(key)
            _opened.discard(key)
        else:
            _closed.discard(key)
            _opened.add(key)
    elif kind == 'STACK':
        state = context.window_manager.bsm
        state.active_modifier = action[2]
        if not action[2] and context.mode == 'EDIT_MESH':
            pass
    elif kind == 'EXPLORER_ROW':
        explorer_click(context, action[1])
    if kind in {'SET', 'TOGGLE'} and (isinstance(action[1], bpy.types.ID) or isinstance(getattr(action[1], 'id_data', None), bpy.types.ID)):
        bpy.ops.ed.undo_push(message='Max Edit')
    runtime.redraw()
    return {'FINISHED'}


def clear():
    global _editing
    _targets.clear()
    _hover.clear()
    _hover_since.clear()
    _closed.clear()
    _opened.clear()
    _scroll.clear()
    _editing = None
