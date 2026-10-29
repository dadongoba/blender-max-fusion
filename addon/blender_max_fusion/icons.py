# SPDX-License-Identifier: GPL-3.0-or-later
"""Original vector controls for the Blender Max interface.

The supplied application screenshot establishes the visual vocabulary: small
silver silhouettes, turquoise construction lines, ochre snap indicators and
blue pressed buttons. The paths below are independently drawn geometry. This
module contains no extracted application artwork, fonts or brand marks.

``draw(name, x, y, size, active=False, enabled=True)`` draws into the current
Blender GPU region. Coordinates specify the bottom-left of a square. All paths
use a 24-unit design grid; strokes are triangles, so scaling does not depend on
driver line-width support. ``geometry(name)`` exposes the same deterministic
triangles without needing a GPU, for tests and asset previews. Call ``clear``
when removing the extension so GPU batches do not outlive their context.
"""
from math import asin, atan2, cos, hypot, pi, sin, sqrt


SILVER = (.80, .80, .80, 1.)
BRIGHT = (.88, .88, .88, 1.)
MUTED = (.46, .50, .52, 1.)
TEAL = (.25, .72, .71, 1.)
DARK_TEAL = (.22, .49, .52, 1.)
GOLD = (1., .72, .03, 1.)
BLUE = (.30, .52, .73, 1.)
RED = (.79, .37, .34, 1.)
GREEN = (.38, .68, .46, 1.)

ICON_NAMES = (
    'undo', 'redo', 'link', 'unlink', 'bind', 'selection', 'cursor',
    'select_list', 'box', 'circle', 'lasso', 'move', 'rotate', 'scale',
    'orientation', 'pivot', 'snap3', 'snap_angle', 'snap_percent',
    'snap_settings', 'selection_lock', 'selection_set', 'mirror', 'align',
    'array', 'clone', 'explorer', 'graph', 'curve', 'dope', 'material',
    'render_setup', 'render', 'teapot', 'frame', 'quad', 'maximize',
    'smooth', 'flat', 'hide', 'unhide', 'isolate', 'create', 'modify',
    'hierarchy', 'motion', 'display', 'utilities', 'geometry', 'shapes',
    'lights', 'cameras', 'helpers', 'spacewarps', 'systems', 'paint',
    'object_paint', 'freeform', 'populate', 'measure', 'script', 'asset',
    'layer', 'frozen', 'visible', 'folder', 'search', 'clear', 'dropdown',
    'left', 'right', 'zoom', 'orbit', 'pan', 'walk', 'home', 'key',
    'first', 'previous', 'play', 'stop', 'next', 'last', 'auto_key',
    'set_key', 'lock', 'unlock', 'save', 'open', 'new', 'import', 'export',
    'help', 'vertex', 'edge', 'border', 'polygon', 'element', 'plus',
    'minus', 'settings', 'filter', 'time', 'viewport', 'camera', 'light',
    'mesh', 'shape', 'modifiers', 'material_library', 'texture', 'schematic',
    'playback', 'render_output', 'selection_region', 'angle', 'percent',
    # Main toolbar extensions.
    'window_crossing', 'fence', 'paint_select', 'select_place',
    'selection_center', 'transform_center', 'manipulate', 'keyboard_override',
    'snap2', 'snap25', 'spinner_snap', 'manage_sets', 'layer_explorer',
    'toggle_ribbon', 'compact_material', 'rendered_frame', 'render_iterative',
    'activeshade', 'project_folder', 'project_set', 'project_new',
    'project_config',
    # Modifier stack toolbar.
    'pin', 'end_result', 'make_unique', 'remove_modifier', 'configure_sets',
    'bulb_on', 'bulb_off',
    # Render toolbar strip.
    'arv', 'arv_render', 'arv_ipr', 'flow_render', 'flow_monitor', 'denoiser',
    'arnold_light', 'arnold_procedural', 'arnold_alembic', 'arnold_volume',
    'bake_geometry', 'arnold_props', 'aovs', 'light_groups', 'operator_graph',
    # Scene Explorer filters, viewport navigation and timeline controls.
    'groups', 'xrefs', 'bones', 'containers', 'display_all', 'display_none',
    'display_invert', 'find_filter', 'time_config', 'key_filters', 'zoom_all',
    'zoom_extents', 'zoom_extents_all', 'zoom_region', 'fov', 'add_time_tag',
    'isolate_toggle', 'abs_rel', 'key_mode',
    # Time controls under the viewports.
    'mini_curve', 'set_keys', 'shield', 'tag_cube', 'tan_auto', 'tan_linear', 'tan_step', 'tan_custom',
    # Slate Material Editor toolbar, in Max 2027's order.
    'sme_select', 'sme_pick', 'sme_put', 'sme_assign', 'sme_delete', 'sme_move_children', 'sme_hide_unused',
    'sme_shaded', 'sme_background', 'sme_material_id', 'sme_layout_all', 'sme_layout_children', 'sme_browser',
    'sme_parameters', 'sme_select_by_material',
)

_geometry = {}
_batches = {}
_shader = None


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _triangulate(points):
    """Ear-clip a small simple outline, including concave cursor silhouettes."""
    points = list(points)
    if len(points) < 3:
        return []
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
    if area < 0:
        points.reverse()
    remaining = list(range(len(points)))
    triangles = []
    while len(remaining) > 3:
        found = False
        for i in range(len(remaining)):
            ia, ib, ic = remaining[i-1], remaining[i], remaining[(i+1)%len(remaining)]
            a,b,c = points[ia],points[ib],points[ic]
            if _cross(a,b,c) <= 1e-8:
                continue
            inside = False
            for index in remaining:
                if index in (ia,ib,ic):
                    continue
                p=points[index]
                if min(_cross(a,b,p),_cross(b,c,p),_cross(c,a,p)) >= -1e-8:
                    inside=True
                    break
            if inside:
                continue
            triangles.append((a,b,c))
            remaining.pop(i)
            found=True
            break
        if not found:
            raise ValueError('Non-simple icon outline')
    if len(remaining)==3:
        triangles.append(tuple(points[i] for i in remaining))
    return triangles


