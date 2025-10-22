import time
import logging
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum

from autopho.imaging.fits_utils import create_fits_file
from autopho.imaging.file_manager import FileManager
from autopho.targets.observability import ObservabilityChecker
from autopho.platesolving.corrector import extract_sequence_from_filename

logger = logging.getLogger(__name__)

class SessionPhase(Enum):
    ACQUISITION = "acquisition"
    SCIENCE = "science"

class ImagingSessionError(Exception):
    pass

class ImagingSession:
    def __init__(self, camera_manager, corrector, config_loader, target_info, filter_code: str, 
                 ignore_twilight: bool = False, exposure_override: Optional[float] = None, 
                 images_base_path: Optional[Path] = None, is_spectroscopy: bool = False):
        self.camera_manager = camera_manager
        self.corrector = corrector
        self.rotator_driver = getattr(corrector, "rotator_driver", None)
        self.config_loader = config_loader
        self.target_info = target_info
        self.filter_code = filter_code
        self.ignore_twilight = ignore_twilight
        self.exposure_override = exposure_override
        self.is_spectroscopy = is_spectroscopy
        self.exposure_count = 0
        self.session_start_time = None
        self.last_correction_exposure = 0
        self.consecutive_failures = 0
        
        self.max_consecutive_failures = 3
        self.main_camera = None
        self.file_manager = None
        self.observability_checker = None
        self.images_base_path = images_base_path
        
        # Acquisition phase tracking
        self.current_phase = SessionPhase.ACQUISITION
        self.acquisition_count = 0
        self.science_count = 0
        self.acquisition_dir = None
        self.science_dir = None
        
        # Load acquisition config
        self.platesolve_config = config_loader.get_config('platesolving')
        self.acquisition_config = self.platesolve_config.get('acquisition', {})
        self.acquisition_enabled = self.acquisition_config.get('enabled', True)
        
        if self.is_spectroscopy:
            self.correction_interval = self.platesolve_config["spectro_acquisition"]["correction_interval"]            # Apply correction every N exposures (science phase)
        else:
            self.correction_interval = self.acquisition_config.get("correction_interval", 2.0)
        
        self._initialize_components()
        
    def _initialize_components(self):
        try:
            # Handle camera initialization - allow None for testing
            if self.camera_manager:
                self.main_camera = self.camera_manager.get_main_camera()
                if not self.main_camera:
                    raise ImagingSessionError("Main camera not found")
                
                if not self.main_camera.connected:
                    if not self.main_camera.connect():
                        raise ImagingSessionError("Failed to connect to main camera")
            else:
                # For testing mode - create a mock camera object or set to None
                self.main_camera = None
                logger.info("Running in test mode - no camera initialized")
            
            self.file_manager = FileManager(self.config_loader)
            
            # Create both acquisition and science directories
            base_target_dir = self.file_manager.create_target_directory(self.target_info.tic_id, base_path=self.images_base_path)
            
            if self.acquisition_enabled:
                # Create acquisition directory
                folder_suffix = self.acquisition_config.get('folder_suffix', '_acq')
                acq_dir_name = base_target_dir.name + folder_suffix
                self.acquisition_dir = base_target_dir.parent / acq_dir_name
                self.acquisition_dir.mkdir(parents=True, exist_ok=True)
                
                # Science directory is the normal one
                self.science_dir = base_target_dir
                
                # Start with acquisition directory
                self.current_target_dir = self.acquisition_dir
                self.current_phase = SessionPhase.ACQUISITION
                logger.info(f"Acquisition mode enabled - starting in: {self.acquisition_dir}")
            else:
                # Skip acquisition, go straight to science
                self.science_dir = base_target_dir
                self.current_target_dir = self.science_dir
                self.current_phase = SessionPhase.SCIENCE
                logger.info("Acquisition mode disabled - starting science imaging")
            
            # Create initial target JSON pointing to current directory
            self._create_complete_target_json(self.current_target_dir)
            
            observatory_config = self.config_loader.get_config('observatory')
            self.observability_checker = ObservabilityChecker(observatory_config)
            
            logger.debug(f"Session initialized: {self.target_info.tic_id}, Filter: {self.filter_code}")
            if self.main_camera:
                logger.debug(f"Camera: {self.main_camera.name}")
            logger.debug(f"Current phase: {self.current_phase.value}")
            
        except Exception as e:
            raise ImagingSessionError(f"Failed to initialize session: {e}")

        
    def _create_complete_target_json(self, target_dir: Path):
        """Update target JSON to point to the specified directory"""
        from autopho.targets.resolver import TICTargetResolver
        resolver = TICTargetResolver()
        target_json_data = resolver.create_target_json(self.target_info)
        
        # Handle case where main_camera is None (for testing)
        camera_name = self.main_camera.name if self.main_camera else "test_camera"
        camera_device_id = self.main_camera.device_id if self.main_camera else "test_device"
        
        if self.is_spectroscopy:
            # fixed vals for spectro
            x0 = 1091 #1101
            y0 = 742 #744
        else:
            if self.main_camera:
                try:
                    cam = self.main_camera.camera
                    binning = self.main_camera.config.get('default_binning', 4)
                    max_x = cam.CameraXSize
                    max_y = cam.CameraYSize
                    x0 = int(((max_x // binning) // 8 * 8) / 2)
                    y0 = int(((max_y // binning) // 2 * 2) / 2)
                except Exception as e:
                    logger.warning(f"Could not query camera for ROI calcs: {e} - using dafaults")
                    # defaults if cam query fails (assumes 4x4 binning)
                    x0 = 1196
                    y0 = 798
            else:
                # defaults for testing (when no camera), assumes 4x4 binning
                x0 = 1196
                y0 = 798
                   
        target_json_data.update({
            "camera_name": camera_name,
            "camera_device_id": camera_device_id,
            "filter_code": self.filter_code,
            "raw_images_directory": str(target_dir),
            "tel": self.file_manager.telescope_id.replace('T', ''),
            "imaging_phase": self.current_phase.value,
            "x0": x0,
            "y0": y0
        })
        
        if self.config_loader.write_target_json(target_json_data):
            logger.info(f"Target JSON updated for {self.current_phase.value} phase: {target_dir}")
        else:
            logger.warning("Failed to write target JSON for external platesolver")
    
    
    # TESTING WITHOUT TEST_ACQUISITION  
    # def test_acquisition_flow(self, simulate_corrections: bool = True) -> bool:
    #     """Test the acquisition phase flow without taking actual images"""
    #     try:
    #         logger.info("Testing acquisition flow...")
            
    #         if not self.acquisition_enabled:
    #             logger.info("Acquisition disabled - test complete")
    #             return True
                
    #         logger.info(f"Acquisition directory: {self.acquisition_dir}")
    #         logger.info(f"Science directory: {self.science_dir}")
    #         logger.info(f"Current phase: {self.current_phase.value}")
            
    #         # Simulate acquisition phase
    #         max_attempts = self.acquisition_config.get('max_attempts', 20)
    #         exposure_time = self.acquisition_config.get('exposure_time', 3.0)
    #         correction_interval = self.acquisition_config.get('correction_interval', 1)
    #         threshold = self.acquisition_config.get('max_total_offset_arcsec', 3.0)
            
    #         logger.info(f"Test config: {exposure_time}s exposures, max {max_attempts} attempts")
    #         logger.info(f"Correction interval: every {correction_interval} frame(s)")
    #         logger.info(f"Acquisition threshold: {threshold} arcseconds")
            
    #         # Simulate some acquisition attempts
    #         for attempt in range(1, min(6, max_attempts + 1)):  # Test up to 5 attempts
    #             logger.info(f"[ACQUISITION] Simulated frame {attempt}")
    #             self.acquisition_count = attempt
                
    #             if simulate_corrections and (attempt % correction_interval) == 0:
    #                 # Simulate improving accuracy over time
    #                 simulated_offset = max(10.0 - (attempt * 2.0), 0.5)
    #                 logger.info(f"Simulated correction applied - offset: {simulated_offset:.1f}\"")
                    
    #                 # Check if we've reached acquisition threshold
    #                 if simulated_offset <= threshold:
    #                     logger.info(f"Simulated acquisition complete! Offset: {simulated_offset:.1f}\" <= {threshold}\"")
    #                     break
                
    #             if attempt >= max_attempts:
    #                 logger.warning(f"Simulated max attempts reached ({max_attempts})")
    #                 break
            
    #         # Test phase transition
    #         logger.info("Testing phase transition...")
    #         self._switch_to_science_phase()
            
    #         if self.current_phase == SessionPhase.SCIENCE:
    #             logger.info("Phase transition successful")
    #             logger.info(f"Now in science phase, directory: {self.science_dir}")
    #             return True
    #         else:
    #             logger.error("Phase transition failed")
    #             return False
                
    #     except Exception as e:
    #         logger.error(f"Acquisition flow test failed: {e}")
    #         return False
    
    
    
    
    def _switch_to_science_phase(self):
        """Transition from acquisition to science imaging"""
        if self.current_phase == SessionPhase.SCIENCE:
            return  # Already in science phase
            
        logger.info("="*60)
        logger.info(" "*15+"SWITCHING TO SCIENCE PHASE")
        logger.info("="*60)
        
        self.current_phase = SessionPhase.SCIENCE
        
        # --- NEW: carry forward adaptive exposure into science for spectroscopy ---
        if (self.is_spectroscopy and self.corrector
                and hasattr(self.corrector, 'get_current_exposure_time')):
            carried = self.corrector.get_current_exposure_time()
            if carried:  # defensive
                self.exposure_override = carried
                # keep the corrector in sync so logs/base match the science exposure
                try:
                    self.corrector.set_current_target(self.target_info.tic_id, carried)
                except Exception:
                    pass
                logger.info(f"Science exposure set to {carried:.1f} s (carried from acquisition)")
        # -------------------------------------------------------------------------
        
        self.current_target_dir = self.science_dir
        
        # Update target JSON to point to science directory
        self._create_complete_target_json(self.science_dir)
        
        # Reset exposure count for science phase
        self.science_count = 0
        self.last_correction_exposure = 0
        
        if (self.corrector and hasattr(self.corrector, 'rotator_driver') and 
            self.corrector.rotator_driver and hasattr(self.corrector.rotator_driver, 'start_field_tracking')):
            time.sleep(1)
            if self.corrector.rotator_driver.start_field_tracking():
                logger.info("Continuous field rotation tracking started")
                self.last_correction_exposure = self.exposure_count + 2
                logger.debug("Supressing platesolve correction for 2 frames to stabilise field rotation")
            else:
                logger.warning("Failed to start field rotation tracking")
        
        if self.corrector:
            self.corrector.min_acceptable_sequence = 0
            self.corrector.last_applied_sequence = -1
            logger.debug("Corrector sequence tracking reset for science phase")
        
        
        logger.info(f"Acquisition complete: {self.acquisition_count} frames")
        logger.info(f"Now saving science frames to: {self.science_dir}")
    
    def _get_current_exposure_time(self) -> float:
        """Get exposure time based on current phase"""
        # Check for adaptive exposure from corrector first (spectroscopy only)
        if (self.is_spectroscopy and self.corrector and 
            hasattr(self.corrector, 'get_current_exposure_time') and
            self.current_phase == SessionPhase.ACQUISITION):
            adaptive_time = self.corrector.get_current_exposure_time()
            if adaptive_time != (self.exposure_override or 0):
                logger.debug(f"Using adaptive exposure time from corrector: {adaptive_time:.1f} s")
                return adaptive_time
        
        # Fall back to original logic
        if self.exposure_override is not None:
            return self.exposure_override
            
        if self.current_phase == SessionPhase.ACQUISITION:
            return self.config_loader.get_exposure_time(
                self.target_info.gaia_g_mag,
                self.filter_code
            ) / 2           # set acquisition exposure time to half that of science phase
        else:
            return self.config_loader.get_exposure_time(
                self.target_info.gaia_g_mag,
                self.filter_code
            )
    
    def _get_current_correction_interval(self) -> int:
        """Get correction interval based on current phase"""
        if self.current_phase == SessionPhase.ACQUISITION:
            return self.acquisition_config.get('correction_interval', 1)
        else:
            return self.correction_interval
    
    def _check_acquisition_complete(self) -> bool:
        """Check if acquisition phase should end"""
        if self.current_phase != SessionPhase.ACQUISITION:
            return True
            
        if not self.corrector:
            logger.warning("No corrector available, skipping acquisition")
            return True
            
        # Check maximum attempts
        max_attempts = self.acquisition_config.get('max_attempts', 20)
        if self.acquisition_count >= max_attempts:
            logger.warning(f"Maximum acquisition attempts reached ({max_attempts})")
            return True
            
        # Check if we have recent or last known correction data
        try:
            correction_status = self.corrector.get_correction_status()
            threshold = self.acquisition_config.get('max_total_offset_arcsec', 3.0)
            
            # Try to get the most recent offset measurement
            total_offset = None
            data_source = None
            
            # First priority: fresh platesolve data
            if correction_status.get('json_file_ready', False):
                pending_offset = correction_status.get('pending_total_offset_arcsec')
                pending_ra = correction_status.get('pending_ra_offset_arcsec', 0.0)
                pending_dec = correction_status.get('pending_dec_offset_arcsec', 0.0)
                
                # Skip if this is a failed solve (exact zeros)
                if pending_ra == 0.0 and pending_dec == 0.0:
                    logger.debug("Skipping 0,0 platesolve result (failed solve)")
                    total_offset = None  # Ignore this result
                else:
                    total_offset = pending_offset
                    data_source = "fresh platesolve"
            
            # Second priority: last known measurement (if recent enough)
            if total_offset is None and correction_status.get('last_total_offset_arcsec') is not None:
                measurement_age = correction_status.get('last_measurement_age_seconds')
                last_ra = correction_status.get('last_ra_offset_arcsec', 0.0)
                last_dec = correction_status.get('last_dec_offset_arcsec', 0.0)
                
                # Skip if cached measurement was also a failed solve
                if last_ra == 0.0 and last_dec == 0.0:
                    logger.debug("Skipping cached 0,0 measurement (was a failed solve)")
                elif measurement_age is not None and measurement_age < 300:  # 5 minutes
                    total_offset = correction_status.get('last_total_offset_arcsec')
                    data_source = f"cached ({measurement_age:.0f}s ago)"
                
            if total_offset is not None:
                # Check if we are within threshold to switch from acq to sci modes
                if total_offset <= threshold:
                    logger.info(f"Target acquired! Total offset: {total_offset:.2f}\" <= {threshold}\" ({data_source})")
                    
                    # Apply the final correction before switching phases
                    logger.info("Applying final acquisition correction...")
                    try:
                        final_result = self.corrector.apply_single_correction(latest_captured_sequence=self.acquisition_count)
                        if final_result.applied:
                            logger.info(f"Final correction applied: {final_result.reason}")
                            time.sleep(final_result.settle_time)
                        else:
                            logger.debug(f"Final correction: {final_result.reason}")
                    except Exception as e:
                        logger.warning(f"Final correction failed: {e} - proceeding to science phase anyway")
                    return True
                else:
                    logger.debug(f"Still acquiring - offset: {total_offset:.2f}\" > {threshold}\" ({data_source})")
            else:
                if self.acquisition_count >= 2:
                    logger.debug("No valid platesolve data available, continuing acquisition")
                else:
                    logger.debug("Waiting for initial platesolve data...")
                    
        except Exception as e:
            logger.warning(f"Could not check acquisition status: {e}")
            
        return False

    def start_imaging_loop(self, max_exposures: Optional[int] = None,
                           duration_hours: Optional[float] = None,
                           telescope_driver = None) -> bool:
        
        logger.info("="*75)
        logger.info(" "*25+"STARTING IMAGING SESSION")
        logger.info("="*75)
        
        # Start continuous field rotation tracking for entire session
        # if (self.corrector and hasattr(self.corrector, 'rotator_driver') and 
        #     self.corrector.rotator_driver and hasattr(self.corrector.rotator_driver, 'start_field_tracking')):
        #     if self.corrector.rotator_driver.start_field_tracking():
        #         logger.info("Continuous field rotation tracking started")
        #     else:
        #         logger.warning("Failed to start field rotation tracking")
        
        if self.acquisition_enabled and self.current_phase == SessionPhase.ACQUISITION:
            logger.info("Starting with target acquisition phase")
            acq_exp_time = self.acquisition_config.get('exposure_time', 3.0)
            max_acq_attempts = self.acquisition_config.get('max_attempts', 20)
            logger.info(f"Acquisition: {acq_exp_time}s exposures, max {max_acq_attempts} attempts")
        
        if max_exposures:
            logger.info(f"Maximum exposures: {max_exposures}")
        if duration_hours:
            logger.info(f"Maximum duration: {duration_hours:.3f} hours")
            
        self.session_start_time = time.time()
        self.exposure_count = 0
        self.consecutive_failures = 0
        
        # ----- start continuous field-rotation tracking for the entire session -----
        try:
            if self.rotator_driver:
                fr_cfg = self.config_loader.get_config('field_rotation')
                if fr_cfg.get('enabled', True):
                    obs_cfg = self.config_loader.get_config('observatory')
                    if self.rotator_driver.initialize_field_rotation(obs_cfg, fr_cfg):
                        # Freeze *current* view: pass reference_pa_deg=None
                        self.rotator_driver.set_tracking_target(
                            self.target_info.ra_j2000_hours,
                            self.target_info.dec_j2000_deg,
                            reference_pa_deg=None
                        )
                        self.rotator_driver.start_field_tracking()
                        logger.info("Field-rotation tracking: started (continuous for session)")
        except Exception as e:
            logger.warning(f"Field-rotation start failed: {e}")
        # --------------------------------------------------------------------------

        
        try:
            while True:
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
                
                # Check if acquisition phase should end
                if (self.current_phase == SessionPhase.ACQUISITION and 
                    self.acquisition_count > 0 and  # At least one acquisition frame
                    self._check_acquisition_complete()):
                    self._switch_to_science_phase()
                
                # Check general termination conditions
                should_terminate, reason = self.check_termination_conditions(max_exposures, duration_hours)
                if should_terminate:
                    logger.info(f"Session terminating: {reason}")
                    break
                
                # Apply corrections based on current phase
                if self._should_apply_correction():
                    self._apply_periodic_correction(last_frame_path=image_filepath)
                
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
        
    def capture_single_exposure(self, telescope_driver = None) -> Optional[str]:
        try:
            exposure_time = self._get_current_exposure_time()
            camera_config = self.main_camera.config
            binning = camera_config.get('default_binning', 4)
            gain = camera_config.get('default_gain', 100)
            
            ##### DEBUGGING #####
            # Report telescope's .Tracking bool and its current RA/Dec Coords and internal Alt/Az coords
            # before every imaging frame
            
            if telescope_driver:
                logger.debug(f"    DEBUG: .Tracking = {telescope_driver.telescope.Tracking}")
                logger.debug(f"    DEBUG: Current Scope Pos (ra_hr, dec_deg) = {telescope_driver.get_coordinates()}")
                logger.debug(f"    DEBUG: Current AltAz: Alt={telescope_driver.telescope.Altitude:.6f}, Az={telescope_driver.telescope.Azimuth:.6f}")
                
            
            phase_prefix = "ACQ" if self.current_phase == SessionPhase.ACQUISITION else "SCI"
            logger.debug(f"{phase_prefix} exposure: {exposure_time} s, binning={binning}, gain={gain}")
            
            # if self.rotator_driver and hasattr(self.rotator_driver, "tracking_notify_exposure_start"):
            #     self.rotator_driver.tracking_notify_exposure_start()

            
            image_array = self.main_camera.capture_image(
                exposure_time=exposure_time,
                binning=binning, 
                gain=gain, 
                light=True
            )
            
            # if self.rotator_driver and hasattr(self.rotator_driver, "tracking_notify_exposure_end"):
            #     self.rotator_driver.tracking_notify_exposure_end()

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
            
            # Add acquisition phase info to FITS header
            if hasattr(hdu, 'header'):
                hdu.header['IMGTYPE'] = (
                    'Acquisition' if self.current_phase == SessionPhase.ACQUISITION else 'Light',
                    'Type of image'
                )
                hdu.header['PHASE'] = (self.current_phase.value, 'Imaging phase')
            
            # Use phase-appropriate sequence number and directory
            if self.current_phase == SessionPhase.ACQUISITION:
                sequence_number = self.acquisition_count + 1
                save_dir = self.acquisition_dir
            else:
                sequence_number = self.science_count + 1
                save_dir = self.science_dir
            
                       
            filepath = self.file_manager.save_fits_file(
                hdu=hdu,
                tic_id=self.target_info.tic_id,
                filter_code=self.filter_code, 
                exposure_time=exposure_time,
                sequence_number=sequence_number,
                target_dir=save_dir
            )
            
            
            
            return str(filepath) if filepath else None
        
        except Exception as e:
            logger.error(f"Single exposure capture failed: {e}")
            return None
        
    def check_termination_conditions(self, max_exposures: Optional[int], 
                                     duration_hours: Optional[float]) -> Tuple[bool, str]:
        
        # Only count science exposures toward max_exposures limit
        science_exposures = self.science_count if self.acquisition_enabled else self.exposure_count
        
        if max_exposures and science_exposures >= max_exposures:
            return True, f"Maximum science exposures reached ({max_exposures})"
        
        if duration_hours and self.session_start_time:
            elapsed_hours = (time.time() - self.session_start_time) / 3600
            if elapsed_hours >= duration_hours:
                return True, f"Maximum duration reached ({duration_hours:.3f} hours)"
        
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
            
        current_interval = self._get_current_correction_interval()
        current_count = self.acquisition_count if self.current_phase == SessionPhase.ACQUISITION else self.science_count
        
        if current_count > 0 and (current_count % current_interval) == 0:
            # Make sure we don't repeat corrections
            if self.current_phase == SessionPhase.ACQUISITION:
                return current_count != self.last_correction_exposure
            else:
                return self.exposure_count != self.last_correction_exposure
                
        return False
    
    def _apply_periodic_correction(self, last_frame_path: str = None) -> bool:
        if not self.corrector:
            return False
        try:
            phase_prefix = "ACQ" if self.current_phase == SessionPhase.ACQUISITION else "SCI"
            logger.debug(f"{phase_prefix} correction check...")
            
            latest_seq = None
            if last_frame_path:
                latest_seq = extract_sequence_from_filename(Path(last_frame_path).name)
                if latest_seq < 0:
                    latest_seq = None
            
            # For photometry, we can pass the last frame path for validation
            # (though less critical than spectroscopy)
            result = self.corrector.apply_single_correction(latest_captured_sequence=latest_seq)
            
            if result.applied:
                logger.info(f"{phase_prefix} correction applied: {result.reason} "
                            f"(Total offset: {result.total_offset_arcsec:.2f}\")")
                self.last_correction_exposure = self.exposure_count
                return True
            else:
                logger.debug(f"{phase_prefix} no correction needed: {result.reason}")
                return False
        except Exception as e:
            logger.warning(f"Correction check failed: {e}")
            return False

    def get_session_stats(self) -> Dict[str, Any]:
        if not self.session_start_time:
            return {'status': 'not_started'}
            
        elapsed_time = time.time() - self.session_start_time
        stats = {
            'status': 'running',
            'current_phase': self.current_phase.value,
            'total_exposures': self.exposure_count,
            'elapsed_hours': elapsed_time / 3600,
            'consecutive_failures': self.consecutive_failures,
            'target': self.target_info.tic_id,
            'filter': self.filter_code,
            'camera_connected': self.main_camera.connected if self.main_camera else False,
            'corrector_available': self.corrector is not None
        }
        
        if self.acquisition_enabled:
            stats.update({
                'acquisition_enabled': True,
                'acquisition_count': self.acquisition_count,
                'science_count': self.science_count,
                'current_directory': str(self.current_target_dir)
            })
        else:
            stats['acquisition_enabled'] = False
            
        return stats