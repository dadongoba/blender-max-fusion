# SPDX-License-Identifier: GPL-3.0-or-later
"""Slate and Compact material surfaces backed by real Blender shader data.

The visual structure follows Autodesk's documented material-editor workflows.
All graphics are independently drawn. A node on this canvas is a ShaderNode,
a wire is a NodeLink, fields edit RNA sockets, and sample slots hold persistent
Material pointers. The module does not implement proprietary shader classes.
"""
from .localization import tr as _tr

import math
import time
from types import SimpleNamespace

import bpy
import gpu
from bpy.props import (CollectionProperty, EnumProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy_extras.io_utils import ImportHelper
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d

from . import runtime, surfaces


BG = (.255, .255, .255, 1)
PANEL = (.285, .285, .285, 1)
GRAPH = (.19, .19, .19, 1)
EDGE = (.13, .13, .13, 1)
TEXT = (.82, .82, .82, 1)
DIM = (.61, .61, .61, 1)
GOLD = (.92, .75, .34, 1)
BLUE = (.29, .46, .63, 1)

# This is a creation catalogue, not an imitation material model. Each entry
# instantiates the listed Blender shader class in the current material tree.
CATALOGUE = (
    ('Materials', 'Physical Material', 'ShaderNodeBsdfPrincipled'),
    ('Materials', 'Diffuse', 'ShaderNodeBsdfDiffuse'),
    ('Materials', 'Glass', 'ShaderNodeBsdfGlass'),
    ('Materials', 'Emission', 'ShaderNodeEmission'),
    ('Materials', 'Mix Material', 'ShaderNodeMixShader'),
    ('Materials', 'Material Output', 'ShaderNodeOutputMaterial'),
    ('Maps', 'Bitmap', 'ShaderNodeTexImage'),
    ('Maps', 'Noise', 'ShaderNodeTexNoise'),
    ('Maps', 'Checker', 'ShaderNodeTexChecker'),
    ('Maps', 'Gradient', 'ShaderNodeTexGradient'),
    ('Maps', 'Voronoi', 'ShaderNodeTexVoronoi'),
    ('Maps', 'Color Correction', 'ShaderNodeHueSaturation'),
    ('Maps', 'Color Ramp', 'ShaderNodeValToRGB'),
    ('Maps', 'Bump', 'ShaderNodeBump'),
    ('Maps', 'Normal Map', 'ShaderNodeNormalMap'),
    ('Maps', 'Texture Coordinates', 'ShaderNodeTexCoord'),
    ('Maps', 'Mapping', 'ShaderNodeMapping'),
    ('Maps', 'Math', 'ShaderNodeMath'),
    ('Maps', 'RGB Color', 'ShaderNodeRGB'),
    ('Maps', 'Value', 'ShaderNodeValue'),
)
CATALOGUE_LABELS = {entry[2]: entry[1] for entry in CATALOGUE}
MAIN_INPUTS = {'Base Color', 'Metallic', 'Roughness', 'IOR', 'Alpha', 'Normal',
               'Coat Weight', 'Emission Color', 'Emission Strength'}
_states = {}
_drag = None
_enum_target = None
_menu_click = None  # a menu waiting for the release of the click that opens it
_textures = {}
_sphere_batches = {}
_smooth_shader = None
_pending_previews = {}
_preview_checks = 0


class _Canvas(surfaces.Canvas):
    """Clip hit targets with their drawing, including scrolled-off fields."""
    def __init__(self,context):
        super().__init__(context)
        self.clip_box=(0.,0.,self.w,self.h)
    def hit(self,x,y,w,h,action,label=''):
        cx,cy,cw,ch=self.clip_box
        left=max(x,cx); bottom=max(y,cy)
        right=min(x+w,cx+cw); top=min(y+h,cy+ch)
        if right>left and top>bottom:
            super().hit(left,bottom,right-left,top-bottom,action,label)


class BSM_MaterialSlot(bpy.types.PropertyGroup):
    material: PointerProperty(name='Material', type=bpy.types.Material)


def register_data():
    """Call after registering CLASSES; properties are normal saved scene data."""
    bpy.types.Scene.bsm_material_slots = CollectionProperty(type=BSM_MaterialSlot)
    bpy.types.Scene.bsm_material_slot_index = IntProperty(default=0, min=0, max=23)
    bpy.types.Scene.bsm_material_slot_grid = EnumProperty(
        items=(('6', '3 x 2', ''), ('15', '5 x 3', ''), ('24', '6 x 4', '')),
        default='6')


def unregister_data():
    clear()
    for name in ('bsm_material_slots', 'bsm_material_slot_index',
                 'bsm_material_slot_grid'):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)


def ensure_slots(scene):
    """Initialize empty pointer slots outside a draw callback."""
    if not hasattr(scene, 'bsm_material_slots'):
        return []
    slots = scene.bsm_material_slots
    while len(slots) < 24:
        slots.add()
    return slots


def _state(area):
    key = area.as_pointer()
    state = _states.get(key)
    if state is None:
        state = SimpleNamespace(
            kind='Slate', material=None, selected_node='', search='', zoom=1.,
            pan=[210., 370.], browser_scroll=0, param_scroll=0, param_max=0,
            browser=True, parameter=True, navigator=True, expanded=set(),
            browser_item='', view=(0, 0, 1, 1), socket_positions={},
            node_boxes={}, needs_fit=True, compact_page=0, preview_label='',
            name_scroll=0, material_pointer=0, browser_max=0, hidden_slots=set(), move_children=False)
        _states[key] = state
    return state


def prepare(context, kind='Slate'):
    """Call when opening a material surface (not from its GPU draw callback)."""
    slots = ensure_slots(context.scene)
    state = _state(context.area)
    state.kind = kind
    active = getattr(context.view_layer.objects.active, 'active_material', None)
    if active and slots and slots[context.scene.bsm_material_slot_index].material is None:
        slots[context.scene.bsm_material_slot_index].material = active
    if state.material is None:
        state.material = active or (slots[context.scene.bsm_material_slot_index].material if slots else None)
    if state.material:
        request_preview(state.material)
    return state


def _valid_material(value):
    try:
        return value if value and value.name in bpy.data.materials else None
    except ReferenceError:
        return None


def current_material(context, state=None):
    state = state or _state(context.area)
    slots = getattr(context.scene, 'bsm_material_slots', ())
    if state.kind == 'Compact' and slots:
        index = min(context.scene.bsm_material_slot_index, len(slots)-1)
        return _valid_material(slots[index].material)
    value = _valid_material(state.material)
    if value:
        return value
    if slots:
        value = _valid_material(slots[min(context.scene.bsm_material_slot_index,
                                          len(slots)-1)].material)
    return value or getattr(context.view_layer.objects.active, 'active_material', None)


def _set_material(context, material, state=None):
    state = state or _state(context.area)
    state.material = material
    state.selected_node = ''
    state.needs_fit = True
    state.param_scroll = 0
    slots = ensure_slots(context.scene)
    if slots:
        slots[context.scene.bsm_material_slot_index].material = material
    if material:
        request_preview(material)


