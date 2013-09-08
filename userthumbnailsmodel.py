
import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class ThumbnailsModel(QAbstractTableModel):
	def __init__(self, usersdata, username, userdir, parent=None):
		super(ThumbnailsModel, self).__init__(parent)
		self._usersdata = usersdata # type -> 'UsersData'
		self._currentuser = None    # type -> 'User'
		self.images = None
		self.imagescount = 0
		self.columncount = 0
		self.rowcount = self.getRowCount()
		self.userdir = userdir      # type -> 'UserDir'
		
		if username == '':
			self.rowcount = 7
			self.columncount = 7
			self.imagescount = 49
		
		if username in self._usersdata.getUsernames():
			self._currentuser = self._usersdata.getUser(username)
			self.images = self._currentuser.images
			self.imagescount = len(self.images)
	
	def setColumnCount(self, columncount):
		if self._currentuser != None:
			self.columncount = columncount
			self.rowcount = self.getRowCount()
			self.emit(SIGNAL("modelReset()"))
		
	def getRowCount(self):
		if self.columncount != 0:
			x = self.imagescount
			return (x / self.columncount) + int(x % self.columncount != 0)
		else:
			return 0
	
	def rowCount(self, parent):
		return self.rowcount
	
	def columnCount(self, parent):
		return self.columncount
	
	def getIndexFromRowColumn(self, row, column):
		""" Note, the row and column is assumed to be zero based integers.
		"""
		return (row * self.columncount) + column

	def data(self, index, role):
		row = index.row()
		column = index.column()
		listindex = self.getIndexFromRowColumn(row, column)
		
		if self._currentuser != None and self._currentuser != '' and listindex < self.imagescount:
			if role == Qt.DisplayRole:
				pass
				# if self._currentuser != None and self._currentuser.images != None:
				# 	return str(self.images[listindex].id)
			
			if role == Qt.TextAlignmentRole:
				return Qt.AlignCenter
			
			if role == Qt.DecorationRole:
				thumbfile = os.path.join(self.userdir.thumbnailspath, self.images[listindex].thumbname)
				if os.path.isfile(thumbfile):
					return QIcon(QPixmap(thumbfile))
			
			if role == Qt.ToolTipRole:
				return self._currentuser.images[listindex].filename

			if role == Qt.CheckStateRole:
				if self._currentuser != None and self._currentuser.images != None:
					checked = self._currentuser.images[listindex].checked
					if checked:
						return QVariant(Qt.Checked)
					else:
						return QVariant(Qt.Unchecked)
	
	def setData(self, index, value, role):
		row = index.row()
		column = index.column()
		listindex = self.getIndexFromRowColumn(row, column)
		
		if self._currentuser != None and self._currentuser != '' and listindex < self.imagescount:
			if role == Qt.CheckStateRole:
				if value == Qt.Checked:
					self._currentuser.images[listindex].checked = True
				else:
					self._currentuser.images[listindex].checked = False
				self._usersdata.savePickle()
				return True
	
	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

	def updateModel(self):
		self.emit(SIGNAL("modelReset()"))
