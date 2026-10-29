# SPDX-License-Identifier: GPL-3.0-or-later
"""Scene Explorer table, backed by real objects, parents and collections."""
from dataclasses import dataclass, field

import bpy
from bpy.props import StringProperty

from . import runtime,surfaces

_states={}
_drag=None
TEXT=(.81,.81,.81,1)
DIM=(.58,.58,.58,1)
BG=(.265,.265,.265,1)
BLUE=(.27,.43,.61,1)
TYPES=(('MESH','Geometry','geometry'),('CURVE','Shapes','shapes'),
       ('LIGHT','Lights','lights'),('CAMERA','Cameras','cameras'),
       ('EMPTY','Helpers','helpers'),('ARMATURE','Bones','hierarchy'),
       ('OTHER','Other Objects','systems'))
COLUMNS=(('NAME','Name'),('TYPE','Type'),('LAYER','Layer'),
         ('FROZEN','Frozen'),('HIDDEN','Hidden'),('RENDERABLE','Renderable'))


@dataclass
class ViewState:
    search:str=''
    enabled:set=field(default_factory=lambda:{item[0] for item in TYPES})
    show_hidden:bool=True
    show_frozen:bool=True
    hierarchy:bool=True
    closed:set=field(default_factory=set)
    sort:str='NAME'
    descending:bool=False
    scroll:int=0
    anchor:object=None
    popup:str=''
    popup_x:float=0.
    popup_y:float=0.
    selection:set=field(default_factory=set)
    last_scene_selection:set=field(default_factory=set)


def state_for(area):
    return _states.setdefault(area.as_pointer(),ViewState())


def _kind(obj):
    return obj.type if obj.type in {item[0] for item in TYPES[:-1]} else 'OTHER'


def _layer(obj):
    return ', '.join(sorted(c.name for c in obj.users_collection))


def _hidden(obj,context):
    return obj.hide_get(view_layer=context.view_layer) or obj.hide_viewport


def _selection(context,state):
    """Explorer can retain frozen/hidden rows that Blender cannot viewport-select."""
    valid=set(context.view_layer.objects)
    actual={o for o in valid if o.select_get()}
    state.selection.intersection_update(valid)
    if actual!=state.last_scene_selection:
        state.selection={o for o in state.selection if o.hide_select or _hidden(o,context)}|actual
    state.last_scene_selection=actual
    return state.selection


def _apply_selection(context,state,members):
    state.selection=set(members)
    for obj in context.view_layer.objects:obj.select_set(obj in state.selection)
    state.last_scene_selection={o for o in context.view_layer.objects if o.select_get()}


def _sort_key(obj,state,context):
    value={'NAME':obj.name.casefold(),'TYPE':obj.type,'LAYER':_layer(obj).casefold(),
           'FROZEN':obj.hide_select,'HIDDEN':_hidden(obj,context),
           'RENDERABLE':not obj.hide_render}[state.sort]
    return value,obj.name.casefold()


def rows(context,state):
    """(object, depth, collection, matches_filter, expandable) table rows."""
    objects=list(context.view_layer.objects)
    all_set=set(objects);query=state.search.casefold().strip()
    allowed={o for o in objects if _kind(o) in state.enabled
             and (state.show_hidden or not _hidden(o,context))
             and (state.show_frozen or not o.hide_select)
             and (not query or query in o.name.casefold() or query in _layer(o).casefold())}
    ordered=lambda values:sorted(values,key=lambda o:_sort_key(o,state,context),reverse=state.descending)
    result=[]
    if state.hierarchy:
        included=set(allowed)
        for obj in tuple(allowed):
            parent=obj.parent
            while parent in all_set:
                included.add(parent);parent=parent.parent
        children={}
        for obj in included:
            children.setdefault(obj.parent if obj.parent in included else None,[]).append(obj)
        def walk(parent,depth):
            for obj in ordered(children.get(parent,())):
                members=children.get(obj,())
                result.append((obj,depth,None,obj in allowed,bool(members)))
                if obj.as_pointer() not in state.closed:
                    walk(obj,depth+1)
        walk(None,0)
    else:
        def walk_collection(collection,depth,ancestors):
            if collection in ancestors:return
            direct=ordered(o for o in collection.objects if o in allowed)
            nested=[]
            for child in collection.children:
                if any(o in allowed for o in child.all_objects):nested.append(child)
            if collection!=context.scene.collection:
                result.append((None,depth,collection,True,bool(direct or nested)))
                if collection.as_pointer() in state.closed:return
                depth+=1
            for child in sorted(nested,key=lambda c:c.name.casefold(),reverse=state.descending):
                walk_collection(child,depth,ancestors|{collection})
            for obj in direct:
                result.append((obj,depth,collection,True,False))
        walk_collection(context.scene.collection,0,set())
    return result


