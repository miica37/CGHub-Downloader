
from PyQt4.QtCore import *
from PyQt4.QtGui import *

class MyTableView(QTableView):
	def __init__(self, parent=None):
		super(MyTableView, self).__init__(parent)
	
	def resizeEvent(self, event):
		width = event.size().width()
		self.setColumnWidth(0, width * 0.5)
		self.setColumnWidth(1, width * 0.25)
		self.setColumnWidth(2, (width * 0.25) - 10)
