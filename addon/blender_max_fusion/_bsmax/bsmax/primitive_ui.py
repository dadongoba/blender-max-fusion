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
# 2024/05/21

def get_adaptive_plane_panel(cls, layout):
	layout.label(text=_tr("Adaptive Plane"), icon='MOD_BEVEL')
	col = layout.column(align=True)
	col.prop(cls, 'width', text=_tr("width"))
	col.prop(cls, 'length', text=_tr("length"))
	col.prop(cls, 'thickness', text=_tr("Min Size"))
	col.prop(cls, 'bias', text=_tr("Bias"))


def get_plane_panel(cls, layout):
	layout.label(text=_tr("Plane"), icon='MESH_PLANE')
	col = layout.column(align=True)
	col.prop(cls, 'width', text=_tr("width"))
	col.prop(cls, 'length', text=_tr("length"))

	col = layout.column(align=True)
	col.prop(cls, 'wsegs', text=_tr("WSegs"))
	col.prop(cls, 'lsegs', text=_tr("LSegs"))


def get_box_panel(cls, layout):
	layout.label(text=_tr("Box"), icon='MESH_CUBE')
	col = layout.column(align=True)
	col.prop(cls, 'width', text=_tr("width"))
	col.prop(cls, 'length', text=_tr("length"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'wsegs', text=_tr("WSegs"))
	col.prop(cls, 'lsegs', text=_tr("LSegs"))
	col.prop(cls, 'hsegs', text=_tr("HSegs"))


def get_bolt_panel(cls, layout):
	layout.label(text=_tr("Bolt"), icon='TOOL_SETTINGS')
	col = layout.column()

	# ENUMS
	col.prop(cls, 'bf_Model_Type')
	col.separator()

	# Bit
	if cls.bf_Model_Type == 'bf_Model_Bolt':
		col.prop(cls, 'bf_Bit_Type')
		if cls.bf_Bit_Type == 'bf_Bit_None':
			pass

		elif cls.bf_Bit_Type == 'bf_Bit_Allen':
			col.prop(cls, 'bf_Allen_Bit_Depth')
			col.prop(cls, 'bf_Allen_Bit_Flat_Distance')

		elif cls.bf_Bit_Type == 'bf_Bit_Torx':
			col.prop(cls, 'bf_Torx_Bit_Depth')
			col.prop(cls, 'bf_Torx_Size_Type')

		elif cls.bf_Bit_Type == 'bf_Bit_Philips':
			col.prop(cls, 'bf_Phillips_Bit_Depth')
			col.prop(cls, 'bf_Philips_Bit_Dia')

		col.separator()

	# Head
	if cls.bf_Model_Type == 'bf_Model_Bolt':
		col.prop(cls, 'bf_Head_Type')
		if cls.bf_Head_Type == 'bf_Head_Hex':
			col.prop(cls, 'bf_Hex_Head_Height')
			col.prop(cls, 'bf_Hex_Head_Flat_Distance')

		elif cls.bf_Head_Type == 'bf_Head_12Pnt':
			col.prop(cls, 'bf_12_Point_Head_Height')
			col.prop(cls, 'bf_12_Point_Head_Flat_Distance')
			col.prop(cls, 'bf_12_Point_Head_Flange_Dia')

		elif cls.bf_Head_Type == 'bf_Head_Cap':
			col.prop(cls, 'bf_Cap_Head_Height')
			col.prop(cls, 'bf_Cap_Head_Dia')

		elif cls.bf_Head_Type == 'bf_Head_Dome':
			col.prop(cls, 'bf_Dome_Head_Dia')

		elif cls.bf_Head_Type == 'bf_Head_Pan':
			col.prop(cls, 'bf_Pan_Head_Dia')

		elif cls.bf_Head_Type == 'bf_Head_CounterSink':
			col.prop(cls, 'bf_CounterSink_Head_Dia')

		col.separator()
	# Shank
	if cls.bf_Model_Type == 'bf_Model_Bolt':
		col.label(text=_tr('Shank'))
		col.prop(cls, 'bf_Shank_Length')
		col.prop(cls, 'bf_Shank_Dia')
		col.separator()
	# Nut
	if cls.bf_Model_Type == 'bf_Model_Nut':
		col.prop(cls, 'bf_Nut_Type')
		if cls.bf_Nut_Type == "bf_Nut_12Pnt":
			col.prop(cls, 'bf_12_Point_Nut_Height')
			col.prop(cls, 'bf_12_Point_Nut_Flat_Distance')
			col.prop(cls, 'bf_12_Point_Nut_Flange_Dia')

		else:
			col.prop(cls, 'bf_Hex_Nut_Height')
			col.prop(cls, 'bf_Hex_Nut_Flat_Distance')

	# Thread
	col.label(text=_tr('Thread'))
	if cls.bf_Model_Type == 'bf_Model_Bolt':
		col.prop(cls, 'bf_Thread_Length')

	col.prop(cls, 'bf_Major_Dia')
	col.prop(cls, 'bf_Minor_Dia')
	col.prop(cls, 'bf_Pitch')
	col.prop(cls, 'bf_Crest_Percent')
	col.prop(cls, 'bf_Root_Percent')
	col.prop(cls, 'bf_Div_Count')

	col.separator()
	col.prop(cls, 'height', text=_tr('Scale'))


def get_cone_panel(cls, layout):
	layout.label(text=_tr("Cone"), icon='MESH_CONE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius1"))
	col.prop(cls, 'radius2', text=_tr("Radius2"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'hsegs', text=_tr("Height Segs"))
	col.prop(cls, 'csegs', text=_tr("Cap Segs"))
	col.prop(cls, 'ssegs', text=_tr("Side Segs"))

	col = layout.column(align=True)
	col.prop(cls, 'sliceon', text=_tr("Slice on"))

	if cls.sliceon:
		col.prop(cls, 'sfrom', text=_tr("From"))
		col.prop(cls, 'sto', text=_tr("To"))


def get_sphere_panel(cls, layout):
	layout.label(text=_tr("Sphere"), icon="MESH_UVSPHERE")
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))

	if not cls.seglock:
		col.prop(cls, 'ssegs', text=_tr("Side Segs"))
		col.prop(cls, 'hsegs', text=_tr("Height Segs"))

	else:
		col.prop(cls, 'ssegs', text=_tr("Segments"))

	col.prop(cls, 'seglock', text=_tr("Lock Segments"))
	col.prop(cls, 'bias', text=_tr("Hemisphere"))
	#Col.prop(cls, 'chop')
	col.prop(cls, 'sliceon', text=_tr("Sliceon"))

	if cls.sliceon:
		col.prop(cls, 'sfrom', text=_tr("From"))
		col.prop(cls, 'sto', text=_tr("To"))

	col.prop(cls, 'base', text=_tr("Base"))


def get_icosphere_panel(cls, layout):
	layout.label(text=_tr("Icosphere"), icon='MESH_ICOSPHERE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'wsegs', text=_tr("subdiv"))


def get_capsule_panel(cls, layout):
	layout.label(text=_tr("Capsule"), icon='META_CAPSULE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'center', text=_tr("Center/Overall"))

	col = layout.column(align=True)
	col.prop(cls, 'hsegs', text=_tr("Height segs"))
	col.prop(cls, 'ssegs', text=_tr("Side segs"))

	if not cls.seglock:
		col.prop(cls,'csegs', text=_tr("Cap"))

	col.prop(cls, 'seglock', text=_tr("Segs Lock"))
	col = layout.column(align=True)
	col.prop(cls, 'sliceon', text=_tr("Sliceon"))

	if cls.sliceon:
		col.prop(cls, 'sfrom', text=_tr("From"))
		col.prop(cls, 'sto', text=_tr("To"))


def get_oiltank_panel(cls, layout):
	layout.label(text=_tr("Capsule"), icon='META_CAPSULE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'height', text=_tr("Height"))
	col.prop(cls, 'thickness', text=_tr("Cap Height"))

	col = layout.column(align=True)
	col.prop(cls, 'center', text=_tr("Center/Overall"))

	col = layout.column(align=True)
	#col.prop(cls,"chamfer1", text="Blend")
	col.prop(cls, 'hsegs', text=_tr("Height segs"))
	col.prop(cls, 'ssegs', text=_tr("Side segs"))

	if not cls.seglock:
		col.prop(cls, 'csegs', text=_tr("Cap"))

	col.prop(cls, 'seglock', text=_tr("Segs Lock"))
	col = layout.column(align=True)
	col.prop(cls, 'sliceon', text=_tr("Sliceon"))

	if cls.sliceon:
		col.prop(cls, 'sfrom', text=_tr("From"))
		col.prop(cls, 'sto', text=_tr("To"))


def get_cylinder_panel(cls, layout):
	layout.label(text=_tr("Cylinder"), icon='MESH_CYLINDER')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'hsegs', text=_tr("Height Segs"))
	col.prop(cls, 'csegs', text=_tr("Cap Segs"))
	col.prop(cls, 'ssegs', text=_tr("Side Segs"))

	col = layout.column(align=True)
	col.prop(cls, 'sliceon', text=_tr("Slice on"))

	if cls.sliceon:
		col.prop(cls, 'sfrom', text=_tr("From"))
		col.prop(cls, 'sto', text=_tr("To"))


def get_teapot_panel(cls, layout):
	layout.label(text=_tr("Teapot"), icon='MESH_CYLINDER')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius1"))
	col.prop(cls, 'csegs', text=_tr("Segs"))

	col = layout.column(align=True)
	col.prop(cls, 'bool1', text=_tr("Body"))
	col.prop(cls, 'bool2', text=_tr("Handle"))
	col.prop(cls, 'bool3', text=_tr("Spout"))
	col.prop(cls, 'bool4', text=_tr("Lid"))


def get_tube_panel(cls, layout):
	layout.label(text=_tr("Tube"), icon='MESH_CYLINDER')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius1"))
	col.prop(cls, 'radius2', text=_tr("Radius2"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'hsegs', text=_tr("Height Segs"))
	col.prop(cls, 'csegs', text=_tr("Cap Segs"))
	col.prop(cls, 'ssegs', text=_tr("Side segs"))

	col = layout.column(align=True)
	col.prop(cls, 'sliceon', text=_tr("Slice on"))

	if cls.sliceon:
		col.prop(cls, 'sfrom', text=_tr("From"))
		col.prop(cls, 'sto', text=_tr("To"))


def get_torus_panel(cls, layout):
	layout.label(text=_tr("Torus"), icon='MESH_TORUS')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius1"))
	col.prop(cls, 'radius2', text=_tr("Radius2"))

	col = layout.column(align=True)
	col.prop(cls, 'rotation', text=_tr("Rotation"))
	col.prop(cls, 'twist', text=_tr("Twist"))

	col = layout.column(align=True)
	col.prop(cls, 'ssegs', text=_tr("Segments"))
	col.prop(cls, 'ssegs_b', text=_tr("Sides"))

	col = layout.column(align=True)
	col.prop(cls, 'sliceon')
	if cls.sliceon:
		col.prop(cls, 'sfrom')
		col.prop(cls, 'sto')


def get_torusknot_panel(cls, layout):
	layout.label(text=_tr("TorusKnot"), icon='HAND')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius A"))
	col.prop(cls, 'radius2', text=_tr("Radius B"))
	col.prop(cls, 'height', text=_tr("height Scale"))

	col = layout.column(align=True)
	col.prop(cls, 'turns', text=_tr("P Turns"))
	col.prop(cls, 'twist', text=_tr("Q Twist"))

	col = layout.column(align=True)
	col.prop(cls, 'lsegs', text=_tr("Segments"))
	# col.prop(cls, 'ssegs', text="Sides")


def get_pyramid_panel(cls, layout):
	layout.label(text=_tr("Pyramid"), icon='MARKER')
	col = layout.column(align=True)
	col.prop(cls, 'width', text=_tr("Width"))
	col.prop(cls, 'length', text=_tr("Depth"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'wsegs', text=_tr("Width Segs"))
	col.prop(cls, 'lsegs', text=_tr("Depth Segs"))
	col.prop(cls, 'hsegs', text=_tr("Height Segs"))


def get_quadsphere_panel(cls, layout):
	layout.label(text=_tr("QuadSphere"), icon='SHADING_WIRE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'wsegs', text=_tr("Segments"))
	col.prop(cls, 'bias_np', text=_tr("Factor"))


def get_monkey_panel(cls, layout):
	layout.label(text=_tr("Monkey"),icon='MESH_MONKEY')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))


def get_rectangle_panel(cls, layout):
	layout.label(text=_tr("Rectangle"),icon='META_PLANE')
	col = layout.column(align=True)
	col.prop(cls, 'width', text=_tr("Width"))
	col.prop(cls, 'length', text=_tr("Length"))
	col.prop(cls, 'chamfer1', text=_tr("Corner Radius"))


def get_circle_panel(cls, layout):
	layout.label(text=_tr("Circle"),icon='MESH_CIRCLE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'ssegs', text=_tr("Segments"))


def get_ellipse_panel(cls, layout):
	layout.label(text=_tr("Ellipse"), icon='MESH_CAPSULE')
	col = layout.column(align=True)
	col.prop(cls, 'width', text=_tr("Width"))
	col.prop(cls, 'length', text=_tr("Length"))
	col.prop(cls, 'outline', text=_tr("Outline"))

	if cls.outline:
		col.prop(cls, 'thickness', text=_tr("Thickness"))

def get_arc_panel(cls, layout):
	layout.label(text=_tr("Arc"), icon='SPHERECURVE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius"))
	col.prop(cls, 'sfrom', text=_tr("Start"))
	col.prop(cls, 'sto', text=_tr("End"))
	col.prop(cls, 'sliceon', text=_tr("Pie"))


def get_donut_panel(cls, layout):
	layout.label(text=_tr("Donut"), icon='MESH_CIRCLE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("radius1"))
	col.prop(cls, 'radius2', text=_tr("radius2"))


def get_ngon_panel(cls, layout):
	layout.label(text=_tr("NGon"), icon='SEQ_CHROMA_SCOPE')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("radius"))
	col.prop(cls, 'ssegs', text=_tr("sides"))
	#col.prop(cls, 'chamfer1', text="cornerradius")
	col.prop(cls, 'smooth', text=_tr("circular"))


def get_star_panel(cls, layout):
	layout.label(text=_tr("Star"), icon='SOLO_OFF')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius1"))
	col.prop(cls, 'radius2', text=_tr("Radius2"))
	col.prop(cls, 'ssegs', text=_tr("Points"))
	col.prop(cls, 'twist', text=_tr("Distortion"))
	#col.prop(cls, 'chamfer1', text="filletradius1")
	#col.prop(cls, 'chamfer2', text="filletradius2")
	col.prop(cls, 'seed', text=_tr("Seed"))
	col.prop(cls, 'random', text=_tr("Randval"))


def get_helix_panel(cls, layout):
	layout.label(text=_tr("Helix"), icon='MOD_SCREW')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Radius1"))
	col.prop(cls, 'radius2', text=_tr("Radius2"))
	col.prop(cls, 'height', text=_tr("Height"))

	col = layout.column(align=True)
	col.prop(cls, 'turns', text=_tr("Turns"))
	col.prop(cls, 'ssegs', text=_tr("Segs"))

	col = layout.column(align=True)
	col.prop(cls, 'bias_np', text=_tr("Bias"))

	col = layout.column(align=True)
	row = col.row()
	row.prop(cls, 'ccw', text=_tr("ccw"))
	row.prop(cls, 'bool1', text=_tr("Bezier/Segment"))


def get_profilo_panel(cls, layout):
	layout.label(text=_tr("Profilo"), icon='MOD_BOOLEAN')
	col = layout.column(align=True)
	col.prop(cls, 'profilo_mode')
	col = layout.column(align=True)

	if cls.profilo_mode == 'Angle':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("Width"))
		col.prop(cls, 'thickness', text=_tr("Thickness"))

		col = layout.column(align=True)
		col.prop(cls, 'corner', text=_tr("Sync Corner Fillets"))

		col = layout.column(align=True)
		col.prop(cls, 'chamfer1', text=_tr("Corner Radius1"))

		if not cls.corner:
			col.prop(cls, 'chamfer2', text=_tr("Corner Radius2"))

		col.prop(cls, 'chamfer3', text=_tr("Edge Radius"))

	elif cls.profilo_mode == 'Bar':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("Width"))
		col.prop(cls, 'chamfer1', text=_tr("Corner Radius"))

	elif cls.profilo_mode == 'Channel':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("width"))
		col.prop(cls, 'thickness', text=_tr("Thickness"))

		col = layout.column(align=True)
		col.prop(cls, 'corner', text=_tr("Sync Corner Fillets"))

		col = layout.column(align=True)
		col.prop(cls, 'chamfer1', text=_tr("Corner Radius1"))

		if not cls.corner:
			col.prop(cls, 'chamfer2', text=_tr("Corner Radius2"))

	elif cls.profilo_mode == 'Cylinder':
		col.prop(cls, 'radius1', text=_tr("Radius"))
		col.prop(cls, 'slicefrom', text=_tr("Slice From"))
		col.prop(cls, 'sliceto', text=_tr("Slice To"))

	elif cls.profilo_mode == 'Pipe':
		col.prop(cls, 'radius1', text=_tr("Radius"))
		col.prop(cls, 'thickness', text=_tr("Thickness"))

	elif cls.profilo_mode == 'Tee':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("Width"))
		col.prop(cls, 'thickness', text=_tr("Thickness"))

		col = layout.column(align=True)
		col.prop(cls, 'chamfer1', text=_tr("Corner Radius"))

	elif cls.profilo_mode == 'Tube':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("Width"))
		col.prop(cls, 'thickness', text=_tr("Thickness"))

		col = layout.column(align=True)
		col.prop(cls, 'corner', text=_tr("Sync Corner Fillets"))
		col.prop(cls, 'chamfer1', text=_tr("Corner Radius1"))

		if not cls.corner:
			col.prop(cls, 'chamfer2', text=_tr("Corner Radius2"))

	elif cls.profilo_mode == 'Width_flange':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("Width"))
		col.prop(cls, 'thickness', text=_tr("Thickness"))
		col.prop(cls, 'chamfer1', text=_tr("Corner Radius"))

	elif cls.profilo_mode == 'Elipse':
		col.prop(cls, 'length', text=_tr("Length"))
		col.prop(cls, 'width', text=_tr("Width"))

		col = layout.column(align=True)
		col.prop(cls, 'outline', text=_tr("Outline"))

		if cls.outline:
			col = layout.column(align=True)
			col.prop(cls, 'thickness', text=_tr("Thickness"))

	# Transform
	col = layout.column(align=True)
	row = col.row(align = True)
	row.prop(cls, 'offset_x', text=_tr("Offset X"))
	row.prop(cls, 'offset_y', text=_tr("Offset Y"))

	row = col.row(align = True)
	row.prop(cls, 'mirror_x', text=_tr("Mirror X"))
	row.prop(cls, 'mirror_y', text=_tr("Mirror Y"))

	col = layout.column(align=True)
	col.prop(cls, 'rotation', text=_tr("Angle"))
	
	# Pivot offset
	col = layout.column(align=True)
	row = col.row(align = True)
	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='BLANK1'
	).pivotaligne = 1

	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='TRIA_UP'
	).pivotaligne = 2

	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='BLANK1'
	).pivotaligne = 3

	row = col.row(align = True)
	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='TRIA_LEFT'
	).pivotaligne = 4

	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='DOT'
	).pivotaligne = 5

	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='TRIA_RIGHT'
	).pivotaligne = 6

	row = col.row(align = True)
	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='BLANK1'
	).pivotaligne = 7

	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='TRIA_DOWN'
	).pivotaligne = 8

	row.operator(
		'create.set_profilo_pivotaligne', text=_tr(""), icon='BLANK1'
	).pivotaligne = 9


