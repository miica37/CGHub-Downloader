
from PyQt4.QtCore import *
from PyQt4.QtGui import *

class MyThumbnailsView(QTableView):
	columnCountChange = pyqtSignal(int)
	
	def __init__(self, parent=None):
		super(MyThumbnailsView, self).__init__(parent)
		self._columnCount = 1
		self.columnwidth = 100
	
	def resizeEvent(self, event):
		width = event.size().width()
		columncount = width / self.columnwidth
		if columncount < 1:
			columncount = 1
		self.columnCountChange.emit(columncount)
		for i in range(columncount+1):
			self.setColumnWidth(i, width / columncount)
