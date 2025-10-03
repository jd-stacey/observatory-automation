import sys
import logging
from rich.logging import RichHandler
import argparse
from pathlib import Path
import json
import time
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from autopho.config.loader import ConfigLoader, ConfigurationError
from autopho.targets.resolver import TICTargetResolver, TargetInfo
from autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver
from autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver
from autopho.devices.drivers.alpaca_focuser import AlpacaFocuserDriver
from autopho.devices.camera import CameraManager, CameraError
from autopho.targets.observability import ObservabilityChecker
from autopho.platesolving.corrector import PlatesolveCorrector, PlatesolveCorrectorError, CorrectionResult
from autopho.imaging.session import ImagingSession, ImagingSessionError, SessionPhase

logger = logging.getLogger(__name__)

def extract_sequence_from_filename(filename: str) -> int:
    '''Extract sequence number from filename like _00123.fits'''
    import re
    match = re.search(r'_(\d+)\.fits', filename)
    return int(match.group(1)) if match else -1


def ensure_telescope_tracking(telescope_driver, check_interval=0.5):
    import threading
    import time
    
    # Use a threading.Event for clean shutdown signaling
    stop_event = threading.Event()
    
    def tracking_monitor():
        logger = logging.getLogger('tracking_monitor')
        while not stop_event.is_set():
            try:
                if telescope_driver and telescope_driver.is_connected():
                    if hasattr(telescope_driver.telescope, 'Tracking'):
                        if not telescope_driver.telescope.Tracking:
                            logger.warning("Telescope tracking disabled - re-enabling")
                            telescope_driver.telescope.Tracking = True
                            time.sleep(0.5)
                            if telescope_driver.telescope.Tracking:
                                logger.info("Telescope tracking successfully re-enabled")
                            else:
                                logger.error("Failed to re-enable telescope tracking")
                        # else:
                        #     logger.debug("Telescope tracking OK")
                
                # Use stop_event.wait() instead of time.sleep() for responsive shutdown
                if stop_event.wait(timeout=check_interval):
                    break  # stop_event was set, exit cleanly
                    
            except Exception as e:
                logger.error(f"Tracking monitor error: {e}")
                if stop_event.wait(timeout=check_interval):
                    break
    
    tracking_thread = threading.Thread(target=tracking_monitor, daemon=True)
    tracking_thread.start()
    
    # Return both thread and stop_event so caller can shut it down properly
    return tracking_thread, stop_event

def setup_logging(log_level: str, log_dir: Path, log_name: str = None):
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if log_name is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_name = f"{timestamp}_spec.log"
        
    logfile = log_dir / log_name
    
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True, 
        show_path=True
        )
    
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.setLevel(numeric_level)
    
    
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]"
    ))
    file_handler.setLevel(logging.DEBUG)
        
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler]
    )
    
    return logfile

class TelescopeMirror:
    """Handles mirroring coordinates from another telescope via JSON file"""

    def __init__(self, mirror_file: str):
        self.mirror_file = Path(mirror_file)
        self.last_timestamp = None
        self.last_coordinates = None
        self.failed_targets = set()  # Track targets that failed to avoid retry loops
        self.script_start_time = time.time()    # Track when script starts
        self.logger = logging.getLogger(__name__)
        
        # Define dome closure statuses that should trigger telescope shutdown
        self.dome_closure_statuses = [
            'weather_danger_closing', 
            'closing_both_panels', 
            'close_requested_left',  
            'close_requested_right', 
            'close_requested', 
            'closed'
        ]

    def check_for_dome_closure(self) -> Tuple[bool, Optional[str]]:
        """Check if dome closure has been requested/executed on the mirrored telescope"""
        self.logger.debug(f"=== check_for_dome_closure() called, checking file: {self.mirror_file} ===")
        
        try:
            if not self.mirror_file.exists():
                self.logger.debug("Mirror file does not exist - no dome closure detected")
                return False, None
                
            # Read the mirror file
            self.logger.debug("Reading mirror file for dome status...")
            with open(self.mirror_file, 'r') as f:
                data = json.load(f)
            
            latest_dome = data.get('latest_dome')
            if not latest_dome:
                self.logger.debug("No latest_dome found in mirror file")
                return False, None
                
            timestamp_str = latest_dome.get('timestamp')
            status = latest_dome.get('status')
            message = latest_dome.get('message', '')
            
            if not timestamp_str or not status:
                self.logger.debug("Missing timestamp or status in latest_dome")
                return False, None
            
            self.logger.debug(f"Found dome status: {status} at {timestamp_str}")
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                dome_timestamp = timestamp.timestamp()
            except Exception as e:
                self.logger.warning(f"Could not parse dome timestamp '{timestamp_str}': {e}")
                return False, None
            
            # Check if dome message is after script start (avoid acting on old messages)
            if dome_timestamp <= self.script_start_time:
                self.logger.debug(f"Dome message is older than script start - ignoring")
                return False, None
            
            # Check if status indicates dome closure
            if status in self.dome_closure_statuses:
                reason = f"Dome closure detected on mirrored telescope: {status} - {message}"
                self.logger.warning(reason)
                return True, reason
            else:
                self.logger.debug(f"Dome status '{status}' does not indicate closure")
                return False, None
                
        except json.JSONDecodeError as e:
            self.logger.debug(f"Invalid JSON in mirror file during dome check: {e}")
        except FileNotFoundError:
            self.logger.debug("Mirror file disappeared during dome check")
        except Exception as e:
            self.logger.debug(f"Error checking dome status: {e}")
        
        # Default to no closure detected on any parsing errors
        return False, None
    
    def check_for_new_target(self) -> Optional[Dict[str, Any]]:
        """Check for new target - relies on atomic writes from writer"""
        self.logger.debug(f"=== check_for_new_target() called, checking file: {self.mirror_file} ===")
        try:
            if not self.mirror_file.exists():
                self.logger.debug("Mirror file does not exist")
                return None
                
            # Simple read - writer should use atomic .tmp -> rename pattern
            self.logger.debug("Reading mirror file...")
            with open(self.mirror_file, 'r') as f:
                data = json.load(f)
            
            latest_move = data.get('latest_move')
            if not latest_move:
                self.logger.debug("No latest_move found in mirror file")
                return None
                
            timestamp_str = latest_move.get('timestamp')
            if not timestamp_str:
                self.logger.debug("No timestamp in latest_move")
                return None
            
            self.logger.debug(f"Raw timestamp from file: '{timestamp_str}'")
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            self.logger.debug(f"Parsed timestamp: {timestamp}")
            
            # Skip if we've already processed this timestamp or it failed
            target_key = f"{timestamp.isoformat()}"
            self.logger.debug(f"Generated target_key: '{target_key}'")
            self.logger.debug(f"Current last_timestamp: {self.last_timestamp}")
            self.logger.debug(f"Failed targets set has {len(self.failed_targets)} entries: {list(self.failed_targets)}")
            
            if self.last_timestamp is not None and timestamp <= self.last_timestamp:
                self.logger.debug(f"SKIPPING: Target timestamp {timestamp} <= last processed {self.last_timestamp}")
                return None
                
            if target_key in self.failed_targets:
                self.logger.debug(f"SKIPPING: Target {target_key} previously failed")
                return None
                
            ra_deg = latest_move.get('ra_deg')
            dec_deg = latest_move.get('dec_deg')
            
            if ra_deg is None or dec_deg is None:
                self.logger.warning("Missing coordinates in mirror file")
                return None
                
            # Validate coordinates are reasonable
            if not (0 <= ra_deg <= 360) or not (-90 <= dec_deg <= 90):
                self.logger.error(f"Invalid coordinates in mirror file: RA={ra_deg}°, Dec={dec_deg}°")
                self.failed_targets.add(target_key)
                return None
            
            ra_hours = ra_deg / 15.0
            new_target = {
                'timestamp': timestamp,
                'ra_hours': ra_hours,
                'dec_deg': dec_deg,
                'ra_deg': ra_deg,
                'source': 'mirrored_telescope',
                'target_key': target_key
            }
            self.logger.debug(f"SUCCESS: Found new target: RA={ra_hours:.6f} h ({ra_deg:.6f}°), Dec={dec_deg:.6f}°, timestamp={timestamp_str}")
            self.last_timestamp = timestamp
            self.last_coordinates = (ra_hours, dec_deg)
            return new_target
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in mirror file: {e}")
        except FileNotFoundError:
            # File disappeared between exists check and read - normal race condition
            self.logger.debug("Mirror file disappeared during read")
        except Exception as e:
            self.logger.warning(f"Error reading mirror file: {e}")
            self.logger.debug("Full traceback:", exc_info=True)
        
        self.logger.debug("=== check_for_new_target() returning None ===")
        return None
    
    def mark_target_failed(self, target_key: str):
        """Mark a target as failed to avoid retry loops"""
        self.failed_targets.add(target_key)
        # Limit the size of failed targets set to prevent memory growth
        if len(self.failed_targets) > 100:
            # Remove oldest failed targets (simple FIFO approximation)
            self.failed_targets = set(list(self.failed_targets)[-50:])

    def get_current_target(self) -> Optional[Dict[str, Any]]:
        if self.last_coordinates:
            return {
                'ra_hours': self.last_coordinates[0],
                'dec_deg': self.last_coordinates[1],
                'source': 'mirrored_telescope'
            }
        return None


