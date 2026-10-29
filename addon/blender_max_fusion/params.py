# SPDX-License-Identifier: GPL-3.0-or-later
"""Parametric 3ds Max-style primitives: unscaled objects whose parameters rebuild their own mesh."""
from math import asin, atan2, cos, hypot, pi, radians, sin, sqrt
import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Matrix

KINDS=('BOX','CONE','SPHERE','GEOSPHERE','CYLINDER','TUBE','TORUS','PYRAMID','TEAPOT','PLANE')
NAMES=dict(zip(KINDS,('Box','Cone','Sphere','GeoSphere','Cylinder','Tube','Torus','Pyramid','Teapot','Plane')))
_EPS=1e-9
_busy=set()


def _update(self,context):
    obj=self.id_data
    if isinstance(obj,bpy.types.Object):
        build(obj)


def _dist(name,default=1.0,**kw):
    return FloatProperty(name=name,default=default,subtype='DISTANCE',unit='LENGTH',step=1,precision=3,update=_update,**kw)
def _deg(name):
    return FloatProperty(name=name,default=0.0,step=100,precision=1,update=_update)
def _int(name,default,low,high=200):
    return IntProperty(name=name,default=default,min=low,max=high,update=_update)
def _bool(name,default=False):
    return BoolProperty(name=name,default=default,update=_update)


class BSM_PrimitiveParams(bpy.types.PropertyGroup):
    kind: StringProperty(name='Primitive',default='')
    length: _dist('Length')
    width: _dist('Width')
    height: _dist('Height')
    depth: _dist('Depth')
    radius: _dist('Radius',0.5,min=0.0)
    radius1: _dist('Radius 1',0.5,min=0.0)
    radius2: _dist('Radius 2',0.2,min=0.0)
    length_segs: _int('Length Segs',1,1)
    width_segs: _int('Width Segs',1,1)
    height_segs: _int('Height Segs',1,1)
    depth_segs: _int('Depth Segs',1,1)
    cap_segs: _int('Cap Segments',1,1)
    sides: _int('Sides',18,3)
    segments: _int('Segments',4,1)
    sphere_segments: _int('Segments',32,4)
    torus_segments: _int('Segments',24,3)
    smooth: _bool('Smooth',True)
    smooth_mode: EnumProperty(name='Smooth',default='ALL',update=_update,items=(
        ('ALL','All','Smooth the whole torus'),('SIDES','Sides','Smooth bands running around the torus'),
        ('NONE','None','Faceted torus'),('SEGMENTS','Segments','Smooth each segment as a ring')))
    hemisphere: FloatProperty(name='Hemisphere',default=0.0,min=0.0,max=1.0,step=1,precision=2,update=_update)
    squash: _bool('Squash')
    hemi: _bool('Hemisphere')
    base_type: EnumProperty(name='Geodesic Base Type',default='ICOSA',update=_update,items=(
        ('TETRA','Tetra','Tetrahedron base'),('OCTA','Octa','Octahedron base'),('ICOSA','Icosa','Icosahedron base')))
    slice_on: _bool('Slice On')
    slice_from: _deg('Slice From')
    slice_to: _deg('Slice To')
    rotation: _deg('Rotation')
    twist: _deg('Twist')
    base_to_pivot: _bool('Base To Pivot')
    body: _bool('Body',True)
    handle: _bool('Handle',True)
    spout: _bool('Spout',True)
    lid: _bool('Lid',True)
    gen_uv: _bool('Generate Mapping Coords.',True)
    real_world: _bool('Real-World Map Size')


CLASSES=(BSM_PrimitiveParams,)


def register():
    if not getattr(BSM_PrimitiveParams,'is_registered',False):
        bpy.utils.register_class(BSM_PrimitiveParams)
    bpy.types.Object.bsm_prim=PointerProperty(type=BSM_PrimitiveParams)


def unregister():
    if hasattr(bpy.types.Object,'bsm_prim'):
        del bpy.types.Object.bsm_prim
    if getattr(BSM_PrimitiveParams,'is_registered',False):
        bpy.utils.unregister_class(BSM_PrimitiveParams)


