# SPDX-License-Identifier: GPL-3.0-or-later
"""3ds Max 2027 main menu bar and viewport label menus, drawn as Blender menus.

Labels, order, separators, submenus and hotkey hints follow the "Main Menu Bar" and
"Viewport Label Menu Bar" of the installed 3ds Max 2027 Default.mnxb. Entries whose
label could not be resolved are omitted. Every entry runs the closest Blender
operator; entries without a Blender equivalent stay visible but greyed out.

Use: register CLASSES (the generated Menu classes plus the operator that draws greyed
entries), then draw ``layout.menu(idname, text=label)`` for each entry of MAIN_MENUS
(menu bar) or LABEL_MENUS (viewport label menus).
"""
from .localization import tr as _tr
import hashlib
import re

import bpy


class Item:
    """Menu entry. op=None draws it greyed; menu opens an existing Blender menu instead."""
    __slots__ = ('label', 'op', 'props', 'hotkey', 'check', 'menu')

    def __init__(self, label, op=None, props=None, hotkey='', check=None, menu=None):
        self.label, self.op, self.props = label, op, props or {}
        self.hotkey, self.check, self.menu = hotkey, check, menu

    def __repr__(self):
        return 'Item(%r, %r)' % (self.label, self.menu or self.op)


class Sep:
    __slots__ = ()


class Sub:
    """Submenu; idname is assigned when its Menu class is generated."""
    __slots__ = ('label', 'items', 'idname')

    def __init__(self, label, items):
        self.label, self.items, self.idname = label, list(items), ''

    def __repr__(self):
        return 'Sub(%r, %d items)' % (self.label, len(self.items))


SEP = Sep()
# Menus implemented in C (not exposed in bpy.types) that layout.menu() still opens.
C_MENUS = {'TOPBAR_MT_file_open_recent'}
# Menus the extension defines in another module (scene-dependent lists): name -> module.
ADDON_MENUS = {'BSM_MT_view_cameras': 'operators', 'BSM_MT_view_lights': 'operators'}
# Mode-specific equivalents, so Select All/None/Invert also work outside Object Mode.
MODE_OPS = {'object.select_all': {
    'EDIT_MESH': 'mesh.select_all', 'EDIT_CURVE': 'curve.select_all', 'EDIT_SURFACE': 'curve.select_all',
    'EDIT_CURVES': 'curves.select_all', 'EDIT_ARMATURE': 'armature.select_all', 'POSE': 'pose.select_all',
    'EDIT_LATTICE': 'lattice.select_all', 'EDIT_METABALL': 'mball.select_all',
    'EDIT_GREASE_PENCIL': 'grease_pencil.select_all'}}


def _cmd(label, command, hotkey='', check=None):
    return Item(label, 'bsm.max_command', {'command': command}, hotkey, check)


def _mod(label, hotkey=''):
    return Item(label, 'bsm.max_modifier', {'name': label}, hotkey)


def _mods(*labels):
    return [_mod(label) for label in labels]


def _off(*labels):
    return [Item(label) for label in labels]


def _create(label, kind):
    return Item(label, 'bsm.create', {'kind': kind})


def _constraint(label, kind):
    return Item(label, 'bsm.add_constraint', {'kind': kind})


def _view(label, view, hotkey=''):
    return Item(label, 'bsm.view', {'view': view}, hotkey)


def _shade(label, style, hotkey='', check=None):
    return Item(label, 'bsm.viewport_shading', {'style': style}, hotkey, check)


def _editor(label, kind, hotkey=''):
    return Item(label, 'bsm.editor', {'kind': kind}, hotkey)


def _tool(label, tool, hotkey=''):
    return Item(label, 'bsm.tool', {'tool': tool}, hotkey)


def _view3d(context):
    space = getattr(context, 'space_data', None)
    if space is not None and space.type == 'VIEW_3D':
        return space
    screen = getattr(context, 'screen', None)
    for area in (screen.areas if screen else ()):
        if area.type == 'VIEW_3D':
            return area.spaces.active
    return None


def _overlay(name):
    return lambda context: bool(getattr(getattr(_view3d(context), 'overlay', None), name, False))


_grid_on = _overlay('show_floor')
_stats_on = _overlay('show_stats')
_face_orientation_on = _overlay('show_face_orientation')
_edged_faces_on = _overlay('show_wireframes')


def _wireframe_on(context):
    view = _view3d(context)
    return bool(view and view.shading.type == 'WIREFRAME')


def _snap_on(context):
    return context.scene.tool_settings.use_snap


def _safe_frames_on(context):
    camera = context.scene.camera
    return bool(camera and camera.type == 'CAMERA' and camera.data.show_safe_areas)


def _fullscreen_on(context):
    return bool(context.screen and context.screen.show_fullscreen)


# ---------------------------------------------------------------- menu data (3ds Max 2027 Default.mnxb)
_VIEWCUBE = [
    _cmd('Show the ViewCube', 'VIEWCUBE_TOGGLE', hotkey='Ctrl+Alt+V'),
    SEP,
    *_off('Show For Active View', 'Show For All Views'),
    SEP,
    _cmd('Home', 'VIEWCUBE_HOME', hotkey='Ctrl+Alt+H'),
    SEP,
    _view('Orthographic', 'ORTHO'),
    _view('Perspective', 'PERSP'),
    SEP,
    *_off('Set Current View as Home', 'Set Current View as Front', 'Reset Front'),
    SEP,
    Item('Configure...'),
]
_STEERINGWHEELS = [
    Item('Toggle SteeringWheels', hotkey='Shift+W'),
    SEP,
    Item('View Object Wheel'),
    Item('Tour Building Wheel', hotkey='Ctrl+Shift+J'),
    Item('Full Navigation Wheel'),
    SEP,
    *_off('Mini View Object Wheel', 'Mini Tour Building Wheel', 'Mini Full Navigation Wheel'),
    SEP,
    Item('Configure...'),
]
_SHOW_MATERIALS_IN_VIEWPORT_AS = [
    Item('Enable Transparency'),
    SEP,
    *_off(
        'Standard Display', 'Standard Display with Maps', 'Hardware Display', 'Hardware Display with Maps',
        'Shaded Materials without Maps'),
    _shade('Shaded Materials with Maps', 'MATERIALS_SHADED'),
    Item('Realistic Materials without Maps'),
    _shade('Realistic Materials with Maps', 'MATERIALS_REALISTIC'),
    SEP,
    Item('Override Off'),
    _shade('Override with UV Checker', 'UV_CHECKER'),
    *_off('Override with Fast Shader', 'Override with Rendering Setting'),
]
_XVIEW = [
    _cmd('Show Statistics', 'XVIEW_STATS', hotkey='7', check=_stats_on),
    _cmd('Face Orientation', 'XVIEW_FACE_ORIENTATION', check=_face_orientation_on),
    Item('Overlapping Faces'),
    _cmd('Open Edges', 'XVIEW_OPEN_EDGES'),
    *_off(
        'Multiple Edges', 'Isolated Vertices', 'Overlapping Vertices', 'T-Vertices',
        'Missing UVW Coordinates', 'Flipped UVW Faces', 'Overlapped UVW Faces'),
    SEP,
    Item('Select Results'),
    SEP,
    *_off('See-Through', 'Auto Update', 'Display On Top'),
    SEP,
    Item('Configure...'),
]
_VIEWPORT_BACKGROUND = [
    _cmd('Gradient Color', 'BACKGROUND_GRADIENT'),
    _cmd('Solid Color', 'BACKGROUND_SOLID'),
    SEP,
    *_off('Environment Background', 'Custom Image File'),
    SEP,
    Item('Configure Viewport Background...', hotkey='Alt+B'),
]