class _Pen:
    def __init__(self):
        self.vertices=[]
        self.colors=[]

    def polygon(self, points, color=SILVER):
        for triangle in _triangulate(points):
            self.vertices.extend(triangle)
            self.colors.extend([color]*3)

    def rect(self, x, y, w, h, color=SILVER):
        self.polygon(((x,y),(x+w,y),(x+w,y+h),(x,y+h)),color)

    def line(self, points, color=SILVER, width=1.5, closed=False):
        points=list(points)
        if closed:
            points.append(points[0])
        half=width*.5
        for a,b in zip(points,points[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            length=hypot(dx,dy)
            if length < 1e-8:
                continue
            ox,oy=-dy*half/length,dx*half/length
            self.polygon(((a[0]+ox,a[1]+oy),(a[0]-ox,a[1]-oy),
                          (b[0]-ox,b[1]-oy),(b[0]+ox,b[1]+oy)),color)
        # Round joins without extending the silhouette by a pixel-sized cap.
        for point in points[1:-1]:
            self.disc(point[0],point[1],half,color,8)

    def disc(self, x, y, r, color=SILVER, steps=20):
        self.polygon([(x+r*cos(i*2*pi/steps),y+r*sin(i*2*pi/steps))
                      for i in range(steps)],color)

    def ellipse(self, x, y, rx, ry, color=SILVER, width=1.4, start=0., end=2*pi, steps=28):
        self.line([(x+rx*cos(start+(end-start)*i/steps),
                    y+ry*sin(start+(end-start)*i/steps)) for i in range(steps+1)],color,width)

    def arrow(self, a, b, color=SILVER, width=1.6, head=4.):
        self.line((a,b),color,width)
        angle=atan2(b[1]-a[1],b[0]-a[0])
        self.polygon((b,(b[0]-head*cos(angle)+head*.60*sin(angle),
                         b[1]-head*sin(angle)-head*.60*cos(angle)),
                        (b[0]-head*cos(angle)-head*.60*sin(angle),
                         b[1]-head*sin(angle)+head*.60*cos(angle))),color)

    def dashed_box(self, x, y, w, h, color=TEAL, width=1.3):
        for edge in (((x,y),(x+w,y)),((x+w,y),(x+w,y+h)),
                     ((x+w,y+h),(x,y+h)),((x,y+h),(x,y))):
            a,b=edge
            for lo,hi in ((0.,.22),(.39,.61),(.78,1.)):
                self.line(((a[0]+(b[0]-a[0])*lo,a[1]+(b[1]-a[1])*lo),
                           (a[0]+(b[0]-a[0])*hi,a[1]+(b[1]-a[1])*hi)),color,width)

    def cube(self, x=12., y=12., r=8., color=SILVER, filled=False):
        top=(x,y+r)
        left=(x-r*.85,y+r*.48)
        right=(x+r*.85,y+r*.48)
        middle=(x,y)
        bottom=(x,y-r)
        ll=(left[0],left[1]-r)
        rr=(right[0],right[1]-r)
        if filled:
            self.polygon((top,right,middle,left),color)
            self.polygon((left,middle,bottom,ll),tuple(v*.7 for v in color[:3])+(1.,))
            self.polygon((middle,right,rr,bottom),tuple(v*.85 for v in color[:3])+(1.,))
        else:
            self.line((top,right,rr,bottom,ll,left,top),color,1.35)
            self.line((left,middle,right),color,1.1)
            self.line((middle,bottom),color,1.1)

    def cursor(self, x=6., y=3., scale=.9, color=BRIGHT):
        self.polygon([(x+px*scale,y+py*scale) for px,py in
                      ((0,19),(0,1),(4.8,5.7),(8.4,-.2),(11.1,1.3),(7.4,7.5),(14.1,7.8))],color)

    def gear(self, x=12., y=12., r=8., color=SILVER):
        points=[]
        for i in range(32):
            angle=(i+.5)*2*pi/32
            radius=r if i%4 in (0,1) else r*.76
            points.append((x+radius*cos(angle),y+radius*sin(angle)))
        self.line(points,color,1.5,True)
        self.ellipse(x,y,r*.34,r*.34,color,1.5,steps=16)


def _digit3(p, x=3., y=8., scale=1., color=GOLD):
    p.line([(x+px*scale,y+py*scale) for px,py in
            ((0,9),(5,9),(7,7),(5,5),(2,5),(5,5),(7,3),(5,0),(0,0))],color,1.7)


def _magnet(p, x=13., y=8., scale=.9, color=GOLD):
    p.line([(x+px*scale,y+py*scale) for px,py in
            ((-4,5),(-4,0),(-3,-3),(0,-4),(3,-3),(4,0),(4,5))],color,2.4)
    p.line(((x-4*scale,y+5*scale),(x-4*scale,y+7*scale)),SILVER,2.4)
    p.line(((x+4*scale,y+5*scale),(x+4*scale,y+7*scale)),SILVER,2.4)


def _eye(p, crossed=False):
    p.line(((2.5,12),(5,15.5),(8,17.5),(12,18),(16,17.5),(19,15.5),
            (21.5,12),(19,8.5),(16,6.5),(12,6),(8,6.5),(5,8.5),(2.5,12)),SILVER,1.5)
    p.ellipse(12,12,3.8,4.5,TEAL,1.7,steps=20)
    p.disc(12,12,1.6,BRIGHT)
    if crossed:
        p.line(((3,3),(21,21)),GOLD,2.)


def _teapot(p, color=TEAL):
    p.polygon(((5,14),(6,7),(9,4.5),(15,4.5),(18,8),(18,14)),color)
    p.line(((6,14),(8,16),(16,16),(18,14)),BRIGHT,1.3)
    p.rect(8,17,8,1.2,SILVER)
    p.disc(12,19,1.5,SILVER)
    p.line(((5.5,13),(2.5,15),(1.5,12),(2,8),(6,7)),SILVER,1.7)
    p.polygon(((17,11),(20,13),(21,18),(23,18),(21,11),(17,7)),color)
    p.line(((7,6),(9,5),(15,5),(17,8)),SILVER,.8)


def _small_window(p):
    p.rect(1,2,22,21,SILVER)
    p.rect(2,3,20,15,(.265,.265,.265,1.))
    for x in (3,7,11): p.rect(x,19,3,2,(.265,.265,.265,1.))


def _capsule(p,cx,cy,length=8,radius=3,angle=pi/4,color=SILVER,width=2.5):
    points=[]
    for center,start in ((length/2,-pi/2),(-length/2,pi/2)):
        for i in range(13):
            a=start+i*pi/12
            x,y=center+radius*cos(a),radius*sin(a)
            points.append((cx+x*cos(angle)-y*sin(angle),cy+x*sin(angle)+y*cos(angle)))
    p.line(points,color,width,True)


def _stamp(p, shape, x=0., y=0., s=1.):
    """Draw ``shape(pen)`` scaled by ``s`` about the origin, then offset."""
    q=_Pen(); shape(q)
    p.vertices.extend((x+vx*s,y+vy*s) for vx,vy in q.vertices)
    p.colors.extend(q.colors)


def _dashed(p, points, color=TEAL, width=1.4, closed=True, dash=3.6):
    points=list(points)+(list(points[:1]) if closed else [])
    for a,b in zip(points,points[1:]):
        n=max(1,round(hypot(b[0]-a[0],b[1]-a[1])/dash))
        for i in range(n):
            p.line([(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t) for t in (i/n,(i+.58)/n)],color,width)


def _glyph(p, char, x, y, scale=1., color=GOLD, width=1.7):
    paths={'2':((0,7),(1.5,9),(5.5,9),(7,7.5),(7,6),(0,0),(7,0)),
           '5':((7,9),(1,9),(.5,5),(5,5.5),(7,4),(7,1.5),(5.5,0),(0,0))}
    p.line([(x+px*scale,y+py*scale) for px,py in paths[char]],color,width)


def _pot(p, color=SILVER):
    p.polygon(((3,14),(6,3),(16,3),(20,14),(15,17),(8,17)),color)
    p.polygon(((4,12),(0,18),(7,15)),color)
    p.ellipse(19,12,3.3,3.7,color,1.8,steps=20)
    p.rect(8,17,8,1.4,color);p.disc(12,20,1.6,color)


def _cloud(p, color=SILVER):
    for x,y,r in ((6.5,10,4),(12,13,5.5),(17.5,10.5,4.5)): p.disc(x,y,r,color,20)
    p.rect(6.5,6,11,5,color)


def _cycle(p, x, y, r, color=TEAL, width=1.8, end=5.2):
    p.ellipse(x,y,r,r,color,width,.5,end,24)
    ex,ey,h=x+r*cos(end),y+r*sin(end),width*1.9
    p.polygon(((ex-h*sin(end),ey+h*cos(end)),(ex+h*.85*cos(end),ey+h*.85*sin(end)),
               (ex-h*.85*cos(end),ey-h*.85*sin(end))),color)


def _cog(p, x, y, r, color=SILVER, hole=(.265,.265,.265,1.)):
    p.polygon([(x+(r if i%4 in (0,1) else r*.7)*cos((i+.5)*pi/16),
                y+(r if i%4 in (0,1) else r*.7)*sin((i+.5)*pi/16)) for i in range(32)],color)
    p.disc(x,y,r*.32,hole,12)


def _badge(p, x, y, kind='plus', r=5.):
    p.disc(x,y,r,(.265,.265,.265,1.),20)
    if kind=='plus':
        p.rect(x-r*.62,y-r*.17,r*1.24,r*.34,GOLD);p.rect(x-r*.17,y-r*.62,r*.34,r*1.24,GOLD)
    elif kind=='check':
        p.line(((x-r*.58,y+r*.05),(x-r*.15,y-r*.45),(x+r*.6,y+r*.5)),GREEN,1.9)
    else: _cog(p,x,y,r*.8,SILVER)


def _bulb(p, x=12., y=14.5, r=5.8, on=True):
    glass=[(x+r*cos(-.9+i*(pi+1.8)/20),y+r*sin(-.9+i*(pi+1.8)/20)) for i in range(21)]
    glass+=[(x-.42*r,y-1.32*r),(x+.42*r,y-1.32*r)]
    if on:
        p.polygon(glass,GOLD)
        p.ellipse(x,y,r*.58,r*.58,BRIGHT,1.,pi*.55,pi*.95,6)
        for i in range(5):
            c,s=cos(i*pi/4),sin(i*pi/4)
            p.line(((x+r*1.24*c,y+r*1.24*s),(x+r*1.5*c,y+r*1.5*s)),GOLD,1.3)
    else:
        p.polygon(glass,(.32,.35,.36,1.))
        p.line(glass,MUTED,1.3,True)
        p.line(((x-.25*r,y-1.2*r),(x-.25*r,y-.3*r),(x,y+.1*r),(x+.25*r,y-.3*r),(x+.25*r,y-1.2*r)),MUTED,.9)
    base=SILVER if on else MUTED
    p.rect(x-.45*r,y-1.68*r,.9*r,.28*r,base)
    p.rect(x-.38*r,y-2.02*r,.76*r,.24*r,base)
    p.rect(x-.18*r,y-2.22*r,.36*r,.14*r,base)


def _pencil(p, a, b, color=GOLD):
    l=hypot(b[0]-a[0],b[1]-a[1]); ux,uy=(b[0]-a[0])/l,(b[1]-a[1])/l
    m=(b[0]-3.2*ux,b[1]-3.2*uy)
    p.line((a,m),color,3.)
    p.polygon((b,(m[0]-1.5*uy,m[1]+1.5*ux),(m[0]+1.5*uy,m[1]-1.5*ux)),SILVER)
    p.line((a,(a[0]+1.4*ux,a[1]+1.4*uy)),RED,3.)


def _key(p, color=GOLD):
    p.ellipse(7,16,4.4,4.4,color,2.2,steps=24)
    p.line(((10.2,12.8),(20.5,2.5)),color,2.8)
    for x,y in ((15.2,7.8),(18.4,4.6)): p.line(((x,y),(x+2.2,y+2.2)),color,2.4)


def _toolbar_shape(name):
    """Independently drawn functional silhouettes from installed visual references.

    Only original geometry ships; the private Qt resource comparison is outside
    the extension and source archives. This is not a pixel-identity claim.
    """
    p=_Pen(); bg=(.265,.265,.265,1.)
    if name in {'undo','redo'}:
        pts=((7,22),(1,17),(7,12),(7,15),(15,15),(18,14),(19,12),(19,9),(17,6),(12,6),(12,3),(17,3),(20,5),(22,9),(22,13),(20,17),(16,19),(7,19))
        p.polygon(tuple((24-x,y) if name=='redo' else (x,y) for x,y in pts),SILVER)
    elif name in {'link','unlink'}:
        _capsule(p,8,8,7,3.3,width=2.4);_capsule(p,16,16,7,3.3,width=2.4)
        p.line(((8,8),(16,16)),SILVER,2.3)
        if name=='unlink':
            p.line(((8,13),(13,8)),bg,5)
            p.line(((7,14),(10,11)),TEAL,1.6);p.line(((14,7),(17,4)),TEAL,1.6)
    elif name=='bind':
        for y in (4,9,14): p.line([(x,y+1.5*sin((x-1)*pi/9)) for x in range(1,23)],SILVER,1.8)
        _capsule(p,16,19,5,2.4,color=GOLD,width=1.8)
    elif name=='cursor':
        p.rect(1,3,18,19,SILVER)
        p.cursor(15,0,.58,GOLD)
    elif name=='select_list':
        for y,w in ((19,20),(14,20),(9,13),(4,10)): p.rect(2,y,w,3,SILVER)
        p.cursor(16,0,.54,GOLD)
    elif name=='box': p.dashed_box(2,2,20,20,TEAL,1.6)
    elif name=='circle':
        for i in range(12): p.ellipse(12,12,10,10,TEAL,1.8,i*pi/6,i*pi/6+pi/9,3)
    elif name=='move':
        p.rect(10.5,4,3,16,SILVER);p.rect(4,10.5,16,3,SILVER)
        for pts in (((12,24),(7,18),(17,18)),((12,0),(7,6),(17,6)),((0,12),(6,7),(6,17)),((24,12),(18,7),(18,17))): p.polygon(pts,SILVER)
    elif name=='rotate':  # Max's Select and Rotate: an open circular arrow, head at the top right
        start,end=pi*46/180,pi*328/180
        p.ellipse(12,12,7.4,7.4,SILVER,3.4,start,end,34)
        p.disc(12+7.4*cos(end),12+7.4*sin(end),1.7,SILVER,12)  # rounded tail
        hx,hy=12+7.4*cos(start),12+7.4*sin(start)
        tx,ty=sin(start),-cos(start)  # clockwise tangent at the head
        nx,ny=cos(start),sin(start)
        p.polygon(((hx+tx*4.,hy+ty*4.),(hx-nx*3.5,hy-ny*3.5),(hx+nx*3.5,hy+ny*3.5)),SILVER)
    elif name=='scale':
        p.dashed_box(2,2,20,20,TEAL,1.6)
        p.rect(2,2,11,11,SILVER)
        p.line(((10,16),(16,16),(16,10)),TEAL,2.7)
    elif name=='orientation':
        p.rect(2,4,5,18,SILVER);p.rect(14,10,6,12,SILVER)
        for x,y in ((6,5),(19,11)):
            p.rect(x-4,y-1,8,2,TEAL);p.rect(x-1,y-4,2,8,TEAL)
    elif name=='mirror':
        p.polygon(((3,5),(8,1),(8,16),(3,20)),SILVER)
        p.polygon(((16,1),(21,5),(21,20),(16,16)),TEAL)
        for y in (1,7,13,19): p.rect(11,y,2,4,SILVER)
    elif name=='align':
        for y in (1,7,13,19): p.rect(2,y,2,4,TEAL)
        p.rect(7,3,15,6,SILVER);p.rect(7,14,12,6,SILVER)
    elif name in {'snap_angle','snap_percent','snap_settings'}:
        if name=='snap_angle':
            p.line(((3,3),(3,19)),SILVER,2.2)
            p.ellipse(3,3,9,9,SILVER,2.,0,pi/2,20)
        elif name=='snap_percent':
            p.ellipse(5,17,3.1,3.1,SILVER,2.,steps=20)
            p.ellipse(16,5,3.1,3.1,SILVER,2.,steps=20)
            p.line(((4,2),(19,21)),SILVER,2.2)
        else:
            p.polygon(((1,13),(6,20),(11,13)),SILVER)
            p.polygon(((1,9),(6,2),(11,9)),SILVER)
        _capsule(p,18,18,5,3,angle=pi/4,color=GOLD,width=2)
        p.rect(12,9,4,6,bg)
    elif name in {'explorer','dope','layer','array','curve','graph','material','render_setup','render','teapot','schematic'}:
        if name in {'explorer','dope','layer','curve','graph','material'}: _small_window(p)
        if name in {'explorer','dope'}:
            for y in (5,10,15): p.rect(3,y,3,2,SILVER);p.rect(8,y,12,2,SILVER)
        elif name=='layer':
            for y in (7,12): p.polygon(((4,y),(12,y+4),(20,y),(12,y-4)),SILVER)
        elif name=='array':
            p.rect(1,2,22,21,SILVER)
            for x,y,w in ((3,13,6),(14,13,6),(3,5,6),(14,5,6)): p.rect(x,y,w,3,bg)
            p.rect(1,19,10,4,SILVER);p.rect(13,19,4,4,SILVER);p.rect(19,19,4,4,SILVER)
        elif name in {'curve','graph'}:
            pts=[(x,10+3.4*sin((x-3)*pi/9)) for x in range(3,22)]
            p.line(pts,bg,3.6);p.line(pts,TEAL,2.)
        elif name=='material':
            p.disc(8,10,4.3,SILVER,24)
            for x,y in ((5,9),(8,12),(8,6),(11,9)): p.rect(x-1,y-1,2,2,bg)
            for y in (5,10,15): p.rect(15,y,5,2,SILVER)
        elif name=='schematic':
            p.rect(1,19,22,4,SILVER);p.rect(1,2,22,4,TEAL)
            p.arrow((12,17),(12,7),TEAL,4.,5.)
        elif name in {'render_setup','teapot','render'}:
            if name=='teapot':
                _small_window(p);p.rect(2,3,20,15,TEAL)
            p.polygon(((3,14),(6,3),(16,3),(20,14),(15,17),(8,17)),SILVER)
            p.polygon(((4,12),(0,18),(7,15)),SILVER)
            p.ellipse(19,12,3.3,3.7,SILVER,1.6,steps=20)
            p.rect(8,17,8,1.4,SILVER);p.disc(12,20,1.6,SILVER)
            if name=='render_setup': p.disc(15,8,6,GOLD,20);p.gear(15,8,5.5,bg);p.disc(15,8,2.3,SILVER)
            elif name=='render': p.polygon(((18,17),(15,9),(20,9),(14,0),(24,11),(19,11),(22,18)),TEAL)
    else: return None
    return tuple(p.vertices),tuple(p.colors)


def _panel_shape(name):
    """Main-toolbar, modifier-stack, render-strip, explorer and timeline extras."""
    p=_Pen(); bg=(.265,.265,.265,1.)
    # Main toolbar.
    if name=='window_crossing':
        p.disc(15.5,9,7,(.58,.58,.58,1.),28);p.disc(14.8,9.7,6.2,SILVER,28)
        p.dashed_box(2,8,12,14,TEAL,1.6)
    elif name=='fence':
        pts=((3,4),(5,20),(12,14),(21,21),(20,7),(11,2))
        _dashed(p,pts,TEAL,1.5)
        for x,y in pts: p.rect(x-1.3,y-1.3,2.6,2.6,SILVER)
    elif name=='paint_select':
        for lo,hi in ((0,.2),(.34,.54),(.68,.88)):
            p.line([(2+10*t,3+2*t+6*t*t) for t in (lo+(hi-lo)*k/4 for k in range(5))],TEAL,1.8)
        p.disc(16,15,5.6,MUTED,24);p.ellipse(16,15,5.6,5.6,SILVER,1.6,steps=24)
        p.disc(16,15,1.4,BRIGHT,10)
    elif name=='select_place':
        plane=((1,2),(15,2),(23,8.5),(9,8.5))
        p.polygon(plane,DARK_TEAL);p.line(plane,TEAL,1.1,True)
        p.cube(11,9.8,4.4,SILVER,True)
        p.arrow((11,23),(11,15.6),GOLD,1.8,3.8)
    elif name=='selection_center':
        p.cube(6.5,16.5,4.3,SILVER,True);p.cube(17.5,7.5,4.3,SILVER,True)
        p.line(((12,8.5),(12,15.5)),GOLD,1.2);p.line(((8.5,12),(15.5,12)),GOLD,1.2)
        p.ellipse(12,12,2.6,2.6,GOLD,1.4,steps=16)
    elif name=='transform_center':
        p.arrow((10,9),(10,22),SILVER,1.6,4.2);p.arrow((10,9),(22,9),SILVER,1.6,4.2)
        p.arrow((10,9),(3,2),TEAL,1.5,3.6)
        p.ellipse(10,9,3.2,3.2,GOLD,1.2,steps=16);p.disc(10,9,1.6,GOLD,12)
    elif name=='manipulate':
        p.ellipse(16,16,5.5,5.5,TEAL,1.5,steps=28)
        for x,y in ((16,21.5),(21.5,16)): p.rect(x-1.6,y-1.6,3.2,3.2,GOLD)
        p.cursor(3,1,.78,BRIGHT)
    elif name=='keyboard_override':
        p.rect(1,2,22,12,SILVER)
        for y,xs in ((10.5,(3,7,11,15,19)),(7,(5,9,13,17))):
            for x in xs: p.rect(x,y,2.4,2,bg)
        p.rect(6,3.6,12,1.8,bg)
        _capsule(p,12,19,7,3,angle=0,color=TEAL,width=1.6)
        p.disc(15.5,19,1.9,GOLD,14)
    elif name in ('snap2','snap25','spinner_snap'):
        _magnet(p,14,6,.78)
        if name=='snap2': _glyph(p,'2',2.5,12,.9)
        elif name=='snap25':
            _glyph(p,'2',1,13,.68,width=1.5);p.disc(7,13.4,1.,GOLD,10)
            _glyph(p,'5',8.4,13,.68,width=1.5)
        else:
            p.polygon(((1,14),(5.2,20),(9.4,14)),SILVER);p.polygon(((1,12),(5.2,6),(9.4,12)),SILVER)
        p.rect(17,19,3,3,TEAL)
    elif name=='manage_sets':
        p.line(((6,22),(2,22),(2,2),(6,2)),TEAL,1.5)
        for y,w in ((17,10),(12,10),(7,7)): p.rect(5,y,w,2.6,SILVER)
        _pencil(p,(22,19),(15,4))
    elif name=='layer_explorer':
        for y,color in ((6,MUTED),(11,SILVER),(16,TEAL)):
            sheet=((2,y),(12,y+5),(22,y),(12,y-5))
            p.line(sheet,bg,2.2,True);p.polygon(sheet,color)
    elif name=='toggle_ribbon':
        p.line(((2,3),(22,3),(22,21),(2,21),(2,3)),SILVER,1.4)
        p.rect(2,18,20,3,SILVER);p.rect(2.7,12.5,18.6,4.5,TEAL)
        for x in (4.5,9,13.5): p.rect(x,13.5,3,2.5,BRIGHT)
        p.line(((8.5,6),(12,9.5),(15.5,6)),GOLD,1.7)
    elif name=='compact_material':
        for i,(x,y) in enumerate([(x,y) for y in (16,7) for x in (4.5,12,19.5)]):
            p.disc(x,y,3.4,TEAL if i==0 else SILVER,18);p.disc(x-1.1,y+1.2,1.,BRIGHT,8)
    elif name=='rendered_frame':
        _small_window(p)
        p.polygon(((2,3),(22,3),(22,10),(17,14),(12,8),(9,11),(2,5)),TEAL)
        p.disc(7,14.5,2.,GOLD,14)
    elif name in ('render_iterative','activeshade'):
        _stamp(p,_pot,0,0,.72)
        if name=='render_iterative': _cycle(p,18,18,4.3,TEAL,1.7)
        else:
            p.ellipse(17.5,18,5.6,3.6,TEAL,1.6,steps=24);p.disc(17.5,18,2.,BRIGHT,12)
    elif name in ('project_folder','project_set','project_new','project_config'):
        p.polygon(((2,4),(21,4),(23,16),(11,16),(8,20),(2,20)),GOLD)
        p.line(((2,4),(5,14),(23,14)),BRIGHT,1.1)
        if name=='project_folder': p.cube(14,8.6,3.6,TEAL,True)
        else: _badge(p,18,6,{'project_set':'check','project_new':'plus'}.get(name,'gear'),5.3)
    # Modifier stack toolbar.
    elif name=='pin':
        rot=lambda pts:[(12+.707*(x-12+y-12),12+.707*(y-x)) for x,y in pts]
        p.line(rot(((12,.5),(12,8))),BRIGHT,1.3)
        p.polygon(rot(((6.5,8),(17.5,8),(15.5,10.5),(8.5,10.5))),SILVER)
        p.polygon(rot(((9.5,10.5),(14.5,10.5),(13.8,16.5),(10.2,16.5))),SILVER)
        p.polygon(rot(((7.5,16.5),(16.5,16.5),(16.5,19.5),(7.5,19.5))),TEAL)
    elif name=='end_result':
        for i,color in enumerate((MUTED,MUTED,SILVER,GOLD)):
            y=2.5+i*4.6; plate=((2,y),(15,y),(22,y+3.6),(9,y+3.6))
            p.line(plate,bg,2.,True);p.polygon(plate,color)
    elif name=='make_unique':
        p.cube(8,9,6,SILVER)
        p.line(((17,21),(21.25,18.4),(21.25,13.4),(17,11),(12.75,13.4),(12.75,18.4)),bg,2.6,True)
        p.cube(17,16,5,TEAL,True)
    elif name=='remove_modifier':
        p.rect(4,17,16,2.2,SILVER);p.rect(9.5,19.2,5,1.8,SILVER)
        p.polygon(((5.5,15.5),(18.5,15.5),(17,2),(7,2)),SILVER)
        for x in (9,12,15): p.line(((x,4),(x,13.5)),bg,1.2)
    elif name=='configure_sets':
        for y,w in ((18,18),(13,11),(8,8),(3,8)): p.rect(2,y,w,3,SILVER)
        p.disc(17,8,6.6,bg,24);_cog(p,17,8,5.4,TEAL)
    elif name in ('bulb_on','bulb_off'): _bulb(p,on=name=='bulb_on')
    # Render toolbar strip.
    elif name in ('arv','arv_render','arv_ipr'):
        _small_window(p)
        if name=='arv':
            p.line(((4,4.5),(12,16),(20,4.5)),TEAL,2.4);p.line(((8.5,9),(15.5,9)),GOLD,1.6)
        elif name=='arv_render': _stamp(p,lambda q:_pot(q,TEAL),5,3.6,.58)
        else: _cycle(p,12,10.5,5,TEAL,1.8)
    elif name in ('flow_render','flow_monitor'):
        _stamp(p,_cloud,1.2,6,.9)
        if name=='flow_render': _stamp(p,lambda q:_pot(q,TEAL),5,-1.4,.6)
        else:
            for y,w in ((7,14),(3.8,14),(.6,9)):
                p.rect(4,y,2.2,2,TEAL);p.rect(7.6,y,w-3.6,2,SILVER)
    elif name=='denoiser':
        p.rect(12,3,9,18,SILVER)
        for i in range(3):
            for j in range(6):
                if (i+j)%2 or (i*j)%4==1: p.rect(3.5+i*2.9,3.5+j*2.9,2.4,2.4,TEAL if (i*2+j)%5==0 else SILVER)
        p.line(((3,3),(21,3),(21,21),(3,21),(3,3)),SILVER,1.2)
    elif name=='arnold_light':
        panel=((2,15),(15,15),(22,21),(9,21))
        p.polygon(panel,GOLD);p.line(panel,SILVER,1.1,True)
        for a,b in (((4,13),(2.5,4)),((8.5,13),(8,3)),((13,13),(13.5,3)),((18.5,15.5),(20,6))):
            p.line((a,b),GOLD,1.3)
    elif name=='arnold_procedural':
        p.line(((8,21),(5,21),(5,14),(2.5,12),(5,10),(5,3),(8,3)),SILVER,1.8)
        p.line(((16,21),(19,21),(19,14),(21.5,12),(19,10),(19,3),(16,3)),SILVER,1.8)
        p.rect(8,10.9,8,2.2,GOLD);p.rect(10.9,8,2.2,8,GOLD)
    elif name=='arnold_alembic':
        p.line([(11+8*cos(pi/6+i*pi/3),13+8*sin(pi/6+i*pi/3)) for i in range(6)],SILVER,2.,True)
        p.polygon([(11+3.6*cos(pi/6+i*pi/3),13+3.6*sin(pi/6+i*pi/3)) for i in range(6)],TEAL)
        _badge(p,18.5,5.5)
    elif name=='arnold_volume':
        _stamp(p,_cloud,-1,3,1.)
        for x,y in ((6,12),(9.5,15),(13,12.5),(11,18.5),(16,15),(8,10)): p.disc(x,y,.9,MUTED,8)
        _badge(p,18.5,5.5)
    elif name=='bake_geometry':
        p.cube(12,17.6,4.5,SILVER,True)
        p.arrow((12,12.4),(12,6.2),GOLD,1.8,3.6)
        p.polygon(((1,2),(16,2),(23,6),(8,6)),TEAL)
    elif name=='arnold_props':
        p.cube(10,13,8,SILVER,True)
        tag=((12,7),(16,11),(23,11),(23,3),(16,3))
        p.line(tag,bg,2.4,True);p.polygon(tag,GOLD);p.disc(16.3,7,1.2,bg,10)
    elif name=='aovs':
        for x,y,color in ((9,12,MUTED),(5.5,8,SILVER),(2,4,SILVER)):
            frame=((x,y),(x+13,y),(x+13,y+10),(x,y+10))
            p.line(frame,bg,2.2,True);p.polygon(frame,color)
        p.rect(3,5,11,8,bg)
        p.polygon(((3,5),(14,5),(14,8),(11,11),(8,8),(6,10),(3,7)),TEAL)
    elif name=='light_groups':
        for y,color in ((5,MUTED),(9.5,TEAL)):
            sheet=((8,y),(15.5,y+3.8),(23,y),(15.5,y-3.8))
            p.line(sheet,bg,2.,True);p.polygon(sheet,color)
        _bulb(p,7,15.5,3.9)
    elif name=='operator_graph':
        p.line(((9,18),(11.5,17.5),(12.5,12.5),(15,12)),TEAL,1.4)
        p.line(((9,6),(11.5,6.5),(12.5,11.5),(15,12)),TEAL,1.4)
        for x,y in ((1,15.5),(1,3.5),(15,9.5)): p.rect(x,y,8,5,SILVER);p.rect(x,y+3.6,8,1.4,MUTED)
        for x,y in ((9,18),(9,6),(15,12)): p.disc(x,y,1.3,GOLD,10)
    # Scene Explorer filters, viewport navigation and timeline controls.
    elif name=='groups':
        p.line(((6,21),(2,21),(2,3),(6,3)),TEAL,1.6);p.line(((18,21),(22,21),(22,3),(18,3)),TEAL,1.6)
        for x,y in ((8.5,15.5),(15.5,15.5),(12,8.5)): p.cube(x,y,3.6,SILVER,True)
    elif name=='xrefs':
        p.cube(9.5,13.5,7.5,SILVER)
        p.disc(17,7,6.4,bg,22)
        for x,y in ((15,9),(19,5)): _capsule(p,x,y,4,1.9,color=GOLD,width=1.5)
    elif name=='bones':
        p.line(((6,6),(18,18)),SILVER,3.4)
        for x,y in ((3.7,6.9),(6.9,3.7),(17.1,20.3),(20.3,17.1)): p.disc(x,y,2.6,SILVER,16)
    elif name=='containers':
        p.cube(12,11.5,8.5,SILVER,True)
        p.line(((4.78,13.08),(12,9),(19.22,13.08)),GOLD,1.6)
        p.line(((12,9),(12,3)),GOLD,1.6)
    elif name in ('display_all','display_none','display_invert'):
        for y in (16.5,10,3.5):
            p.rect(10,y+1.5,11,2,SILVER)
            if name=='display_all': p.rect(2.5,y,5,5,TEAL)
            elif name=='display_invert': p.polygon(((2.5,y),(7.5,y),(2.5,y+5)),TEAL)
            if name!='display_all': p.line(((2.5,y),(7.5,y),(7.5,y+5),(2.5,y+5),(2.5,y)),SILVER,1.2)
    elif name=='find_filter':
        p.polygon(((1,22),(17,22),(11,14),(11,6),(7,4),(7,14)),SILVER);p.rect(3,19.5,12,1.6,TEAL)
        p.disc(16,9,6.,bg,22);p.ellipse(15.5,9.5,3.8,3.8,TEAL,1.6,steps=20)
        p.line(((18.3,6.7),(22,3)),SILVER,2.6)
    elif name=='time_config':
        p.ellipse(10,13,8,8,SILVER,1.6,steps=28);p.line(((10,18.5),(10,13),(14,11)),TEAL,1.7)
        p.disc(17.5,6.5,6.4,bg,24);_cog(p,17.5,6.5,5.,GOLD)
    elif name=='key_filters':
        _stamp(p,_key,0,0,.85)
        p.polygon(((13,23),(23,23),(19.5,18),(19.5,12.5),(16.5,11),(16.5,18)),SILVER)
    elif name in ('zoom_all','zoom_region'):
        if name=='zoom_region': p.dashed_box(2,10,13,11,TEAL,1.4);p.disc(14,10,5.2,bg,22)
        cx,cy,r=(10,14,6.8) if name=='zoom_all' else (14,10,5.2)
        p.ellipse(cx,cy,r,r,SILVER,1.7,steps=26)
        p.line(((cx+r*.74,cy-r*.74),(22,2)),SILVER,3.)
        if name=='zoom_all':
            for x,y in ((6.6,10.6),(10.4,10.6),(6.6,14.4),(10.4,14.4)): p.rect(x,y,3,3,TEAL)
    elif name in ('zoom_extents','zoom_extents_all'):
        if name=='zoom_extents': p.dashed_box(2,2,20,20,TEAL,1.5);p.cube(12,12,6.5,SILVER,True)
        else:
            for x,y,sx,sy in ((2,2,1,1),(22,2,-1,1),(2,22,1,-1),(22,22,-1,-1)):
                p.line(((x+sx*5,y),(x,y),(x,y+sy*5)),SILVER,1.7)
            p.dashed_box(5.5,5.5,13,13,TEAL,1.3);p.cube(12,12,4.4,SILVER,True)
    elif name=='fov':
        p.polygon(((6,12),(22,21),(22,3)),MUTED)
        p.line(((22,21),(6,12),(22,3)),SILVER,1.5)
        p.ellipse(6,12,10,10,GOLD,1.6,-.51,.51,10)
        p.rect(1,9,5,6,SILVER)
    elif name=='add_time_tag':
        p.polygon(((2,14),(8,8),(19,8),(19,20),(8,20)),SILVER);p.disc(7.5,14,1.6,bg,10)
        _badge(p,18,6,'plus',5.2)
    elif name=='isolate_toggle':
        p.polygon(((9,19.5),(15,19.5),(22,2),(2,2)),DARK_TEAL)
        p.polygon(((8,23),(16,23),(15,19.5),(9,19.5)),GOLD)
        p.cube(12,8.5,5,SILVER,True)
    elif name=='abs_rel':
        p.rect(2,13,1.8,9,SILVER);p.arrow((3,17.5),(21,17.5),SILVER,1.8,4.5)
        p.ellipse(5,6.5,2.2,2.2,TEAL,1.3,steps=14);p.arrow((7.5,6.5),(21,6.5),TEAL,1.8,4.5)
    elif name=='key_mode':  # Key Mode Toggle: arrows apart, as in Max
        p.polygon(((2,12),(10,18),(10,6)),SILVER);p.polygon(((22,12),(14,18),(14,6)),SILVER)
    elif name=='mini_curve':  # Open Mini Curve Editor: track list and a curve
        for y in (17,12,7): p.rect(2,y,4,2,SILVER)
        p.line([(9+i*.6,12+5*sin(i*.45)) for i in range(23)],TEAL,1.8)
    elif name=='set_keys':  # the large Set Keys button: plus with a key
        p.rect(4,11,15,3.2,SILVER);p.rect(9.9,5,3.2,15,SILVER)
        p.disc(17,7,3.6,TEAL,18);p.disc(17,7,1.4,bg,10)
        p.line(((19.6,4.4),(22.5,1.5)),TEAL,2.);p.line(((21.4,2.6),(22.8,4)),TEAL,1.6)
    elif name=='shield':  # Safe Scene Script Execution
        p.polygon(((12,22),(20,19),(19,9),(12,2),(5,9),(4,19)),SILVER)
        p.polygon(((12,19.5),(17.5,17.5),(16.8,10),(12,5)),MUTED)
    elif name=='tag_cube':
        p.cube(12,12,8,SILVER)
    elif name in ('tan_auto','tan_linear','tan_step','tan_custom'):
        if name=='tan_linear': p.line(((4,5),(20,19)),GOLD,1.8)
        elif name=='tan_step': p.line(((4,5),(12,5),(12,19),(20,19)),GOLD,1.8)
        else:  # an arch through the key, like Max's Auto/Spline tangent icons
            p.line([(3+i*.9,4+15*sin(i*pi/20)) for i in range(21)],TEAL,1.8)
            if name=='tan_custom':
                p.line(((7,19),(17,19)),GOLD,1.2);p.rect(16,18,2.4,2.4,GOLD)
        ends=((4,5),(20,19)) if name in ('tan_linear','tan_step') else ((3,4),(21,4))
        for x,y in ends: p.rect(x-1.6,y-1.6,3.2,3.2,SILVER)
    else: return None
    return tuple(p.vertices),tuple(p.colors)


def _dots(p, cx, cy, s=2.6, color=BRIGHT):
    """The Slate toolbar's small material sample: four light cells round a dark centre."""
    for dx, dy in ((-s, 0), (s, 0), (0, s), (0, -s)):
        p.rect(cx+dx-s*.5, cy+dy-s*.5, s, s, color)


def _checker_ball(p, cx, cy, r, light, dark, cells=4):
    """A sample sphere with a checker pattern, as on Max's preview buttons."""
    p.disc(cx, cy, r, light, 28)
    step = 2*r/cells
    for i in range(cells):
        for j in range(cells):
            if (i+j) % 2:
                x0, y0 = cx-r+i*step, cy-r+j*step
                corners = ((x0, y0), (x0+step, y0), (x0, y0+step), (x0+step, y0+step))
                inside = [hypot(x-cx, y-cy) <= r*1.08 for x, y in corners]
                if sum(inside) >= 3 or (cells <= 4 and sum(inside) >= 2):
                    p.rect(x0, y0, step, step, dark)


def _sme_shape(name):
    """Slate Material Editor toolbar icons, drawn after Max 2027's silhouettes."""
    p=_Pen(); bg=(.265,.265,.265,1.); light=(.84,.84,.84,1.)
    if name=='sme_select':
        p.cursor(7,3,.95,BRIGHT)
    elif name=='sme_pick':  # eyedropper: hollow tube, collar and bulb, tip at the bottom left
        p.line(((5.5,5.5),(14,14)),SILVER,4.4); p.line(((6.3,6.3),(13.4,13.4)),bg,1.8)
        p.line(((2.4,2.4),(5.5,5.5)),SILVER,1.6)
        p.line(((11.8,16.6),(16.6,11.8)),SILVER,2.4)
        p.line(((15.5,15.5),(18.6,18.6)),SILVER,4.2); p.disc(19,19,3.2,SILVER)
    elif name in {'sme_put','sme_assign'}:  # a sample, a teal arrow down, then the scene or the selection
        _dots(p,6,18.5)
        p.line(((10.5,20.5),(15.5,20.5),(15.5,14.5)),TEAL,2.2)
        p.polygon(((12.2,14.8),(18.8,14.8),(15.5,10.8)),TEAL)
        if name=='sme_put':
            for x in (3.5,11):
                p.polygon(((x,2.5),(x+5.5,2.5),(x+9.5,8.5),(x+4,8.5)),light)
        else:
            p.rect(11,2.5,8.5,8,light)
    elif name=='sme_delete':  # rubbish bin with three slots
        p.rect(9,20,6,1.8,SILVER); p.rect(4.5,17.6,15,2.2,SILVER)
        p.polygon(((6,3),(18,3),(19,16.4),(5,16.4)),SILVER)
        for x in (8.2,11.1,14):
            p.rect(x,5.5,1.8,8.6,bg)
    elif name=='sme_move_children':
        p.rect(5,17,14.5,4.6,light)
        p.line(((10.5,17),(10.5,12),(16.5,12)),TEAL,2.)
        p.rect(16.5,9.8,4.4,4.4,TEAL)
        p.line(((1.5,6),(8.5,6)),TEAL,2.2); p.polygon(((7.8,9.2),(12,6),(7.8,2.8)),TEAL)
    elif name=='sme_hide_unused':
        p.disc(5.5,9,3.4,light)
        p.rect(9.5,3,11,11.5,TEAL)
        p.polygon(((11,16),(19,16),(15,21)),light)
    elif name=='sme_shaded':  # teal checker sample on a dark tile
        p.rect(2,2,20,20,(.13,.13,.13,1.))
        _checker_ball(p,12,12,8.2,(.53,.82,.81,1.),(.70,.92,.91,1.),6)
    elif name=='sme_background':  # black and white checker sample on a teal tile
        p.rect(2,2,20,20,TEAL)
        _checker_ball(p,12,12,8.2,(.93,.93,.93,1.),(.08,.08,.08,1.),6)
    elif name=='sme_material_id':  # the channel number is drawn over this tile
        p.rect(3,2.5,18,19,light)
    elif name=='sme_layout_all':
        for y in (15,4):
            p.polygon(((6,y+2.5),(9,y+5),(19.5,y+5),(19.5,y),(9,y)),light)
    elif name=='sme_layout_children':
        p.rect(2.5,10,4.6,4.6,light)
        p.line(((7,12.3),(10.5,12.3)),light,1.6); p.line(((10.5,5),(10.5,19.5)),light,1.6)
        p.line(((10.5,19.5),(13,19.5)),light,1.6); p.line(((10.5,5),(13,5)),light,1.6)
        p.rect(13,16.5,5.5,6,light); p.rect(13,2,5.5,6,light)
    elif name=='sme_browser':  # two samples, each with its list line
        for y in (17,7):
            _checker_ball(p,6.5,y,4.8,(.93,.93,.93,1.),(.10,.10,.10,1.),4)
            p.line(((12.5,y),(21.5,y)),light,2.2)
    elif name=='sme_parameters':  # a panel: title bar, then a sample in the body
        p.rect(2.5,2,19,20,(.72,.72,.72,1.))
        p.rect(3.5,17.5,17,3.4,(.20,.20,.20,1.))
        for x in (5,7.5,10,12.5):
            p.rect(x,18.6,1.6,1.2,light)
        _checker_ball(p,12,9.5,6.2,(.96,.96,.96,1.),(.06,.06,.06,1.),4)
    elif name=='sme_select_by_material':
        _checker_ball(p,10,13,7.5,(.36,.36,.36,1.),(.16,.16,.16,1.))
        p.cursor(14,0,.52,MUTED)
    else:
        return None
    return tuple(p.vertices),tuple(p.colors)


def _make(name):
    p=_Pen()
    if name.startswith('sme_'):
        return _sme_shape(name)
    aliases={'selection':'cursor','camera':'cameras','light':'lights',
             'mesh':'geometry','shape':'shapes','modifiers':'modify',
             'playback':'dope','selection_region':'box','settings':'utilities',
             'angle':'snap_angle','percent':'snap_percent','open':'folder',
             'render_output':'render','texture':'material_library'}
    name=aliases.get(name,name)
    specific=_toolbar_shape(name)
    if specific is None: specific=_panel_shape(name)
    if specific is not None: return specific
    if name in ('undo','redo'):
        sign=1 if name=='undo' else -1
        xf=lambda a:(12+sign*(a[0]-12),a[1])
        p.line([xf(a) for a in ((5,15),(13,15),(17,14),(19,11),(19,7),(16,5),(11,5))],SILVER,2.3)
        p.polygon([xf(a) for a in ((7,20),(1.5,15),(7,10))],SILVER)
    elif name in ('link','unlink','bind'):
        p.line(((4,9),(2.7,11),(3,15),(7.5,19.5),(11,20),(13,18.5),(13.5,16)),SILVER,2.2)
        p.line(((10.5,8),(10.5,5.5),(13,3.7),(16,4),(21,9),(21,12),(19,14)),SILVER,2.2)
        if name=='link':
            p.line(((7,8),(16,17)),SILVER,2.3)
        elif name=='unlink':
            p.line(((8,8),(10,10)),SILVER,2.2)
            p.line(((14,14),(16,16)),SILVER,2.2)
            p.line(((5,17),(8,15),(7,21),(9,18),(16,6),(19,4),(17,9),(20,8)),GOLD,1.5)
        else:
            p.line(((7,8),(16,17)),TEAL,2.3)
            p.line(((16,20),(20,20),(20,16)),GOLD,1.6)
    elif name=='cursor':
        p.cursor()
        p.polygon(((6,20),(6,15),(10,16)),GOLD)
    elif name=='select_list':
        for y in (18,14,10,6):
            p.rect(3,y,2,1.7,SILVER)
            p.rect(7,y,10,1.7,SILVER)
        p.cursor(14,2,.57,GOLD)
    elif name=='box':
        p.dashed_box(3,3,18,18)
        p.rect(3,3,3,3,SILVER)
    elif name=='circle':
        for i in range(12):
            a=i*pi/6
            p.ellipse(12,12,9,9,TEAL,1.5,a,a+pi/10,2)
        p.cursor(12,1,.48,SILVER)
    elif name=='lasso':
        p.line(((3,9),(2,14),(5,19),(11,21),(18,19),(21,15),(20,10),(16,7),(10,7),(7,9),(8,12),(11,12),(12,8),(11,3)),TEAL,1.5)
        p.cursor(13,1,.45,SILVER)
    elif name=='move':
        for a,b in (((12,12),(12,22)),((12,12),(12,2)),((12,12),(2,12)),((12,12),(22,12))):
            p.arrow(a,b,SILVER,1.6,4)
        p.disc(12,12,2,SILVER)
    elif name=='rotate':
        p.ellipse(12,12,8.5,8.5,SILVER,1.9,.1,5.25,30)
        p.polygon(((16.5,5),(20.5,4),(20,9)),SILVER)
        p.line(((5,12),(19,12)),TEAL,1.)
        p.line(((12,5),(12,19)),TEAL,1.)
    elif name=='scale':
        p.line(((4,4),(4,16),(16,16),(16,4),(4,4)),TEAL,1.3)
        p.arrow((8,8),(21,21),SILVER,1.8,5)
        p.rect(17,17,5,5,SILVER)
    elif name=='orientation':
        p.arrow((9,6),(9,22),SILVER,1.6,4)
        p.arrow((9,6),(22,6),SILVER,1.6,4)
        p.arrow((9,6),(2,1),TEAL,1.5,3.5)
        p.disc(9,6,2,GOLD)
    elif name=='pivot':
        p.line(((4,5),(4,18),(15,18)),SILVER,1.6)
        p.line(((8,5),(19,5),(19,16)),TEAL,1.6)
        for a,b in (((12,3),(12,22)),((3,12),(22,12))): p.line((a,b),GOLD,1.2)
        p.ellipse(12,12,3.3,3.3,GOLD,1.5,steps=18)
    elif name in ('snap3','snap_angle','snap_percent','snap_settings'):
        _magnet(p,14,6,.78)
        if name=='snap3':
            _digit3(p,2.5,12,.9)
            p.rect(17,19,3,3,TEAL)
        elif name=='snap_angle':
            p.line(((3,13),(3,22),(12,22)),GOLD,1.7)
            p.ellipse(3,22,6,6,GOLD,1.2,-pi/2,0,10)
        elif name=='snap_percent':
            p.line(((2,13),(11,23)),GOLD,1.7)
            p.ellipse(3.5,20.5,2,2,GOLD,1.2,steps=12)
            p.ellipse(10,14.5,2,2,GOLD,1.2,steps=12)
        else:
            p.gear(6,18,4.4,SILVER)
    elif name in ('selection_lock','lock','unlock'):
        p.rect(5,3,14,11,SILVER)
        p.ellipse(12,14,4.5,6,SILVER,2.,0,pi,16)
        if name=='unlock':
            p.rect(15.5,13.5,4,4,(.25,.25,.25,1.))
        p.disc(12,9,1.5,(.25,.27,.28,1.))
        p.rect(11.3,6,1.4,3,(.25,.27,.28,1.))
    elif name=='selection_set':
        p.rect(3,6,18,13,MUTED)
        p.line(((3,19),(3,21),(10,21),(12,19)),SILVER,1.3)
        for x in (6,11,16): p.rect(x,9,3,6,TEAL)
    elif name=='mirror':
        p.polygon(((3,5),(9,5),(9,19)),TEAL)
        p.line(((15,5),(21,5),(15,19),(15,5)),SILVER,1.5)
        p.line(((12,2),(12,22)),SILVER,1.2)
    elif name=='align':
        p.line(((12,2),(12,22)),SILVER,1.4)
        p.rect(3,16,9,4,TEAL)
        p.rect(8,10,9,4,SILVER)
        p.rect(12,4,9,4,TEAL)
        p.arrow((2,11),(6,11),GOLD,1.2,3)
    elif name in ('array','clone'):
        if name=='array':
            for x,y in ((4,4),(12,4),(4,12),(12,12)):
                p.line(((x,y),(x+6,y),(x+6,y+6),(x,y+6),(x,y)),TEAL if x==4 else SILVER,1.2)
        else:
            p.line(((3,3),(14,3),(14,14),(3,14),(3,3)),TEAL,1.4)
            p.rect(9,9,12,12,MUTED)
            p.line(((9,9),(21,9),(21,21),(9,21),(9,9)),SILVER,1.3)
            p.line(((12,15),(18,15),(15,12),(15,18)),GOLD,1.2)
    elif name in ('explorer','dope'):
        p.line(((3,2),(21,2),(21,22),(3,22),(3,2)),SILVER,1.3)
        p.rect(4,17,16,3,TEAL)
        for y in (13,9,5):
            p.rect(5,y,3,2,SILVER)
            p.rect(10,y,9,2,SILVER)
        if name=='dope':
            p.line(((13,3),(13,16)),GOLD,1.3)
            for y in (6,10,14): p.polygon(((13,y+2),(15,y),(13,y-2),(11,y)),GOLD)
    elif name in ('graph','curve'):
        p.line(((3,22),(3,3),(22,3)),SILVER,1.3)
        for y in (8,13,18): p.line(((4,y),(21,y)),MUTED,.65)
        for x in (8,13,18): p.line(((x,4),(x,21)),MUTED,.65)
        curve=((4,6),(7,6),(9,7),(11,10),(13,16),(15,18),(18,18),(21,17))
        p.line(curve,TEAL,1.9)
        if name=='graph':
            for x,y in (curve[0],curve[4],curve[-1]): p.rect(x-1.5,y-1.5,3,3,SILVER)
        else:
            p.line(((9,15),(17,19)),GOLD,1.)
            p.disc(9,15,1.3,GOLD)
            p.disc(17,19,1.3,GOLD)
    elif name in ('material','material_library'):
        if name=='material':
            p.disc(12,12,9,SILVER,28)
            p.polygon(((12,21),(17,18),(20,13),(18,8),(12,3),(14,10),(14,16)),MUTED)
            p.ellipse(12,12,8.8,3.1,TEAL,1.0,steps=28)
            p.ellipse(12,12,3.1,8.8,TEAL,1.0,steps=28)
            p.disc(8,16,2.1,BRIGHT)
        else:
            for x,y in ((7,7),(17,7),(7,17),(17,17)):
                p.disc(x,y,4.2,TEAL if x==7 and y==17 else SILVER,16)
                p.disc(x-1.2,y+1.3,1.2,BRIGHT,10)
    elif name in ('render','render_setup','teapot'):
        _teapot(p,TEAL if name!='teapot' else SILVER)
        if name=='render_setup': p.gear(17.5,6.5,5.,SILVER)
        elif name=='render':
            p.polygon(((19,1),(23,5),(19,9)),BRIGHT)
    elif name in ('frame','quad','maximize','viewport'):
        if name=='quad':
            p.line(((3,3),(21,3),(21,21),(3,21),(3,3)),SILVER,1.3)
            p.line(((12,3),(12,21)),TEAL,1.2)
            p.line(((3,12),(21,12)),TEAL,1.2)
            p.rect(13,13,7,7,TEAL)
        elif name=='maximize':
            p.line(((3,13),(3,21),(11,21)),SILVER,1.5)
            p.line(((13,3),(21,3),(21,11)),SILVER,1.5)
            p.arrow((8,16),(3,21),TEAL,1.3,3.6)
            p.arrow((16,8),(21,3),TEAL,1.3,3.6)
        elif name=='frame':
            for pts in (((2,15),(2,22),(9,22)),((15,22),(22,22),(22,15)),
                        ((22,9),(22,2),(15,2)),((9,2),(2,2),(2,9))):
                p.line(pts,SILVER,1.8)
            p.cube(12,12,5,TEAL)
        else:
            p.line(((2,4),(22,4),(22,20),(2,20),(2,4)),SILVER,1.4)
            p.line(((2,17),(22,17)),TEAL,1.)
            p.cube(12,10,4,TEAL)
    elif name in ('smooth','flat','geometry'):
        if name=='smooth':
            p.disc(12,12,9,SILVER,28)
            p.ellipse(12,12,3.6,9,TEAL,1.,steps=28)
            p.ellipse(12,12,9,3.6,TEAL,1.,steps=28)
        else:
            p.cube(12,12,9,SILVER,True)
            if name=='geometry':
                p.ellipse(12,12,8.8,8.8,SILVER,1.,steps=28)
    elif name in ('hide','unhide','visible','isolate'):
        _eye(p,name=='hide')
        if name=='unhide':
            p.line(((2,20),(6,20),(4,18),(4,22)),GOLD,1.2)
        elif name=='isolate':
            for x,y,sx,sy in ((2,2,1,1),(22,2,-1,1),(2,22,1,-1),(22,22,-1,-1)):
                p.line(((x+sx*4,y),(x,y),(x,y+sy*4)),TEAL,1.3)
    elif name in ('create','plus','minus'):
        p.rect(3,11,18,2.2,SILVER)
        if name!='minus': p.rect(11,3,2.2,18,SILVER)
    elif name=='modify':
        p.line(((5,3),(7,21),(19,21),(17,3),(5,3)),TEAL,1.6)
        p.line(((5,10),(17,10),(6,16),(18,16)),TEAL,1.0)
        for x,y in ((5,3),(7,21),(19,21),(17,3)):
            p.rect(x-1.6,y-1.6,3.2,3.2,SILVER)
    elif name=='hierarchy':
        p.rect(9,17,6,5,TEAL)
        p.line(((12,17),(12,11),(4,11),(4,7),(12,11),(20,11),(20,7)),SILVER,1.3)
        for x in (1,9,17): p.rect(x,2,6,5,SILVER)
    elif name in ('motion','time'):
        if name=='motion':
            p.ellipse(10,12,7.5,7.5,MUTED,2.,steps=24)
            p.ellipse(14,12,7.5,7.5,SILVER,1.7,steps=24)
            p.disc(14,12,4.7,SILVER)
        else:
            p.ellipse(12,12,9,9,SILVER,1.6,steps=30)
            p.line(((12,19),(12,12),(17,9)),TEAL,1.7)
    elif name=='display':
        p.rect(2,8,20,13,MUTED)
        p.line(((2,8),(22,8),(22,21),(2,21),(2,8)),SILVER,1.3)
        p.rect(5,11,14,7,TEAL)
        p.rect(10,4,4,4,SILVER)
        p.rect(6,2,12,2,SILVER)
    elif name=='utilities':
        # Max's open-end wrench: jaw at the upper right, handle to the lower left.
        cx=cy=15.6; r=5.; s=1.65; d=(cos(pi/4),sin(pi/4)); n=(-d[1],d[0])
        rim=sqrt(r*r-s*s); gap=asin(s/r)
        jaw=[(cx+n[0]*s+d[0]*rim,cy+n[1]*s+d[1]*rim)]
        jaw+=[(cx+r*cos(pi/4+gap+(2*pi-2*gap)*i/24),cy+r*sin(pi/4+gap+(2*pi-2*gap)*i/24)) for i in range(1,24)]
        jaw+=[(cx-n[0]*s+d[0]*rim,cy-n[1]*s+d[1]*rim),(cx-n[0]*s+d[0]*.4,cy-n[1]*s+d[1]*.4),
              (cx+n[0]*s+d[0]*.4,cy+n[1]*s+d[1]*.4)]
        p.polygon(jaw,SILVER)
        p.line(((5.2,5.2),(cx-2.,cy-2.)),SILVER,3.4)
        p.disc(5.2,5.2,2.3,SILVER)
        p.disc(5.2,5.2,.9,(.25,.27,.28,1.))
    elif name in ('shapes','freeform','shape'):
        p.line(((4,3),(4,17),(8,21),(19,20),(21,14),(16,10),(9,10),(5,6)),SILVER,1.7)
        for x,y in ((4,3),(8,21),(21,14),(9,10)):
            p.rect(x-1.4,y-1.4,2.8,2.8,TEAL)
    elif name=='lights':
        p.disc(12,14,5.4,SILVER,20)
        p.rect(9,5,6,4,SILVER)
        p.rect(10,2,4,2,SILVER)
        for i in range(7):
            a=(i*.25+.25)*pi
            p.line(((12+7.5*cos(a),14+7.5*sin(a)),(12+10.5*cos(a),14+10.5*sin(a))),SILVER,1.3)
    elif name=='cameras':
        p.rect(3,7,13,11,SILVER)
        p.polygon(((16,10),(22,6),(22,19),(16,15)),SILVER)
        p.disc(7,20,2.6,SILVER)
        p.disc(13,20,2.6,SILVER)
        p.line(((8,6),(5,2),(10,6),(13,2)),TEAL,1.2)
    elif name=='helpers':
        p.line(((3,3),(21,21),(3,21),(21,3)),SILVER,1.6)
        p.line(((3,12),(21,12),(12,3),(12,21)),SILVER,1.2)
        p.ellipse(12,12,3.7,3.7,TEAL,1.3,steps=16)
    elif name=='spacewarps':
        for y in (5,11,17):
            p.line([(x,y+2*sin((x-3)*pi/8)) for x in range(2,23)],SILVER,1.6)
    elif name=='systems':
        for x,y,r in ((7,8,4),(17,8,4),(12,18,3.5)):
            p.ellipse(x,y,r,r,SILVER,1.4,steps=20)
            p.disc(x,y,1.5,TEAL)
        p.line(((8,12),(10,15),(14,15),(16,12)),TEAL,1.2)
    elif name in ('paint','object_paint'):
        p.line(((9,11),(18,21)),SILVER,4.2)
        p.line(((9,11),(18,21)),TEAL,1.7)
        p.polygon(((4,3),(4,8),(7,12),(11,9),(9,5)),SILVER)
        p.line(((3,3),(11,3)),SILVER,1.3)
        if name=='object_paint': p.cube(17,6,4.5,TEAL,True)
    elif name=='populate':
        for x,y,s in ((6,12,.8),(17,12,.8),(12,5,.7)):
            p.disc(x,y+6*s,2.4*s,SILVER,14)
            p.line(((x,y+2*s),(x,y-3*s)),TEAL,2.6*s)
            p.line(((x-4*s,y),(x,y+2*s),(x+4*s,y)),SILVER,1.5*s)
            p.line(((x-3*s,y-7*s),(x,y-3*s),(x+3*s,y-7*s)),SILVER,1.5*s)
    elif name=='measure':
        p.polygon(((3,5),(6,2),(22,18),(19,21)),SILVER)
        for x,y in ((7,6),(10,9),(13,12),(16,15),(19,18)):
            p.line(((x,y),(x+2,y+2)),MUTED,.9)
    elif name=='script':
        p.line(((9,20),(4,20),(4,14),(2,12),(4,10),(4,4),(9,4)),SILVER,1.5)
        p.line(((15,20),(20,20),(20,14),(22,12),(20,10),(20,4),(15,4)),SILVER,1.5)
        p.line(((10,6),(14,18)),TEAL,1.7)
    elif name=='asset':
        p.line(((2,5),(12,1),(22,5),(22,18),(12,22),(2,18),(2,5)),SILVER,1.3)
        p.line(((2,18),(12,14),(22,18),(12,14),(12,1)),TEAL,1.3)
        p.line(((7,20),(17,16),(17,11)),GOLD,2.1)
    elif name=='layer':
        for y,color in ((7,SILVER),(11,TEAL),(15,SILVER)):
            p.line(((2,y),(12,y+6),(22,y),(12,y-6),(2,y)),color,1.4)
    elif name=='frozen':
        for a in (0,pi/3,2*pi/3):
            dx,dy=cos(a),sin(a)
            p.line(((12-10*dx,12-10*dy),(12+10*dx,12+10*dy)),TEAL,1.4)
            for sign in (-1,1):
                x,y=12+sign*6*dx,12+sign*6*dy
                p.line(((x-sign*3*dx-2*dy,y-sign*3*dy+2*dx),
                        (x,y),(x-sign*3*dx+2*dy,y-sign*3*dy-2*dx)),TEAL,1.1)
    elif name=='folder':
        p.polygon(((2,4),(21,4),(23,16),(11,16),(8,20),(2,20)),GOLD)
        p.line(((2,4),(5,14),(23,14)),BRIGHT,1.1)
    elif name in ('search','zoom'):
        p.ellipse(10,14,6.8,6.8,SILVER,1.7,steps=26)
        p.line(((15,9),(22,2)),SILVER,3.)
        if name=='zoom': p.line(((6,14),(14,14),(10,10),(10,18)),TEAL,1.4)
    elif name=='clear':
        p.line(((6,6),(18,18),(6,18),(18,6)),SILVER,1.8)
    elif name=='dropdown': p.polygon(((6,15),(18,15),(12,8)),SILVER)
    elif name in ('left','right'):
        points=((15,5),(8,12),(15,19)) if name=='left' else ((9,5),(16,12),(9,19))
        p.line(points,SILVER,1.9)
    elif name=='orbit':
        p.ellipse(12,12,10,5,TEAL,1.6,.1,5.8,28)
        p.ellipse(12,12,5,10,SILVER,1.4,.1,5.8,28)
        p.polygon(((21,9),(23,13),(18,12)),TEAL)
        p.disc(12,12,2,SILVER)
    elif name=='pan':
        p.polygon(((6,4),(3,11),(3,14),(5,15),(7,12),(7,20),(9,21),(10,15),
                   (10,22),(12,22),(13,15),(14,21),(16,21),(16,14),(18,18),
                   (20,17),(19,8),(16,3),(9,2)),SILVER)
        p.line(((8,8),(10,6),(15,6)),MUTED,1.)
    elif name=='walk':
        p.disc(13,20,2.6,SILVER)
        p.line(((12,16),(10,10),(15,7),(17,2)),SILVER,2.3)
        p.line(((10,10),(6,2)),SILVER,2.3)
        p.line(((11,14),(6,12),(3,15)),TEAL,1.7)
        p.line(((12,15),(16,12),(21,13)),TEAL,1.7)
    elif name=='home':
        p.polygon(((2,12),(12,22),(22,12)),SILVER)
        p.rect(5,3,14,10,SILVER)
        p.rect(10,3,5,7,MUTED)
    elif name in ('key','set_key','auto_key'):
        p.ellipse(7,15,4.8,4.8,GOLD if name!='auto_key' else RED,2.,steps=24)
        p.line(((10.5,11.5),(20.5,1.5)),GOLD if name!='auto_key' else RED,3.)
        p.line(((16,6),(18,8),(20,2),(22,4)),SILVER,2.)
        if name=='set_key': p.line(((17,20),(23,20),(20,17),(20,23)),TEAL,1.3)
        elif name=='auto_key': p.disc(19,19,3,RED,16)
    elif name in ('first','previous','play','stop','next','last'):
        if name=='stop': p.rect(5,5,14,14,SILVER)
        elif name=='play': p.polygon(((6,3),(21,12),(6,21)),SILVER)
        else:
            backward=name in ('first','previous')
            xf=lambda x:24-x if backward else x
            p.polygon(((xf(5),4),(xf(17),12),(xf(5),20)),SILVER)
            p.rect(3 if backward else 19,4,2,16,SILVER)
            if name in ('first','last'):
                p.polygon(((xf(1),6),(xf(9),12),(xf(1),18)),SILVER)
    elif name=='save':
        p.polygon(((3,2),(21,2),(21,18),(17,22),(3,22)),SILVER)
        p.rect(7,13,10,9,MUTED)
        p.rect(14,15,2,6,TEAL)
        p.rect(6,4,12,7,MUTED)
    elif name=='new':
        p.polygon(((5,2),(20,2),(20,17),(15,22),(5,22)),SILVER)
        p.line(((15,22),(15,17),(20,17)),MUTED,1.)
        p.line(((8,8),(17,8),(12.5,4),(12.5,12)),TEAL,1.3)
    elif name in ('import','export'):
        p.line(((3,3),(21,3),(21,15),(16,20),(3,20),(3,3)),SILVER,1.3)
        p.arrow((3,12),(17,12),TEAL,2.,5.) if name=='import' else p.arrow((8,12),(22,12),GOLD,2.,5.)
    elif name=='help':
        p.ellipse(12,12,10,10,SILVER,1.3,steps=30)
        p.line(((8,16),(8,18),(11,20),(15,19),(16,16),(14,13),(12,12),(12,9)),TEAL,1.8)
        p.disc(12,5.5,1.2,TEAL)
    elif name in ('vertex','edge','border','polygon','element'):
        p.cube(12,12,9,TEAL)
        if name=='vertex':
            for x,y in ((12,21),(4.35,16.32),(19.65,16.32),(12,12),(12,3),(4.35,7.32),(19.65,7.32)):
                p.rect(x-1.4,y-1.4,2.8,2.8,BRIGHT)
        elif name=='edge': p.line(((12,21),(19.65,16.32)),GOLD,2.6)
        elif name=='border': p.line(((12,21),(19.65,16.32),(12,12),(4.35,16.32),(12,21)),GOLD,2.1)
        elif name=='polygon': p.polygon(((12,21),(19.65,16.32),(12,12),(4.35,16.32)),GOLD)
        else: p.cube(12,12,8,GOLD,True)
    elif name=='filter':
        p.polygon(((2,21),(22,21),(14,12),(14,4),(10,2),(10,12)),SILVER)
        p.rect(4,18,16,2,TEAL)
    else:
        raise KeyError(name)
    return tuple(p.vertices),tuple(p.colors)


def geometry(name):
    """Return ``(positions, colors)``: matching tuples of triangle vertices."""
    if name not in ICON_NAMES:
        raise KeyError(name)
    if name not in _geometry:
        _geometry[name]=_make(name)
    return _geometry[name]


def draw(name, x, y, size, active=False, enabled=True):
    """Draw an original vector icon in region pixel coordinates.

    The caller owns clipping. This preserves the caller's GPU matrix and blend
    state. No draw handlers, timers, application data, or UI classes are added.
    """
    global _shader
    if size<=0:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    if _shader is None:
        _shader=gpu.shader.from_builtin('SMOOTH_COLOR')
    cache_key=(name,bool(enabled),bool(active))
    batch=_batches.get(cache_key)
    if batch is None:
        vertices,colors=geometry(name)
        if not enabled:
            colors=tuple((c[0]*.53,c[1]*.53,c[2]*.53,c[3]) for c in colors)
        if active:
            vertices=((0,0),(24,0),(24,24),(0,0),(24,24),(0,24))+vertices
            colors=((.28,.46,.64,1.),)*6+colors
        batch=batch_for_shader(_shader,'TRIS',{'pos':vertices,'color':colors})
        _batches[cache_key]=batch
    blend=gpu.state.blend_get()
    try:
        gpu.state.blend_set('ALPHA')
        with gpu.matrix.push_pop():
            gpu.matrix.translate((x,y,0.))
            gpu.matrix.scale((size/24.,size/24.,1.))
            _shader.bind()
            batch.draw(_shader)
    finally:
        gpu.state.blend_set(blend)


def clear():
    """Release cached GPU resources; safe without a graphics context."""
    global _shader
    _batches.clear()
    _shader=None