_SLICE=[('slice_on','Slice On'),('slice_from','Slice From:'),('slice_to','Slice To:')]
_MAP=[('gen_uv','Generate Mapping Coords.'),('real_world','Real-World Map Size')]
_ROUND=[('height_segs','Height Segments:'),('cap_segs','Cap Segments:'),('sides','Sides:'),('smooth','Smooth')]
PARAMETERS={
    'BOX':[('length','Length:'),('width','Width:'),('height','Height:'),('length_segs','Length Segs:'),
           ('width_segs','Width Segs:'),('height_segs','Height Segs:')]+_MAP,
    'CONE':[('radius1','Radius 1:'),('radius2','Radius 2:'),('height','Height:')]+_ROUND+_SLICE+_MAP,
    'SPHERE':[('radius','Radius:'),('sphere_segments','Segments:'),('smooth','Smooth'),('hemisphere','Hemisphere:'),
              ('squash','Squash')]+_SLICE+[('base_to_pivot','Base To Pivot')]+_MAP,
    'GEOSPHERE':[('radius','Radius:'),('segments','Segments:'),('base_type','Geodesic Base Type'),('smooth','Smooth'),
                 ('hemi','Hemisphere'),('base_to_pivot','Base to Pivot')]+_MAP,
    'CYLINDER':[('radius','Radius:'),('height','Height:')]+_ROUND+_SLICE+_MAP,
    'TUBE':[('radius1','Radius 1:'),('radius2','Radius 2:'),('height','Height:')]+_ROUND+_SLICE+_MAP,
    'TORUS':[('radius1','Radius 1:'),('radius2','Radius 2:'),('rotation','Rotation:'),('twist','Twist:'),
             ('torus_segments','Segments:'),('sides','Sides:'),('smooth_mode','Smooth')]+_SLICE+_MAP,
    'PYRAMID':[('width','Width:'),('depth','Depth:'),('height','Height:'),('width_segs','Width Segs:'),
               ('depth_segs','Depth Segs:'),('height_segs','Height Segs:')]+_MAP,
    'TEAPOT':[('radius','Radius:'),('segments','Segments:'),('smooth','Smooth'),('body','Body'),('handle','Handle'),
              ('spout','Spout'),('lid','Lid')]+_MAP,
    'PLANE':[('length','Length:'),('width','Width:'),('length_segs','Length Segs:'),('width_segs','Width Segs:')]+_MAP,
}
KEYBOARD={
    'BOX':[('length','Length:'),('width','Width:'),('height','Height:')],
    'CONE':[('radius1','Radius 1:'),('radius2','Radius 2:'),('height','Height:')],
    'SPHERE':[('radius','Radius:')],
    'GEOSPHERE':[('radius','Radius:')],
    'CYLINDER':[('radius','Radius:'),('height','Height:')],
    'TUBE':[('radius1','Inner Radius:'),('radius2','Outer Radius:'),('height','Height:')],
    'TORUS':[('radius1','Major Radius:'),('radius2','Minor Radius:')],
    'PYRAMID':[('width','Width:'),('depth','Depth:'),('height','Height:')],
    'TEAPOT':[('radius','Radius:')],
    'PLANE':[('length','Length:'),('width','Width:')],
}
CREATION_METHODS={k:list(v) for k,v in {
    'BOX':(('CUBE','Cube'),('BOX','Box')),'GEOSPHERE':(('DIAMETER','Diameter'),('CENTER','Center')),
    'PYRAMID':(('BASE_APEX','Base/Apex'),('CENTER','Center')),'PLANE':(('RECTANGLE','Rectangle'),('SQUARE','Square')),
    **{k:(('EDGE','Edge'),('CENTER','Center')) for k in ('CONE','SPHERE','CYLINDER','TUBE','TORUS','TEAPOT')}}.items()}
