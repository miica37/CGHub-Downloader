
import os
import re
import sys
import gzip
import cPickle
import string

from bs4 import BeautifulSoup
from PyQt4.QtCore import *

from settings import *
from loadwebpage import isInternetConnected, getWebpage, getPartialWebpage

VALID_CHARS = "-_.() %s%s" % (string.ascii_letters, string.digits)

#  Logging
#  ----------------------------------------
import logging
from logformat import *
logger = logging.getLogger("userdata")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(LOG_PRINT_FORMAT, LOG_DATE_FORMAT))
logger.addHandler(console_handler)

class UserImage(object):
	def __init__(self, image_dict):
		if image_dict:
			self.id = image_dict['id']
			origtitle = image_dict['title']
			self.title = ''.join( c for c in origtitle if c in VALID_CHARS )
			self.thumburl = 'http:'+image_dict['thumb'].replace( '\\', '' )
			self.thumbname = self.thumburl.split( '/' )[-1]
			self.imageurl = 'http:'+image_dict['image'].replace( '\\', '' )
			self.imagename = self.imageurl.split( '/' )[-1]
			imagenumber = self.imagename.split( '_' )[0]
			self.filename = "{0}_{1}.{2}".format( self.title, imagenumber, self.imagename.split('/')[-1].split('.')[-1] )
			
			# self.thumb = image_dict['thumb']	# not used
			# self.url = image_dict['url']		# not used
			
			# imageurl -> http://s.cghub.com/files/Image/152001-153000/152444/335_max.jpg
			# imagename -> 335_max.jpg
			# imagenumber -> 335
			
			# For table view
			self.checked = True
			self.completed = 0.0		# Percent downloaded in float
			self.filesize = None
			self.filesize_dl = None
			# self.status = None			# 'Completed', 'Incomplete' or 'None'

class DummyUser(object):
	""" Object for used in loading and saving just the data
	"""
	def __init__(self, userobj):
		super(DummyUser, self).__init__()
		self.name = userobj.name
		self.exists = userobj.exists
		self.hasEmptyGallery = userobj.hasEmptyGallery
		self.viewImageUrl = userobj.viewImageUrl
		self.images = userobj.images
		self.userpagehtml = userobj.userpagehtml
		self.avatarpath = userobj.avatarpath
		self.isDirty = userobj.isDirty

