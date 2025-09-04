import zwoasi as asi
import sys
import time
import numpy as np
from astropy.io import fits
import os


print('Initialising ZWO ASI SDK...')
asi.init('C:\\ASI SDK\\lib\\x64\\ASICamera2.dll')
cameras = asi.list_cameras()
if not cameras:
    sys.exit('No cameras found.')
    
print(f'Found {len(cameras)} ASI Cameras')

output_dir = "camera_test_images"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f'Created directory: {output_dir}')
    

for i, cam in enumerate(cameras):
    print(f'\nCamera #{i}: {cam}')
    try:
        camera = asi.Camera(i)
        info = camera.get_camera_property()
         
        print('    Taking test image...')
        
        test_width, test_height = info['MaxWidth'], info['MaxHeight']
        
        # test_width = (info['MaxWidth'] // 2) // 8 * 8
        # test_height = info['MaxHeight'] // 2
        
        camera.set_roi(width=test_width, height=test_height, image_type=asi.ASI_IMG_RAW16)
        exposure_us = int(5e6)  # 5s
        
        camera.set_control_value(asi.ASI_EXPOSURE, exposure_us)
        camera.set_control_value(asi.ASI_GAIN, 500) # 100 normal
        camera.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, 90)
        
        camera.start_exposure()
        
        while camera.get_exposure_status() == asi.ASI_EXP_WORKING:
            time.sleep(0.1)
            
        print('    Reading image data...')
        raw_data = camera.get_data_after_exposure()
        image = np.frombuffer(raw_data, dtype=np.uint16).reshape(test_height, test_width)
        
        model_clean = info.get('Name', f'Camera{i}').replace(' ', '_').replace('/', '_')
        filename = f"{model_clean}_test_5s.fits"
        filepath = os.path.join(output_dir, filename)
        
        hdu = fits.PrimaryHDU(image)
        hdu.header['CAMERA'] = info.get('Name', 'Unknown')
        hdu.header['CAMID'] = i
        hdu.header['EXPTIME'] = 5.0
        hdu.header['PIXSIZE'] = info.get('PixelSize', 0)
        
        hdu.writeto(filepath, overwrite=True)
        
        print(f'    Test Image Saved: {filepath}')
        print(f'    Image Size: {image.shape[1]} x {image.shape[0]}')
        print(f'    Data Range: {np.min(image)} - {np.max(image)}')
        
        camera.close()
    
    except Exception as e:
        print(f'Error: {e}')
        

print(f'\n{"="*50}')
print(f'Test images saved in {os.path.abspath(output_dir)}')


       
'''
camera_id = 0 is the spectro guide cam 294MM
camera_id = 1 is the main photometry cam 6200MM
'''