def select_row(context,state,index,ctrl=False,shift=False):
    table=rows(context,state)
    if not 0<=index<len(table):return
    obj=table[index][0]
    if obj is None:
        members=[o for o in table[index][2].all_objects if o.name in context.view_layer.objects]
    else:members=[obj]
    if shift and state.anchor:
        anchor=next((i for i,row in enumerate(table) if row[0]==state.anchor),index)
        members=[row[0] for row in table[min(anchor,index):max(anchor,index)+1] if row[0]]
    elif obj:
        state.anchor=obj
    # Clicking an already selected row preserves a multi-object selection.
    selection=set(_selection(context,state))
    preserve=obj is not None and obj in selection and not ctrl and not shift
    if not ctrl and not preserve:selection.clear()
    for member in members:
        if ctrl and not shift and member in selection:selection.remove(member)
        else:selection.add(member)
    _apply_selection(context,state,selection)
    active=next((o for o in reversed(members) if o in selection),None)
    if active:context.view_layer.objects.active=active
    runtime.redraw()


def toggle_property(context,source,prop):
    state=state_for(context.area);selection=set(_selection(context,state))
    targets=list(selection) if source in selection else [source]
    if prop=='FROZEN':value=not source.hide_select
    elif prop=='HIDDEN':value=not _hidden(source,context)
    else:value=source.hide_render  # Renderable is the inverse hide_render switch.
    count=0
    for obj in targets:
        if not obj.is_editable:continue
        if prop=='FROZEN':obj.hide_select=value
        elif prop=='HIDDEN':
            if not value:obj.hide_viewport=False
            obj.hide_set(value,view_layer=context.view_layer)
        elif prop=='RENDERABLE':obj.hide_render=not value
        count+=1
    _apply_selection(context,state,selection)
    runtime.redraw();_undo('Scene Explorer Property')
    return count


def reparent(context,objects,parent):
    """Link selected roots; reject every cyclic request before changing any object."""
    selected=set(objects)
    roots=[]
    for obj in objects:
        if not obj.is_editable:continue
        ancestor=obj.parent
        while ancestor is not None and ancestor not in selected:ancestor=ancestor.parent
        if ancestor is None:roots.append(obj)
    for obj in roots:
        ancestor=parent
        while ancestor is not None:
            if ancestor==obj:return False
            ancestor=ancestor.parent
    context.view_layer.update()
    saved=[(o,o.matrix_world.copy()) for o in roots]
    for obj,world in saved:
        obj.parent=parent
        if parent:obj.matrix_parent_inverse=parent.matrix_world.inverted_safe()
        else:obj.matrix_parent_inverse.identity()
        obj.matrix_world=world
    context.view_layer.update()
    runtime.redraw()
    if roots:_undo('Scene Explorer Link')
    return bool(roots)


def _undo(message):
    if not bpy.app.background:
        try:bpy.ops.ed.undo_push(message=message)
        except RuntimeError:pass


def _action(command,*values):return ('SCENE',command,*values)


def _columns(width):
    left=32.;available=max(330.,width-left-15)
    fixed=min(92.,available*.12)
    name=max(140.,available-fixed*3-available*.12-available*.23)
    widths=(name,available*.12,available*.23,fixed,fixed,fixed)
    result=[];x=left
    for (key,label),w in zip(COLUMNS,widths):
        result.append((key,label,x,w));x+=w
    return result


