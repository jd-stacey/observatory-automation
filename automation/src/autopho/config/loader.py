import yaml
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigurationError (Exception):
    pass

class ConfigLoader:
    
    
    def __init__(self, config_dir: str = 'config'):
        self.config_dir = Path(config_dir)
        self._configs = {}
        self._validate_config_dir()
        
    def _validate_config_dir(self):
        if not self.config_dir.exists():
            raise ConfigurationError(f"Configuartion directory not found: {self.config_dir}")
        
        required_files = [
            "observatory.yaml",
            "devices.yaml",
            "exposures.yaml",
            "paths.yaml",
            "headers.yaml",
            "platesolving.yaml",
            'field_rotation.yaml'
        ]
        
        missing = []
        for file in required_files:
            if not (self.config_dir / file).exists():
                missing.append(file)
                
        if missing:
            raise ConfigurationError(f"Missing configuration files: {missing}")
        
    
    def _load_yaml_file(self,filename: str):
        filepath = self.config_dir / filename
        try:
            with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
                    logger.debug(f"Loaded config file: {filename}")
                    return data or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {filename}: {e}")
        except IOError as e:
            raise ConfigurationError(f"Cannot read {filename}: {e}")
        
    def load_all_configs(self):
        config_files = {
            'observatory': 'observatory.yaml',
            'devices': 'devices.yaml',
            'exposures': 'exposures.yaml',
            'paths': 'paths.yaml',
            'headers': 'headers.yaml',
            'platesolving': 'platesolving.yaml',
            'field_rotation': 'field_rotation.yaml'
        }
                            
        self._configs = {}
        for key, filename in config_files.items():
            self._configs[key] = self._load_yaml_file(filename)
            
        self._validate_configs()
        logger.debug("All configuration files loaded successfully")
        return self._configs
    
    def _validate_configs(self):
        obs = self._configs.get('observatory', {})
        required_obs = ['latitude', 'longitude', 'altitude', 'min_altitude', 'twilight_altitude']
        for field in required_obs:
            if field not in obs:
                raise ConfigurationError(f"Missing required observatory field: {field}")
       
        devices = self._configs.get('devices', {})    
        if 'telescope' not in devices:
            raise ConfigurationError(f"Missing telescope configuration")
        
        telescope = devices['telescope']
        if 'type' not in telescope:
            raise ConfigurationError(f"Missing telescope type")
        
        rotator = devices.get('rotator', {})
        if rotator:
            required_fields = ['type', 'address', 'device_number']
            for field in required_fields:
                if field not in rotator:
                    raise ConfigurationError(f'Missing required rotator config field: {field}')
        
        cover = devices.get('cover', {})
        if cover:
            required_fields = ['type', 'address', 'device_number']
            for field in required_fields:
                if field not in rotator:
                    raise ConfigurationError(f'Missing required cover config field: {field}')
        
        cameras = devices.get('cameras', {})
        if not cameras:
            raise ConfigurationError("No cameras configured")
        
        for role, camera_config in cameras.items():
            if 'name_pattern' not in  camera_config:
                raise ConfigurationError(f"Missing name_pattern for camera role: {role}")
            if 'type' not in camera_config:
                raise ConfigurationError(f"Missing type for camera role: {role}")
        
        paths = self._configs.get('paths', {})
        required_paths = ['raw_images', 'target_json', 'solver_status_json']
        for path in required_paths:
            if path not in paths:
                raise ConfigurationError(f"Missing required path: {path}")
            
            
    def get_config(self, section: str):
        if not self._configs:
            self.load_all_configs()
        if section not in self._configs:
            raise ConfigurationError(f"Configuration section not found: {section}")
        
        return self._configs[section]
    
    
    def get_telescope_config(self):
        return self.get_config('devices')['telescope']
    
    def get_rotator_config(self):
        devices_config = self.get_config('devices')
        return devices_config.get('rotator', {})
    
    def get_cover_config(self):
        devices_config = self.get_config('devices')
        return devices_config.get('cover', {})
    
    def get_camera_configs(self):
        '''Get camera configuration (multiple cameras by name pattern)'''
        devices = self.get_config('devices')
        return devices.get('cameras', {})
    
    def get_camera_config(self, role: str = "main"):
        cameras = self.get_camera_configs()
        if role not in cameras:
            raise ConfigurationError(f"Camera role: {role} not found in configuration")
        return cameras[role]
    
    def get_filter_wheel_config(self) -> Optional[Dict[str, Any]]:
        devices_config = self.get_config('devices')
        return devices_config.get('filter_wheel')
    
    def get_exposure_time(self, gaia_g_mag: float, filter_code: str = 'C') -> float:
        exposures = self.get_config('exposures')
        base_exposure = exposures.get('default_exposure', 5.0)
        magnitude_ranges = exposures.get('magnitude_ranges', [])
        for range_config in magnitude_ranges:
            min_mag = range_config.get('min', 0.0)
            max_mag = range_config.get('max', 20.0)
            
            if min_mag <= gaia_g_mag < max_mag:
                base_exposure = range_config['exposure']
                break
            
        filter_scaling = exposures.get('filter_scaling', {})
        
        filter_scale_map ={
            'C': 'Clear', 'B': 'B', 'G': 'V', 'R': 'R',
            'L': 'Lum', 'I': 'I', 'H': 'Ha'
        }
        
        scale_key = filter_scale_map.get(filter_code.upper(), 'Clear')
        scale_factor = filter_scaling.get(scale_key, 1.0)
        
        final_exposure = base_exposure * scale_factor
        
        logger.debug(f"Exposure calc: G={gaia_g_mag:.2f}, filter={filter_code.upper()}, "
                     f"base={base_exposure}, scale={scale_factor}, final={final_exposure:.1f} s")
        
        return final_exposure
        
    def get_focuser_config(self) -> Dict[str, Any]:
        devices_config = self.get_config("devices")
        return devices_config.get('focuser', {})
    
    def get_header_config(self) -> Dict[str, Any]:
        if not hasattr(self, '_header_config'):
            header_file = self.config_dir / "headers.yaml"
            if not header_file.exists():
                logger.warning(f"Headers config not found: {header_file}")
                self._header_config = {
                    'observatory': {},
                    'defaults': {'EPOCH': 2000.0, 'IMAGETYP': 'LIGHT'},
                    'filter_names': {'C': 'Clear', 'B': 'Blue', 'G': 'Green',
                                     'R': 'Sloan-r', 'L': 'Lum', 'I': 'Sloan-i', 'H': 'H-alpha'}
                }
            else:
                with open(header_file, 'r') as f:
                    self._header_config = yaml.safe_load(f)
        return self._header_config
    
    def get_field_rotation_config(self):
        return self.get_config('field_rotation')
    
    def get_fits_headers(self):
        return self.get_config('headers')
    
    def get_paths(self):
        return self.get_config('paths')
    
    def write_target_json (self, target_data: Dict[str, Any]):
        try:
            paths = self.get_paths()
            target_file = Path(paths['target_json'])
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_file, 'w') as f:
                json.dump(target_data, f, indent=2)
                
            logger.info(f"Target JSON written to: {target_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to write target JSON: {e}")
            return False
        
    def read_solver_status(self):
        try:
            paths = self.get_paths()
            status_file = Path(paths['solver_status_json'])
            
            if not status_file.exists():
                return None
            
            import time
            mod_time = status_file.stat().st_mtime
            age_seconds = time.time() - mod_time
            
            if age_seconds > 200:
                logger.warning(f"Solver status is {age_seconds:.0f}s old")
                return None
            
            with open(status_file, 'r') as f:
                data = json.load(f)
                logger.debug(f"Read solver status from JSON")
                return data
            
        except Exception as e:
            logger.error(f"Failed to read solver status: {e}")
            return None


_global_config = None    


def get_config_loader(config_dir: str='config'):
    global _global_config
    if _global_config is None:
        _global_config = ConfigLoader(config_dir)
    return _global_config

    
        
    
    
    
    
        
    

            

    