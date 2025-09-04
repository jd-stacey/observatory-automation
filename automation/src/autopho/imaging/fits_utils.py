import logging
from datetime import datetime
from typing import Dict, Any, Optional
from astropy.io import fits
import numpy as np

logger = logging.getLogger(__name__)

from ..config.loader import ConfigLoader
from ..devices.camera import CameraDevice

class FITSHeaderError(Exception):
    pass

def inject_headers(hdu: fits.PrimaryHDU,
                   target_info,
                   camera_device: CameraDevice, 
                   config_loader: ConfigLoader,
                   filter_code: str,
                   exposure_time: float) -> fits.PrimaryHDU:
    
    try:
        header_config = config_loader.get_header_config()
        camera_settings = camera_device.get_camera_settings()
        obs_config = header_config.get('observatory', {})
        for key, value in obs_config.items():
            hdu.header[key] = value
        
        if target_info:
            if isinstance(target_info, dict):
                hdu.header['OBJECT'] = target_info.get('object_name', 'Unknown')
                hdu.header['RA'] = target_info.get('ra_hours', 0.0)
                hdu.header['DEC'] = target_info.get('dec_degrees', 0.0)
                if 'magnitude' in target_info:
                    hdu.header['MAG'] = target_info['magnitude']
            else:
                hdu.header['OBJECT'] = getattr(target_info, 'object_name', 'Unknown')
                hdu.header['RA'] = getattr(target_info, 'ra_j2000_hours', 0.0)
                hdu.header['DEC'] = getattr(target_info, 'dec_j2000_deg', 0.0)
                if hasattr(target_info, 'gaia_g_mag'):
                    hdu.header['MAG'] = target_info.gaia_g_mag
                
        defaults = header_config.get('defaults', {})
        for key, value in defaults.items():
            hdu.header[key] = value
            
        hdu.header['CAMERA'] = camera_settings.get('camera_name', 'Unknown')
        hdu.header['CAMID'] = camera_settings.get('camera_id', -1)
        
        if camera_settings.get('ccd_temperature') is not None:
            hdu.header['CCDTEMP'] = camera_settings['ccd_temperature']
        if camera_settings.get('cooler_on') is not None:
            hdu.header['COOLERON'] = camera_settings['cooler_on']
        if camera_settings.get('pixel_size_x'):
            hdu.header['PIXSIZEX'] = camera_settings['pixel_size_x']
        if camera_settings.get('pixel_size_y'):
            hdu.header['PIXSIZEY'] = camera_settings['pixel_size_y']
            
        hdu.header['EXPTIME'] = exposure_time
        hdu.header['BINNING'] = camera_settings.get('bin_x', 1)
        hdu.header['XBINNING'] = camera_settings.get('bin_x', 1)
        hdu.header['YBINNING'] = camera_settings.get('bin_y', 1)
        
        if camera_settings.get('gain') is not None:
            hdu.header['GAIN'] = camera_settings['gain']
            
        filter_names = header_config.get('filter_names', {})
        hdu.header['FILTER'] = filter_names.get(filter_code.upper(), filter_code)
        
        hdu.header['DATE-OBS'] = datetime.now().isoformat()
        
        logger.info(f"FITS headers injected for {filter_code} filter, {exposure_time} s exposure")
        return hdu
    except Exception as e:
        logger.error(f"Failed to inject FITS headers: {e}")
        raise FITSHeaderError(f"Header injection failed: {e}")
    
def create_fits_file(image_array: np.ndarray, 
                     target_info: Dict[str, Any],
                     camera_device: CameraDevice,
                     config_loader: ConfigLoader,
                     filter_code: str,
                     exposure_time: float) -> fits.PrimaryHDU:
    
    try:
        hdu = fits.PrimaryHDU(image_array)
        hdu = inject_headers(hdu, target_info, camera_device, config_loader, filter_code, exposure_time)
        
        return hdu
    except Exception as e:
        logger.error(f"Failed to create FITS file: {e}")
        raise FITSHeaderError(f"FITS creation failed: {e}")
