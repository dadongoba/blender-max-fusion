# SPDX-License-Identifier: GPL-3.0-or-later
"""Environment lifecycle. No third-party add-ons are inspected or modified."""
import json
import os
from pathlib import Path
import bpy
from bpy.app.handlers import persistent

_active = False
_pending = None
_previous_workspace = {}
_patched = []
_patched_polls = []
_saved_lock_state = []
_saved_orientation = {}
_msgbus_owner = object()
WORKSPACE_NAME = 'Blender Max'
OLD_WORKSPACE_NAMES = ('Blender Studio Max',)  # files saved before the rename
_splash_before = []  # the variable's value before Max mode replaced the splash
SPLASH_ENV = 'BLENDER_CUSTOM_SPLASH'  # read by Blender each time it builds the splash


def preferences():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def is_active():
    return _active


def apply_splash(on):
    """While Max mode is on, Blender's splash shows the image chosen in the preferences."""
    prefs = preferences()
    path = os.path.abspath(bpy.path.abspath(prefs.splash_image)) if prefs and prefs.splash_image else ''
    if on and path and os.path.isfile(path):
        if not _splash_before:
            _splash_before.append(os.environ.get(SPLASH_ENV))
        os.environ[SPLASH_ENV] = path
    elif _splash_before:
        previous = _splash_before.pop()
        if previous is None:
            os.environ.pop(SPLASH_ENV, None)
        else:
            os.environ[SPLASH_ENV] = previous


def in_workspace(context):
    return _active and context.workspace and context.workspace.get('bsm_workspace', False)


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def _hex(value, alpha=None):
    color = tuple(int(value[i:i+2], 16)/255 for i in (0, 2, 4))
    return color+(alpha,) if alpha is not None else color


def _theme_paths():
    """Colours from 3ds Max 2027 DefaultUI.clrx (dark theme)."""
    paths = {
        'properties.space.back': (.267, .267, .267),
        'properties.space.header': (.267, .267, .267, 1),
        'image_editor.space.back': (.267, .267, .267),
        'image_editor.space.header': (.29, .29, .29, 1),
        'dopesheet_editor.space.back': (.23, .23, .23),
        'dopesheet_editor.space.header': (.267, .267, .267, 1),
        'topbar.space.header': (.25, .25, .25, 1),
        'statusbar.space.back': (.267, .267, .267),
        'view_3d.space.gradients.background_type': 'SINGLE_COLOR',
        'view_3d.space.gradients.high_gradient': _hex('383838'),
        'view_3d.space.gradients.gradient': _hex('1a1a1a'),
        'view_3d.grid': (.29, .29, .29, 1),
        'view_3d.object_selected': _hex('00b2ff'),
        'view_3d.object_active': _hex('66d1ff'),
        'view_3d.vertex_select': _hex('d00000'),
        'view_3d.edge_select': _hex('d00000'),
        'view_3d.edge_mode_select': _hex('d00000'),
        'view_3d.face_select': _hex('d00000', .18),
        'view_3d.face_mode_select': _hex('d00000', .18),
        'view_3d.wire_edit': (0, 0, 0),
        'view_3d.editmesh_active': (1, 1, 1, .5),
    }
    for widget in ('regular', 'tool', 'toolbar_item', 'radio', 'text', 'option',
                   'toggle', 'num', 'numslider', 'box', 'menu', 'pulldown',
                   'menu_back', 'menu_item', 'list_item', 'tab'):
        prefix = f'user_interface.wcol_{widget}'
        paths[f'{prefix}.inner'] = (0.35, 0.35, 0.35, 1.0)
        paths[f'{prefix}.inner_sel'] = _hex('5f8ac1', 1.)
        paths[f'{prefix}.text'] = _hex('dcdcdc')
        paths[f'{prefix}.text_sel'] = (1.0, 1.0, 1.0)
        paths[f'{prefix}.outline'] = (0.10, 0.10, 0.10, 1.0)
        paths[f'{prefix}.roundness'] = 0.12
    paths['user_interface.wcol_box.inner'] = (.28, .28, .28, 1)
    paths['user_interface.wcol_menu_item.inner_sel'] = _hex('3c82dc', 1.)
    return paths


