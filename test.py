import os
from subprocess import run, check_output

storagePath = 'tmp'

output = check_output(["ls", storagePath])
print(output)

filename = "0001613058923664"
filename = os.path.sep.join([storagePath, filename])
output = check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1", filename + '.h264'])
print("our output: {}".format(output))