class SpectroscopyImagingSession(ImagingSession):
    """Imaging session using only the guide camera for spectroscopy"""

    def __init__(self, camera_manager, corrector, config_loader, target_info: TargetInfo,
         ignore_twilight: bool = False, exposure_override: Optional[float] = None,
         dry_run: bool = False, filter_code: str = 'C'):
    
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
        # Load platesolve config first to get spectro settings
        platesolve_config = config_loader.get_config('platesolving')
        spectro_acq_cfg = platesolve_config.get('spectro_acquisition', {})
        
        # Calculate exposure based on priority: override -> YAML -> magnitude calculation
        if exposure_override is not None:
            # Explicit override provided
            final_exposure = exposure_override
            self.logger.debug(f"Using explicit exposure override: {final_exposure:.1f}s")
        else:
            # Try to get from YAML config first
            yaml_exposure = spectro_acq_cfg.get('exposure_time')
            if yaml_exposure is not None:
                final_exposure = yaml_exposure
                self.logger.debug(f"Using YAML spectro_acquisition.exposure_time: {final_exposure:.1f}s")
            elif hasattr(target_info, 'gaia_g_mag'):
                # Calculate from magnitude as fallback
                base_exp = 30.0
                mag_diff = target_info.gaia_g_mag - 12.0
                calculated_exp = base_exp * (2.5 ** mag_diff)  # 2.5x per magnitude
                final_exposure = max(1.0, min(calculated_exp, 300.0))  # Clamp 1-300s
                self.logger.debug(f"Calculated exposure from magnitude {target_info.gaia_g_mag}: {final_exposure:.1f}s")
            else:
                # Final fallback
                final_exposure = 120.0
                self.logger.debug(f"Using fallback exposure time: {final_exposure:.1f}s")
        
        # Store the final exposure time
        exposure_override = final_exposure
        
        # For spectroscopy, filter to only use 294MM cameras
        if camera_manager and not dry_run:
            cameras_to_remove = []
            for name, camera in camera_manager.cameras.items():
                if '294MM' not in camera.name:
                    cameras_to_remove.append(name)
            
            for name in cameras_to_remove:
                logger.debug(f"Removing non-294MM camera for spectroscopy: {camera_manager.cameras[name].name}")
                camera_manager.cameras.pop(name)
            
            # Ensure we have the 294MM as both main and guide
            guide_camera = camera_manager.get_guide_camera()
            if not guide_camera or '294MM' not in guide_camera.name:
                raise ImagingSessionError("294MM guide camera not found for spectroscopy")
            
            if not guide_camera.connected and not guide_camera.connect():
                raise ImagingSessionError("Failed to connect to 294MM camera")
            
            # Set 294MM as main camera for spectroscopy
            camera_manager.cameras['main'] = guide_camera
            logger.info(f"Using 294MM camera for spectroscopy: {guide_camera.name}")
        
        # Initialize paths and parent class
        paths_config = config_loader.get_config('paths')
        spectro_root = Path(paths_config['spectro_images'])
        
        # Initialize parent with 'C' filter (clear) for spectroscopy
        super().__init__(camera_manager, corrector, config_loader, target_info,
                        filter_code=filter_code, ignore_twilight=ignore_twilight,
                        exposure_override=exposure_override, images_base_path=spectro_root,
                        is_spectroscopy=True)
        
        self.acquisition_config.update(spectro_acq_cfg)
        
        # Setup directory structure
        full_dir = self.file_manager.create_target_directory(self.target_info.tic_id, base_path=spectro_root)
        self.science_dir = full_dir
        self.acquisition_dir = full_dir.parent / (full_dir.name + "_acq")
        self.current_target_dir = self.acquisition_dir if self.acquisition_enabled else self.science_dir
        
        # Configure acquisition settings
        if self.acquisition_enabled and hasattr(self, 'acquisition_config'):
            self.acquisition_config['exposure'] = self.exposure_override
            self.logger.debug(f"Acquisition exposure set to {self.exposure_override}")
        
        # Update acquisition settings for tighter spectroscopy requirements
        if hasattr(self, 'acquisition_config'):
            # Tighten acquisition threshold for spectroscopy (fiber alignment critical)
            self.acquisition_config['max_total_offset_arcsec'] = 1.0
            self.logger.debug("Tightened acquisition threshold to 1.0\" for spectroscopy")
        
        # Initialize session state
        self._running = False
        self._stop_event = threading.Event()
        
        if dry_run:
            self.main_camera = None
            self.logger.info("DRY RUN MODE - No camera operations will be performed")
        
        # Set target in corrector for stale data detection
        self._set_target_in_corrector()
        logger.debug(f"SpectroscopyImagingSession initialized with immediate correction checking")

        

    def run_simulated_acquisition(self):
        """Simulate acquisition + science frames for testing"""
        self.logger.info("Starting simulated spectroscopy sequence...")
        self._running = True
        
        try:
            # Simulate acquisition phase
            if self.acquisition_enabled:
                self.logger.info("Phase: acquisition")
                for i in range(3):
                    if self._stop_event.is_set():
                        break
                    self.logger.info(f"  ACQ Frame {i+1}/3, exposure 3s")
                    time.sleep(0.1)  # fast-forward in simulation
                
                self.logger.info("Acquisition complete, switching to science...")
                
            # Simulate science phase  
            self.logger.info("Phase: science")
            for i in range(5):
                if self._stop_event.is_set():
                    break
                exposure_time = self.exposure_override or 30.0
                self.logger.info(f"  SCI Frame {i+1}/5, exposure {exposure_time:.1f}s")
                time.sleep(0.1)  # fast-forward in simulation
                
        finally:
            self._running = False
            
    
    def _should_apply_correction(self):
        """Spectroscopy uses synchronous corrections only - disable periodic checks"""
        return False

    def _apply_periodic_correction(self):
        """No-op for spectroscopy - corrections happen synchronously"""
        pass
    
    
    def capture_single_exposure(self, telescope_driver=None) -> Optional[str]:
        """Override to use synchronous corrections for spectroscopy"""
        # Check stop event BEFORE capture
        if self._stop_event.is_set():
            return None
        
        # Capture image using parent method
        image_filepath = super().capture_single_exposure(telescope_driver=telescope_driver)
        
        # Check stop event BEFORE waiting for correction
        if self._stop_event.is_set() or not image_filepath:
            return image_filepath
        
        if image_filepath and self.corrector:
            # For spectroscopy: ALWAYS wait for correction synchronously (both ACQ and SCI)
            solver_wait_time = self.acquisition_config.get('solver_wait_time', 30.0)
            logger.debug(f"Spectroscopy mode - waiting up to {solver_wait_time:.1f} s for platesolve correction...")
            
            try:
                correction_applied = self.corrector.wait_for_correction_with_timeout(solver_wait_time, current_frame_path=image_filepath)
                
                if not correction_applied:
                    logger.warning("No correction applied within timeout - proceeding")
                else:
                    logger.debug("Synchronous correction completed successfully")
                    
            except Exception as e:
                logger.warning(f"Error during synchronous correction: {e}")
        
        return image_filepath

    def _switch_to_science_phase(self):
        '''Override to reset corrector tracking when switching phases'''
        
        # Call parent implementation (from session.py) to do normal phase switching stuff
        super()._switch_to_science_phase()
        
        # Delete the platesolve JSON to prevent stale data from acquisition phase
        if self.corrector and hasattr(self.corrector, 'delete_platesolve_json'):
            self.corrector.delete_platesolve_json(reason="acquisition -> science phase transition")
        
        # Reset corrector's sequence tracking since we are starting a new directory and file suffixes
        if self.corrector and hasattr(self.corrector, 'reset_for_new_sequence'):
            self.corrector.reset_for_new_sequence(reason="acquisition -> science phase")
    
    
    
    def _should_switch_to_science_from_correction(self, correction_result) -> bool:
        """Determine if correction result indicates we should switch to science phase"""
        if self.current_phase != SessionPhase.ACQUISITION:
            return False
        
        max_offset = self.acquisition_config.get('max_total_offset_arcsec', 2.0)
        
        # Switch if total offset is within threshold
        if correction_result.total_offset_arcsec <= max_offset:
            logger.debug(f"Offset {correction_result.total_offset_arcsec:.2f}\" = {max_offset}\" threshold")
            return True
        
        return False

    def _set_target_in_corrector(self):
        """Set current target info in corrector for stale data detection"""
        if self.corrector and hasattr(self.corrector, 'set_current_target'):
            target_id = self.target_info.tic_id
            self.corrector.set_current_target(target_id, self.exposure_override)
            logger.debug(f"Set corrector target: {target_id} with base exposure: {self.exposure_override}")
    
    
    def start_imaging_loop(self, max_exposures: Optional[int] = None,
                       duration_hours: Optional[float] = None,
                       telescope_driver = None) -> bool:
        
        # Call parent initialization
        logger.info("="*75)
        logger.info(" "*25+"STARTING IMAGING SESSION")
        logger.info("="*75)
        
        if self.acquisition_enabled and self.current_phase == SessionPhase.ACQUISITION:
            logger.info("Starting with target acquisition phase")
            acq_exp_time = self.acquisition_config.get('exposure_time', 30.0)
            max_acq_attempts = self.acquisition_config.get('max_attempts', 45)
            logger.debug(f"Config defaults: {acq_exp_time} s exposures, max {max_acq_attempts} attempts")
        
        if max_exposures:
            logger.info(f"Maximum exposures: {max_exposures}")
        if duration_hours:
            logger.info(f"Maximum duration: {duration_hours:.3f} hours")
            
        self.session_start_time = time.time()
        self.exposure_count = 0
        self.consecutive_failures = 0
        
        # Field rotation setup (same as parent)
        try:
            if self.rotator_driver:
                fr_cfg = self.config_loader.get_config('field_rotation')
                if fr_cfg.get('enabled', True):
                    obs_cfg = self.config_loader.get_config('observatory')
                    if self.rotator_driver.initialize_field_rotation(obs_cfg, fr_cfg):
                        self.rotator_driver.set_tracking_target(
                            self.target_info.ra_j2000_hours,
                            self.target_info.dec_j2000_deg,
                            reference_pa_deg=None
                        )
                        self.rotator_driver.start_field_tracking()
                        logger.info("Field-rotation tracking: started (continuous for session)")
        except Exception as e:
            logger.warning(f"Field-rotation start failed: {e}")
        
        try:
            while True:
                # **ADD THIS STOP CHECK**
                if self._stop_event.is_set():
                    logger.info("Stop event detected, ending imaging loop")
                    break
                
                try:
                    image_filepath = self.capture_single_exposure(telescope_driver=telescope_driver)
                    if image_filepath:
                        self.exposure_count += 1
                        self.consecutive_failures = 0
                        
                        # Update phase-specific counters
                        if self.current_phase == SessionPhase.ACQUISITION:
                            self.acquisition_count += 1
                        else:
                            self.science_count += 1
                        
                        elapsed_time = (time.time() - self.session_start_time) / 3600
                        phase_info = f"[{self.current_phase.value.upper()}]"
                        logger.info(f"{phase_info} Exposure {self.exposure_count}: {Path(image_filepath).name} "
                                f"(Session: {elapsed_time:.3f} h)")
                    else:
                        self.consecutive_failures += 1
                        logger.warning(f"Capture failed ({self.consecutive_failures}/{self.max_consecutive_failures})")
                        
                except Exception as e:
                    self.consecutive_failures += 1
                    logger.error(f"Exposure error: {e} ({self.consecutive_failures}/{self.max_consecutive_failures})")
                    
                    if self.consecutive_failures > self.max_consecutive_failures:
                        logger.error("Too many consecutive failures, terminating session")
                        return False
                
                # **ADD STOP CHECK AFTER EACH EXPOSURE TOO**
                if self._stop_event.is_set():
                    logger.info("Stop event detected after exposure, ending imaging loop")
                    break
                
                # Check if acquisition phase should end
                if (self.current_phase == SessionPhase.ACQUISITION and 
                    self.acquisition_count > 0 and
                    self._check_acquisition_complete()):
                    self._switch_to_science_phase()
                
                # Check general termination conditions
                should_terminate, reason = self.check_termination_conditions(max_exposures, duration_hours)
                if should_terminate:
                    logger.info(f"Session terminating: {reason}")
                    break
                
                # Apply corrections based on current phase
                if self._should_apply_correction():
                    self._apply_periodic_correction()
            
            # Rest of the method is the same as parent...
            session_duration = (time.time() - self.session_start_time) / 3600
            logger.info("="*75)
            logger.info(" "*30+"IMAGING COMPLETED")
            logger.info("="*75)
            logger.info(f"Total exposures: {self.exposure_count}")
            if self.acquisition_enabled:
                logger.info(f"  Acquisition: {self.acquisition_count}")
                logger.info(f"  Science: {self.science_count}")
            logger.info(f"Final phase: {self.current_phase.value}")
            logger.info(f"Files saved to: {self.current_target_dir}")
            logger.info(f"Session duration: {session_duration:.3f} hours")
            return True
            
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
            return True
        except Exception as e:
            logger.error(f"Session failed: {e}")
            return False
        finally:
            # Stop continuous tracking when session ends
            try:
                if self.rotator_driver:
                    self.rotator_driver.stop_field_tracking()
                    logger.info("Field-rotation tracking: stopped")
            except Exception:
                pass
    
    
    
    def start_imaging_loop_async(self, duration_hours: float = 1.0):
        """Start imaging loop in separate thread"""
        def imaging_worker():
            try:
                if self.dry_run:
                    self.run_simulated_acquisition()
                else:
                    self.start_imaging_loop(duration_hours=duration_hours)
            except Exception as e:
                self.logger.error(f"Imaging loop error: {e}")
            finally:
                self._running = False
        
        self._running = True
        self.imaging_thread = threading.Thread(target=imaging_worker, daemon=True)
        self.imaging_thread.start()
            
    def _abort_current_exposure(self) -> bool:
        """Abort current camera exposure if possible"""
        if not self.main_camera or not self.main_camera.connected:
            return False
        
        try:
            cam = self.main_camera.camera
            if hasattr(cam, 'AbortExposure'):
                cam.AbortExposure()
                self.logger.info("Aborted current exposure")
                return True
            else:
                self.logger.warning("Camera does not support exposure abortion")
                return False
        except Exception as e:
            self.logger.warning(f"Failed to abort exposure: {e}")
            return False
    
    
    def stop_session(self):
        """Stop the current imaging session"""
        self.logger.info("Stopping spectroscopy session...")
        
        # Set stop flags first
        self._stop_event.set()
        self._running = False
        
        # The try to abort any ongoing exposure
        self._abort_current_exposure()
        
        # Wait for imaging thread to finish (with timeout)
        if hasattr(self, 'imaging_thread') and self.imaging_thread.is_alive():
            self.logger.debug("Waiting for imaging thread to stop...")
            self.imaging_thread.join(timeout=15.0)
            if self.imaging_thread.is_alive():
                self.logger.warning("Imaging thread did not stop cleanly")
            else:
                self.logger.debug("Imaging thread stopped successfully")
    
    def is_running(self) -> bool:
        return self._running



