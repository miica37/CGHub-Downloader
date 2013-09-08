
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from projectmanager import convertSize

class UserImagesModel(QAbstractTableModel):
	"""	Model for table view, to display user's images for downloads.
	This model is created separately for each user. If the user is 
	deleted, so should this model.
	"""
	def __init__(self, usersdata, username, parent=None):
		super(UserImagesModel, self).__init__(parent)
		self._usersdata = usersdata	# type -> 'UsersData'
		self._currentuser = None	# type -> 'User'
		self._headers = ['Image\'s  Filenames', 'Status', 'Filesize']
		
		if username in self._usersdata.getUsernames():
			self._currentuser = self._usersdata.getUser(username)
	
	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return self._headers[section]
			else:
				return section+1
		
		if role == Qt.SizeHintRole:
			if orientation == Qt.Horizontal:
				return QSize(0,30)
	
	def rowCount(self, parent):
		if self._currentuser != None and self._currentuser.images != None:
			return len(self._currentuser.images)
		else:
			return 0
	
	def columnCount(self, parent):
		return len(self._headers)

	def data(self, index, role):
		if role == Qt.DisplayRole:
			
			# self._currentuser will be None if it's an empty('') user
			# which we should just display a blank table.
			if self._currentuser != None and self._currentuser.images != None:
				row = index.row()
				column = index.column()
				if column == 0:
					return self._currentuser.images[row].filename
				if column == 1:
					imgobj = self._currentuser.images[row]
					completed = imgobj.completed
					if completed == 100.0:
						return "Complete"
					else:
						if imgobj.filesize_dl != None:
							return "%3.2f%%" % (imgobj.filesize_dl*100.0/imgobj.filesize)
						else:
							return "%3.2f%%" % 0.0
				if column == 2:
					filesize = self._currentuser.images[row].filesize
					if filesize == None:
						return ""
					else:
						filesizeKb = convertSize(filesize/1024.0)
						return filesizeKb
		
		elif role == Qt.TextAlignmentRole: 
			if index.column() == 0:
				return Qt.AlignLeft
			if index.column() == 1:
				return Qt.AlignCenter
			return Qt.AlignRight
		
		if role == Qt.CheckStateRole:
			if self._currentuser != None and self._currentuser.images != None:
				row = index.row()
				column = index.column()
				if column == 0:
					checked = self._currentuser.images[row].checked
					if checked:
						return QVariant(Qt.Checked)
					else:
						return QVariant(Qt.Unchecked)
	
	def setData(self, index, value, role):
		if role == Qt.CheckStateRole:
			row = index.row()
			if value == Qt.Checked:
				self._currentuser.images[row].checked = True
			else:
				self._currentuser.images[row].checked = False
			self._usersdata.savePickle()
			return True
	
	def flags(self, index):
		if index.column() == 0:
			return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
		else:
			return Qt.ItemIsEnabled
	
	def getCheckedItems(self):
		if self._currentuser != None and self._currentuser.images != None:
			return [ imgs for imgs in self._currentuser.images if imgs.checked ]
		return None

	def updateModel(self):
		self.emit(SIGNAL("modelReset()"))