def _theme_property(path):
    value = bpy.context.preferences.themes[0]
    parts = path.split('.')
    for part in parts[:-1]:
        value = getattr(value, part)
    return value, parts[-1]


def _plain(value):
    return value if isinstance(value, (str, int, float, bool)) else list(value)


def apply_theme():
    prefs = preferences()
    if not prefs or not prefs.studio_colors:
        return
    # Persist a small recovery snapshot alongside this extension's preferences.
    if not prefs.theme_backup:
        backup = {}
        for path in _theme_paths():
            try:
                owner, attr = _theme_property(path)
                backup[path] = _plain(getattr(owner, attr))
            except (AttributeError, TypeError):
                continue
        prefs.theme_backup = json.dumps(backup)
    for path, value in _theme_paths().items():
        try:
            owner, attr = _theme_property(path)
            setattr(owner, attr, value)
        except (AttributeError, TypeError, ValueError):
            continue


def restore_theme():
    prefs = preferences()
    if not prefs or not prefs.theme_backup:
        return
    try:
        backup = json.loads(prefs.theme_backup)
        for path, value in backup.items():
            try:
                owner, attr = _theme_property(path)
                setattr(owner, attr, value)
            except (AttributeError, TypeError, ValueError):
                continue
    except (TypeError, ValueError):
        print('Blender Max: invalid theme recovery data; snapshot retained')
        return
    prefs.theme_backup = ''


def _patch_draw(cls, replacement):
    original = cls.draw

    def draw(self, context):
        if in_workspace(context):
            replacement(self, context)
        else:
            original(self, context)
    _patched.append((cls, original, draw))
    cls.draw = draw


def _install_draws():
    from . import ui, chrome
    _patch_draw(bpy.types.VIEW3D_HT_header, ui.draw_view_header)
    _patch_draw(bpy.types.TOPBAR_MT_editor_menus, ui.draw_menus)
    _patch_draw(bpy.types.DOPESHEET_HT_header, ui.draw_time_header)
    from ._maya.ui import own_draw
    own_draw.swap("TOPBAR_HT_upper_bar", chrome.draw_topbar)
    _patch_draw(bpy.types.IMAGE_HT_header, chrome.draw_image_header)
    _patch_draw(bpy.types.PROPERTIES_HT_header, chrome.draw_properties_header)
    _patch_draw(bpy.types.STATUSBAR_HT_header, chrome.draw_status)
    # Hide native active-tool/workspace panels only in our dedicated Command Panel.
    for name in ('VIEW3D_PT_tools_active', 'PROPERTIES_PT_navigation_bar',
                 'WORKSPACE_PT_main', 'WORKSPACE_PT_addons'):
        cls = getattr(bpy.types, name, None)
        if cls and hasattr(cls, 'draw'):
            _patch_draw(cls, lambda self, context: None)
    # The Properties editor's Tool page is assembled from 3D-view panels by C
    # code. Use the universally available Scene page for our command panel.
    # Suppress native Scene panels only inside the primary studio workspace.
    from bl_ui import properties_scene
    panels = [cls for cls in properties_scene.classes
              if issubclass(cls, bpy.types.Panel) and getattr(bpy.types, cls.__name__, None) is cls]
    # Blender caches whether a class has a poll callback at registration time.
    # Re-register in dependency order so the scoped poll is actually honored.
    for cls in panels:
        own = cls.__dict__.get('poll')
        original = getattr(cls, 'poll', None)

        def make_poll(original_poll):
            # RNA callbacks require the exact (cls, context) signature.
            def poll(panel_cls, context):
                if in_workspace(context) and context.workspace.get('bsm_primary_workspace'):
                    return False
                return original_poll(context) if original_poll else True
            return poll
        replacement = classmethod(make_poll(original))
        _patched_polls.append((cls, own, replacement))
    # Record the entire restoration transaction before unregistering anything.
    for cls in reversed(panels):
        bpy.utils.unregister_class(cls)
    for cls, own, replacement in _patched_polls:
        cls.poll = replacement
        bpy.utils.register_class(cls)