_NOSLICE=dict(slice_on=False,slice_from=0.0,slice_to=0.0)
DEFAULTS={k:{**v,'gen_uv':True,'real_world':False} for k,v in {
    'BOX':dict(length=1.0,width=1.0,height=1.0,length_segs=1,width_segs=1,height_segs=1),
    'CONE':dict(radius1=0.5,radius2=0.0,height=1.0,height_segs=5,cap_segs=1,sides=24,smooth=True,**_NOSLICE),
    'SPHERE':dict(radius=0.5,sphere_segments=32,smooth=True,hemisphere=0.0,squash=False,base_to_pivot=False,**_NOSLICE),
    'GEOSPHERE':dict(radius=0.5,segments=4,base_type='ICOSA',smooth=True,hemi=False,base_to_pivot=False),
    'CYLINDER':dict(radius=0.5,height=1.0,height_segs=5,cap_segs=1,sides=18,smooth=True,**_NOSLICE),
    'TUBE':dict(radius1=0.5,radius2=0.4,height=1.0,height_segs=5,cap_segs=1,sides=18,smooth=True,**_NOSLICE),
    'TORUS':dict(radius1=0.5,radius2=0.2,rotation=0.0,twist=0.0,torus_segments=24,sides=12,smooth_mode='ALL',**_NOSLICE),
    'PYRAMID':dict(width=1.0,depth=1.0,height=1.0,width_segs=1,depth_segs=1,height_segs=1),
    'TEAPOT':dict(radius=0.5,segments=4,smooth=True,body=True,handle=True,spout=True,lid=True),
    'PLANE':dict(length=1.0,width=1.0,length_segs=4,width_segs=4),
}.items()}


class _Mesh:
    def __init__(self,real):
        self.co=[];self.faces=[];self.hard=set();self.real=real;self.flip=False
    def v(self,x,y,z):
        self.co.append((x,y,z));return len(self.co)-1
    def f(self,idx,uvs,group,su=1.0,sv=1.0):
        if self.real: uvs=[(u*su,v*sv) for u,v in uvs]
        self.faces.append((idx,uvs,group))


def _grid(m,at,nu,nv,group,su=1.0,sv=1.0,vs=None,uv=None):
    """Quads (a,b)->(a+1,b)->(a+1,b+1)->(a,b+1); the normal is dir(a) x dir(b)."""
    if nu<1 or nv<1: return
    vs=vs or [b/nv for b in range(nv+1)]
    for a in range(nu):
        for b in range(nv):
            q=((a,b),(a+1,b),(a+1,b+1),(a,b+1))
            idx=[at(*c) for c in q]
            m.f(idx,[uv(m.co[i]) for i in idx] if uv else [(c[0]/nu,vs[c[1]]) for c in q],group,su,sv)


def _arc(p,n):
    if p.slice_on:
        # 3ds Max keeps the part running counter-clockwise from Slice To to Slice From.
        span=radians(p.slice_from-p.slice_to)%(2*pi)
        if 1e-6<span<2*pi-1e-6:
            a0=radians(p.slice_to)
            return [a0+span*i/n for i in range(n+1)],span,False
    return [2*pi*i/n for i in range(n)],2*pi,True


def _ring(m,ang,r,z):
    if abs(r)<_EPS:
        return [m.v(0.0,0.0,z)]*len(ang)
    return [m.v(r*cos(a),r*sin(a),z) for a in ang]


def _cap(m,rings,top,full,center,R,group,close=True):
    """Flat cap from concentric rings ordered outer to inner, facing +Z when top."""
    L=len(rings[0]);n=L if full else L-1;R=R or 1.0
    uv=lambda c:(0.5+(c[0] if top else -c[0])/(2*R),0.5+c[1]/(2*R))
    rs=rings if top else rings[::-1]
    _grid(m,lambda a,b:rs[b][a%L],n,len(rs)-1,group,2*R,2*R,uv=uv)
    if close:
        idx=rings[-1][:n] if full else [center]+rings[-1]
        if not top: idx=idx[::-1]
        m.f(idx,[uv(m.co[i]) for i in idx],group,2*R,2*R)


def _slice(m,start,end,R,z0,z1,ga,gb):
    """Planar slice faces from vertex grids [row bottom->top][column axis->rim]."""
    T,C=len(start)-1,len(start[0])-1;R=R or 1.0;hz=(z1-z0) or 1.0
    _grid(m,lambda a,b:start[b][a],C,T,ga,R,abs(hz),uv=lambda c:(hypot(c[0],c[1])/R,(c[2]-z0)/hz))
    _grid(m,lambda a,b:end[b][C-a],C,T,gb,R,abs(hz),uv=lambda c:(1-hypot(c[0],c[1])/R,(c[2]-z0)/hz))


