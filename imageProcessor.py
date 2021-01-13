"""@package docstring
Image processor implements QThread
images are passed via wrapper
"""
 
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import cv2
import numpy as np
import traceback
from imageEnhancer import ImageEnhancer
from imageSegmenter import ImageSegmenter
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThread, QEventLoop
from fps import FPS
from wait import wait_signal
from rectangle import Rectangle

def union(a,b):
    x = min(a[0], b[0])
    y = min(a[1], b[1])
    w = max(a[0]+a[2], b[0]+b[2]) - x
    h = max(a[1]+a[3], b[1]+b[3]) - y
    return (x, y, w, h)

def intersection(a,b):
    x = max(a[0], b[0])
    y = max(a[1], b[1])
    w = min(a[0]+a[2], b[0]+b[2]) - x
    h = min(a[1]+a[3], b[1]+b[3]) - y
    if w<0 or h<0: return () # or (0,0,0,0) ?
    return (x, y, w, h)


class ImageProcessor(QThread):
    '''
    Worker thread

    :param callback: The function callback to run on this worker thread. Supplied args and 
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''
    image = None
    imageQuality = 0
    ROI = None
    finished = pyqtSignal()
    postMessage = pyqtSignal(str)
    frame = pyqtSignal(np.ndarray)
    quality = pyqtSignal(float)

    enhancer = ImageEnhancer()
    segmenter = ImageSegmenter()

    def __init__(self):
        super().__init__()

        self.focusTarget = 0
        
        self.enhancer.postMessage.connect(self.relayMessage)
        self.segmenter.postMessage.connect(self.relayMessage)

        self.fps = FPS().start()
       
        
    def __del__(self):
        self.wait()

    @pyqtSlot(np.ndarray)
    # Note that we need this wrapper around the Thread run function, since the latter will not accept any parameters
    def update(self, image=None):
        try:
            
            if self.isRunning():
                # thread is already running
                # drop frame
                self.postMessage.emit("{}: info; busy, frame dropped".format(self.__class__.__name__))
            elif image is not None:
                # we have a new image
                self.image = image #.copy()        
                self.start()
                
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            

       
    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        if self.image is not None:
##            self.postMessage.emit("{}: info; running worker".format(self.__class__.__name__))
           
            # Retrieve args/kwargs here; and fire processing using them
            try:
                if self.isInterruptionRequested():
                    self.finished.emit()
                    return

                # Set general ROI
                if self.ROI is None:
                    ROI_leg = int(min(self.image.shape)/4)
                    x, y = int(self.image.shape[1]/2), int(self.image.shape[0]/2)
                    self.ROI = Rectangle(x - ROI_leg, y - ROI_leg, x + ROI_leg, y + ROI_leg)

                # Enhance image
                self.image = self.enhancer.start(self.image)
                
                if self.focusTarget == 0:
                    # Compute variance of Laplacian in RoI
                    img = self.image[self.ROI.y1:self.ROI.y2, self.ROI.x1:self.ROI.x2]
                    self.imageQuality = cv2.Laplacian(img, ddepth=cv2.CV_32F, ksize=5).var()
                    # draw ROI in image
                    cv2.rectangle(self.image, self.ROI.p1, self.ROI.p2, (0, 255, 0), 2)                    
                elif self.focusTarget == 1:
                    # Segment image according to grid
                    ROIs, self.imageQuality = self.segmenter.start(self.image)
                    # draw ROIs in image
                    for rois in ROIs:
                        for roi in rois:
                            cv2.rectangle(self.image, roi.p1, roi.p2, (0, 255, 0), 2)
                elif self.focusTarget == 2:
                    self.imageQuality, nr_of_rois = 0, 0
                    # Segment image according to intersection of ROI and grid
                    ROIs, _ = self.segmenter.start(self.image)                    
                    for rois in ROIs:
                        for roi in rois:
                            roi_intersection = roi & self.ROI
                            # exclude grid RoIS that go outside main ROI
                            if roi_intersection is not None and roi_intersection.area == roi.area:
                                # Compute variance of Laplacian in Grid RoIs
                                img = self.image[roi.y1:roi.y2, roi.x1:roi.x2]                                
                                self.imageQuality += cv2.Laplacian(img, ddepth=cv2.CV_32F, ksize=5).var()
                                nr_of_rois += 1
                                # draw ROIs in image                                
                                cv2.rectangle(self.image, roi.p1, roi.p2, (0, 255, 0), 2)
                    if nr_of_rois > 0:
                        self.imageQuality = int(self.imageQuality/nr_of_rois)
                else:
                    raise ValueError("focusTarget unknown")
                    
            except Exception as err:
                self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
            else:
                self.fps.update()
                self.frame.emit(self.image)
                self.quality.emit(self.imageQuality)
                
    @pyqtSlot()
    def stop(self):
        self.postMessage.emit("{}: info; stopping".format(__class__.__name__))
        if self.isRunning():
            self.requestInterruption()
            wait_signal(self.finished, 2000)            
        self.fps.stop()
        msg = "{}: info; approx. processing speed: {:.2f} fps".format(self.__class__.__name__, self.fps.fps())
        self.postMessage.emit(msg)
        print(msg)
        self.quit()

    @pyqtSlot(str)
    def relayMessage(self, text):
        text = self.__class__.__name__ + "; " + str(text)
        self.postMessage.emit(text)

    @pyqtSlot(int)
    def setFocusTarget(self, val):
        self.focusTarget = val        

            