def _restore_draws():
    from ._maya.ui import own_draw
    from . import chrome
    own_draw.restore("TOPBAR_HT_upper_bar", chrome.draw_topbar)
    for cls, original, ours in reversed(_patched_polls):
        if getattr(bpy.types, cls.__name__, None) is cls:
            bpy.utils.unregister_class(cls)
    for cls, original, ours in _patched_polls:
        if cls.__dict__.get('poll') is ours:
            if original is None:
                delattr(cls, 'poll')
            else:
                cls.poll = original
        if getattr(bpy.types, cls.__name__, None) is not cls:
            bpy.utils.register_class(cls)
    _patched_polls.clear()
    for cls, original, ours in reversed(_patched):
        if cls.draw is ours:
            cls.draw = original
    _patched.clear()


# Reference coordinate system: Max "View" is World in perspective/user views and
# screen-aligned in Top/Front/Left; the other choices map onto Blender orientations.
REFERENCE = {'SCREEN': 'VIEW', 'WORLD': 'GLOBAL', 'PARENT': 'PARENT', 'LOCAL': 'LOCAL', 'GIMBAL': 'GIMBAL',
             'GRID': 'GLOBAL', 'WORKING': 'CURSOR', 'LOCAL_ALIGNED': 'NORMAL'}


def sync_reference(context, region=None):
    if not _active or not hasattr(context.window_manager, 'bsm'):
        return
    state = context.window_manager.bsm
    slot = context.scene.transform_orientation_slots[0]
    choice = state.ref_coord
    if choice == 'VIEW':
        r3d = region.data if region is not None and region.type == 'WINDOW' else None
        if r3d is None:
            try:
                from .operators import viewport_override
                r3d = viewport_override(context)['region'].data
            except (RuntimeError, AttributeError):
                return
        if r3d is None:
            return
        from .operators import view_name
        side = r3d.view_perspective == 'ORTHO' and view_name(r3d) in {'Top', 'Bottom', 'Front', 'Back', 'Left', 'Right'}
        target = 'VIEW' if side else 'GLOBAL'
    elif choice == 'PICK':
        obj = bpy.data.objects.get(state.ref_pick)
        if obj is None:
            return
        name = f'Pick: {obj.name}'
        if slot.type != name:
            existing = context.scene.transform_orientation_slots[0]
            try:
                existing.type = name
            except TypeError:
                from .operators import viewport_override
                override = viewport_override(context)
                active = context.view_layer.objects.active
                with context.temp_override(**override, active_object=obj, object=obj):
                    bpy.ops.transform.create_orientation(name=name, use=True, overwrite=True)
                context.view_layer.objects.active = active
        return
    else:
        target = REFERENCE.get(choice, 'GLOBAL')
    if slot.type != target:
        slot.type = target


def apply_selection_filter(context):
    state = context.window_manager.bsm
    allowed = {'ALL': None, 'GEOMETRY': {'mesh', 'surf', 'meta', 'font', 'curves', 'pointcloud', 'volume'}, 'SHAPES': {'curve', 'font'},
               'LIGHTS': {'light'}, 'CAMERAS': {'camera'}, 'HELPERS': {'empty'}, 'WARPS': {'empty'}, 'BONE': {'armature'}}[state.selection_filter]
    for space in _studio_spaces(context):
        for prop in space.bl_rna.properties:
            name = prop.identifier
            if name.startswith('show_object_select_'):
                setattr(space, name, allowed is None or name[len('show_object_select_'):] in allowed)


def apply_manipulate(context):
    on = context.window_manager.bsm.manipulate
    for space in _studio_spaces(context):
        for attr in ('show_gizmo_light_size', 'show_gizmo_light_look_at', 'show_gizmo_camera_lens', 'show_gizmo_camera_dof_distance',
                     'show_gizmo_empty_image', 'show_gizmo_empty_force_field'):
            if hasattr(space, attr):
                setattr(space, attr, on)