def _menu_items(name):
    return {
      'Select':[('Select All',_action('SELECT','ALL')),('Select None',_action('SELECT','NONE')),
                ('Invert Selection',_action('SELECT','INVERT')),('Select Children',_action('SELECT','CHILDREN')),
                ('Select Parents',_action('SELECT','PARENTS')),('Find Selected Object',_action('FIND'))],
      'Display':[('Display All Types',_action('TYPES','ALL')),('Display No Types',_action('TYPES','NONE')),
                 ('Invert Object Filters',_action('TYPES','INVERT')),('Show Hidden Objects',_action('SHOW_HIDDEN')),
                 ('Show Frozen Objects',_action('SHOW_FROZEN')),('Hide Selection',_action('BATCH','HIDDEN',True)),
                 ('Unhide All',_action('ALL','HIDDEN',False)),('Freeze Selection',_action('BATCH','FROZEN',True)),
                 ('Unfreeze All',_action('ALL','FROZEN',False))],
      'Edit':[('Rename...',surfaces.op('bsm.scene_rename')),('Delete Selection',_action('DELETE')),
              ('Unlink Selection',_action('UNPARENT')),('Undo',surfaces.op('ed.undo')),('Redo',surfaces.op('ed.redo'))],
      'Tools':[('Sort By Hierarchy',_action('HIERARCHY',True)),('Sort By Layer',_action('HIERARCHY',False)),
               ('Expand All',_action('EXPAND')),('Collapse All',_action('COLLAPSE')),
               ('Find Selected Object',_action('FIND'))],
    }.get(name,[])


