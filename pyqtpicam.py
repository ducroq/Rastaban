#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Based on
 https://picamera.readthedocs.io/en/latest/
 https://picamera.readthedocs.io/en/release-1.13/api_camera.html
 https://www.raspberrypi.org/documentation/hardware/camera/
    
version December 2020, January 2021
Note that there are different image sizes involved:
1. frameSize: intended image capture frame size, this is converted to a size that the picamera can deal with, i.e. raw_frame_size
2. clipFrameSize: intended video capture frame size
3. processingFrameSize: size of frames that get emitted to the processing chain.
"""
import os
import cv2
import time
import warnings
import traceback
import numpy as np
from fps import FPS
from picamera import PiCamera
from picamera.array import PiRGBArray, PiYUVArray, PiArrayOutput
from PyQt5.QtCore import QThread, QSettings, pyqtSlot, QTimer, QEventLoop, pyqtSignal
from wait import wait_signal, wait_ms
from io import BytesIO
from subprocess import run, check_output


def raw_frame_size(frame_size, splitter=False):
    """
    Round a (width, height) tuple up to the nearest multiple of 32 horizontally
    and 16 vertically (as this is what the Pi's camera module does for
    unencoded output).
    """
    width, height = frame_size
    if splitter:
        fwidth = (width + 15) & ~15
    else:
        fwidth = (width + 31) & ~31
    fheight = (height + 15) & ~15
    return (fwidth, fheight)

def frame_size_from_sensor_mode(sensorMode):
    if sensorMode == 0:
        frameSize = (4056,3040)
    if sensorMode == 1:
        frameSize = (1920,1080)
    elif sensorMode == 2 or sensorMode == 3:
        frameSize = (3280, 2464)               
    elif sensorMode == 4:
        frameSize = (1640, 1232)               
    elif sensorMode == 5:
        frameSize = (1640,922)
    elif sensorMode == 6:
        frameSize = (1280, 720)
    elif sensorMode == 7:
        frameSize = (640, 480)
    else:
        raise ValueError
    return frameSize

def frame_size_from_string(frameSizeStr):
    (width, height) = frameSizeStr.split('x')
    return (int(width), int(height))

class PiYArray(PiArrayOutput):
    """
    Produces a 2-dimensional Y only array from a YUV capture.
    Does not seem faster than PiYUV array...
    """
    def __init__(self, camera, size=None):
        super(PiYArray, self).__init__(camera, size)
        self.fwidth, self.fheight = raw_frame_size(self.size or self.camera.resolution)
        self.y_len = self.fwidth * self.fheight
##        uv_len = (fwidth // 2) * (fheight // 2)
##        if len(data) != (y_len + 2 * uv_len):
##            raise PiCameraValueError
##            'Incorrect buffer length for frame_size %dx%d' % (width, height))

    def flush(self):
        super(PiYArray, self).flush()
        a = np.frombuffer(self.getvalue()[:self.y_len], dtype=np.uint8)
        self.array = a[:self.y_len].reshape((self.fheight, self.fwidth))


## PiVideoStream class streams camera images to a numpy array
class PiVideoStream(QThread):
    image = None
    finished = pyqtSignal()
    postMessage = pyqtSignal(str)
    frame = pyqtSignal(np.ndarray)
    progress = pyqtSignal(int)       
    captured = pyqtSignal()
    
    camera = PiCamera()
    videoStream = BytesIO()
    
    storagePath = None
    cropRect = [0] * 4

    ## @param ins is the number of instances created. This may not exceed 1.
    ins = 0

    ## Note that:
    ##  The video recording methods default to using splitter port 1,
    ##    while the image capture methods default to splitter port 0 (when the use_video_port parameter is also True).
    ##  A splitter port cannot be simultaneously used for video recording and image capture,
    ##    so you are advised to avoid splitter port 0 for video recordings unless you never intend to capture images whilst recording.
    
    def __init__(self):
        super().__init__()

        ## Instance limiter. Checks if an instance exists already. If so, it deletes the current instance.
        if PiVideoStream.ins >= 1:
            del self            
            self.postMessage.emit("{}: error; multiple instances of created, while only 1 instance is allowed".format(__class__.__name__))
            return        
        try:
            PiVideoStream.ins+=1
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))
        else:
            warnings.filterwarnings('default', category=DeprecationWarning)
            self.settings = QSettings("settings.ini", QSettings.IniFormat)
            self.loadSettings()
            self.initStream()
            
            
    def loadSettings(self):
        self.postMessage.emit("{}: info; loading camera settings from {}".format(self.__class__.__name__, self.settings.fileName()))

        # load
        self.monochrome = self.settings.value('camera/monochrome', False, type=bool)
        self.use_video_port = self.settings.value('camera/use_video_port', False, type=bool)
        self.sensorMode = int(self.settings.value('camera/sensor_mode'))
        self.clipSensorMode = int(self.settings.value('camera/clip_sensor_mode'))
        self.frameRate = int(self.settings.value('camera/frame_rate'))
        self.clipFrameRate = int(self.settings.value('camera/clip_frame_rate'))

        # set frame sizes
        self.frameSize = frame_size_from_sensor_mode(self.sensorMode)
        self.processingFrameSize = frame_size_from_string(self.settings.value('processing_frame_size'))
        self.clipFrameSize = frame_size_from_string(self.settings.value('camera/clip_frame_size'))

        if not self.monochrome:
            self.processingFrameSize = self.processingFrameSize + (3,)

    @pyqtSlot()
    def initStream(self):
        # Initialize the camera stream
        if self.isRunning():
            # in case init gets called, while thread is running
            self.postMessage.emit("{}: error; video stream is already running".format(__class__.__name__))
        else:
            # Set camera parameters
            self.camera.resolution = self.frameSize
            self.camera.sensor_mode = self.sensorMode
            self.camera.framerate = self.frameRate
            self.camera.image_effect = self.settings.value('camera/effect')
            self.camera.shutter_speed = int(self.settings.value('camera/shutter_speed'))
            self.camera.iso = int(self.settings.value('camera/iso')) # should force unity analog gain       
            self.camera.video_denoise = self.settings.value('camera/video_denoise', False, type=bool)

            # Wait for the automatic gain control to settle
            wait_ms(2000)

            # Now fix the values
            self.camera.shutter_speed = self.camera.exposure_speed
            self.camera.exposure_mode = 'off'
            g = self.camera.awb_gains
            self.camera.awb_mode = 'off'
            self.camera.awb_gains = g
            
##            # Setup video port, GPU resizes frames, and compresses to mjpeg stream
##            self.camera.start_recording(self.videoStream, format='mjpeg', splitter_port=1, resize=self.processingFrameSize)

            # Setup capture port
            if self.monochrome:
                self.rawCapture = PiYArray(self.camera, size=self.processingFrameSize)
                self.captureStream = self.camera.capture_continuous(self.rawCapture, 'yuv', self.use_video_port, resize=self.processingFrameSize)
            else:
                self.rawCapture = PiRGBArray(self.camera, size=self.processingFrameSize)
                self.captureStream = self.camera.capture_continuous(self.rawCapture, 'bgr', self.use_video_port, resize=self.processingFrameSize)
            # init crop rectangle
            if self.cropRect[2] == 0:
                self.cropRect[2] = self.camera.resolution[1]
            if self.cropRect[3] == 0:
                self.cropRect[3] = self.camera.resolution[0]
                
            # start the thread
            self.start()
            msg = "{}: info; video stream initialized with frame size = {} and {:d} channels".format(\
                __class__.__name__, str(self.camera.resolution), 1 if self.monochrome else 3)
            self.postMessage.emit(msg)

    @pyqtSlot()
    def run(self):
        self.fps = FPS().start()
        while not self.isInterruptionRequested():
            try:
                # Grab a frame from the capture port
                self.rawCapture.seek(0) 
                img = next(self.captureStream).array # grab the frame from the stream
                self.frame.emit(img)#cv2.resize(img, self.processingFrameSize[:2]))
                self.fps.update()

##                # Grab jpeg from an mpeg video stream
##                self.videoStream.seek(0)
##                buf = self.videoStream.read()
##                if buf.startswith(b'\xff\xd8'):
##                    # jpeg magic number is detected
##                    flag = cv2.IMREAD_GRAYSCALE if self.monochrome else cv2.IMREAD_COLOR
##                    img = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), flag) 
##                    self.frame.emit(img)
##                    self.fps.update()
##                    self.videoStream.truncate(0)
            except Exception as err:
                self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
            
        self.fps.stop()
        msg = "{}: info; finished, approx. processing speed: {:.2f} fps".format(self.__class__.__name__, self.fps.fps())
        self.postMessage.emit(msg)
        self.finished.emit()

        
    @pyqtSlot()
    def stop(self):
        self.postMessage.emit("{}: info; stopping".format(__class__.__name__))
        try:
            if self.isRunning():
                self.requestInterruption()
                wait_signal(self.finished, 2000)
        except Exception as err:
            msg = "{}: error; stopping method".format(self.__class__.__name__)
            print(msg)
       
    @pyqtSlot(str)
    def takeImage(self, filename_prefix=None):
        if filename_prefix is not None:
            (head, tail) = os.path.split(filename_prefix)
            if not os.path.exists(head):
                os.makedirs(head)
            filename = os.path.sep.join([head, '{:016d}_'.format(round(time.time() * 1000)) + tail + '.png'])
        else:
            filename = '{:016d}'.format(round(time.time() * 1000)) + '.png'
            # open path
            if self.storagePath is not None:
                filename = os.path.sep.join([self.storagePath, filename])

        self.camera.capture(filename, format='png')

        self.captured.emit()
        self.postMessage.emit("{}: info; image written to {}".format(__class__.__name__, filename))
                

    @pyqtSlot(str, int)
    def recordClip(self, duration=10):
        """
        Captures a videoclip of duration at clipFrameRate fps and resolution clipFrameSize.
        Camera videomode is set by clipSensorMode, such that the camera frameSize equals
          1640x1232 or lower, since higher resolutions result in system freezing.
        The GPU resizes the captured video to the intended resolution.
        In many cases, the intended framerate is not achieved. For that reason, ffprobe counts
        the total number of frames that were actually taken.        
        Next, the h264 video file is boxed using MP4box.
        For some reason, changing the framerate with MP4Box did not work out.        
        """
        filename = '{:016d}_{}s'.format(round(time.time() * 1000), round(duration))
                
        # open path
        if self.storagePath is not None:
            filename = os.path.sep.join([self.storagePath, filename])

        # stop current video stream, maybe mpeg and h264 compression cannot run simultaneously?
        self.postMessage.emit("{}: info; starting recording for {} s".format(__class__.__name__, duration))
        
        self.stop()
        self.camera.sensor_mode = self.clipSensorMode
        self.camera.framerate = self.clipFrameRate
        # GPU resizes frames, and compresses to h264 stream
        self.camera.start_recording(filename + '.h264', format='h264', splitter_port=2, resize=self.clipFrameSize, sps_timing=True)
        wait_ms(duration*1000)
        self.camera.stop_recording(splitter_port=2)
        
        # Wrap an MP4 box around the video
        try:
            nr_of_frames = check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1", filename + '.h264'])
            real_fps = duration/float(nr_of_frames)
            self.postMessage.emit("{}: info; video clip captured with real framerate: {} fps".format(__class__.__name__, real_fps))
##            run(["MP4Box", "-fps", str(self.clipFrameRate), "-add", filename + '.h264:fps=' + str(real_fps), "-new", filename + '.mp4'])
            run(["MP4Box", "-fps", str(self.clipFrameRate), "-add", filename + ".h264", "-new", filename + "_{}fr.mp4".format(int(nr_of_frames))])
            run(["rm", filename + '.h264'])
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
            
        self.captured.emit()
        self.postMessage.emit("{}: info; video written to {}".format(__class__.__name__, filename))

        # Revert to original stream parameters
        self.initStream()


    @pyqtSlot(str)
    def setStoragePath(self, path):
        self.storagePath = path
        
    @pyqtSlot(int)
    def setCropXp1(self, val):
        if 0 <= val <= self.cropRect[3]:        
            self.cropRect[1] = val
        else:
            raise ValueError('crop x1')
            
    @pyqtSlot(int)
    def setCropXp2(self, val):
        if self.cropRect[1] < val < self.camera.resolution[1]:            
            self.cropRect[3] = val
        else:
            raise ValueError('crop x2')
            
    @pyqtSlot(int)
    def setCropYp1(self, val):
        if 0 <= val <= self.cropRect[2]:        
            self.cropRect[0] = val            
        else:
            raise ValueError('crop y1')
            
    @pyqtSlot(int)
    def setCropYp2(self, val):
        if self.cropRect[0] < val < self.camera.resolution[0]:
            self.cropRect[2] = val            
        else:
            raise ValueError('crop y2')   

