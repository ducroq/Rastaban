"""@package docstring
MainWindow
""" 
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import numpy as np
import cv2
from checkOS import is_raspberry_pi
import matplotlib
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QEventLoop, QSettings
from PyQt5.QtGui import QCloseEvent, QImage, QPixmap
# Make sure that we are using QT5
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import time


current_milli_time = lambda: int(round(time.time() * 1000))

class MainWindow(QWidget):
    '''
    GUI
    '''
    image = None
    postMessage = pyqtSignal(str)
    closed = pyqtSignal()
    

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.appName = os.path.basename(__file__)

        # Store constructor arguments (re-used for processing)
        self.args = args
        self.kwargs = kwargs
        
        self.prevClockTime = None
        self.settings = QSettings("settings.ini", QSettings.IniFormat)
        self.initUI()
        self.loadSettings()

    def initUI(self):
        self.setWindowTitle(self.appName)
        screen = QDesktopWidget().availableGeometry()
        self.imageWidth = round(screen.height() * 0.8)
        self.imageHeight = round(screen.width() * 0.8)
        self.imageScalingFactor = 1.0
        self.imageScalingStep = 0.1
        
        # Labels
        self.PixImage = QLabel()
        self.timerLabel = QLabel()
        self.imageQualityLabel = QLabel()
        self.temperatureLabel = QLabel()
        
        # a figure instance to plot on
        self.canvas = FigureCanvas(Figure()) #(figsize=(5, 3)))
        self.axes = self.canvas.figure.subplots(2, 2, sharex=False, sharey=False)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
##        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # Buttons
        self.snapshotButton = QPushButton("Snapshot")
        self.autoFocusButton = QPushButton("AutoFocus")
        self.runButton = QPushButton("Run timelapse")
        self.gridDetectorButton = QCheckBox("GridDetector")
        # Spinboxes
        self.VCSpinBox = QDoubleSpinBox(self)
        self.VCSpinBoxTitle = QLabel("VC")
        self.VCSpinBox.setSuffix("%")
        self.VCSpinBox.setMinimum(-100.0)
        self.VCSpinBox.setMaximum(100.0)
        self.VCSpinBox.setSingleStep(0.01)
        self.rotateSpinBox = QDoubleSpinBox(self)
        self.rotateSpinBoxTitle = QLabel("rotate")
        self.rotateSpinBox.setSuffix("°")
        self.rotateSpinBox.setMinimum(-5.0)
        self.rotateSpinBox.setMaximum(5.0)
        self.rotateSpinBox.setSingleStep(0.1)
        self.gammaSpinBox = QDoubleSpinBox(self)
        self.gammaSpinBoxTitle = QLabel("gamma")
        self.gammaSpinBox.setMinimum(0.0)
        self.gammaSpinBox.setMaximum(5.0)
        self.gammaSpinBox.setSingleStep(0.1)
        self.gammaSpinBox.setValue(1.0)
        self.claheSpinBox = QDoubleSpinBox(self)
        self.claheSpinBoxTitle = QLabel("clahe")
        self.claheSpinBox.setMinimum(0.0)
        self.claheSpinBox.setMaximum(10.0)
        self.claheSpinBox.setSingleStep(0.1)
        self.cropXp1Spinbox = QSpinBox(self)
        self.cropXp1SpinboxTitle = QLabel("xp1")
        self.cropXp1Spinbox.setMinimum(0)
##        self.cropXp1Spinbox.setMaximum(WIDTH/2)
##        self.cropXp1Spinbox.setSingleStep(10)
        self.cropXp2Spinbox = QSpinBox(self)
        self.cropXp2SpinboxTitle = QLabel("xp2")
        self.cropXp2Spinbox.setMinimum(self.cropXp1Spinbox.value())
##        self.cropXp2Spinbox.setMaximum(WIDTH)
##        self.cropXp2Spinbox.setSingleStep(10)
##        self.cropXp2Spinbox.setValue(WIDTH)
##        self.cropXp2Spinbox.setSingleStep(10)
        self.cropYp1Spinbox = QSpinBox(self)
        self.cropYp1SpinboxTitle = QLabel("yp1")
        self.cropYp1Spinbox.setMinimum(0)
##        self.cropYp1Spinbox.setMaximum(HEIGHT/2)
##        self.cropYp1Spinbox.setSingleStep(10)
        self.cropYp2Spinbox = QSpinBox(self)
        self.cropYp2SpinboxTitle = QLabel("yp2")
        self.cropYp2Spinbox.setMinimum(self.cropYp1Spinbox.value())
