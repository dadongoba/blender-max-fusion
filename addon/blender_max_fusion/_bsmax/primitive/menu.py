from ...localization import tr as _tr
############################################################################
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation,either version 3 of the License,or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not,see <https://www.gnu.org/licenses/>.
############################################################################
# 2025/07/16

import bpy

from bpy.types import Menu
from bpy.utils import register_class, unregister_class


# Mesh create menu
class BsMax_MT_VertexCreate(Menu):
	bl_idname = 'BSMAX_MT_vertex_create_menu'
	bl_label = "Vertex"

	def draw(self, ctx):
		layout=self.layout
		layout.operator(
			'create.vertex', text=_tr("Vertex"), icon='DOT'
		).fill_type='NONE'

		layout.operator(
			'create.vertex', text=_tr("Vertexs"), icon='STICKY_UVS_DISABLE'
		).fill_type='VERT'

		layout.operator(
			'create.vertex', text=_tr("Edge"), icon='CON_TRACKTO'
		).fill_type='EDGE'

		icon = 'LIGHTPROBE_PLANE'
		layout.operator(
			'create.vertex', text=_tr("Face"), icon=icon
		).fill_type='FACE'


# Mesh create menu
class BsMax_MT_Mesh_Extera(Menu):
	bl_idname = 'BSMAX_MT_mesh_extera_menu'
	bl_label = "Mesh Extera"

	def draw(self, ctx):
		layout=self.layout
		layout.operator(
			'mesh.add_spider_web', text=_tr("Spider Web"), icon='FREEZE'
		)
		
		layout.operator(
			'mesh.make_pillow', text=_tr("Pillow"), icon='GHOST_ENABLED'
		)
		
		layout.operator_context = "EXEC_DEFAULT"
		
		layout.operator(
			'object.create', text=_tr("Bolt"), icon='TOOL_SETTINGS'
		).type='BOLT'
		

# Mesh create menu
class BsMax_MT_MeshCreate(Menu):
	bl_idname = 'BSMAX_MT_mesh_create_menu'
	bl_label = "Mesh"

	def draw(self, ctx):
		layout=self.layout
		# layout.operator(
		# 	'create.adaptive_plane', text="Adaptive Plane", icon='MOD_BEVEL'
		# )

		layout.operator(
			'create.plane', text=_tr("Plane"), icon='MESH_PLANE'
		)

		layout.operator(
			'create.box', text=_tr("Box"), icon='MESH_CUBE'
		)

		layout.operator(
			'create.cone', text=_tr("Cone"), icon='MESH_CONE'
		)

		layout.operator(
			'create.sphere', text=_tr("Sphere"), icon='MESH_UVSPHERE'
		)

		# layout.operator(
		# 	'bsmax.creategeosphere', icon='MESH_ICOSPHERE"
		# )

		layout.operator(
			'create.uicosphere', text=_tr("IcoSphere"), icon='MESH_ICOSPHERE'
		)

		layout.operator(
			'create.capsule', text=_tr("Capsule"), icon='META_CAPSULE'
		)

		layout.operator(
			'create.oiltank', text=_tr("OilTank"), icon='META_CAPSULE'
		)

		layout.operator(
			'create.cylinder', text=_tr("Cylinder"), icon='MESH_CYLINDER'
		)

		layout.operator(
			'create.tube', text=_tr("Tube"), icon='MESH_TORUS'
		)

		layout.operator(
			'create.torus', text=_tr("Torus"), icon='MESH_TORUS'
		)

		layout.operator(
			'create.pyramid', text=_tr("Pyramid"), icon='MARKER'
		)

		layout.operator(
			'create.quadsphere', text=_tr("QuadSphere"), icon='SHADING_WIRE'
		)

		layout.operator(
			'create.teapot', text=_tr("Teapot"), icon='NODE_MATERIAL'
		)

		layout.operator(
			'create.monkey', text=_tr("Monkey"), icon='MESH_MONKEY'
		)

		layout.separator()
		layout.menu('BSMAX_MT_vertex_create_menu', icon='DOT')
		layout.separator()

		layout.separator()
		layout.menu('BSMAX_MT_mesh_extera_menu', icon='DOCUMENTS')