def get_compass_panel(cls, layout):
	layout.label(text=_tr("Compass"), icon='LIGHT_SUN')
	col = layout.column(align=True)
	col.prop(cls, 'radius1', text=_tr("Icon Size"))


def get_primitive_edit_panel(cls, layout):
	if cls.classname == "Adaptive_Plane":
		get_adaptive_plane_panel(cls, layout)

	elif cls.classname == "Plane":
		get_plane_panel(cls, layout)

	elif cls.classname == "Box":
		get_box_panel(cls, layout)

	elif cls.classname == "Bolt":
		get_bolt_panel(cls, layout)

	elif cls.classname == "Cone":
		get_cone_panel(cls, layout)

	elif cls.classname == "Sphere":
		get_sphere_panel(cls, layout)

	elif cls.classname == "Icosphere":
		get_icosphere_panel(cls, layout)

	elif cls.classname == "Capsule":
		get_capsule_panel(cls, layout)

	elif cls.classname == "OilTank":
		get_oiltank_panel(cls, layout)

	elif cls.classname == "Cylinder":
		get_cylinder_panel(cls, layout)

	elif cls.classname == "Teapot":
		get_teapot_panel(cls, layout)

	elif cls.classname == "Tube":
		get_tube_panel(cls, layout)

	elif cls.classname == "Torus":
		get_torus_panel(cls, layout)

	elif cls.classname == "TorusKnot":
		get_torusknot_panel(cls, layout)

	elif cls.classname == "Pyramid":
		get_pyramid_panel(cls, layout)

	elif cls.classname == "QuadSphere":
		get_quadsphere_panel(cls, layout)

	elif cls.classname == "Monkey":
		get_monkey_panel(cls, layout)

	elif cls.classname == "Rectangle":
		get_rectangle_panel(cls, layout)

	elif cls.classname == "Circle":
		get_circle_panel(cls, layout)

	elif cls.classname == "Ellipse":
		get_ellipse_panel(cls, layout)

	elif cls.classname == "Arc":
		get_arc_panel(cls, layout)

	elif cls.classname == "Donut":
		get_donut_panel(cls, layout)

	elif cls.classname == "NGon":
		get_ngon_panel(cls, layout)

	elif cls.classname == "Star":
		get_star_panel(cls, layout)

	elif cls.classname == "Helix":
		get_helix_panel(cls, layout)

	elif cls.classname == "Profilo":
		get_profilo_panel(cls, layout)

	elif cls.classname == "Compass":
		get_compass_panel(cls, layout)

	col = layout.column(align=True)
	col.prop(cls, 'animatable', text=_tr("Animatable"))