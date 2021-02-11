## @brief ReadTemperatures measure CPU /GPU temperature
## @author Jeroen Veen
import os
import traceback
from PyQt5.QtCore import QTimer, QObject, pyqtSlot, pyqtSignal

## @brief Periodically read temperatures and signal an alarm if threshold is exceeded
## @author Jeroen Veen
class SystemTemperatures(QObject):
    postMessage = pyqtSignal(str)    
    timer = QTimer()
    alarm = pyqtSignal()
    alarmRemoved = pyqtSignal()
    failure = pyqtSignal()

    def __init__(self, interval=1, alarm_temperature = 50, failure_temperature = 75):
        super().__init__()
        self.interval = 1000*interval
        self.threshold = alarm_temperature
        self.fail_threshold = failure_temperature
        self.timer.timeout.connect(self.update)
        self.timer.start(self.interval)
        self.alarmed = False
        

    def update(self):
        try:
            cpu_temp = float(self.get_cpu_tempfunc())
            self.postMessage.emit('{}: info; T_CPU={:.1f}°C'.format(self.__class__.__name__, cpu_temp))
            if (cpu_temp > self.fail_threshold):
                self.failure.emit()
                self.postMessage.emit('{}: error; temperature gets too high'.format(self.__class__.__name__))
            elif (cpu_temp > self.threshold) and not self.alarmed:
                self.alarm.emit()
                self.alarmed = True
                self.postMessage.emit('{}: info; temperature alarm on'.format(self.__class__.__name__))
            elif (cpu_temp < 0.95*self.threshold) and self.alarmed:
                self.alarmRemoved.emit()
                self.alarmed = False
                self.postMessage.emit('{}: info; temperature alarm off'.format(self.__class__.__name__))
        except Exception as err:
            traceback.print_exc()
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))
            

    @pyqtSlot()
    def resetAlarm(self):
        self.alarmRemoved.emit()
        self.alarmed = False
        

    @pyqtSlot()
    def stop(self):
        self.msg("info;stopping")
        if self.timer.isActive():
            self.timer.stop()
        self.signals.finished.emit()

    ## @brief Return CPU temperature as a string, based on https://github.com/gavinlyonsrepo/raspberrypi_tempmon
    def get_cpu_tempfunc(self):
        """ Return CPU temperature """
        result = 0
        try:
            mypath = "/sys/class/thermal/thermal_zone0/temp"
            with open(mypath, 'r') as mytmpfile:
                for line in mytmpfile:
                    result = line
            result = float(result)/1000
            result = round(result, 1)
        except Exception as err:
            traceback.print_exc()
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))
        return str(result)
    

    ## @brief Return GPU temperature as a string, based on https://github.com/gavinlyonsrepo/raspberrypi_tempmon
#     a some point os.popen keeps throwing an OSError: [Errno 12] Cannot allocate memory
# no clue how to solve this, so just skip GPU temperature
    def get_gpu_tempfunc(self):
        """ Return GPU temperature as a character string"""
        res = os.popen('/opt/vc/bin/vcgencmd measure_temp').readline()
        res = res.replace("temp=", "")
        res = res.replace("'C", "")
        return res