# curve / shape / spline create menu
class BsMax_MT_CurveCreate(Menu):
	bl_idname = 'BSMAX_MT_curve_create_menu'
	bl_label = "Curve"

	def draw(self, ctx):
		layout = self.layout
		layout.operator('create.line', text=_tr("Line"), icon='CURVE_PATH')
		layout.operator(
			'create.rectangle', text=_tr("Rectangle"), icon='META_PLANE'
		)
		
		layout.operator('create.circle', text=_tr("Circle"), icon='MESH_CIRCLE')
		layout.operator('create.ellipse', text=_tr("Ellipse"), icon='MESH_CAPSULE')
		layout.operator('create.arc', text=_tr("Arc"), icon='SPHERECURVE')
		layout.operator('create.donut', text=_tr("Donut"), icon='MESH_CIRCLE')
		layout.operator('create.ngon', text=_tr("Ngon"), icon='SEQ_CHROMA_SCOPE')
		layout.operator('create.star', text=_tr("Start"), icon='SOLO_OFF')
		layout.operator('create.torusknot', text=_tr("TorusKnot"), icon='HAND')
		layout.operator('create.helix', text=_tr("Helix"), icon='MOD_SCREW')
		layout.operator('create.profilo', text=_tr("Profilo"), icon='MOD_BOOLEAN')
		layout.separator()
		

# Surface create menu
class BsMax_MT_SurfaceCreate(Menu):
	bl_idname = 'BSMAX_MT_surface_create_menu'
	bl_label = "Surface"

	def draw(self, ctx):
		layout = self.layout
		layout.label(text=_tr("coming soon"))


# Metaball create menu
class BsMax_MT_MetaballCreate(Menu):
	bl_idname = 'BSMAX_MT_metaball_create_menu'
	bl_label = "Metaball"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.metaball', text=_tr("Ball"), icon='META_BALL'
		).metaball_type='BALL'

		layout.operator(
			'create.metaball', text=_tr("Capcule"), icon='META_CAPSULE'
		).metaball_type='CAPSULE'

		layout.operator(
			'create.metaball', text=_tr("Plane"), icon='META_PLANE'
		).metaball_type='PLANE'

		layout.operator(
			'create.metaball', text=_tr("Ellipsoid"), icon='META_ELLIPSOID'
		).metaball_type='ELLIPSOID'

		layout.operator(
			'create.metaball', text=_tr("Cube"), icon='META_CUBE'
		).metaball_type='CUBE'


# Text create menu
class BsMax_MT_TextCreate(Menu):
	bl_idname = 'BSMAX_MT_text_create_menu'
	bl_label = "Text"

	def draw(self, ctx):
		layout = self.layout

		layout.operator(
			'create.text', text=_tr("Text"), icon='OUTLINER_OB_FONT'
		).fill_mode='BOTH'

		layout.operator(
			'create.text', text=_tr("Text"), icon='FONT_DATA'
		).fill_mode='NONE'


# Greace Pencil create menu
class BsMax_MT_GreacePencilCreate(Menu):
	bl_idname = 'BSMAX_MT_gracepencil_create_menu'
	bl_label = "Greace Pencil"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.greacepencil', text=_tr("Blank"), icon='EMPTY_AXIS'
		).gpencil_type='EMPTY'
		
		layout.operator(
			'create.greacepencil', text=_tr("Stroke"),
			icon='OUTLINER_OB_GREASEPENCIL'
		).gpencil_type='STROKE'
		
		layout.operator(
			'create.greacepencil', text=_tr("Monkey"), icon='MESH_MONKEY'
		).gpencil_type='MONKEY'


# Armature create menu
class BsMax_MT_ArmatureCreate(Menu):
	bl_idname = 'BSMAX_MT_armature_create_menu'
	bl_label = "Armature"

	def draw(self, ctx):
		layout = self.layout
		layout.operator('create.bone', text=_tr("Bone"), icon='BONE_DATA')
		#layout.operator('create.bone',text="Armature",icon='ARMATURE_DATA')


# Lattice create menu
class BsMax_MT_LatticeCreate(Menu):
	bl_idname = 'BSMAX_MT_lattice_create_menu'
	bl_label = "Lattice"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.lattice', text=_tr('Lattice 2x2x2 (Create)'),
			icon='OUTLINER_OB_LATTICE'
		).resolution=2
		
		layout.operator(
			'create.lattice', text=_tr('Lattice 3x3x3 (Create)'),
			icon='OUTLINER_OB_LATTICE'
		).resolution=3
		
		layout.operator(
			'create.lattice', text=_tr('Lattice 4x4x4 (Create)'),
			icon='OUTLINER_OB_LATTICE'
		).resolution=4