def draw(context,kind='Scene'):
    c=surfaces.Canvas(context);state=state_for(context.area)
    selection=_selection(context,state)
    c.rect(0,0,c.w,c.h,BG)
    c.rect(0,c.h-26,c.w,26,(.20,.20,.20,1))
    c.icon('explorer',6,c.h-23,18);c.text('Scene Explorer',30,c.h-18,11)
    c.button(c.w-105,c.h-23,100,20,'Viewports',_action('RETURN'),flat=True)
    for i,name in enumerate(('Select','Display','Edit','Tools')):
        c.button(5+i*62,c.h-54,60,23,name,_action('MENU',name,5+i*62,c.h-55),selected=state.popup==name,flat=True)
    c.field(35,c.h-82,max(110.,min(350.,c.w-295)),state,'search',label='Search:')
    c.button(6,c.h-83,24,22,icon='search',action=surfaces.op('bsm.scene_search'),flat=True)
    x=min(392.,c.w-245)
    for i,(icon,command,selected) in enumerate((('hierarchy',_action('HIERARCHY',True),state.hierarchy),
            ('layer',_action('HIERARCHY',False),not state.hierarchy),('plus',_action('EXPAND'),False),
            ('minus',_action('COLLAPSE'),False),('selection',_action('FIND'),False),
            ('frozen',_action('SHOW_FROZEN'),state.show_frozen),('visible',_action('SHOW_HIDDEN'),state.show_hidden))):
        c.button(x+i*26,c.h-85,24,24,icon=icon,action=command,selected=selected,flat=True)
    # The vertical display toolbar follows the reference's compact type filters.
    c.rect(0,25,30,c.h-115,(.23,.23,.23,1))
    for i,(key,label,icon) in enumerate(TYPES):
        c.button(3,c.h-142-i*27,24,24,icon=icon,action=_action('TYPE',key),selected=key in state.enabled,flat=True)
    c.button(3,c.h-142-len(TYPES)*27-12,24,24,icon='filter',action=_action('TYPES','INVERT'),flat=True)
    columns=_columns(c.w)
    for key,label,x,w in columns:
        c.rect(x,c.h-115,w-1,23,(.315,.315,.315,1))
        suffix=(' ▼' if state.descending else ' ▲') if state.sort==key else ''
        c.text(label+suffix,x+6,c.h-108,9)
        c.hit(x,c.h-115,w-1,23,_action('SORT',key),label)
        c.line([(x,25),(x,c.h-115)],(.20,.20,.20,1))
    table=rows(context,state)
    visible_count=max(0,int((c.h-143)/22));state.scroll=min(state.scroll,max(0,len(table)-visible_count))
    for i,row in enumerate(table[state.scroll:state.scroll+visible_count]):
        obj,depth,collection,matches,expandable=row;y=c.h-140-i*22
        selected=obj in selection if obj else any(o in selection for o in collection.all_objects)
        if selected:c.rect(31,y-4,c.w-45,22,BLUE)
        elif i%2:c.rect(31,y-4,c.w-45,22,(.253,.253,.253,1))
        c.hit(32,y-4,c.w-47,22,_action('ROW',i+state.scroll),'Select '+(obj.name if obj else collection.name))
        label=obj.name if obj else collection.name
        indent=depth*15
        if expandable:
            pointer=obj.as_pointer() if obj else collection.as_pointer()
            c.text('▸' if pointer in state.closed else '▾',36+indent,y+1,10,DIM)
            c.hit(32+indent,y-3,17,21,_action('EXPAND_ROW',pointer),'Expand '+label)
        icon=dict((key,glyph) for key,_,glyph in TYPES).get(_kind(obj),'systems') if obj else 'layer'
        c.icon(icon,52+indent,y-1,16)
        name_width=columns[0][3]-indent-42
        c.text(label[:max(4,int(name_width/5.8))],73+indent,y+2,9,TEXT if matches else DIM)
        if obj:
            values={'TYPE':obj.type.title(),'LAYER':_layer(obj),
                    'FROZEN':'■' if obj.hide_select else '□',
                    'HIDDEN':'●' if _hidden(obj,context) else '○',
                    'RENDERABLE':'●' if not obj.hide_render else '○'}
            for key,title,x,w in columns[1:]:
                value=values[key]
                c.text(value[:max(3,int((w-10)/5.7))],x+7,y+2,9,TEXT if matches else DIM)
                if key in {'FROZEN','HIDDEN','RENDERABLE'} and obj.is_editable:
                    c.hit(x,y-4,w-1,22,_action('PROPERTY',obj,key),title)
    c.rect(0,0,c.w,24,(.23,.23,.23,1))
    selected=len(selection)
    c.text(f'{len(table)} Entries    {selected} Selected',7,8,9,DIM)
    c.text('Ctrl: add/remove    Shift: range    Drag name: link to parent',max(300,c.w-415),8,8,DIM)
    # Functional scrollbar; no cosmetic controls with disconnected state.
    if len(table)>visible_count and visible_count:
        top=c.h-118;track=top-27;thumb=max(20.,track*visible_count/len(table))
        sy=top-thumb-(track-thumb)*state.scroll/max(1,len(table)-visible_count)
        c.rect(c.w-12,27,10,track,(.20,.20,.20,1));c.rect(c.w-11,sy,8,thumb,(.43,.43,.43,1))
        c.hit(c.w-15,27,15,track,_action('SCROLLBAR'),'Scroll Objects')
    if _drag and _drag.get('state') is state and _drag.get('moving'):
        target=_drag.get('target')
        c.text('Link to '+(target.name if target else 'scene root')+'  —  Esc cancels',35,32,10,(.70,.83,.93,1))
    if state.popup:
        items=_menu_items(state.popup)
        x=min(state.popup_x,c.w-235);top=min(state.popup_y,c.h-55)
        c.rect(x-1,top-len(items)*23-2,234,len(items)*23+4,(.13,.13,.13,1))
        for i,(label,action) in enumerate(items):
            c.button(x,top-(i+1)*23,232,23,label,action,flat=True)


