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
from timeLapse import TimeLapse
from sysTemp import SystemTemperatures
import pigpio

'''
main application
'''    
pio = pigpio.pi()
if not pio.connected:
    print("ERROR: pigpio daemon is not started")
    exit()
    
app = QApplication([])
mw = MainWindow()
lw = LogWindow()
vs = PiVideoStream()
ip = ImageProcessor()
vc = VoiceCoil(pio)
af = AutoFocus(doPlot=True)
tl = TimeLapse()
htr = Heater(pio, 2000)
st = SystemTemperatures(interval=10, alarm_temperature=55)

# Connect GUI signals
mw.rotateSpinBox.valueChanged.connect(ip.enhancer.setRotateAngle)
mw.gammaSpinBox.valueChanged.connect(ip.enhancer.setGamma)
mw.claheSpinBox.valueChanged.connect(ip.enhancer.setClaheClipLimit)
mw.cropXp1Spinbox.valueChanged.connect(vs.setCropXp1)
mw.cropYp1Spinbox.valueChanged.connect(vs.setCropYp1)
mw.cropXp2Spinbox.valueChanged.connect(vs.setCropXp2)
mw.cropYp2Spinbox.valueChanged.connect(vs.setCropYp2)
mw.VCSpinBox.valueChanged.connect(vc.setVal)
mw.TemperatureSPinBox.valueChanged.connect(htr.setTemperature)
mw.snapshotButton.clicked.connect(vs.takeImage)
mw.autoFocusButton.clicked.connect(lambda: af.start(mw.VCSpinBox.value()))
mw.focusTargetComboBox.currentIndexChanged.connect(ip.setFocusTarget)

mw.runButton.clicked.connect(tl.start)
htr.reading.connect(mw.temperatureUpdate)
ip.frame.connect(mw.update)
ip.quality.connect(mw.imageQualityUpdate)

# Start video stream
vs.start(QThread.HighPriority)
ip.start(QThread.HighPriority)

# Connect processing signals
vs.frame.connect(ip.update, type=Qt.BlockingQueuedConnection)
ip.quality.connect(af.imageQualityUpdate)
af.setFocus.connect(mw.VCSpinBox.setValue)
tl.setLogFileName.connect(lw.setLogFileName)
tl.setImageStoragePath.connect(vs.setStoragePath)
tl.startCamera.connect(vs.initStream)
tl.stopCamera.connect(vs.stop)
tl.setFocusTarget.connect(mw.focusTargetComboBox.setCurrentIndex)
tl.startAutoFocus.connect(lambda: af.start(mw.VCSpinBox.value()))
af.focussed.connect(tl.focussedSlot)
tl.takeImage.connect(vs.takeImage)
tl.setFocusWithOffset.connect(lambda offset: vc.setVal(mw.VCSpinBox.value() + offset))
vs.captured.connect(tl.capturedSlot)
vs.captured.connect(lambda: lw.append("main: info; voice coil={:.1f} temperature={:.1f}".format(vc.value, htr.temperature)))
tl.setTemperature.connect(htr.setTemperature)

# Connect logging signals
vs.postMessage.connect(lw.append)
mw.postMessage.connect(lw.append)
ip.postMessage.connect(lw.append)
af.postMessage.connect(lw.append)
vc.postMessage.connect(lw.append)
htr.postMessage.connect(lw.append)
tl.postMessage.connect(lw.append)
st.postMessage.connect(lw.append)

# Connect closing signals
st.failure.connect(mw.close, type=Qt.QueuedConnection)
tl.finished.connect(mw.close)
mw.closed.connect(htr.stop)
mw.closed.connect(ip.stop)
mw.closed.connect(vs.stop)
mw.closed.connect(vc.stop)
mw.closed.connect(af.stop)
mw.closed.connect(tl.stop)
mw.closed.connect(lw.close)
    
# Start the show
settings = QSettings("settings.ini", QSettings.IniFormat)
lw.append("App started")
vs.initStream()
ip.enhancer.setRotateAngle(mw.rotateSpinBox.value())
ip.enhancer.setGamma(mw.gammaSpinBox.value())
ip.enhancer.setClaheClipLimit(mw.claheSpinBox.value())
ip.enhancer.setBlend(0.25)
ip.enhancer.setKsize(5)
vc.setVal(mw.VCSpinBox.value())
vs.setStoragePath(settings.value('temp_folder'))
### set max parameters from here?
##frame_size_str = self.settings.value('camera/frame_size')
#mw.cropXp1Spinbox.setMaximum
mw.move(100,100)
mw.resize(1500, 500)
lw.move(100,800)
lw.resize(1500, 200)
mw.show()
lw.show()
app.exec_()