def _studio_spaces(context):
    for workspace in bpy.data.workspaces:
        if not workspace.get('bsm_primary_workspace'):
            continue
        for screen in workspace.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    yield area.spaces.active


def on_state(context, name):
    if name == 'keyboard_override':
        from . import keymap
        keymap.set_enabled(context.window_manager.bsm.keyboard_override)
    elif name == 'manipulate':
        apply_manipulate(context)
    elif name == 'selection_filter':
        apply_selection_filter(context)
    elif name == 'ref_coord':
        sync_reference(context)
    elif name == 'set_key_mode' and context.window_manager.bsm.set_key_mode:
        context.scene.tool_settings.use_keyframe_insert_auto = False  # Max: Auto Key and Set Key exclude each other
    redraw()


def _object_mode_changed():
    """Entering Edit Mode on a primitive converts it to Editable Poly, as Max requires."""
    context = bpy.context
    obj = context.view_layer.objects.active if context.view_layer else None
    if not _active or obj is None or obj.mode != 'EDIT' or obj.type != 'MESH':
        if obj is not None and obj.mode == 'OBJECT' and hasattr(context.window_manager, 'bsm'):
            context.window_manager.bsm.component = 0
        return
    prim = getattr(obj, 'bsm_prim', None)
    if prim is not None and prim.kind:
        from . import params
        params.collapse(obj)
        context.window_manager.bsm.prompt = f'{obj.name} converted to Editable Poly'
    level = {(True, False, False): 1, (False, True, False): 2, (False, False, True): 4}.get(tuple(context.tool_settings.mesh_select_mode))
    state = context.window_manager.bsm
    if state.component == 0 and level:
        state.component = level
    redraw()


def _active_changed():
    if not _active:
        return
    from .commands import promote_groups
    try:
        promote_groups(bpy.context)
    except (AttributeError, ReferenceError):
        pass


def subscribe():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    bpy.msgbus.subscribe_rna(key=(bpy.types.Object, 'mode'), owner=_msgbus_owner, args=(), notify=_object_mode_changed)
    bpy.msgbus.subscribe_rna(key=(bpy.types.LayerObjects, 'active'), owner=_msgbus_owner, args=(), notify=_active_changed)


def unsubscribe():
    bpy.msgbus.clear_by_owner(_msgbus_owner)


# Blender 5.0 factory startup objects: type, location, rotation.
FACTORY_OBJECTS = {
    'Cube': ('MESH', (0, 0, 0), (0, 0, 0)),
    'Camera': ('CAMERA', (7.358891, -6.925791, 4.958309), (1.109319, 0, .814928)),
    'Light': ('LIGHT', (4.076245, 1.005454, 5.903862), (.650328, .055217, 1.866391)),
}


def _close(values, expected):
    return all(abs(a-b) < 1e-4 for a, b in zip(values, expected))


def _factory_objects(scene):
    """Blender's untouched startup Cube, Camera and Light, or None if the scene differs.

    bpy.data.is_dirty is already set on startup (even in a factory process), so the
    objects themselves are compared with the factory values instead."""
    objects = {o.name: o for o in scene.objects}
    if set(objects) != set(FACTORY_OBJECTS):
        return None
    for name, (kind, location, rotation) in FACTORY_OBJECTS.items():
        obj = objects[name]
        if (obj.type != kind or obj.parent or obj.modifiers or obj.constraints or obj.animation_data
                or obj.rotation_mode != 'XYZ' or not _close(obj.scale, (1, 1, 1))
                or not _close(obj.location, location) or not _close(obj.rotation_euler, rotation)):
            return None
    cube, camera, light = objects['Cube'].data, objects['Camera'].data, objects['Light'].data
    if len(cube.vertices) != 8 or any(not _close(map(abs, v.co), (1, 1, 1)) for v in cube.vertices):
        return None
    if camera.type != 'PERSP' or abs(camera.lens-50) > 1e-4:
        return None
    if light.type != 'POINT' or abs(light.energy-1000) > 1e-3 or not _close(light.color, (1, 1, 1)):
        return None
    return list(objects.values())