def dispatch(context,action):
    state=state_for(context.area);command=action[1];args=action[2:]
    selection=set(_selection(context,state))
    if command!='MENU':state.popup=''
    if command=='MENU':
        name,x,y=args;state.popup='' if state.popup==name else name;state.popup_x=x;state.popup_y=y
    elif command=='RETURN':
        primary=next((w for w in bpy.data.workspaces if w.get('bsm_primary_workspace')),None)
        if primary:context.window.workspace=primary
    elif command=='SORT':
        state.descending=not state.descending if state.sort==args[0] else False;state.sort=args[0]
    elif command=='HIERARCHY':state.hierarchy=args[0];state.scroll=0
    elif command=='TYPE':
        key=args[0];state.enabled.remove(key) if key in state.enabled else state.enabled.add(key);state.scroll=0
    elif command=='TYPES':
        all_types={item[0] for item in TYPES}
        state.enabled=all_types-state.enabled if args[0]=='INVERT' else all_types if args[0]=='ALL' else set();state.scroll=0
    elif command=='SHOW_HIDDEN':state.show_hidden=not state.show_hidden
    elif command=='SHOW_FROZEN':state.show_frozen=not state.show_frozen
    elif command=='EXPAND':state.closed.clear()
    elif command=='COLLAPSE':
        state.closed={o.as_pointer() for o in context.view_layer.objects}|{c.as_pointer() for c in bpy.data.collections}
    elif command=='EXPAND_ROW':
        key=args[0];state.closed.remove(key) if key in state.closed else state.closed.add(key)
    elif command=='PROPERTY':toggle_property(context,args[0],args[1])
    elif command in {'BATCH','ALL'}:
        prop,value=args
        for obj in context.view_layer.objects:
            if not obj.is_editable or command=='BATCH' and obj not in selection:continue
            if prop=='FROZEN':obj.hide_select=value
            elif prop=='HIDDEN':
                if not value:obj.hide_viewport=False
                obj.hide_set(value,view_layer=context.view_layer)
        _apply_selection(context,state,selection)
        _undo('Scene Explorer Display')
    elif command=='SELECT':
        mode=args[0]
        current=list(selection)
        if mode in {'ALL','NONE','INVERT'}:
            for row in rows(context,state):
                if row[0] and row[3]:
                    if mode=='NONE' or mode=='INVERT' and row[0] in selection:selection.discard(row[0])
                    else:selection.add(row[0])
        elif mode=='CHILDREN':
            for obj in current:
                for child in obj.children_recursive:
                    if child.name in context.view_layer.objects:selection.add(child)
        elif mode=='PARENTS':
            for obj in current:
                if obj.parent and obj.parent.name in context.view_layer.objects:selection.add(obj.parent)
        _apply_selection(context,state,selection)
    elif command=='FIND':
        state.search='';state.closed.clear()
        table=rows(context,state)
        state.scroll=next((i for i,row in enumerate(table) if row[0] in selection),0)
    elif command=='UNPARENT':reparent(context,list(selection),None)
    elif command=='DELETE':
        for obj in list(context.view_layer.objects):
            if obj in selection and obj.is_editable:bpy.data.objects.remove(obj,do_unlink=True)
        state.selection.clear();state.last_scene_selection.clear();state.anchor=None;_undo('Delete Objects')
    elif command=='ROW':select_row(context,state,args[0])
    runtime.redraw();return {'FINISHED'}


def _row_at(context,state,region,y):
    if y>region.height/surfaces.scale()-122 or y<25:return None
    index=int((region.height/surfaces.scale()-122-y)/22)+state.scroll
    table=rows(context,state)
    return table[index][0] if 0<=index<len(table) else None


def active_event(context,event):
    global _drag
    d=_drag
    if d is None or context.window.as_pointer()!=d['window']:return None
    u=surfaces.scale();region=d['region'];state=d['state']
    x=(event.mouse_x-region.x)/u;y=(event.mouse_y-region.y)/u
    if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':
        _drag=None;runtime.redraw();return {'RUNNING_MODAL'}
    if event.type=='LEFTMOUSE' and event.value=='RELEASE':
        if d['kind']=='PARENT' and d['moving']:
            target=_row_at(context,state,region,y)
            if 32<=x<region.width/u-15:reparent(context,d['objects'],target)
        _drag=None;runtime.redraw();return {'RUNNING_MODAL'}
    if event.type=='MOUSEMOVE':
        if d['kind']=='SCROLL':
            visible=max(1,int((region.height/u-143)/22));count=len(rows(context,state))
            factor=max(0.,min(1.,(region.height/u-118-y)/max(1.,region.height/u-145)))
            state.scroll=round(max(0,count-visible)*factor)
        else:
            d['moving']=d['moving'] or abs(x-d['x'])+abs(y-d['y'])>5
            d['target']=_row_at(context,state,region,y)
        runtime.redraw()
    return {'RUNNING_MODAL'}


