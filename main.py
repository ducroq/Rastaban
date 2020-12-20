#!/usr/bin/python3
# -*- coding: utf-8 -*-
from checkOS import is_raspberry_pi

if not is_raspberry_pi():
    print("ERROR: this app is for raspberrypi")
    exit()

from PyQt5.QtCore import Qt, QThread, QEventLoop, QTimer, QSettings
from PyQt5.QtWidgets import QApplication
from mainWindow import MainWindow
from log import LogWindow     
from imageProcessor import ImageProcessor
from pyqtpicam import PiVideoStream
from autoFocus import AutoFocus
from voiceCoil import VoiceCoil
from heater import Heater
import pigpio

'''
main application
'''    
pio = pigpio.pi()
if not pio.connected:
    print("ERROR: pigpio daemon is not started")
    exit()
    
settings = QSettings("settings.ini", QSettings.IniFormat)
app = QApplication([])
mw = MainWindow()
lw = LogWindow()
vs = PiVideoStream()
ip = ImageProcessor()
vc = VoiceCoil(pio)
af = AutoFocus()
htr = Heater(pio, 2000)

# Connect GUI signals
mw.rotateSpinBox.valueChanged.connect(ip.enhancer.setRotateAngle)
mw.gammaSpinBox.valueChanged.connect(ip.enhancer.setGamma)
mw.claheSpinBox.valueChanged.connect(ip.enhancer.setClaheClipLimit)
mw.cropXp1Spinbox.valueChanged.connect(ip.enhancer.setCropXp1)
mw.cropYp1Spinbox.valueChanged.connect(ip.enhancer.setCropYp1)
mw.cropXp2Spinbox.valueChanged.connect(ip.enhancer.setCropXp2)
mw.cropYp2Spinbox.valueChanged.connect(ip.enhancer.setCropYp2)
mw.VCSpinBox.valueChanged.connect(vc.setVal)
mw.TemperatureSPinBox.valueChanged.connect(htr.setVal)
mw.snapshotButton.clicked.connect(lambda: vs.snapshot(settings.value('temp_folder') +'/'))
mw.autoFocusButton.clicked.connect(lambda: af.start(mw.VCSpinBox.value()))
mw.gridDetectorButton.stateChanged.connect(ip.setGridDetection)
htr.reading.connect(mw.temperatureUpdate)
ip.frame.connect(mw.update)
ip.quality.connect(mw.imageQualityUpdate)

# Start video stream
vs.start(QThread.HighPriority)
ip.start(QThread.HighPriority)

# Connect processing signals
vs.frame.connect(ip.update, type=Qt.BlockingQueuedConnection)
ip.quality.connect(af.imageQualityUpdate)
af.focus.connect(mw.VCSpinBox.setValue)
    
# Connect logging signals
vs.message.connect(lw.append)
ip.message.connect(lw.append)
af.message.connect(lw.append)
vc.message.connect(lw.append)
htr.message.connect(lw.append)

# Initialize objects from GUI
ip.enhancer.setRotateAngle(mw.rotateSpinBox.value())
ip.enhancer.setGamma(mw.gammaSpinBox.value())
ip.enhancer.setClaheClipLimit(mw.claheSpinBox.value())
vc.setVal(mw.VCSpinBox.value())
    
# Recipes invoked when main window is closed, note that scheduler stops other threads
mw.closed.connect(ip.stop, type=Qt.QueuedConnection)
mw.closed.connect(vs.stop, type=Qt.QueuedConnection)
mw.closed.connect(vc.stop, type=Qt.QueuedConnection)
mw.closed.connect(af.stop, type=Qt.QueuedConnection)
mw.closed.connect(lw.close, type=Qt.QueuedConnection)
    
# Start the show
lw.append("App started")
mw.move(100,100)
mw.resize(1500, 500)
lw.move(100,800)
lw.resize(1500, 200)
mw.show()
lw.show()
app.exec_()

