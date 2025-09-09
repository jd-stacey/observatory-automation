import time
import logging
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

try:
    from alpaca.camera import Camera
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class CameraError(Exception):
    pass

class CameraDevice:
    
    def __init__(self, device_id: int, name: str, camera_obj: Any, config: Dict[str, Any]):
        self.device_id = device_id
        self.name = name
        self.camera = camera_obj
        self.config = config
        self.role = config.get('role', 'unknown')
        self.connected = False
        
    def connect(self):
        try:
            if not self.camera.Connected:
                self.camera.Connected = True
                time.sleep(0.5)
                
            self.connected = self.camera.Connected
            if self.connected:
                logger.info(f"Connected to {self.role} camera: {self.name} (ID: {self.device_id})")
                
                #Initialize cooler after camera connection
                self.initialize_cooler()
            
            return self.connected
        except Exception as e:
            logger.error(f"Failed to connected to camera {self.name}: {e}")
            return False
        
    def disconnect(self):
        try:
            if self.camera and self.connected:
                self.camera.Connected = False
                self.connected = False
                logger.info(f"Disconnected from {self.role} camera {self.name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to disconnect camera {self.name}: {e}")
            return False
        
    def get_camera_settings(self) -> Dict[str, Any]:
        if not self.connected:
            raise ConnectionError(f"Camera: {self.name} not connected")
        settings = {}
        try:
            cam = self.camera
            settings.update({
                'camera_name': cam.Name,
                'camera_id': self.device_id,
                'camera_state': getattr(cam, 'CameraState', 'Unknown'),
                'bin_x': getattr(cam, 'BinX', 'None'),
                'bin_y': getattr(cam, 'BinY', 'None'),
                'size_x': getattr(cam, 'CameraXSize', 'None'),
                'size_y': getattr(cam, 'CameraYSize', 'None'),
                'gain': getattr(cam, 'Gain', None),
                'pixel_size_x': getattr(cam, 'PixelSizeX', None),
                'pixel_size_y': getattr(cam, 'PixelSizeY', None),
                'ccd_temperature': getattr(cam, 'CCDTemperature', None),
                'cooler_on': getattr(cam, 'CoolerOn', None)
            })
        except Exception as e:
            logger.error(f"Failed to get camera settings: {e}")
            
        return settings
    
    def set_roi_and_binning(self, binning: int = None) -> bool:
        if not self.connected:
            logger.error(f"Camera {self.name} not connected")
            return False
        try:
            cam = self.camera
            
            if binning is None:
                binning = self.config.get('default_binning', 4)
                
            cam.BinX = binning
            cam.BinY = binning
            max_x = cam.CameraXSize
            max_y = cam.CameraYSize
            binned_x = (max_x // binning) // 8 * 8      # Ensure integer multiple of 8
            binned_y = (max_y // binning) // 2 * 2      # Ensure integer multiple of 2
            
            cam.StartX = 0
            cam.StartY = 0
            cam.NumX = binned_x
            cam.NumY = binned_y
            
            logger.debug(f"ROI Set: {binned_x}x{binned_y} at {binning}x{binning} binning")
            return True
        except Exception as e:
            logger.error(f"Failed to set ROI and binning: {e}")
            
    def capture_image(self, exposure_time: float, binning: int = None, gain: int = None, light: bool = True) -> Optional[np.ndarray]:
        if not self.connected:
            raise ConnectionError(f"Camera {self.name} not connected")
        
        try:
            cam = self.camera
        
            if not cam.Connected:
                logger.warning(f"Camera {self.name} not connected, attempting reconnection")
                cam.Connected = True
                time.sleep(0.5)
                
            logger.info(f"Starting {exposure_time:.1f} s exposure, Camera: {cam.Name}")
            
            if not self.set_roi_and_binning():
                raise CameraError("Failed to set ROI and binning")
            
            try:
                if gain is None:
                    gain = self.config.get('default_gain', 100)
                cam.Gain = gain
            except Exception as e:
                logger.warning(f"Gain setting not supported: {e}")
                
            try:
                temp = cam.CCDTemperature
                logger.debug(f"CCD Temperature: {temp:.1f} C")
            except:
                pass
            
            cam.StartExposure(exposure_time, light)
            start_time = time.time()
            
            while not cam.ImageReady:
                try:
                    percent = cam.PercentCompleted
                    elapsed = time.time() - start_time
                    if elapsed % 5 < 0.5:
                        logger.info(f"Exposure progress: {percent:.1f}% ({elapsed:.1f} s)")
                except:
                    pass
                time.sleep(min(0.5, exposure_time / 10))
                
            logger.debug('Exposure complete, reading image...')
            image_array = np.array(cam.ImageArray).transpose()
            
            logger.info(f"Image captured: {image_array.shape[1]}x{image_array.shape[0]}, "
                        f"range: {np.min(image_array)}-{np.max(image_array)}")
            
            return image_array
        except Exception as e:
            logger.error(f"Image capture failed: {e}")
            raise CameraError(f"Capture failed: {e}")
        
        
    def initialize_cooler(self, target_temp: float = -10.0) -> bool:
        """Initialize camera cooler to target temperature"""
        if not self.connected:
            logger.error(f"Camera {self.name} not connected")
            return False
        
        try:
            cam = self.camera
            
            # Check if cooler is available
            if not hasattr(cam, 'CoolerOn') or not hasattr(cam, 'SetCCDTemperature'):
                logger.warning(f"Camera {self.name} does not support cooling")
                return True  # Not an error if cooler not available
            
            # Get target temperature from config or use default
            target_temp = self.config.get('target_temperature', target_temp)
            
            logger.debug(f"Setting cooler target: {target_temp}°C")
            cam.SetCCDTemperature = target_temp
            cam.CoolerOn = True
            
            # Give it a moment to start
            time.sleep(1.0)
            
            current_temp = cam.CCDTemperature
            logger.debug(f"Cooler enabled: current {current_temp:.1f}°C, target {target_temp}°C")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize cooler: {e}")
            return False
    
    def turn_cooler_off(self) -> bool:
        if not self.connected:
            logger.error(f"Camera {self.name} not connected")
            return False
        
        try:
            cam = self.camera
            
            # Check if cooler is available
            if not hasattr(cam, 'CoolerOn') or not hasattr(cam, 'SetCCDTemperature'):
                logger.warning(f"Camera {self.name} does not support cooling")
                return True  # Not an error if cooler not available
            
            logger.debug("Turning cooler off...")
            cam.CoolerOn = False
            time.sleep(0.5)
            if cam.CoolerOn:
                logger.warning("Cooler did not turn off correctly - check manually")
                return True     # continue even if unsuccessful
            else:
                logger.debug("Cooler turned off successfully")
                return True
        except Exception as e:
            logger.warning(f"Failed to turn cooler off: {e}")
            return True         # continue even if unsuccessful
                
    
        
class CameraManager:
    
    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise CameraError(f"Alpaca Library not available. Please install")
        
        self.cameras = {}
        self.discovered_devices = []
        
    def discover_cameras(self, camera_configs: Dict[str, Dict[str, Any]]):
        logger.debug(f"Discovering cameras...")
        self.cameras.clear()
        self.discovered_devices.clear()
        
        first_config = next(iter(camera_configs.values()))
        address = first_config.get('address', '127.0.0.1:11113')
        
        for device_id in [0, 1]:
            try:
                camera_obj = Camera(address, device_id)
                try:
                    name = camera_obj.Name
                except:
                    try:
                        camera_obj.Connected = True
                        time.sleep(0.5)
                        name = camera_obj.Name
                        camera_obj.Connected = False
                    except:
                        logger.warning(f"Could not get name for camera device {device_id}")
                        continue
                self.discovered_devices.append({
                    'device_id': device_id,
                    'name': name,
                    'camera_obj': camera_obj
                })
                
                logger.info(f"Found camera device {device_id}: {name}")
                
            except Exception as e:
                logger.debug(f"No camera found at device ID {device_id}: {e}")
                
        missing_roles = []
        for role, config in camera_configs.items():
            name_pattern = config.get('name_pattern', '')
            
            matched = False
            for device in self.discovered_devices:
                if name_pattern in device['name']:
                    camera_device = CameraDevice(
                        device['device_id'],
                        device['name'],
                        device['camera_obj'],
                        config
                    )
                    self.cameras[role] = camera_device
                    matched = True
                    logger.info(f"Matched {role} camera: {device['name']} (pattern: '{name_pattern}')")
                    break
            
            if not matched:
                missing_roles.append(role)
                
        if missing_roles:
            logger.error(f"Could not find cameras for role: {missing_roles}")
            logger.info(f"Available cameras:")
            for device in self.discovered_devices:
                logger.info(f"  Device {device['device_id']}: {device['name']}")
            return False
        
        logger.info(f"Successfully discovered {len(self.cameras)} cameras")
        return True
    
    def connect_camera(self, role: str):
        if role not in self.cameras:
            logger.error(f"Camera role {role} not found")
            return False
        return self.cameras[role].connect()
    
    def connect_all_cameras(self):
        success = True
        for role, camera in self.cameras.items():
            if not camera.connect():
                success = False
        return success
    
    def disconnect_all_cameras(self):
        success = True
        for role, camera in self.cameras.items():
            if not camera.disconnect():
                success = False
        return success
    
    def shutdown_all_coolers(self):
        for role, camera in self.cameras.items():
            if camera and camera.connected:
                try:
                    logger.debug(f"Turning off cooler for {role} camera...")
                    camera.turn_cooler_off()
                except Exception as e:
                    logger.warning(f"Error shutting down {role} camera cooler: {e}")
    
    
    def get_camera(self, role: str):
        return self.cameras.get(role)
    
    def get_main_camera(self) -> Optional[CameraDevice]:
        return self.get_camera('main')
    
    def get_guide_camera(self) -> Optional[CameraDevice]:
        return self.get_camera('guide')            
    
    def is_camera_connected(self, role: str):
        camera = self.get_camera(role)
        return camera is not None and camera.connected
    
    def get_camera_status(self, role: str):
        camera = self.get_camera(role)
        if not camera:
            return {'found': False}
        
        status = {
            'found': True,
            'role': camera.role,
            'device_id': camera.device_id,
            'name': camera.name,
            'connected': camera.connected
        }
        
        if camera.connected:
            try:
                cam = camera.camera
                status.update({
                    'camera_state': getattr(cam, 'CameraState', 'Unknown'),
                    'temperature': getattr(cam, 'CCDTemperature', None),
                    'cooler_on': getattr(cam, 'CoolerOn', None),
                    'gain': getattr(cam, 'Gain', None),
                    'binning_x': getattr(cam, 'BinX', None),
                    'binning_y': getattr(cam, 'BinY', None),
                    'size_x': getattr(cam, 'CameraXSize', None),
                    'size_y': getattr(cam, 'CameraYSize', None)
                })
            except Exception as e:
                status['error'] = f"Failed to get camera details: {e}"
                
        return status
    
    def list_all_cameras(self):
        cameras_list = []
        for role, camera in self.cameras.items():
            cameras_list.append(self.get_camera_status(role))
        return cameras_list
    
def find_camera_by_scope(scope:str, address: str = "127.0.0.1:11113"):
    '''legacy check'''
    for cam_id in [0, 1]:
        try:
            C = Camera(address, cam_id)
            if not C.Connected:
                C.Connected = True
                time.sleep(0.5)
            name = C.Name
            C.Connected = False
            
            if scope.lower().strip() == 'main' and "6200MM" in name:
                return cam_id
            elif scope.lower().strip() == 'guide' and "294MM" in name:
                return cam_id
        except:
            continue
    return None

