# SPDX-License-Identifier: GPL-3.0-or-later
"""Custom studio editor workspaces; all scene data stays in the current file."""
import os
from pathlib import Path
import bpy
from . import runtime, surfaces

ROLES = {'MATERIAL': 'Slate', 'COMPACT': 'Compact', 'GRAPH': 'Curve', 'DOPESHEET': 'Dope', 'UV': 'UV', 'RENDER': 'Render', 'SCENE': 'Scene'}
NAMES = {'Slate': 'Slate Material Editor', 'Compact': 'Compact Material Editor', 'Curve': 'Track View - Curve Editor',
         'Dope': 'Track View - Dope Sheet', 'UV': 'Edit UVWs', 'Render': 'Render Setup', 'Scene': 'Scene Explorer'}
TEMPLATE = Path(__file__).with_name('editor_workspace.blend')


def prepare(window):
    kind = window.workspace.get('bsm_editor_kind')
    if kind not in NAMES:
        return
    from . import chrome
    for area in window.screen.areas:
        area.type = 'IMAGE_EDITOR'
        chrome._roles[area.as_pointer()] = kind
        space = area.spaces.active
        space.image = None
        space.show_region_header = False
        space.show_region_toolbar = False
        space.show_region_ui = False
        space.show_gizmo = False
    chrome._remove_legacy_images()
    if kind in {'Slate', 'Compact'}:
        from . import material_ui
        area = window.screen.areas[0]
        with bpy.context.temp_override(window=window, area=area, region=next(r for r in area.regions if r.type == 'WINDOW')):
            material_ui.prepare(bpy.context, kind)
    chrome.register_mode()
    runtime.redraw()


def _workspace(context, window, name, tags):
    ws = next((w for w in bpy.data.workspaces if all(w.get(k) == v for k, v in tags.items())), None)
    if ws is None:
        before = set(bpy.data.workspaces)
        with context.temp_override(window=window):
            bpy.ops.workspace.append_activate(idname='BSM_Editor', filepath=str(TEMPLATE))
        ws = next(w for w in bpy.data.workspaces if w not in before and w.name.startswith('BSM_Editor'))
        ws.name = name
        ws['bsm_workspace'] = True
        for key, value in tags.items():
            ws[key] = value
    return ws


def _new_window(context, floating):
    window = context.window
    if floating and not window.workspace.get('bsm_editor_kind') and not window.workspace.get('bsm_native_kind'):
        before = set(context.window_manager.windows)
        handles = {h for h, _, _ in _os_windows()}
        bpy.ops.wm.window_new()
        window = next((w for w in context.window_manager.windows if w not in before), window)
        # The OS window exists as soon as window_new returns: remember which one it is.
        new = [h for h, _, _ in _os_windows() if h not in handles]
        if window not in before and len(new) == 1:
            _title_handles[window.as_pointer()] = new[0]
    return window


def _when_ready(window, ws, callback):
    attempts = [0]

    def ready():
        attempts[0] += 1
        if not runtime.is_active() or attempts[0] > 60:
            return None
        try:
            if window.workspace != ws or window.screen not in list(ws.screens):
                return .05
            callback(window)
        except ReferenceError:
            return None
        return None
    bpy.app.timers.register(ready, first_interval=.1)


# Client size of Max 2027 dialogs that open as their own window, in layout units
# (1 unit = 1 px of the owner's 2000 px wide Max screenshots, which surfaces.scale() matches).
DIALOG_SIZES = {'Render': (355, 834)}


def _raise(window):
    """Bring an editor's OS window to the front; False when it cannot be found."""
    if os.name != 'nt':
        return False
    try:
        ctypes, wintypes, user32 = _win32()
        hwnd = _handle(window)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE, in case it was minimized
        user32.SetForegroundWindow(hwnd)
        return True
    except (AttributeError, OSError):
        return False