def new_material(context, name=None, state=None):
    slots = ensure_slots(context.scene)
    index = getattr(context.scene, 'bsm_material_slot_index', 0)
    material = bpy.data.materials.new(name or f'{index+1:02d} - Default')
    material.use_nodes = True
    material.preview_render_type = 'SPHERE'
    shader = next((n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if shader:
        shader.location = (0, 0)
        shader.label = 'Physical Material'
    output = next((n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if output:
        output.location = (290, 0)
    _set_material(context, material, state)
    return material


def assign_material(context, material):
    """Assign to selected objects or selected mesh faces using native slots."""
    from .editors import _assign_material
    if not material:
        return 0
    objects = [obj for obj in context.selected_objects
               if obj.is_editable and getattr(obj, 'data', None) is not None
               and obj.data.is_editable and hasattr(obj.data, 'materials')]
    for obj in objects:
        _assign_material(obj, material)
    return len(objects)


def select_material_users(context, material):
    users = []
    for obj in context.view_layer.objects:
        uses = material is not None and any(s.material == material for s in obj.material_slots)
        if not obj.hide_select:
            obj.select_set(uses)
            if uses:
                users.append(obj)
    if users:
        context.view_layer.objects.active = users[0]
    return users


def node_inputs(node, expanded=False, hide_unused=False):
    result = [s for s in node.inputs if s.enabled and not s.hide]
    if hide_unused:  # Max's Hide Unused Nodeslots
        return [s for s in result if s.is_linked]
    if node.type == 'BSDF_PRINCIPLED' and not expanded:
        result = [s for s in result if s.name in MAIN_INPUTS or s.is_linked]
    return result


def node_outputs(node):
    return [s for s in node.outputs if s.enabled and not s.hide]


def add_node(material, node_type, location=(0., 0.)):
    if not material:
        raise ValueError('Choose a material first')
    material.use_nodes = True
    node = material.node_tree.nodes.new(node_type)
    node.location = location
    for other in material.node_tree.nodes:
        other.select = other == node
    material.node_tree.nodes.active = node
    if node_type == 'ShaderNodeBsdfPrincipled':
        node.label = 'Physical Material'
    request_preview(material)
    return node


def connect_sockets(material, first, second):
    """Connect opposite sockets on this tree; Blender performs type validation."""
    if not material or not material.node_tree:
        return None
    if first.is_output == second.is_output or first.node == second.node:
        return None
    output, input_socket = (first, second) if first.is_output else (second, first)
    if output.id_data != material.node_tree or input_socket.id_data != material.node_tree:
        return None
    link = material.node_tree.links.new(output, input_socket)
    request_preview(material)
    return link


def _undo(message):
    if not bpy.app.background:
        try:
            bpy.ops.ed.undo_push(message=message)
        except RuntimeError:
            pass


def _socket_color(socket):
    return {'RGBA': (.75, .70, .21, 1), 'VECTOR': (.35, .45, .76, 1),
            'SHADER': (.38, .65, .33, 1), 'BOOLEAN': (.65, .58, .67, 1),
            'INT': (.41, .64, .62, 1)}.get(socket.type, (.64, .64, .64, 1))


def _disc(c, x, y, radius, color):
    c.c.polygon([((x + math.cos(i*math.tau/16)*radius)*c.u,
                  (y + math.sin(i*math.tau/16)*radius)*c.u)
                 for i in range(16)], color)


def _border(c, x, y, w, h, color=EDGE, width=1):
    c.line([(x,y),(x+w,y),(x+w,y),(x+w,y+h),
            (x+w,y+h),(x,y+h),(x,y+h),(x,y)],color,width)


def _clip_text(c, value, x, y, width, size=9, color=TEXT, bold=False):
    # Approximate truncation is sufficient for a fixed Segoe UI font; clipping
    # still applies at the enclosing panel boundary.
    limit = max(1, int(width/(size*.51)))
    value = str(value)
    c.text(value if len(value)<=limit else value[:max(0,limit-1)]+'…',
           x,y,size,color,bold)


def _clip(c, box):
    """Draw only inside box (layout units) until _unclip; hit targets are clipped with it.
    A region draws into its own buffer, so the scissor box is relative to the region."""
    x,y,w,h=box
    previous=(gpu.state.scissor_get(),c.clip_box)
    c.clip_box=box
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(int(x*c.u),int(y*c.u),max(1,int(w*c.u)),max(1,int(h*c.u)))
    return previous


def _unclip(c,previous):
    scissor,box=previous
    c.clip_box=box
    if box==(0.,0.,c.w,c.h):  # back to the whole canvas
        gpu.state.scissor_test_set(False)
    else:
        gpu.state.scissor_set(*scissor)


def _wire(c, start, end, color, width=1.6):
    reach=max(40.,abs(end[0]-start[0])*.45)
    p0=start; p1=(start[0]+reach,start[1]); p2=(end[0]-reach,end[1]); p3=end
    points=[]
    for i in range(25):
        t=i/24.; q=1-t
        points.append((q*q*q*p0[0]+3*q*q*t*p1[0]+3*q*t*t*p2[0]+t*t*t*p3[0],
                       q*q*q*p0[1]+3*q*q*t*p1[1]+3*q*t*t*p2[1]+t*t*t*p3[1]))
    c.line([point for pair in zip(points,points[1:]) for point in pair],color,width)


def material_values(material):
    """Fallback sphere inputs; this intentionally does not evaluate map trees."""
    base = (.5,.5,.5,1.)
    roughness=.5; metallic=0.
    if material:
        base=tuple(material.diffuse_color)
        roughness=material.roughness; metallic=material.metallic
        if material.use_nodes and material.node_tree:
            shader=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if shader:
                base=tuple(shader.inputs['Base Color'].default_value)
                roughness=shader.inputs['Roughness'].default_value
                metallic=shader.inputs['Metallic'].default_value
    return base,roughness,metallic


def _srgb(value):
    value=max(0.,min(1.,value))
    return value*12.92 if value<=.0031308 else 1.055*value**(1/2.4)-.055


def _sphere(c,x,y,size,material):
    """Original analytic sphere used only while a renderer preview is pending."""
    global _smooth_shader
    values=material_values(material)
    key=(tuple(round(v,3) for v in values[0]),round(values[1],3),round(values[2],3),
         round(x*c.u,1),round(y*c.u,1),round(size*c.u,1))
    batch=_sphere_batches.get(key)
    if batch is None:
        base,rough,metal=values
        positions=[]; colors=[]; indices=[]
        cx=(x+size*.5)*c.u; cy=(y+size*.5)*c.u; radius=size*.44*c.u
        rings=12; segments=40
        light=(-.45,.58,.679); half=(-.247,.319,.915)
        for ring in range(rings+1):
            rr=ring/rings
            z=math.sqrt(max(0,1-rr*rr))
            for segment in range(segments):
                angle=segment*math.tau/segments
                nx=rr*math.cos(angle); ny=rr*math.sin(angle)
                diffuse=max(0,nx*light[0]+ny*light[1]+z*light[2])
                shine=max(0,nx*half[0]+ny*half[1]+z*half[2])**max(3,160*(1-rough)**2)
                color=tuple(_srgb(base[k]*(.08+.73*diffuse)*(1-.35*metal)
                            +shine*(.28*(1-metal)+base[k]*metal)*(.55+.45*(1-rough)))
                            for k in range(3))
                positions.append((cx+nx*radius,cy+ny*radius))
                colors.append((*color,1.))
        for ring in range(rings):
            for segment in range(segments):
                a=ring*segments+segment; b=ring*segments+(segment+1)%segments
                d=(ring+1)*segments+segment; e=(ring+1)*segments+(segment+1)%segments
                indices.extend(((a,b,e),(a,e,d)))
        if _smooth_shader is None: _smooth_shader=gpu.shader.from_builtin('SMOOTH_COLOR')
        batch=batch_for_shader(_smooth_shader,'TRIS',{'pos':positions,'color':colors},indices=indices)
        if len(_sphere_batches)>96: _sphere_batches.clear()
        _sphere_batches[key]=batch
    _smooth_shader.bind(); batch.draw(_smooth_shader)


def _fingerprint(material):
    parts=[material.name, tuple(round(v,4) for v in material.diffuse_color)]
    if material.node_tree:
        for node in material.node_tree.nodes:
            inputs=[]
            for socket in list(node.inputs)+list(node.outputs):
                value=getattr(socket,'default_value',None)
                if isinstance(value,(int,float,bool,str)): inputs.append(value)
                elif hasattr(value,'__len__'):
                    try: inputs.append(tuple(round(v,4) for v in value))
                    except TypeError: pass
            options=tuple((attr,getattr(node,attr)) for attr in
                          ('interpolation','projection','extension','noise_dimensions',
                           'noise_type','normalize','voronoi_dimensions','distance',
                           'feature','gradient_type','operation','use_clamp','vector_type',
                           'space','uv_map','distribution') if hasattr(node,attr))
            ramp=getattr(node,'color_ramp',None)
            ramp_values=(ramp.interpolation,tuple((round(e.position,4),tuple(round(v,4) for v in e.color)) for e in ramp.elements)) if ramp else None
            image=getattr(node,'image',None)
            image_values=(image.name,image.filepath,image.colorspace_settings.name) if image else None
            parts.append((node.name,node.bl_idname,node.mute,tuple(inputs),options,ramp_values,image_values))
        parts.append(tuple((link.from_node.name,link.from_socket.identifier,
                            link.to_node.name,link.to_socket.identifier)
                           for link in material.node_tree.links))
    return tuple(parts)


def request_preview(material):
    global _preview_checks
    if bpy.app.background or not _valid_material(material): return
    _pending_previews[material.as_pointer()]=material
    _preview_checks=30
    if not bpy.app.timers.is_registered(_preview_tick):
        bpy.app.timers.register(_preview_tick,first_interval=.2)


def _preview_tick():
    global _preview_checks
    if bpy.app.background: return None
    pending=list(_pending_previews.values())
    _pending_previews.clear()
    for material in pending:
        if _valid_material(material):
            try:
                material.asset_generate_preview()
            except (RuntimeError,AttributeError):
                # An analytic sample remains visible if the chosen renderer
                # does not supply previews. Shader data is never substituted.
                pass
    runtime.redraw()
    _preview_checks-=1
    return .25 if _preview_checks>0 or _pending_previews else None


_preview_background=[False]  # Show Background in Preview


def _checker(c,x,y,size,cells=8):
    step=size/cells
    for i in range(cells):
        for j in range(cells):
            c.rect(x+i*step,y+j*step,step,step,(.78,.78,.78,1) if (i+j)%2 else (.32,.32,.32,1))


def _preview(c,x,y,size,material):
    """Draw Blender's actual ID preview without adding image IDs to the scene."""
    if _preview_background[0]:
        _checker(c,x,y,size)
    if material:
        pointer=material.as_pointer()
        cached=_textures.get(pointer)
        now=time.monotonic()
        if cached is None or now-cached['checked']>.8:
            signature=_fingerprint(material)
            if cached is None or cached['signature']!=signature:
                request_preview(material)
            preview=material.preview
            pixels=None; dimensions=(0,0)
            if preview:
                dimensions=tuple(preview.image_size)
                if dimensions[0]>0 and dimensions[1]>0:
                    pixels=list(preview.image_pixels_float)
                    # Preview jobs allocate an opaque black buffer before
                    # rendering. Keep the explicitly approximate sphere until
                    # the renderer has actually written image content.
                    if not any(pixels[i]>.0001 for i in range(0,len(pixels),4)) and not any(pixels[i]>.0001 for i in range(1,len(pixels),4)) and not any(pixels[i]>.0001 for i in range(2,len(pixels),4)):
                        pixels=None
            stamp=(dimensions,tuple(round(pixels[i],4) for i in range(0,len(pixels),max(1,len(pixels)//23)))) if pixels else None
            if cached is None:
                cached={'texture':None,'stamp':None}
                _textures[pointer]=cached
            if pixels and stamp!=cached['stamp']:
                buffer=gpu.types.Buffer('FLOAT',len(pixels),pixels)
                cached['texture']=gpu.types.GPUTexture(dimensions,format='RGBA16F',data=buffer)
                cached['stamp']=stamp
            cached.update(signature=signature,checked=now)
        if cached['texture']:
            draw_texture_2d(cached['texture'],(x*c.u,y*c.u),size*c.u,size*c.u)
            return True
    _sphere(c,x,y,size,material)
    return False


def _menu_bar(c,kind):
    y=c.h-20
    c.rect(0,y,c.w,20,(.22,.22,.22,1))
    menus=(('Modes','BSM_MT_material_modes'),('Material','BSM_MT_material_actions'),
           ('Edit','BSM_MT_material_edit'),('Select','BSM_MT_material_select'),
           ('View','BSM_MT_material_view'),('Tools','BSM_MT_slate_tools'))
    x=7
    for label,name in menus:
        width=len(label)*5.5+17
        c.button(x,y+1,width,18,label,surfaces.menu(name),flat=True)
        x+=width
    c.text(('Slate' if kind=='Slate' else 'Compact')+' Material Editor',
           max(x+15,c.w-190),y+6,9,DIM)


# Slate toolbar of Max 2027: icon, tooltip, action; None is a separator.
SLATE_TOOLBAR=(('sme_select','Select Tool','SELECT'),('sme_pick','Pick Material from Object','GET'),
               ('sme_put','Put Material to Scene','PUT'),('sme_assign','Assign Material to Selection','ASSIGN'),None,
               ('sme_delete','Delete Selected','DELETE'),('sme_move_children','Move Children','MOVE_CHILDREN'),
               ('sme_hide_unused','Hide Unused Nodeslots','HIDE_UNUSED'),None,
               ('sme_shaded','Show Shaded Material in Viewport','VIEWPORT'),
               ('sme_background','Show Background in Preview','BACKGROUND'),
               ('sme_material_id','Material ID Channel','MATERIAL_ID'),None,
               ('sme_layout_all','Lay Out All','LAYOUT'),('sme_layout_children','Lay Out Children','LAYOUT_CHILDREN'),None,
               ('sme_browser','Material/Map Browser','BROWSER'),('sme_parameters','Parameter Editor','PARAMETER'),
               ('sme_select_by_material','Select by Material','SELECT_USERS'))
FLYOUTS={'VIEWPORT','MATERIAL_ID','LAYOUT'}


def _shown_in_viewport(material):
    from .operators import viewport_override
    try:
        area=viewport_override(bpy.context)['area']
    except RuntimeError:
        return False
    return material is not None and area.spaces.active.shading.type in {'MATERIAL','RENDERED'}


def _toolbar_state(context,state,material,action):
    """(enabled, pressed) of a toolbar button, as Max greys and highlights them."""
    node=material.node_tree.nodes.get(state.selected_node) if material and material.node_tree else None
    selected=bool(context.selected_objects)
    return {'SELECT':(True,True),
            'GET':(context.view_layer.objects.active is not None,False),
            'PUT':(False,False),  # Blender materials are live: there is no scene copy to update
            'ASSIGN':(material is not None and selected,False),
            'DELETE':(material is not None and any(n.select for n in material.node_tree.nodes) if material and material.node_tree else False,False),
            'MOVE_CHILDREN':(True,state.move_children),
            'HIDE_UNUSED':(node is not None,node is not None and node.name in state.hidden_slots),
            'VIEWPORT':(material is not None,_shown_in_viewport(material)),
            'BACKGROUND':(True,_preview_background[0]),
            'MATERIAL_ID':(material is not None,False),
            'LAYOUT':(material is not None,False),
            'LAYOUT_CHILDREN':(node is not None,False),
            'BROWSER':(True,state.browser),
            'PARAMETER':(True,state.parameter),
            'SELECT_USERS':(material is not None,False)}.get(action,(True,False))


def _toolbar(c,state,material):
    y=c.h-50
    c.rect(0,y,c.w,30,BG)
    x=5
    for item in SLATE_TOOLBAR if state.kind=='Slate' else ():
        if item is None:  # Max separates the groups with a gap, not a line
            x+=7
            continue
        icon,tip,action=item
        enabled,pressed=_toolbar_state(c.context,state,material,action)
        c.button(x,y+3,24,24,icon=icon,action=('MAT',action),flat=True,enabled=enabled,selected=pressed,tip=tip)
        if action=='MATERIAL_ID':
            number=str(material.pass_index if material else 0)
            c.text(number,x+12-c.text_width(number,11,True)/2,y+9,11,(.15,.15,.15,1) if enabled else (.45,.45,.45,1),bold=True)
        if action in FLYOUTS:
            c.c.polygon([(v*c.u,(z+c.oy)*c.u) for v,z in ((x+21,y+4),(x+24,y+4),(x+24,y+7))],TEXT)
        x+=26
    if state.kind!='Slate':
        for i,(icon,tip,action) in enumerate((('sme_pick','Get Material','GET'),('sme_assign','Assign Material to Selection','ASSIGN'),
                                             ('sme_select_by_material','Select by Material','SELECT_USERS'))):
            enabled,pressed=_toolbar_state(c.context,state,material,action)
            c.button(x,y+3,24,24,icon=icon,action=('MAT',action),flat=True,enabled=enabled,tip=tip)
            x+=26
    x=max(x+16,min(390,c.w-190))
    if c.w>x+170: c.dropdown(x,y+7,160,material.name if material else 'View 1',surfaces.menu('BSM_MT_material_scene'))
    c.line([(0,y),(c.w,y)],EDGE)


def _browser(c,state):
    if not state.browser: return 0.
    width=min(220.,max(155.,c.w*.19))
    top=c.h-50; bottom=22
    c.rect(0,bottom,width,top-bottom,PANEL)
    c.rect(0,top-22,width,22,(.31,.31,.31,1))
    c.text('Material/Map Browser',7,top-15,10)
    c.button(width-20,top-20,18,18,'×',('MAT','BROWSER'),flat=True)
    c.field(7,top-45,width-14,state,'search')
    if not state.search: c.text('Search by Name...',11,top-41,9,DIM)
    previous=_clip(c,(0,bottom,width,top-bottom-49))
    y=top-66+state.browser_scroll*19
    rows=[]
    query=state.search.casefold()
    for group in ('Materials','Maps'):
        entries=[(label,node_type) for cat,label,node_type in CATALOGUE
                 if cat==group and (not query or query in label.casefold())]
        if entries:
            c.rect(3,y-5,width-6,18,(.33,.33,.33,1)); c.text('−  '+group,9,y,9,bold=True)
            y-=22
        for label,node_type in entries:
            selected=state.browser_item==node_type
            c.button(16,y-4,width-21,18,'',('MAT','BROWSER_NODE',node_type),flat=True,selected=selected)
            c.icon('material' if group=='Materials' else 'texture',19,y-2,14)
            _clip_text(c,label,38,y,width-43,9)
            rows.append((y,label))
            y-=19
    materials=[m for m in bpy.data.materials if not query or query in m.name.casefold()]
    if materials:
        c.rect(3,y-5,width-6,18,(.33,.33,.33,1)); c.text('−  Scene Materials',9,y,9,bold=True); y-=22
    material=current_material(c.context,state)
    for mat in materials:
        c.button(16,y-4,width-21,18,'',('MAT','MATERIAL',mat),flat=True,selected=mat==material)
        c.icon('material',19,y-2,14); _clip_text(c,mat.name,38,y,width-43,9)
        rows.append((y,mat.name)); y-=19
    state.browser_max=max(0,int((len(rows)*19+66-(top-bottom))/19)+7)
    _unclip(c,previous)
    c.line([(width,bottom),(width,top)],EDGE)
    return width


def _node_box(node,state):
    x0,y0,_,_=state.view
    zoom=state.zoom
    x=x0+state.pan[0]+node.location.x*zoom
    y=y0+state.pan[1]+node.location.y*zoom
    width=205*zoom
    sockets=node_inputs(node,node.name in state.expanded,node.name in state.hidden_slots)
    outputs=node_outputs(node)
    header=25*zoom; row=18*zoom
    preview_height=63*zoom if node.type in {'BSDF_PRINCIPLED','BSDF_DIFFUSE','BSDF_GLASS','EMISSION'} else 0
    height=header+preview_height+max(len(sockets),len(outputs),1)*row+12*zoom
    return x,y-height,width,height,sockets,outputs,preview_height


def _graph(c,state,material,left,right):
    x=left; y=22.; width=max(1,c.w-left-right); height=c.h-94
    state.view=(x,y,width,height)
    c.rect(x,y,width,height,GRAPH)
    top=y+height
    c.rect(x,top,width,22,(.27,.27,.27,1))
    c.button(x+3,top+2,min(145,width-6),19,'View 1',('MAT','FRAME'),selected=True,flat=True)
    if material and material.node_tree and state.needs_fit:
        frame_nodes(state,material)
        state.needs_fit=False
    state.socket_positions={}; state.node_boxes={}
    previous=_clip(c,state.view)
    step=max(12,32*state.zoom)
    ox=x+(state.pan[0]%step); oy=y+(state.pan[1]%step)
    for i in range(int(width/step)+2):
        xx=ox+i*step; c.line([(xx,y),(xx,top)],(.225,.225,.225,1))
    for i in range(int(height/step)+2):
        yy=oy+i*step; c.line([(x,yy),(x+width,yy)],(.225,.225,.225,1))
    if not material or not material.node_tree:
        c.text('Double-click a material in the browser to create it.',x+22,y+height*.55,11,DIM)
        c.button(x+22,y+height*.55-36,136,23,'Create Physical Material',('MAT','NEW'))
        _unclip(c,previous)
        return
    nodes=list(material.node_tree.nodes)
    for node in nodes:
        box=_node_box(node,state)
        state.node_boxes[node.name]=box[:4]
        nx,ny,nw,nh,inputs,outputs,ph=box
        for j,socket in enumerate(inputs):
            sy=ny+nh-(25+9+j*18)*state.zoom-ph
            state.socket_positions[(node.name,False,list(node.inputs).index(socket))]=(nx,sy)
        for j,socket in enumerate(outputs):
            sy=ny+nh-(25+9+j*18)*state.zoom-ph
            state.socket_positions[(node.name,True,list(node.outputs).index(socket))]=(nx+nw,sy)
    for link in material.node_tree.links:
        first=state.socket_positions.get((link.from_node.name,True,list(link.from_node.outputs).index(link.from_socket)))
        second=state.socket_positions.get((link.to_node.name,False,list(link.to_node.inputs).index(link.to_socket)))
        if first and second: _wire(c,first,second,_socket_color(link.from_socket))
    for node in sorted(nodes,key=lambda n:n.select):
        nx,ny,nw,nh=state.node_boxes[node.name]
        if nx> x+width or nx+nw<x or ny>top or ny+nh<y: continue
        zoom=state.zoom
        header=(.27,.40,.28,1) if node.type.startswith(('BSDF','EMISSION')) else (.47,.27,.27,1) if node.bl_idname.startswith('ShaderNodeTex') else (.27,.32,.42,1)
        c.rect(nx,ny,nw,nh,(.32,.32,.32,1))
        c.rect(nx,ny+nh-25*zoom,nw,25*zoom,header)
        _border(c,nx,ny,nw,nh,GOLD if node.select else (.09,.09,.09,1),1.6 if node.select else 1)
        label=node.label or CATALOGUE_LABELS.get(node.bl_idname,node.name)
        _clip_text(c,label,nx+8*zoom,ny+nh-17*zoom,nw-16*zoom,9*zoom,TEXT,True)
        c.hit(nx,ny,nw,nh,('MAT','NODE',material,node),label)
        ph=63*zoom if node.type in {'BSDF_PRINCIPLED','BSDF_DIFFUSE','BSDF_GLASS','EMISSION'} else 0
        if ph:
            _preview(c,nx+nw*.5-28*zoom,ny+nh-25*zoom-ph+3*zoom,56*zoom,material)
        for is_output,sockets in ((False,node_inputs(node,node.name in state.expanded,node.name in state.hidden_slots)),(True,node_outputs(node))):
            for socket in sockets:
                index=list(node.outputs if is_output else node.inputs).index(socket)
                sx,sy=state.socket_positions[(node.name,is_output,index)]
                _disc(c,sx,sy,4*zoom,EDGE); _disc(c,sx,sy,2.7*zoom,_socket_color(socket))
                label=socket.name
                if is_output:
                    # Keep outputs on their own half so long names do not run
                    # through input labels.
                    _clip_text(c,label,nx+nw*.59,sy-3.4*zoom,nw*.37,8*zoom,DIM)
                else:
                    _clip_text(c,label,nx+8*zoom,sy-3.4*zoom,nw*.54,8*zoom,TEXT)
                c.hit(sx-7,sy-7,14,14,('MAT','SOCKET',material,node,is_output,index),socket.name)
    if _drag and _drag.get('kind')=='LINK' and _drag['area']==c.key:
        first=_drag['first_position']; last=_drag['last']
        _wire(c,first,last,GOLD,2.)
    _unclip(c,previous)


def _upstream(material,nodes):
    """The nodes wired, directly or not, into these nodes: Max's children."""
    found=set(nodes); frontier=set(nodes)
    while frontier:
        frontier={l.from_node for l in material.node_tree.links if l.to_node in frontier}-found
        found|=frontier
    return found


def _moving_nodes(state,material):
    selected={n for n in material.node_tree.nodes if n.select}
    return _upstream(material,selected) if state.move_children else selected


def frame_nodes(state,material,selected=False):
    nodes=list(material.node_tree.nodes) if material and material.node_tree else []
    if selected and any(n.select for n in nodes):
        nodes=[n for n in nodes if n.select]
    if not nodes: return
    bounds=[]
    for node in nodes:
        inputs=node_inputs(node,node.name in state.expanded,node.name in state.hidden_slots)
        rows=max(len(inputs),len(node_outputs(node)),1)
        height=37+rows*18+(63 if node.type in {'BSDF_PRINCIPLED','BSDF_DIFFUSE','BSDF_GLASS','EMISSION'} else 0)
        bounds.append((node.location.x,node.location.y-height,node.location.x+205,node.location.y))
    left=min(b[0] for b in bounds); bottom=min(b[1] for b in bounds)
    right=max(b[2] for b in bounds); top=max(b[3] for b in bounds)
    _,_,width,height=state.view
    zoom=min(1.2,max(.25,min((width-90)/max(1,right-left),(height-75)/max(1,top-bottom))))
    state.zoom=zoom
    state.pan=[(width-(right-left)*zoom)*.5-left*zoom,
               (height-(top-bottom)*zoom)*.5-bottom*zoom]


def _rollout(c,state,x,y,width,title,height,key):
    closed=key in state.expanded
    c.rect(x,y-21,width,21,(.32,.32,.32,1))
    c.text(('▸ ' if closed else '▾ ')+title,x+7,y-14,9,bold=True)
    c.hit(x,y-21,width,21,('MAT','ROLLOUT',key),title)
    if not closed: c.rect(x,y-21-height,width,height,(.285,.285,.285,1))
    return y-21,not closed


def _parameter_socket(c,state,material,node,socket,x,y,width):
    _clip_text(c,socket.name,x+8,y+4,width*.47-11,9)
    index=list(node.inputs).index(socket)
    if socket.is_linked:
        c.text('Mapped',x+width*.48,y+4,9,DIM)
        c.button(x+width-26,y,18,17,'M',('MAT','UNLINK',material,node,False,index),selected=True)
        return 22
    if not hasattr(socket,'default_value'):
        return 22
    value=socket.default_value
    if socket.type=='RGBA':
        color=tuple(value)
        c.rect(x+width*.49,y,width*.39-4,16,tuple(_srgb(v) for v in color[:3])+(1.,))
        _border(c,x+width*.49,y,width*.39-4,16)
        c.hit(x+width*.49,y,width*.39-4,16,('MAT','COLOR',material,node,False,index),socket.name)
    elif isinstance(value,(float,int)):
        c.field(x+width*.49,y,width*.39-4,socket,'default_value')
    elif isinstance(value,bool):
        c.button(x+width*.49,y,18,16,'✓' if value else '',surfaces.toggle(socket,'default_value'))
    elif hasattr(value,'__len__'):
        count=min(3,len(value)); fw=(width*.45-8)/count
        for i in range(count): c.field(x+width*.49+i*(fw+2),y,fw,socket,'default_value',i)
    c.button(x+width-26,y,18,17,'',('MAT','MAP',material,node,index),flat=False)
    return 22


def _parameters(c,state,material,x,bottom,width,top,compact=False):
    c.rect(x,bottom,width,top-bottom,PANEL)
    previous=_clip(c,(x,bottom,width,top-bottom))
    y=top+state.param_scroll
    c.rect(x,y-22,width,22,(.31,.31,.31,1))
    c.text('Material Parameter Editor' if not compact else 'Material Parameters',x+7,y-15,10)
    y-=47
    if material:
        c.field(x+7,y,width-14,material,'name')
    else:
        c.text('No material selected',x+10,y+4,10,DIM)
        c.button(x+10,y-31,width-20,23,'Create Material',('MAT','NEW'))
        _unclip(c,previous)
        state.param_max=0
        return
    y-=23
    node=None
    if material.node_tree:
        node=material.node_tree.nodes.get(state.selected_node)
        if node is None: node=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if node is None: node=material.node_tree.nodes.active
    typename=CATALOGUE_LABELS.get(node.bl_idname,node.bl_label) if node else 'Material'
    c.dropdown(x+7,y,width-14,typename,surfaces.menu('BSM_MT_material_node_add'))
    y-=9
    if not material.use_nodes or not material.node_tree:
        y,opened=_rollout(c,state,x+4,y,width-8,'Shader',55,'shader')
        if opened:
            c.button(x+12,y-33,width-24,22,'Enable Physical Material',('MAT','ENABLE_NODES'))
            y-=55
    elif node:
        y,opened=_rollout(c,state,x+4,y,width-8,'Basic Parameters',52,'basic')
        if opened:
            y-=24
            c.text('Name',x+12,y+4,9); c.field(x+width*.30,y,width*.66,node,'label')
            y-=23
            c.button(x+12,y,width*.43,18,'Mute',surfaces.toggle(node,'mute'),selected=node.mute)
            c.button(x+width*.51,y,width*.44,18,'Select By Material',('MAT','SELECT_USERS'))
            y-=12
        sockets=[s for s in node.inputs if s.enabled and not s.hide and (hasattr(s,'default_value') or s.is_linked)]
        if node.type=='BSDF_PRINCIPLED':
            groups=[('Base Color and Reflections',[s for s in sockets if s.name in {'Base Color','Metallic','Roughness','IOR','Alpha','Normal','Diffuse Roughness'}]),
                    ('Specular',[s for s in sockets if s.name.startswith(('Specular','Anisotropic')) or s.name=='Tangent']),
                    ('Coating',[s for s in sockets if s.name.startswith('Coat')]),
                    ('Transparency',[s for s in sockets if s.name.startswith('Transmission')]),
                    ('Sub-Surface Scattering',[s for s in sockets if s.name.startswith('Subsurface')]),
                    ('Emission',[s for s in sockets if s.name.startswith('Emission')]),
                    ('Sheen',[s for s in sockets if s.name.startswith('Sheen')])]
            included={s.identifier for _,entries in groups for s in entries}
            remaining=[s for s in sockets if s.identifier not in included]
            if remaining: groups.append(('Additional Parameters',remaining))
        else: groups=[('Material Parameters' if node.type.startswith('BSDF') else 'Map Parameters',sockets)]
        for title,group_sockets in groups:
            if not group_sockets and node.type=='BSDF_PRINCIPLED': continue
            height=max(28,len(group_sockets)*22+12)
            y-=5
            y,opened=_rollout(c,state,x+4,y,width-8,title,height,'inputs:'+title)
            if opened:
                for socket in group_sockets:
                    y-=22
                    _parameter_socket(c,state,material,node,socket,x+4,y,width-8)
                if not group_sockets:
                    y-=22; c.text('No numeric inputs',x+14,y+4,9,DIM)
                y-=12
        if node.type in {'RGB','VALUE'}:
            y-=5; y,opened=_rollout(c,state,x+4,y,width-8,'Output',40,'constant')
            if opened and node.outputs:
                socket=node.outputs[0]
                y-=24
                if socket.type=='RGBA':
                    c.rect(x+15,y,width-30,18,tuple(_srgb(v) for v in socket.default_value[:3])+(1.,))
                    c.hit(x+15,y,width-30,18,('MAT','COLOR',material,node,True,0),'Color')
                else: c.field(x+15,y,width-30,socket,'default_value')
                y-=17
        attrs={
            'TEX_IMAGE':('interpolation','projection','extension'),
            'TEX_NOISE':('noise_dimensions','noise_type','normalize'),
            'TEX_VORONOI':('voronoi_dimensions','distance','feature','normalize'),
            'TEX_GRADIENT':('gradient_type',),
            'MATH':('operation','use_clamp'),
            'MAPPING':('vector_type',),
            'NORMAL_MAP':('space','uv_map'),
            'BSDF_GLASS':('distribution',),
        }.get(node.type,())
        attrs=[attr for attr in attrs if hasattr(node,attr)]
        if attrs or node.type=='TEX_IMAGE':
            y-=5; y,opened=_rollout(c,state,x+4,y,width-8,'Options',len(attrs)*24+65,'options')
            if opened:
                if node.type=='TEX_IMAGE':
                    y-=24
                    c.button(x+12,y,width-24,21,'Open Bitmap...',('MAT','IMAGE',material,node))
                    y-=20; _clip_text(c,getattr(node.image,'name','No image selected'),x+12,y+4,width-24,9,DIM)
                for attr in attrs:
                    y-=24
                    c.text(attr.replace('_',' ').title(),x+12,y+4,9)
                    value=getattr(node,attr)
                    prop=node.bl_rna.properties.get(attr)
                    if prop.type=='ENUM': c.dropdown(x+width*.47,y,width*.49,str(value).replace('_',' ').title(),('MAT','ENUM',node,attr))
                    elif isinstance(value,bool): c.button(x+width*.70,y,18,17,'✓' if value else '',surfaces.toggle(node,attr))
                    else: c.field(x+width*.47,y,width*.49,node,attr)
                y-=14
        if node.type=='VALTORGB':
            y-=5
            elements=list(node.color_ramp.elements)
            y,opened=_rollout(c,state,x+4,y,width-8,'Gradient',len(elements)*25+55,'ramp')
            if opened:
                for i,element in enumerate(elements):
                    y-=25; c.field(x+13,y,width*.36,element,'position')
                    c.rect(x+width*.46,y,width*.35,17,tuple(_srgb(v) for v in element.color[:3])+(1.,))
                    c.hit(x+width*.46,y,width*.35,17,('MAT','RAMP_COLOR',material,node,i),'Ramp Color')
                    c.button(x+width-30,y,17,17,'−',('MAT','RAMP_REMOVE',material,node,i),enabled=len(elements)>2)
                y-=27
                c.button(x+13,y,width-26,20,'Add Stop',('MAT','RAMP_ADD',material,node))
                y-=12
        y-=5
        y,opened=_rollout(c,state,x+4,y,width-8,'Maps',max(33,len([s for s in node.inputs if s.is_linked])*22+10),'maps')
        if opened:
            linked=[s for s in node.inputs if s.is_linked]
            if not linked:
                y-=22; c.text('No maps assigned',x+13,y+4,9,DIM)
            for socket in linked:
                y-=22
                c.text(socket.name,x+13,y+4,9)
                c.button(x+width-65,y,52,17,'Remove',('MAT','UNLINK',material,node,False,list(node.inputs).index(socket)))
            y-=12
    content=top+state.param_scroll-y
    state.param_max=max(0,int(content-(top-bottom)+15))
    _unclip(c,previous)


def _navigator(c,state,material,x,y,width,height):
    c.rect(x,y,width,height,(.16,.16,.16,1))
    c.rect(x,y+height-19,width,19,(.30,.30,.30,1)); c.text('Navigator',x+6,y+height-13,9)
    if material and material.node_tree and material.node_tree.nodes:
        nodes=list(material.node_tree.nodes)
        minx=min(n.location.x for n in nodes); maxx=max(n.location.x+205 for n in nodes)
        miny=min(n.location.y-100 for n in nodes); maxy=max(n.location.y for n in nodes)
        zoom=min((width-20)/max(1,maxx-minx),(height-39)/max(1,maxy-miny))
        for node in nodes:
            nx=x+10+(node.location.x-minx)*zoom; ny=y+9+(node.location.y-miny)*zoom
            c.rect(nx,ny-28*zoom,205*zoom,max(4,28*zoom),BLUE if node.select else (.40,.40,.40,1))
        c.hit(x,y,width,height,('MAT','FRAME'),'Frame All Nodes')
    _border(c,x,y,width,height,EDGE)


def _compact(c,state,material):
    # A compact, dense six-by-four slot array is the documented 24-slot mode.
    # Wider windows leave room for the browser rather than stretching spheres.
    panel_width=min(560.,max(360.,c.w*.48))
    content_x=max(0.,(c.w-panel_width)*.5)
    if c.w>1050:
        browser_width=_browser(c,state)
        content_x=browser_width+max(15,(c.w-browser_width-panel_width)*.5)
    c.rect(content_x,22,panel_width,c.h-72,PANEL)
    count=int(getattr(c.context.scene,'bsm_material_slot_grid','24'))
    cols,rows={6:(3,2),15:(5,3),24:(6,4)}[count]
    samples_width=panel_width-34
    size=min(samples_width/cols,90.)
    grid_width=cols*size
    gx=content_x+10; top=c.h-60
    slots=getattr(c.context.scene,'bsm_material_slots',())
    active=getattr(c.context.scene,'bsm_material_slot_index',0)
    if count<24: state.compact_page=min(24-count,max(0,active//count*count))
    else: state.compact_page=0
    any_fallback=False
    for visible in range(count):
        index=visible+state.compact_page
        sx=gx+(visible%cols)*size; sy=top-(visible//cols+1)*size
        mat=slots[index].material if index<len(slots) else None
        c.rect(sx+1,sy+1,size-2,size-2,(.12,.12,.12,1))
        actual=_preview(c,sx+2,sy+2,size-4,mat)
        any_fallback|=bool(mat and not actual)
        if mat and any(any(s.material==mat for s in obj.material_slots) for obj in c.context.scene.objects):
            c.line([(sx+3,sy+size-10),(sx+3,sy+size-3),(sx+3,sy+size-3),(sx+10,sy+size-3),
                    (sx+size-10,sy+3),(sx+size-3,sy+3),(sx+size-3,sy+3),(sx+size-3,sy+10)],(.88,.88,.88,1),1.3)
        if index==active: _border(c,sx+1,sy+1,size-2,size-2,GOLD,1.7)
        c.hit(sx,sy,size,size,('MAT','SLOT',index),mat.name if mat else f'{index+1:02d} - Default')
    side_x=gx+grid_width+4
    for i,(icon,action,tip) in enumerate((('material_library','GET','Get Material'),('material','NEW','New Material'),
                                          ('sme_shaded','VIEWPORT','Show Shaded Material in Viewport'),
                                          ('sme_background','BACKGROUND','Background'),('quad','GRID','Sample Slots'),
                                          ('sme_parameters','PARAMETER','Options'))):
        c.button(side_x,top-25-i*26,24,24,icon=icon,action=('MAT',action),flat=True,tip=tip,
                 selected=action=='BACKGROUND' and _preview_background[0])
    y=top-rows*size-27
    for i,(icon,action,tip) in enumerate((('material_library','GET','Get Material'),('sme_assign','ASSIGN','Assign Material to Selection'),
                                          ('clone','DUPLICATE','Make Material Copy'),('sme_select_by_material','SELECT_USERS','Select by Material'),
                                          ('clear','CLEAR_SLOT','Reset Map/Mtl to Default Settings'),('frame','PREVIEW','Make Preview'),
                                          ('sme_shaded','VIEWPORT','Show Shaded Material in Viewport'))):
        enabled=material is not None or action=='GET'
        if action=='ASSIGN': enabled=material is not None and bool(c.context.selected_objects)
        c.button(gx+i*27,y,24,23,icon=icon,action=('MAT',action),flat=True,enabled=enabled,tip=tip)
    c.text(f'{active+1:02d}',gx+215,y+7,9,DIM)
    if material and any_fallback:
        c.text('Preview approximation',gx+250,y+7,9,DIM)
    param_top=y-7
    _parameters(c,state,material,content_x+4,23,panel_width-8,param_top,True)
    if c.w>content_x+panel_width+170:
        px=content_x+panel_width+24
        c.text('Active Sample',px,c.h-85,10)
        size=min(230,c.w-px-25)
        actual=_preview(c,px,c.h-100-size,size,material)
        if material:
            _clip_text(c,material.name,px,c.h-123-size,size,10)
            if not actual: c.text('Preview approximation',px,c.h-143-size,9,DIM)


def draw(context,kind='Slate'):
    """Render a complete editor into its Image Editor WINDOW region."""
    state=_state(context.area); state.kind=kind
    c=_Canvas(context)
    material=current_material(context,state)
    c.rect(0,0,c.w,c.h,BG)
    _menu_bar(c,kind)
    _toolbar(c,state,material)
    if kind=='Compact':
        _compact(c,state,material)
    else:
        left=_browser(c,state)
        right=min(330.,max(235.,c.w*.25)) if state.parameter else 0.
        _graph(c,state,material,left,right)
        if state.parameter:
            nav_height=min(150.,c.h*.22) if state.navigator else 0.
            top=c.h-50
            if nav_height:
                _navigator(c,state,material,c.w-right,top-nav_height,right,nav_height)
                top-=nav_height
            _parameters(c,state,material,c.w-right,22,right,top)
            c.line([(c.w-right,22),(c.w-right,c.h-50)],EDGE)
    c.rect(0,0,c.w,22,(.22,.22,.22,1))
    status=f'{len(material.node_tree.nodes)} Nodes, {len(material.node_tree.links)} Wires' if material and material.node_tree and kind=='Slate' else '24 Sample Slots'
    c.text(status,8,7,9,DIM)
    if kind=='Slate':
        c.text(f'{round(state.zoom*100)}%',c.w-145,7,9,DIM)
        for i,(icon,action) in enumerate((('zoom','ZOOM_IN'),('pan','PAN'),('frame','FRAME'))):
            c.button(c.w-99+i*31,1,29,20,icon=icon,action=('MAT',action),flat=True)
    c.button(max(160,c.w*.45),1,70,20,'Slate' if kind=='Compact' else 'Compact',
             surfaces.op('bsm.editor',kind='MATERIAL' if kind=='Compact' else 'COMPACT'),flat=True)


def _inside(box,x,y):
    bx,by,bw,bh=box
    return bx<=x<bx+bw and by<=y<by+bh


def _node_select(material,node,extend=False):
    if not material or not material.node_tree: return
    for other in material.node_tree.nodes:
        if other==node: other.select=not other.select if extend else True
        elif not extend: other.select=False
    material.node_tree.nodes.active=node


def _node_at(state,material,x,y):
    if not material or not material.node_tree: return None
    for node in sorted(material.node_tree.nodes,key=lambda n:not n.select):
        box=state.node_boxes.get(node.name)
        if box and _inside(box,x,y): return node
    return None


def _socket_from_action(action):
    _,_,material,node,is_output,index=action
    try: return (node.outputs if is_output else node.inputs)[index]
    except (ReferenceError,IndexError): return None


def active_event(context,event):
    """Route an existing gesture across area boundaries; None means idle."""
    global _drag
    if not _drag: return None
    drag=_drag
    if context.window.as_pointer()!=drag['window']: return None
    area=next((a for a in context.window.screen.areas if a.as_pointer()==drag['area']),None)
    if area is None:
        _drag=None; return {'RUNNING_MODAL'}
    region=next((r for r in area.regions if r.type=='WINDOW'),None)
    if region is None:
        _drag=None; return {'RUNNING_MODAL'}
    u=surfaces.scale(); x=(event.mouse_x-region.x)/u; y=(event.mouse_y-region.y)/u
    state=_state(area)
    if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':
        if drag['kind']=='NODES':
            for node,position in drag['positions']:
                try: node.location=position
                except ReferenceError: pass
        elif drag['kind']=='PAN': state.pan=list(drag['pan'])
        _drag=None; runtime.redraw(); return {'RUNNING_MODAL'}
    if event.type=='MOUSEMOVE':
        dx=x-drag['start'][0]; dy=y-drag['start'][1]
        drag['last']=(x,y)
        if drag['kind']=='NODES':
            for node,position in drag['positions']:
                try: node.location=(position[0]+dx/state.zoom,position[1]+dy/state.zoom)
                except ReferenceError: pass
        elif drag['kind']=='PAN': state.pan=[drag['pan'][0]+dx,drag['pan'][1]+dy]
        runtime.redraw(); return {'RUNNING_MODAL'}
    release=event.type==('MIDDLEMOUSE' if drag['kind']=='PAN' else 'LEFTMOUSE') and event.value=='RELEASE'
    if release:
        with context.temp_override(area=area,region=region):
            if drag['kind']=='LINK' and _inside(state.view,x,y):
                hit=surfaces.lookup(area,x,y)
                if hit and hit[4][:2]==('MAT','SOCKET'):
                    second=_socket_from_action(hit[4])
                    if second and connect_sockets(drag['material'],drag['socket'],second): _undo('Connect Material Map')
            elif drag['kind']=='BROWSER' and _inside(state.view,x,y):
                distance=math.hypot(x-drag['start'][0],y-drag['start'][1])
                if distance>5:
                    material=current_material(context,state) or new_material(context,state=state)
                    vx,vy,_,_=state.view
                    node=add_node(material,drag['node_type'],((x-vx-state.pan[0])/state.zoom,(y-vy-state.pan[1])/state.zoom))
                    state.selected_node=node.name; _undo('Create Material Map')
            elif drag['kind']=='NODES': _undo('Move Material Nodes')
        _drag=None; runtime.redraw(); return {'RUNNING_MODAL'}
    return {'RUNNING_MODAL'}


def handle_event(context,event,area,region,x,y):
    """Process material-canvas gestures using logical (scaled, y-up) coords.

    Ordinary FIELD, TOGGLE and OP hits return None so the shell's common RNA
    editing dispatcher can handle them. MAT actions are handled locally.
    """
    global _drag,_menu_click
    if _drag: return active_event(context,event)
    state=_state(area); material=current_material(context,state)
    hit=surfaces.lookup(area,x,y)
    action=hit[4] if hit else None
    if event.type in {'LEFTMOUSE','RIGHTMOUSE'}:
        click,_menu_click=_menu_click,None
        if click and event.value=='RELEASE' and event.type==click['button']:
            # Max menus open on a click and stay open. Opened on the press, Blender
            # would pick the item under the cursor on this release and close.
            if click['area']==area.as_pointer() and click['still'](x,y): click['open'](context)
            return {'RUNNING_MODAL'}
    if event.type=='MOUSEMOVE':
        surfaces._hover[area.as_pointer()]=(x,y); area.tag_redraw(); return None
    graph=state.kind=='Slate' and _inside(state.view,x,y)
    if event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
        step=1 if event.type=='WHEELUPMOUSE' else -1
        if graph:
            vx,vy,_,_=state.view
            old=state.zoom; state.zoom=max(.20,min(2.5,old*(1.12 if step>0 else 1/1.12)))
            ratio=state.zoom/old
            state.pan=[x-vx-(x-vx-state.pan[0])*ratio,y-vy-(y-vy-state.pan[1])*ratio]
        elif state.kind=='Slate' and x<state.view[0]:
            state.browser_scroll=max(0,min(state.browser_max,state.browser_scroll-step*3))
        else: state.param_scroll=max(0,min(state.param_max,state.param_scroll-step*45))
        runtime.redraw(); return {'RUNNING_MODAL'}
    if event.type=='MIDDLEMOUSE' and event.value=='PRESS' and graph:
        _drag=dict(kind='PAN',area=area.as_pointer(),window=context.window.as_pointer(),
                   start=(x,y),last=(x,y),pan=tuple(state.pan))
        return {'RUNNING_MODAL'}
    if event.type=='LEFTMOUSE' and event.value in {'PRESS','DOUBLE_CLICK'}:
        if action and action[0]!='MAT': return None
        if action:
            name=action[1]
            if name=='SOCKET':
                socket=_socket_from_action(action)
                if socket:
                    _drag=dict(kind='LINK',area=area.as_pointer(),window=context.window.as_pointer(),
                               start=(x,y),last=(x,y),first_position=state.socket_positions.get((socket.node.name,socket.is_output,action[-1]),(x,y)),
                               material=action[2],socket=socket)
                return {'RUNNING_MODAL'}
            if name=='NODE':
                node=action[3]; _node_select(material,node,event.ctrl or event.shift)
                state.selected_node=node.name; state.param_scroll=0
                if event.value!='DOUBLE_CLICK':
                    _drag=dict(kind='NODES',area=area.as_pointer(),window=context.window.as_pointer(),
                               start=(x,y),last=(x,y),positions=[(n,tuple(n.location)) for n in _moving_nodes(state,material)])
                runtime.redraw(); return {'RUNNING_MODAL'}
            if name=='BROWSER_NODE':
                state.browser_item=action[2]
                if event.value=='DOUBLE_CLICK':
                    mat=material or new_material(context,state=state)
                    vx,vy,vw,vh=state.view
                    node=add_node(mat,action[2],((vw*.5-state.pan[0])/state.zoom,(vh*.65-state.pan[1])/state.zoom))
                    state.selected_node=node.name; _undo('Create Material Map')
                else:
                    _drag=dict(kind='BROWSER',area=area.as_pointer(),window=context.window.as_pointer(),
                               start=(x,y),last=(x,y),node_type=action[2])
                runtime.redraw(); return {'RUNNING_MODAL'}
            if name in {'ENUM','GET'}:  # option lists, and the scene list when the object has no material
                rect=hit[:4]
                _menu_click=dict(area=area.as_pointer(),button='LEFTMOUSE',open=lambda ctx:dispatch(ctx,action),
                                 still=lambda mx,my:(surfaces.lookup(area,mx,my) or (None,))[:4]==rect)
                return {'RUNNING_MODAL'}
            result=dispatch(context,action)
            return {'RUNNING_MODAL'} if result is not None else None
        if graph and material and material.node_tree:
            for node in material.node_tree.nodes: node.select=False
            runtime.redraw(); return {'RUNNING_MODAL'}
    if event.type=='RIGHTMOUSE' and event.value=='PRESS' and graph:
        if action and action[:2]==('MAT','SOCKET'):
            dispatch(context,('MAT','UNLINK')+action[2:])
            return {'RUNNING_MODAL'}
        node=_node_at(state,material,x,y)
        if node:
            _node_select(material,node); state.selected_node=node.name; runtime.redraw()
        name='BSM_MT_material_edit' if node else 'BSM_MT_material_node_add'
        _menu_click=dict(area=area.as_pointer(),button='RIGHTMOUSE',open=lambda ctx:bpy.ops.wm.call_menu(name=name),
                         still=lambda mx,my:_inside(state.view,mx,my))
        return {'RUNNING_MODAL'}
    if event.value=='PRESS':
        from .keymap import match
        row=match(SLATE_KEYS if state.kind=='Slate' else COMPACT_KEYS,event)
        if row:
            dispatch(context,('MAT',)+row[4]); runtime.redraw(); return {'RUNNING_MODAL'}
        if state.kind=='Slate' and not (event.ctrl or event.alt or event.shift):
            if event.type=='X': dispatch(context,('MAT','DELETE')); return {'RUNNING_MODAL'}
            if event.type in {'F','HOME'}: dispatch(context,('MAT','FRAME')); return {'RUNNING_MODAL'}
    return None


_C,_A,_S={'ctrl':True},{'alt':True},{'shift':True}
# Default.hsxb SME table (369891408): shortcut, action, key, modifiers, command, action id.
SLATE_KEYS=(
    ('A','Assign Material to Selection','A',{},('ASSIGN',),'369891408-40500'),
    ('Ctrl+A','Select All','A',_C,('SELECT_ALL',),'369891408-40063'),
    ('Ctrl+D','Select None','D',_C,('SELECT_NONE',),'369891408-40064'),
    ('Ctrl+I','Select Invert','I',_C,('SELECT_INVERT',),'369891408-40065'),
    ('Shift+Page Down','Select Children','PAGE_DOWN',_S,('SELECT_CHILDREN',),'369891408-40066'),
    ('Ctrl+T','Select Tree','T',_C,('SELECT_TREE',),'369891408-55564'),
    ('Delete','Delete Selected','DEL',{},('DELETE',),'369891408-40058'),
    ('L','Lay Out All','L',{},('LAYOUT',),'369891408-40060'),
    ('C','Lay Out Children','C',{},('LAYOUT_CHILDREN',),'369891408-40076'),
    ('Alt+C','Move Children','C',_A,('MOVE_CHILDREN',),'369891408-40077'),
    ('H','Hide Unused Nodeslots','H',{},('HIDE_UNUSED',),'369891408-40075'),
    ('O','Material/Map Browser','O',{},('BROWSER',),'369891408-40068'),
    ('P','Parameter Editor','P',{},('PARAMETER',),'369891408-40069'),
    ('N','Navigator','N',{},('NAVIGATOR',),'369891408-55565'),
    ('Z','Zoom Extents Selected','Z',{},('FRAME_SELECTED',),'369891408-40071'),
    ('Ctrl+Alt+Z','Zoom Extents','Z',{'ctrl':True,'alt':True},('FRAME',),'369891408-40070'),
    ('Alt+P','Pan to Selected','P',_A,('PAN',),'369891408-40072'),
    ('U','Update Selected Previews','U',{},('PREVIEW',),'369891408-55570'),
)
# Default.hsxb Material Editor table (2) for the Compact editor.
COMPACT_KEYS=(
    ('A','Assign Material to Selection','A',{},('ASSIGN',),'2-1074'),
    ('O','Get Material','O',{},('GET',),'2-1069'),
)
# No equivalent in these editors: Rename (F2), Show Grid, the Select/Pan/Zoom tool modes,
# Auto Update Previews, and the Compact editor's sibling/parent navigation and Make Preview.


def dispatch(context,action):
    global _enum_target
    if not action or action[0]!='MAT': return None
    state=_state(context.area); material=current_material(context,state)
    name=action[1]
    if name=='NEW': new_material(context,state=state); _undo('Create Material')
    elif name=='ENABLE_NODES':
        if material: material.use_nodes=True; request_preview(material); _undo('Enable Material Shader')
    elif name=='GET':
        material=getattr(context.view_layer.objects.active,'active_material',None)
        if material: _set_material(context,material,state)
        else: bpy.ops.wm.call_menu(name='BSM_MT_material_scene')
    elif name=='MATERIAL': _set_material(context,action[2],state)
    elif name=='ASSIGN':
        if assign_material(context,material): _undo('Assign Material to Selection')
    elif name=='SELECT_USERS': select_material_users(context,material)
    elif name=='DUPLICATE':
        if material:
            _set_material(context,material.copy(),state); _undo('Duplicate Material')
    elif name=='CLEAR_SLOT':
        slots=ensure_slots(context.scene)
        if slots: slots[context.scene.bsm_material_slot_index].material=None
        state.material=None; _undo('Clear Material Sample Slot')
    elif name=='SLOT':
        slots=ensure_slots(context.scene); index=action[2]
        context.scene.bsm_material_slot_index=index
        material=slots[index].material if slots else None
        if not material: material=new_material(context,state=state); _undo('Create Material Sample')
        state.material=material; state.selected_node=''; state.param_scroll=0
        request_preview(material)
    elif name=='BROWSER': state.browser=not state.browser
    elif name=='PARAMETER': state.parameter=not state.parameter
    elif name=='NAVIGATOR': state.navigator=not state.navigator
    elif name=='GRID':
        context.scene.bsm_material_slot_grid={'24':'6','6':'15','15':'24'}[context.scene.bsm_material_slot_grid]
    elif name=='GRID_SET': context.scene.bsm_material_slot_grid=action[2]
    elif name=='ROLLOUT':
        key=action[2]
        if key in state.expanded: state.expanded.remove(key)
        else: state.expanded.add(key)
    elif name=='PREVIEW':
        if material: request_preview(material)
    elif name=='VIEWPORT':
        from .operators import viewport_override
        try: override=viewport_override(context)
        except RuntimeError: override={}
        view=override.get('area')
        if view and view.type=='VIEW_3D': view.spaces.active.shading.type='MATERIAL'
        # An editor-only workspace may not contain a viewport; the primary
        # workspace can still be prepared to show the material on return.
        for workspace in bpy.data.workspaces:
            if workspace.get('bsm_primary_workspace'):
                for screen in workspace.screens:
                    for area in screen.areas:
                        if area.type=='VIEW_3D': area.spaces.active.shading.type='MATERIAL'
    elif name=='DELETE':
        if material and material.node_tree:
            nodes=[n for n in material.node_tree.nodes if n.select]
            for node in nodes: material.node_tree.nodes.remove(node)
            state.selected_node=''; request_preview(material)
            if nodes: _undo('Delete Material Nodes')
    elif name=='FRAME': frame_nodes(state,material)
    elif name=='PUT': pass  # disabled: Blender edits the scene material itself
    elif name=='MOVE_CHILDREN': state.move_children=not state.move_children
    elif name=='HIDE_UNUSED':
        if material and material.node_tree:
            node=material.node_tree.nodes.get(state.selected_node)
            for n in [n for n in material.node_tree.nodes if n.select] or ([node] if node else []):
                state.hidden_slots^={n.name}
    elif name=='BACKGROUND': _preview_background[0]=not _preview_background[0]
    elif name=='MATERIAL_ID':
        if material: bpy.ops.wm.call_menu(name='BSM_MT_material_id')
    elif name=='MATERIAL_ID_SET':
        if material: material.pass_index=int(action[2]); _undo('Material ID Channel')
    elif name=='LAYOUT_CHILDREN':
        if material and material.node_tree:
            root=material.node_tree.nodes.get(state.selected_node)
            if root:
                # Max's Lay Out Children: the maps wired into the node, in columns to its left.
                depth={root:0}; frontier=[root]
                while frontier:
                    nxt=[]
                    for link in material.node_tree.links:
                        if link.to_node in frontier and link.from_node not in depth:
                            depth[link.from_node]=depth[link.to_node]+1; nxt.append(link.from_node)
                    frontier=nxt
                rows={}
                for node,level in sorted(depth.items(),key=lambda item:item[1]):
                    if node is root: continue
                    row=rows.get(level,0); rows[level]=row+1
                    node.location=(root.location.x-level*310,root.location.y-row*max(220,60+len(node_inputs(node))*18))
                _undo('Lay Out Children')
    elif name=='FRAME_SELECTED': frame_nodes(state,material,selected=True)
    elif name=='ZOOM_IN': state.zoom=min(2.5,state.zoom*1.2)
    elif name=='ZOOM_OUT': state.zoom=max(.2,state.zoom/1.2)
    elif name=='PAN':
        # The navigation control recenters on the selected node; MMB performs
        # continuous pan. This button never creates a dead modal tool.
        if material and material.node_tree:
            node=material.node_tree.nodes.get(state.selected_node)
            if node:
                _,_,w,h=state.view
                state.pan=[w*.5-node.location.x*state.zoom-100*state.zoom,
                           h*.55-node.location.y*state.zoom]
            else: frame_nodes(state,material)
    elif name=='SELECT': pass
    elif name=='SELECT_ALL':
        if material and material.node_tree:
            for node in material.node_tree.nodes: node.select=True
    elif name in {'SELECT_NONE','SELECT_INVERT'}:
        if material and material.node_tree:
            for node in material.node_tree.nodes: node.select=name=='SELECT_INVERT' and not node.select
    elif name in {'SELECT_CHILDREN','SELECT_TREE'}:
        # Max's children are the maps wired into the selected nodes; the tree is all of them.
        if material and material.node_tree:
            chosen={n for n in material.node_tree.nodes if n.select}
            frontier=set(chosen)
            while frontier:
                inputs={l.from_node for l in material.node_tree.links if l.to_node in frontier}-chosen
                chosen|=inputs; frontier=inputs if name=='SELECT_TREE' else set()
            for node in chosen: node.select=True
    elif name=='LAYOUT':
        if material and material.node_tree:
            nodes=list(material.node_tree.nodes)
            ranks={n.name:0 for n in nodes}
            for _ in range(len(nodes)):
                changed=False
                for link in material.node_tree.links:
                    rank=min(len(nodes),ranks[link.from_node.name]+1)
                    if ranks[link.to_node.name]<rank:
                        ranks[link.to_node.name]=rank; changed=True
                if not changed: break
            counts={}
            for node in nodes:
                rank=ranks[node.name]; row=counts.get(rank,0); counts[rank]=row+1
                height=max(220,60+len(node_inputs(node))*18)
                node.location=(rank*310,-row*height)
            state.needs_fit=True; _undo('Lay Out Material Nodes')
    elif name=='EXPAND':
        if material and material.node_tree:
            node=material.node_tree.nodes.get(state.selected_node)
            if node:
                if node.name in state.expanded: state.expanded.remove(node.name)
                else: state.expanded.add(node.name)
    elif name=='NODE_ADD':
        mat=material or new_material(context,state=state)
        node=add_node(mat,action[2]); state.selected_node=node.name
        state.needs_fit=True; _undo('Create Material Map')
    elif name=='UNLINK':
        mat,node,is_output,index=action[2:]
        socket=(node.outputs if is_output else node.inputs)[index]
        for link in list(socket.links): mat.node_tree.links.remove(link)
        request_preview(mat); _undo('Remove Material Map Connection')
    elif name=='COLOR':
        mat,node,is_output,index=action[2:]
        socket=(node.outputs if is_output else node.inputs)[index]
        bpy.ops.bsm.material_color('INVOKE_DEFAULT',material=mat.name,node=node.name,
                                   socket=socket.identifier,output=is_output)
    elif name=='MAP':
        mat,node,index=action[2:]
        socket=node.inputs[index]
        mapnode=add_node(mat,'ShaderNodeTexImage',(node.location.x-310,node.location.y-index*30))
        output=mapnode.outputs.get('Color')
        connect_sockets(mat,output,socket)
        state.selected_node=mapnode.name; state.needs_fit=True
        bpy.ops.bsm.material_image('INVOKE_DEFAULT',material=mat.name,node=mapnode.name)
        _undo('Assign Bitmap Map')
    elif name=='IMAGE':
        bpy.ops.bsm.material_image('INVOKE_DEFAULT',material=action[2].name,node=action[3].name)
    elif name=='ENUM':
        _enum_target=(action[2],action[3]); bpy.ops.wm.call_menu(name='BSM_MT_material_enum')
    elif name=='RAMP_ADD':
        action[3].color_ramp.elements.new(.5); request_preview(action[2]); _undo('Add Color Ramp Stop')
    elif name=='RAMP_REMOVE':
        ramp=action[3].color_ramp
        if len(ramp.elements)>2: ramp.elements.remove(ramp.elements[action[4]])
        request_preview(action[2]); _undo('Remove Color Ramp Stop')
    elif name=='RAMP_COLOR':
        bpy.ops.bsm.material_color('INVOKE_DEFAULT',material=action[2].name,node=action[3].name,ramp=action[4])
    else: return None
    runtime.redraw()
    return {'FINISHED'}


class BSM_OT_material_action(bpy.types.Operator):
    bl_idname='bsm.material_action'
    bl_label='Material Editor Action'
    action: StringProperty()
    value: StringProperty()
    def execute(self,context):
        if self.action=='NODE_ADD': return dispatch(context,('MAT','NODE_ADD',self.value))
        if self.action=='MATERIAL':
            material=bpy.data.materials.get(self.value)
            if material: return dispatch(context,('MAT','MATERIAL',material))
            return {'CANCELLED'}
        if self.action=='GRID_SET': return dispatch(context,('MAT','GRID_SET',self.value))
        if self.action=='MATERIAL_ID_SET': return dispatch(context,('MAT','MATERIAL_ID_SET',self.value))
        if self.action=='ENUM_SET':
            if _enum_target:
                owner,attr=_enum_target
                try:
                    setattr(owner,attr,self.value); _undo('Material Option')
                except (ValueError,ReferenceError,TypeError): return {'CANCELLED'}
            runtime.redraw(); return {'FINISHED'}
        return dispatch(context,('MAT',self.action)) or {'CANCELLED'}


class BSM_MT_material_id(bpy.types.Menu):
    bl_label='Material ID Channel'
    def draw(self,context):
        state=_state(context.area) if context.area else None
        material=current_material(context,state) if state else None
        for i in range(16):
            _menu_action(self.layout,str(i),'MATERIAL_ID_SET',str(i),icon='RADIOBUT_ON' if material and material.pass_index==i else 'RADIOBUT_OFF')


class BSM_OT_material_color(bpy.types.Operator):
    bl_idname='bsm.material_color'
    bl_label='Color Selector'
    bl_options={'REGISTER','UNDO'}
    material: StringProperty(options={'HIDDEN'})
    node: StringProperty(options={'HIDDEN'})
    socket: StringProperty(options={'HIDDEN'})
    output: bpy.props.BoolProperty(default=False,options={'HIDDEN'})
    ramp: IntProperty(default=-1,options={'HIDDEN'})
    color: FloatVectorProperty(name='Color',subtype='COLOR',size=4,min=0.,max=1.,default=(.5,.5,.5,1.))
    def _target(self):
        material=bpy.data.materials.get(self.material)
        node=material.node_tree.nodes.get(self.node) if material and material.node_tree else None
        if not node: return None
        if self.ramp>=0:
            return node.color_ramp.elements[self.ramp] if self.ramp<len(node.color_ramp.elements) else None
        return next((s for s in (node.outputs if self.output else node.inputs) if s.identifier==self.socket),None)
    def invoke(self,context,event):
        target=self._target()
        if target is None: return {'CANCELLED'}
        self.color=target.color if self.ramp>=0 else target.default_value
        return context.window_manager.invoke_props_dialog(self,width=360)
    def draw(self,context):
        self.layout.template_color_picker(self,'color',value_slider=True)
        self.layout.prop(self,'color',text=_tr('RGBA'))
    def execute(self,context):
        target=self._target()
        if target is None: return {'CANCELLED'}
        if self.ramp>=0: target.color=self.color
        else: target.default_value=self.color
        material=bpy.data.materials.get(self.material)
        request_preview(material); runtime.redraw()
        return {'FINISHED'}


class BSM_OT_material_image(bpy.types.Operator,ImportHelper):
    bl_idname='bsm.material_image'
    bl_label='Open Bitmap'
    bl_options={'REGISTER','UNDO'}
    material: StringProperty(options={'HIDDEN'})
    node: StringProperty(options={'HIDDEN'})
    filter_glob: StringProperty(default='*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.exr;*.hdr;*.bmp;*.tga',options={'HIDDEN'})
    def execute(self,context):
        material=bpy.data.materials.get(self.material)
        node=material.node_tree.nodes.get(self.node) if material and material.node_tree else None
        if not node or node.type!='TEX_IMAGE': return {'CANCELLED'}
        try:
            image=bpy.data.images.load(self.filepath,check_existing=True)
            if not image.size[0] or not image.size[1]:
                self.report({'ERROR'},'The selected file could not be decoded as an image')
                return {'CANCELLED'}
            node.image=image
        except (RuntimeError,OSError) as error:
            self.report({'ERROR'},str(error)); return {'CANCELLED'}
        request_preview(material); runtime.redraw(); return {'FINISHED'}


def _menu_action(layout,text,action,value='',icon='NONE'):
    op=layout.operator('bsm.material_action',text=_tr(text),icon=icon)
    op.action=action; op.value=value


class BSM_MT_material_modes(bpy.types.Menu):
    bl_label='Modes'
    def draw(self,context):
        self.layout.operator('bsm.editor',text=_tr('Slate Material Editor')).kind='MATERIAL'
        self.layout.operator('bsm.editor',text=_tr('Compact Material Editor')).kind='COMPACT'


class BSM_MT_material_actions(bpy.types.Menu):
    bl_label='Material'
    def draw(self,context):
        for label,action in (('Get Material from Selected Object','GET'),('Create Material','NEW'),
                             ('Assign Material to Selection','ASSIGN'),('Duplicate Material','DUPLICATE'),
                             ('Select By Material','SELECT_USERS'),('Show Material in Viewport','VIEWPORT'),
                             ('Update Preview','PREVIEW')):
            _menu_action(self.layout,label,action)
        self.layout.menu('BSM_MT_material_scene')


class BSM_MT_material_edit(bpy.types.Menu):
    bl_label='Edit'
    def draw(self,context):
        self.layout.menu('BSM_MT_material_node_add')
        for label,action in (('Delete Selected Nodes','DELETE'),('Show All / Main Inputs','EXPAND'),
                             ('Lay Out All','LAYOUT'),('Duplicate Material','DUPLICATE')):
            _menu_action(self.layout,label,action)


class BSM_MT_material_select(bpy.types.Menu):
    bl_label='Select'
    def draw(self,context):
        _menu_action(self.layout,'Select All Nodes','SELECT_ALL')
        _menu_action(self.layout,'Select Objects By Material','SELECT_USERS')


class BSM_MT_material_view(bpy.types.Menu):
    bl_label='View'
    def draw(self,context):
        for label,action in (('Zoom Extents','FRAME'),('Zoom In','ZOOM_IN'),('Zoom Out','ZOOM_OUT'),('Pan to Selected','PAN'),('Lay Out All','LAYOUT')):
            _menu_action(self.layout,label,action)
        self.layout.separator()
        for value,label in (('6','3 x 2 Sample Windows'),('15','5 x 3 Sample Windows'),('24','6 x 4 Sample Windows')):
            _menu_action(self.layout,label,'GRID_SET',value)


class BSM_MT_slate_tools(bpy.types.Menu):
    bl_label='Tools'
    def draw(self,context):
        for label,action in (('Material/Map Browser','BROWSER'),('Parameter Editor','PARAMETER'),('Navigator','NAVIGATOR')):
            _menu_action(self.layout,label,action)


class BSM_MT_material_node_add(bpy.types.Menu):
    bl_label='Materials and Maps'
    def draw(self,context):
        previous=''
        for group,label,node_type in CATALOGUE:
            if group!=previous:
                if previous: self.layout.separator()
                self.layout.label(text=_tr(group)); previous=group
            _menu_action(self.layout,label,'NODE_ADD',node_type)


class BSM_MT_material_scene(bpy.types.Menu):
    bl_label='Scene Materials'
    def draw(self,context):
        for material in bpy.data.materials:
            _menu_action(self.layout,material.name,'MATERIAL',material.name)
        if not bpy.data.materials: self.layout.label(text=_tr('No scene materials'))
        self.layout.separator(); _menu_action(self.layout,'Create Material','NEW')


class BSM_MT_material_enum(bpy.types.Menu):
    bl_label='Material Option'
    def draw(self,context):
        if not _enum_target: return
        owner,attr=_enum_target
        try:
            for item in owner.bl_rna.properties[attr].enum_items:
                if item.identifier: _menu_action(self.layout,item.name,'ENUM_SET',item.identifier)
        except ReferenceError: pass


def clear():
    """Cancel modal gestures and release GPU objects; preserve scene materials."""
    global _drag,_enum_target,_smooth_shader,_menu_click
    if _drag and _drag.get('kind')=='NODES':
        for node,position in _drag['positions']:
            try: node.location=position
            except ReferenceError: pass
    _drag=None; _enum_target=None; _menu_click=None
    _states.clear(); _textures.clear(); _sphere_batches.clear(); _pending_previews.clear()
    _smooth_shader=None
    if bpy.app.timers.is_registered(_preview_tick): bpy.app.timers.unregister(_preview_tick)


CLASSES=(BSM_MaterialSlot,BSM_OT_material_action,BSM_OT_material_color,
         BSM_OT_material_image,BSM_MT_material_modes,BSM_MT_material_actions,
         BSM_MT_material_edit,BSM_MT_material_select,BSM_MT_material_view,
         BSM_MT_slate_tools,BSM_MT_material_node_add,BSM_MT_material_scene,
         BSM_MT_material_enum,BSM_MT_material_id)