MAIN = [
    ('File', [
        Sub('New', [
            Item('New All', 'wm.read_homefile', {'use_empty': False}),
            Item('New from Template', menu='TOPBAR_MT_file_new'),
        ]),
        Item('Reset', 'wm.read_homefile', {'use_empty': False}),
        Item('Open...', 'wm.open_mainfile', hotkey='Ctrl+O'),
        Item('Open Recent', menu='TOPBAR_MT_file_open_recent'),
        Item('Autobackup', menu='TOPBAR_MT_file_recover'),
        Item('View Image File...'),
        SEP,
        Item('Save', 'wm.save_mainfile', hotkey='Ctrl+S'),
        Item('Save As...', 'wm.save_as_mainfile', hotkey='Ctrl+Shift+S'),
        Item('Save Incremental (+)', 'wm.save_mainfile', {'incremental': True}, hotkey='Ctrl+Alt+S'),
        Item('Save Copy As...', 'wm.save_as_mainfile', {'copy': True}),
        *_off('Save Selected...', 'Archive...'),
        SEP,
        Sub('Import', [
            Item('Import...', menu='TOPBAR_MT_file_import'),
            Item('Merge...', 'wm.append'),
            *_off('Replace...', 'Link Revit', 'Link FBX', 'Link AutoCAD'),
        ]),
        Sub('Export', [
            Item('Export...', menu='TOPBAR_MT_file_export'),
            *_off('Export Selected...', 'Publish to DWF...', 'Real-Time Exporter...'),
        ]),
        Sub('Send to', [
            Sub('Send to Maya', []),
            Sub('Send to Motion Builder', []),
            Sub('Send to Mudbox', []),
        ]),
        Sub('Reference', [
            Item('XRef Objects...', 'wm.link'),
            Item('XRef Scene...', 'wm.link'),
            Item('Manage Links'),
            Item('Asset Tracking Toggle', menu='TOPBAR_MT_file_external_data', hotkey='Shift+T'),
        ]),
        Sub('Project', [
            Sub('Recent Projects', []),
            Item('Set Active Project...'),
            SEP,
            *_off('Create Empty...', 'Create Default...', 'Create From Current...'),
            SEP,
            _cmd('Configure Project Paths...', 'CONFIGURE_PATHS'),
        ]),
        _cmd('Summary Info...', 'SUMMARY_INFO'),
        Item('File Properties...'),
        Item('Preferences...', 'screen.userpref_show'),
        SEP,
        Item('Exit', 'wm.quit_blender'),
    ]),
    ('Edit', [
        Item('Undo Scene Operation', 'ed.undo', hotkey='Ctrl+Z'),
        Item('Redo Scene Operation', 'ed.redo', hotkey='Ctrl+Y'),
        SEP,
        _cmd('Hold', 'HOLD', hotkey='Ctrl+H'),
        _cmd('Fetch', 'FETCH', hotkey='Ctrl+Alt+F'),
        SEP,
        _cmd('Delete', 'DELETE', hotkey='Del'),
        Item('Clone', 'bsm.clone', hotkey='Ctrl+V'),
        SEP,
        _tool('Move', 'MOVE', hotkey='W'),
        _tool('Rotate', 'ROTATE', hotkey='E'),
        _tool('Scale', 'SCALE'),
        _cmd('Placement', 'PLACEMENT'),
        Item('Transform Type-In...', 'bsm.transform_typein', hotkey='F12'),
        Item('Transform Toolbox...'),
        SEP,
        Item('Select All', 'object.select_all', {'action': 'SELECT'}, hotkey='Ctrl+A'),
        Item('Select None', 'object.select_all', {'action': 'DESELECT'}, hotkey='Ctrl+D'),
        Item('Select Invert', 'object.select_all', {'action': 'INVERT'}, hotkey='Ctrl+I'),
        SEP,
        _cmd('Select Similar', 'SELECT_SIMILAR', hotkey='Ctrl+Shift+A'),
        _cmd('Select Instances', 'SELECT_INSTANCES'),
        Sub('Select By', [
            _cmd('Name', 'SELECT_BY_NAME', hotkey='H'),
            _cmd('Layer...', 'SELECT_BY_LAYER'),
            _cmd('Color', 'SELECT_BY_COLOR'),
        ]),
        SEP,
        Sub('Selection Region', [
            _cmd('Rectangular Region', 'SELECT_REGION_RECT'),
            _cmd('Circular Region', 'SELECT_REGION_CIRCLE'),
            _cmd('Fence Region', 'SELECT_REGION_FENCE'),
            _cmd('Lasso Region', 'SELECT_REGION_LASSO'),
            _cmd('Paint Selection Region', 'SELECT_REGION_PAINT'),
            SEP,
            _cmd('Window', 'SELECT_WINDOW'),
            _cmd('Crossing', 'SELECT_CROSSING'),
        ]),
        SEP,
        _cmd('Manage Selection Sets...', 'MANAGE_SELECTION_SETS'),
        SEP,
        _cmd('Object Properties...', 'OBJECT_PROPERTIES'),
    ]),
    ('Tools', [
        _cmd('Scene Explorer...', 'SCENE_EXPLORER'),
        _cmd('Layer Explorer...', 'LAYER_EXPLORER'),
        Item('Crease Explorer...'),
        Sub('All Global Explorers', []),
        Item('Manage Local Explorers...'),
        Sub('Local Scene Explorers', []),
        SEP,
        Sub('Containers', [
            Sub('Local Content', []),
            Sub('Inherited Content', []),
        ]),
        SEP,
        _cmd('Isolate Selection', 'ISOLATE', hotkey='Alt+Q'),
        _cmd('End Isolate', 'END_ISOLATE'),
        _cmd('Zoom Extents On Isolate', 'ZOOM_EXTENTS_ISOLATE'),
        SEP,
        Item('Display Floater...'),
        SEP,
        *_off('Manage Scene States...', 'Manage Templates...'),
        SEP,
        _cmd('Light Lister...', 'LIGHT_LISTER'),
        SEP,
        _cmd('Mirror...', 'MIRROR'),
        _cmd('Array...', 'ARRAY'),
        Sub('Align', [
            _cmd('Align...', 'ALIGN', hotkey='Alt+A'),
            _cmd('Quick Align', 'QUICK_ALIGN', hotkey='Shift+A'),
            Item('Spacing Tool...', hotkey='Shift+I'),
            Item('Clone and Align ...'),
            SEP,
            _cmd('Align to View...', 'ALIGN_TO_VIEW'),
            Item('Normal Align...', hotkey='Alt+N'),
            *_off('Align Camera', 'Place Highlight'),
        ]),
        _cmd('Snapshot...', 'SNAPSHOT'),
        SEP,
        Sub('Flow Studio', [
            Item('Launch Flow Studio'),
        ]),
        SEP,
        _cmd('Rename Objects...', 'RENAME_OBJECTS'),
        SEP,
        *_off('Assign Vertex Colors...', 'Color Clipboard...', 'Perspective Match...'),
        SEP,
        Item('Viewport Canvas...'),
        SEP,
        Sub('Screen Capture', [
            _cmd('Create Preview Animation...', 'PREVIEW_ANIMATION', hotkey='Shift+V'),
            _cmd('Capture Still Image...', 'CAPTURE_STILL'),
            SEP,
            _cmd('Play Preview Animation...', 'PLAY_PREVIEW'),
            *_off('Save Preview Animation As...', 'Open Preview Animation folder...'),
        ]),
        SEP,
        Sub('Grids and Snaps', [
            _cmd('Grid and Snap Settings...', 'GRID_SNAP_SETTINGS'),
            SEP,
            _cmd('Show Home Grid', 'SHOW_HOME_GRID', check=_grid_on),
            *_off('Activate Home Grid', 'Activate Grid Object', 'Align Grid to View'),
            SEP,
            _cmd('Snaps Toggle', 'SNAPS_TOGGLE', hotkey='S', check=_snap_on),
            _cmd('Angle Snap Toggle', 'ANGLE_SNAP', hotkey='A'),
            _cmd('Percent Snap Toggle', 'PERCENT_SNAP'),
            Item('Enable Axis Constraints in Snaps', hotkey='Alt+F3'),
        ]),
        Sub('Snap Working Pivot Tools', [
            Item('Place Working Pivot', hotkey='Ctrl+Shift+`'),
            Item('Selection Pivot', hotkey='Alt+Shift+S'),
            *_off('Align Working Pivot', 'Reset Working Pivot'),
            SEP,
            Item('Align Pivot To Working Pivot'),
            SEP,
            Item('Place Pivot Bounding Box'),
            SEP,
            *_off('Create Grid From Working Pivot', 'Create Point From Working Pivot'),
        ]),
        _cmd('Measure Distance...', 'MEASURE_DISTANCE'),
        SEP,
        Item('Channel Info...'),
        Sub('Mesh Inspector', _off('Activate Mesh Inspector', 'Mesh Auto Repair')),
    ]),
    ('Group', [
        _cmd('Group...', 'GROUP'),
        _cmd('Ungroup', 'UNGROUP'),
        SEP,
        _cmd('Open', 'GROUP_OPEN'),
        _cmd('Open Recursively', 'GROUP_OPEN_RECURSIVE'),
        _cmd('Close', 'GROUP_CLOSE'),
        SEP,
        _cmd('Attach', 'GROUP_ATTACH', hotkey='Ctrl+U'),
        _cmd('Detach', 'GROUP_DETACH'),
        SEP,
        _cmd('Explode', 'GROUP_EXPLODE'),
        SEP,
        Sub('Assembly', [
            *_off('Assemble', 'Disassemble'),
            SEP,
            *_off('Open', 'Close'),
            SEP,
            *_off('Attach', 'Detach'),
            SEP,
            Item('Explode'),
        ]),
    ]),
    ('Views', [
        _cmd('Undo View Change', 'UNDO_VIEW', hotkey='Shift+Z'),
        _cmd('Redo View Change', 'REDO_VIEW', hotkey='Shift+Y'),
        SEP,
        _cmd('Active Viewport Settings', 'VIEWPORT_CONFIG'),
        _cmd('Viewports Configuration...', 'VIEWPORT_CONFIG'),
        _cmd('Redraw All Views', 'REDRAW_ALL', hotkey='`'),
        SEP,
        Sub('Set Active Viewport', [
            _view('Perspective', 'PERSP', hotkey='P'),
            _view('Orthographic', 'ORTHO', hotkey='U'),
            _view('Front', 'FRONT', hotkey='F'),
            _view('Back', 'BACK'),
            _view('Top', 'TOP', hotkey='T'),
            _view('Bottom', 'BOTTOM'),
            _view('Left', 'LEFT', hotkey='L'),
            _view('Right', 'RIGHT'),
            SEP,
            _cmd('Save Active View', 'ACTIVE_VIEW_SAVE'),
            _cmd('Restore Active View', 'ACTIVE_VIEW_RESTORE'),
        ]),
        _cmd('Save Active View', 'ACTIVE_VIEW_SAVE'),
        _cmd('Restore Active View', 'ACTIVE_VIEW_RESTORE'),
        SEP,
        Sub('ViewCube', _VIEWCUBE),
        Sub('SteeringWheels', _STEERINGWHEELS),
        SEP,
        _cmd('Create Physical Camera From View', 'CAMERA_FROM_VIEW', hotkey='Alt+Shift+C, Ctrl+C'),
        _cmd('Create Standard Camera From View', 'CAMERA_FROM_VIEW', hotkey='Ctrl+Alt+Shift+C'),
        SEP,
        Sub('Show Materials in Viewport As', _SHOW_MATERIALS_IN_VIEWPORT_AS),
        SEP,
        Sub('Viewport Lighting and Shadows', [
            Item('Auto Display Selected Lights'),
            SEP,
            *_off('Lock Selected Lights', 'Unlock Selected Lights'),
        ]),
        SEP,
        Sub('xView', _XVIEW),
        SEP,
        Sub('Viewport Background', _VIEWPORT_BACKGROUND),
        SEP,
        _cmd('Show Transform Gizmo', 'SHOW_GIZMO'),
        _cmd('Show Ghosting', 'SHOW_GHOSTING'),
        _cmd('Show Key Times', 'SHOW_KEY_TIMES'),
        _cmd('Shade Selected', 'SHADE_SELECTED'),
        Item('Show Dependencies'),
        SEP,
        Item('Update During Spinner Drag'),
        Item('Adaptive Degradation', hotkey='O'),
        Item('Progressive Display'),
        SEP,
        _cmd('Expert Mode', 'EXPERT_MODE', hotkey='Ctrl+Alt+X'),
    ]),
    ('Create', [
        Sub('Standard Primitives', [
            _create('Box', 'BOX'),
            _create('Cone', 'CONE'),
            _create('Sphere', 'SPHERE'),
            _create('GeoSphere', 'GEOSPHERE'),
            _create('Cylinder', 'CYLINDER'),
            _create('Tube', 'TUBE'),
            _create('Torus', 'TORUS'),
            _create('Pyramid', 'PYRAMID'),
            _create('Teapot', 'TEAPOT'),
            _create('Plane', 'PLANE'),
            _create('TextPlus', 'TEXTPLUS'),
        ]),
        Sub('Extended Primitives', [
            *_off('Hedra', 'Torus Knot'),
            _create('Chamfer Box', 'CHAMFER_BOX'),
            _create('Chamfer Cylinder', 'CHAMFER_CYL'),
            Item('Oil Tank'),
            _create('Capsule', 'CAPSULE'),
            *_off('Spindle', 'L-Extrusion', 'Gengon', 'C-Extrusion', 'RingWave', 'Hose', 'Prism'),
        ]),
        Sub('AEC Objects', [
            *_off('Foliage', 'Railing', 'Wall'),
            SEP,
            *_off('Pivot Door', 'Sliding Door', 'BiFold Door'),
            SEP,
            *_off('Straight Stair', 'L-Type Stair', 'U-Type Stair', 'Spiral Stair'),
            SEP,
            *_off(
                'Awning Window', 'Casement Window', 'Fixed Window', 'Pivoted Window', 'Sliding Window',
                'Projected Window'),
            SEP,
            Sub('MCG Tools', [
                Sub('MCG Controllers', _off(
                    'MCG LookAt Constraint', 'MCG Ray to Surface Position Constraint',
                    'MCG Ray to Surface Position and Orientation Constraints',
                    'MCG Ray to Surface Transform Constraint', 'MCG 1 DOF Rotation Spring Controller',
                    'MCG 3 DOF Rotation Spring Controller')),
            ]),
        ]),
        Sub('Compound', _off(
            'Morph', 'Scatter', 'Conform', 'Connect', 'BlobMesh', 'ShapeMerge', 'Boolean', 'Terrain', 'Loft',
            'Mesher', 'ProBoolean', 'ProCutter')),
        Sub('Particles', [
            Item('Particle Flow Source'),
            SEP,
            *_off('Spray', 'Snow', 'Blizzard', 'PArray', 'PCloud', 'Super Spray'),
        ]),
        Sub('Patch Grids', _off('Quad Patch', 'Tri Patch')),
        Sub('NURBS', [
            _create('CV Surface', 'CV_SURFACE'),
            _create('Point Surface', 'POINT_SURFACE'),
            SEP,
            _create('CV Curve', 'CV_CURVE'),
            _create('Point Curve', 'POINT_CURVE'),
        ]),
        Sub('Point Cloud', []),
        Sub('Dynamics', _off('Damper', 'Spring')),
        SEP,
        Sub('Shapes', [
            _create('Line', 'LINE'),
            _create('Rectangle', 'RECTANGLE'),
            _create('Circle', 'CIRCLE'),
            _create('Ellipse', 'ELLIPSE'),
            _create('Arc', 'ARC'),
            _create('Donut', 'DONUT'),
            _create('NGon', 'NGON'),
            _create('Star', 'STAR'),
            _create('Text', 'TEXT'),
            _create('Helix', 'HELIX'),
            *_off('Section', 'Egg', 'Freehand'),
            SEP,
            Item('ShapeBoolean'),
        ]),
        Sub('Extended Shapes', _off('WRectangle', 'Channel', 'Angle', 'Tee', 'Wide Flange')),
        SEP,
        Sub('Lights', [
            Sub('Photometric Lights', [
                _create('Target Light', 'TARGET_LIGHT'),
                _create('Free Light', 'FREE_LIGHT'),
            ]),
            Sub('Standard Lights', [
                _create('Target Spotlight', 'TARGET_SPOT'),
                _create('Free Spotlight', 'FREE_SPOT'),
                _create('Target Directional', 'TARGET_DIRECT'),
                _create('Directional', 'FREE_DIRECT'),
                _create('Omni', 'OMNI'),
                _create('Skylight', 'SKYLIGHT'),
                SEP,
                Item('Add Default Lights to Scene'),
            ]),
            SEP,
            Item('Daylight System'),
            _create('Sun Positioner', 'SUN_POSITIONER'),
        ]),
        Sub('Cameras', [
            _create('Free Camera', 'FREE_CAMERA'),
            _create('Target Camera', 'TARGET_CAMERA'),
            _create('Physical Camera', 'PHYSICAL_CAMERA'),
            SEP,
            _cmd('Create Physical Camera From View', 'CAMERA_FROM_VIEW', hotkey='Alt+Shift+C, Ctrl+C'),
            _cmd('Create Standard Camera From View', 'CAMERA_FROM_VIEW', hotkey='Ctrl+Alt+Shift+C'),
        ]),
        SEP,
        Sub('Helpers', [
            _create('Dummy', 'DUMMY'),
            Item('Expose Transform'),
            _create('Grid', 'GRID'),
            _create('Point', 'POINT'),
            Item('Container'),
            _create('Arrow', 'ARROW'),
            SEP,
            _create('Tape Measure', 'TAPE'),
            _create('Protractor', 'PROTRACTOR'),
            _create('Compass', 'COMPASS'),
            SEP,
            Item('Camera Point'),
            SEP,
            Item('Influence Helper'),
            SEP,
            *_off('Delegate', 'Crowd'),
            SEP,
            Sub('Atmospherics', _off('Box Gizmo', 'Cylinder Gizmo', 'Sphere Gizmo')),
            Sub('Manipulators', _off('Slider', 'Plane Angle', 'Cone Angle')),
            Sub('Particle Flow', _off(
                'Speed by Icon', 'Find Target', 'Particle Paint', 'Birth Texture', 'Initial State',
                'Group Select')),
        ]),
        Sub('SpaceWarps', [
            Sub('Forces', [
                _create('Motor', 'MOTOR'),
                _create('Push', 'PUSH'),
                _create('Drag', 'DRAG'),
                _create('Vortex', 'VORTEX'),
                _create('Path Follow', 'PATH_FOLLOW'),
                Item('PBomb'),
                _create('Displace', 'DISPLACE_WARP'),
                _create('Gravity', 'GRAVITY'),
                _create('Wind', 'WIND'),
                Item('Motion Field'),
            ]),
            Sub('Deflectors', _off(
                'POmniFlect', 'SOmniFlect', 'SDeflector', 'UOmniFlect', 'UDeflector', 'Deflector')),
            Sub('Geometric/Deformable', [
                *_off('FFD(Box)', 'FFD(Cyl)', 'Wave', 'Ripple'),
                _create('Displace', 'DISPLACE_WARP'),
                *_off('Conform', 'Bomb'),
            ]),
            Sub('Modifier-Based', _off('Bend', 'Noise', 'Skew', 'Taper', 'Twist', 'Stretch')),
            Sub('Particles & Dynamics', [
                Item('Vector Field'),
            ]),
        ]),
        Sub('Systems', [
            _create('Bones IK Chain', 'BONES'),
            Item('Biped'),
            SEP,
            Item('Daylight System'),
        ]),
        SEP,
        Sub('Fluids', [
            Item('Liquid', 'object.quick_liquid'),
            Item('Fluid Loader'),
        ]),
    ]),
    ('Modifiers', [
        Sub('Selection Modifiers', _mods(
            'FFD Select', 'Mesh Select', 'Patch Select', 'Poly Select', 'Select By Channel', 'Spline Select',
            'Volume Select')),
        SEP,
        Sub('Patch/Spline Editing', _mods(
            'Cross Section', 'Delete Patch', 'Delete Spline', 'Edit Patch', 'Edit Spline', 'Spline Chamfer',
            'Lathe', 'Normalize Spline', 'Renderable Spline Modifier', 'Surface', 'Sweep', 'Trim/Extend',
            'Optimize Spline', 'Spline Mirror', 'Spline Relax')),
        Sub('Mesh Editing', _mods(
            'Attribute Transfer', 'Cap Holes', 'Chamfer', 'Delete Mesh', 'Edit Mesh', 'Edit Normals', 'Edit Poly',
            'Extrude', 'Face Extrude', 'MultiRes', 'Normal Modifier', 'Optimize', 'ProOptimizer', 'Quadify Mesh',
            'Smooth', 'STL Check', 'Symmetry', 'Tessellate', 'Vertex Paint', 'Vertex Weld', 'Weighted Normals')),
        SEP,
        Sub('Conversion', _mods('Turn To Mesh', 'Turn To Patch', 'Turn To Poly')),
        SEP,
        Sub('Animation', _mods(
            'Attribute Holder', 'Flex', 'Linked XForm', 'Melt', 'Morpher', 'Patch Deform', 'Patch Deform (WSM)',
            'Path Deform', 'Spline Influence', 'Spline Morph', 'Spline Overlap', 'Path Deform (WSM)', 'Skin',
            'Skin Morph', 'Skin Wrap', 'Skin Wrap Patch', 'SplineIk Control', 'Surf Deform', 'Surf Deform (WSM)')),
        SEP,
        Sub('Cloth', _mods('Cloth', 'Garment Maker', 'Welder')),
        SEP,
        Sub('Hair and Fur', [
            _mod('Hair and Fur (WSM)'),
        ]),
        SEP,
        Sub('UV Coordinates', _mods(
            'Camera Map', 'Camera Map (WSM)', 'MapScaler (WSM)', 'Projection', 'Unwrap UVW', 'UVW Map',
            'UVW Mapping Add', 'UVW Mapping Clear', 'UVW XForm')),
        SEP,
        Sub('Cache Tools', _mods('Point Cache', 'Point Cache (WSM)')),
        SEP,
        Sub('Subdivision Surfaces', _mods(
            'Crease', 'CreaseSet', 'HSDS Modifier', 'MeshSmooth', 'OpenSubdiv', 'TurboSmooth')),
        SEP,
        Sub('Free Form Deformers', _mods('FFD 2x2x2', 'FFD 3x3x3', 'FFD 4x4x4', 'FFD Box', 'FFD Cylinder')),
        SEP,
        Sub('Parametric Deformers', _mods(
            'Affect Region', 'Bend', 'Conform Modifier', 'Data Channel', 'Displace', 'Lattice', 'Mirror', 'Noise',
            'Noise Plus', 'Physique', 'Push', 'Preserve', 'Relax', 'Ripple', 'Shell', 'Slice', 'Skew', 'Stretch',
            'Spherify', 'Squeeze', 'Twist', 'Taper', 'Substitute', 'XForm', 'Wave')),
        SEP,
        Sub('Surface', _mods('Disp Approx', 'Displace Mesh (WSM)', 'Material', 'Material By Element')),
        SEP,
        Sub('NURBS Editing', _mods('Disp Approx', 'Surf Deform', 'Surface Select')),
        SEP,
        Sub('Radiosity', _mods('Subdivide', 'Subdivide (WSM)')),
        SEP,
        Sub('Cameras', [
            _mod('Camera Correction'),
        ]),
    ]),
    ('Animation', [
        *_off('Load Animation...', 'Save Animation...'),
        SEP,
        Sub('IK Solvers', [
            *_off('HI Solver', 'HD Solver', 'IK Limb Solver'),
            SEP,
            Item('SplineIK Solver'),
        ]),
        SEP,
        Sub('Constraints', [
            _constraint('Attachment Constraint', 'ATTACHMENT'),
            _constraint('Surface Constraint', 'SURFACE'),
            SEP,
            _constraint('Path Constraint', 'PATH'),
            _constraint('Position Constraint', 'POSITION'),
            SEP,
            _constraint('Link Constraint', 'LINK'),
            SEP,
            _constraint('LookAt Constraint', 'LOOKAT'),
            _constraint('Orientation Constraint', 'ORIENTATION'),
        ]),
        SEP,
        Sub('Transform Controllers', [
            _constraint('Link Constraint', 'LINK'),
            *_off('Position/Rotation/Scale', 'Script', 'List'),
        ]),
        Sub('Position Controllers', [
            *_off(
                'Audio', 'Bezier', 'Expression', 'Linear', 'Motion Capture', 'Noise', 'TCB Position', 'Reaction',
                'Spring', 'Script', 'X Y Z', 'List'),
            SEP,
            _constraint('Attachment Constraint', 'ATTACHMENT'),
            _constraint('Path Constraint', 'PATH'),
            _constraint('Position Constraint', 'POSITION'),
            _constraint('Surface Constraint', 'SURFACE'),
        ]),
        Sub('Rotation Controllers', [
            *_off(
                'Audio', 'Euler X Y Z', 'Linear', 'Motion Capture', 'Noise', 'TCB Rotation', 'Reaction', 'Script',
                'Smooth', 'List'),
            SEP,
            _constraint('LookAt Constraint', 'LOOKAT'),
            _constraint('Orientation Constraint', 'ORIENTATION'),
        ]),
        Sub('Scale Controllers', _off(
            'Audio', 'Bezier', 'Expression', 'Linear', 'Motion Capture', 'Noise', 'TCB Scale', 'Reaction', 'Script',
            'X Y Z', 'List')),
        Sub('MCG Controllers', _off(
            'MCG LookAt Constraint', 'MCG Ray to Surface Position Constraint',
            'MCG Ray to Surface Position and Orientation Constraints', 'MCG Ray to Surface Transform Constraint',
            'MCG 1 DOF Rotation Spring Controller', 'MCG 3 DOF Rotation Spring Controller')),
        Sub('CAT', _off('Capture Animation', 'Pose Mixer', 'Apply Max IK')),
        Sub('MassFX', [
            Sub('Rigid Bodies', [
                Item('Set Selected as Dynamic Rigid Body', 'rigidbody.objects_add', {'type': 'ACTIVE'}),
                Item('Set Selected as Kinematic Rigid Body'),
                Item('Set Selected as Static Rigid Body', 'rigidbody.objects_add', {'type': 'PASSIVE'}),
                SEP,
                *_off('Create Dynamic Ragdoll', 'Create Kinematic Ragdoll', 'Remove Ragdoll'),
            ]),
            Sub('Cloth', [
                Item('Create mCloth', 'object.modifier_add', {'type': 'CLOTH'}),
                Item('Remove mCloth'),
            ]),
            Sub('Constraints', [
                Item('Create Rigid Constraint', 'rigidbody.connect', {'con_type': 'FIXED'}),
                Item('Create Slide Constraint', 'rigidbody.connect', {'con_type': 'SLIDER'}),
                Item('Create Hinge Constraint', 'rigidbody.connect', {'con_type': 'HINGE'}),
                Item('Create Twist Constraint'),
                Item('Create Ball-and-Socket Constraint', 'rigidbody.connect', {'con_type': 'POINT'}),
                Item('Create Universal Constraint'),
            ]),
            Sub('Simulation', [
                Item('Play Simulation', 'screen.animation_play'),
                Item('Step Simulation', 'screen.frame_offset', {'delta': 1}),
                Item('Reset Simulation', 'screen.frame_jump', {'end': False}),
                SEP,
                Item('Bake All Objects', 'ptcache.bake_all', {'bake': True}),
                Item('Bake Selected Objects', 'rigidbody.bake_to_keyframes'),
                Item('Unbake All Objects', 'ptcache.free_bake_all'),
                Item('Unbake Selected Objects'),
            ]),
            Sub('Utilities', [
                *_off('Show MassFX Tools', 'Open Dynamics Explorer'),
                SEP,
                *_off('Validate MassFX Scene', 'Export MassFX Scene'),
                SEP,
                Item('Capture Current Transforms'),
                SEP,
                Item('About MassFX'),
            ]),
        ]),
        Sub('Fluids', [
            Item('Liquid', 'object.quick_liquid'),
            *_off('Fluid Loader', 'Motion Field', 'Simulation View'),
        ]),
        SEP,
        Sub('Offset Controllers', _off('Add Offset Controllers', 'Delete Offset Controllers', 'Remove All')),
        *_off('Parameter Editor...', 'Parameter Collector...'),
        SEP,
        Sub('Wire Parameters', _off('Wire Parameters...', 'Parameter Wire Dialog...')),
        SEP,
        Item('Animation Layers...'),
        SEP,
        Item('Reaction Manager...'),
        SEP,
        Item('Bone Tools...'),
        SEP,
        *_off('Set as Skin Pose', 'Assume Skin Pose', 'Skin Pose Mode'),
        SEP,
        Item('Toggle Limits'),
        SEP,
        _cmd('Delete Selected Animation', 'DELETE_SELECTED_ANIMATION'),
        SEP,
        Sub('Populate', [
            Item('Populate Tools...'),
        ]),
        Item('Walkthrough Assistant...'),
        Sub('Presets', [
            Item('Load Preset'),
            SEP,
            *_off('Add Scene Preset to Selected', 'Remove Preset from Selected'),
            SEP,
            Item('Create Preset'),
            SEP,
            Item('Remove Preset From Disk'),
        ]),
    ]),
    ('Graph Editors', [
        _editor('Track View - Curve Editor...', 'GRAPH'),
        _editor('Track View - Dope Sheet...', 'DOPESHEET'),
        _editor('New Track View...', 'GRAPH'),
        Item('Delete Track View...'),
        Sub('Saved Track Views', _off(
            'Saved Track View 1', 'Saved Track View 2', 'Saved Track View 3', 'Saved Track View 4',
            'Saved Track View 5', 'Saved Track View 6', 'Saved Track View 7', 'Saved Track View 8',
            'Saved Track View 9', 'Saved Track View 10', 'Saved Track View 11', 'Saved Track View 12',
            'Saved Track View 13')),
        SEP,
        _cmd('New Schematic View...', 'SCHEMATIC_VIEW'),
        Item('Delete Schematic View...'),
        Sub('Saved Schematic Views', _off(
            'Saved Schematic View 1', 'Saved Schematic View 2', 'Saved Schematic View 3', 'Saved Schematic View 4',
            'Saved Schematic View 5', 'Saved Schematic View 6', 'Saved Schematic View 7', 'Saved Schematic View 8',
            'Saved Schematic View 9', 'Saved Schematic View 10', 'Saved Schematic View 11',
            'Saved Schematic View 12', 'Saved Schematic View 13')),
        SEP,
        Item('Particle View Toggle', hotkey='6'),
        SEP,
        _cmd('Motion Mixer...', 'MOTION_MIXER'),
    ]),
    ('Rendering', [
        _cmd('Render', 'RENDER', hotkey='Shift+Q, Shift+F9'),
        *_off('Render in the Cloud', 'Open Autodesk A360 Gallery'),
        _editor('Render Setup...', 'RENDER', hotkey='F10'),
        _cmd('Rendered Frame Window...', 'RENDERED_FRAME_WINDOW'),
        SEP,
        *_off('Radiosity...', 'Light Tracer...'),
        SEP,
        Item('Scene Converter...'),
        SEP,
        _cmd('Exposure Control...', 'EXPOSURE'),
        SEP,
        _cmd('Environment...', 'ENVIRONMENT', hotkey='8'),
        *_off('Effects...', 'Raytracer Settings...', 'Raytrace Global Include/Exclude...'),
        SEP,
        *_off('Render to Texture...', 'Render Surface Map...'),
        SEP,
        Sub('Material Editor', [
            _editor('Compact Material Editor...', 'COMPACT'),
            _editor('Slate Material Editor...', 'MATERIAL'),
        ]),
        Item('Material/Map Browser...'),
        _cmd('Material Explorer...', 'MATERIAL_EXPLORER'),
        SEP,
        Item('Video Post...'),
        SEP,
        Item('Panorama Exporter...'),
        _cmd('Print Size Assistant...', 'PRINT_SIZE'),
        SEP,
        _cmd('Color Management...', 'COLOR_MANAGEMENT'),
        Item('Compare Media in RAM Player...'),
    ]),
    ('Customize', [
        _cmd('Customize User Interface...', 'CUSTOMIZE_UI'),
        _cmd('Hotkey Editor...', 'HOTKEY_EDITOR'),
        Item('Menu Editor...'),
        SEP,
        *_off('Load Custom UI Scheme...', 'Save Custom UI Scheme...'),
        SEP,
        Item('Custom Defaults Switcher...'),
        SEP,
        *_off('Revert to Startup UI Layout', 'Lock UI Layout'),
        SEP,
        Sub('Show UI', [
            *_off('Command Panel', 'Ribbon', 'Shared Views', 'Time Slider', 'Viewport Layout Tabs'),
            SEP,
            Sub('Float Viewport', _off('Floating Viewport - 2', 'Floating Viewport - 3')),
            SEP,
            *_off('Main Toolbar', 'Floating Toolbars'),
        ]),
        Sub('Show Editors', [
            _editor('Material Editor', 'MATERIAL_LAST', hotkey='M'),
            _editor('Curve Editor', 'GRAPH'),
            _editor('Dope Sheet', 'DOPESHEET'),
            *_off('Max Creation Graph Editor', 'Parameter Editor'),
            SEP,
            Item('Asset Tracking', menu='TOPBAR_MT_file_external_data', hotkey='Shift+T'),
            _cmd('Light Lister', 'LIGHT_LISTER'),
            _cmd('Object Properties', 'OBJECT_PROPERTIES'),
            Item('Particle View', hotkey='6'),
        ]),
        Sub('Show Explorers', [
            _cmd('Scene Explorer', 'SCENE_EXPLORER'),
            _cmd('Layer Explorer', 'LAYER_EXPLORER'),
            *_off(
                'Crease Explorer', 'Container Explorer', 'Dynamics Explorer', 'Light Explorer',
                'Missing Plug-in Explorer', 'Revit Property Explorer'),
        ]),
        SEP,
        _cmd('Configure Project Paths...', 'CONFIGURE_PATHS'),
        _cmd('Configure User and System Paths...', 'CONFIGURE_PATHS'),
        SEP,
        _cmd('Units Setup...', 'UNITS_SETUP'),
        SEP,
        _cmd('Plug-in Manager...', 'PLUGIN_MANAGER'),
        SEP,
        Item('Preferences...', 'screen.userpref_show'),
    ]),
    ('Scripting', [
        Item('Install Max Creation Graph (.mcg) Package...'),
        SEP,
        *_off('New Max Creation Graph', 'Open Max Creation Graph...', 'Max Creation Graph Editor'),
        SEP,
        *_off('Create MCG Geometry...', 'Create and Apply MCG Modifier...'),
        SEP,
        _cmd('New Script', 'NEW_SCRIPT'),
        _cmd('Open Script...', 'OPEN_SCRIPT'),
        _cmd('Run Script...', 'RUN_SCRIPT'),
        SEP,
        _cmd('Scripting Listener...', 'LISTENER', hotkey='F11'),
        _cmd('Scripting Editor...', 'SCRIPT_EDITOR'),
        SEP,
        _cmd('Macro Recorder', 'MACRO_RECORDER'),
        SEP,
        Item('Visual MAXScript Editor...'),
        SEP,
        Item('Debugger Dialog...'),
        SEP,
        Item('MAXScript Help...'),
        SEP,
        _cmd('Python Help...', 'PYTHON_HELP'),
    ]),
    ('Help', [
        Item('Autodesk 3ds Max Help', 'wm.url_open_preset', {'type': 'MANUAL'}),
        Item("What's New", 'wm.url_open_preset', {'type': 'RELEASE_NOTES'}),
        Item('Welcome Screen', 'wm.splash'),
        *_off('Autodesk Learning Resources', 'Plugin Help...'),
        Sub('Tutorials', _off('3ds Max Learning Channel', 'More Learning Resources')),
        Sub('3ds Max Developer Resources', [
            Item('3ds Max Developer Help', 'wm.url_open_preset', {'type': 'API'}),
            Item('3ds Max SDK Download'),
            Item('Autodesk Developer Network', 'wm.url_open', {'url': 'https://developer.blender.org/docs/'}),
        ]),
        SEP,
        _cmd('Search 3ds Max Commands...', 'SEARCH_COMMANDS', hotkey='X'),
        SEP,
        Sub('3ds Max Communities', _off('Join Autodesk Feedback Community', 'Student Community')),
        Sub('Feedback', [
            Item('Report a Problem...', 'wm.url_open_preset', {'type': 'BUG'}),
            *_off('Ideas for 3ds Max', 'Desktop Analytics Program...'),
        ]),
        Sub('3ds Max Services and Support', [
            Item('Support Center', 'wm.url_open', {'url': 'https://www.blender.org/support'}),
            *_off('Data Exchange Solutions', 'Certified Hardware'),
        ]),
        Sub('3ds Max Resources and Tools', [
            Item('Autodesk App Store', 'wm.url_open_preset', {'type': 'EXTENSIONS'}),
            *_off('FBX Review', 'Character Generator'),
            Item('Diagnose Video Hardware', 'wm.sysinfo'),
            Item('Keyboard Shortcut Map', 'bsm.shortcuts'),
        ]),
        Sub('Autodesk Product Information', [
            Item('3ds Max Home Page', 'wm.url_open_preset', {'type': 'BLENDER'}),
            *_off('Check for Updates', 'Try Other Autodesk Products'),
            SEP,
            Item('About 3ds Max', 'wm.splash_about'),
        ]),
    ]),
]

