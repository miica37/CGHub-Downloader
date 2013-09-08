
#  Based on PyQt4\examples\itemviews\basicsortfiltermodel.pyw

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from usersdata import UsersData

class DatViewerWindow(QMainWindow):
	def __init__(self, parent=None):
		super(DatViewerWindow, self).__init__(parent)
		
		#  Keyboard shortcuts
		#  ----------------------------------------
		shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
		self.connect(shortcut, SIGNAL('activated()'), self.deleteLater)

		#  Setup Main UI elements
		#  ----------------------------------------
		centralwidget = QWidget(self)
		self.setCentralWidget(centralwidget)
		
		vertical_Layout = QVBoxLayout(centralwidget)
		proxy_GroupBox = QGroupBox("Users List")
		vertical_Layout.addWidget(proxy_GroupBox)
		proxy_Layout = QVBoxLayout(proxy_GroupBox)
		
		self.proxyView = QTreeView()
		self.proxyView.setRootIsDecorated(False)
		self.proxyView.setAlternatingRowColors(True)
		self.proxyView.setSortingEnabled(True)
		self.proxyView.setSelectionMode(self.proxyView.ExtendedSelection)
		proxy_Layout.addWidget(self.proxyView)
		
		#  Create Model
		#  ----------------------------------------
		self._usersdata = UsersData()
		
		NAME, VALID, DIRTY, URL, IMAGES, HTML = range(6)
		self.model = QStandardItemModel( 0, 6, self )
		self.model.setHeaderData( NAME, Qt.Horizontal, "Name" )
		self.model.setHeaderData( VALID, Qt.Horizontal, "Exists" )
		self.model.setHeaderData( DIRTY, Qt.Horizontal, "Dirty" )
		self.model.setHeaderData( URL, Qt.Horizontal, "Url" )
		self.model.setHeaderData( IMAGES, Qt.Horizontal, "Images" )
		self.model.setHeaderData( HTML, Qt.Horizontal, "Html" )
		
		for userobj in self._usersdata.getUsers():
			self.addUser(self.model, userobj.name, userobj.exists, \
				userobj.isDirty, userobj.viewImageUrl, str(userobj.images), userobj.userpagehtml[:10])
		
		self.proxyModel = QSortFilterProxyModel()
		self.proxyModel.setDynamicSortFilter(True)
		self.proxyModel.setSourceModel(self.model)
		self.proxyView.setModel(self.proxyModel)
		
		#  Create Menubar
		#  ----------------------------------------
		editMenu = self.menuBar().addMenu("&Edit")
		editDeleteAction = self.createAction("Delete", self.deleteUser, "Delete", None, "Delete selected items.")
		editMarkDirtyAction = self.createAction("Mark Dirty", self.markDirty, "Alt+D", None, "Mark selected users as dirty")
		editSaveAction = self.createAction("Save", self.save, "Ctrl+S", None, "Save edits")
		self.addActions(editMenu, (editDeleteAction, editMarkDirtyAction, editSaveAction))
		
		#  Finalize setup
		#  ----------------------------------------
		self.setWindowTitle( "Dat Viewer" )
		self.resize( 600, 500 )
	
	def markDirty(self):
		pass

	def deleteUser( self ):
		# This is how you delete selected rows from QTableView!

		#  Get selected users
		#  ----------------------------------------
		# Note: gen is NOT a list, but a special type called generator.
		# I have no idea what is the generator type, but I see it
		# can be iterated like a list.
		gen = ( self.proxyModel.mapToSource(i) for i in self.proxyView.selectedIndexes() ) 
		
		selectedUser = []
		for i in gen:
			if self.model.itemFromIndex(i).data( Qt.UserRole ).toPyObject() == 'user':
				user = self.model.itemFromIndex(i).text()   # 'itemFromIndex()' returns QStandardItem
				selectedUser.append( user )
				self.users.deleteUserNoSave( str(user) )

		#  Get selected rows
		#  ----------------------------------------
		selectedRows = []
		for i in self.proxyView.selectedIndexes():
			if i.row() not in selectedRows:
				selectedRows.append( i.row() )
		
		#  Delete selected rows
		#  ----------------------------------------
		for inc, i in enumerate( selectedRows ):
			self.proxyModel.removeRow( i-inc if i is not 0 else 0 )
		
	def save(self):
		self._usersdata.savePickle()

	def createAction( self, text, slot=None, shortcut=None, icon=None, \
		tip=None, checkable=False, signal="triggered()" ):
		# ( Copied from Rapid GUI Programming with Python and Qt,
		#		Chapter 6, imagechanger.py )
		action = QAction(text, self)
		if icon is not None:
			action.setIcon(QIcon(":/%s.png" % icon))
		if shortcut is not None:
			action.setShortcut(shortcut)
		if tip is not None:
			action.setToolTip(tip)
			action.setStatusTip(tip)
		if slot is not None:
			self.connect(action, SIGNAL(signal), slot)
		if checkable:
			action.setCheckable(True)
		return action

	def addActions(self, target, actions):
		# ( Copied from Rapid GUI Programming with Python and Qt,
		#		Chapter 6, imagechanger.py )
		for action in actions:
			if action is None:
				target.addSeparator()
			else:
				target.addAction(action)

	def addUser(self, model, name, valid, dirty, viewImagePageUrl, images, html):
		NAME, VALID, DIRTY, URL, IMAGES, HTML = range(6)
		
		model.insertRow(0)
		model.setData(model.index(0,NAME), name)
		model.setData(model.index(0,NAME), QVariant('user'), Qt.UserRole)
		model.setData(model.index(0,VALID), valid)
		model.setData(model.index(0,DIRTY), dirty)
		model.setData(model.index(0,URL), viewImagePageUrl)
		model.setData(model.index(0,IMAGES), images)
		model.setData(model.index(0,HTML), html)

if __name__ == '__main__':
	import sys
	app = QApplication(sys.argv)
	window = DatViewerWindow()
	window.show()
	sys.exit( app.exec_() )
