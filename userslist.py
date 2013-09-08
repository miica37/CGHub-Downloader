
import os
import sys
import gzip
import cPickle

from settings import *

#  Logging
#  ----------------------------------------
import logging
from logformat import *
logger = logging.getLogger("userslist")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(LOG_PRINT_FORMAT, LOG_DATE_FORMAT))
logger.addHandler(console_handler)

def enum(**enums):
	return type('Enum', (), enums)

USER_DISPLAY_STATUS = enum(SHOW=1, HIDE=2, DISABLE=3)

class UsersList(object):
	""" Note: Do update the data by using updateFromUsersData(UsersData).
	"""
	def __init__(self, usersdata=None):
		super(UsersList, self).__init__()
		self.users = []
		self._projdir = None
			
	def addUser(self, userobj):
		""" Note: This method is called after the user is verified to exists
		which at the time doesn't have images informations.
		"""
		if userobj.images != None:
			userimageslength = len(userobj.images)
		else:
			userimageslength = 0
		
		self.users.append([userobj.name, USER_DISPLAY_STATUS.SHOW, userimageslength])
		self.savePickle()
	
	def updateImagesCount(self, userobj):
		if userobj.images != None:
			self.users[self.getUserIndex(userobj.name)][2] = len(userobj.images)

	def getUsers(self):
		""" getUsers() -> [username1, username2]
		"""
		return [ username for username, userstatus, userimagescount in self.users ]
		
	def getUserIndex(self, username):
		for (i, (username_, userstatus, userimagescount)) in enumerate(self.users):
			if username_ == username:
				return i
		return None
	
	def updateFromUsersData(self, usersdata):
		if usersdata == None:
			return None
		
		availablenames = usersdata.getUsernames()
		newusers = []
		for user in self.users:
			username, userstatus, userimagescount = user
			userimages = usersdata.getUser(username).images
			if userimages != None:
				userimagescount = len(usersdata.getUser(username).images)
			if username in availablenames:
				newusers.append((username, userstatus, userimagescount))
		self.users = newusers
	
	def deleteUser(self, username):
		self.users = [ (username_, userstatus, userimagescount) \
			for (username_, userstatus, userimagescount) in self.users if username_ != username ]
	
	def __iter__(self):
		return iter(self.users)
	
	def __getitem__(self, key):
		#  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
		#  ----------------------------------------
		#  Btw, there is a bug that will cause key to be outside the range 
		#  of the list, but I can't find where is that coming from yet
		return self.users[key]
	
	def setProjectDir(self, location):
		logger = logging.getLogger("userslist.setProjectDir")
		self._projdir = str(location)
		ok = self.loadPickle()
		if not ok:
			logger.warning("Can't load dat file from {0}".format(location))
			
			# Set _users to blank to prevent saving other project's
			# data to the new location
			del self.users[:]
			
			# Save a new empty dat file to the new location
			self.savePickle()
	
	def loadPickle(self, datfile=USERS_LIST_DAT):
		error = None
		fh = None
		if self._projdir != None:
			datfile = os.path.join(self._projdir, datfile)
		logger = logging.getLogger("userslist.loadPickle")
		logger.info("Loading '{0}'".format(datfile))
		try:
			fh = gzip.open(datfile, "rb")
			users = cPickle.load(fh)
			if users:
				self.users = users
		except Exception:
			(e_type, e_val, e_traceback) = sys.exc_info()
			logger.error("{0}, {1}".format(e_type, e_val))
		finally:
			if fh is not None:
				fh.close()
				logger.info("Users list from '{0}' loaded".format(USERS_LIST_DAT))
				return True
			else:
				logger.warning("Can't load '{0}'".format(USERS_LIST_DAT))
				return False

	def savePickle(self, datfile=USERS_LIST_DAT):
		error = None
		fh = None
		if self._projdir != None:
			datfile = os.path.join(self._projdir, datfile)
		logger = logging.getLogger("userslist.savePickle")
		logger.info("Saving '{0}'".format(datfile))
		try:
			fh = gzip.open(datfile, "wb")
			cPickle.dump(self.users, fh, 2)
		except Exception:
			(e_type, e_val, e_traceback) = sys.exc_info()
			logger.error("{0}, {1}".format(e_type, e_val))
		finally:
			if fh is not None:
				fh.close()
				logger.info("Users list saved to '{0}'".format(USERS_LIST_DAT))
				return True
			else:
				logger.warning("Can't save '{0}'".format(USERS_LIST_DAT))
				return False