VIEWPORT_LABEL = {
    'PLUS': [
        Item('Maximize Viewport Toggle', 'bsm.quad_view', hotkey='Alt+W'),
        Sub('Active Viewport', _off(
            'Active Viewport 1', 'Active Viewport 2', 'Active Viewport 3', 'Active Viewport 4')),
        Item('Disable Viewport', hotkey='Ctrl+Shift+D'),
        SEP,
        Item('Presentation Mode', 'screen.screen_full_area', {'use_hide_panels': True}, hotkey='Ctrl+Space',
             check=_fullscreen_on),
        SEP,
        _cmd('Show Grids', 'SHOW_HOME_GRID', hotkey='G', check=_grid_on),
        SEP,
        Sub('ViewCube', _VIEWCUBE),
        Sub('SteeringWheels', _STEERINGWHEELS),
        SEP,
        Sub('xView', _XVIEW),
        SEP,
        Sub('Create Preview', [
            _cmd('Capture Still Image...', 'CAPTURE_STILL'),
            _cmd('Create Preview Animation...', 'PREVIEW_ANIMATION', hotkey='Shift+V'),
            SEP,
            _cmd('Play Preview Animation...', 'PLAY_PREVIEW'),
            Item('Save Preview Animation As...'),
        ]),
        SEP,
        _cmd('Configure Viewports...', 'VIEWPORT_CONFIG'),
        SEP,
        Item('2D Pan Zoom Mode'),
        SEP,
        Sub('Float Viewport', _off('Floating Viewport - 2', 'Floating Viewport - 3')),
    ],
    'POV': [
        # Max lists the scene's cameras and spot/directional lights here (Default.mnxb
        # holds placeholders "Viewport Camera 1..10"); these menus list the real objects.
        Item('Cameras', menu='BSM_MT_view_cameras'),
        Item('Lights', menu='BSM_MT_view_lights'),
        SEP,
        _view('Perspective', 'PERSP', hotkey='P'),
        _view('Orthographic', 'ORTHO', hotkey='U'),
        _view('Top', 'TOP', hotkey='T'),
        _view('Bottom', 'BOTTOM'),
        _view('Front', 'FRONT', hotkey='F'),
        _view('Back', 'BACK'),
        _view('Left', 'LEFT', hotkey='L'),
        _view('Right', 'RIGHT'),
        SEP,
        _cmd('Restore Active View', 'ACTIVE_VIEW_RESTORE'),
        _cmd('Save Active View', 'ACTIVE_VIEW_SAVE'),
        SEP,
        Sub('Extended Viewports', [
            Sub('Track View', [
                Item('New'),
                SEP,
                *_off(
                    'Saved Trackview 1', 'Saved Trackview 2', 'Saved Trackview 3', 'Saved Trackview 4',
                    'Saved Trackview 5'),
            ]),
            Sub('Scene Explorer', [
                Item('New'),
                SEP,
                *_off(
                    'Viewport Scene Explorer 1', 'Viewport Scene Explorer 2', 'Viewport Scene Explorer 3',
                    'Viewport Scene Explorer 4', 'Viewport Scene Explorer 5', 'Viewport Scene Explorer 6',
                    'Viewport Scene Explorer 7', 'Viewport Scene Explorer 8', 'Viewport Scene Explorer 9',
                    'Viewport Scene Explorer 10', 'More...'),
            ]),
            Sub('Schematic View', [
                Item('New'),
                SEP,
                *_off(
                    'Schematic View Save 1', 'Schematic View Save 2', 'Schematic View Save 3',
                    'Schematic View Save 4', 'Schematic View Save 5'),
            ]),
            SEP,
            Sub('Grid', _off('Front', 'Back', 'Top', 'Bottom', 'Left', 'Right', 'Display Planes')),
            Item('Shape'),
            SEP,
            *_off(
                'Extended Views 1', 'Extended Views 2', 'Extended Views 3', 'Extended Views 4', 'Extended Views 5',
                'Extended Views 6', 'Extended Views 7', 'Extended Views 8', 'Extended Views 9',
                'Extended Views 10'),
        ]),
        SEP,
        Item('Show Safe Frames', 'wm.context_toggle', {'data_path': 'scene.camera.data.show_safe_areas'},
             hotkey='Shift+F', check=_safe_frames_on),
        *_off('Viewport Clipping', 'Select Viewport Node', 'Select Viewport Node Target'),
        SEP,
        _cmd('Undo Viewport Operation', 'UNDO_VIEW', hotkey='Shift+Z'),
        _cmd('Redo Viewport Operation', 'REDO_VIEW', hotkey='Shift+Y'),
    ],
    'PRESET': [
        _shade('High Quality', 'HIGH_QUALITY', hotkey='Shift+F3'),
        _shade('Standard', 'STANDARD'),
        _shade('Performance', 'PERFORMANCE'),
        _shade('DX Mode', 'DX_MODE'),
        Item('User Defined'),
        SEP,
        Sub('Lighting and Shadows', [
            _shade('Illuminate with Default Lights', 'DEFAULT_LIGHTS'),
            _shade('Illuminate with Scene Lights', 'SCENE_LIGHTS'),
            Sub('Scene Lights Control', [
                Item('Auto Display Selected Lights'),
                SEP,
                *_off('Lock Selected Lights', 'Unlock Selected Lights'),
            ]),
            SEP,
            Item('Progressive Skylight'),
            _shade('Shadows', 'SHADOWS'),
        ]),
        Sub('Materials', _SHOW_MATERIALS_IN_VIEWPORT_AS),
        SEP,
        _cmd('Viewports Configuration', 'VIEWPORT_CONFIG'),
        _cmd('Active Viewport Settings', 'VIEWPORT_CONFIG'),
    ],
    'SHADING': [
        _shade('Default Shading', 'DEFAULT_SHADING'),
        _shade('Facets', 'FACETS'),
        _shade('Bounding Box', 'BOUNDING_BOX'),
        _shade('Flat Color', 'FLAT_COLOR'),
        _shade('Hidden Line', 'HIDDEN_LINE'),
        _shade('Clay', 'CLAY'),
        Item('Model Assist'),
        Sub('Stylized', _off('Graphite', 'Color Pencil', 'Ink', 'Color Ink', 'Acrylic', 'Pastel', 'Tech')),
        SEP,
        _shade('Wireframe Override', 'WIREFRAME_OVERRIDE', check=_wireframe_on),
        _shade('Edged Faces', 'EDGED_FACES', check=_edged_faces_on),
        SEP,
        Sub('Display Selected', [
            Item('Display Selected With Edged Faces'),
            _shade('Shade Selected Faces', 'SHADE_SELECTED', hotkey='F2'),
        ]),
        SEP,
        Sub('Viewport Background', _VIEWPORT_BACKGROUND),
        SEP,
        _cmd('Viewport Preferences', 'VIEWPORT_CONFIG'),
        Item('Viewport Filter'),
    ],
}