class SpectroscopyCorrector(PlatesolveCorrector):
    """Enhanced platesolve corrector for spectroscopy with immediate corrections and adaptive exposure"""
    
    def __init__(self, telescope_driver, config_loader):
        # Initialize with memory enabled for spectroscopy
        super().__init__(telescope_driver, config_loader, rotator_driver=None, store_last_measurements=True)
        
        # Use spectro-specific platesolve path if configured
        paths_config = config_loader.get_config('paths')
        self.json_file_path = Path(paths_config.get('spectro_platesolve_json', 
                                                paths_config.get('platesolve_json')))
        
        # Load spectro-specific configuration
        platesolve_config = config_loader.get_config('platesolving')
        self.spectro_config = platesolve_config.get('spectro_acquisition', {})
        
        # Track current target for stale data detection
        self.current_target_id = None
        self.target_start_time = None
        self.base_exposure_time = self.spectro_config.get('exposure_time', 10.0)
    
        self.current_exposure_time = self.spectro_config.get('exposure_time', 10.0)
        self.max_exposure_time = self.spectro_config.get('max_exposure_time', 120.0)  # 2 minutes
        self.exposure_increase_factor = self.spectro_config.get('exposure_increase_factor', 2.0)
        self.max_zero_attempts = self.spectro_config.get('max_zero_attempts', 4)  # 2 attempts at max exposure
        
        self.last_applied_sequence = -1
        self.last_processed_filename = None
        self.last_target_id = None
        self.last_wait_failed_filename = None
        self.min_acceptable_sequence = 0
        
        logger.info("SpectroscopyCorrector initialized with immediate corrections and adaptive exposure")
    
    def set_current_target(self, target_id: str, base_exposure_time: Optional[float] = None):
        """Set the current target ID to help detect stale platesolve data"""
        if self.current_target_id != target_id:
            # NEW TARGET - reset everything including session time
            self.current_target_id = target_id
            self.target_start_time = time.time()
            self.session_start_time = time.time()  # Reset for each new target
            
            # Try to delete old platesolve data
            if self.json_file_path.exists():
                try:
                    self.json_file_path.unlink()
                    logger.info(f"Deleted old platesolve data for new target: {target_id}")
                except PermissionError:
                    logger.debug("Could not delete platesolve JSON (file in use) - will validate by timestamp instead")
                except Exception as e:
                    logger.warning(f"Could not delete old platesolve JSON: {e}")
            
            # Reset all tracking
            self.base_exposure_time = base_exposure_time if base_exposure_time is not None else self.spectro_config.get("exposure_time", 30.0)
            self.current_exposure_time = self.base_exposure_time
            self.last_failed_filename = None
            self.last_applied_sequence = -1
            self.last_processed_filename = None
            self.last_target_id = None
            self.min_acceptable_sequence = 0
            
            # Clear retry tracking
            if hasattr(self, 'current_exposure_retries'):
                delattr(self, 'current_exposure_retries')
            if hasattr(self, 'science_failure_count'):
                delattr(self, 'science_failure_count')
            
            logger.info(f"New spectroscopy target: {target_id}")
            logger.info(f"Reset adaptive exposure time to {self.current_exposure_time:.1f} s for new target")
        
        else:
            # SAME target - update exposure if provided, but DON'T reset session_start_time
            if base_exposure_time is not None and base_exposure_time != self.base_exposure_time:
                old_base = self.base_exposure_time
                self.base_exposure_time = base_exposure_time
                self.current_exposure_time = base_exposure_time
                
                if hasattr(self, 'current_exposure_retries'):
                    delattr(self, 'current_exposure_retries')
                if hasattr(self, 'science_failure_count'):
                    delattr(self, 'science_failure_count')
                    
                logger.info(f"Updated base exposure time from {old_base:.1f} s to {base_exposure_time:.1f} s for target {target_id}")
    
    def delete_platesolve_json(self, reason: str = "manual deletion"):
        """Delete the platesolve JSON file to force waiting for fresh data"""
        if self.json_file_path.exists():
            try:
                self.json_file_path.unlink()
                logger.info(f"Deleted platesolve JSON: {reason}")
                # Also reset tracking since file is gone
                self.last_processed_filename = None
                self.last_applied_sequence = -1
                self.last_wait_failed_filename = None
                return True
            except PermissionError:
                logger.warning(f"Could not delete platesolve JSON (file in use): {reason}")
                return False
            except Exception as e:
                logger.warning(f"Error deleting platesolve JSON: {e}")
                return False
        else:
            logger.debug(f"Platesolve JSON already deleted: {reason}")
            return True
    
    
    def is_platesolve_current_for_frame(self, data: Dict[str, Any], current_frame_path: str) -> bool:
        """Check if platesolve is valid and not yet processed"""
        try:
            # NEW: First check if platesolve file is from current session
            if self.session_start_time is not None:
                try:
                    json_mtime = self.json_file_path.stat().st_mtime
                    if json_mtime < self.session_start_time:
                        logger.debug(f"Platesolve predates current session - rejecting (JSON age: {time.time() - json_mtime:.1f} s, session age: {time.time() - self.session_start_time:.1f} s)")
                        return False
                except Exception as e:
                    logger.warning(f"Could not check platesolve file time: {e}")
            
            solved_filename = data.get('fitsname', {}).get("0", "")
            if not solved_filename:
                return False
            
            solved_basename = Path(solved_filename).name
            current_basename = Path(current_frame_path).name
            
            # Double-check for acquisition/science phase mismatch
            solved_is_acq = '_acq' in solved_basename
            current_is_acq = '_acq' in current_basename
            
            if solved_is_acq != current_is_acq:
                phase_mismatch = "acquisition->science" if solved_is_acq else "science->acquisition"
                logger.debug(f"Platesolve phase mismatch ({phase_mismatch}) - rejecting")
                return False
            
            
            import re
            def extract_target_id(filename):
                match = re.match(r'^(.+?)_[A-Z]?_\d{8}_', filename)
                if match:
                    return match.group(1)
                match = re.match(r'^(.+?)_\d{8}_', filename)
                return match.group(1) if match else None
            
                        
            def normalize_target_id(tid: str) -> str:
                return tid.replace('-', '').replace('+', '') if tid else tid

            solved_target = extract_target_id(solved_basename)
            current_target = extract_target_id(current_basename)

            # Normalize both forms before any comparisons
            solved_target_norm  = normalize_target_id(solved_target)
            current_id_norm     = normalize_target_id(self.current_target_id)
            current_target_norm = normalize_target_id(current_target)

            if solved_target_norm != current_id_norm:
                logger.debug(f"Platesolve is for different target: {solved_target} vs current {self.current_target_id}")
                return False

            if solved_target_norm != current_target_norm:
                logger.debug(f"Platesolve is for different target: {solved_target} vs {current_target}")
                return False

            
            # Check if platesolve is from acquisition directory when we're in science mode
            if '_acq' in solved_basename and '_acq' not in current_basename:
                logger.debug(f"Platesolve is from acquisition phase, current frame is science - rejecting")
                return False
            
            solved_seq = extract_sequence_from_filename(solved_basename)
            
            if solved_seq < 0:
                logger.debug("Could not extract sequence number from platesolve")
                return False
            
            if solved_seq <= self.last_applied_sequence:
                logger.debug(f"Platesolve already processed: solved seq {solved_seq} <= last applied {self.last_applied_sequence}")
                return False
            
            # Check against the gate: only accept solves for frames captured after last correction
            if solved_seq < self.min_acceptable_sequence:
                logger.debug(f"Platesolve too old: solved seq {solved_seq} < min acceptable {self.min_acceptable_sequence}")
                return False
            
            logger.debug(f"Platesolve is valid: solved frame {solved_seq} (new, not yet applied)")
            return True
                
        except KeyboardInterrupt as e:
            logger.debug(f"Interrupted by user: {e}")
            return False
        
        except Exception as e:
            logger.warning(f"Error checking frame currency: {e}")
            return False  # Default to assuming it's current to avoid blocking corrections
    
    def detect_platesolve_failure(self, data: Dict[str, Any], current_phase: str = None) -> Optional[float]:
        """Detect if platesolve failed and return new exposure time if needed"""
        try:
            ra_offset_deg = float(data['ra_offset']["0"])
            dec_offset_deg = float(data['dec_offset']["0"])
            
            # Check if we've already processed this exact platesolve data
            current_filename = data.get('fitsname', {}).get("0", "")
            if current_filename and current_filename == getattr(self, 'last_failed_filename', None):
                logger.debug("Already processed this failed platesolve data, not increasing exposure again")
                return self.current_exposure_time  # Return current time without increasing
            
            # Exact zeros indicate platesolve failure
            if ra_offset_deg == 0.0 and dec_offset_deg == 0.0:
                logger.debug("Detected platesolve failure: exact zero offsets")
                
                # Remember this failed filename to prevent re-processing
                self.last_failed_filename = current_filename
                
                # Different handling for science vs acquisition mode
                if current_phase == "science":
                    # Track consecutive science failures
                    if not hasattr(self, 'science_failure_count'):
                        self.science_failure_count = 0
                    self.science_failure_count += 1
                    
                    threshold = self.spectro_config.get('science_consecutive_failures_before_adaptive', 3)
                    if self.science_failure_count < threshold:
                        logger.info(f"Science platesolve failed ({self.science_failure_count}/{threshold}) - continuing without adaptive exposure")
                        return self.current_exposure_time  # Keep current exposure
                    else:
                        logger.info(f"Science platesolve failed {self.science_failure_count} times - enabling adaptive exposure")
                        # Fall through to adaptive logic below
                
                # Adaptive exposure logic for acquisition or threshold-exceeded science
                # Initialize retry tracking if needed
                if not hasattr(self, 'current_exposure_retries'):
                    self.current_exposure_retries = 1
                else:
                    self.current_exposure_retries += 1
                
                max_retries = self.spectro_config.get('retries_per_exposure_level', 2)
                
                if self.current_exposure_retries < max_retries:
                    # Stay at current exposure, just retry
                    logger.info(f"Platesolve failed - retry {self.current_exposure_retries}/{max_retries} at {self.current_exposure_time:.1f}s")
                    return self.current_exposure_time
                else:
                    # Move to next exposure level
                    if self.current_exposure_time < self.max_exposure_time:
                        new_exposure = min(
                            self.current_exposure_time * self.exposure_increase_factor,
                            self.max_exposure_time
                        )
                        self.current_exposure_time = new_exposure
                        self.current_exposure_retries = 1  # Reset retry counter for new exposure level
                        logger.info(f"Increased exposure to {new_exposure:.1f} s after {max_retries} failures at previous level")
                        return new_exposure
                    else:
                        logger.warning(f"Already at maximum exposure time ({self.max_exposure_time}s), retry {self.current_exposure_retries}/{max_retries}")
                        return self.current_exposure_time
            
            # Successful platesolve - clear failure tracking
            if ra_offset_deg != 0.0 or dec_offset_deg != 0.0:
                self.last_failed_filename = None
                if hasattr(self, 'current_exposure_retries'):
                    delattr(self, 'current_exposure_retries')
                if hasattr(self, 'science_failure_count'):
                    self.science_failure_count = 0  # Reset science failure count on success
                logger.debug(f"Platesolve successful - maintaining exposure time at {self.current_exposure_time:.1f}s")
                return None
            
            return None  # No failure detected
            
        except KeyboardInterrupt as e:
            logger.debug(f"Interrupted by user: {e}")
            return None
        
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Could not check for platesolve failure: {e}")
            return None
    
    def get_current_exposure_time(self) -> float:
        """Get the current adaptive exposure time"""
        return self.current_exposure_time

    
    def process_platesolve_data(self, data: Dict[str, Any]) -> Tuple[float, float, float, float]:
        """Override to use immediate full corrections for spectroscopy"""
        try:
            # First check if data is current for our target
            # if not self.is_platesolve_data_current(data):
            #     raise PlatesolveCorrectorError("Platesolve data is stale for current target")
            
            # Check for platesolve failure and handle adaptive exposure
            new_exposure = self.detect_platesolve_failure(data)
            if new_exposure is not None:
                raise PlatesolveCorrectorError(f"Platesolve failed, try exposure time {new_exposure:.1f} s")
            
            ra_offset_deg = float(data['ra_offset']["0"])
            dec_offset_deg = float(data['dec_offset']["0"])
            # Ignore rotation offset for spectroscopy
            rot_offset_deg = 0.0  
            base_settle_time = float(data['exptime']["0"])
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset_arcsec = (ra_offset_arcsec**2 + dec_offset_arcsec**2)**0.5
            
            logger.debug(f"Spectro offsets: RA={ra_offset_arcsec:.2f}\", Dec={dec_offset_arcsec:.2f}\", "
                        f"Total={total_offset_arcsec:.2f}\" (rotation ignored)")
            
            # Use spectro-specific thresholds - much tighter for fiber alignment
            spectro_thresholds = self.platesolve_config.get('spectro_thresholds', {})
            min_threshold = spectro_thresholds.get('min_arcsec', 0.01)  # Very tight for spectroscopy
            
            if total_offset_arcsec < min_threshold:
                scale_factor = 0.0
                settle_time = 1.0  # Minimal settle time for spectroscopy
                logger.debug(f"Offset below spectro minimum threshold ({min_threshold:.2f}\"), no correction")
            else:
                # Always apply full correction for spectroscopy - no scaling down
                scale_factor = 1.0
                settle_time = 2.0  # Quick settle for spectroscopy
                logger.debug(f"Spectro offset above threshold, applying full correction")
                
            ra_offset_deg *= scale_factor
            dec_offset_deg *= scale_factor
            
            # Minimal settle time for spectroscopy
            settle_limits = self.spectro_config.get('settle_time', {})
            min_settle = settle_limits.get('min', 1)
            max_settle = settle_limits.get('max', 5)  # Much shorter for spectroscopy
            settle_time = max(min_settle, min(max_settle, settle_time))
            
            return ra_offset_deg, dec_offset_deg, rot_offset_deg, settle_time
            
        except KeyError as e:
            logger.error(f"Missing key in platesolve data: {e}")
            raise PlatesolveCorrectorError(f"Invalid platesolve data format: missing {e}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid data type in platesolve data: {e}")
            raise PlatesolveCorrectorError(f"Invalid platesolve data values: {e}")
    
    def apply_immediate_correction_if_available(self, current_phase: str = None, current_frame_path: str = None, 
                                           latest_captured_sequence: Optional[int] = None) -> CorrectionResult:
        """Apply correction immediately if fresh platesolve data is available"""
        try:
            # Safety check: don't apply corrections while telescope is slewing
            if self.telescope_driver and hasattr(self.telescope_driver.telescope, 'Slewing'):
                if self.telescope_driver.telescope.Slewing:
                    return CorrectionResult(
                        applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                        rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                        reason="Telescope is slewing - not safe to apply correction"
                    )
            
            # Check for fresh data without waiting
            file_ready, data = self.check_json_file_ready()
            
            if not file_ready:
                return CorrectionResult(
                    applied=False,
                    ra_offset_arcsec=0.0,
                    dec_offset_arcsec=0.0, 
                    rotation_offset_deg=0.0,
                    total_offset_arcsec=0.0, 
                    settle_time=0.0, 
                    reason="No fresh platesolve data available"
                )
            
            # Validate frame currency if provided
            if current_frame_path and not self.is_platesolve_current_for_frame(data, current_frame_path):
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                    rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                    reason="Platesolve is for older frame"
                )
            
            # Check if we've already processed this exact solution
            current_filename = data.get('fitsname', {}).get("0", "")
            if current_filename and current_filename == self.last_processed_file:
                return CorrectionResult(
                    applied=False,
                    ra_offset_arcsec=0.0,
                    dec_offset_arcsec=0.0, 
                    rotation_offset_deg=0.0,
                    total_offset_arcsec=0.0, 
                    settle_time=0.0, 
                    reason="Already processed this solution"
                )
            
            # Process the correction
            return self._apply_correction_from_data(data, current_filename, current_phase, latest_captured_sequence)
            
        except PlatesolveCorrectorError:
            # Re-raise specific corrector errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error in immediate correction: {e}")
            raise PlatesolveCorrectorError(f"Immediate correction failed: {e}")
    
    def _apply_correction_from_data(self, data: Dict[str, Any], filename: str, current_phase: str = None,
                                latest_captured_sequence: Optional[int] = None) -> CorrectionResult:
        """Apply correction from platesolve data"""
        # Check if we already processed this exact file
        solved_filename = data.get('fitsname', {}).get("0", "")
        if solved_filename == self.last_processed_filename:
            return CorrectionResult(
                applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                reason="Already processed this exact solution"
            )

        # Extract target ID from filename (everything before the timestamp)
        solved_basename = Path(solved_filename).name
        import re
        target_match = re.match(r'^(.+?)_\d{8}_', solved_basename)
        current_target_id = target_match.group(1) if target_match else None
        
        # Check sequence number if same target
        solved_seq = extract_sequence_from_filename(solved_basename)
        if current_target_id and current_target_id == self.last_target_id:
            if solved_seq <= self.last_applied_sequence:
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                    rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                    reason=f"Already applied correction for sequence {self.last_applied_sequence}"
                )
        else:
            # Must be a different target - reset sequence tracking
            logger.debug(f"New target detected in platesolve: {current_target_id}")
            self.last_target_id = current_target_id
            self.last_applied_sequence = -1
        
        new_exposure = self.detect_platesolve_failure(data, current_phase)
        if new_exposure is not None:
            raise PlatesolveCorrectorError(f"Platesolve failed, try exposure time {new_exposure:.1f} s")
        
        ra_offset_deg, dec_offset_deg, rot_offset_deg, settle_time = self.process_platesolve_data(data)
        
        ra_offset_arcsec = ra_offset_deg * 3600.0
        dec_offset_arcsec = dec_offset_deg * 3600.0
        total_offset_arcsec = (ra_offset_arcsec**2 + dec_offset_arcsec**2)**0.5
        
        # Store last measurements
        if self.store_last_measurements:
            self.last_total_offset_arcsec = total_offset_arcsec
            self.last_ra_offset_arcsec = ra_offset_arcsec
            self.last_dec_offset_arcsec = dec_offset_arcsec
            self.last_rotation_offset_deg = rot_offset_deg
            self.last_measurement_time = time.time()
        
        # Check if correction is needed (use spectro thresholds)
        spectro_thresholds = self.platesolve_config.get('spectro_thresholds', {})
        min_correction = spectro_thresholds.get('min_arcsec', 0.01)
        
        if total_offset_arcsec < min_correction:
            return CorrectionResult(
                applied=False,
                ra_offset_arcsec=ra_offset_arcsec,
                dec_offset_arcsec=dec_offset_arcsec, 
                rotation_offset_deg=rot_offset_deg,
                total_offset_arcsec=total_offset_arcsec, 
                settle_time=settle_time, 
                reason=f"Spectro offset below threshold: {total_offset_arcsec:.3f}\" < {min_correction:.3f}\""
            )
        
        # Apply coordinate correction
        logger.info(f"Applying immediate spectro correction: RA={ra_offset_arcsec:.2f}\", Dec={dec_offset_arcsec:.2f}\", Total={total_offset_arcsec:.2f}\"")
        
        if not self.telescope_driver or not self.telescope_driver.is_connected():
            return CorrectionResult(
                applied=False,
                ra_offset_arcsec=ra_offset_arcsec,
                dec_offset_arcsec=dec_offset_arcsec, 
                rotation_offset_deg=rot_offset_deg,
                total_offset_arcsec=total_offset_arcsec, 
                settle_time=settle_time, 
                reason="Telescope not connected"
            )
        
        success = self.telescope_driver.apply_coordinate_correction(ra_offset_deg, dec_offset_deg)
        
        if success:
            self.last_processed_filename = solved_filename
            self.last_applied_sequence = solved_seq
            self.last_target_id = current_target_id
            
            # Set gate based on what frame we're actually at NOW (not the solved frame)
            if latest_captured_sequence is not None:
                # Only accept solves for frames captured AFTER this correction
                self.min_acceptable_sequence = latest_captured_sequence + 1
                logger.info(f"Applied correction for target={current_target_id}, seq={solved_seq}")
                logger.debug(f"Set min_acceptable_sequence={self.min_acceptable_sequence} (latest captured was {latest_captured_sequence})")
            else:
                # Fallback if we don't know current position: use solved sequence + 1
                self.min_acceptable_sequence = solved_seq + 1
                logger.info(f"Applied correction for target={current_target_id}, seq={solved_seq}")
                logger.warning(f"Set min_acceptable_sequence={self.min_acceptable_sequence} based on solved seq (no capture info)")
            
            return CorrectionResult(
                applied=True, 
                ra_offset_arcsec=ra_offset_arcsec, 
                dec_offset_arcsec=dec_offset_arcsec, 
                rotation_offset_deg=rot_offset_deg,
                total_offset_arcsec=total_offset_arcsec, 
                settle_time=settle_time, 
                reason="Spectro correction applied successfully",
                rotation_applied=False
            )
        else:
            logger.error("Spectro coordinate correction failed")
            return CorrectionResult(
                applied=False, 
                ra_offset_arcsec=ra_offset_arcsec, 
                dec_offset_arcsec=dec_offset_arcsec, 
                rotation_offset_deg=rot_offset_deg,
                total_offset_arcsec=total_offset_arcsec, 
                settle_time=settle_time, 
                reason="Coordinate correction failed",
                rotation_applied=False
            )
    
    def wait_for_correction_with_timeout(self, timeout_seconds: float, current_frame_path: str = None) -> bool:
        """Wait for platesolve correction with active polling"""
        start_time = time.time()
        check_interval = 1.0
        
        logger.debug(f"Waiting up to {timeout_seconds:.1f} s for platesolve correction...")
        
        last_reason = None
        reason_count = 0
        
        def normalize_reason(reason: str) -> str:
            """Normalize reasons with varying numbers for apparently futile deduplication efforts"""
            import re
            reason = re.sub(r'\d+\.\d+s old', 'X.X s old', reason)
            reason = re.sub(r'\d+\.\d+ s old', 'X.X s old', reason)
            reason = re.sub(r'age: \d+ s', 'age: X s', reason)
            reason = re.sub(r'age: \d+s', 'age: X s', reason)
            reason = re.sub(r'frame \d+', 'frame X', reason)
            return reason
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                # Extract sequence from current frame path
                latest_seq = None
                if current_frame_path:
                    latest_seq = extract_sequence_from_filename(Path(current_frame_path).name)
                    if latest_seq < 0:
                        latest_seq = None
                
                result = self.apply_immediate_correction_if_available(
                    current_phase="spectro_sync", 
                    current_frame_path=current_frame_path,
                    latest_captured_sequence=latest_seq
                )
                if result.applied:
                    self.last_wait_failed_filename = None   # Reset on successful correction
                    if reason_count > 1:
                        logger.debug(f"  (previous message repeated {reason_count} times)")
                    logger.info(f"Correction applied during wait: {result.total_offset_arcsec:.2f}\" offset")
                    time.sleep(result.settle_time)
                    return True
                
                # No correction applied - keep waiting
                normalized = normalize_reason(result.reason)
                
                if normalized != last_reason:
                    if reason_count > 1:
                        logger.debug(f"  (previous message repeated {reason_count} times)")
                    logger.debug(result.reason)
                    last_reason = normalized
                    reason_count = 1
                else:
                    reason_count += 1
                        
            except PlatesolveCorrectorError as e:
                # Failed platesolve detected - check if it's NEW
                file_ready, data = self.check_json_file_ready()
                current_failed_file = data.get('fitsname', {}).get("0", "") if file_ready else None
                
                if current_failed_file and current_failed_file != self.last_wait_failed_filename:
                    # NEW failed solve - exit early
                    self.last_wait_failed_filename = current_failed_file
                    error_msg = str(e)
                    normalized = normalize_reason(error_msg)
                    
                    if normalized != last_reason:
                        if reason_count > 1:
                            logger.debug(f"  (previous message repeated {reason_count} times)")
                        logger.debug(f"Platesolve failure detected: {error_msg}")
                    
                    logger.debug("New platesolve completed (failed) - ending wait early")
                    return False
                else:
                    # Same failed solve we've already seen, keep waiting
                    normalized = normalize_reason(str(e))
                    if normalized != last_reason:
                        if reason_count > 1:
                            logger.debug(f"  (previous message repeated {reason_count} times)")
                        logger.debug(f"Platesolve failure detected: {str(e)}")
                        last_reason = normalized
                        reason_count = 1
                    else:
                        reason_count += 1
                        
            except Exception as e:
                logger.debug(f"Unexpected error during correction wait: {e}")
            
            time.sleep(check_interval)
        
        if reason_count > 1:
            logger.debug(f"  (previous message repeated {reason_count} times)")
        
        logger.warning(f"Platesolve timeout after {timeout_seconds:.1f} s - continuing")
        return False
    
    def reset_for_new_sequence(self, reason: str = 'phase change'):
        '''Reset tracking state when starting a new sequence (e.g. from acq to sci phases)'''
        self.last_applied_sequence = -1
        self.last_processed_filename = None
        self.last_target_id = None
        self.min_acceptable_sequence = 0
        self.last_wait_failed_filename = None
        logger.info(f"Reset platesolve tracking: {reason}")