def handle_event(context,event,area,region,x,y):
    global _drag
    state=state_for(area)
    if event.type=='MOUSEMOVE':return None
    if event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
        state.scroll=max(0,state.scroll+(3 if event.type=='WHEELDOWNMOUSE' else -3));runtime.redraw();return {'RUNNING_MODAL'}
    if event.type=='LEFTMOUSE' and event.value=='DOUBLE_CLICK':
        hit=surfaces.lookup(area,x,y)
        if hit and hit[4][:2]==('SCENE','ROW'):
            with context.temp_override(area=area,region=region):return bpy.ops.bsm.scene_rename('INVOKE_DEFAULT')
    if event.value!='PRESS':return None
    if event.type=='F2':return bpy.ops.bsm.scene_rename('INVOKE_DEFAULT')
    if event.type=='A' and event.ctrl:dispatch(context,_action('SELECT','ALL'));return {'RUNNING_MODAL'}
    if event.type=='DEL':dispatch(context,_action('DELETE'));return {'RUNNING_MODAL'}
    if event.type=='RIGHTMOUSE':
        state.popup='Edit';state.popup_x=x;state.popup_y=y;runtime.redraw();return {'RUNNING_MODAL'}
    if event.type!='LEFTMOUSE':return None
    hit=surfaces.lookup(area,x,y)
    if not hit:
        if state.popup:state.popup='';runtime.redraw();return {'RUNNING_MODAL'}
        return None
    action=hit[4]
    if action[0]!='SCENE':return None
    command=action[1]
    if command=='ROW':
        index=action[2]
        select_row(context,state,index,event.ctrl,event.shift)
        table=rows(context,state);obj=table[index][0] if index<len(table) else None
        if obj and state.hierarchy and not event.ctrl and not event.shift:
            _drag=dict(window=context.window.as_pointer(),area=area,region=region,state=state,x=x,y=y,
                       kind='PARENT',moving=False,target=None,
                       objects=list(_selection(context,state)))
        return {'RUNNING_MODAL'}
    if command=='SCROLLBAR':
        _drag=dict(window=context.window.as_pointer(),area=area,region=region,state=state,
                   kind='SCROLL',x=x,y=y,moving=True)
        return active_event(context,event)
    with context.temp_override(area=area,region=region):dispatch(context,action)
    return {'RUNNING_MODAL'}


class BSM_OT_scene_search(bpy.types.Operator):
    bl_idname='bsm.scene_search'
    bl_label='Search Scene Explorer'
    text:StringProperty(name='Name or Layer')
    def invoke(self,context,event):
        self.text=state_for(context.area).search
        return context.window_manager.invoke_props_dialog(self,width=320)
    def draw(self,context):self.layout.prop(self,'text')
    def execute(self,context):
        state=state_for(context.area);state.search=self.text;state.scroll=0
        runtime.redraw();return {'FINISHED'}


class BSM_OT_scene_rename(bpy.types.Operator):
    bl_idname='bsm.scene_rename'
    bl_label='Rename Object'
    bl_options={'REGISTER','UNDO'}
    object_name:StringProperty(options={'HIDDEN'})
    name:StringProperty(name='Name')
    def invoke(self,context,event):
        obj=context.view_layer.objects.active
        if not obj or not obj.is_editable:
            self.report({'WARNING'},'Select an editable object');return {'CANCELLED'}
        self.object_name=obj.name;self.name=obj.name
        return context.window_manager.invoke_props_dialog(self,width=330)
    def draw(self,context):self.layout.prop(self,'name')
    def execute(self,context):
        obj=context.view_layer.objects.get(self.object_name)
        if not obj or not obj.is_editable:return {'CANCELLED'}
        obj.name=self.name.strip() or obj.name
        runtime.redraw();return {'FINISHED'}


def clear():
    global _drag
    _drag=None;_states.clear()


CLASSES=(BSM_OT_scene_search,BSM_OT_scene_rename)
