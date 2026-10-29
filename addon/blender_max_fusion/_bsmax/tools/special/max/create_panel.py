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
# 2024/03/03

import bpy

from bpy.types import Panel
from bpy.utils import register_class, unregister_class


def get_draw_alignment_ui(ctx, layout):
	box = layout.box()
	row = box.row()
	row.label(text=_tr('Drawing Gride'))
	row.prop(
		ctx.scene.primitive_setting, 'draw_mode',
		text=_tr(''), expand=True
	)


def get_create_mesh_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'mesh_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	
	box = layout.box()
	if cPanel.mesh_types == 'STANDARD':
		row = box.row()
		row.operator("create.box", text=_tr("Box"))
		row.operator("create.cone", text=_tr("Cone"))
		row = box.row()
		row.operator("create.sphere", text=_tr("Sphere"))
		row.operator("create.sphere", text=_tr("GeoSphere"))
		row = box.row()
		row.operator("create.cylinder", text=_tr("Cylinder"))
		row.operator("create.tube", text=_tr("Tube"))
		row = box.row()
		row.operator("create.torus", text=_tr("Torus"))
		row.operator("create.pyramid", text=_tr("Pyramid"))
		row = box.row()
		row.operator("create.teapot", text=_tr("Teapot"))
		row.operator("create.plane", text=_tr("Plane"))
		row = box.row()
		row.operator("create.text", text=_tr("TextPlus"))

	elif cPanel.mesh_types == 'EXTENDED':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Hedra"))
		row.operator("bsmax.reserved", text=_tr("Torus Knot"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("ChamferBox"))
		row.operator("bsmax.reserved", text=_tr("ChamferCyl"))
		row = box.row()
		row.operator("create.oiltank", text=_tr("OilTank"))
		row.operator("create.capsule", text=_tr("Capsule"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Spindle"))
		row.operator("bsmax.reserved", text=_tr("L-Ext"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Gengon"))
		row.operator("bsmax.reserved", text=_tr("C-Ext"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("RingWave"))
		row.operator("bsmax.reserved", text=_tr("Hose"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Prism"))
	
	elif cPanel.mesh_types == 'COMPOUND':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Morph"))
		row.operator("bsmax.reserved", text=_tr("Scatter"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Conform"))
		row.operator("bsmax.reserved", text=_tr("Connect"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("BlobMesh"))
		row.operator("bsmax.reserved", text=_tr("ShapeMerg"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Terrain"))
		row.operator("bsmax.reserved", text=_tr("Loft"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Mesher"))
		row.operator("bsmax.reserved", text=_tr("ProBooleeean"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("ProCutter"))
		row.operator("bsmax.reserved", text=_tr("Booleean"))

	elif cPanel.mesh_types == 'PARTICLE':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("PF Source"))
		row.operator("bsmax.reserved", text=_tr("Spray"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Snow"))
		row.operator("bsmax.reserved", text=_tr("Super Spray"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Blizzard"))
		row.operator("bsmax.reserved", text=_tr("PArray"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("PCloud"))

	elif cPanel.mesh_types == 'PATHGRIDE':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Quad Patch"))
		row.operator("bsmax.reserved", text=_tr("Tri Patch"))

	elif cPanel.mesh_types == 'BODY':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Body Utility"))
		row.operator("bsmax.reserved", text=_tr("Body Object"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Join Bodies"))
		row.operator("bsmax.reserved", text=_tr("Body Cutter"))

	elif cPanel.mesh_types == 'NURBS':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Point Surf"))
		row.operator("bsmax.reserved", text=_tr("CV Surf"))
	
	elif cPanel.mesh_types == 'ARCHITECTURE':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("AEC Foliage"))
		row.operator("bsmax.reserved", text=_tr("AEC Railing"))
		# Wall
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Wall"))
		row = box.row()
		# Doors
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Pivot Door"))
		row.operator("bsmax.reserved", text=_tr("Sliding Door"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("BiFold Door"))
		row = box.row()
		# Stairs
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Straight Stair"))
		row.operator("bsmax.reserved", text=_tr("L-Type Stair"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("U-Type Stair"))
		row.operator("bsmax.reserved", text=_tr("Spiral Stair"))
		row = box.row()
		# Windows
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Awning Window"))
		row.operator("bsmax.reserved", text=_tr("Casement Window"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Fixed Window"))
		row.operator("bsmax.reserved", text=_tr("Pivoted Window"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Projected Window"))
		row.operator("bsmax.reserved", text=_tr("Sliding Window"))

	elif cPanel.mesh_types == 'POINTCLOUD':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("PointCloud"))

	elif cPanel.mesh_types == 'DYNAMIC':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Spring"))
		row.operator("bsmax.reserved", text=_tr("Damper"))

	elif cPanel.mesh_types == 'ABC':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Alembic"))
		row.operator("bsmax.reserved", text=_tr("Procedural"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Volume"))
		row.operator("bsmax.reserved", text=_tr("USD"))

	elif cPanel.mesh_types == 'FLUIDS':
		row = box.row()
		row.operator("object.quick_smoke", text=_tr("ُQuick Smoke"))
		row.operator("object.quick_fur", text=_tr("ُQuick Fur"))
		row = box.row()
		row.operator("object.quick_explode", text=_tr("ُQuick Explod"))
		row.operator("object.quick_liquid", text=_tr("ُQuick Liquid"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Fluid Loader"))


def get_create_curve_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'curve_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	box = layout.box()

	if cPanel.curve_types == 'SPLINE':
		row = box.row()
		row.operator("create.line", text=_tr("Line"))
		row.operator("create.rectangle", text=_tr("Rectangle"))
		row = box.row()
		row.operator("create.circle", text=_tr("Circle"))
		row.operator("create.ellipse", text=_tr("Elipse"))
		row = box.row()
		row.operator("create.arc", text=_tr("Arc"))
		row.operator("create.donut", text=_tr("Donut"))
		row = box.row()
		row.operator("create.ngon", text=_tr("NGon"))
		row.operator("create.star", text=_tr("Star"))
		row = box.row()
		row.operator("create.text", text=_tr("Text"))
		row.operator("create.helix", text=_tr("Helix"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Egg"))
		row.operator("bsmax.reserved", text=_tr("Section"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Freehand"))
		row.operator("create.torusknot", text=_tr("Tors Knot"))
	
	elif cPanel.curve_types == 'NURBS':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Point Curve"))
		row.operator("bsmax.reserved", text=_tr("CV Curve"))

	elif cPanel.curve_types == 'COMPOUND':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("ShpBoolean"))

	elif cPanel.curve_types == 'EXTENDED':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("WRectangle"))
		row.operator("bsmax.reserved", text=_tr("Chanel"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Angle"))
		row.operator("bsmax.reserved", text=_tr("Tee"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Wide Flange"))

	elif cPanel.curve_types == 'CREATIONGRAPH':
		pass


def get_create_light_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'light_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	box = layout.box()

	if cPanel.light_types == 'PHOTOMETRIC':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Target Light"))
		row.operator("bsmax.reserved", text=_tr("Free Light"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Sun Positioner"))

	elif cPanel.light_types == 'STANDARD':
		row = box.row()
		row.operator("create.pointlight", text=_tr("Point"))
		row.operator("create.spotlight", text=_tr("Spot"))
		row = box.row()
		row.operator("create.arealight", text=_tr("Area")).free=True
		row.operator("create.arealight", text=_tr("Area Target"))
		row = box.row()
		row.operator("create.sunlight", text=_tr("Sun"))

	elif cPanel.light_types == 'ARNOLD':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Arnold"))


def get_create_camera_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'camera_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	box = layout.box()

	if cPanel.camera_types == 'STANDARD':
		row = box.row()
		row.operator("create.camera", text=_tr("Camera"))

	elif cPanel.camera_types == 'ARNOLD':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Vr Camera"))
		row.operator("bsmax.reserved", text=_tr("Fisheye"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Spherical"))
		row.operator("bsmax.reserved", text=_tr("Cylindrical"))


def get_create_empty_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'empty_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	box = layout.box()

	if cPanel.empty_types == 'STANDARD':
		row = box.row()
		row.operator("create.empty", text=_tr("Point axis")).empty_type='PLAIN_AXES'
		row.operator("create.empty", text=_tr("Arrows")).empty_type='ARROWS'
		row = box.row()
		row.operator("create.empty", text=_tr("Single Arrow")).empty_type='SINGLE_ARROW'
		row.operator("create.empty", text=_tr("Circle")).empty_type='CIRCLE'
		row = box.row()
		row.operator("create.empty", text=_tr("Cube")).empty_type='CUBE'
		row.operator("create.empty", text=_tr("Sphere")).empty_type='SPHERE'
		row = box.row()
		row.operator("create.empty", text=_tr("Cone")).empty_type='CONE'
		row.operator("create.empty", text=_tr("Image")).empty_type='IMAGE'

		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Dummy"))
		row.operator("bsmax.reserved", text=_tr("Containeer"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Crowd"))
		row.operator("bsmax.reserved", text=_tr("Delegate"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("ExposeeeTm"))
		row.operator("bsmax.reserved", text=_tr("Grid"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Point"))
		row.operator("bsmax.reserved", text=_tr("Tape"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Protractor"))
		row.operator("bsmax.reserved", text=_tr("Influencer"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Arrow"))
		row.operator("bsmax.reserved", text=_tr("Volume"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Compass"))

	elif cPanel.empty_types == 'ATOMOSPHER':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("BoxGizmo"))
		row.operator("bsmax.reserved", text=_tr("ShpereGizmo"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("CylGizmo"))

	elif cPanel.empty_types == 'CAMERAMATCH':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("CamPoint"))

	elif cPanel.empty_types == 'ASSEMBLY':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Luminair"))

	elif cPanel.empty_types == 'MANPULATOR':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Cone Angle"))
		row.operator("bsmax.reserved", text=_tr("Plane Angle"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Slider"))

	elif cPanel.empty_types == 'PFLOW':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Find Target"))
		row.operator("bsmax.reserved", text=_tr("SpeedByIcon"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Initial State"))
		row.operator("bsmax.reserved", text=_tr("Group Select"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Particle Paint"))
		row.operator("bsmax.reserved", text=_tr("Birth Texture"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("mP Solver"))
		row.operator("bsmax.reserved", text=_tr("mP Buoyancy"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("BrithGrid"))
		row.operator("bsmax.reserved", text=_tr("BirthStream"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("mP World"))
		row.operator("bsmax.reserved", text=_tr("BlurWind"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Data Icon"))
		row.operator("bsmax.reserved", text=_tr("RandomWalk"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Test Icon"))

	elif cPanel.empty_types == 'MASSFX':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("UConstraint"))

	elif cPanel.empty_types == 'CAT':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("CATMuscle"))
		row.operator("bsmax.reserved", text=_tr("Muscle Strand"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("CATParent"))

	elif cPanel.empty_types == 'VRML97':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Anchor"))
		row.operator("bsmax.reserved", text=_tr("TouchSensor"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("ProxSensor"))
		row.operator("bsmax.reserved", text=_tr("TimeSensor"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("NavInfo"))
		row.operator("bsmax.reserved", text=_tr("Background"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Fog"))
		row.operator("bsmax.reserved", text=_tr("AudioClip"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Sound"))
		row.operator("bsmax.reserved", text=_tr("BilBoard"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("LOD"))
		row.operator("bsmax.reserved", text=_tr("Inline"))


def get_create_spacewrap_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'spacewrap_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	box = layout.box()

	if cPanel.spacewrap_types == 'FORCE':
		row = box.row()
		row.operator("create.effector", text=_tr("Force")).effector_type='FORCE'
		row.operator("create.effector", text=_tr("Wind")).effector_type='WIND'
		row = box.row()
		row.operator("create.effector", text=_tr("Vortex")).effector_type='VORTEX'
		row.operator("create.effector", text=_tr("Magnet")).effector_type='MAGNET'
		row = box.row()
		row.operator("create.effector", text=_tr("Harmonic")).effector_type='HARMONIC'
		row.operator("create.effector", text=_tr("Charge")).effector_type='CHARGE'
		row = box.row()
		row.operator("create.effector", text=_tr("Lennard-jones")).effector_type='LENNARDJ'
		row.operator("create.effector", text=_tr("Texture")).effector_type='TEXTURE'
		row = box.row()
		row.operator("create.effector", text=_tr("Guide")).effector_type='GUIDE'
		row.operator("create.effector", text=_tr("Boid")).effector_type='BOID'
		row = box.row()
		row.operator("create.effector", text=_tr("Turbulence")).effector_type='TURBULENCE'
		row.operator("create.effector", text=_tr("Drag")).effector_type='DRAG'
		# row = box.row()
		# row.operator("create.effector", text="Smoke").effector_type='SMOKE'

	elif cPanel.spacewrap_types == 'DEFELECTOR':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("POmniFlect"))
		row.operator("bsmax.reserved", text=_tr("SOminiFlect"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("UOmniFlect"))
		row.operator("bsmax.reserved", text=_tr("UDefelector"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("SDefelector"))
		row.operator("bsmax.reserved", text=_tr("Defelector"))
	
	elif cPanel.spacewrap_types == 'DEFORABLE':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("FFD(BOX)"))
		row.operator("bsmax.reserved", text=_tr("FFD(Cyl)"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Wave"))
		row.operator("bsmax.reserved", text=_tr("Ripple"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Displace"))
		row.operator("bsmax.reserved", text=_tr("Confirm"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Bomb"))
	
	elif cPanel.spacewrap_types == 'MODIFIER':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Bend"))
		row.operator("bsmax.reserved", text=_tr("Twist"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Taper"))
		row.operator("bsmax.reserved", text=_tr("Skew"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Noise"))
		row.operator("bsmax.reserved", text=_tr("Stretch"))
	
	elif cPanel.spacewrap_types == 'PARTICLE':
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Vector Field"))


def get_create_setting_ui(ctx, layout, cPanel):
	layout.prop(cPanel, 'setting_types', text=_tr(""))
	get_draw_alignment_ui(ctx, layout)
	box = layout.box()

	if cPanel.setting_types == 'STANDARD':
		row = box.row()
		row.operator("create.bone", text=_tr("Bones"))
		row.operator("bsmax.reserved", text=_tr("Ring Array"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Biped"))
		row.operator("bsmax.reserved", text=_tr("Sunlight"))
		row = box.row()
		row.operator("bsmax.reserved", text=_tr("Daylight"))


def create_next_ui(ctx, layout):
	row = layout.row()
	primitive_setting = ctx.scene.primitive_setting
	if primitive_setting.active_tool:
		row.prop(primitive_setting, 'next_name', text=_tr(''))
		row.prop(primitive_setting, 'next_color', text=_tr(''))


def get_create_panel(layout, ctx):
	cPanel = ctx.scene.command_panel
	layout.prop(cPanel, 'create_type', expand=True)
		
	if cPanel.create_type == 'MESH':
		get_create_mesh_ui(ctx, layout, cPanel)

	elif cPanel.create_type == 'CURVE':
		get_create_curve_ui(ctx, layout, cPanel)
		
	elif cPanel.create_type == 'LIGHT':
		get_create_light_ui(ctx, layout, cPanel)

	elif cPanel.create_type == 'CAMERA':
		get_create_camera_ui(ctx, layout, cPanel)

	elif cPanel.create_type == 'EMPTY':
		get_create_empty_ui(ctx, layout, cPanel)
	
	elif cPanel.create_type == 'SPACEWRAP':
		get_create_spacewrap_ui(ctx, layout, cPanel)

	elif cPanel.create_type == 'SETTING':
		get_create_setting_ui(ctx, layout, cPanel)
	
	create_next_ui(ctx, layout.box())


class SCENE_OP_BsMax_Create_Panel(Panel):
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_label = "Create"
	bl_idname = 'VIEW3D_PT_BsMax_create'
	bl_category = "BsMax"

	@classmethod
	def poll(self, ctx):
		return ctx.scene.command_panel.main_tab == 'CREATE'
	
	def draw(self, ctx):
		get_create_panel(self.layout, ctx)


def register_create_panel():
	register_class(SCENE_OP_BsMax_Create_Panel)


def unregister_create_panel():
	if SCENE_OP_BsMax_Create_Panel.is_registered:
		unregister_class(SCENE_OP_BsMax_Create_Panel)


if __name__ == '__main__':
	register_create_panel()