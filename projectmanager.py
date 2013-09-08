
import os
import math
import inspect
import requests
from bs4 import BeautifulSoup

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from settings import *
from factory import BaseWorker, Factory
from usersdata import UsersData, User

#  Logging
#  ----------------------------------------
import logging
from logformat import *
logger = logging.getLogger("pm")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(LOG_PRINT_FORMAT, LOG_DATE_FORMAT))
logger.addHandler(console_handler)


def convertSize(size):
	"""
	By http://stackoverflow.com/users/2062973/james
	Source: http://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python
	"""
	size_name = ("KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
	i = int(math.floor(math.log(size,1024)))
	p = math.pow(1024,i)
	s = int(round(size/p,2))
	
	if (s > 0):
		return '%s %s' % (s,size_name[i])
	else:
		return '0B'

def hasImageExt(filename):
	images_exts = ['.jpeg', '.jpg', '.png', '.bmp']
	filename, extension = os.path.splitext(filename)
	
	if extension in images_exts:
		return True
	return False

class UserDir(object):
	def __init__(self, username, projDir):
		logger = logging.getLogger("pm.UserDir")
		logger.debug("Constructing UserDir for {0}".format(username))
		
		self.username = username
		self.path = os.path.join(projDir, username)
		self.files = []   # images files inside user's folder
		self.thumbnailspath = os.path.join(self.path, 'thumbs')
		self.thumbnails = []
		
		if not os.path.exists(self.path):
			os.makedirs(self.path)
		else:
			self.files = [ f for f in os.listdir(self.path) if \
			os.path.isfile(self.path+'/'+f) and hasImageExt(f) ]
		
		if not os.path.exists(self.thumbnailspath):
			os.makedirs(self.thumbnailspath)
		else:
			self.updateFileList()
		
		logger.debug("username={0} | path={1} | files={2} files | thumbnailspath={3} | thumbnails={4} files".format( \
			self.username, self.path, len(self.files), self.thumbnailspath, len(self.thumbnails) ))
		logger.debug("Finish constructing UserDir for {0}".format(username))
	
	def updateFileList(self):
		thumbnails = []
		for f in os.listdir(self.thumbnailspath):
			if os.path.isfile(self.thumbnailspath+'/'+f) and hasImageExt(f) \
				and os.path.getsize(os.path.join(self.thumbnailspath, f)) > 100:
				thumbnails.append(f)
		self.thumbnails = thumbnails

	def hasFile(self, filename):
		return filename in self.files

class DownloadWorker(BaseWorker):
	logger = logging.getLogger("pm.DownloadWorker")
	logger.info("Worker for downloading images ready")
	
	def doJob(self, jobdata):
		logger = logging.getLogger("pm.DownloadWorker.doJob")
		(projman, userobj, userdir, imgobj, imageurl) = jobdata
		logger.info("Downloading {0}'s image: {1}".format(userobj.name, imageurl))
		ok = projman.downloadImage(userobj, userdir, imgobj, imageurl)
		
		if not ok:
		 	self.emit(SIGNAL("error"), errormsg)

class DownloadThumbnailsWorker(BaseWorker):
	logger = logging.getLogger("pm.DownloadThumbnailsWorker.doJob")
	logger.info("Worker for downloading thumbnails ready")
	
	def doJob(self, jobdata):
		logger = logging.getLogger("pm.DownloadThumbnailsWorker.doJob")
		(projman, userobj, userdir, imgobj, thumbnailurl) = jobdata
		logger.info("Calling downloadThumbnails({1})".format(userobj.name, thumbnailurl))
		ok = projman.downloadThumbnails(userobj, userdir, imgobj, thumbnailurl)

class ProjectManager(QObject):
	saveData = pyqtSignal()     # connected to mainwindow.saveData
	updateModel = pyqtSignal()  # connected to mainwindow's table model's (UserImagesModel) updateModel
	updateThumbnailsModel = pyqtSignal()  # similar to above
	
	def __init__(self, location):
		super(ProjectManager, self).__init__()
		logger = logging.getLogger("pm.ProjectManager")
		logger.info("Constructing ProjectManager with location: {0}".format(location))
		
		self.projdir = location
		self.usersdirs = {}     # Hold a list of 'UserDir' objects
		self.factory = Factory()
		self.factory.addClass('Download', DownloadWorker)
		self.factory.addWorkers('Download')
		self.factory.addClass('DownloadThumbnails', DownloadThumbnailsWorker)
		self.factory.addWorkers('DownloadThumbnails', 5)
		self.updateUsersDir()
		
		logger.info("Finish constructing ProjectManager")

	def logCurrentMethod(self, msg, logtype='info'):
		methodname = inspect.stack()[1][3]
		logger = logging.getLogger("pm.ProjectManager."+methodname)
		if logtype == 'info':
			logger.info(msg)
		elif logtype == 'debug':
			logger.debug(msg)
		elif logtype == 'warning':
			logger.warning(msg)
		elif logtype == 'error':
			logger.error(msg)

	def setProjectDir(self, location):
		if os.path.isdir(location):
			self.projdir = location
			self.logCurrentMethod("Project directory set to: {0}".format(location))
		else:
			self.logCurrentMethod("Project directory failed to set to: {0}".format(location), 'error')
	
	def createUserDir(self, username):
		"""	Create a directory for user.
		createUserDir(str) -> UserDir()
		"""
		self.logCurrentMethod("Creating UserDir for '{0}'".format(username))
		userdir = UserDir(username, self.projdir)
		self.usersdirs[username] = userdir
		return userdir
	
	def getDirsInProjdir(self):
		""" List all directories inside project directory.
		getUsersInProjdir() -> ['dir_1', 'dir_2', ...]
		"""
		self.logCurrentMethod("Returning a list of dirs in {0}".format(self.projdir))
		return [ d for d in os.listdir(self.projdir) if os.path.isdir(self.projdir+'/'+d) ]
	
	def getUserDir(self, username):
		if username in self.usersdirs.keys():
			return self.usersdirs[username]
		else:
			userdir = self.createUserDir(username)
			return userdir
	
	def updateUsersDir(self):
		self.logCurrentMethod("Updating self.usersdirs with dirs inside {0}".format(self.projdir))
		for dir_ in self.getDirsInProjdir():
			if self.usersdirs.has_key(dir_):
				del self.usersdirs[dir_]
			self.usersdirs[dir_] = UserDir(dir_, self.projdir)
	
	# def updateUsersData(self, usersdata):
	def updateWithExistingImages(self, usersdata):
		""" Check out the images that already exists in Project's User's folder,
		and update usersdata so the status of each images is displayed correctly
		in the table view.
		"""
		self.logCurrentMethod("Updating usersdata user's images completed status")
		for userobj in usersdata.getUsers():
			if userobj.images == None:
				continue
			
			userdirobj = UserDir(userobj.name, self.projdir)
			
			for imgobj in userobj.images:
				exists = userdirobj.hasFile(imgobj.filename)
				
				if exists:
					filepath = userdirobj.path+'/'+imgobj.filename
					try:
						imgobj.filesize_dl = os.path.getsize(filepath)
						if imgobj.filesize_dl == imgobj.filesize:
							imgobj.completed = 100.0
					except:
						imgobj.filesize_dl = 0
		
			# Also check for avatar inside user's dir
			if userobj.avatarpath != None:
				avatarfilename = os.path.basename(userobj.avatarpath)
				if not userdirobj.hasFile(avatarfilename):
					userobj.avatarpath = None
		
	def processUser(self, userobj, thumbnails=False):
		""" processUser() -> True or False
		Put user's imageurls into queue, to be processed by download workers.
		Specify thumbnails to 'True' to download thumbnails.
		"""
		if thumbnails == True:
			self.logCurrentMethod("Processing {0}'s thumbnails to be downloaded".format(userobj.name))
		else:
			self.logCurrentMethod("Processing {0}'s images to be downloaded".format(userobj.name))
		
		if userobj == None:
			self.logCurrentMethod("'{0}' is not a valid user".format(username), 'error')
			return False
		
		userdir = UserDir(userobj.name, self.projdir)
		
		if not thumbnails:
			self.logCurrentMethod("Processing image list: {0}".format(userobj.images), 'debug')
			for imgobj in userobj.images:
				if imgobj.checked and \
					(imgobj.filename not in userdir.files or imgobj.completed < 100.0 ):
					self.logCurrentMethod("Adding '{0}' to download queue".format(imgobj.filename))
					self.factory.addJob('Download', (self, userobj, userdir, imgobj, imgobj.imageurl))

		if thumbnails:
			thumbnailsnames = [ t.thumbname for t in userobj.images ]
			self.logCurrentMethod("Processing thumbnails list: {0}".format(thumbnailsnames), 'debug')
			for imgobj in userobj.images:
				if not imgobj.thumbname in userdir.thumbnails:
					self.logCurrentMethod("Adding '{0}' to download queue".format(imgobj.thumbname))
					self.factory.addJob('DownloadThumbnails', (self, userobj, userdir, imgobj, imgobj.thumburl))

	def downloadThumbnails(self, userobj, userdir, imgobj, thumbnailurl):
		savetofile = os.path.join(userdir.thumbnailspath, imgobj.thumbname)
		self.logCurrentMethod("Downloading '{0}' to '{1}'".format(thumbnailurl, savetofile))
		try:
			with open(savetofile, 'wb') as fh:
				r = requests.get(thumbnailurl, stream=True)
				fh.write(r.raw.read())
				self.logCurrentMethod("Download of '{0}' completed".format(imgobj.thumbname))
		except:
			(e_type, e_val, e_traceback) = sys.exc_info()
			logger.error("Download of '{0}' stops unexpectedly".format(imgobj.thumbname))
			logger.error("{0}, {1}".format(e_type, e_val))
			return False
		finally:
			self.updateThumbnailsModel.emit()
			return True
	
	def downloadImage(self, userobj, userdir, imgobj, imageurl):
		""" downloadImage(...) -> True if success
		"""
		savetofile = os.path.join(userdir.path, imgobj.filename)
		self.logCurrentMethod("Downloading '{0}' to '{1}'".format(imageurl, savetofile))
		self.updateModel.emit()

		r = requests.get(imageurl, stream=True)
		filesize = int(r.headers['Content-Length'])
		filesizeKb = convertSize(filesize/1024.0)
		self.filesize = filesize
		self.logCurrentMethod("Size of '{0}': {1}".format(imgobj.filename, filesizeKb))

		filesize_dl = 0
		blocksize = 8192
		
		with open(savetofile, 'wb') as handle:
			for block in r.iter_content(1024*8):
				filesize_dl += len(block)
				filesizeKb = convertSize(filesize_dl/1024.0)
				imgobj.filesize_dl = filesize_dl
				imgobj.completed = filesize_dl*100.0/filesize
				self.updateModel.emit()
				
				if not block:
					break
				
				handle.write(block)
		
		if imgobj.completed < 100.0:
			logger.error("Download of '{0}' stops unexpectedly".format(imgobj.filename))
			# imgobj.status = 'Incomplete'
		else:
			self.logCurrentMethod("Download of '{0}' completed".format(imgobj.filename))
			# imgobj.status = 'Saved'
		
		self.saveData.emit()
		self.updateModel.emit()
		userdir.updateFileList()
		
		return True

	def getUserAvatar(self, userobj, html):
		""" Download user avatar
		getUserAvatar(User, str) -> filepath or None
		"""
		logger = logging.getLogger("pm.ProjectManager.getUserAvatar")
		if userobj.avatarpath != None:
			return userobj.avatarpath
		
		soup = BeautifulSoup(html)
		avatarurl = ''
		result = soup.find_all('img', class_='userpic', id='avatarImg')
		if len(result) != 0:
			result = result[0]
			avatarurl = "http:"+result['src']
			username = userobj.name
			userdir = UserDir(username, self.projdir)
			avatarfilename = avatarurl.split('/')[-1]
			savetofile = userdir.path+'/'+avatarfilename
			self.logCurrentMethod("Downloading '{0}' to '{1}'".format(avatarurl, savetofile))

			r = requests.get(avatarurl, stream=True)
			filesize = int(r.headers['Content-Length'])
			filesizeKb = convertSize(filesize/1024.0)
			self.logCurrentMethod("Size of '{0}': {1}".format(avatarfilename, filesizeKb))

			filesize_dl = 0
			blocksize = 8192

			with open(savetofile, 'wb') as filehandle:
				for block in r.iter_content(1024*8):
					filesize_dl += len(block)
					if not block:
						break
					filehandle.write(block)
			
			if filesize_dl == filesize:
				self.logCurrentMethod("Download of '{0}' completed".format(avatarurl))
				userobj.avatarpath = savetofile
				self.saveData.emit()
				return savetofile
			else:
				logger.error("Download of '{0}' stops unexpectedly".format(avatarurl))
				return None