##        self.cropYp2Spinbox.setMaximum(HEIGHT)
##        self.cropYp2Spinbox.setSingleStep(10)
##        self.cropYp2Spinbox.setValue(HEIGHT)
        self.adaptiveThresholdOffsetSpinbox = QDoubleSpinBox(self)
        self.adaptiveThresholdOffsetSpinboxTitle = QLabel("aThresOffset")
        self.adaptiveThresholdOffsetSpinbox.setSingleStep(0.1)
        self.adaptiveThresholdOffsetSpinbox.setMinimum(-10)
        self.adaptiveThresholdOffsetSpinbox.setMaximum(10)
        self.adaptiveThresholdBlocksizeSpinBox = QSpinBox(self)
        self.adaptiveThresholdBlocksizeSpinBoxTitle = QLabel("aThresBlocksize")
        self.adaptiveThresholdBlocksizeSpinBox.setMinimum(3)
        self.adaptiveThresholdBlocksizeSpinBox.setSingleStep(2)
        self.TemperatureSPinBox = QDoubleSpinBox(self)
        self.TemperatureSPinBoxTitle = QLabel("Temperature")
        self.TemperatureSPinBox.setSingleStep(1)
        self.TemperatureSPinBox.setSuffix(" °C")
        self.TemperatureSPinBox.setMinimum(0.0)
        self.TemperatureSPinBox.setMaximum(100.0)
     
        # Compose layout grid
        self.keyWidgets = [self.VCSpinBoxTitle, self.rotateSpinBoxTitle,
                           self.gammaSpinBoxTitle, self.claheSpinBoxTitle,
                           self.adaptiveThresholdOffsetSpinboxTitle,
                           self.adaptiveThresholdBlocksizeSpinBoxTitle,
                           self.cropXp1SpinboxTitle, self.cropYp1SpinboxTitle,
                           self.cropXp2SpinboxTitle, self.cropYp2SpinboxTitle,
                           self.TemperatureSPinBoxTitle]
        self.valueWidgets = [self.VCSpinBox, self.rotateSpinBox,
                             self.gammaSpinBox, self.claheSpinBox,
                             self.adaptiveThresholdOffsetSpinbox,
                             self.adaptiveThresholdBlocksizeSpinBox,
                             self.cropXp1Spinbox, self.cropYp1Spinbox,
                             self.cropXp2Spinbox, self.cropYp2Spinbox,
                             self.TemperatureSPinBox]
        widgetLayout = QGridLayout()
        for index, widget in enumerate(self.keyWidgets):
            if widget is not None:
                widgetLayout.addWidget(widget, index, 0, Qt.AlignCenter)
        for index, widget in enumerate(self.valueWidgets):
            if widget is not None:
                widgetLayout.addWidget(widget, index, 1, Qt.AlignCenter)
        widgetLayout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum,QSizePolicy.Expanding))  # variable space
        widgetLayout.addWidget(self.snapshotButton,index+1,0,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(self.runButton,index+1,1,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(self.autoFocusButton,index+2,0,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(self.gridDetectorButton,index+2,1,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(QLabel("Image quality [au]: "),index+3,0,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(self.imageQualityLabel,index+3,1,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(QLabel("Processing time [ms]: "),index+4,0,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(self.timerLabel,index+4,1,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(QLabel("Temperature [°C]: "),index+5,0,alignment=Qt.AlignLeft)
        widgetLayout.addWidget(self.temperatureLabel,index+5,1,alignment=Qt.AlignLeft)

        # Compose final layout
        layout = QHBoxLayout()
        layout.addLayout(widgetLayout, Qt.AlignTop|Qt.AlignCenter)
        layout.addWidget(self.PixImage, Qt.AlignTop|Qt.AlignCenter)
##        layout.addWidget(self.canvas, Qt.AlignTop|Qt.AlignCenter)
        self.setLayout(layout)

    def progress_fn(self, n):
        print("%d%% done" % n)

    @pyqtSlot(np.ndarray)
    def update(self, image=None):
        self.kickTimer() # Measure time delay
##        self.postMessage.emit(self.name + ": height " + str(image.shape[0]))
        if image is not None:  # we have a new image
            self.image = image
            if self.imageScalingFactor > 0 and self.imageScalingFactor < 1:  # Crop the image to create a zooming effect
                height, width = image.shape[:2]  # get dimensions
                delta_height = round(height * (1 - self.imageScalingFactor) / 2)
                delta_width = round(width * (1 - self.imageScalingFactor) / 2)
                image = image[delta_height:height - delta_height, delta_width:width - delta_width]
            height, width = image.shape[:2]  # get dimensions
            if self.imageHeight != height or self.imageWidth != width:  # we need scaling
                scaling_factor = self.imageHeight / float(height)  # get scaling factor
                if self.imageWidth / float(width) < scaling_factor:
                    scaling_factor = self.imageWidth / float(width)
                    image = cv2.resize(image, None, fx=scaling_factor, fy=scaling_factor,
                                       interpolation=cv2.INTER_AREA)  # resize image
            height, width = image.shape[:2]  # get dimensions
            if len(image.shape) < 3:  # check nr of channels
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)  # convert to color image
            height, width = image.shape[:2]  # get dimensions
            qImage = QImage(image.data, width, height, width * 3, QImage.Format_RGB888)  # Convert from OpenCV to PixMap
            self.PixImage.setPixmap(QPixmap(qImage))
            self.PixImage.show()

    @pyqtSlot(int, np.ndarray, np.ndarray)
    def updatePlot(self, figType, quadrant, x, y):
        if not (y is None) or not (x is None):
            # select axes
            if quadrant == 1:
                axes = self.axes[0, 1]
            elif quadrant == 2:
                axes = self.axes[0, 0]
            elif quadrant == 3:
                axes = self.axes[1, 0]
            elif quadrant == 4:
                axes = self.axes[1, 1]
            # plot new data
            axes.clear()
            if (figType is FigureTypes.LINEAR) or (figType is None): 
                if x is None:
                    axes.plot(y)
                else:
                    axes.plot(x, y)

            elif figType == FigureTypes.SCATTER:
                if not(x is None):
                    #scatter plot
                    if len(x) >= 100:
                        t = np.arange(0, 100, 1)
                        length = len(x) - 100

                        axes.scatter(t, x[length:len(x)], c="blue", alpha=0.5)
                        # axes.set_xlabel('frame')
                        # axes.set_ylabel('Distance')

            elif figType == FigureTypes.HISTOGRAM:
                #hist
                if not(x is None):
                    if len(x) > 0:
                        axes.hist(x, 30, density=True, facecolor="blue", alpha=0.5)
                    #axes.set_xlabel('Distance')
                    #axes.set_ylabel('Occurance')
            axes.figure.canvas.draw()            

    @pyqtSlot()
    def kickTimer(self):
        clockTime = current_milli_time() # datetime.now()
        if self.prevClockTime is not None:
            timeDiff = clockTime - self.prevClockTime
            self.timerLabel.setNum(round(timeDiff)) # Text("Processing time: " + "{:4d}".format(round(timeDiff)) + " ms")
##            self.postMessage.emit("{}: info; processing delay = {} ms".format(self.__class__.__name__, round(timeDiff)))
        self.prevClockTime = clockTime

    @pyqtSlot(np.float)
    def temperatureUpdate(self, temp=None):
        self.temperatureLabel.setNum(round(temp)) # Text("Processing time: " + "{:4d}".format(round(timeDiff)) + " ms")

    @pyqtSlot(np.float)
    def imageQualityUpdate(self, image_quality=None):
        self.imageQualityLabel.setNum(round(image_quality)) # Text("Processing time: " + "{:4d}".format(round(timeDiff)) + " ms")

    def wheelEvent(self, event):
        if (event.angleDelta().y() > 0) and (self.imageScalingFactor > self.imageScalingStep):  # zooming in
            self.imageScalingFactor -= self.imageScalingStep
        elif (event.angleDelta().y() < 0) and (self.imageScalingFactor < 1.0):  # zooming out
            self.imageScalingFactor += self.imageScalingStep        
        self.imageScalingFactor = round(self.imageScalingFactor, 2)  # strange behaviour, so rounding is necessary
        self.update()  # redraw the image with different scaling

    def closeEvent(self, event: QCloseEvent):
        self.saveSettings()
        self.closed.emit()
        event.accept()        

    def loadSettings(self):
        self.postMessage.emit("{}: info; Loading settings from: {}".format(self.__class__.__name__, self.settings.fileName()))
        frame_size_str = self.settings.value('image_frame_size')
        (width, height) = frame_size_str.split('x')
        self.image_size = (int(width), int(height))
        for index, widget in enumerate(self.keyWidgets):  # retreive all labeled parameters
            if isinstance(widget, QLabel):
                key = "mainwindow/" + widget.text()
                if self.settings.contains(key):
                    self.valueWidgets[index].setValue(float(self.settings.value(key)))                    

    def saveSettings(self):
        self.postMessage.emit("{}: info; Saving settings to: {}".format(self.__class__.__name__, self.settings.fileName()))
        for index, widget in enumerate(self.keyWidgets):  # save all labeled parameters
            if isinstance(widget, QLabel):
                key = "mainwindow/" + widget.text()
                self.settings.setValue(key, self.valueWidgets[index].value())
        for index, widget in enumerate(self.valueWidgets):  # save all labeled parameters
            if isinstance(widget, QCheckBox):
                key = "mainwindow/" + widget.text()
                self.settings.setValue(key, widget.isChecked())       