# Empty create menu
class BsMax_MT_EmptyCreate(Menu):
	bl_idname = 'BSMAX_MT_empty_create_menu'
	bl_label = "Empty"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.empty', text=_tr("Plane Axis"), icon='EMPTY_AXIS'
		).empty_type='PLAIN_AXES'
		
		layout.operator(
			'create.empty', text=_tr("Arrows"), icon='EMPTY_ARROWS'
		).empty_type='ARROWS'
		
		layout.operator(
			'create.empty', text=_tr("Single Arrows"), icon='EMPTY_SINGLE_ARROW'
		).empty_type='SINGLE_ARROW'

		layout.operator(
			'create.empty', text=_tr("Circle"), icon='MESH_CIRCLE'
		).empty_type='CIRCLE'
		
		layout.operator(
			'create.empty', text=_tr("Cube"), icon='CUBE'
		).empty_type='CUBE'
		
		layout.operator(
			'create.empty', text=_tr("Sphere"), icon='SPHERE'
		).empty_type='SPHERE'
		
		layout.operator(
			'create.empty', text=_tr("Cone"), icon='CONE'
		).empty_type='CONE'
		
		layout.operator(
			'create.empty', text=_tr("Image"), icon='FILE_IMAGE'
		).empty_type='IMAGE'


# Image create menu
class BsMax_MT_ImageCreate(Menu):
	bl_idname = 'BSMAX_MT_image_create_menu'
	bl_label = "Image"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.image', text=_tr("Refrence"), icon='IMAGE_REFERENCE'
		).image_type='REFERENCE'
		
		layout.operator(
			'create.image', text=_tr("BackGround"), icon='IMAGE_BACKGROUND'
		).image_type='BACKGROUND'


# Light create menu
class BsMax_MT_LightCreate(Menu):
	bl_idname = "BSMAX_MT_light_create_menu"
	bl_label = "Light"

	def draw(self,  ctx):
		layout = self.layout
		layout.operator(
			'create.pointlight', text=_tr("Point"), icon='LIGHT_POINT'
		)

		layout.operator(
			'create.sunlight', text=_tr("Sun"), icon='LIGHT_SUN'
		)

		layout.operator(
			'create.spotlight', text=_tr("Spot Light Free/Target"),
			icon='LIGHT_SPOT'
		)

		layout.operator(
			'create.arealight', text=_tr("Free Area"),icon='LIGHT_AREA'
		).free = True

		layout.operator(
			'create.arealight', text=_tr("Target Area"),icon='LIGHT_AREA'
		)


# Light Probs create menu
class BsMax_MT_LightProbsCreate(Menu):
	bl_idname = 'BSMAX_MT_lightProbs_primitives'
	bl_label = "Light Probe"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.light_probe_cubemap',
			text=_tr("Reflection Cubemap"), icon='LIGHTPROBE_SPHERE'
		)
		
		layout.operator(
			'create.light_probe_planer',
			text=_tr("Reflection Plane"), icon='LIGHTPROBE_PLANE'
		)
		
		layout.operator(
			'create.light_probe_grid',
			text=_tr("Irradiance Volume"), icon='LIGHTPROBE_VOLUME'
		)


# Camera create menu
class BsMax_MT_CameraCreate(Menu):
	bl_idname = "BSMAX_MT_camera_create_menu"
	bl_label = "Camera"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.camera',
			text=_tr("Camera Free/Target"), icon='OUTLINER_OB_CAMERA'
		)
		
		layout.operator(
			'camera.create_from_view', icon='OUTLINER_OB_CAMERA'
		)


# Speaker create menu
class BsMax_MT_SpeakerCreate(Menu):
	bl_idname = 'BSMAX_MT_speakercreatemenu'
	bl_label = "Speaker"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.speaker', text=_tr("Speaker"), icon='OUTLINER_OB_SPEAKER'
		)


