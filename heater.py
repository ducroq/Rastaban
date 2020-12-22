#!/usr/bin/python3
# -*- coding: utf-8 -*-
## Heater
# MCP9800 temp sensor communicating via I2C_SDA, I2C_SCL, and alert pin on GPIO.
# Resistive heater using PWM on GPIO .
#
import pigpio
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
import time

class Heater(QThread):
    reading = pyqtSignal(float)  # Temperature signal
    postMessage = pyqtSignal(str)    

    i2cBus = 1  # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)
    MCP9800Address = 0b1001000  # MCP9800/02A0    
    MCP9800_T_alert = 10 # Alert is raised bij MCP9800 temp sensor, GPIO10, pin 19
    pwm_pin = 9 # PWM pin, GPIO9, pin 21
    pwm_frequency = 50000
    PWM_dutycyle_range = 100
    temperature = None

    def __init__(self, pio, interval=1000):
        super().__init__()
        if not isinstance(pio, pigpio.pi):
            raise TypeError("Heater constructor attribute is not a pigpio.pi instance!")
        self.pio = pio  # reference to pigpio
        self.interval = interval  # timer interval, i.e. update period [ms]
        self.timer = QTimer()
##        self.pio.set_mode(self.dir_pin, pigpio.OUTPUT)
##        self.pio.hardware_PWM(self.pwm_pin, self.pwm_frequency, 0)
        self.pio.set_mode(self.pwm_pin, pigpio.OUTPUT)
        self.pio.set_PWM_frequency(self.pwm_pin, self.pwm_frequency)
        self.pio.set_PWM_range(self.pwm_pin, self.PWM_dutycyle_range)
        self.pio.set_PWM_dutycycle(self.pwm_pin, 0) # PWM off
        self.MCP9800Handle = self.pio.i2c_open(self.i2cBus, self.MCP9800Address)  # open device on bus
        self.pio.i2c_write_byte_data(self.MCP9800Handle, 0x01, 0b01100000)  # write config register resolution = 10 bit, see p18 of datasheet
        self.timer.timeout.connect(self.update)
        self.timer.start(self.interval)

    @pyqtSlot()
    def update(self):        
        try:
            if self.pio is not None:
                data = self.pio.i2c_read_word_data(self.MCP9800Handle, 0x0)
                self.temperature = round((data & 0xFF) + (data >> 12)*2**-4, 1)  # MSB and LSB seem flipped
                self.reading.emit(self.temperature)
                # todo: PID here                
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            


    @pyqtSlot(float)
    def setVal(self, val):
        # val specifies percentage of full current
        pwm_val = round((abs(val)/100)*self.PWM_dutycyle_range, 1)
        self.postMessage.emit("{}: info; heater value = {}".format(self.__class__.__name__, pwm_val))
        try:
            if self.pio is not None:
                self.pio.set_PWM_dutycycle(self.pwm_pin, pwm_val)
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            

       
    @pyqtSlot()
    def stop(self):
        try:
            self.postMessage.emit("{}: info; stopping worker".format(self.__class__.__name__))
            if self.pio is not None:
                self.pio.set_PWM_dutycycle(self.pwm_pin, 0) # PWM off
                self.pio.i2c_close(self.MCP9800Handle)
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            

