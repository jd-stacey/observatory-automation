import sys, os, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from autopho.config.loader import ConfigLoader
from autopho.devices.camera import CameraManager
from autopho.imaging.fits_utils import create_fits_file

def setup_logging():
    
    logging.basicConfig(
        level=logging.INFO,
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
def test_camera_capture():
    try:
        config_loader = ConfigLoader("config")
        config_loader.load_all_configs()
        
        device_config = config_loader.get_config('devices')
        header_config = config_loader.get_header_config()
        camera_manager = CameraManager()
        camera_configs = device_config.get('cameras', {})
        if not camera_manager.discover_cameras(camera_configs):
            print("ERROR: Camera discovery failed")
            return False
        if not camera_manager.connect_camera('guide'):
            print("ERROR: Failed to connect to main camera")
            return False
        main_camera = camera_manager.get_main_camera()
        if not main_camera:
            print("ERROR: Main camera not found")
            return False
        
        settings = main_camera.get_camera_settings()
        if not main_camera.set_roi_and_binning(4):
            print("WARNING: ROI Setup failed")
        else:
            print("    ROI and binning set")
            
        target_info = {
            'object_name': 'TEST_CAPTURE',
            'ra_hours': 12.5,
            'dec_degrees': -15.3,
            'magnitude': 10.0
        }
        
        exposure_time = 2
        filter_code = 'C'
        
        image_array = main_camera.capture_image(
            exposure_time=exposure_time,
            binning=4, 
            gain=100, 
            light=False
            )
        if image_array is None:
            print("ERROR: Image capture returned None")
            return False
        
        try:
            hdu = create_fits_file(
                image_array=image_array,
                target_info=target_info, 
                camera_device=main_camera, 
                config_loader=config_loader,
                filter_code=filter_code,
                exposure_time=exposure_time
            )
            
            test_dir = Path("test_captures")
            test_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_capture_{filter_code}_{timestamp}_{exposure_time}s.fits"
            filepath = test_dir / filename
            
            hdu.writeto(str(filepath), overwrite=True)
            
        except Exception as e:
            print(f"ERROR: FIRST file creation failed: {e}")
            return False
        
        return True
    
    except Exception as e:
        print(f"\nERROR: Test failed with exception :{e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            if camera_manager in locals():
                camera_manager.disconnect_all_cameras()
        except:
            pass
        
def main():
    setup_logging()
    
    success = test_camera_capture()
    
    if success:
        print("Success")
    else:
        print("FAILURE, DOOM AND GLOOM")
        sys.exit(1)
        
if __name__ == "__main__":
    main()