# Force field create menu
class BsMax_MT_ForceFieldCreate(Menu):
	bl_idname = 'BSMAX_MT_forcefield_cecreate_menu'
	bl_label = "Force field"

	def draw(self, ctx):
		layout = self.layout
		layout.operator(
			'create.effector', text=_tr("Force"), icon='FORCE_FORCE'
		).effector_type = 'FORCE'

		layout.operator(
			'create.effector', text=_tr("Wind"), icon='FORCE_WIND'
		).effector_type = 'WIND'

		layout.operator(
			'create.effector', text=_tr("Vortex"), icon='FORCE_VORTEX'
		).effector_type = 'VORTEX'

		layout.operator(
			'create.effector', text=_tr("Magnet"), icon='FORCE_MAGNETIC'
		).effector_type = 'MAGNET'

		layout.operator(
			'create.effector', text=_tr("Harmonic"), icon='FORCE_HARMONIC'
		).effector_type = 'HARMONIC'

		layout.operator(
			'create.effector', text=_tr("Charge"), icon='FORCE_CHARGE'
		).effector_type = 'CHARGE'

		layout.operator(
			'create.effector', text=_tr("Lennardj"), icon='FORCE_LENNARDJONES'
		).effector_type = 'LENNARDJ'

		layout.operator(
			'create.effector', text=_tr("Texture"), icon='FORCE_TEXTURE'
		).effector_type = 'TEXTURE'

		layout.operator(
			'create.effector', text=_tr("Guide"), icon='FORCE_CURVE'
		).effector_type = 'GUIDE'

		layout.operator(
			'create.effector', text=_tr("Boid"), icon='FORCE_BOID'
		).effector_type = 'BOID'

		layout.operator(
			'create.effector', text=_tr("Turbulence"), icon='FORCE_TURBULENCE'
		).effector_type = 'TURBULENCE'

		layout.operator(
			'create.effector', text=_tr("Drag"), icon='FORCE_DRAG'
		).effector_type = 'DRAG'

		layout.operator(
			'create.effector', text=_tr("Smoke"), icon='FORCE_FLUIDFLOW'
		).effector_type = 'SMOKE'


def mesh_add_append_menu(self, _):
	layout = self.layout
	layout.separator()
	layout.operator_context = "EXEC_DEFAULT"
	layout.operator(
		'object.create', text=_tr("Plane"), icon='MESH_PLANE'
	).type='PLANE'

	layout.operator(
		'object.create', text=_tr("Box"), icon='MESH_CUBE'
	).type='BOX'

	layout.operator(
		'object.create', text=_tr("Cone"), icon='MESH_CONE'
	).type='CONE'

	layout.operator(
		'object.create', text=_tr("Sphere"), icon='MESH_UVSPHERE'
	).type='SPHERE'

	layout.operator(
		'object.create', text=_tr("IcoSphere"), icon='MESH_ICOSPHERE'
	).type='ICOSPHERE'

	layout.operator(
		'object.create', text=_tr("Capsule"), icon='META_CAPSULE'
	).type='CAPSULE'

	layout.operator(
		'object.create', text=_tr("OilTank"), icon='META_CAPSULE'
	).type='OILTANK'

	layout.operator(
		'object.create', text=_tr("Cylinder"), icon='MESH_CYLINDER'
	).type='CYLINDER'

	layout.operator(
		'object.create', text=_tr("Tube"), icon='MESH_TORUS'
	).type='TUBE'

	layout.operator(
		'object.create', text=_tr("Torus"), icon='MESH_TORUS'
	).type='TORUS'

	layout.operator(
		'object.create', text=_tr("Pyramid"), icon='MARKER'
	).type='PYRAMID'
	
	layout.operator(
		'object.create', text=_tr("QuadSphere"), icon='SHADING_WIRE'
	).type='QUADSPHERE'

	layout.operator(
		'object.create', text=_tr("Teapot"), icon='NODE_MATERIAL'
	).type='TEAPOT'

	layout.operator(
		'object.create', text=_tr("Monkey"), icon='MESH_MONKEY'
	).type='MONKEY'

	layout.operator(
		'object.create', text=_tr("Bolt"), icon='TOOL_SETTINGS'
	).type='BOLT'

	# layout.separator()
	# layout.menu('BSMAX_MT_vertex_create_menu', icon='DOT').type=''