def _place(window, width, height):
    """Resize a new OS window to a Max dialog's client size, keeping its centre and staying
    inside the work area. Windows only; elsewhere Blender's size is kept."""
    if os.name != 'nt':
        return
    try:
        ctypes, wintypes, user32 = _win32()
        hwnd = _title_handles.get(window.as_pointer())
        if not hwnd or not user32.IsWindow(hwnd):
            return
        outer, inner, work = wintypes.RECT(), wintypes.RECT(), wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(outer))
        user32.GetClientRect(hwnd, ctypes.byref(inner))
        user32.SystemParametersInfoW(0x30, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
        frame_w = (outer.right-outer.left)-inner.right
        frame_h = (outer.bottom-outer.top)-inner.bottom
        u = surfaces.scale()
        w = min(int(width*u)+frame_w, work.right-work.left)
        h = min(int(height*u)+frame_h, work.bottom-work.top)
        cx, cy = (outer.left+outer.right)//2, (outer.top+outer.bottom)//2
        x = min(max(work.left, cx-w//2), work.right-w)
        y = min(max(work.top, cy-h//2), work.bottom-h)
        user32.SetWindowPos(hwnd, None, x, y, w, h, 0x0004)  # SWP_NOZORDER
    except (AttributeError, OSError):
        return


def title(context, kind):
    """The OS window title: Max names Render Setup after the active renderer."""
    if kind == 'Render':
        engine = context.scene.render.engine
        name = 'Cycles' if engine == 'CYCLES' else 'EEVEE' if 'EEVEE' in engine else engine.replace('BLENDER_', '').title()
        return f'Render Setup: {name}'
    return NAMES.get(kind, '')


def open_editor(context, kind, floating=False):
    role = ROLES[kind]
    if floating:
        # As in Max, the dialog's key brings an open dialog forward instead of a second copy.
        existing = next((w for w in context.window_manager.windows
                         if w != context.window and w.workspace.get('bsm_editor_kind') == role), None)
        if existing is not None and _raise(existing):
            return {'FINISHED'}
    before = set(context.window_manager.windows)
    window = _new_window(context, floating)
    if window not in before and role in DIALOG_SIZES:
        _place(window, *DIALOG_SIZES[role])
    ws = _workspace(context, window, NAMES[role], {'bsm_editor_kind': role, 'bsm_editor_layout': 1})
    window.workspace = ws
    _when_ready(window, ws, prepare)
    return {'FINISHED'}


def open_native(context, space_type, name, setup=None):
    """A floating window with one native Blender editor (Listener, Script Editor, Schematic...)."""
    window = _new_window(context, True)
    ws = _workspace(context, window, name, {'bsm_native_kind': space_type})
    window.workspace = ws

    def finish(window):
        area = window.screen.areas[0]
        area.type = space_type
        space = area.spaces.active
        result = setup(space) if setup else None
        if result == 'OPEN' and space_type == 'TEXT_EDITOR':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.text.open('INVOKE_DEFAULT')
    _when_ready(window, ws, finish)
    return {'FINISHED'}


_title_handles = {}
_title_pending = set()
_title_misses = {}


def _win32():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.SetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPCWSTR)
    user32.IsWindow.argtypes = (wintypes.HWND,)
    return ctypes, wintypes, user32


def _os_windows():
    """(handle, title, (x, width, height) of the client area) for this process's visible
    Blender windows; empty outside Windows."""
    if os.name != 'nt':
        return []
    try:
        ctypes, wintypes, user32 = _win32()
    except (AttributeError, OSError):
        return []
    found = []
    pid = os.getpid()

    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        name = ctypes.create_unicode_buffer(32)
        user32.GetClassNameW(hwnd, name, 32)
        if owner.value == pid and name.value == 'GHOST_WindowClass' and user32.IsWindowVisible(hwnd):
            text = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, text, 256)
            rect, corner = wintypes.RECT(), wintypes.POINT(0, 0)
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            user32.ClientToScreen(hwnd, ctypes.byref(corner))
            found.append((hwnd, text.value, (corner.x, rect.right, rect.bottom)))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def _handle(window):
    """The OS window of a secondary Blender window: recorded when the add-on opened it, else
    the one with its position and size that is not the main window."""
    ctypes, wintypes, user32 = _win32()
    hwnd = _title_handles.get(window.as_pointer())
    if hwnd and user32.IsWindow(hwnd):
        return hwnd
    import time
    if time.monotonic()-_title_misses.get(window.as_pointer(), -9.) < 1.:
        return None  # looked a moment ago: retry at most once a second while drawing
    main = bpy.context.window_manager.windows[0]
    taken = set(_title_handles.values())
    matches = [h for h, title, geometry in _os_windows()
               if geometry == (window.x, window.width, window.height) and h not in taken
               and geometry != (main.x, main.width, main.height)]
    if len(matches) == 1:
        _title_handles[window.as_pointer()] = matches[0]
        return matches[0]
    _title_misses[window.as_pointer()] = time.monotonic()
    return None


def sync_title(window, title):
    """Blender titles child windows after their first editor type ("Image Editor"); show
    the Max editor name instead. Blender resets it on workspace changes; the next draw of
    the editor restores it."""
    # Only Blender's secondary windows: child windows and temporary ones such as the render window.
    if os.name != 'nt' or window is None or not title or (window.parent is None and not window.screen.is_temporary):
        return
    try:
        ctypes, wintypes, user32 = _win32()
        hwnd = _handle(window)
        if not hwnd:
            return
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, text, 256)
        if text.value != title and hwnd not in _title_pending:
            _title_pending.add(hwnd)

            def retitle():
                # Outside drawing: retitling sends the window a message synchronously.
                _title_pending.discard(hwnd)
                if user32.IsWindow(hwnd):
                    user32.SetWindowTextW(hwnd, title)
                return None
            bpy.app.timers.register(retitle, first_interval=0.)
    except (AttributeError, OSError):
        return


render_view = ['']  # Max view name of the last Studio render: Perspective, Top, Camera001...


def render_title(context):
    """The Rendered Frame Window title, in Max's order: view, frame, colour display, image
    type and colour depth, zoom ratio. Blender renders in float, with OCIO-style display
    and view transforms (Max 2027 shows Display: and View: in OCIO mode)."""
    scene = context.scene
    view = render_view[0] or (scene.camera.name if scene.camera else 'Perspective')
    zoom = context.space_data.zoom[0] if getattr(context.space_data, 'zoom', None) else 1.
    ratio = f'({max(1, round(zoom))}:1)' if zoom >= 1 else f'(1:{max(1, round(1/zoom))})'
    return (f'{view}, frame {scene.frame_current}, Display: {scene.display_settings.display_device}, '
            f'View: {scene.view_settings.view_transform}, RGBA Color 32 Bits/Channel {ratio}')


def draw(context, kind):
    sync_title(context.window, title(context, kind))
    if kind in {'Slate', 'Compact'}:
        from . import material_ui
        material_ui.draw(context, kind)
    elif kind in {'Curve', 'Dope'}:
        from . import animation_ui
        animation_ui.draw(context, kind)
    elif kind == 'Scene':
        from . import scene_ui
        scene_ui.draw(context, kind)
    else:
        from . import utility_editors
        utility_editors.draw(context, kind)


def active_event(context, event):
    from . import material_ui, animation_ui, utility_editors, scene_ui
    for module in (material_ui, animation_ui, utility_editors, scene_ui):
        result = module.active_event(context, event)
        if result is not None:
            return result
    return None


def handle_event(context, event, area, region, x, y, kind):
    if kind in {'Slate', 'Compact'}:
        from . import material_ui as module
    elif kind in {'Curve', 'Dope'}:
        from . import animation_ui as module
    elif kind == 'Scene':
        from . import scene_ui as module
    else:
        from . import utility_editors as module
    return module.handle_event(context, event, area, region, x, y)


def dispatch(context, action):
    if action[0] == 'MAT':
        from . import material_ui
        return material_ui.dispatch(context, action)
    if action[0] == 'ANIM':
        from . import animation_ui
        return animation_ui.dispatch(context, action)
    if action[0] == 'UTIL':
        from . import utility_editors
        return utility_editors.dispatch(context, action)
    if action[0] == 'SCENE':
        from . import scene_ui
        return scene_ui.dispatch(context, action)
    return None


def clear():
    from . import material_ui, animation_ui, utility_editors, scene_ui
    material_ui.clear()
    animation_ui.clear()
    utility_editors.clear()
    scene_ui.clear()