# ---------------------------------------------------------------- drawing
def _op_rna(idname):
    module, _, name = idname.partition('.')
    try:
        return getattr(getattr(bpy.ops, module), name).get_rna_type()
    except (AttributeError, KeyError):
        return None


def _menu_exists(name):
    return name in C_MENUS or hasattr(bpy.types, name)


def _resolve(item, context):
    """Operator idname to run for this entry now, or None when it cannot run as specified."""
    if not item.op:
        return None
    op = MODE_OPS.get(item.op, {}).get(getattr(context, 'mode', ''), item.op)
    rna = _op_rna(op)
    if rna is None:
        return None
    for key, value in item.props.items():
        prop = rna.properties.get(key)
        # A missing property or an unknown enum value would silently run the wrong action.
        if prop is None or (prop.type == 'ENUM' and len(prop.enum_items) and value not in prop.enum_items.keys()):
            return None
    return op


def _checked(item, context):
    try:
        return bool(item.check(context))
    except Exception:
        return False


def _set_props(kmi):
    props = kmi.properties
    if props is None:
        return {}
    return {p.identifier: getattr(props, p.identifier) for p in props.bl_rna.properties
            if p.identifier != 'rna_type' and props.is_property_set(p.identifier)}


def _blender_shortcuts(context, ops):
    """(op, props) pairs Blender itself will annotate with a shortcut in this menu.

    Approximates Blender's lookup: window/screen keymaps, plus the keymaps of the area
    the menu was opened from (3D View also searches the object/mesh mode keymaps).
    """
    keyconfig = context.window_manager.keyconfigs.user
    if not keyconfig or not ops:
        return []
    area = getattr(context, 'area', None)
    space = area.type if area else None
    names = {'Window', 'Screen'} | ({'Object Mode', 'Mesh'} if space == 'VIEW_3D' else set())
    found = []
    for keymap in keyconfig.keymaps:
        if keymap.name in names or (space and keymap.space_type == space):
            found.extend((kmi.idname, _set_props(kmi)) for kmi in keymap.keymap_items
                         if kmi.active and kmi.idname in ops)
    return found


