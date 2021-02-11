#!/usr/bin/python3
# -*- coding: utf-8 -*-
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import matplotlib.pyplot as plt
from wait import wait_ms, wait_signal

## Autofocus
## Perform a naive grid search to optimize the image quality parameter, imgQual, by varying the camera focus.
## A grid of size P, centred around the current focus, with grid spacing dP is searched.
## When the maximum IQ is found, the focus is to the value where max IQ occured.
## Then, the procedure is repeated N_n times, where in every iteration the grid spacing is halved.
##
## TODO: extend to 2 dimensional search by including optimization of the rotation angle



class AutoFocus(QObject):
##    Gridsearch of a hyperparameter H (image quality) over a process variable P (focus).
##    Start signal initiates a search around a given point P_centre, with gridsize N_p and gridspacing dP.
##    The search is repeated N_n times, where the gridspacing is halved with each step.
    setFocus = pyqtSignal(float)  # Focus signal
    postMessage = pyqtSignal(str)
    focussed = pyqtSignal(float)
    rPositionReached = pyqtSignal() # repeat signal
    rImageQualityUpdated = pyqtSignal() # repeat signal
    
    def __init__(self,display=False):
        super().__init__()
        self.display = display
        self.k = 0 # plot position counter
        
    @pyqtSlot(float)
    def start(self, P_centre=0):
        N_p = 5 # half of total grid points
        dP = .5 # initial actuater step size
        avg_H = 3 # number of quality gauges to average
        R = 3 # iterations

        self.postMessage.emit("{}: info; running".format(self.__class__.__name__))

        if self.display and (self.k == 0): # we have not plotted before
            self.fig, (self.ax1, self.ax2) = plt.subplots(2,1)
            self.graph1 = None
            self.ax1.grid(True)
            self.ax1.set_ylabel("Image quality")
            self.graph2 = None
            self.ax2.grid(True)
            self.ax2.set_ylabel("Voice coil value")
            plt.show(block=False)

        for r in range(R):        
            P = P_centre + (dP/(r+1))*(np.arange(2*N_p, dtype=float) - N_p)
            H = np.zeros_like(P)

            self.setFocus.emit(P[0])  # Move to starting point of grid search
    ##        wait_signal(self.rPositionReached, 10000)
            wait_ms(500)        
            
            for i,p in enumerate(P):
                self.setFocus.emit(p)
    ##            wait_signal(self.rPositionReached, 10000)
                wait_ms(100)
                # average a few image quality values
                H[i] = 0
                for j in range(avg_H):
                    wait_signal(self.rImageQualityUpdated, 10000)
                    H[i] += self.imgQual
                H[i] /= avg_H
                # plot measurement
                if self.display:
                    # draw grid lines
                    self.graph1 = self.ax1.plot(self.k, H[i], 'bo')[0]
                    self.graph2 = self.ax2.plot(self.k, p, 'bo')[0]
                    # We need to draw *and* flush
                    self.fig.canvas.draw()
                    self.fig.canvas.flush_events()
                    self.k += 1
            # wrap up        
            max_ind = np.argmax(H)
            P_centre = P[max_ind] # set new grid centre point
            self.postMessage.emit("{}: info; current focus position = {}".format(self.__class__.__name__, round(P_centre,2)))
            
            
        value = round(P_centre,2)
        self.setFocus.emit(value)  # set next focus
##        wait_signal(self.rPositionReached, 10000)
        self.focussed.emit(value) # publish focus

    @pyqtSlot(float)
    def imageQualityUpdate(self, imgQual):
        self.imgQual = imgQual
        self.rImageQualityUpdated.emit()
          
    @pyqtSlot()
    def stop(self):
        try:
            if self.display:
                plt.close()                
            self.postMessage.emit("{}: info; stopping worker".format(self.__class__.__name__))
            self.running = False
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))

    @pyqtSlot()
    def positionReached(self):
        self.rPositionReached.emit()