def _box(m,p):
    w,l,h=p.width,p.length,p.height;n=(p.width_segs,p.length_segs,p.height_segs);size=(w,l,h)
    m.flip=w*l*h<0
    ids={}
    def vert(c):
        if c not in ids: ids[c]=m.v(-w/2+c[0]/n[0]*w,-l/2+c[1]/n[1]*l,c[2]/n[2]*h)
        return ids[c]
    W,L,H=n
    sides=(((0,0,H),0,1,1,1),((W,0,0),0,-1,1,1),((0,0,0),0,1,2,1),((W,L,0),0,-1,2,1),((W,0,0),1,1,2,1),((0,L,0),1,-1,2,1))
    for g,(o,ua,ud,va,vd) in enumerate(sides,1):
        def at(a,b):
            c=list(o);c[ua]+=ud*a;c[va]+=vd*b
            return vert(tuple(c))
        _grid(m,at,n[ua],n[va],g,abs(size[ua]),abs(size[va]))


def _plane(m,p):
    w,l,W,L=p.width,p.length,p.width_segs,p.length_segs
    m.flip=w*l<0
    ids=[[m.v(-w/2+a/W*w,-l/2+b/L*l,0.0) for b in range(L+1)] for a in range(W+1)]
    _grid(m,lambda a,b:ids[a][b],W,L,1,abs(w),abs(l))


def _pyramid(m,p):
    w,d,h=p.width,p.depth,p.height;W,D,H=p.width_segs,p.depth_segs,p.height_segs
    m.flip=w*d*h<0
    ids={}
    def v(t,i,j):
        k=(H,) if t==H else (t,i,j)
        if k not in ids:
            s=1-t/H;ids[k]=m.v((-w/2+i/W*w)*s,(-d/2+j/D*d)*s,t/H*h)
        return ids[k]
    fy,fx=hypot(h,d/2),hypot(h,w/2)
    _grid(m,lambda a,b:v(0,W-a,b),W,D,1,abs(w),abs(d))
    _grid(m,lambda a,b:v(b,a,0),W,H,2,abs(w),fy)
    _grid(m,lambda a,b:v(b,W,a),D,H,3,abs(d),fx)
    _grid(m,lambda a,b:v(b,W-a,D),W,H,4,abs(w),fy)
    _grid(m,lambda a,b:v(b,0,D-a),D,H,5,abs(d),fx)


def _cone(m,p,r1,r2):
    h,H,C,n=p.height,p.height_segs,p.cap_segs,p.sides
    m.flip=h<0
    ang,span,full=_arc(p,n);L=len(ang)
    rad=lambda t:r1+(r2-r1)*t/H
    side=[_ring(m,ang,rad(t),h*t/H) for t in range(H+1)]
    _grid(m,lambda a,b:side[b][a%L],n,H,1 if p.smooth else 0,span*max(r1,r2),hypot(r1-r2,h))
    axis=None if full else [side[t][0] if rad(t)<_EPS else m.v(0.0,0.0,h*t/H) for t in range(H+1)]
    caps={}
    for t,r,g,top in ((0,r1,3,False),(H,r2,2,True)):
        if r<_EPS: continue
        caps[t]=[side[t]]+[_ring(m,ang,r*c/C,h*t/H) for c in range(C-1,0,-1)]
        _cap(m,caps[t],top,full,None if full else axis[t],r,g)
    if full: return
    def grid(k):
        rows=[]
        for t in range(H+1):
            row=[axis[t]]
            for c in range(1,C):
                rr=rad(t)*c/C
                row.append(caps[t][C-c][k] if t in caps else axis[t] if rr<_EPS else m.v(rr*cos(ang[k]),rr*sin(ang[k]),h*t/H))
            rows.append(row+[side[t][k]])
        return rows
    _slice(m,grid(0),grid(L-1),max(r1,r2),0.0,h,4,5)


