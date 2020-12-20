"""@package docstring
Image processor implements QThread
images are passed via wrapper
"""
 
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import numpy as np
import traceback
from imageEnhancer import ImageEnhancer
from imageSegmenter import ImageSegmenter
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThread, QEventLoop
from fps import FPS
from wait import wait_signal


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
    finished = pyqtSignal()
    message = pyqtSignal(str)
    frame = pyqtSignal(np.ndarray)
    quality = pyqtSignal(float)

    enhancer = ImageEnhancer()
    segmenter = ImageSegmenter(plot=False)

    def __init__(self):
        super().__init__()

        self.gridDetection = False
        
        self.enhancer.message.connect(self.messageRelay)
        self.segmenter.message.connect(self.messageRelay)

        self.fps = FPS().start()
       
        
    def __del__(self):
        None
        self.wait()

    @pyqtSlot(np.ndarray)
    # Note that we need this wrapper around the Thread run function, since the latter will not accept any parameters
    def update(self, image=None):
        try:
            
            if self.isRunning():
                # thread is already running
                # drop frame
                self.message.emit("{}: info; busy, frame dropped".format(self.__class__.__name__))
            elif image is not None:
                # we have a new image
                self.image = image #.copy()        
                self.start()
                
        except Exception as err:
            self.message.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            

       
    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        if self.image is not None:
##            self.message.emit("{}: info; running worker".format(self.__class__.__name__))
           
            # Retrieve args/kwargs here; and fire processing using them
            try:
                if self.isInterruptionRequested():
                    self.finished.emit()
                    return
                
                # Enhance image
                self.image = self.enhancer.start(self.image)
                
                # Segment image according to grid 
                if self.gridDetection:
                    self.image, self.imageQuality = self.segmenter.start(self.image)

            except Exception as err:
                self.message.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
            else:
                self.fps.update()
                self.frame.emit(self.image)
                self.quality.emit(self.imageQuality)
                
    @pyqtSlot()
    def stop(self):
        self.message.emit("{}: info; stopping".format(__class__.__name__))
        if self.isRunning():
            self.requestInterruption()
            wait_signal(self.finished, 2000)            
        self.fps.stop()
        msg = "{}: info; approx. processing speed: {:.2f} fps".format(self.__class__.__name__, self.fps.fps())
        self.message.emit(msg)
        print(msg)
        self.quit()

    @pyqtSlot(int)
    def setGridDetection(self, val):
        self.gridDetection = val

    @pyqtSlot(str)
    def messageRelay(self, text):
        text = self.__class__.__name__ + "; " + str(text)
        self.message.emit(text)

            

