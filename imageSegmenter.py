"""@package docstring
Segment the image based on the cell counter grid 

TODO: how to pass roi's and imageQuality? via getter or (result) signal?
No median blurring, but bilateral?
"""
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import numpy as np
import cv2
import inspect
import traceback
import matplotlib.pyplot as plt
from PyQt5.QtCore import QObject, QSettings, QThread, QTimer, QEventLoop, pyqtSignal, pyqtSlot
from fps import FPS

class ImageSegmenter(QObject):
    """Image segmenter
        \param image
        \return image
    """
    image = None
    imageQuality = 0
    postMessage = pyqtSignal(str)
    result = pyqtSignal(np.ndarray)
    
    def __init__(self, *args, **kwargs):
        """The constructor."""
        super().__init__()

        # Findgrid parameter as a fraction of the image size
        self.sizeFrac = kwargs['sizeFrac'] if 'sizeFrac' in kwargs else 0.005

        # Plotting
        self.plot = kwargs['plot'] if 'plot' in kwargs else False

        # Debug plot
        self.debugPlot = kwargs['debugPlot'] if 'debugPlot' in kwargs else False

        self.fps = FPS().start()

        if self.debugPlot:
            self.fig, (self.ax1, self.ax2) = plt.subplots(2,1)
            self.graph1 = None
            self.graph2 = None
            self.ax1.grid(True)
            self.ax2.grid(True)
            plt.show(block=False)
        
    def __del__(self):
        """The deconstructor."""
        pass    
        
    def start(self, Image):
        """Image processing function."""        
        try:
            self.image = Image

            # Find grid pattern along row and column averages
            row_av = cv2.reduce(self.image, 0, cv2.REDUCE_AVG, dtype=cv2.CV_32S).flatten('F')
            row_seg_list, row_mask, smooth_row_av = find1DGrid(row_av, int(self.sizeFrac*row_av.size))
            col_av = cv2.reduce(self.image, 1, cv2.REDUCE_AVG, dtype=cv2.CV_32S).flatten('F')
            col_seg_list, col_mask, smooth_col_av = find1DGrid(col_av, int(self.sizeFrac*col_av.size))

            # Create ROI list and annotate image
            list_width = len(row_seg_list)
            list_length = len(col_seg_list)
            self.ROIs = np.zeros([list_width*list_length,4], dtype=np.uint16)
            self.ROI_total_area = 0
            for i, x in enumerate(row_seg_list):
                for j, y in enumerate(col_seg_list):
                    # ROI: (left,top,width,height)
                    self.ROIs[i+j*list_width] = [x[0],y[0],x[1],y[1]]
                    cv2.rectangle(self.image, (x[0],y[0]), (x[0]+x[1],y[0]+y[1]), (0, 255, 0), 2)
                    self.ROI_total_area += x[1]*y[1]

            # Compute metrics from grid pattern
            # Rationale: parameterize edge histogram by variance to amplitude (0-bin) ratio
            col_stuff = np.diff(smooth_col_av[~col_mask]) # slice masked areas
            col_stuff = col_stuff[50:-50]  # slice edge effects
            row_stuff = np.diff(smooth_row_av[~row_mask]) # slice masked areas
            row_stuff = row_stuff[50:-50]  # slice edge effects
            self.imageQuality = np.sqrt( np.var(col_stuff) # / col_stuff[np.abs(col_stuff) < .5].size
                                         + np.var(row_stuff) ) # / row_stuff[np.abs(row_stuff) < .5].size )
            # Rationale: sharp edges result in ROI increase
##            self.imageQuality *= 100*(self.ROI_total_area/np.prod(self.image.shape[0:2]))
            self.imageQuality = round(self.imageQuality,2)
                
            # Plot curves
            if self.debugPlot:
                col_hist, bin_edges = np.histogram(col_stuff, bins=np.arange(-5,5,.1), density=True)
                
                # Draw grid lines
                self.ax1.clear()
                self.graph1 = self.ax1.plot(row_stuff)[0]  # (col_hist)[0]
                self.ax2.clear()
                self.graph2 = self.ax2.plot(col_stuff)[0]  # smooth_col_av)[0]

                # We need to draw *and* flush
                self.fig.canvas.draw()
                self.fig.canvas.flush_events()

### This way of plotting is probably faster, but right now can't get it to work with clearing as well                    
##                    if (self.graph1 is None):
##                        self.graph1 = self.ax1.plot(smooth_row_av)[0]
##                        self.graph2 = self.ax2.plot(smooth_col_av)[0]
##                    else: 
##                        self.graph1.set_image(np.arange(smooth_row_av.shape[1]), smooth_row_av)
##                        self.graph2.set_image(np.arange(smooth_col_av.shape[1]), smooth_col_av)
##                    # Need both of these in order to rescale
##                    self.ax1.relim()
##                    self.ax1.autoscale_view()
##                    self.ax2.relim()
##                    self.ax2.autoscale_view()

        except Exception as err:
            self.postMessage.emit("{}: error; type: {}, args: {}".format(self.__class__.__name__, type(err), err.args))            
        else:
            self.fps.update()
        finally:
            return self.image, self.imageQuality

            
def moving_average(x, N=5):
    if N > 1 and (N & 1) == 1:
        x = np.pad(x, pad_width=(N // 2, N // 2),
                   mode='constant')  # Assuming N is odd
        cumsum = np.cumsum(np.insert(x, 0, 0))
        return (cumsum[N:] - cumsum[:-N]) / float(N)
    else:
        raise ValueError("Moving average size must be odd and greater than 1.")

def find1DGrid(data, N):    
    if N <= 1:
        raise ValueError('findGrid parameter <= 1')
    if (N & 1) != 1:  # enforce N to be odd
        N += 1
    gridSmoothKsize = N
    gridMinSegmentLength = 10*N
    
    # High-pass filter, to suppress uneven illumination
    data = np.abs(data - moving_average(data, int(3*N)))
    data[:N] = 0 # cut off MA artifacts
    data[-N:] = 0 # cut off MA artifacts, why not -(N-1)/2?? ??
    smooth_data = moving_average(data, gridSmoothKsize)
    smooth_data = smooth_data - np.mean(smooth_data)
    mask_data = np.zeros(data.shape, dtype='bool')  # mask grid lines
    mask_data[np.where(smooth_data < 0)[0]] = True
    
    # Now filter mask_data based on segment length and suppress too short segments
    prev_x = False
    segmentLength = 0
    segmentList = []
    for index, x in enumerate(mask_data):
        if x:  # segment
            segmentLength += 1
        elif x != prev_x:  # falling edge
            if segmentLength < gridMinSegmentLength:  # suppress short segments
                mask_data[index - segmentLength: index] = False
                # print(diff(data[index - segmentLength:index]))
            else:
                segmentList.append((index - segmentLength, segmentLength))  # Save segment start and length
            segmentLength = 0  # reset counter
        prev_x = x

    return (segmentList, mask_data, smooth_data)


    
