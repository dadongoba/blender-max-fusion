from .....localization import tr as _tr
############################################################################
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <https://www.gnu.org/licenses/>.
############################################################################
# 2024/09/09

import bpy
from bpy.types import Panel


class UV_OP_Property_Panel(Panel):
	bl_idname = 'UV_PT_Tools_Sheet'
	bl_label = "UV Tools"
	bl_space_type = 'IMAGE_EDITOR'
	bl_region_type = 'UI'
	bl_category = 'UV Tools'

	@classmethod
	def poll(self, ctx):
		return ctx.mode == 'EDIT_MESH'
	
	def draw(self, ctx):
		layout = self.layout

		# Pin
		box = layout.box()
		row = box.row()
		row.operator('uv.pin', text=_tr(""), icon='PINNED').clear=False
		row.operator('uv.pin', text=_tr(""), icon='UNPINNED').clear=True

		# Mirror
		box = layout.box()
		box.operator('mesh.faces_mirror_uv')
		row = box.row(align=True)
		row.operator('uv.mirror_cover', text=_tr("X"), icon='MOD_MIRROR').axis='X'
		row.operator('uv.mirror_cover', text=_tr("Y"), icon='MOD_MIRROR').axis='Y'
		row.operator('uv.turn', text=_tr("-90"), icon='LOOP_BACK').ccw = False
		row.operator('uv.turn', text=_tr("+90"), icon='LOOP_FORWARDS').ccw = True

		# Snap
		box = layout.box()
		box.label(text=_tr("Snap"))
		row = box.row(align=True)
		row.prop(ctx.space_data.uv_editor, 'pixel_snap_mode', expand=True)
		row = box.row(align=True)
		row.operator(
			'uv.snap_selected', text=_tr(" "), icon='SNAP_VERTEX'
		).target='PIXELS'

		row.operator(
			'uv.snap_selected', text=_tr(" "), icon='PIVOT_CURSOR'
		).target='CURSOR'

		row.operator(
			'uv.snap_selected', text=_tr(" "), icon='ORIENTATION_GIMBAL'
		).target='CURSOR_OFFSET'

		row.operator(
			'uv.snap_selected', text=_tr(" "), icon='SELECT_SET'
		).target='ADJACENT_UNSELECTED'

		row = box.row(align=True)
		row.operator(
			'uv.snap_cursor', text=_tr("Cursor"), icon='ORIENTATION_CURSOR'
		).target='PIXELS'
		
		row.operator(
			'uv.snap_cursor', text=_tr("Vertex"), icon='SNAP_VERTEX'
		).target='SELECTED'
		
		box.prop(
			ctx.space_data.uv_editor, 'lock_bounds',
			text=_tr("Lock Bound"), icon='VIEW_ORTHO'
		)

		# Merge / Split
		box = layout.box()
		box.label(text=_tr('Merge / Split'))
		row = box.row(align=True)
		row.operator('uv.weld', text=_tr(" Weld"), icon='FULLSCREEN_EXIT')
		row.operator(
			'uv.snap_selected', text=_tr(" To Cursor"), icon='ORIENTATION_CURSOR'
		).target='CURSOR'

		row.operator(
			'uv.remove_doubles', text=_tr(" Merge"), icon='DRIVER_DISTANCE'
		)

		row = box.row(align=True)
		row.operator('uv.split_to_island', text=_tr("Split"))
		row.operator('uv.stitch', text=_tr("Stitch"))

		# UNwarap
		box = layout.box()
		box.label(text=_tr("Unwrap"))
		row = box.row(align=True)
		row.operator(
			'uv.mark_seam', text=_tr(" Mark Seam"), icon='MESH_PLANE'
		).clear=False
		
		row.operator(
			'uv.mark_seam', text=_tr(" Clear Seam"), icon='SELECT_SET'
		).clear=True
		
		row.operator(
			'uv.seams_from_islands', text=_tr(" Seam From Island"),
			icon='MOD_BOOLEAN'
		)

		row = box.row(align=True)
		row.operator('uv.unwrap', text=_tr(" Unwarp"), icon='MATCLOTH')

		row.operator(
			'uv.cube_project', text=_tr(" Cube Projection"), icon='MESH_CUBE'
		)

		row.operator(
			'uv.cylinder_project', text=_tr(" Cylinder Projection"),
			icon='MESH_CYLINDER'
		)

		row.operator(
			'uv.sphere_project', text=_tr(" Sphere Projection"),
			icon='MESH_UVSPHERE'
		)

		row = box.row(align=True)
		row.operator('uv.smart_project', text=_tr(" Smart Project"), icon='MONKEY')
		row.operator(
			'uv.lightmap_pack', text=_tr(" Ligtmap Pack"), icon='MOD_MULTIRES'
		)
		
		row.operator(
			'uv.follow_active_quads', text=_tr(" Fallow Active Quad"),
			icon='VIEW_PERSPECTIVE'
		)
		
		# Align
		box = layout.box()
		box.label(text=_tr('Align'))
		row = box.row(align=True)
		row.operator('uv.align', text=_tr(" Straighten")).axis='ALIGN_S'
		row.operator('uv.align', text=_tr("X Straighten")).axis='ALIGN_T'
		row.operator('uv.align', text=_tr("Y Straighten")).axis='ALIGN_U'
		row = box.row(align=True)

		row.operator(
			'uv.align', text=_tr("Flatten"), icon='NODE_CORNER'
		).axis='ALIGN_AUTO'

		row.operator(
			'uv.align', text=_tr("X"), icon='NODE_SIDE'
		).axis='ALIGN_X'

		row.operator(
			'uv.align', text=_tr("Y"), icon='NODE_TOP'
		).axis='ALIGN_Y'

		row = box.row(align=True)
		
		# Pack
		box = layout.box()
		box.label(text=_tr('Pack'))

		row = box.row()
		row.operator('uv.pack_islands', icon='SEQ_STRIP_META')
		row.operator('uv.average_islands_scale', icon='OBJECT_HIDDEN')

		row = box.row()
		row.operator('uv.minimize_stretch')

		layout.operator('uv.reset')


def register_panel():
	bpy.utils.register_class(UV_OP_Property_Panel)


def unregister_panel():
	bpy.utils.unregister_class(UV_OP_Property_Panel)


if __name__ == '__main__':
	register_panel()