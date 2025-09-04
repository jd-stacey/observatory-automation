import zwoasi as asi
import sys
import time
import numpy as np
from astropy.io import fits
import os


print('Initialising ZWO ASI SDK...')
asi.init('C:\\ASI SDK\\lib\\x64\\ASICamera2.dll')

num_cameras = asi.get_num_cameras()
print(f"Found {num_cameras} ASI Cameras")

if num_cameras == 0:
    sys.exit('Exiting - No cameras found.')

cameras = asi.list_cameras()
  
fields = ['CameraID', 'MaxHeight', 'MaxWidth', 'IsColorCam', 'PixelSize', 'IsCoolerCam', 'IsUSB3Host', 'IsUSB3Camera', 'ElecPerADU', 'BitDepth']
for i, cam in enumerate(cameras):
    print(f'\nCamera #{i}: {cam}')
    try:
        camera = asi.Camera(i)
        info = camera.get_camera_property()
        
        for k, v in info.items():
            if k in fields:
                print(f"    {k}: {v}")      
        
        camera.close()
    
    except Exception as e:
        print(f'Error: {e}')
        


       
'''
camera_id = 0 is the spectro guide cam 294MM
camera_id = 1 is the main photometry cam 6200MM
'''