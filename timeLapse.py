"""@package docstring
"""
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os, glob
import re
import time
import traceback
import numpy as np
import smtplib, ssl
from webdav3.client import Client
from webdav3.exceptions import WebDavException
from PyQt5.QtCore import QSettings, QObject, QTimer, QEventLoop, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDialog, QFileDialog #, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QVBoxLayout, QGridLayout
from wait import wait_signal, wait_ms
import subprocess
    
class TimeLapse(QObject):
    postMessage = pyqtSignal(str)
    setLogFileName = pyqtSignal(str)
    setImageStoragePath = pyqtSignal(str)
    stopCamera = pyqtSignal()
    startCamera = pyqtSignal()
    takeImage = pyqtSignal()
    recordClip = pyqtSignal(int)
    startAutoFocus = pyqtSignal()
    focussed = pyqtSignal() # repeater signal
    setFocusTarget = pyqtSignal(int)
    captured = pyqtSignal() # repeater signal
    progressUpdate = pyqtSignal(int)
    finished = pyqtSignal()
    setFocusWithOffset = pyqtSignal(float)
    setTemperature = pyqtSignal(float)

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

            if self.timelapse_settings.contains('temperature'):
                self.setTemperature.emit(float(self.timelapse_settings.value('temperature')))

            # set logging file
            self.local_storage_path = self.settings.value('temp_folder')
            self.log_file_name = os.path.sep.join([self.local_storage_path, self.timelapse_settings.value('id') + ".log"])
            self.setLogFileName.emit(self.log_file_name)
            wait_ms(100)

            # clear temporary storage path
            self.postMessage.emit('{}: info; clearing temporary storage path: {}'.format(self.__class__.__name__, self.local_storage_path))
            files = glob.glob(os.path.sep.join([self.local_storage_path, '*']))
            for f in files:
                if not os.path.isdir(f):
                    os.remove(f)

            # copy timelapse setting file to storage folder
            os.system('cp {} {}'.format(timelapse_setting_file_name, self.local_storage_path))

            # create temporary image storage path
            self.local_image_storage_path = os.path.sep.join([self.local_storage_path,'img'])
            if not os.path.exists(self.local_image_storage_path):
                os.makedirs(self.local_image_storage_path)
            self.postMessage.emit('{}: info; temporary image storage path: {}'.format(self.__class__.__name__,
                                                                                  self.local_image_storage_path))
            self.setImageStoragePath.emit(self.local_image_storage_path)

            # set op connectivity
            if self.timelapse_settings.contains('connections/storage'):
                if self.timelapse_settings.value('connections/storage') == 'rclone':
                    # rclone to path provided in connections.ini file
                    self.server_storage_path = self.conn_settings.value('rclone/storage_path') + ':' + self.timelapse_settings.value('id')

                    try:
                        subprocess.run(["rclone", "mkdir", self.server_storage_path])
                        subprocess.run(["rclone", "copy", "--no-traverse", self.local_storage_path, self.server_storage_path])

                        # create directory structure on server
                        for offset in self.timelapse_settings.value('acquisition/offsets'):
                            subprocess.run(["rclone", "mkdir", os.path.sep.join([self.server_storage_path, offset])])
                        
                    except Exception as err:
                        self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))

                    self.postMessage.emit('{}: info; rclone connection to {}'.format(self.__class__.__name__, self.server_storage_path))
                    
                elif self.timelapse_settings.value('connections/storage') == 'wbedav':
                    # open WebDAV connection to server, using credentials from connections.ini file
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

                    # copy files to server
                    self.webdav_client.push(local_directory=self.local_storage_path, remote_directory=self.server_storage_path)
                    self.server_log_file_name = os.path.sep.join([self.server_storage_path, self.timelapse_settings.value('id') + ".log"])

                    # create directory structure on server
                    for offset in self.timelapse_settings.value('acquisition/offsets'):
                        self.webdav_client.mkdir(os.path.sep.join([self.server_storage_path, offset]))

                    self.postMessage.emit('{}: info; WebDAV connection to {}: {}'.format(self.__class__.__name__,
                                                                                     self.conn_settings.value('webdav/hostname'),
                                                                                     self.server_storage_path))
                else:
                    self.postMessage.emit('{}: error; unknown remote'.format(self.__class__.__name__))
                
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))


        # get timelapse schedule
        t = time.strptime(self.timelapse_settings.value('run/duration')[1],'%H:%M:%S')
        days = int(self.timelapse_settings.value('run/duration')[0].split('d')[0])
        self.run_duration_s = ((24*days + t.tm_hour)*60 + t.tm_min)*60 + t.tm_sec
        t = time.strptime(self.timelapse_settings.value('run/wait'),'%H:%M:%S')
        self.run_wait_s = (t.tm_hour*60 + t.tm_min)*60 + t.tm_sec

        message = """Subject: Experiment started \n\n ."""
        # do something fancy here in future: https://realpython.com/python-send-email/#sending-fancy-emails
        self.sendNotification(message)            

        self.postMessage.emit('{}: info; run duration: {} s, run wait: {} s'.format(self.__class__.__name__,
                                                                                    self.run_duration_s,
                                                                                    self.run_wait_s))
        # start timer
        self.prev_note_nr = 0 # for logging
        self.start_time_s = time.time()
        self.timer.start(0)

        
    @pyqtSlot()
    def stop(self):
        try:
            self.postMessage.emit("{}: info; stopping worker".format(self.__class__.__name__))
            self.running = False
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))
            

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
            if self.timelapse_settings.value('acquisition/autofocus', False, type=bool):
                focusTarget = self.timelapse_settings.value('acquisition/focustarget', 0, type=int)
                self.postMessage.emit('{}: info; using focus target {}'.format(self.__class__.__name__, focusTarget))
                self.setFocusTarget.emit(focusTarget)
                wait_ms(200) # wait to let grid detection fire up
                self.startAutoFocus.emit()
                wait_signal(self.focussed, 60000)

            # move through all offset
            for offset_str in self.timelapse_settings.value('acquisition/offsets'):
                
                # set offset                
                offset = float(offset_str)
                self.setFocusWithOffset.emit(offset)
                wait_ms(500) # wait to let camera image settle

                # clear local image storage path
                self.postMessage.emit('{}: info; clearing temporary image storage path: {}'.format(self.__class__.__name__, self.local_image_storage_path))
                files = glob.glob(os.path.sep.join([self.local_image_storage_path, '*']))
                for f in files:
                    os.remove(f)
                
                # take image or video
                if self.timelapse_settings.value('acquisition/snapshot', False, type=bool):
                    self.takeImage.emit()
                    wait_signal(self.captured, 30000) # snapshot taken
                if self.timelapse_settings.value('acquisition/videoclip', False, type=bool):
                    duration = self.timelapse_settings.value('acquisition/clip_length', 10, type=int)
                    self.recordClip.emit(duration)                    
                    wait_signal(self.captured, (30+duration)*1000) # video taken
                    
                # push capture to remote
                if self.timelapse_settings.contains('connections/storage'):
                    if self.timelapse_settings.value('connections/storage') == 'rclone':
                        subprocess.run(["rclone", "copy", "--no-traverse", self.local_image_storage_path, os.path.sep.join([self.server_storage_path, offset_str])])
                    elif self.timelapse_settings.value('connections/storage') == 'wbedav':
                        self.webdav_client.push(remote_directory=os.path.sep.join([self.server_storage_path, offset_str]),
                                                local_directory=self.local_image_storage_path)
                val = self.focus + offset if self.focus is not None else offset
                self.postMessage.emit('{}: info; saved image and/or video at focus: {:.1f}%'.format(self.__class__.__name__, val))

            # return to no offset
            self.setFocusWithOffset.emit(0)
            wait_ms(100) # wait to let camera image settle
            
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

            # send a notification
            note_nr = int(progress_percentage/10)
            if note_nr != self.prev_note_nr:
                self.prev_note_nr = note_nr

                if progress_percentage < 100:
                    message = """Subject: Progress = {}% \n\n Still {} s left""".format(progress_percentage, int(self.run_duration_s - elapsed_total_time_s))
                else:
                    message = """Subject: Experiment finalized \n\n  Done."""
                # do something fancy here in future: https://realpython.com/python-send-email/#sending-fancy-emails
                self.sendNotification(message)              

            # check if we still have time to do another round
            if elapsed_total_time_s + self.run_wait_s < self.run_duration_s:
                self.timer.setInterval(self.run_wait_s*1000)
                self.postMessage.emit("{}: info; wait for {:.1f} s".format(self.__class__.__name__, self.run_wait_s))
            else:
                self.timer.stop()
                self.postMessage.emit("{}: info; run finalized".format(self.__class__.__name__))
                if self.timelapse_settings.value('shutdown', False, type=bool):
                    self.postMessage.emit("{}: info; shutdown app".format(self.__class__.__name__))
                    self.finished.emit()

            # push log file
            if self.timelapse_settings.contains('connections/storage'):
                if self.timelapse_settings.value('connections/storage') == 'rclone':
                    print(["rclone", "copy", "--no-traverse", self.log_file_name, self.server_storage_path])
                    subprocess.run(["rclone", "copy", "--no-traverse", self.log_file_name, self.server_storage_path])
                elif self.timelapse_settings.value('connections/storage') == 'wbedav':
                    self.webdav_client.push(remote_directory=self.server_storage_path, local_directory=self.local_storage_path)
                    
        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))
            

    def sendNotification(self, message):
##        if self.timelapse_settings.contains('connections/email'):
        conn_settings = QSettings("connections.ini", QSettings.IniFormat)
        context = ssl.create_default_context()  # Create a secure SSL context
        try:
            host = conn_settings.value('smtp/host')
            port = conn_settings.value('smtp/port', 400, type=int)
            
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                login = conn_settings.value('smtp/login')
                password = conn_settings.value('smtp/password')
                server.login(login, password)
                server.sendmail(conn_settings.value('smtp/login'), \
                                self.timelapse_settings.value('connections/email'), \
                                message)
                print(conn_settings.value('smtp/login'), \
                                self.timelapse_settings.value('connections/email'), \
                                message)
            self.postMessage.emit("{}: info; notification send to {}".format(self.__class__.__name__, self.timelapse_settings.value('connections/email')))
        except Exception as err:
            traceback.print_exc()
            self.signals.error.emit((type(err), err.args, traceback.format_exc()))            
                          