def _text_width(context):
    """Width function in the menu font, or None when text cannot be measured."""
    try:
        from .localization import blf
        prefs = context.preferences
        blf.size(0, prefs.ui_styles[0].widget.points * (prefs.system.ui_scale or 1.0))
        if blf.dimensions(0, '    ')[0] <= 0:
            return None
        return lambda text: blf.dimensions(0, text)[0]
    except Exception:
        return None


def _display_texts(context, items):
    """Labels with Max hotkey hints padded into one aligned column (Blender menus have no API for it)."""
    entries = [item for item in items if not isinstance(item, Sep)]
    hinted = [item for item in entries if isinstance(item, Item) and item.hotkey]
    if not hinted:
        return {}
    shown = _blender_shortcuts(context, {item.op for item in hinted if item.op})
    hinted = [item for item in hinted if (item.op, item.props) not in shown]
    width = _text_width(context) if hinted else None
    if width is None:
        return {id(item): item.label + '    ' + item.hotkey for item in hinted}
    column = max(width(item.label) for item in entries) + width('    ')
    space, fine = width(' '), width(' ')
    texts = {}
    for item in hinted:
        need = column - width(item.label)
        count = max(1, int(need // space))
        rest = need - count * space
        texts[id(item)] = item.label + ' ' * count + (' ' * int(round(rest / fine)) if 0 < fine < space else '') \
            + item.hotkey
    return texts


class BSM_OT_max_menu_unavailable(bpy.types.Operator):
    """No Blender equivalent for this 3ds Max command"""
    bl_idname = 'bsm.max_menu_unavailable'
    bl_label = 'Not Available'
    bl_options = {'INTERNAL'}
    reason: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return False  # Drawn greyed, aligned like real entries, with an explanatory tooltip.

    @classmethod
    def description(cls, context, properties):
        return properties.reason or cls.__doc__

    def execute(self, context):
        return {'CANCELLED'}


def _greyed(layout):
    row = layout.row()
    row.enabled = False
    return row


def _unavailable(layout, text, reason=''):
    if _op_rna(BSM_OT_max_menu_unavailable.bl_idname) is None:
        _greyed(layout).label(text=_tr(text), translate=False)
    else:
        layout.operator(BSM_OT_max_menu_unavailable.bl_idname, text=_tr(text), translate=False).reason = reason


def draw_items(layout, items, context=None):
    """Draw entries into a menu layout: separators, submenus, greyed fallbacks, hints and checkboxes."""
    context = context or bpy.context
    texts = _display_texts(context, items)
    for item in items:
        if isinstance(item, Sep):
            layout.separator()
            continue
        text = texts.get(id(item), item.label)
        if isinstance(item, Sub):
            if item.idname:
                (layout if item.items else _greyed(layout)).menu(item.idname, text=_tr(text), translate=False)
            else:
                _unavailable(layout, text)
        elif item.menu:
            if _menu_exists(item.menu):
                layout.menu(item.menu, text=_tr(text), translate=False)
            else:
                _unavailable(layout, text, 'Blender menu %s is not available' % item.menu)
        else:
            op = _resolve(item, context)
            if op is None:
                _unavailable(layout, text, 'Needs %s, which is not available' % item.op if item.op else '')
                continue
            icon = ('CHECKBOX_HLT' if _checked(item, context) else 'CHECKBOX_DEHLT') if item.check else 'NONE'
            props = layout.operator(op, text=_tr(text), icon=icon, translate=False)
            for key, value in item.props.items():
                setattr(props, key, value)


# ---------------------------------------------------------------- generated Menu classes
_PREFIX = 'BSM_MT_max_'


def _idname(path, used):
    slug = re.sub(r'[^0-9a-z]+', '_', '_'.join(path).lower()).strip('_')
    name = _PREFIX + slug
    if len(name) > 60 or name in used:
        digest = hashlib.md5('/'.join(path).encode('utf-8')).hexdigest()[:6]
        name = _PREFIX + slug[:60 - len(_PREFIX) - 7].rstrip('_') + '_' + digest
    return name


def _menu_class(idname, label, items):
    def draw(self, context):
        draw_items(self.layout, items, context)
    return type(idname, (bpy.types.Menu,), {'bl_idname': idname, 'bl_label': label, 'draw': draw,
                                            'bsm_items': items})


def _build(path, label, items, used, classes):
    idname = _idname(path, used)
    used.add(idname)
    classes.append(_menu_class(idname, label, items))
    for item in items:
        if isinstance(item, Sub):
            if item.idname:
                raise ValueError('Sub %r is used twice; give each place its own Sub' % item.label)
            item.idname = _build(path + (item.label,), item.label, item.items, used, classes)
    return idname


_LABEL_TITLES = {'PLUS': 'Views - General Viewport Label Menu', 'POV': 'Views - POV Viewport Label Menu',
                 'PRESET': 'Views - Shading Viewport Nitrous Label Menu', 'SHADING': 'Views - Viewport Preferences'}
_used, _classes = set(), []
MAIN_MENUS = [(_build((label,), label, items, _used, _classes), label) for label, items in MAIN]
LABEL_MENUS = {key: _build(('vp', key), _LABEL_TITLES[key], items, _used, _classes)
               for key, items in VIEWPORT_LABEL.items()}
CLASSES = (BSM_OT_max_menu_unavailable,) + tuple(_classes)
del _used, _classes
