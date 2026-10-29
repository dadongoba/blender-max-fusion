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
# 2025/09/07


""" This file can be instaled as an stand alone add-on too """
from .....localization import tr as _tr

bl_info = {
	"name": "BsMax-CharacterTools",
	"description": "Some Simple Character Tools (Blender 4.2LTS ~ 4.5LTS)",
	"author": "Nevil",
	"version": (1, 0, 0),
	"blender": (4, 2, 0),
	"location": "View3D/ Object/ Animation/ ...",
	"doc_url": "https://github.com/NevilArt/BsMax/wiki",
	"tracker_url": "https://github.com/NevilArt/BsMax/issues",
	"category": "Animation"
}

import bpy

from bpy.types import Operator
from bpy.props import StringProperty
from bpy.utils import register_class, unregister_class


def set_as_active_object(ctx, obj):
	if not obj:
		return

	for obj in ctx.selected_objects:
		obj.select_set(False)

	obj.select_set(state=True)
	ctx.view_layer.objects.active = obj


class CharacterSet:
	def __init__(self):
		self.characters = []
	
	def get_scene_characters(self):
		self.characters = [
			char for char in bpy.data.objects
			if char.type == 'ARMATURE'
		]
	
	def get_character_by_name(self, name):
		for char in self.characters:
			if char.name == name:
				return char
		return None

character_set = CharacterSet()


class Armature_TO_Select_By_Name(Operator):
	bl_idname = 'anim.select_by_name'
	bl_label = "Select Armature By Name"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
	
	name: StringProperty(default="")
	
	@classmethod
	def poll(self, ctx):
		return ctx.mode == 'OBJECT'
	
	def execute(self,ctx):
		if not self.name:
			return{'FINISHED'}
		
		bpy.ops.object.select_all(action='DESELECT')

		if self.name in bpy.data.objects:
			set_as_active_object(ctx, bpy.data.objects[self.name])

		return{'FINISHED'}


class Armature_TO_Character_Hide(Operator):
	bl_idname = 'anim.character_hide'
	bl_label = "Character Hide"
	bl_description = "Hide/Unhide Character (for now only Armature)"
	bl_options={'REGISTER', 'INTERNAL'}

	name: StringProperty(default="")

	def execute(self, _):
		character = character_set.get_character_by_name(self.name)
		if character:
			state = not character.hide_viewport
			character.hide_viewport = state
			character.hide_render = False
			character.hide_select = False

		return{'FINISHED'}


class Armature_TO_Character_Isolate(Operator):
	bl_idname = 'anim.character_isolate'
	bl_label = "Character Isolate"
	bl_description = "Isolate only this Character (for now only Armature)"
	bl_options={'REGISTER', 'INTERNAL'}

	name: StringProperty(default="")

	def execute(self, _):
		character = character_set.get_character_by_name(self.name)
		if character:
			for char in character_set.characters:
				if char != character:
					char.hide_viewport = True
					char.hide_render = True
					char.hide_select = True
				else:
					char.hide_viewport = False
					char.hide_render = False
					char.hide_select = False

		return{'FINISHED'}


class Armature_TO_Character_Rest(Operator):
	bl_idname = 'anim.character_rest'
	bl_label = "Character Rest/Pose"
	bl_description = "Rest/Pose Switch"
	bl_options={'REGISTER', 'INTERNAL'}

	name: StringProperty(default="") # type: ignore

	def execute(self, _):
		character = character_set.get_character_by_name(self.name)
		if character:
			state = character.data.pose_position
			state = 'POSE' if state == 'REST' else 'REST'
			character.data.pose_position = state

		return{'FINISHED'}


class Anim_TO_Character_Lister(Operator):
	bl_idname = 'anim.character_lister'
	bl_label = "Character lister"
	bl_description = "List of Character for quick managment"
	bl_options={'REGISTER'}

	def get_field(self, row, character):
		name = character.name
		row.operator(
			'anim.select_by_name', icon='ARMATURE_DATA', text=character.name
		).name = name

		hide_icon = 'HIDE_ON' if character.hide_viewport else 'HIDE_OFF'
		row.operator(
			'anim.character_hide', icon=hide_icon, text=_tr("")
		).name = name

		hide_viewport = character.hide_viewport
		isolate_icon = 'RADIOBUT_OFF' if hide_viewport else 'RADIOBUT_ON'
		row.operator(
			'anim.character_isolate', icon=isolate_icon, text=_tr("")
		).name = name

		pose_position = character.data.pose_position
		rest_icon = 'ARMATURE_DATA' if pose_position == 'REST' else 'EVENT_T'
		row.operator(
			'anim.character_rest', icon=rest_icon, text=_tr("")
		).name = name

	def draw(self, _):
		box = self.layout.box()
		col = box.column()
		row = col.row()
		row.label(text=_tr(""))
		for character in character_set.characters:
			self.get_field(col.row(align=True), character)
	
	def execute(self, _):
		return{'FINISHED'}

	def invoke(self, ctx, _):
		""" collect armature objects in scene """
		character_set.get_scene_characters()
		return ctx.window_manager.invoke_props_dialog(self,width=200)


class Object_TO_Make_Override_Library_plus(Operator):
	bl_idname = 'object.make_override_library_multi'
	bl_label = "Make Library Override (Multi)"
	bl_description = "Convert Multiple selection to library overide"
	bl_options={'REGISTER'}

	@classmethod
	def poll(self, _):
		return bpy.ops.object.make_override_library.poll()
	
	def execute(self, ctx):
		objs = []
		for obj in ctx.selected_objects:
			if obj.type == 'EMPTY':
				if obj.instance_type == 'COLLECTION':
					objs.append(obj)

		bpy.ops.object.select_all(action='DESELECT')

		for obj in objs:
			set_as_active_object(ctx, obj)
			if bpy.ops.object.make_override_library.poll():
				bpy.ops.object.make_override_library()

		return{'FINISHED'}


def library_override_menu(self, _):
	self.layout.operator('object.make_override_library_multi')


def character_lister_menu(self, _):
	layout = self.layout
	layout.separator()
	layout.operator('anim.character_lister')


classes = {
	Armature_TO_Select_By_Name,
	Armature_TO_Character_Hide,
	Armature_TO_Character_Isolate,
	Armature_TO_Character_Rest,
	Anim_TO_Character_Lister,
	Object_TO_Make_Override_Library_plus
}


def register_character_tools():
	for cls in classes:
		register_class(cls)

	None
	None


def unregister_character_tools():
	None
	None

	for cls in classes:
		unregister_class(cls)


# Stand alone mode only
def register():
	register_character_tools()


def unregister():
	unregister_character_tools()


# Test mode only
if __name__ == '__main__':
	register_character_tools()