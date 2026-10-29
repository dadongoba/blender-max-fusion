from .....localization import tr as _tr
############################################################################
#	BsMax, 3D apps inteface simulator and tools pack for Blender
#	Copyright (C) 2020  Naser Merati (Nevil)
#
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

import bpy

from mathutils import Vector
from bpy.types import Operator, Panel
from bpy.utils import register_class, unregister_class
from bpy.props import PointerProperty, EnumProperty, IntProperty, BoolProperty
from bpy_extras import view3d_utils

# TODO list
# Pic ground
# random rotation/scale
# Reset/Set rotation/Scale 

class Hit_Point:
	def __init__(self, hit, location, normal, face_index, obj, matrix):
		self.hit = hit
		self.location = location
		self.normal = normal
		self.face_index = face_index
		self.obj = obj
		self.matrix = matrix


def raycast(ctx, x, y):
	region = ctx.region
	coord = (x, y)
	depsgraph = bpy.context.evaluated_depsgraph_get()
	rv3d = ctx.space_data.region_3d
	origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
	direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord).normalized()
	hit, location, normal, face_index, obj, matrix = ctx.scene.ray_cast(depsgraph, origin, direction)
	return Hit_Point(hit, location, normal, face_index, obj, matrix)


def pic_ground(ctx, co):
	region = ctx.region
	depsgraph = bpy.context.evaluated_depsgraph_get()
	rv3d = ctx.space_data.region_3d
	origin = co
	direction = Vector((0, 0, -1))
	hit, location, normal, face_index, obj, matrix = ctx.scene.ray_cast(depsgraph, origin, direction)
	return Hit_Point(hit, location, normal, face_index, obj, matrix)


# there is no api for add new point to pointclud yet
def pointcloud_new(ctx, co, normal):
	new_mesh = bpy.data.meshes.new("pointcloudtemp")
	new_mesh.vertices.add(1)
	new_mesh.vertices[0].co = co
	new_obj = bpy.data.objects.new("pointcloudtemp", new_mesh)
	ctx.scene.collection.objects.link(new_obj)
	new_obj.select_set(True)

	new_obj.data.attributes.new("rotation", 'FLOAT_VECTOR', domain='POINT')
	rotaion = new_obj.data.attributes['rotation'].data.values()[0].vector
	rotaion.x = normal.x
	rotaion.y = normal.y
	rotaion.z = normal.z

	bpy.ops.object.convert(target='POINTCLOUD')
	bpy.ops.object.join()


class POINTCLOUD_OT_Pic_Ground(Operator):
	bl_idname = 'pointcloud.pic_ground'
	bl_label = "Pic Ground"
	bl_description = ''
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(self, ctx):
		return ctx.mode == 'EDIT_POINTCLOUD'
	
	def execute(self, ctx):
		if '.selection' not in ctx.object.data.attributes:
			return{'FINISHED'}

		count = len(ctx.object.data.points)

		selection_data = ctx.object.data.attributes['.selection'].data
		points = ctx.object.data.points.values()
		for index in range(0, count):
			if selection_data.values()[index].value:
				hp = pic_ground(ctx, points[index].co)
				if hp.hit:
					points[index].co = hp.location

		return{'FINISHED'}


class POINTCLOUD_OT_set_Rotate(Operator):
	bl_idname = 'pointcloud.set_rotate'
	bl_label = "Set Rotation"
	bl_description = ''
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(self, ctx):
		return ctx.mode == 'EDIT_POINTCLOUD'
	
	def execute(self, ctx):
		return{'FINISHED'}



class POINTCOLUD_OP_Pic_Surface(Operator):
	bl_idname="pointcloud.put_on_surface"
	bl_label="Add New Point On Surface"
	bl_options = {'REGISTER','UNDO'}

	used_keys = ['LEFTMOUSE', 'RIGHTMOUSE', 'ESC', 'MOUSEMOVE', 'Z']
	cancel_keys = ['RIGHTMOUSE', 'ESC']

	@classmethod
	def poll(self, ctx):
		if ctx.mode == 'OBJECT':
			if ctx.object:
				return ctx.object.type == 'POINTCLOUD'
		return False
	
	def modal(self, ctx, event):

		if event.type in {'RIGHTMOUSE', 'ESC'}:
			return {'CANCELLED'}
		
		if not event.type in self.used_keys:
			return {'PASS_THROUGH'}
		
		if event.type == 'LEFTMOUSE':
			if event.value =='RELEASE':
				hit_point =  raycast(ctx, event.mouse_region_x, event.mouse_region_y)

				if hit_point.hit:
					pointcloud_new(ctx, hit_point.location, hit_point.normal)

		return {'RUNNING_MODAL'}

	def invoke(self, ctx, event):
		ctx.window_manager.modal_handler_add(self)
		return {'RUNNING_MODAL'}


class OBJECTR_OP_Pointcloud_Transform(Panel):
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_label = 'Points'
	bl_idname = 'VIEW3D_PT_edit_Pointcloud'
	bl_category = 'Item'

	@classmethod
	def poll(self, ctx):
		return ctx.mode in {'OBJECT', 'EDIT_POINTCLOUD'}

	def draw(self, ctx):
		layout = self.layout
		layout.label(text=_tr("Left Handle "))
		layout.operator('pointcloud.pic_ground')
		layout.operator('pointcloud.put_on_surface')


classes = {
	OBJECTR_OP_Pointcloud_Transform,
	POINTCLOUD_OT_Pic_Ground,
	POINTCOLUD_OP_Pic_Surface
}


def register_point_cloud():
	for cls in classes:
		register_class(cls)
	# VIEW3D_MT_edit_pointcloud
	# bpy.types.VIEW3D_MT_edit_pointcloud.


def unregister_point_cloud():
	for cls in classes:
		unregister_class(cls)


if __name__ == '__main__':
	register_point_cloud()