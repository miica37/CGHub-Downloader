
import os
import sys
import time
import inspect
from functools import partial
from subprocess import call

import requests
from PyQt4.QtCore import *
from PyQt4.QtGui import *

import ui_cghubdownloader
import ui_aboutdialog

import datviewer2
import stylesheets
from settings import *
from projectmanager import ProjectManager
from factory import BaseWorker, Factory
from usersdata import UsersData, User
from userslist import UsersList, USER_DISPLAY_STATUS
from userimagesmodel import UserImagesModel
from userslistmodel import UsersListModel
from userthumbnailsmodel import ThumbnailsModel
from loadwebpage import isInternetConnected

__version__ = '1.0.0'

#  Logging
#  ----------------------------------------
import logging
from logformat import *
logging.basicConfig(filename='log.txt', filemode='w', level=logging.DEBUG, \
	format=LOG_FILE_FORMAT, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger("mainwindow")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(LOG_PRINT_FORMAT, LOG_DATE_FORMAT))
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

logger = logging.getLogger("factoryclass")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(LOG_PRINT_FORMAT, LOG_DATE_FORMAT))
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)


def convertPathToExplorer(path):
	""" Explorer.exe seems to only accept this slash -> '\'
	"""
	return os.path.normpath(path).replace('/', '\\')

class ProcessUserValidation(BaseWorker):
	logger = logging.getLogger("factoryclass.ProcessUserValidation")
	logger.info("Worker for Processing user's validation ready")
	
	def doJob(self, jobdata):
		userobj = jobdata   # renamed for clarity
		
		logging.info("Check if {0} exists".format(userobj.name))
		ok, result = userobj.checkIfExists()
		if not ok:
			errormsg = result
			self.emit(SIGNAL("error"), errormsg)
		else:
			(userobj, html) = result
			self.emit(SIGNAL("updateList"), userobj, html)

class ProcessUserImages(BaseWorker):
	logger = logging.getLogger("factoryclass.ProcessUserImages")
	logger.info("Worker for Processing user's images ready")
	
	def doJob(self, jobdata):
		(userobj, projman) = jobdata   # renamed for clarity
		
		logging.info("Getting {0}'s images".format(userobj.name))
		ok, result = userobj.getUserImages()
		if not ok:
			errormsg = result
			self.emit(SIGNAL("error"), errormsg)
		else:
			userobj = result
			self.emit(SIGNAL("updateTable"), userobj)

class CheckImagesFilesize(BaseWorker):
	logger = logging.getLogger("factoryclass.CheckImagesFilesize")
	logger.info("Worker for Checking images file size ready")
	
	def doJob(self, jobdata):
		(usersdata, username) = jobdata   # renamed for clarity
		
		if not isInternetConnected():
			logger.warning("Internet is not connected")
			return None
		
		userobj = usersdata.getUser(username)
		if userobj:
			for imgobj in userobj.images:
				if imgobj.filesize == None:
					logger.info("Getting file size for '{0}'".format(imgobj.imageurl))
					r = requests.get(imgobj.imageurl, stream=True)
					imgobj.filesize = int(r.headers['Content-Length'])
					logger.info("Filesize: {0} bytes".format(imgobj.filesize))
					usersdata.savePickle()
					self.emit(SIGNAL("updateTableModel"))

class LogText( object ):
	ATTENTION_DURATION = 3 # secs
	BRIGHT_COLOR = '#66d9ef'
	DIM_COLOR = '#75715e'
	FONT_ATTRS = " style=\"font-size:11px; font-family:Courier New\" "
	
	class Message(object):
		def __init__(self, time_stamp, msg):
			"""
			__init__(self, time_stamp:float, msg:str)
			"""
			self.timeStamp = time_stamp
			self.message = msg

	def __init__( self ):
		self.textbrowser = QTextBrowser()
		self.textbrowser.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
		self.textbrowser.setMinimumWidth(150)
		self._msgs = [] # Will holds a list of 'Message' class instances
	
	def addNewMsg(self, msg):
		self.textbrowser.clear()
		
		# Print the new message first
		time_ = time.strftime("%M:%S", time.gmtime())
		html = "<font color={0}{1} > {2} > {3}</font>".format(self.BRIGHT_COLOR, self.FONT_ATTRS, time_, msg)
		self.textbrowser.append(html)
		
		# Then print all previous messages
		for msgobj in reversed(self._msgs):
			timediff = time.mktime(time.gmtime()) - msgobj.timeStamp
			color = self.DIM_COLOR if timediff > self.ATTENTION_DURATION else self.BRIGHT_COLOR
			# html = "<font color=%s %s > >>> %s</font>" % (color, self.FONT_ATTRS, msgobj.message)
			time_ = time.strftime("%M:%S", time.gmtime(msgobj.timeStamp))
			html = "<font color=%s %s > %s > %s</font>" % (color, self.FONT_ATTRS, time_, msgobj.message)
			self.textbrowser.append(html)
		self._msgs.append( self.Message(time.mktime(time.gmtime()), msg) )
		
		self.textbrowser.verticalScrollBar().setValue(0)   # Scroll to the top

