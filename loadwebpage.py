
import sys
import requests
import unicodedata

def safeprint(s):
	""" Used to avoid 'UnicodeEncodeError'
	"""
	try:
		print unicodedata.normalize('NFKD',s).encode('ascii','ignore')
	except TypeError:
		print str(s)
	sys.stdout.flush()

def isInternetConnected(url="http://www.google.com/"):
	try:
		requests.get(url)
	except requests.exceptions.ConnectionError, e:
		return False
	return True

def getWebpage(url):
	if not isInternetConnected():
		return False, "Internet is not connected."
	
	try:
		r = requests.get(url)
		return True, r.text
	except requests.exceptions.MissingSchema, e:
		return False, "Invalid URL address."
	except requests.exceptions.ConnectionError, e:
		return False, "Can't get to website."
	except Exception, e:
		return False, e.message
		# print type(e)
		# print e.message

def getPartialWebpage(url, terminate_str=None, blocksize=1024*8):
	if not isInternetConnected():
		return False, "Internet is not connected."
	
	text = ""
	try:
		r = requests.get(url, stream=False)
		for block in r.iter_content(blocksize):
			if not block:
				break
			else:
				text += block
				if isinstance(terminate_str, str) and terminate_str in text:
					return True, text
		return True, text
	except requests.exceptions.MissingSchema, e:
		return False, "Invalid URL address."
	except requests.exceptions.ConnectionError, e:
		return False, "Can't get to website."
	except Exception, e:
		return False, e.message
		# print type(e)
		# print e.message
