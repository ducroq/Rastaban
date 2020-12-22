"""@package docstring
"""
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import re
import time
import traceback
import numpy as np
##import smtplib, ssl
from webdav3.client import Client
from webdav3.exceptions import WebDavException
##from math import sqrt
from PyQt5.QtCore import QSettings, QObject, QTimer, QEventLoop, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDialog, QFileDialog #, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QVBoxLayout, QGridLayout
from wait import wait_signal, wait_ms

def checkSetting(setting):
    s = str(setting)
    return s.lower() in ['true', '1', 't', 'y', 'yes']

    
class TimeLapse(QObject):
    postMessage = pyqtSignal(str)
    setLogFileName = pyqtSignal(str)
    setImageStoragePath = pyqtSignal(str)
    stopCamera = pyqtSignal()
    startCamera = pyqtSignal()
    takeImage = pyqtSignal()
    startAutoFocus = pyqtSignal()
    focussed = pyqtSignal() # repeater signal
    setGridDetector = pyqtSignal()
    captured = pyqtSignal() # repeater signal
    progressUpdate = pyqtSignal(int)
    finished = pyqtSignal()
    setFocusWithOffset = pyqtSignal(float)

    focus = None
    
    def __init__(self):
        super().__init__()

        self.settings = QSettings('settings.ini', QSettings.IniFormat)
        self.conn_settings = QSettings('connections.ini', QSettings.IniFormat)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run)
        self.isInterruptionRequested = False        

    def __del__(self):
        pass

    @pyqtSlot()
    def start(self):

        try:
            # open timelapse settings file
            dlg = QFileDialog()
            timelapse_setting_file_name = QFileDialog.getOpenFileName(dlg, 'Open timelapse settings file', os.getcwd(), "Ini file (*.ini)")[0]
            if timelapse_setting_file_name == "" or timelapse_setting_file_name == None:
                self.postMessage.emit('{}: error; not a timelapse settings file selected'.format(self.__class__.__name__))            
                return

            self.postMessage.emit('{}: info; loading settings from {}'.format(self.__class__.__name__, timelapse_setting_file_name))          
            self.timelapse_settings = QSettings(timelapse_setting_file_name, QSettings.IniFormat)

            if not self.timelapse_settings.value('filetype') == 'timelapse':
                self.postMessage.emit('{}: error; not a timelapse settings file selected'.format(self.__class__.__name__))            
                return

            # set logging file
            self.local_storage_path = self.settings.value('temp_folder')
            log_file_name = os.path.sep.join([self.local_storage_path, self.timelapse_settings.value('id') + ".log"])
            self.setLogFileName.emit(log_file_name)            

            # clear temporary storage path
            path = os.path.sep.join([self.local_storage_path, '*'])
            self.postMessage.emit('{}: info; clearing temporary storage path: {}'.format(self.__class__.__name__, path))
            os.system('rm -rf {:s}'.format(path))

            # copy timelapse setting file to storage folder
            os.system('cp {:s} {:s}'.format(timelapse_setting_file_name, self.local_storage_path))

            # create temporary image storage path
            self.local_image_storage_path = os.path.sep.join([self.local_storage_path,'img'])
            if not os.path.exists(self.local_image_storage_path):
                os.makedirs(self.local_image_storage_path)
            self.postMessage.emit('{}: info; temporary image storage path: {}'.format(self.__class__.__name__,
                                                                                  self.local_image_storage_path))
            self.setImageStoragePath.emit(self.local_image_storage_path)

            # open WebDAV connection to server, esing credentials from connections.ini file
            self.openWebDAV()

            # copy files to server
            self.webdav_client.push(remote_directory=self.server_storage_path, local_directory=self.local_storage_path)
            self.server_log_file_name = os.path.sep.join([self.server_storage_path, self.timelapse_settings.value('id') + ".log"])

            # create directory structure on server
            for offset in self.timelapse_settings.value('acquisition/offsets'):
                self.webdav_client.mkdir(os.path.sep.join([self.server_storage_path, offset]))

            
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))


        # get timelapse schedule
        t = time.strptime(self.timelapse_settings.value('run/duration')[1],'%H:%M:%S')
        days = int(self.timelapse_settings.value('run/duration')[0].split('d')[0])
        self.run_duration_s = ((24*days + t.tm_hour)*60 + t.tm_min)*60 + t.tm_sec
        t = time.strptime(self.timelapse_settings.value('run/wait'),'%H:%M:%S')
        self.run_wait_s = (t.tm_hour*60 + t.tm_min)*60 + t.tm_sec

        self.postMessage.emit('{}: info; run duration: {} s, run wait: {} s'.format(self.__class__.__name__,
                                                                                    self.run_duration_s,
                                                                                    self.run_wait_s))
        # start timer
        self.start_time_s = time.time()
        self.timer.start(0)

        
    @pyqtSlot()
    def stop(self):
        try:
            self.postMessage.emit("{}: info; stopping worker".format(self.__class__.__name__))
            self.running = False
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))
            

    def openWebDAV(self):
        self.server_storage_path = os.path.sep.join([self.conn_settings.value('webdav/storage_path'),
                                                     self.timelapse_settings.value('id')])
        
        options = {'webdav_hostname': self.conn_settings.value('webdav/hostname'),
                   'webdav_login': self.conn_settings.value('webdav/login'),
                   'webdav_password': self.conn_settings.value('webdav/password')
                   }
        try:
            self.webdav_client = Client(options)
            self.webdav_client.mkdir(self.server_storage_path)
        except WebDavException as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))

        self.postMessage.emit('{}: info; WebDAV connection to {}: {}'.format(self.__class__.__name__,
                                                                         self.conn_settings.value('webdav/hostname'),
                                                                         self.server_storage_path))

    @pyqtSlot()
    def capturedSlot(self):
        self.captured.emit()

    @pyqtSlot(float)
    def focussedSlot(self, val):
        self.focus = val
        self.focussed.emit()

        
    def run(self):
        ''' Timer call back function, als initiates next one-shot 
        '''
        try:
            # wake up peripherals
            start_run_time_s = time.time()
            self.startCamera.emit()

            # autofocus
            if checkSetting(self.timelapse_settings.value('acquisition/autofocus')):
                if str(self.timelapse_settings.value('acquisition/focusgoal')).lower() in ['grid', 'g']:
                    self.setGridDetector.emit()
                    wait_ms(500)
                    self.postMessage.emit('{}: info; using grid as focus goal'.format(self.__class__.__name__))
                    
                self.startAutoFocus.emit()
                wait_signal(self.focussed, 60000)

            # move through all offset
            for offset_str in self.timelapse_settings.value('acquisition/offsets'):
                
                # set offset                
                offset = float(offset_str)
                self.setFocusWithOffset.emit(offset)

                # clear local image storage path
                path = os.path.sep.join([self.local_image_storage_path, '*'])
                self.postMessage.emit('{}: info; clearing temporary image storage path: {}'.format(self.__class__.__name__, path))
                os.system('rm -rf {:s}'.format(path))
                
                # take image or video
                self.takeImage.emit()
                wait_signal(self.captured, 10000) # snapshot taken
                ## TODO !! initiate videoclip recording
                    
                # push image file
                self.webdav_client.push(remote_directory=os.path.sep.join([self.server_storage_path, offset_str]),
                                        local_directory=self.local_image_storage_path)
                val = self.focus + offset if self.focus is not None else offset
                self.postMessage.emit('{}: info; saved image at focus: {:.1f}%'.format(self.__class__.__name__, val))
                
            # push log file
            self.webdav_client.push(remote_directory=self.server_storage_path, local_directory=self.local_storage_path)
            
            # wrap up current round of acquisition     
            self.stopCamera.emit()
            elapsed_total_time_s = time.time() - self.start_time_s
            elapsed_run_time_s = time.time() - start_run_time_s
            self.postMessage.emit("{}: info; single run time={:.1f}s, total run time={:.1f}s".format(self.__class__.__name__,
                                                                                                     elapsed_run_time_s,
                                                                                                     elapsed_total_time_s))
            progress_percentage = int(100*elapsed_total_time_s/self.run_duration_s)
            self.progressUpdate.emit(progress_percentage)
            self.postMessage.emit("{}: info; progress={:d}%".format(self.__class__.__name__, progress_percentage))

            # check if we still have time to do another round
            if elapsed_total_time_s + self.run_wait_s < self.run_duration_s:
                self.timer.setInterval(self.run_wait_s*1000)
                self.postMessage.emit("{}: info; wait for {:.1f} s".format(self.__class__.__name__, self.run_wait_s))
            else:
                self.timer.stop()
                self.postMessage.emit("{}: info; run finalized".format(self.__class__.__name__))
                self.webdav_client.push(remote_directory=self.server_storage_path, local_directory=self.local_storage_path)
                if checkSetting(self.timelapse_settings.value('shutdown')):
                    self.postMessage.emit("{}: info; shutdown app".format(self.__class__.__name__))
                    self.finished.emit()

        
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))               
                      
