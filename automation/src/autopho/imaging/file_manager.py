import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import re

try:
    from astropy.io import fits
    FITS_AVAILABLE = True
except ImportError:
    FITS_AVAILABLE = False
# Set up logging    
logger = logging.getLogger(__name__)

class FileManagerError(Exception):
    pass
# Set up file manager class
class FileManager:
    
    def __init__(self, config_loader):
        if not FITS_AVAILABLE:
            raise FileManagerError(f"astropy.io.fits not available - please install")
        # Default paths taken from paths.yaml config, device info from devices.yaml config
        self.config_loader = config_loader
        self.paths_config = config_loader.get_paths()
        self.raw_images_path = Path(self.paths_config['raw_images'])
        devices_config = config_loader.get_config('devices')
        telescope_config = devices_config.get('telescope', {})
        self.telescope_id = telescope_config.get('telescope_id', 'Unknown-Telescope')
        
        logger.debug(f"FileManager initialized: {self.raw_images_path}")
        logger.debug(f"Telescope ID: {self.telescope_id}")
        
    def create_target_directory(self, tic_id: str, base_path: Optional[Path] = None) -> Path:
        '''Create the directories for the target in form: raw_images_path\YYYY\YYYYMMDD\T2\target_id'''
        try:
            root = base_path or self.raw_images_path
            clean_tic = self._clean_tic_id(tic_id)
            current_year = datetime.now(timezone.utc).strftime("%Y")
            current_day = datetime.now(timezone.utc).strftime("%Y%m%d")
            target_dir = root / current_year / current_day / self.telescope_id / clean_tic
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Target directory: {target_dir}")
            return target_dir
        except Exception as e:
            raise FileManagerError(f"Failed to create target directory: {e}")
        
    def generate_filename(self, tic_id: str, filter_code: str, exposure_time: float,
                          sequence_number: int, timestamp: Optional[datetime] = None) -> str:
        '''Generate the filename for the image files (.fits) based on target id, date, exposure time, sequence etc'''
        try:
            clean_tic = self._clean_tic_id(tic_id)
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            date_str = timestamp.strftime("%Y%m%d")
            time_str = timestamp.strftime("%H%M%S")
            exp_str = f"{exposure_time:.1f}".rstrip('0').rstrip('.')
            seq_str = f"{sequence_number:05d}"
            filename = f"{clean_tic}_{filter_code.upper()}_{date_str}_{time_str}_{exp_str}s_{seq_str}.fits"
            
            logger.debug(f"Generated filename: {filename}")
            return filename
        except Exception as e:
            raise FileManagerError(f"Failed to generate filename: {e}")
        
    def get_next_sequence_number(self, target_dir: Path) -> int:
        '''Update sequence number for files (e.g. _00001.fits, _00002.fits)'''
        try:
            if not target_dir.exists():
                return 1
            pattern = r'_(\d{5})\.fits$'
            max_sequence = 0
            
            for fits_file in target_dir.glob("*.fits"):
                match = re.search(pattern, fits_file.name)
                if match:
                    sequence_num = int(match.group(1))
                    max_sequence = max(max_sequence, sequence_num)
            next_sequence = max_sequence + 1
            logger.debug(f"Next sequence number: {next_sequence}")
            return next_sequence
        except Exception as e:
            logger.warning(f"Error determining sequence number, using 1: {e}")
            return 1
        
    def save_fits_file(self, hdu: fits.PrimaryHDU, tic_id: str, filter_code: str, 
                        exposure_time: float, sequence_number: int, target_dir: Optional[Path] = None) -> Optional[Path]:
        # Save the fits file to the target directory
        try:
            if target_dir is None:
                target_dir = self.create_target_directory(tic_id)       # Create the directory if it doesnt already exist
            if sequence_number is None:
                sequence_number = self.get_next_sequence_number(target_dir) # Get the next sequence number
            timestamp = datetime.now(timezone.utc)
            filename = self.generate_filename(tic_id, filter_code, exposure_time, sequence_number, timestamp)   # Get the filename
            filepath = target_dir / filename
            # Check if a file already exists with that exact name, if so, update the sequence number
            if filepath.exists():
                logger.warning(f"File already exists, finding next sequence: {filepath.name}")
                sequence_number = self.get_next_sequence_number(target_dir)
                filename = self.generate_filename(tic_id, filter_code, exposure_time, sequence_number, timestamp)
                filepath = target_dir / filename
            hdu.writeto(filepath, overwrite=False)      # Write to the filepath
            # Ensure new file now exists
            if not filepath.exists():
                raise FileManagerError("FITS file was not created")
            file_size = filepath.stat().st_size     # Get and log filesize of the new image
            logger.info(f"FITS file saved: {filepath.name} ({file_size:,} bytes)")
            
            return filepath
        
        except Exception as e:
            logger.error(f"Failed to save FITS file: {e}")
            return None
        
    def check_disk_space(self, target_dir: Path, min_gb: float = 0.5) -> bool:
        '''Check enough disk space exists for the new file (minimum set from min_gb above)'''
        try:
            if not target_dir.exists():
                target_dir = target_dir.parent
            stat = os.statvfs(str(target_dir))
            available_bytes = stat.f_bavail * stat.f_frsize
            available_gb = available_bytes / (1024**3)
            
            if available_gb < min_gb:
                logger.warning(f"Low disk space: {available_gb:.1f} GB available (minimum: {min_gb} GB)")
                return False
            
            logger.debug(f"Disk space OK: {available_gb:.1f} GB available")
            return True
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            return True
        
    def get_session_directory_info(self, tic_id: str) -> Dict[str, Any]:
        '''For end of session reporting - get info about the  current target directory'''
        try:
            target_dir = self.create_target_directory(tic_id)
            fits_files = list(target_dir.glob("*.fits"))
            file_count = len(fits_files)
            total_size = sum(f.stat().st_size for f in fits_files)
            total_size_mb = total_size / (1024**2)
            
            next_sequence = self.get_next_sequence_number(target_dir)
            disk_space_ok = self.check_disk_space(target_dir)
            return {
                'directory': str(target_dir),
                'existing_files': file_count,
                'total_size_mb': total_size_mb, 
                'next_sequence': next_sequence, 
                'disk_space_ok': disk_space_ok
            }
        except Exception as e:
            logger.error(f"Error getting directory info: {e}")
            return {'error': str(e)}
        
    def _clean_tic_id(self, tic_id: str) -> str:
        '''Get just the number from imput TIC ids - e.g. user uses TIC-123456789 and we just want 123456789'''
        clean = tic_id.strip()
        clean = clean.replace('-', '')
        
        if not clean.upper().startswith('TIC'):
            if clean.isdigit():
                clean=f"TIC{clean}"
            elif 'TIC' in clean.upper():
                numbers = re.search(f'(\d+)', clean)
                if numbers:
                    clean = f"TIC{numbers.group(1)}"
                    
        if clean.upper().startswith('TIC'):
            number_part = clean[3:]
            clean = f"TIC{number_part}"
        return clean
    
    