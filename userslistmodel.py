
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from userslist import USER_DISPLAY_STATUS

class UsersListModel(QAbstractListModel):
	onSelectionChanged = pyqtSignal(QModelIndex)
	
	def __init__(self, userslist):
		super(UsersListModel,self).__init__()
		self._userslist = userslist
		
	def handleSelectionChanged(self, selected, deselected):
		# print selected -> QItemSelection
		# print selected.indexes() -> [QModelIndex]
		if len(selected.indexes()) > 0:
			self.onSelectionChanged.emit(selected.indexes()[0])
	
	def rowCount(self, parent):
		return len(self._userslist.getUsers())
	
	def data(self, index, role):
		if role == Qt.EditRole:
			row = index.row()
			return self._userslist[row][0]

		if role == Qt.DisplayRole:
			row = index.row()
			imagescount = self._userslist[index.row()][2]
			if self._userslist[row][1] == USER_DISPLAY_STATUS.SHOW:
				return "{0} ({1})".format(self._userslist[index.row()][0], imagescount)
		
		# if role == Qt.ToolTipRole:
		# 	return "Hex code: " + self._colors[index.row()].name()

		# if role == Qt.DecorationRole:
		#  	row = index.row()
		# 	value = self._colors[row]
		
		# 	pixmap = QPixmap(26,26)
		# 	pixmap.fill(value)
			
		# 	icon = QIcon(pixmap)
		# 	return icon

	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable

	def updateModel(self):
		self.emit(SIGNAL("modelReset()"))