def curve_add_append_menu(self, ctx):
	layout = self.layout
	layout.separator()
	layout.operator_context = 'EXEC_DEFAULT'

	layout.operator(
		'object.create', text=_tr("Rectangle"), icon='META_PLANE'
	).type='RECTANGLE'

	layout.operator(
		'object.create', text=_tr("Circle"), icon='MESH_CIRCLE'
	).type='CIRCLE'

	layout.operator(
		'object.create', text=_tr("Ellipse"), icon='MESH_CAPSULE'
	).type='ELLIPSE'

	layout.operator(
		'object.create', text=_tr("Arc"), icon='SPHERECURVE'
	).type='ARC'

	layout.operator(
		'object.create', text=_tr("Donut"), icon='MESH_CIRCLE'
	).type='DONUT'

	layout.operator(
		'object.create', text=_tr("Ngon"), icon='SEQ_CHROMA_SCOPE'
	).type='NGON'

	layout.operator(
		'object.create', text=_tr("Start"), icon='SOLO_OFF'
	).type='STAR'

	layout.operator(
		'object.create', text=_tr("TorusKnot"), icon='HAND'
	).type='TORUSKNOT'

	layout.operator(
		'object.create', text=_tr("Helix"), icon='MOD_SCREW'
	).type='HELIX'

	layout.operator(
		'object.create', text=_tr("Profilo"), icon='MOD_BOOLEAN'
	).type='PROFILO'


def create_menu(self, ctx):
	layout = self.layout
	row = layout.row()
	row.prop(
		ctx.scene.primitive_setting, 'draw_mode', text=_tr("")
	)

	layout.separator()
	layout.menu(
		'BSMAX_MT_mesh_create_menu', icon='OUTLINER_OB_MESH'
	)

	layout.menu(
		'BSMAX_MT_curve_create_menu', icon='OUTLINER_OB_CURVE'
	)

	layout.menu(
		'BSMAX_MT_surface_create_menu', icon='OUTLINER_OB_SURFACE'
	)

	layout.menu(
		'BSMAX_MT_metaball_create_menu', icon='OUTLINER_OB_META'
	)

	layout.menu(
		'BSMAX_MT_text_create_menu', icon='OUTLINER_OB_FONT'
	)

	layout.menu(
		'BSMAX_MT_gracepencil_create_menu', icon='OUTLINER_OB_GREASEPENCIL'
	)

	layout.separator()
	layout.menu(
		'BSMAX_MT_armature_create_menu', icon='OUTLINER_OB_ARMATURE'
	)

	layout.menu(
		'BSMAX_MT_lattice_create_menu', icon='OUTLINER_OB_LATTICE'
	)

	layout.separator()
	layout.menu(
		'BSMAX_MT_empty_create_menu', icon='OUTLINER_OB_EMPTY'
	)

	layout.menu(
		'BSMAX_MT_image_create_menu', icon='OUTLINER_OB_IMAGE'
	)

	layout.separator()
	layout.menu(
		'BSMAX_MT_light_create_menu', icon='OUTLINER_OB_LIGHT'
	)

	layout.menu(
		'BSMAX_MT_lightProbs_primitives', icon='OUTLINER_OB_LIGHTPROBE'
	)

	layout.separator()
	layout.menu(
		'BSMAX_MT_camera_create_menu', icon='OUTLINER_OB_CAMERA'
	)

	layout.separator()
	layout.operator(
		'create.speaker', icon='OUTLINER_OB_SPEAKER'
	)

	layout.separator()
	layout.menu(
		'BSMAX_MT_forcefield_cecreate_menu', icon='OUTLINER_OB_FORCE_FIELD'
	)
	# OUTLINER_OB_GROUP_INSTANCE


def objects_context_menu(self, _):
	layout = self.layout
	layout.separator()
	layout.operator('primitive.cleardata', text=_tr("Clear Primitive Data"))


def CreateMenu_CallBack(self, ctx):
	if ctx.mode == 'OBJECT':
		self.layout.menu('BSMAX_MT_create_menu')


classes = {
	BsMax_MT_VertexCreate,
	BsMax_MT_Mesh_Extera,
	BsMax_MT_MeshCreate,
	BsMax_MT_CurveCreate,
	BsMax_MT_SurfaceCreate,
	BsMax_MT_MetaballCreate,
	BsMax_MT_TextCreate,
	BsMax_MT_GreacePencilCreate,
	BsMax_MT_ArmatureCreate,
	BsMax_MT_LatticeCreate,
	BsMax_MT_EmptyCreate,
	BsMax_MT_ImageCreate,
	BsMax_MT_LightCreate,
	BsMax_MT_LightProbsCreate,
	BsMax_MT_CameraCreate,
	BsMax_MT_SpeakerCreate,
	BsMax_MT_ForceFieldCreate
}


def register_menu():
	for cls in classes:
		register_class(cls)

	#TODO find a way to put Create menu anfter add menu rather than first of the list
	None
	None
	None
	None
	None


def unregister_menu():
	None  
	None
	None
	None
	None

	for cls in classes:
		unregister_class(cls)


if __name__ == '__main__':
	register_menu()