class User(QObject):
	""" 
	Note: It is a QObject because we need to send signals to main window.
	      And now, we are sending it to UsersData too to tell it to constantly
	      saving the data.
	"""
	def __init__(self, name):
		super(User, self).__init__()
		self.name = name
		self.exists = None
		self.hasEmptyGallery = None
		self.viewImageUrl = None
		self.images = None       # Holds a list of UserImage objects
		self.userpagehtml = None
		self.avatarpath = None
		self.isDirty = False     # 'Dirty' means we should re-update the user data from server
	
	@classmethod
	def createFromDummy(cls, dummyobj):
		newuserobj = cls(dummyobj.name)
		newuserobj.exists = dummyobj.exists
		newuserobj.hasEmptyGallery = dummyobj.hasEmptyGallery
		newuserobj.viewImageUrl = dummyobj.viewImageUrl
		newuserobj.images = dummyobj.images
		newuserobj.userpagehtml = dummyobj.userpagehtml
		newuserobj.avatarpath = dummyobj.avatarpath
		newuserobj.isDirty = dummyobj.isDirty
		return newuserobj
	
	# def createAndSaveConnection(self, receiver, sender, signal, slot):
	# 	connection = (receiver, sender, signal, slot)
	# 	if connection not in self._connections:
	# 		self._connections.append((receiver, sender, signal, slot))
	
	# def restoreConnections(self):
	# 	for connection in self._connections:
	# 		receiver, sender, signal, slot = connection
	# 		receiver.connect(sender, signal, slot)
	
	def print_(self, msg):
		print msg
		self.emit(SIGNAL("print"), msg)
	
	def callWarning(self, msg):
		self.emit(SIGNAL("warning"), msg)
	
	def markDirty(self, msg):
		self.exists = None
		self.hasEmptyGallery = None
		self.viewImageUrl = None
		self.images = None
		self.userpagehtml = None
		self.avatarpath = None
		self.isDirty = True
	
	def checkIfExists(self, partialLoading=True):
		""" checkIfExists() -> (True, (self,html)) or (False, error_message)
		"""
		logger = logging.getLogger("userdata.User.checkIfExists")
		
		if self.exists == True and self.userpagehtml != None:
			logger.info("'{0}' found in database and exists".format(self.name))
			return True, (self, self.userpagehtml)
		
		if self.exists == False:
			return False, "User:'{0}'' does not exists.".format(self.name)
		else:   # self.exists == None, we haven't seen this user before, process new user
			gallery_url = "http://%s.cghub.com/" % self.name
			logger.info("Loading {0}'s gallery.".format(self.name))
			
			if partialLoading:
				ok, text = getPartialWebpage(gallery_url, "<!--  User's pictures block end -->")
			else:
				ok, text = getWebpage(gallery_url)
			
			if not ok:
				logger.warning("Fail to load {0}'s gallery".format(self.name))
				return False, text
			else:
				self.userpagehtml = text
				logger.info("{0}'s gallery load with success".format(self.name))
			
			#  Verify user
			#  ----------------------------------------
			#  Check if the title of the page that returns,
			#  it should starts with 'Animation, Concept Art blah blah blah' if user page is valid
			logger.info("Checking on '{0}'".format(self.name))
			soup = BeautifulSoup(text)
			
			if "{0} - CGHUB".format(self.name).lower() in soup.title.text.lower():
				self.exists = True
				logger.info("'{0}' found".format(self.name))
			else:
				self.exists = False
				logger.info("'{0}' not found".format(self.name))
				return False, "User:'{0}' not found.".format(self.name)
			
			#  Get 'view-image' url
			#  ----------------------------------------
			#  It is the link to view a single image, eg. http://cghub.com/images/view/307678/
			#  From that page we can extract a list of user images.
			viewImageUrl = None
			
			#  Using http://user.cghub.com/images/
			#  ----------------------------------------
			# for detgallery in soup.find_all('ul', class_='detgallery'):
			# 	for a_Tag in detgallery.select( 'a[href]' ):
			# 		viewImageUrl = a_Tag['href']   # We will just get the first 'a' tag
			# 		break
			
			#  Using http://user.cghub.com/
			#  ----------------------------------------
			result = soup.find_all('ul', class_='gallery')
			if len(result) != 0:
				result = result[0]
				if result.find("a"):
					viewImageUrl = result.find("a")['href']
			
			
			if viewImageUrl:
				logger.info("View image page found:'{0}'".format(viewImageUrl))
			else:
				logger.warning("View image page not found")
				self.emit(SIGNAL("warning"), "'{0}' has empty gallery.".format(self.name))
				viewImageUrl = False

			self.viewImageUrl = viewImageUrl
			self.isDirty = False   # Marked that we have processed this user, thus Not Dirty anymore
			self.emit(SIGNAL("savedata"))
			logger.info("User:'{0}' exists".format(self.name))
			
			return True, (self, text)
	
	def getUserImages(self, partialLoading=True):
		""" getUserImages() -> (True, self) or (False, error_message) or (-1, username)
		
		Value of -1 means the user has empty gallery
		For now, we are not handling returning value of -1, but will just return it
		"""
		logger = logging.getLogger("userdata.User.getUserImages")
		
		if self.isDirty:
			ok, msg = self.checkIfExists()
			if not ok:
				return False, msg

		if self.images != None:
			return True, self

		if self.viewImageUrl is False:
			logger.warning("'{0}' has empty gallery".format(self.name))
			return -1, self.name
		
		logger.info("Loading '{0}'".format(self.name))
		
		if partialLoading:
			ok, text = getPartialWebpage(self.viewImageUrl, '<div class="imagealign">')
		else:
			ok, text = getWebpage(gallery)

		if not ok:
			logger.error("Fail to load '{0}'".format(self.viewImageUrl))
			return False, text
		else:
			logger.info("'{0}' load with success".format(self.viewImageUrl))
		
		imagesJson = None
		soup = BeautifulSoup(text)
		
		for script_Tag in soup.find_all('script'):
			if 'thisUserOtherImagesJson' in script_Tag.text:
				match = re.search('thisUserOtherImagesJson = \[(.+)\];', script_Tag.text)
				if match:
					imagesJson = match.group(1)
				else:
					logger.error("'Can't find thisUserOtherImagesJson")
					return None, "'Can't find thisUserOtherImagesJson"
		
		# Once we get the data from javascript, we try to convert it to Python's data type.
		# If succesfull, we will get a tuple. Each element in the tuple is a dictionary.
		imagesTuple = None
		
		try:
			imagesTuple = eval( imagesJson )
		except:
			logger.error("Fail to eval data from javascript")
			return False, "Fail to eval data from javascript"
		
		# Convert the javascript json data to UserImage class type
		self.images = [ UserImage(img_dict) for img_dict in imagesTuple ]
		self.emit(SIGNAL("savedata"))
		logger.info("'{0}' images retrieved from view image page".format(self.name))
		
		return True, self