def clear_factory_scene(scene):
    """Max opens on an empty scene: remove the startup Cube, Camera and Light and their data."""
    objects = _factory_objects(scene)
    if not objects:
        return False
    for obj in objects:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            for collection in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights):
                if data.name in collection and collection[data.name] == data:
                    collection.remove(data)
                    break
    material = bpy.data.materials.get('Material')
    if material is not None and material.users == 0:
        bpy.data.materials.remove(material)
    return True


def apply_scene_defaults(context):
    """A brand-new, untouched scene starts like Max: empty, frames 0-100 at 30 fps (NTSC)."""
    scene = context.scene
    if bpy.data.filepath or bpy.data.actions or scene.get('bsm_defaults_applied'):
        return
    scene['bsm_defaults_applied'] = True
    if (scene.frame_start, scene.frame_end, scene.render.fps) == (1, 250, 24):
        scene.frame_start, scene.frame_end, scene.frame_current = 0, 100, 0
        scene.render.fps, scene.render.fps_base = 30, 1
    # Interactive sessions only: scripts and render farms keep the scene they load.
    if not bpy.app.background:
        clear_factory_scene(scene)


def enter_workspace(window):
    if window and (window.workspace.get('bsm_editor_kind') or window.workspace.get('bsm_native_kind')):
        if window.workspace.get('bsm_editor_kind'):
            from . import editor_host
            editor_host.prepare(window)
        return
    if not window or (window.workspace.get('bsm_workspace') and window.workspace.get('bsm_layout_version', 0) >= 2):
        if window:
            from . import chrome
            chrome.prepare_workspace(window)
        return
    _previous_workspace[window.as_pointer()] = window.workspace.name
    target = next((w for w in bpy.data.workspaces if w.get('bsm_primary_workspace') and w.get('bsm_layout_version', 0) >= 2), None)
    if target is None:
        before = set(bpy.data.workspaces)
        with bpy.context.temp_override(window=window):
            bpy.ops.workspace.append_activate(idname='BSM_Layout', filepath=str(Path(__file__).with_name('workspace.blend')))
        target = next((w for w in bpy.data.workspaces if w not in before and w.name.startswith('BSM_Layout')), None)
        if target is None:
            raise RuntimeError('The Blender Max workspace could not be appended')
        target.name = WORKSPACE_NAME
        target['bsm_workspace'] = True
        target['bsm_primary_workspace'] = True
    window.workspace = target
    attempts = [0]

    def prepare():
        attempts[0] += 1
        if not _active or attempts[0] > 40:
            return None
        if window.workspace != target or window.screen not in list(target.screens):
            return .05
        from . import chrome
        chrome.prepare_workspace(window)
        return None
    bpy.app.timers.register(prepare, first_interval=.01)


def leave_workspace(window):
    if not window or not window.workspace.get('bsm_workspace'):
        return
    previous = _previous_workspace.get(window.as_pointer(), '')
    target = bpy.data.workspaces.get(previous)
    if not target or target.get('bsm_workspace'):
        target = bpy.data.workspaces.get('Layout') or next((w for w in bpy.data.workspaces if not w.get('bsm_workspace')), None)
    if target:
        window.workspace = target
    else:
        with bpy.context.temp_override(window=window):
            bpy.ops.workspace.append_activate(idname='Layout', filepath='<startup.blend>')



def _cleanup_max_workspaces():
    """Remove the temporary Max tab only after all windows have left it."""
    if _active:
        return None
    occupied = {window.workspace for window in bpy.context.window_manager.windows}
    unused = [workspace for workspace in bpy.data.workspaces
              if workspace.get('bsm_primary_workspace') and workspace not in occupied]
    if unused:
        bpy.data.batch_remove(ids=unused)
    _previous_workspace.clear()
    return None


def _schedule_workspace_cleanup():
    # Workspace activation finishes at the next event-loop update. Deleting its
    # screen in the switching callback can leave a window with stale UI data.
    if not bpy.app.timers.is_registered(_cleanup_max_workspaces):
        bpy.app.timers.register(_cleanup_max_workspaces, first_interval=0.1)


