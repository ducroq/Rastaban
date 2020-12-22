"""@package docstring
Documentation for this module.

TODO:
For the first image of the stream 'self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)' results in a runtime warning, why?
Auto-rotate, based on info obtained further down the DIP chain
Auto-crop, e.g. fixed, or based on rotate and on info obtained further down the DIP chain (cut uncharp edges)
 
"""
 
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import numpy as np
import cv2
import inspect
import traceback
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from fps import FPS


class ImageEnhancer(QObject):
    """Image enhancer
    Subsequently, convert to grayscale, rotate and crop the image, 
    perform Contrast Limited Adaptive Histogram Equalization, gamma adaption.
     
    More details.
    """
    image = prevImage = None
    postMessage = pyqtSignal(str)
    result = pyqtSignal(np.ndarray)
    
    def __init__(self, *args, **kwargs):
        """The constructor."""
        super().__init__()
        
        # Set crop area to (p1_y, p1_x, p2_y, p2_x)
        self.cropRect = kwargs['cropRect'] if 'cropRect' in kwargs else [0,0,0,0]

        # Set rotation angle, sometimes strange behaviour, and rounding seems required
        self.rotAngle = round(kwargs['rotAngle'], 1) if 'rotAngle' in kwargs else 0.0

        # Set threshold for contrast limiting
        self.clahe = cv2.createCLAHE(clipLimit=kwargs['clahe'], tileGridSize=(8,8)) if 'clahe' in kwargs else None

        # Set gamma correction
        self.gamma = kwargs['gamma'] if 'gamma' in kwargs else 1.0

        # Set video smoothing
        self.alpha = kwargs['alpha'] if 'alpha' in kwargs else 0.0

        self.fps = FPS().start()
       
    def __del__(self):
        """The deconstructor."""
        pass    
        
    def start(self, Image):
        """Image processing function."""        
        try:
            self.image = Image

            if self.cropRect[2] == 0:
                self.cropRect[2] = self.image.shape[0]
            if self.cropRect[3] == 0:
                self.cropRect[3] = self.image.shape[1]

            # Convert to gray scale
            if len(self.image.shape) > 2:  # if color image
                self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)

            # Rotate
            if 0.0 < abs(self.rotAngle) <= 5.0:
                image_center = tuple(np.array(self.image.shape[1::-1]) / 2)
                rot_mat = cv2.getRotationMatrix2D(image_center, self.rotAngle, 1.0) ## no scaling
                self.image = cv2.warpAffine(self.image, rot_mat, self.image.shape[1::-1], flags=cv2.INTER_LINEAR)
                deltaw = int(.5*np.round(np.arcsin(np.pi*np.abs(self.rotAngle)/180)*self.image.shape[0]))
                deltah = int(.5*np.round(np.arcsin(np.pi*np.abs(self.rotAngle)/180)*self.image.shape[1]))
            else:
                deltaw = deltah = 0

            # Crop
            p1_y = self.cropRect[0] + deltah
            p1_x = self.cropRect[1] + deltaw
            p2_y = self.image.shape[0] - deltah if self.cropRect[2] == 0 else self.cropRect[2] - deltah
            p2_x = self.image.shape[1] - deltaw if self.cropRect[3] == 0 else self.cropRect[3] - deltaw

            if (p2_y > p1_y) and (p2_x > p1_x):
                self.image = self.image[p1_y:p2_y, p1_x:p2_x]
            
            # Contrast Limited Adaptive Histogram Equalization.
            if self.clahe is not None:  
                self.image = self.clahe.apply(self.image)
                
            # Change gamma correction
            if 1.0 < self.gamma < 10.0:  
                self.image = adjust_gamma(self.image, self.gamma)

            self.prevImage = self.image.copy()

        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
        else:
            self.fps.update()
        finally:
            return self.image

    @pyqtSlot(float)
    def setRotateAngle(self, val):
        if -5.0 <= val <= 5.0:
            self.rotAngle = round(val, 1)  # strange behaviour, and rounding seems required
        else:
            raise ValueError('rotation angle')
            
    @pyqtSlot(float)
    def setGamma(self, val):
        if 0.0 <= val <= 10.0:
            self.gamma = val
        else:
            raise ValueError('gamma')
            
    @pyqtSlot(float)
    def setClaheClipLimit(self, val):
        if val <= 0.0:
            self.clahe = None
        elif val <= 10.0:
            self.clahe = cv2.createCLAHE(clipLimit=val, tileGridSize=(8,8))  # Sets threshold for contrast limiting
        else:
            raise ValueError('clahe clip limit')
            
    @pyqtSlot(int)
    def setCropXp1(self, val):
        if 0 <= val <= self.cropRect[3]:        
            self.cropRect[1] = val
        else:
            raise ValueError('crop x1')
            
    @pyqtSlot(int)
    def setCropXp2(self, val):
        if self.cropRect[1] < val < self.image.shape[1]:            
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
        if self.cropRect[0] < val < self.image.shape[0]:
            self.cropRect[2] = val            
        else:
            raise ValueError('crop y2')

    @pyqtSlot(float)
    def setBlend(self, val):
        if 0 <= val < 1:
            self.alpha = val
        else:
            raise ValueError('blend alpha')

        
  
def adjust_gamma(image, gamma=1.0):
   invGamma = 1.0 / gamma
   table = np.array([((i / 255.0) ** invGamma) * 255
##   table = np.array([(  np.log(1.0 + i/255.0)*gamma) * 255  # log transform
      for i in np.arange(0, 256)]).astype("uint8")
   return cv2.LUT(image, table)