class UsersData(QObject):
	error = pyqtSignal()
	
	def __init__(self, mainwin=None):
		super(UsersData, self).__init__()
		self._users = {}
		self._mainwin = mainwin
		self._projdir = None
		self.loadPickle()
	
	def setProjectDir(self, location):
		logger = logging.getLogger("userdata.UsersData.setProjectDir")
		self._projdir = str(location)
		ok, result = self.loadPickle()
		if not ok:
			logger.warning("Can't load dat file from {0}".format(location))
			# Set _users to blank to prevent saving other project's
			# data to the new location
			self._users.clear()
			# Save a new empty dat file to the new location
			self.savePickle()
	
	def createConnections(self, userobj):
		if self._mainwin:
			logger = logging.getLogger("userdata.UsersData.createConnections")
			logger.debug("Connecting signals and slots for '{0}'".format(userobj.name))
			self._mainwin.connect(userobj, SIGNAL('print'), self._mainwin.printToLog)
			self._mainwin.connect(userobj, SIGNAL('warning'), self._mainwin.callWarning)
			self.connect(userobj, SIGNAL('savedata'), self.savePickle)

	def loadPickle(self, datfile=USERS_DAT):
		error = None
		fh = None
		
		if self._projdir != None:
			datfile = os.path.join(self._projdir, datfile)
		
		logger = logging.getLogger("userdata.UsersData.loadPickle")
		logger.info("Opening '{0}' to load data".format(datfile))
		
		try:
			fh = gzip.open(datfile, "rb")
			dummyUsers = cPickle.load(fh)
			self._users.clear()
			
			for dummyuser in dummyUsers:
				self._users[dummyuser.name] = User.createFromDummy(dummyuser)
				self.createConnections(self._users[dummyuser.name])   # Restore connections
			
		except Exception:
			(e_type, e_val, e_traceback) = sys.exc_info()
			logger.error("{0}, {1}".format(e_type, e_val))
			error = "Failed to load {0}: {1}, {2}".format(datfile, e_type, e_val)
		
		finally:
			if fh is not None:
				fh.close()
			
			if error is not None:
				logger.warning("Fail to load '{0}'".format(datfile))
				self.emit(SIGNAL("error"), error)
				return False, error
			
			logger.info("Users data loaded from '{0}'".format(datfile))
			
			return True, "Users data loaded from '%s'" % datfile

	def savePickle(self, datfile=USERS_DAT):
		error = None
		fh = None
		
		if self._projdir != None:
			datfile = os.path.join(self._projdir, datfile)
		
		logger = logging.getLogger("userdata.UsersData.savePickle")
		logger.info("Opening '{0}' to save data".format(datfile))
		
		try:
			fh = gzip.open(datfile, "wb")
			# Note: We can't dump self._users directly because pickle won't
			#       recognized QObject, otherwise we would just
			#       called cPickle.dump(self._users, fh, 2)
			dummyUsers = [ DummyUser(self._users[userkey]) for userkey in self._users.keys() ]
			cPickle.dump(dummyUsers, fh, 2)
			
		except Exception:
			(e_type, e_val, e_traceback) = sys.exc_info()
			logger.error("{0}, {1}".format(e_type, e_val))
			error = "Failed to save {0}: {1}, {2}".format(datfile, e_type, e_val)
			
		finally:
			if fh is not None:
				fh.close()
			if error is not None:
				logger.warning("Fail to save '{0}'".format(datfile))
				self.emit(SIGNAL("error"), error)
				return False, error
			
			logger.info("Users data saved to '{0}'".format(datfile))
			
			return True, "Users data saved to '%s'" % datfile

	def deleteUser(self, username):
		username = str(username)
		if self._users.has_key(username):
			del self._users[username]
		self.savePickle()

	def deleteUserNoSave(self, username):
		username = str(username)
		if self._users.has_key(username):
			del self._users[username]

	def addNewUser(self, username):
		"""	Create new user if not already exists, else do nothing
		"""
		username = str(username)
		if not self._users.has_key(username):
			userobj = User(username)
			self._users[username] = userobj
			self.createConnections(userobj)
			self.savePickle()

	def getUser(self, username):
		""" getUser(string) -> User object
		"""
		username = str(username)
		if self._users.has_key(username):
			return self._users[username]
		return None

	def getUsers(self):
		""" getUser() -> A list of User objects
		"""
		userobjsList = []
		for userkey in self._users.keys():
			userobjsList.append(self._users[userkey])
		return userobjsList

	def getUsernames(self):
		""" getUsernames() -> A list of User's names in str
		"""
		return self._users.keys()
