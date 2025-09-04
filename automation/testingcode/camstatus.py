from alpaca.camera import Camera
from alpaca.exceptions import *
from datetime import datetime
import sys

ALPACA_ADDRESS = "127.0.0.1:11113"

def get_camera_status(camera_id):
    C = None
    status = {
    'camera_id': camera_id,
    'timestamp': datetime.now().isoformat()
    }
    
    try:
        C = Camera(ALPACA_ADDRESS, camera_id)
        
        properties = {
        'Connected': lambda: C.Connected,
        'Name': lambda: C.Name,
        'Description': lambda: C.Description,
        'CameraState': lambda: C.CameraState.name if hasattr(C.CameraState, 'name') else str(C.CameraState),
        'CCDTemperature': lambda: C.CCDTemperature,
        'CoolerOn': lambda: C.CoolerOn,
        'CoolerPower': lambda: C.CoolerPower,
        'CanSetCCDTemperature': lambda: C.CanSetCCDTemperature,
        'Gain': lambda: C.Gain,
        'Offset': lambda: C.Offset,
        'BinX': lambda: C.BinX,
        'BinY': lambda: C.BinY,
        'MaxBinX': lambda: C.MaxBinX,
        'MaxBinY': lambda: C.MaxBinY,
        'CameraXSize': lambda: C.CameraXSize,
        'CameraYSize': lambda: C.CameraYSize,
        'ExposureMin': lambda: C.ExposureMin,
        'ExposureMax': lambda: C.ExposureMax,
        'ExposureResolution': lambda: C.ExposureResolution,
        'ImageReady': lambda: C.ImageReady,
        'CanAbortExposure': lambda: C.CanAbortExposure,
        'PixelSizeX': lambda: C.PixelSizeX,
        'PixelSizeY': lambda: C.PixelSizeY,       
        }
        
        for prop_name, prop_func in properties.items():
            try:
                status[prop_name] = prop_func()
            except Exception as e:
                print(f"ERROR: {str(e)}")

    except Exception as e:
        status["general_error"] = f"General Error: {str(e)}"
    
    finally:
        if C:
            try:
                pass
            except:
                pass
                
    return status
     
def format_camera_status(status):
    camera_id = status.get('camera_id', 'Unknown')
    timestamp = status.get('timestamp', 'Unknown')
    
    print(f"\n{'='*50}")
    print(f"CAMERA {camera_id} STATUS - {timestamp}")
    print(f"{'='*50}")
    
    if 'general_error' in status:
        print(f"GENERAL ERROR: {status['general_error']}")
        return
        
    important_props = {
    'Connected': 'Connected',
    'Name': 'Camera Name',
    'Description': 'Description',
    'CameraState': 'Camera State'
    }    
    
    print(f"\nBASIC INFO:")
    for prop_key, disp_name in important_props.items():
        value = status.get(prop_key, 'Not Available')
        print(f"    {disp_name:15} {value}")
        
    temp_props = {
    'CCDTemperature': 'Current Temp',
    'SetCCDTemperature': 'Set Temp',
    'CoolerOn': 'Cooler On',
    'CoolerPower': 'Cooler Power',
    'CanSetCCDTemperature': 'Can Set Temp',
    }
    
    print(f"\nTEMPERATURE:")
    for prop_key, disp_name in temp_props.items():
        value = status.get(prop_key, 'Not Available')
        print(f"    {disp_name:15} {value}")
    
    
    imaging_props = {
    'Gain': 'Gain',
    'Offset': 'Offset',
    'CameraXSize': 'Camera X Size',
    'CameraYSize': 'Camera Y Size',
    'BinX': 'Binning X',
    'BinY': 'Binning Y',
    'MaxBinX': 'Max Bin X',
    'MaxBinY': 'Max Bin Y',
    'PixelSizeX': 'Pixel Size X',
    'PixelSizeY': 'Pixel Size Y',
    }
    
    print(f"\nIMAGING:")
    for prop_key, disp_name in imaging_props.items():
        value = status.get(prop_key, 'Not Available')
        print(f"    {disp_name:15} {value}")
        
        
    exp_props = {
    'ExposureMin': 'Exposure Min.',
    'ExposureMax': 'Exposure Max.',
    'ExposureResolution': 'Exp. Increment',
    'ImageReady': 'Image Ready',
    'CanAbortExposure': 'Can Abort',
    }
    
    print(f"\nEXPOSURE:")
    for prop_key, disp_name in exp_props.items():
        value = status.get(prop_key, 'Not Available')
        print(f"    {disp_name:15} {value}")
    
    handled_props = set(important_props.keys()) | set(temp_props.keys()) | set(imaging_props.keys()) | set(exp_props.keys())
    handled_props.update(['camera_id', 'timestamp', 'general_error'])
   
    other_props = {k: v for k, v in status.items() if k not in handled_props}
    
    if other_props:
        print(f"\nOTHER PROPERTIES:")
        for prop_key, value in sorted(other_props.items()):
            print(f"    {prop_key:15} {value}")
    
    
def main():
    print(f"\n{'='*50}")
    print("ZWO Camera Status Monitor (Alpyca)")
    print("="*50)
    
    try:
        for camera_id in [0,1]:
            try:
                status = get_camera_status(camera_id)
                format_camera_status(status)
            except Exception as e:
                print(f"\nERROR checking camera {camera_id}: {str(e)}")
                
        print(f"\n{'='*50}")
        print('Status Check Complete')
        
    except Exception as e:
        print('ERROR: {str(e)}')
        
    finally:
        print("\n--- PROGRAM EXITED ---")
        
if __name__ == '__main__':
    main()