def _tube(m,p):
    h,H,C,n=p.height,p.height_segs,p.cap_segs,p.sides
    ro,ri=max(p.radius1,p.radius2),min(p.radius1,p.radius2)
    m.flip=h<0
    ang,span,full=_arc(p,n);L=len(ang)
    so=[_ring(m,ang,ro,h*t/H) for t in range(H+1)]
    si=[_ring(m,ang,ri,h*t/H) for t in range(H+1)]
    _grid(m,lambda a,b:so[b][a%L],n,H,1 if p.smooth else 0,span*ro,abs(h))
    _grid(m,lambda a,b:si[b][(n-a)%L],n,H,2 if p.smooth else 0,span*ri,abs(h))
    caps={}
    for t,g,top in ((0,4,False),(H,3,True)):
        caps[t]=[so[t]]+[_ring(m,ang,ri+(ro-ri)*c/C,h*t/H) for c in range(C-1,0,-1)]+[si[t]]
        _cap(m,caps[t],top,full,None,ro,g,close=False)
    if full: return
    def grid(k):
        return [[caps[t][C-c][k] if t in caps else si[t][k] if c==0 else so[t][k] if c==C else
                 m.v((ri+(ro-ri)*c/C)*cos(ang[k]),(ri+(ro-ri)*c/C)*sin(ang[k]),h*t/H) for c in range(C+1)] for t in range(H+1)]
    _slice(m,grid(0),grid(L-1),ro,0.0,h,5,6)


