#!/usr/bin/python3
# -*- coding: utf-8 -*-
import pigpio
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import time

class VoiceCoil(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    message = pyqtSignal(str)
    
    pio = None # Reference to PigPIO object
    dir_pin = 17 # Switch current direction through voicecoil, GPIO17, pin 11
    pwm_pin = 18 # PWM pin, GPIO18, pin 12
    pwm_frequency = 100000
    
    def __init__(self, pio):
        super().__init__()
        if not isinstance(pio, pigpio.pi):
            raise TypeError("VoiceCoil constructor attribute is not a pigpio.pi instance!")
        self.pio = pio
        self.pio.set_mode(self.dir_pin, pigpio.OUTPUT)
        self.pio.hardware_PWM(self.pwm_pin, self.pwm_frequency, 0)
        self.value = 0.0

    @pyqtSlot(float)
    def setVal(self, val):
        # val specifies polarity and percentage of full current
        self.value = round(val,1)
        self.message.emit("{}: info; voice coil value = {}".format(self.__class__.__name__, self.value))
        try:
            if self.pio is not None:
                self.pio.hardware_PWM(self.pwm_pin, self.pwm_frequency, int(abs(self.value)*1e4))
                if val > 0:
                    self.pio.write(self.dir_pin, 0)
                elif val < 0:
                    self.pio.write(self.dir_pin, 1)
                else:
                    self.pio.hardware_PWM(self.pwm_pin, self.pwm_frequency, 0) # PWM off
        except Exception as err:
            self.message.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
            
    @pyqtSlot()
    def stop(self):
        try:
            if self.pio is not None:
                self.pio.hardware_PWM(self.pwm_pin, 0, 0) # PWM off
        except Exception as err:
            self.message.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
            
