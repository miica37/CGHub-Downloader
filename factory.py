
import Queue
from PyQt4.QtCore import QThread

class BaseWorker(QThread):
	""" A base class intended to be subclassed and be used by Factory class
	"""
	def __init__(self, queue):
		"""	
		Keyword arguments:
			queue -- a Queue object
		"""
		QThread.__init__(self)
		self._queue = queue
	
	def run(self):
		while True:
			job = self._queue.get()
			self.doJob(job)
			self._queue.task_done()
	
	def doJob(self, data):
		""" Implement this method in your subclass
		Keyword arguments:
			data -- data from the queue
		"""
		pass

class Factory(object):
	""" A class to create workers and handle jobs queues.
	
	Usage example:
		factory = Factory()
		factory.addClass('Artist', ArtistWorker)
		factory.addClass('Cleaner', CleanerWorker)
		factory.addWorkers('Artist')
		factory.addWorkers('Cleaner')
		factory.addJob('Artist', 'cat') # tell ArtistWorker to work on the 'cat'
		factory.addJob('Cleaner', 'room') # tell CleanerWorker to work on the 'rom'
	"""
	def __init__(self):
		super(Factory, self).__init__()
		self.jobClass = {}	# a dict to lookup job_type: job_class
		self._queues = {}	# a dict to lookup job_type: Queue()
		self._workers = {}

	def addClass(self, job_type, job_class):
		"""	
		Keyword arguments:
			job_type -- string
			job_class -- subclass of BaseWorker
		"""
		self.jobClass[job_type] = job_class
		self._queues[job_type] = Queue.Queue()
	
	def addWorkers(self, job_type, num=3):
		"""	
		Keyword arguments:
			job_type -- string
			num -- number of Workers to create
		"""
		if not self._workers.has_key(job_type):
			self._workers[job_type] = []
		for i in range(num):
			workerClass = self.jobClass[job_type]
			worker = workerClass(self._queues[job_type])
			#worker.setDaemon(True)
			worker.start()
			self._workers[job_type].append(worker)
	
	def addJob(self, job_type, job_data):
		"""	
		Keyword arguments:
			job_type -- string
			job_data -- data that will be passed to Worker's doJob()
		"""
		self._queues[job_type].put(job_data)

	def getWorkers(self, job_type):
		return self._workers[job_type]