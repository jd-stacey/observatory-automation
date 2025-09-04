import time
import logging
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from autopho.imaging.fits_utils import create_fits_file
from autopho.imaging.file_manager import FileManager
from autopho.targets.observability import ObservabilityChecker

logger = logging.getLogger(__name__)

class ImagingSessionError(Exception):
    pass

class ImagingSession:
    def __init__(self, camera_manager, corrector, config_loader, target_info, filter_code: str, 
                 ignore_twilight: bool = False, exposure_override: Optional[float] = None):
        self.camera_manager = camera_manager
        self.corrector = corrector
        self.config_loader = config_loader
        self.target_info = target_info
        self.filter_code = filter_code
        self.ignore_twilight = ignore_twilight
        self.exposure_override = exposure_override
        self.exposure_count = 0
        self.session_start_time = None
        self.last_correction_exposure = 0
        self.consecutive_failures = 0
        self.correction_interval = 5            # Apply correction every N exposures
        self.max_consecutive_failures = 3
        self.main_camera = None
        self.file_manager = None
        self.observability_checker = None
        self._initialize_components()
        
    def _initialize_components(self):
        try:
            self.main_camera = self.camera_manager.get_main_camera()
            if not self.main_camera:
                raise ImagingSessionError("Main camera not found")
            
            if not self.main_camera.connected:
                if not self.main_camera.connect():
                    raise ImagingSessionError("Failed to connect to main camera")
            
            self.file_manager = FileManager(self.config_loader)
            
            self.target_dir = self.file_manager.create_target_directory(self.target_info.tic_id)
            
            self._create_complete_target_json(self.target_dir)
            
            observatory_config = self.config_loader.get_config('observatory')
            self.observability_checker = ObservabilityChecker(observatory_config)
            logger.debug(f"Session initialized: {self.target_info.tic_id}, Filter: {self.filter_code}")
            logger.debug(f"Camera: {self.main_camera.name}")
            
        except Exception as e:
            raise ImagingSessionError(f"Failed to initialize session: {e}")
        
    def _create_complete_target_json(self, target_dir: Path):
        from autopho.targets.resolver import TICTargetResolver
        resolver = TICTargetResolver()
        target_json_data = resolver.create_target_json(self.target_info)
        
        target_json_data.update({
            "camera_name": self.main_camera.name,
            "camera_device_id": self.main_camera.device_id,
            "filter_code": self.filter_code,
            "raw_images_directory": str(target_dir),
            "tel": self.file_manager.telescope_id.replace('T', '')
        })
        if self.config_loader.write_target_json(target_json_data):
            logger.info(f"Target JSON created with camera: {self.main_camera.name}")
            logger.debug(f"Raw images directory: {target_dir}")
        else:
            logger.warning("Failed to write target JSON for external platesolver")
    
    def start_imaging_loop(self, max_exposures: Optional[int] = None,
                           duration_hours: Optional[float] = None) -> bool:
        
        logger.info("="*75)
        logger.info(" "*25+"STARTING IMAGING SESSION")
        logger.info("="*75)
        
        if max_exposures:
            logger.info(f"Maximum exposures: {max_exposures}")
        if duration_hours:
            logger.info(f"Maximum duration: {duration_hours:.1f} hours")
            
        self.session_start_time = time.time()
        self.exposure_count = 0
        self.consecutive_failures = 0
        
        try:
            while True:
                
                try:
                    image_filepath = self.capture_single_exposure()
                    if image_filepath:
                        self.exposure_count += 1
                        self.consecutive_failures = 0
                        elapsed_time = (time.time() - self.session_start_time) / 3600
                        logger.info(f"Exposure {self.exposure_count}: {Path(image_filepath).name} "
                                     f"(Session: {elapsed_time:.1f} h)")
                    else:
                        self.consecutive_failures += 1
                        logger.warning(f"Capture failed ({self.consecutive_failures}/{self.max_consecutive_failures})")
                except Exception as e:
                    self.consecutive_failures += 1
                    logger.error(f"Exposure error: {e} ({self.consecutive_failures}/{self.max_consecutive_failures})")
                    
                    if self.consecutive_failures > self.max_consecutive_failures:
                        logger.error("Too many consecutive failures, terminating session")
                        return False
                
                should_terminate, reason = self.check_termination_conditions(max_exposures, duration_hours)
                if should_terminate:
                    logger.info(f"Session terminating: {reason}")
                    break
                
                if self._should_apply_correction():
                    self._apply_periodic_correction()
                
                
                
                
            session_duration = (time.time() - self.session_start_time) / 3600
            logger.info("="*75)
            logger.info(" "*30+"IMAGING COMPLETED")
            logger.info("="*75)
            logger.info(f"Total exposures: {self.exposure_count}")
            logger.info(f"Files saved to: {self.target_dir}")
            logger.info(f"Session duration: {session_duration:.1f} hours")
            return True
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
            return True
        except Exception as e:
            logger.error(f"Session failed: {e}")
            return False
        
    def capture_single_exposure(self) -> Optional[str]:
        try:
            if self.exposure_override is not None:
                exposure_time = self.exposure_override
            else:
                exposure_time = self.config_loader.get_exposure_time(
                self.target_info.gaia_g_mag,
                self.filter_code
                )
            camera_config = self.main_camera.config
            binning = camera_config.get('default_binning', 4)
            gain = camera_config.get('default_gain', 100)
            
            logger.debug(f"Starting exposure: {exposure_time} s, binning={binning}, gain={gain}")
            
            image_array = self.main_camera.capture_image(
            exposure_time=exposure_time,
            binning=binning, 
            gain=gain, 
            light=True
            )
            if image_array is None:
                logger.error("Camera returned no image data")
                return None
            
            hdu = create_fits_file(
                image_array=image_array,
                target_info=self.target_info, 
                camera_device=self.main_camera, 
                config_loader=self.config_loader,
                filter_code=self.filter_code,
                exposure_time=exposure_time
            )
            
            filepath = self.file_manager.save_fits_file(
                hdu=hdu,
                tic_id=self.target_info.tic_id,
                filter_code=self.filter_code, 
                exposure_time=exposure_time,
                sequence_number=self.exposure_count + 1
            )
            
            return str(filepath) if filepath else None
        
        except Exception as e:
            logger.error(f"Single exposure capture failed: {e}")
            return None
        
    def check_termination_conditions(self, max_exposures: Optional[int], 
                                     duration_hours: Optional[float]) -> Tuple[bool, str]:
        
        if max_exposures and self.exposure_count >= max_exposures:
            return True, f"Maximum exposures reached ({max_exposures})"
        
        if duration_hours and self.session_start_time:
            elapsed_hours = (time.time() - self.session_start_time) / 3600
            if elapsed_hours >= duration_hours:
                return True, f"Maximum duration reached ({duration_hours:.1f} hours)"
        
        try:
            obs_status = self.observability_checker.check_target_observability(
                self.target_info.ra_j2000_hours,
                self.target_info.dec_j2000_deg,
                ignore_twilight=self.ignore_twilight
            )
            
            if not obs_status.observable:
                reasons_text = "; ".join(obs_status.reasons)
                return True, f"Target no longer observable: {reasons_text}"
        except Exception as e:
            logger.warning(f"Could not check observability: {e}")
            
        if self.consecutive_failures >= self.max_consecutive_failures:
            return True, f"Too many consecutive failures ({self.consecutive_failures})"
        return False, "Session continuing"
    
    def _should_apply_correction(self) -> bool:
        if not self.corrector:
            return False
        if self.exposure_count > 0 and (self.exposure_count % self.correction_interval) == 0:
            if self.exposure_count != self.last_correction_exposure:
                return True
        # Checks for platesolve correction before first image
        # if self.exposure_count == 0:
        #     return True
        return False
    
    def _apply_periodic_correction(self) -> bool:
        if not self.corrector:
            return False
        try:
            logger.debug(f"Checking for platesolve correction...")
            result = self.corrector.apply_single_correction(timeout_seconds=1)
            if result.applied:
                logger.info(f"Correction applied: {result.reason} "
                            f"(Total offset: {result.total_offset_arcsec:.2f}\")")
                self.last_correction_exposure = self.exposure_count
                return True
            else:
                logger.debug(f"No correction needed: {result.reason}")
                return False
        except Exception as e:
            logger.warning(f"Correction check failed: {e}")
            return False
    def get_session_stats(self) -> Dict[str, Any]:
        if not self.session_start_time:
            return {'status': 'not_started'}
        elapsed_time = time.time() - self.session_start_time
        return {
            'status': 'running',
            'exposure_count': self.exposure_count,
            'elapsed_hours': elapsed_time / 3600,
            'consecutive_failures': self.consecutive_failures,
            'target': self.target_info.tic_id,
            'filter': self.filter_code,
            'camera_connected': self.main_camera.connected if self.main_camera else False,
            'corrector_available': self.corrector is not None
        }
        