class SpectroscopySession:
    """Manages spectroscopy sessions with optional mirror support and automatic shutdown"""

    def __init__(self, camera_manager, corrector, config_loader, telescope_driver,
             mirror_file: str = None, ignore_twilight: bool = False,
             dry_run: bool = False, exposure_override: Optional[float] = None,
             duration_override: Optional[float] = None, filter_code: str = 'C'):
        self.camera_manager = camera_manager
        self.corrector = corrector
        self.config_loader = config_loader
        self.telescope_driver = telescope_driver
        self.ignore_twilight = ignore_twilight
        self.dry_run = dry_run
        self.exposure_override = exposure_override
        self.duration_override = duration_override
        self.filter_code = filter_code

        self.mirror = TelescopeMirror(mirror_file) if mirror_file else None
        self.current_session = None
        self.current_target = None
        self.logger = logging.getLogger(__name__)
        
        # Initialize observability checker for target validation AND shutdown checks
        observatory_config = config_loader.get_config('observatory')
        self.obs_checker = ObservabilityChecker(observatory_config)
        
        # Add shutdown tracking
        self.should_shutdown = False
        self.shutdown_reason = None

    def check_should_shutdown(self) -> bool:
        """Check if we should shutdown due to sun rise or dome closure conditions"""
        # First check dome closure if we have mirror monitoring
        if self.mirror:
            try:
                dome_closure, dome_reason = self.mirror.check_for_dome_closure()
                if dome_closure:
                    self.shutdown_reason = dome_reason
                    self.should_shutdown = True
                    return True
            except Exception as e:
                self.logger.warning(f"Error checking dome closure status: {e}")
                # Continue to other checks on dome check failure
        
        # If ignore_twilight is set, don't shutdown based on sun altitude
        if self.ignore_twilight:
            return False
            
        try:
            # Create a dummy target to check sun conditions - we just need sun altitude
            # Use current telescope position if available, otherwise use a reference point
            if self.current_target:
                ra_hours = self.current_target['ra_hours']
                dec_deg = self.current_target['dec_deg']
            else:
                # Use a reference point (doesn't matter for sun altitude check)
                ra_hours, dec_deg = 12.0, 0.0
            
            obs_status = self.obs_checker.check_target_observability(
                ra_hours, dec_deg, ignore_twilight=False
            )
            
            # Check if sun is too high (above twilight limit)
            observatory_config = self.config_loader.get_config('observatory')
            twilight_limit = observatory_config.get('twilight_altitude', -18.0)
            
            if obs_status.sun_altitude > twilight_limit:
                sun_condition = "daylight" if obs_status.sun_altitude > 0 else "twilight"
                self.shutdown_reason = f"Sun too high for observations: {obs_status.sun_altitude:.1f}° > {twilight_limit}° ({sun_condition})"
                self.should_shutdown = True
                return True
                
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking shutdown conditions: {e}")
            return False

    def start_monitoring(self, poll_interval: float = 10.0):
        self.logger.info("="*60)
        self.logger.info(" "*15+"STARTING SPECTROSCOPY MONITORING")
        self.logger.info("="*60)
        if self.mirror:
            self.logger.info(f"Monitoring mirror file: {self.mirror.mirror_file}")
            self.logger.info("Dome closure monitoring: ENABLED")
        if self.dry_run:
            self.logger.info("DRY RUN MODE - No telescope movement")

        if self.ignore_twilight:
            self.logger.info("Automatic twilight checks DISABLED due to --ignore-twilight flag")
        else:
            self.logger.info("Automatic shutdown enabled when sun rises")
            # === WAIT FOR ASTRONOMICAL TWILIGHT BEFORE STARTING ===
            while True:
                try:
                    # Check sun altitude using dummy RA/Dec
                    obs_status = self.obs_checker.check_target_observability(12.0, 0.0, ignore_twilight=False)
                    twilight_limit = self.config_loader.get_config("observatory").get("twilight_altitude", -18.0)
                    if obs_status.sun_altitude <= twilight_limit:
                        self.logger.info(
                            f"Sun below twilight limit ({obs_status.sun_altitude:.1f}° <= {twilight_limit}°). Proceeding..."
                        )
                        break
                    else:
                        self.logger.info(
                            f"Waiting for astronomical twilight... Sun alt={obs_status.sun_altitude:.1f}° (limit={twilight_limit}°)"
                        )
                except Exception as e:
                    self.logger.warning(f"Twilight wait check failed: {e}")
                time.sleep(poll_interval)    
        
        try:
            while True:
                # Check for shutdown conditions (dome closure, sunrise, etc.)
                if self.check_should_shutdown():
                    self.logger.info("="*60)
                    self.logger.info("SHUTDOWN CONDITION DETECTED")
                    self.logger.info(f"Reason: {self.shutdown_reason}")
                    self.logger.info("="*60)
                    
                    # If dome closure was detected, immediately abort current exposure
                    if "dome closure" in self.shutdown_reason.lower():
                        if self.current_session and self.current_session.is_running():
                            self.logger.info("Dome closure detected - aborting current exposure immediately")
                            try:
                                self.current_session._abort_current_exposure()
                            except Exception as e:
                                self.logger.warning(f"Error aborting exposure: {e}")
                    
                    break

                self.logger.debug(f"Polling for new targets... (poll interval: {poll_interval}s)")

                if self.mirror:
                    new_target = self.mirror.check_for_new_target()
                    if new_target:
                        self.logger.info("NEW TARGET DETECTED")
                        self.logger.info(f"RA={new_target['ra_hours']:.6f} h ({new_target['ra_hours']*15.0:.6f}°), Dec={new_target['dec_deg']:.6f}°")

                        # Check observability before attempting to use target
                        if not self._validate_target_observability(new_target):
                            self.logger.warning("Target not observable, marking as failed")
                            self.mirror.mark_target_failed(new_target['target_key'])
                            continue

                        # Stop current session if running
                        if self.current_session and self.current_session.is_running():
                            self.logger.info("Stopping current session...")
                            try:
                                self.current_session.stop_session()
                                time.sleep(2.0)
                            except Exception as e:
                                self.logger.warning(f"Error stopping session: {e}")
                            finally:
                                self.current_session = None
                                self.current_target = None

                        # Start new session
                        if not self._start_new_session(new_target):
                            self.mirror.mark_target_failed(new_target['target_key'])
                    else:
                        self.logger.debug("No new targets found")

                # Clean up finished sessions
                if self.current_session and not self.current_session.is_running():
                    self.logger.info("Current session finished")
                    self.current_session = None
                    self.current_target = None

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            self.logger.info("Monitoring interrupted by user")
            self.shutdown_reason = "User interruption"
            return
        except Exception as e:
            self.logger.error(f"Critical error in monitoring loop: {e}")
            self.shutdown_reason = f"Critical error: {e}"
        finally:
            self.logger.info("="*60)
            self.logger.info("BEGINNING SHUTDOWN SEQUENCE")
            if self.shutdown_reason:
                self.logger.info(f"Shutdown reason: {self.shutdown_reason}")
            self.logger.info("="*60)

            if self.current_session:
                try:
                    self.logger.info("Stopping active imaging session...")
                    self.current_session.stop_session()
                except Exception as e:
                    self.logger.warning(f"Error during session cleanup: {e}")
                finally:
                    self.current_session = None

            self.logger.info("Spectroscopy monitoring ended - hardware cleanup will follow")

    def _validate_target_observability(self, target_data: Dict[str, Any]) -> bool:
        """Check if target is observable before attempting to use it"""
        try:
            obs_status = self.obs_checker.check_target_observability(
                target_data['ra_hours'],
                target_data['dec_deg'],
                ignore_twilight=self.ignore_twilight
            )
            
            if obs_status.observable:
                self.logger.debug(f"Target is observable (alt={obs_status.target_altitude:.1f}°)")
                return True
            else:
                reasons = "; ".join(obs_status.reasons)
                self.logger.info(f"Target not observable: {reasons}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking target observability: {e}")
            return False

    def _start_new_session(self, target_data: Dict[str, Any]) -> bool:
        """Start new session with proper error handling and safety checks"""
        try:
            timestamp_suffix = target_data['timestamp'].strftime('%H%M%S')
            target_info = TargetInfo(
                tic_id=f"MIRROR_{target_data['ra_hours']:.3f}h_{target_data['dec_deg']:+.3f}d_{timestamp_suffix}",  # NO _C here!
                ra_j2000_hours=target_data['ra_hours'],
                dec_j2000_deg=target_data['dec_deg'],
                gaia_g_mag=12.0,
                magnitude_source="spectro-default"
            )

            # IMPORTANT: Set target in corrector BEFORE slewing to prevent applying corrections for old target
            if self.corrector and hasattr(self.corrector, 'set_current_target'):
                self.corrector.set_current_target(target_info.tic_id, self.exposure_override)
                self.logger.debug(f"Set corrector target to {target_info.tic_id} before slew")

            # Slew telescope (with safety checks)
            if not self.dry_run:
                self.logger.info("Slewing telescope to target...")
                if not self.telescope_driver or not self.telescope_driver.slew_to_coordinates(
                    target_info.ra_j2000_hours, target_info.dec_j2000_deg
                ):
                    self.logger.error("Failed to slew to target")
                    return False
            else:
                self.logger.info(f"DRY RUN: Would slew to RA={target_info.ra_j2000_hours:.6f} h ({target_info.ra_j2000_hours*15.0:.6f}°), Dec={target_info.dec_j2000_deg:.6f}°")

            self.logger.info("Starting spectroscopy imaging session...")
            session = SpectroscopyImagingSession(
                camera_manager=self.camera_manager,
                corrector=self.corrector,
                config_loader=self.config_loader,
                target_info=target_info,
                ignore_twilight=self.ignore_twilight,
                dry_run=self.dry_run,
                exposure_override=self.exposure_override,
                filter_code=self.filter_code
            )

            # Start imaging asynchronously so monitoring can continue
            platesolve_config = self.config_loader.get_config("platesolving")
            spectro_config = platesolve_config.get("spectro_acquisition", {})
            default_duration = spectro_config.get("default_session_duration_hours", 1.0)
            duration_hours = self.duration_override or default_duration
            session.start_imaging_loop_async(duration_hours=duration_hours)

            self.current_session = session
            self.current_target = target_data
            self.logger.info("Session started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start new session: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Automated Spectroscopy")
    parser.add_argument("target_mode", choices=["tic", "coords", "mirror"])
    parser.add_argument("target_value", nargs="?", help="TIC ID, coordinates, or mirror file")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"])
    parser.add_argument("--ignore-twilight", action="store_true", 
                        help="Bypass twilight checks for daytime testing")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Simulate without any hardware movement")
    parser.add_argument("--duration", type=float, help="Imaging session duration in hours")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="How often to check the mirror json for new targets in seconds (default 10 s)")
    parser.add_argument("--exposure-time", type=float, help="Override exposure time in seconds")
    args = parser.parse_args()

    if args.target_mode in ['tic', 'coords'] and not args.target_value:
        parser.error(f"Target mode '{args.target_mode}' requires a target value")

    config_loader = ConfigLoader(args.config_dir)
    config_loader.load_all_configs()
    
    log_dir = Path(config_loader.get_config("paths")["logs"])
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if args.target_mode == "tic":
        log_name = f"{timestamp}_{args.target_value}_spec.log"
    elif args.target_mode == "coords":
        log_name = f"{timestamp}_MANUAL_spec.log"
    else:  # mirror mode
        log_name = f"{timestamp}_MIRROR_spec.log"
        
    logfile = setup_logging(args.log_level, log_dir, log_name)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging to {logfile}")
    logging.getLogger('astroquery').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

    # Initialize variables for cleanup
    camera_manager = None
    telescope_driver = None
    cover_driver = None
    corrector = None

    try:

        if not args.dry_run:
            logger.info("Discovering cameras...")
            camera_manager = CameraManager()
            if not camera_manager.discover_cameras(config_loader.get_camera_configs()):
                logger.warning("Full camera discovery failed, checking if guide camera available for spectroscopy...")
                
                # For spectroscopy, we only need the guide camera
                guide_camera = camera_manager.get_guide_camera()
                if not guide_camera or '294MM' not in guide_camera.name:
                    logger.error("294MM guide camera not found - required for spectroscopy")
                    return 1
                
                logger.info(f"Continuing with guide camera only for spectroscopy: {guide_camera.name}")
            
            logger.info("Connecting to telescope...")
            telescope_driver = AlpacaTelescopeDriver()
            if not telescope_driver.connect(config_loader.get_telescope_config()):
                logger.error("Failed to connect to telescope")
                return 1
            
            # Safety check: verify telescope is not parked before turning on motor
            tel_info = telescope_driver.get_telescope_info()
            if tel_info.get('at_park', False):
                logger.info("Telescope is parked - unparking...")
                if not telescope_driver.unpark():
                    logger.error("Failed to unpark telescope")
                    return 1
            
            if not telescope_driver.motor_on():
                logger.error("Failed to turn telescope motor on")
                return 1
            
            logger.info(f"Telescope connected: RA={tel_info.get('ra_hours', 0):.6f} h ({tel_info.get('ra_hours', 0)*15.0:.6f}°), Dec={tel_info.get('dec_degrees', 0):.6f}°")

            logger.info("Starting telescope tracking monitor...")
            tracking_thread, tracking_stop_event = ensure_telescope_tracking(telescope_driver, check_interval=0.5)

            # Initialize spectroscopy platesolve corrector (no rotator)
            logger.info("Initializing platesolve corrector for spectroscopy...")
            try:
                corrector = SpectroscopyCorrector(telescope_driver, config_loader)
                logger.info("Spectroscopy corrector initialized")
            except Exception as e:
                logger.warning(f"Corrector initialization failed: {e} - continuing without")
                corrector = None
            
            
            # Connect and open the covers
            try:
                cover_driver = AlpacaCoverDriver()
                if cover_driver.connect(config_loader.get_cover_config()):
                    cover_info = cover_driver.get_cover_info()
                    if cover_info.get('cover_state') != 'Open':
                        logger.info("Opening cover...")
                        if not cover_driver.open_cover():
                            logger.warning("Failed to open cover - continuing anyway")
                    else:
                        logger.info("Cover already open")
                else:
                    logger.warning("Failed to connect to cover - continuing without")
            except Exception as e:
                logger.warning(f"Cover error: {e} - continuing without")         
                
        else:
            logger.info("DRY RUN MODE - Simulating hardware initialization")

        if args.target_mode == "mirror":
            mirror_file = args.target_value or config_loader.get_config("paths")["spectro_mirror_file"]
            logger.info(f"Starting mirror mode with file: {mirror_file}")
                        
            spectro_session = SpectroscopySession(
                camera_manager, corrector, config_loader, telescope_driver,
                mirror_file=mirror_file,
                ignore_twilight=args.ignore_twilight,
                dry_run=args.dry_run,
                exposure_override=args.exposure_time,
                duration_override=args.duration
            )
            
            try:
                spectro_session.start_monitoring(args.poll_interval)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received - shutting down gracefully")
                return 0

        else:
            # Single target mode
            if args.target_mode == "tic":
                logger.info(f"Resolving TIC target: {args.target_value}")
                resolver = TICTargetResolver(config_loader)
                target_info = resolver.resolve_tic_id(args.target_value)
            else:
                logger.info(f"Using manual coordinates: {args.target_value}")
                try:
                    coords = args.target_value.strip().split()
                    if len(coords) != 2:
                        raise ValueError("Expected format: 'RA_DEGREES DEC_DEGREES'")
                    ra, dec = map(float, coords)
                    ra = ra / 15.0
                    
                    # Validate coordinates
                    if not (0 <= ra <= 24) or not (-90 <= dec <= 90):
                        raise ValueError(f"Invalid coordinates: RA={float(coords[0])}, Dec={dec}")
                    
                    target_info = TargetInfo(
                        tic_id=f"MANUAL_{ra:.3f}h_{dec:+.3f}d",
                        ra_j2000_hours=ra,
                        dec_j2000_deg=dec,
                        gaia_g_mag=12.0,
                        magnitude_source="manual-default"
                    )
                except (ValueError, AttributeError) as e:
                    logger.error(f"Invalid coordinates format: {e}")
                    return 1

            # Check observability for single targets
            logger.info("Checking target observability...")
            obs_checker = ObservabilityChecker(config_loader.get_config("observatory"))
            obs_status = obs_checker.check_target_observability(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg,
                ignore_twilight=args.ignore_twilight
            )
            logger.info(f"Target altitude: {obs_status.target_altitude:.1f}°")
            if not obs_status.observable and not args.dry_run:
                logger.error("Target not observable")
                return 1

            
            # Slew to target for single target mode
            if not args.dry_run and telescope_driver:
                logger.info("Slewing to target...")
                if not telescope_driver.slew_to_coordinates(
                    target_info.ra_j2000_hours, target_info.dec_j2000_deg
                ):
                    logger.error("Failed to slew to target")
                    return 1
                else:
                    # Cover handling with error recovery
                    logger.info("Connecting to cover...")
                    try:
                        cover_driver = AlpacaCoverDriver()
                        if cover_driver.connect(config_loader.get_cover_config()):
                            cover_info = cover_driver.get_cover_info()
                            if cover_info.get('cover_state') != 'Open':
                                logger.info("Opening cover...")
                                if not cover_driver.open_cover():
                                    logger.warning("Failed to open cover - continuing anyway")
                            else:
                                logger.info("Cover already open")
                        else:
                            logger.warning("Failed to connect to cover - continuing without")
                            cover_driver = None
                    except Exception as e:
                        logger.warning(f"Cover error: {e} - continuing without")
                        cover_driver = None

            # Start single session
            session = SpectroscopyImagingSession(
                camera_manager, corrector, config_loader, target_info,
                ignore_twilight=args.ignore_twilight,
                dry_run=args.dry_run,
                exposure_override=args.exposure_time
            )
            
            if args.dry_run:
                session.run_simulated_acquisition()
            else:
                session.start_imaging_loop(duration_hours=args.duration or 1)

        logger.info("Spectroscopy complete")
        return 0

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received - initiating shutdown")
        # Fall through to finally block for cleanup
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.debug("Full traceback:", exc_info=True)

    finally:
        # Critical cleanup - ensure hardware is safe
        logger.info("Cleaning up...")
        
        # First: stop any background threads that might spam logs
        try:
            if 'tracking_thread' in locals() and tracking_thread.is_alive():
                logger.info("Stopping telescope tracking monitor...")
                tracking_stop_event.set()
                tracking_thread.join(timeout=2.0)
                if tracking_thread.is_alive():
                    logger.warning("Tracking monitor did not shut down cleanly")
        except KeyboardInterrupt:
            logger.warning("Interrupted during tracking cleanup - skipping")
        except Exception as e:
            logger.error(f"Tracking cleanup error: {e}")
        
        # Camera cleanup
        try:
            if camera_manager:
                logger.info("Shutting down camera coolers...")
                camera_manager.shutdown_all_coolers()
        except KeyboardInterrupt:
            logger.warning("Interrupted during camera cleanup - skipping")
        except Exception as e:
            logger.error(f"Camera cleanup error: {e}")
        
        # Cover cleanup
        try:
            if cover_driver:
                logger.info("Closing cover...")
                cover_driver.close_cover()
        except KeyboardInterrupt:
            logger.warning("Interrupted during cover closure - skipping")
        except Exception as e:
            logger.error(f"Cover cleanup error: {e}")
        
        # Telescope cleanup (most critical - parking)
        try:
            if telescope_driver:
                logger.info("Parking telescope...")
                telescope_driver.park()
                telescope_driver.motor_off()
                telescope_driver.disconnect()
        except KeyboardInterrupt:
            logger.warning("Interrupted during telescope cleanup - telescope may not be parked!")
        except Exception as e:
            logger.error(f"Telescope cleanup error: {e}")
        
        logger.info("Program terminated")


if __name__ == "__main__":
    sys.exit(main())