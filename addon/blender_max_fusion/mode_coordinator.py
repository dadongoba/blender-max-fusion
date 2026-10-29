# SPDX-License-Identifier: GPL-3.0-or-later
"""Mutually exclusive Maya and Max modes, restoring original hooks on unload."""
import sys
_hooks=[]
def install():
    if _hooks: return
    from . import runtime
    for name,module in list(sys.modules.items()):
        if not name.endswith('.allset.switch') or not hasattr(module,'set_mode'): continue
        original=module.set_mode
        def coordinated(on,layout=True,_original=original):
            if on and runtime.is_active(): runtime.set_active(False)
            return _original(on,layout=layout)
        module.set_mode=coordinated
        _hooks.append((module,original,coordinated))
def before_max():
    install()
    for module,original,wrapper in _hooks:
        if module.is_on(): original(False,layout=False)
def uninstall():
    while _hooks:
        module,original,wrapper=_hooks.pop()
        if module.set_mode is wrapper: module.set_mode=original
