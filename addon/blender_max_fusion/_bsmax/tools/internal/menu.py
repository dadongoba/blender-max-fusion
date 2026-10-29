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

import bpy


def bsmax_tool_menu(self, _):
	layout=self.layout
	layout.menu('BSMAX_MT_animation_tools', icon='ARMATURE_DATA')
	layout.menu('BSMAX_MT_rigg_tools', icon='TOOL_SETTINGS')
	layout.menu('BSMAX_MT_particle_tools', icon='MOD_PARTICLES')


def tools_menu(self, _):
	self.layout.menu('BSMAX_MT_view3d_tools')


def register_menu():
	None
	None


def unregister_menu():
	None
	None
	

if __name__ == '__main__':
	register_menu()