class AboutDialog(QDialog, ui_aboutdialog.Ui_about_dialog):
	def __init__(self, parent=None):
		super(AboutDialog, self).__init__(parent)
		self.setupUi(self)
		self.ok_buttonWidget.clicked.connect(self.deleteLater)

class MainWindow(QMainWindow, ui_cghubdownloader.Ui_CGHubDownloader):
	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		
		#  Start logging
		#  ----------------------------------------
		logger = logging.getLogger("mainwindow.__init__")
		
		#  Member variables and init stuffs
		#  ----------------------------------------
		self.projdir = os.path.join(os.getcwd(), 'Downloads')
		
		if not os.path.isdir(self.projdir):
			os.makedirs(self.projdir)
		
		self.addedUsers = []
		self.currentuser = ''
		self.currentusermodel = None         # holds UserImagesModel
		self.currentthumbnailsmodel = None   # holds ThumbnailsModel
		self.currentview = 0   # 0 -> Table view, 1 -> Thumbnails view
		self.setupUi(self)
		
		#  Factory
		#  ----------------------------------------
		self.factory = Factory()
		self.factory.addClass('UserValidation', ProcessUserValidation)
		self.factory.addWorkers('UserValidation')
		self.factory.addClass('UserImages', ProcessUserImages)
		self.factory.addWorkers('UserImages')
		self.factory.addClass('ImagesFilesize', CheckImagesFilesize)
		self.factory.addWorkers('ImagesFilesize')
		
		for worker in self.factory.getWorkers('UserValidation'):
			self.connect(worker, SIGNAL('error'), self.callError)
			self.connect(worker, SIGNAL('updateList'), self.refreshUserList)
		
		for worker in self.factory.getWorkers('UserImages'):
			self.connect(worker, SIGNAL('error'), self.callError)
			self.connect(worker, SIGNAL('updateTable'), self.refreshTableView)
		
		for worker in self.factory.getWorkers('ImagesFilesize'):
			self.connect(worker, SIGNAL('updateTableModel'), self.updateTableModel)
		
		#  Users data
		#  ----------------------------------------
		self.usersdata = UsersData(self)
		self.usersdata.setProjectDir(self.projdir)
		self.usersdata.error.connect(self.callError) # SIGNAL("error()")
		self.userslistdata = UsersList(self.usersdata)
		self.userslistdata.setProjectDir(self.projdir)
		self.userslistdata.updateFromUsersData(self.usersdata)
		
		for worker in self.factory.getWorkers('UserImages'):
			self.connect(worker, SIGNAL('updateTable'), self.userslistdata.updateImagesCount)
		
		#  Project manager
		#  ----------------------------------------
		self.projman = ProjectManager(self.projdir)
		self.projman.updateWithExistingImages(self.usersdata)
		self.projman.saveData.connect(self.saveData) # SIGNAL("saveData()")
		
		#  Users list
		#  ----------------------------------------
		self.userslistmodel = UsersListModel(self.userslistdata)
		self.users_listViewWidget.setModel(self.userslistmodel)
		self.users_listViewWidget.setGridSize(QSize(20,20))
		headerstyle = "font-size: 12px;"
		self.users_listViewWidget.setStyleSheet(headerstyle)
		# Handle selection changed
		selectionmodel = self.users_listViewWidget.selectionModel()
		selectionmodel.selectionChanged.connect(self.userslistmodel.handleSelectionChanged)
		self.userslistmodel.onSelectionChanged.connect(self.onUserSelect)
		
		#  Setup layout inside stacked widget
		#  ----------------------------------------
		#  ( I can't understand how to set this up in Qt Designer,
		#    I can only create layout for one of them, then there
		#    seems to be no way to set layout for the other one )
		self.horizontalLayout_a = QHBoxLayout(self.page)
		self.horizontalLayout_a.addWidget(self.images_tableViewWidget)
		self.horizontalLayout_b = QHBoxLayout(self.page_2)
		self.horizontalLayout_b.addWidget(self.thumbnails_tableViewWidget)
		
		#  Table View
		#  ----------------------------------------
		self.gettablemodel = {}
		self.setTableModel('')
		#  Set table header's font size
		headerstyle = "QHeaderView { font-family: Segoe UI Light; font-size: 12px; }"
		self.images_tableViewWidget.horizontalHeader().setStyleSheet(headerstyle)
		self.images_tableViewWidget.verticalHeader().setStyleSheet(headerstyle)
		#  Set column width
		self.images_tableViewWidget.setColumnWidth(2,100)
		self.images_tableViewWidget.setColumnWidth(1,100)
		self.images_tableViewWidget.horizontalHeader().setResizeMode(1, QHeaderView.Fixed)
		self.images_tableViewWidget.horizontalHeader().setResizeMode(2, QHeaderView.Fixed)
		
		#  Thumbnails View
		#  ----------------------------------------
		self.getthumbnailsmodel = {}
		self.setThumbnailsModel('')
		self.thumbnails_tableViewWidget.setIconSize(QSize(64, 64))
		
		#  Table view popup menu
		#  ----------------------------------------
		self.table_popMenu = QMenu(self)
		checkSelected_Action = QAction('Check Selected', self)
		uncheckSelected_Action = QAction('Uncheck Selected', self)
		checkAll_Action = QAction('Check All', self)
		uncheckAll_Action = QAction('Uncheck All', self)
		viewFile_Action = QAction('View File', self)
		self.connect(checkAll_Action, SIGNAL("triggered()"), partial(self.checkSelected, True))
		self.connect(uncheckAll_Action, SIGNAL("triggered()"), partial(self.checkSelected, False))
		self.connect(checkAll_Action, SIGNAL("triggered()"), partial(self.checkAll, True))
		self.connect(uncheckAll_Action, SIGNAL("triggered()"), partial(self.checkAll, False))
		self.connect(viewFile_Action, SIGNAL("triggered()"), self.viewFile)
		self.table_popMenu.addAction(checkSelected_Action)
		self.table_popMenu.addAction(uncheckSelected_Action)
		self.table_popMenu.addSeparator()
		self.table_popMenu.addAction(checkAll_Action)
		self.table_popMenu.addAction(uncheckAll_Action)
		self.table_popMenu.addSeparator()
		self.table_popMenu.addAction(viewFile_Action)
		self.images_tableViewWidget.setContextMenuPolicy(Qt.CustomContextMenu)
		self.images_tableViewWidget.customContextMenuRequested.connect(self.tableviewPopup)
		
		#  Thumbnails view popup menu
		#  ----------------------------------------
		self.thumbnails_popMenu = QMenu(self)
		thumbCheckSelected_Action = QAction('Check Selected', self)
		thumbUncheckSelected_Action = QAction('Uncheck Selected', self)
		thumbCheckAll_Action = QAction('Check All', self)
		thumbUncheckAll_Action = QAction('Uncheck All', self)
		self.connect(thumbCheckSelected_Action, SIGNAL("triggered()"), partial(self.checkSelected, True))
		self.connect(thumbUncheckSelected_Action, SIGNAL("triggered()"), partial(self.checkSelected, False))
		self.connect(thumbCheckAll_Action, SIGNAL("triggered()"), partial(self.checkAll, True))
		self.connect(thumbUncheckAll_Action, SIGNAL("triggered()"), partial(self.checkAll, False))
		self.thumbnails_popMenu.addAction(thumbCheckSelected_Action)
		self.thumbnails_popMenu.addAction(thumbUncheckSelected_Action)
		self.thumbnails_popMenu.addSeparator()
		self.thumbnails_popMenu.addAction(thumbCheckAll_Action)
		self.thumbnails_popMenu.addAction(thumbUncheckAll_Action)
		self.thumbnails_tableViewWidget.setContextMenuPolicy(Qt.CustomContextMenu)
		self.thumbnails_tableViewWidget.customContextMenuRequested.connect(self.thumbnailsViewPopup)
		
		#  Users list view popup menu
		#  ----------------------------------------
		self.list_popMenu = QMenu(self)
		deleteUser_Action = QAction('Delete user', self)
		self.connect(deleteUser_Action, SIGNAL("triggered()"), self.deleteUser)
		self.list_popMenu.addAction(deleteUser_Action)
		self.users_listViewWidget.setContextMenuPolicy(Qt.CustomContextMenu)
		self.users_listViewWidget.customContextMenuRequested.connect(self.listviewPopup)
		
		#  Set project button popup menu
		#  ----------------------------------------
		self.setproject_buttonWidget.setContextMenuPolicy(Qt.CustomContextMenu)
		self.setproject_buttonWidget.customContextMenuRequested.connect(self.projectButtonPopup)
		self.project_popMenu = QMenu(self)
		openProjectDir_Action = QAction('Open Download location', self)
		self.connect(openProjectDir_Action, SIGNAL("triggered()"), partial(self.openFolder, 'project'))
		self.project_popMenu.addAction(openProjectDir_Action)
		
		#  Avatar
		#  ----------------------------------------
		self.icon = QIcon()
		#  Set default avatar
		self.loadAvatar(":no_avatar100.gif")
		self.username_labelWidget.setText(self.currentuser)
		
		#  Log Dock Widget
		#  ----------------------------------------
		logDockWidget = QDockWidget("Log", self)
		logDockWidget.setObjectName("LogDockWidget")
		logDockWidget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
		self.logtext = LogText()
		self.log_TextBrowser = self.logtext.textbrowser
		logDockWidget.setWidget(self.log_TextBrowser)
		self.addDockWidget(Qt.RightDockWidgetArea, logDockWidget)
		self.log_TextBrowser.setStyleSheet(stylesheets.logArea)
		logDockWidget.hide()
		
		#  Menu Additions
		#  ----------------------------------------
		#  View menu
		viewDatabase_Action = self.createAction('View Database', self.openDatViewer, "Alt+D", None, None, False)
		switchView_Action = self.createAction('Switch view', self.userSwitchView, "Alt+Q", None, None, False)
		# self.menu_View.addAction(logDockWidget.toggleViewAction())
		self.view_Menu.addAction(switchView_Action)
		self.view_Menu.addSeparator()
		self.view_Menu.addAction(viewDatabase_Action)
		#  Help menu
		about_Action = self.createAction('About', self.showAboutDialog, "", None, None, False)
		# self.about_Action.activated.connect(self.showAboutDialog)
		self.help_Menu.addAction(about_Action)
		
		#  Connect Signals and Slots
		#  ----------------------------------------
		#  Main Widgets
		self.adduser_buttonWidget.pressed.connect(self.onAddUser)			# SIGNAL("pressed()")
		self.newuser_lineEditWidget.returnPressed.connect(self.onAddUser)	# SIGNAL("returnPressed()")
		self.users_listViewWidget.doubleClicked.connect(self.onUserSelect)
		
		# Note: I leave out activated signal because I not sure what it does
		# self.users_listViewWidget.activated.connect(self.onUserSelect)
		
		# Note: clicked signal is not used because we already have
		#  self.userslistmodel.onSelectionChanged.connect(self.onUserSelect).
		#  Adding both will double trigger the onUserSelect method which
		#  will cause the view be refresed twice
		# self.users_listViewWidget.clicked.connect(self.onUserSelect)
		
		#  Buttons on left panel
		self.setproject_buttonWidget.clicked.connect(self.setProjectLocation)
		self.download_buttonWidget.clicked.connect(self.downloadSelected)
		self.avatar_buttonWidget.clicked.connect(partial(self.openFolder, 'user'))
		self.tableview_buttonWidget.clicked.connect(partial(self.switchView, 0))
		self.thumbnailview_buttonWidget.clicked.connect(partial(self.switchView, 1))
		#  Actions
		self.test_action.triggered.connect(self.test)
		self.openDatViewer_action.triggered.connect(self.openDatViewer)
				
		#  Finalizing
		#  ----------------------------------------
		self.newuser_lineEditWidget.setFocus()
		self.resize(900,500)
		self.setStatus("Hello", 1.5)
		self.switchView(1)   # Set view to table view
		self.setProjectDir(os.path.join(os.getcwd(), 'Downloads'))
		QTimer.singleShot(0, self.newuser_lineEditWidget, SLOT('setFocus()'))
		
		logger.info("Finish constructing main window")
	
	def createAction( self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False, signal="triggered()" ):
		# ( Copied from Rapid GUI Programming with Python and Qt,
		#		Chapter 6, imagechanger.py )
		action = QAction( text, self )
		if icon is not None:
			action.setIcon( QIcon(":/%s.png" % icon) )
		if shortcut is not None:
			action.setShortcut( shortcut )
		if tip is not None:
			action.setToolTip( tip )
			action.setStatusTip( tip )
		if slot is not None:
			self.connect( action, SIGNAL(signal), slot )
		if checkable:
			action.setCheckable( True )
		return action
	
	#  Non-UI methods
	#  ----------------------------------------
	def test(self):
		pass

	def logCurrentMethod(self, msg):
		methodname = inspect.stack()[1][3]
		logger = logging.getLogger("mainwindow."+methodname)
		logger.info(msg)

	def printToLog(self, msg=''):
		self.logtext.addNewMsg(msg)	
	
	def callWarning(self, msg=''):
		self.logtext.addNewMsg(msg)
		QMessageBox.warning(self, 'Warning', msg)

	def callError(self, msg=''):
		self.logtext.addNewMsg(msg)
		QMessageBox.warning(self, 'Error', msg)
	
	def setStatus(self, msg, secs=3):
		self.statusbar.showMessage(msg, secs*1000)
	
	def saveData(self):
		self.logCurrentMethod("Saving self.usersdata")
		self.usersdata.savePickle()
	
	def loadAvatar(self, avatarpath):
		self.logCurrentMethod("Loading avatar: {0}".format(avatarpath))
		self.icon.addPixmap(QPixmap(avatarpath), QIcon.Normal, QIcon.Off)
		self.avatar_buttonWidget.setIcon(self.icon)
		self.avatar_buttonWidget.setIconSize(QSize(50, 50))
	
	def setProjectDir(self, location):
		self.logCurrentMethod("Setting project dir to: {0}".format(location))
		self.projman.setProjectDir(location)
		self.setWindowTitle('CG Hub Downloader - {0}'.format(location))
	
	def switchView(self, view):
		self.logCurrentMethod("Switching view to...")
		button = None
		
		if view == 0:
			self.logCurrentMethod("Table view")
			self.tableview_buttonWidget.setEnabled(False)
			self.thumbnailview_buttonWidget.setEnabled(True)
		else:
			self.logCurrentMethod("Thumbnails view")
			self.tableview_buttonWidget.setEnabled(True)
			self.thumbnailview_buttonWidget.setEnabled(False)
		
		self.currentview = view
		self.stackedWidget.setCurrentIndex(view)
	
	def userSwitchView(self):
		self.switchView(not self.currentview)
	
	#  Direct-UI methods
	#  ----------------------------------------
	def setProjectLocation(self):
		dialog = QFileDialog()
		dialog.setFileMode(QFileDialog.Directory)
		dialogdir = self.projdir # or can use QDir.currentPath()
		directory = dialog.getExistingDirectory(self, "Set download location", \
			dialogdir, QFileDialog.ShowDirsOnly)
		
		if directory:
			self.setProjectDir(directory)
			self.usersdata.setProjectDir(directory)
			self.userslistdata.setProjectDir(directory)
			self.userslistdata.updateFromUsersData(self.usersdata)
			
			# Deselect all from users list
			for modelindex in self.users_listViewWidget.selectedIndexes():
				selectionmodel = self.users_listViewWidget.selectionModel()
				selectionmodel.select(modelindex, QItemSelectionModel.Deselect)
			
			# Clear table view
			self.clearTable()
			
			# Load default avatar
			self.loadAvatar(":no_avatar100.gif")
		
	def downloadSelected(self):
		if self.currentuser != None and self.currentuser != '':
			self.logCurrentMethod("Downloading selected images from {0}".format(self.currentuser))
			userobj = self.usersdata.getUser(self.currentuser)
			self.projman.processUser(userobj)
	
	def openFolder(self, folderType):
		self.logCurrentMethod("Opening folder")
		if folderType == 'project':
			call(["explorer.exe ", convertPathToExplorer(self.projdir)])
		elif folderType == 'user':
			if self.currentuser != None and self.currentuser != '':
				userdir = convertPathToExplorer(self.projdir+'\\'+self.currentuser)
				if os.path.isdir(userdir):
					call(["explorer.exe ", userdir])
	
	def openDatViewer( self ):
		window = datviewer2.DatViewerWindow( self )
		window.show()
	
	def showAboutDialog(self):
		aboutdialog = AboutDialog(self)
		aboutdialog.show()

	#  Table View related methods
	#  ----------------------------------------
	def onUserSelect(self, modelindex):
		self.logCurrentMethod("Loading user's images")
		username = self.userslistmodel.data(modelindex, Qt.DisplayRole)
		# Note: username will looks like -> "username (10)"
		username = username.split(' ')[0]
		userobj = self.usersdata.getUser(username)
		self.factory.addJob('UserImages', (userobj, self.projman))

	def refreshTableView(self, userobj):
		self.logCurrentMethod("Updating table view")
		self.projman.updateWithExistingImages(self.usersdata)
		
		# It might always be true, but just to be clear, please be
		# aware that both table model and thumbnails model need to
		# receive the same userobj in order to sync with each other.
		self.setTableModel(userobj.name)
		self.setThumbnailsModel(userobj.name)
		self.currentthumbnailsmodel.updateModel()

		# Load avatar
		self.loadAvatar(userobj.avatarpath)
		
		# Set current user
		self.currentuser = userobj.name
		
		# Update user name
		self.username_labelWidget.setText(self.currentuser)
		
		# Update Images filesize
		self.updateImagesFilesize()
		
		# Update/Download Thumbnails
		self.projman.processUser(userobj, thumbnails=True)
		
		# Redownload avatar if it's missing
		if userobj.avatarpath == None:
			avatarpath = self.projman.getUserAvatar(userobj, userobj.userpagehtml)
			if avatarpath:
				self.loadAvatar(avatarpath)

	def setTableModel(self, username):
		""" Attact a table model to view. If no table model found for
		the user, create a new one.
		"""
		self.logCurrentMethod("Setting table model for '{0}'".format(username))
		model = None
		
		if username not in self.gettablemodel.keys():
			model = UserImagesModel(self.usersdata, username)
			self.gettablemodel[username] = model
			
			# When projman is downloading an image, it will fires
			# 'updateModel' signal. This model will catch it and 
			# calls 'updateModel' (which is just a simple 'modelReset()')
			# to tell the view to update. This process shows the
			# download progress
			self.projman.updateModel.connect(model.updateModel)
			
		else:
			model = self.gettablemodel[username]
		
		self.images_tableViewWidget.setModel(model)
			
		# Keep self updated about the change
		self.currentusermodel = model
	
	def updateTableModel(self):
		self.logCurrentMethod("Asking table model to 'resetModel()'")
		self.currentusermodel.updateModel()
	
	def clearTable(self):
		self.logCurrentMethod("Clearing table, setting table model to empty user ('')")
		self.images_tableViewWidget.clearSpans()
		self.setTableModel('')   # Set to empty user will clear the table model

	def updateImagesFilesize(self):
		if self.currentuser != None and self.currentuser != '':
			self.logCurrentMethod("Updating images file size for '{0}'".format(self.currentuser))
			self.projman.updateWithExistingImages(self.currentusermodel._usersdata)
			self.setStatus("Checking {0}'s images file size...".format(self.currentuser), 3.5)
			self.factory.addJob('ImagesFilesize', (self.usersdata, self.currentuser))
	
	#  Thumbnails view methods
	#  ----------------------------------------
	def setThumbnailsModel(self, username):
		""" Attacth a thumbnails model to view. If no thumbnails model found for
		the user, create a new one.
		"""
		self.logCurrentMethod("Setting thumbnails model for '{0}'".format(username))
		model = None
		
		if username not in self.getthumbnailsmodel.keys():
			# Passing a UserDir to ThumbnailsModel() so that it
			# knows where to look for the thumbnails
			userdir = self.projman.getUserDir(username)
			model = ThumbnailsModel(self.usersdata, username, userdir)
			self.getthumbnailsmodel[username] = model
			
			# The thumbnails table view is an instance of MyThumbnailsView,
			# MyThumbnailsView will fires the 'columnCountChange' everytime
			# the window is resized. This will tell the model to change
			# it's column counts to fit the new size.
			self.thumbnails_tableViewWidget.columnCountChange.connect(model.setColumnCount)
			
			# When projman is downloading a thumbnails, it will fires
			# 'updateThumbnailsModel' signal. This model will catch it and 
			# calls 'updateModel' (which is just a simple 'modelReset()')
			# to tell the view to update.
			self.projman.updateThumbnailsModel.connect(model.updateModel)
			
		else:
			model = self.getthumbnailsmodel[username]

		self.thumbnails_tableViewWidget.setModel(model)
			
		# Keep self updated about the change
		self.currentthumbnailsmodel = model

	#  Table view right click context menu
	#  ----------------------------------------
	def tableviewPopup(self, point):
		self.table_popMenu.exec_(self.images_tableViewWidget.mapToGlobal(point))

	def checkSelected(self, check):
		self.logCurrentMethod("Check selected")
		view = None
		model = None
		checkstate = Qt.Checked if check else Qt.Unchecked
		
		if self.stackedWidget.currentIndex() == 0:
			view = self.images_tableViewWidget
			model = self.currentusermodel
		else:
			view = self.thumbnails_tableViewWidget
			model = self.currentthumbnailsmodel
		
		for idx in view.selectedIndexes():
			model.setData(idx, checkstate, Qt.CheckStateRole)
	
	def checkAll(self, check):
		self.logCurrentMethod("Check all")
		view = None
		model = None
		checkstate = Qt.Checked if check else Qt.Unchecked
		
		if self.stackedWidget.currentIndex() == 0:
			view = self.images_tableViewWidget
			model = self.currentusermodel
		else:
			view = self.thumbnails_tableViewWidget
			model = self.currentthumbnailsmodel
		
		view.selectAll()
		for idx in view.selectedIndexes():
			model.setData(idx, checkstate, Qt.CheckStateRole)
		view.selectionModel().clearSelection()
	
	def viewFile(self):
		# for idx in self.images_tableViewWidget.selectedIndexes():
		# 	self.currentusermodel.setData(idx, Qt.Unchecked, Qt.CheckStateRole)
		pass

	#  Thumbnails view right click context menu
	#  ----------------------------------------
	def thumbnailsViewPopup(self, point):
		self.thumbnails_popMenu.exec_(self.thumbnails_tableViewWidget.mapToGlobal(point))

	#  Users list view right click context menu
	#  ----------------------------------------
	def listviewPopup(self, point):
		self.list_popMenu.exec_(self.users_listViewWidget.mapToGlobal(point))
	
	def deleteUser(self):
		# Delete from users list
		self.userslistdata.deleteUser(self.currentuser)
		# Delete from usersdata as well
		self.usersdata.deleteUser(self.currentuser)
		self.userslistmodel.updateModel()
		
		# Selection the first item on the list
		modelindex = self.userslistmodel.index(0,0)
		if modelindex:
			self.users_listViewWidget.setCurrentIndex(modelindex)
			username = self.userslistmodel.data(modelindex, Qt.DisplayRole)
			self.refreshTableView(self.usersdata.getUser(username))
	
	#  Set project button right click context menu
	#  -------------------------------------------
	def projectButtonPopup(self, point):
		self.project_popMenu.exec_(self.setproject_buttonWidget.mapToGlobal(point))

	#  User lists related methods
	#  ----------------------------------------
	def onAddUser( self ):
		user = self.newuser_lineEditWidget.text()
		user = str(user).lower()
		self.logCurrentMethod("Adding '{0}' to list".format(user))
		if len( user ) > 0:
			if user not in self.addedUsers:
				self.usersdata.addNewUser(user)
				userobj = self.usersdata.getUser(user)
				self.setStatus("Adding '{0}'...".format(user), 3)
				self.factory.addJob('UserValidation', userobj)
	
	def refreshUserList(self, userobj, html):
		self.logCurrentMethod("Refreshing users list")
		if userobj.exists and userobj.viewImageUrl == False:
			# need to mark user empty???
			self.callWarning("{0}'s gallery is empty".format(userobj.name))
			logger.warning("{0}'s gallery is empty".format(userobj.name))
		else:
			self.userslistdata.addUser(userobj)
			self.userslistmodel.updateModel()
			# Select new user
			idx = self.userslistdata.getUserIndex(userobj.name)
			if idx != None:
				modelindex = self.userslistmodel.index(idx, 0)
				self.users_listViewWidget.setCurrentIndex(modelindex)
			avatarpath = self.projman.getUserAvatar(userobj, html)
			if avatarpath != None:
				self.loadAvatar(avatarpath)

if __name__ == '__main__':
	import sys
	app = QApplication(sys.argv)
	app.setApplicationName('CGHub Downloader')
	form = MainWindow()
	form.show()
	sys.exit( app.exec_() )
