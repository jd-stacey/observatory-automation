### THIS IS THE ALPACA TEST CAM SCRIPT ###


from alpaca.camera import Camera
from alpaca.exceptions import *
from datetime import datetime
from astropy.io import fits
import os
import numpy as np
import sys
import time

ALPACA_ADDRESS = "127.0.0.1:11113"
OUTPUT_DIR = "alpaca_exposures"

def find_camera_by_scope(scope):
    for cam_id in [0, 1]:
        try:
            C = Camera(ALPACA_ADDRESS, cam_id)
            if not C.Connected:
                C.Connected = True
                time.sleep(0.5)
            name = C.Name
            
            if scope.lower().strip() == 'main' and "6200MM" in name:
                return cam_id
            elif scope.lower().strip() == 'guide' and '294MM' in name:
                return cam_id
        except:
            continue
    return None



def take_exposure(scope=None, camera_id=None, exposure_time=5.0, binning=4, gain=100, light=True, filename_prefix="test"):
    '''
    '''
    
    if camera_id is None and scope:
        camera_id = find_camera_by_scope(scope)
        if camera_id is None:
            print(f"ERROR: Could not find {scope} camera")
            return None
    elif camera_id is None:
        print(f"ERROR: Must specify either scope or camera_id")
        return None
        
    C = None
    
    try:
        print(f"\n{'='*50}")
        print(f"Camera {camera_id} - Starting {exposure_time:.1f}s exposure, Binning: {binning}x{binning}, Gain: {gain}")
        print(f"{'='*50}")
        
        C = Camera(ALPACA_ADDRESS, camera_id)
        
        if not C.Connected:
            print('Connecting to camera...')
            C.Connected = True
            time.sleep(2)
            
        print(f"Camera: {C.Name}    State: {C.CameraState}")
        
        C.BinX = binning
        C.BinY = binning
        
        try:
            max_x = C.CameraXSize
            max_y = C.CameraYSize
            binned_x = (max_x // binning) // 8 * 8      # Ensure integer multiple of 8
            binned_y = (max_y // binning) // 2 * 2      # Ensure integer multiple of 2
            
            C.StartX = 0
            C.StartY = 0
            C.NumX = binned_x
            C.NumY = binned_y
            
            print(f"ROI Set: {binned_x}x{binned_y} at {binning}x{binning} binning")
        
        except Exception as e:
            print(f"Error setting ROI: {e}")
        
        try:
            C.Gain = gain
        except Exception as e:
            print(f"Gain setting not supported: {e}")
            
        try:
            print(f"CCD Temp: {C.CCDTemperature:.1f} deg C")
        except:
            pass
            
        
        C.StartExposure(exposure_time, light)    #True for light frame, False for dark frame
        
        start_time = time.time()
        
        while not C.ImageReady:
            try:
                percent = C.PercentCompleted
                elapsed = time.time() - start_time
                print(f"\rProgress: {percent}% complete ({elapsed:.1f}s elapsed)", end='', flush=True)
            except:
                elapsed = time.time() - start_time
                print(f"\rProgress: ({elapsed:.1f}s elapsed)", end='', flush=True)
            time.sleep(exposure_time/5)
        print("\nExposure complete! Reading image...")
        
        image_array = np.array(C.ImageArray).transpose()
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_cam{camera_id}_exp{exposure_time}s_bin{binning}_{timestamp}.fits"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        hdu = fits.PrimaryHDU(image_array)
        
        hdu.header['CAMERA'] = C.Name
        hdu.header['CAMID'] = camera_id
        hdu.header['EXPTIME'] = exposure_time
        hdu.header['BINNING'] = binning
        hdu.header['GAIN'] = gain
        hdu.header['DATE-OBS'] = datetime.now().isoformat()
        hdu.header['OBSERVER'] = 'Alpaca_Test'
        hdu.header['OBJECT'] = 'Test_Frame'
        hdu.header['IMAGETYP'] = 'LIGHT'
        
        
        try:
            hdu.header['CCDTEMP'] = C.CCDTemperature
        except:
            pass
            
        try:
            hdu.header['COOLERON'] = C.CoolerOn
        except:
            pass
            
        try:
            hdu.header['PIXSIZEX'] = C.PixelSizeX
            hdu.header['PIXSIZEY'] = C.PixelSizeY
        except:
            pass
            
        try:
            hdu.header['XBINNING'] = C.BinX
            hdu.header['YBINNING'] = C.BinY
        except:
            pass
        
       
        hdu.writeto(filepath, overwrite=True)
        
        
        print(f"\nSUCCESS!")    
        print(f"Image Saved: {filename}")
        print(f"Image Size: {image_array.shape[1]} x {image_array.shape[0]}")
        print(f"Data Range: {np.min(image_array)} - {np.max(image_array)}")
        
        return filepath
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return None
        
def main():
    # scope = 'main' for 6200MM 'guide' for 294MM
    # light = False for dark frame, True for light frame
    take_exposure(scope='guide', exposure_time=2, binning=4, gain=100, light=True, filename_prefix="quick_test")
    
    
if __name__ == "__main__":
    main()