def _remember_orientation():
    _saved_orientation.clear()
    for scene in bpy.data.scenes:
        _saved_orientation[scene.name] = (scene.transform_orientation_slots[0].type, scene.tool_settings.transform_pivot_point)


def _restore_orientation():
    for name, (orientation, pivot) in _saved_orientation.items():
        scene = bpy.data.scenes.get(name)
        if scene is None:
            continue
        try:
            scene.transform_orientation_slots[0].type = orientation
        except TypeError:
            scene.transform_orientation_slots[0].type = 'GLOBAL'
    _saved_orientation.clear()


def set_active(on, layout=True):
    global _active
    on = bool(on)
    if on == _active:
        if on and layout and not bpy.app.background:
            from . import chrome
            for window in bpy.context.window_manager.windows:
                enter_workspace(window)
            chrome.register_mode()
        return
    from . import keymap, chrome
    prefs = preferences()
    if on:
        _active = True
        try:
            _install_draws()
            keymap.register_mode()
            apply_theme()
            _remember_orientation()
            subscribe()
            apply_scene_defaults(bpy.context)
            if layout:
                for window in bpy.context.window_manager.windows:
                    enter_workspace(window)
            chrome.register_mode()
            if hasattr(bpy.context.window_manager, 'bsm'):
                keymap.set_enabled(bpy.context.window_manager.bsm.keyboard_override)
                sync_reference(bpy.context)
            apply_splash(True)
        except Exception:
            chrome.unregister_mode()
            keymap.unregister_mode()
            unsubscribe()
            _restore_draws()
            restore_theme()
            apply_splash(False)
            _active = False
            raise
    else:
        chrome.unregister_mode()
        keymap.unregister_mode()
        unsubscribe()
        _restore_draws()
        restore_theme()
        _restore_orientation()
        apply_splash(False)
        _active = False
        if not bpy.app.background:
            from . import max_gizmo, commands
            max_gizmo.restore_blender_tools(bpy.context)
            # Blender's viewports get back the guides that ActiveShade hid.
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D' and area.spaces.active.as_pointer() in commands._activeshade:
                        commands.set_activeshade(area.spaces.active, False)
        if layout:
            for window in bpy.context.window_manager.windows:
                leave_workspace(window)
            _schedule_workspace_cleanup()
        # A lock is temporary interaction state, never a saved restriction.
        recover_selection_lock()
    if prefs:
        prefs.enabled_mode = on
    redraw()


def _apply_pending():
    global _pending
    on = _pending
    _pending = None
    if on is not None:
        try:
            set_active(on)
        except Exception as error:
            print('Blender Max switch failed:', error)
            import traceback
            traceback.print_exc()
    return None


def request(on):
    global _pending
    _pending = bool(on)
    if not bpy.app.timers.is_registered(_apply_pending):
        bpy.app.timers.register(_apply_pending, first_interval=0.01)


@persistent
def load_post(_):
    # Blender unloads add-on fonts when it opens a file: without this every Max label,
    # field and menu drawn by the extension went blank in the loaded scene.
    from .surfaces import reset_fonts
    from .commands import _activeshade
    from .operators import _quad_memory
    reset_fonts()
    _activeshade.clear()  # the loaded file has its own viewports
    _quad_memory.clear()
    recover_selection_lock()
    # The keymaps remain registered across file loads; enter a workspace in the new file.
    if _active:
        subscribe()

        def activate():
            if _active and not bpy.app.background:
                from . import chrome
                chrome.restart_events()
                apply_scene_defaults(bpy.context)
                for window in bpy.context.window_manager.windows:
                    enter_workspace(window)
                chrome.register_mode()
            elif _active:
                apply_scene_defaults(bpy.context)
            return None
        bpy.app.timers.register(activate, first_interval=0.25)


