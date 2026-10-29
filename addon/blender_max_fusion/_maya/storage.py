# SPDX-License-Identifier: GPL-3.0-or-later
import bpy,os
def user_path(path='',create=False):
    host=__package__.rsplit('.',1)[0]
    if host.startswith('bl_ext.'):
        return bpy.utils.extension_path_user(host,path=path,create=create)
    base=bpy.utils.user_resource('CONFIG',path='unified_workflow',create=create)
    target=os.path.join(base,path)
    if create: os.makedirs(target,exist_ok=True)
    return target
