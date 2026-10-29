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
# 2025/06/05

import bpy

from bpy.props import IntProperty
from bpy.types import Operator
from bpy.utils import register_class, unregister_class


def set_mode(mode):
	bpy.ops.object.mode_set(mode=mode)


def set_mesh_sub_mode(ctx, vertex, edge, face):
	ctx.tool_settings.mesh_select_mode = vertex, edge, face


def is_primitive(obj):
	if obj.type in {'MESH', 'CURVE'}:
		if 'classname' in obj.data.primitivedata:
			return obj.data.primitivedata['classname']
	return False


def set_mesh_mode(ctx, mode, level):
	v, e, f = ctx.tool_settings.mesh_select_mode

	if level == 1: # Vertex mode
		if mode == "EDIT_MESH" and v:
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')
			set_mesh_sub_mode(ctx, True, False, False)

	elif level == 2: # Edge mode
		if mode == "EDIT_MESH" and e:
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')
			set_mesh_sub_mode(ctx, False, True, False)

	#elif self.level == 3: # Reserved for Border mode
	#	# this is reserved for border mode for now just act as edge mode
	#	if mode == "EDIT_MESH" and e:
	#		set_mode('OBJECT')
	#	else:
	#		set_mode('EDIT')
	#		self.mesh(ctx,False,True,False)

	elif level in {3, 4}: # Mesh mode
		if mode == "EDIT_MESH" and f:
			set_mode('OBJECT')
		else:
			set_mode('EDIT')
			set_mesh_sub_mode(ctx, False, False, True)
	#elif self.level == 5: # Reserved for Element mode
	#	# this is reserved for Element mode for now act as Face mode
	#	if mode == "EDIT_MESH" and f:
	#		set_mode('OBJECT')
	#	else:
	#		set_mode('EDIT')
	#	self.mesh(ctx,False,False,True)

	elif level == 6:
		set_mode('OBJECT')

	# this do not have similar in 3D Max
	elif level == 7:
		if mode == "SCULPT": 
			set_mode('OBJECT')
		else: 
			set_mode('SCULPT')

	elif level == 8:
		if mode == "PAINT_VERTEX":
			set_mode('OBJECT')
		else:
			set_mode('VERTEX_PAINT')

	elif level == 9:
		if mode == "PAINT_WEIGHT":
			set_mode('OBJECT')
		else: 
			set_mode('WEIGHT_PAINT')

	elif level == 0:
		if mode == "PAINT_TEXTURE": 
			set_mode('OBJECT')
		else: 
			set_mode('TEXTURE_PAINT')


def set_surface_mode(mode, level):
	if level == 1:
		if mode == "EDIT_SURFACE": 
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')

	elif level == 0 or level >= 2:
		set_mode('OBJECT')


def set_curve_mode(mode, level):
	if level == 1:
		if mode == "EDIT_CURVE": 
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')

	elif level == 0 or level >= 2: 
		set_mode('OBJECT')


def set_curves_mode(mode, level):
	if level == 1:
		if mode == "EDIT_CURVES": 
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')

	if level == 2:
		if mode == "SCULPT_CURVES": 
			set_mode('OBJECT')
		else: 
			set_mode('SCULPT')

	elif level == 0 or level >= 2: 
		set_mode('OBJECT')


def set_meta_mode(mode, level):
	if level == 1:
		if mode == "EDIT_METABALL": 
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')

	elif level == 0 or level >= 2: 
		set_mode('OBJECT')


def set_lattice_mode(mode, level):
	if level == 1:
		if mode == "EDIT_LATTICE": 
			set_mode('OBJECT')
		else: 
			set_mode('EDIT')
	elif level == 0 or level >= 2: 
		set_mode('OBJECT')


def set_armature_mode(mode, level):
	if level == 1:
		if mode == "EDIT_ARMATURE":
			set_mode('OBJECT')
		else:
			# this for proxy and librery overide the cant be set in edit mode #
			# TODO find a way to check is linked or not rather then use try #
			try:
				set_mode('EDIT')
			except:
				pass

	elif level == 2:
		if mode == "POSE":
			set_mode('OBJECT')
		else:
			set_mode('POSE')

	elif level == 0 or level >= 3:
		set_mode('OBJECT')


def set_point_cloude_mode(mode, level):
	# print(level, mode)
	if level == 1:
		if mode == 'EDIT_POINTCLOUD':
			set_mode('OBJECT')
		else:
			set_mode('EDIT')
	
	elif level == 0 or level >= 2:
		set_mode('OBJECT')


def set_gpencil_mode(mode, level):
	if level == 1:
		if mode == 'GPENCIL_EDIT':
			set_mode('OBJECT')
		else:
			set_mode('GPENCIL_EDIT')

	elif level == 2:
		if mode == 'GPENCIL_SCULPT':
			set_mode('OBJECT')
		else:
			set_mode('GPENCIL_SCULPT')

	elif level == 3:
		if mode == 'GPENCIL_PAINT':
			set_mode('OBJECT')
		else:
			set_mode('GPENCIL_PAINT')

	elif level == 4:
		if mode == 'GPENCIL_WEIGHT':
			set_mode('OBJECT')
		else:
			set_mode('GPENCIL_WEIGHT')

	elif level == 0 or level >= 5:
		set_mode('OBJECT')


class Object_OT_Subobject_Level(Operator):
	bl_idname = "object.subobject_level"
	bl_label = "Subobject Level"
	bl_options = {'REGISTER', 'INTERNAL'}

	level: IntProperty(name="SubobjectLevel") # type: ignore

	@classmethod
	def poll(_, ctx):
		return ctx.object

	def execute(self, ctx):
		obj = ctx.object
		mode = ctx.mode
		level = self.level
		obj_type = obj.type

		if is_primitive(obj):
			set_mode('OBJECT')
			return{'FINISHED'}

		if obj_type == 'MESH':
			set_mesh_mode(ctx, mode, level)

		elif obj_type == 'SURFACE':
			set_surface_mode(mode, level)

		elif obj_type == 'CURVE':
			set_curve_mode(mode, level)
		
		elif obj_type == 'CURVES':
			set_curves_mode(mode, level)

		elif obj_type == 'META':
			set_meta_mode(mode, level)

		elif obj_type == 'LATTICE':
			set_lattice_mode(mode, level)

		elif obj_type == 'ARMATURE':
			set_armature_mode(mode, level)
		
		elif obj_type == 'POINTCLOUD':
			set_point_cloude_mode(mode, level)

		elif obj_type == 'GPENCIL':
			set_gpencil_mode(mode, level)

		return{'FINISHED'}


def register_subobject_level():
	register_class(Object_OT_Subobject_Level)


def unregister_subobject_level():
	unregister_class(Object_OT_Subobject_Level)


if __name__ == '__main__':
	register_subobject_level()