def _sphere(m,p):
    r,n=p.radius,p.sphere_segments
    bands=max(2,n//2)
    top=pi*(1.0-min(max(p.hemisphere,0.0),1.0))
    if top<1e-6: return
    if p.squash: phis=[top*k/bands for k in range(bands+1)]
    else: phis=[pi*k/bands for k in range(bands) if pi*k/bands<top-1e-6]+[top]
    phis.reverse()
    zoff=-r*cos(top) if p.base_to_pivot else 0.0
    ang,span,full=_arc(p,n);L=len(ang)
    rows=[_ring(m,ang,r*sin(f),r*cos(f)+zoff) for f in phis]
    K=len(rows)-1
    _grid(m,lambda a,b:rows[b][a%L],n,K,1 if p.smooth else 0,span*r,top*r,vs=[1-f/top for f in phis])
    axis=None if full else [row[0] if row[0]==row[1] else m.v(0.0,0.0,m.co[row[0]][2]) for row in rows]
    if top<pi-1e-6:
        _cap(m,[rows[0]],False,full,None if full else axis[0],r*sin(top),2)
    if not full:
        _slice(m,[[axis[b],rows[b][0]] for b in range(K+1)],[[axis[b],rows[b][-1]] for b in range(K+1)],
               r,zoff+r*cos(top),zoff+r,3,4)


def _bases():
    s5=1/sqrt(5);t=sqrt(8)/3
    ico=[(0,0,1)]+[(2*s5*cos(k*pi*2/5+o),2*s5*sin(k*pi*2/5+o),z) for o,z in ((0,s5),(pi/5,-s5)) for k in range(5)]+[(0,0,-1)]
    faces=[]
    for k in range(5):
        u0,u1,l0,l1=1+k,1+(k+1)%5,6+k,6+(k+1)%5
        faces+=[(0,u0,u1),(u0,l0,u1),(u1,l0,l1),(11,l1,l0)]
    return {'ICOSA':(ico,faces),
            'OCTA':([(1,0,0),(0,1,0),(-1,0,0),(0,-1,0),(0,0,1),(0,0,-1)],
                    [(0,1,4),(1,2,4),(2,3,4),(3,0,4),(1,0,5),(2,1,5),(3,2,5),(0,3,5)]),
            'TETRA':([(0,0,1)]+[(t*cos(k*pi*2/3),t*sin(k*pi*2/3),-1/3) for k in range(3)],
                     [(0,1,2),(0,2,3),(0,3,1),(1,3,2)])}
_BASES=_bases()


def _sphere_uv(pts):
    us=[atan2(y,x)/(2*pi)%1.0 if x*x+y*y>1e-12 else None for x,y,z in pts]
    known=[u for u in us if u is not None]
    if known and max(known)-min(known)>0.5:
        us=[u if u is None or u>=0.5 else u+1 for u in us];known=[u for u in us if u is not None]
    mid=sum(known)/len(known) if known else 0.5
    return [(mid if u is None else u,0.5+asin(max(-1.0,min(1.0,z/(sqrt(x*x+y*y+z*z) or 1))))/pi) for u,(x,y,z) in zip(us,pts)]


def _geosphere(m,p):
    r,f=p.radius,p.segments
    V,F=_BASES[p.base_type]
    pos={}
    def key(weights):
        k=tuple(sorted(x for x in weights if x[1]))
        if k not in pos:
            x,y,z=(sum(V[i][a]*w for i,w in k) for a in range(3));l=sqrt(x*x+y*y+z*z)
            pos[k]=(x/l,y/l,z/l)
        return k
    polys=[]
    for a,b,c in F:
        P=lambda i,j:key(((a,f-i-j),(b,i),(c,j)))
        for i in range(f):
            for j in range(f-i):
                polys.append((P(i,j),P(i+1,j),P(i,j+1)))
                if i+j<f-1: polys.append((P(i+1,j),P(i+1,j+1),P(i,j+1)))
    if p.hemi:
        def cut(a,b):
            k=('cut',)+tuple(sorted((a,b)))
            if k not in pos:
                (x0,y0,z0),(x1,y1,z1)=pos[a],pos[b];t=z0/(z0-z1)
                pos[k]=(x0+(x1-x0)*t,y0+(y1-y0)*t,0.0)
            return k
        kept=[]
        for poly in polys:
            out=[]
            for i in range(len(poly)):
                a,b=poly[i-1],poly[i];za,zb=pos[a][2],pos[b][2]
                if zb>=-_EPS:
                    if za<-_EPS and zb>_EPS: out.append(cut(a,b))
                    out.append(b)
                elif za>_EPS: out.append(cut(a,b))
            if len(out)>=3: kept.append(out)
        polys=kept
    zoff=-min((pos[k][2] for poly in polys for k in poly),default=0.0)*r if p.base_to_pivot else 0.0
    ids={}
    def vid(k):
        if k not in ids: x,y,z=pos[k];ids[k]=m.v(x*r,y*r,z*r+zoff)
        return ids[k]
    g=1 if p.smooth else 0
    for poly in polys:
        m.f([vid(k) for k in poly],_sphere_uv([pos[k] for k in poly]),g,2*pi*r,pi*r)
    if p.hemi:
        rim=sorted({k for poly in polys for k in poly if abs(pos[k][2])<=_EPS},key=lambda k:-atan2(pos[k][1],pos[k][0]))
        if len(rim)>=3:
            m.f([vid(k) for k in rim],[(0.5-pos[k][0]/2,0.5+pos[k][1]/2) for k in rim],2,2*r,2*r)


def _torus(m,p):
    R,r,n,s=p.radius1,p.radius2,p.torus_segments,p.sides
    ang,span,full=_arc(p,n);L=len(ang)
    rot,tw=radians(p.rotation),radians(p.twist)
    psi=lambda i,j:rot+tw*i/n+2*pi*j/s
    rings=[[m.v((R+r*cos(psi(i,j)))*cos(t),(R+r*cos(psi(i,j)))*sin(t),r*sin(psi(i,j))) for j in range(s)]
           for i,t in enumerate(ang)]
    # A full twisted torus closes onto the nearest matching side of the first section.
    shift=round(tw*s/(2*pi)) if full else 0
    at=lambda a,b:rings[0][(b+shift)%s] if a==L else rings[a][b%s]
    mode=p.smooth_mode
    _grid(m,at,n,s,0 if mode=='NONE' else 1,span*R,2*pi*r)
    if mode=='SIDES': m.hard.update(frozenset((at(a,b),at(a+1,b))) for a in range(n) for b in range(s))
    if mode=='SEGMENTS': m.hard.update(frozenset((at(a,b),at(a,b+1))) for a in range(L) for b in range(s))
    if not full:
        for i,end,g in ((0,False,2),(L-1,True,3)):
            js=list(range(s))[::-1] if end else range(s)
            m.f([rings[i][j] for j in js],[(0.5+(-0.5 if end else 0.5)*cos(psi(i,j)),0.5+0.5*sin(psi(i,j))) for j in js],g,2*r,2*r)


# Martin Newell's 1975 Utah teapot (public domain Bezier patch data), stored compactly:
# rotational parts are (radius, z) cubic segments swept by the patches' cubic quarter circle,
# handle and spout rows are (x_a, z_a, x_b, z_b, half width) of patches mirrored across XZ.
_TP_QUARTER=((1,0),(1,0.56),(0.56,1),(0,1))
_TP_BODY=(((0,0),(1.425,0),(1.5,0.075),(1.5,0.15)),((1.5,0.15),(1.5,0.225),(2,0.45),(2,0.9)),
          ((2,0.9),(2,1.35),(1.75,1.875),(1.5,2.4)),((1.5,2.4),(1.4375,2.53125),(1.3375,2.53125),(1.4,2.4)))
_TP_LID=(((1.3,2.4),(1.3,2.55),(0.4,2.55),(0.2,2.7)),((0.2,2.7),(0,2.85),(0.8,3.15),(0,3.15)))
_TP_HANDLE=((-1.6,2.025,-1.5,2.25,0.3),(-2.3,2.025,-2.5,2.25,0.3),(-2.7,2.025,-3,2.25,0.3),(-2.7,1.8,-3,1.8,0.3),
            (-2.7,1.575,-3,1.35,0.3),(-2.5,1.125,-2.65,0.9375,0.3),(-2,0.9,-1.9,0.6,0.3))
_TP_SPOUT=((1.7,1.425,1.7,0.6,0.66),(2.6,1.425,3.1,0.825,0.66),(2.3,2.1,2.4,2.025,0.25),(2.7,2.4,3.3,2.4,0.25),
           (2.8,2.475,3.525,2.49375,0.25),(2.9,2.475,3.45,2.5125,0.15),(2.8,2.4,3.2,2.4,0.15))


def _bern(t):
    s=1-t
    return (s*s*s,3*t*s*s,3*t*t*s,t*t*t)


def _bez(ctrl,t):
    w=_bern(t)
    return tuple(sum(a*c[k] for a,c in zip(w,ctrl)) for k in range(len(ctrl[0])))


def _teapot(m,p):
    sc,s=p.radius/2,min(p.segments,64)
    ring=[]
    for b in range(4*s):
        q,t=divmod(b,s);x,y=_bez(_TP_QUARTER,t/s);c,sn=((1,0),(0,1),(-1,0),(0,-1))[q]
        ring.append((x*c-y*sn,x*sn+y*c))
    N=len(ring)
    def lathe(segs,g):
        prof=[_bez(seg,i/s) for k,seg in enumerate(segs) for i in range(1 if k else 0,s+1)]
        rows=[[m.v(0.0,0.0,z*sc)]*N if r<_EPS else [m.v(r*x*sc,r*y*sc,z*sc) for x,y in ring] for r,z in prof]
        arc=sum(hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(prof,prof[1:]))
        _grid(m,lambda a,b:rows[b][a%N],N,len(prof)-1,g,2*pi*max(r for r,z in prof)*sc,arc*sc)
    def tube(spec,g):
        net=[((xa,0,za),(xa,-w,za),(xb,-w,zb),(xb,0,zb),(xb,w,zb),(xa,w,za),(xa,0,za)) for xa,za,xb,zb,w in spec]
        def ev(a,b):
            i0,j0=min(a//s,1),min(b//s,1);wu,wv=_bern(a/s-i0),_bern(b/s-j0)
            return tuple(sc*sum(wu[i]*wv[j]*net[3*i0+i][3*j0+j][k] for i in range(4) for j in range(4)) for k in range(3))
        P=[[ev(a,b) for b in range(2*s)] for a in range(2*s+1)]
        mid=[sum(c[k] for c in P[s])/(2*s) for k in range(3)]
        o,du,dv=P[s][s//2],P[s+1][s//2],P[s][s//2+1]
        e1,e2,out=[du[k]-o[k] for k in range(3)],[dv[k]-o[k] for k in range(3)],[o[k]-mid[k] for k in range(3)]
        nrm=(e1[1]*e2[2]-e1[2]*e2[1],e1[2]*e2[0]-e1[0]*e2[2],e1[0]*e2[1]-e1[1]*e2[0])
        sign=-1 if sum(a*b for a,b in zip(nrm,out))<0 else 1
        ids=[[m.v(*c) for c in row] for row in P]
        dist=lambda a,b:sqrt(sum((a[k]-b[k])**2 for k in range(3)))
        su=sum(dist(P[a][0],P[a+1][0]) for a in range(2*s));sv=sum(dist(P[s][b-1],P[s][b]) for b in range(2*s))
        _grid(m,lambda a,b:ids[a][(sign*b)%(2*s)],2*s,2*s,g,su,sv)
    smooth=p.smooth
    if p.body: lathe(_TP_BODY,1 if smooth else 0)
    if p.handle: tube(_TP_HANDLE,2 if smooth else 0)
    if p.spout: tube(_TP_SPOUT,3 if smooth else 0)
    if p.lid: lathe(_TP_LID,4 if smooth else 0)


_BUILDERS={'BOX':_box,'PLANE':_plane,'PYRAMID':_pyramid,'SPHERE':_sphere,'GEOSPHERE':_geosphere,'TUBE':_tube,
           'TORUS':_torus,'TEAPOT':_teapot,'CONE':lambda m,p:_cone(m,p,p.radius1,p.radius2),
           'CYLINDER':lambda m,p:_cone(m,p,p.radius,p.radius)}


def _commit(mesh,m,gen_uv):
    bm=bmesh.new()
    vs=[bm.verts.new(c) for c in m.co]
    uvl=bm.loops.layers.uv.new('UVMap') if gen_uv else None
    gl=bm.faces.layers.int.new('bsm_group')
    for idx,uvs,group in m.faces:
        ids,cs=[],[]
        for i,uv in zip(idx,uvs):
            if ids and ids[-1]==i: cs[-1].append(uv)
            else: ids.append(i);cs.append([uv])
        if len(ids)>1 and ids[0]==ids[-1]: ids.pop();cs[0]+=cs.pop()
        if len(ids)<3 or len(set(ids))<len(ids): continue
        if m.flip: ids.reverse();cs.reverse()
        try: face=bm.faces.new([vs[i] for i in ids])
        except ValueError: continue
        face.smooth=group!=0;face[gl]=group
        if uvl:
            for loop,c in zip(face.loops,cs): loop[uvl].uv=(sum(u for u,_ in c)/len(c),sum(v for _,v in c)/len(c))
    for e in bm.edges:
        lf=e.link_faces
        if len(lf)==2: e.smooth=lf[0][gl]==lf[1][gl]!=0
    for a,b in (tuple(h) for h in m.hard if len(h)==2):
        e=bm.edges.get((vs[a],vs[b]))
        if e: e.smooth=False
    loose=[v for v in bm.verts if not v.link_faces]
    if loose: bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.faces.layers.int.remove(gl)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def is_parametric(obj):
    p=getattr(obj,'bsm_prim',None) if obj is not None else None
    return bool(p is not None and obj.type=='MESH' and p.kind in _BUILDERS)


def label(obj):
    return NAMES[obj.bsm_prim.kind] if is_parametric(obj) else ''


def collapse(obj):
    if is_parametric(obj): obj.bsm_prim.kind=''


def build(obj):
    if not is_parametric(obj) or obj.mode=='EDIT' or obj.data.is_editmode: return
    key=obj.as_pointer()
    if key in _busy: return
    _busy.add(key)
    try:
        p=obj.bsm_prim;m=_Mesh(p.real_world)
        _BUILDERS[p.kind](m,p)
        _commit(obj.data,m,p.gen_uv)
    finally:
        _busy.discard(key)


def new_object(context,kind,matrix=None,**values):
    base=NAMES[kind];n=1
    while f'{base}{n:03d}' in bpy.data.objects or f'{base}{n:03d}' in bpy.data.meshes: n+=1
    name=f'{base}{n:03d}'
    obj=bpy.data.objects.new(name,bpy.data.meshes.new(name))
    (context.collection or context.scene.collection).objects.link(obj)
    for o in context.view_layer.objects:
        if o is not None and o.select_get(): o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active=obj
    if matrix is not None:
        loc,rot,_=Matrix(matrix).decompose()
        obj.matrix_world=Matrix.LocRotScale(loc,rot,None)
    key=obj.as_pointer();_busy.add(key)
    try:
        p=obj.bsm_prim
        for attr,value in {**DEFAULTS[kind],**values}.items(): setattr(p,attr,value)
        p.kind=kind
    finally:
        _busy.discard(key)
    build(obj)
    return obj