def recover_selection_lock():
    if not hasattr(bpy.data, 'objects'):
        return
    for obj in bpy.data.objects:
        if '_bsm_selectable_before_lock' in obj:
            obj.hide_select = bool(obj['_bsm_selectable_before_lock'])
            del obj['_bsm_selectable_before_lock']
    if hasattr(bpy.context, 'window_manager') and hasattr(bpy.context.window_manager, 'bsm'):
        bpy.context.window_manager.bsm.selection_locked = False


@persistent
def save_pre(_):
    _saved_lock_state.clear()
    for obj in bpy.data.objects:
        if '_bsm_selectable_before_lock' in obj:
            previous = bool(obj['_bsm_selectable_before_lock'])
            _saved_lock_state.append((obj, previous))
            obj.hide_select = previous
            del obj['_bsm_selectable_before_lock']


@persistent
def save_post(_):
    if _active:
        for obj, previous in _saved_lock_state:
            try:
                obj['_bsm_selectable_before_lock'] = previous
                obj.hide_select = True
            except ReferenceError:
                continue
    _saved_lock_state.clear()


def recover_startup():
    recover_selection_lock()
    return None


def register():
    restore_theme()  # Recover the baseline if a previous session ended while active.
    bpy.app.timers.register(recover_startup, first_interval=0.0)
    if load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.save_pre.append(save_pre)
    bpy.app.handlers.save_post.append(save_post)
    if hasattr(bpy.app.handlers, 'save_post_fail'):
        bpy.app.handlers.save_post_fail.append(save_post)
    prefs = preferences()
    if False:  # unified startup_mode is the sole startup owner
        # The startup splash is built before the deferred activation runs.
        apply_splash(True)
        request(True)
        # Startup can replace the factory screen after the initial activation.
        # Reconcile the saved mode once the interactive window is ready.
        if not bpy.app.background:
            bpy.app.timers.register(reconcile_startup, first_interval=6.0)
            if bpy.context.preferences.view.show_splash:  # bpy.data is restricted here
                _splash_attempts[0] = 0
                bpy.app.timers.register(startup_splash, first_interval=.5)


_splash_attempts = [0]


def startup_splash():
    """Blender opens its splash on the startup screen and entering the Studio workspace
    closes it, so open it again once the Studio screen is in place."""
    window = bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None
    _splash_attempts[0] += 1
    if not _active or bpy.data.filepath or window is None or _splash_attempts[0] > 40:
        return None
    if not window.workspace.get('bsm_primary_workspace') or window.screen not in list(window.workspace.screens):
        return .1
    with bpy.context.temp_override(window=window, screen=window.screen):
        bpy.ops.wm.splash('INVOKE_DEFAULT')
    return None


def reconcile_startup():
    if not _active:
        return None
    if not bpy.context.window_manager.windows:
        return .25
    if any(not win.workspace.get('bsm_primary_workspace') and not win.workspace.get('bsm_editor_kind') for win in bpy.context.window_manager.windows):
        # A later startup handler can replace the initial screen. Rebuild our
        # scoped hooks against that final screen; scene data is untouched.
        set_active(False, layout=False)
        set_active(True)
    else:
        set_active(True)
    return None


def unregister():
    global _pending
    _pending = None
    if bpy.app.timers.is_registered(_apply_pending):
        bpy.app.timers.unregister(_apply_pending)
    if bpy.app.timers.is_registered(recover_startup):
        bpy.app.timers.unregister(recover_startup)
    if bpy.app.timers.is_registered(reconcile_startup):
        bpy.app.timers.unregister(reconcile_startup)
    if bpy.app.timers.is_registered(startup_splash):
        bpy.app.timers.unregister(startup_splash)
    if load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post)
    for collection, fn in ((bpy.app.handlers.save_pre, save_pre), (bpy.app.handlers.save_post, save_post)):
        if fn in collection:
            collection.remove(fn)
    if hasattr(bpy.app.handlers, 'save_post_fail') and save_post in bpy.app.handlers.save_post_fail:
        bpy.app.handlers.save_post_fail.remove(save_post)
    if _active:
        set_active(False)
    else:
        restore_theme()
        recover_selection_lock()
    apply_splash(False)
