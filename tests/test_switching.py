import unittest

class SwitchingTests(unittest.TestCase):
    def test_queued_workspace_routes(self):
        import ast
        from pathlib import Path
        from types import SimpleNamespace as N
        p=Path(__file__).resolve().parents[1]/'addon/blender_max_fusion/unified_controller.py'
        tree=ast.parse(p.read_text(encoding='utf-8'))
        class StripImports(ast.NodeTransformer):
            def visit_ImportFrom(self,node): return None
        names={'_remember_blender_workspaces','_restore_blender_workspaces','_queue_blender_restore','_sync_return_workspaces','set_mode'}
        nodes=[StripImports().visit(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        class WS(dict):
            def __init__(self,name,**kw): super().__init__(kw); self.name=name
            def __eq__(self,other): return self is other
            __hash__=object.__hash__
        class Window:
            def __init__(self,workspace): self.current=workspace; self.pending=None; self.screen=N(areas=[])
            @property
            def workspace(self): return self.current
            @workspace.setter
            def workspace(self,value): self.pending=value
            def tick(self):
                if self.pending is not None: self.current,self.pending=self.pending,None
            def as_pointer(self): return id(self)
        model,uv,maxws,mayaws=[WS('Modeling'),WS('UV Editing'),WS('Max',bsm_workspace=True),WS('Maya',maya=True)]
        w=Window(model); w2=Window(uv)
        windows=[w,w2]; state={'max':False,'maya':False}; timers=set(); calls=[]
        bpy=N(context=N(window_manager=N(windows=windows)),data=N(workspaces=[model,uv,maxws,mayaws]),app=N(timers=N(is_registered=lambda fn:fn in timers,register=lambda fn,**kw:timers.add(fn))))
        def max_set(on,layout=True):
            calls.append(('MAX',on,layout))
            state['max']=on
            if layout:
                for win in windows: win.workspace=maxws if on else uv # simulate wrong local fallback
        
        def maya_set(on,layout=True):
            calls.append(('MAYA',on,layout))
            state['maya']=on
            if layout:
                for win in windows: win.workspace=mayaws if on else uv
        ns=dict(bpy=bpy,_mode='BLENDER',_busy=False,_blender_workspaces={},_originals={'max_set':max_set,'maya_set':maya_set},runtime=N(_schedule_workspace_cleanup=lambda:None,_previous_workspace={},is_active=lambda:state['max']),_maya=N(switch=N(_delete_later=lambda *args:None,MASK_KEY='masks',PREV_KEY='prev',BLENDER_PREV_KEY='blender_prev',is_on=lambda:state['maya'],is_maya_workspace=lambda ws:ws.get('maya'))))
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(p),'exec'),ns)
        def settle():
            for _ in range(4):
                for win in windows: win.tick()
                ns['_restore_blender_workspaces']()
        for route in [('MAX','BLENDER'),('MAYA','BLENDER'),('MAX','MAYA','BLENDER'),('MAYA','MAX','BLENDER')]*5:
            for mode in route:
                ns['set_mode'](mode)
                # Deliberately acquire the next mode before the UI processes assignments.
            settle()
            assert w.workspace is model and w2.workspace is uv,route
            assert not ns['_blender_workspaces']
        # User chooses another Blender tab: the next round trip must remember the new choice.
        w.workspace=uv; w.tick()
        ns['set_mode']('MAX'); settle(); ns['set_mode']('BLENDER'); settle()
        assert w.workspace is uv
        print('PASS: 20 mixed mode round trips with queued activation, two independent windows, and manual Blender tab change')
        
        # Single-window handoff: Maya's mode-local return must never point at Max.
        windows.remove(w2)
        w.workspace=model; w.tick()
        ns['set_mode']('MAX'); w.tick()
        assert w.workspace is maxws
        mayaws['prev']=maxws.name  # what Maya observes before queued Max exit completes
        ns['set_mode']('MAYA')
        assert mayaws['prev']=='Modeling'
        w.tick()
        ns['set_mode']('BLENDER'); settle()
        assert w.workspace is model
        print('PASS: MAX -> MAYA rewrites its return destination from Max to Modeling before exit')
        
        for source,target in [('MAX','MAYA'),('MAYA','MAX')]:
            ns['set_mode'](source); settle()
            calls.clear()
            ns['set_mode'](target)
            assert (source,False,False) in calls,calls
            assert (target,True,True) in calls,calls
            assert not any(not on and layout for _,on,layout in calls),calls
            settle(); ns['set_mode']('BLENDER'); settle()
        print('PASS: both cross-mode handoffs skip intermediate Blender layout activation')
