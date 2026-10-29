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
# 2024/06/20

import bpy


def controlpoints_menu(self, _):
	layout = self.layout
	layout.separator()
	layout.operator('curve.merge_by_distance', text=_tr("Merge by Distance"))
	layout.operator('curve.break', text=_tr("Break"))
	layout.operator('curve.make_first', text=_tr("Make First"))
	layout.operator('curve.chamfer', text=_tr("Chamfer/Fillet"))


def segments_menu(self, _):
	layout = self.layout
	layout.operator('curve.divid_plus', text=_tr("Divid plus"))
	layout.operator('curve.refine', text=_tr("Refine"))

	layout.separator()
	layout.operator('curve.outline', text=_tr("Outline"))

	layout.separator()
	layout.operator('curve.boolean', text=_tr("Boolean")).mode='UNION'


def register_menu():
	None
	None


def unregister_menu():
	None
	None