import json
import time
import math
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger=logging.getLogger(__name__)

def extract_sequence_from_filename(filename: str) -> int:
    '''Extract sequence number from filename like _00123.fits'''
    import re
    match = re.search(r'_(\d+)\.fits', filename)
    return int(match.group(1)) if match else -1


@dataclass
class CorrectionResult:
    applied: bool
    ra_offset_arcsec: float
    dec_offset_arcsec: float
    rotation_offset_deg: float
    total_offset_arcsec: float
    settle_time: float
    reason: str
    rotation_applied: bool = False
    
class PlatesolveCorrectorError(Exception):
    pass

class PlatesolveCorrector:
    
    def __init__(self, telescope_driver, config_loader, rotator_driver=None, store_last_measurements=False):
        self.telescope_driver = telescope_driver
        self.config_loader = config_loader
        self.last_processed_file = ""
        self.last_applied_sequence = -1
        self.last_target_id = None
        self.last_failed_filename = None
        self.min_acceptable_sequence = 0
        
        self.current_target_id = None
        self.session_start_time = None
        
        self.cumulative_zero_time = 0
        self.rotator_driver = rotator_driver
        
        # NEW: Add these fields for acquisition memory
        self.store_last_measurements = store_last_measurements
        if store_last_measurements:
            self.last_total_offset_arcsec = None
            self.last_ra_offset_arcsec = None
            self.last_dec_offset_arcsec = None
            self.last_rotation_offset_deg = None
            self.last_measurement_time = None
        else:
            # Ensure fields exist but are always None for backwards compatibility
            self.last_total_offset_arcsec = None
            self.last_ra_offset_arcsec = None
            self.last_dec_offset_arcsec = None
            self.last_rotation_offset_deg = None
            self.last_measurement_time = None
                
        self.paths_config = config_loader.get_config('paths')
        self.platesolve_config = config_loader.get_config('platesolving')
        
        self.json_file_path = Path(self.paths_config['platesolve_json'])
        
        if rotator_driver:
            logger.info("PlatesolveCorrector initialized with rotator support")
        else:
            logger.info("PlatesolveCorrector initialized without rotator")
        
    def set_current_target(self, target_id: str):
        """Set the expected target ID for validation"""
        if self.current_target_id != target_id:
            self.current_target_id = target_id
            self.session_start_time = time.time()
            
            # Try to delete old platesolve data
            if self.json_file_path.exists():
                try:
                    self.json_file_path.unlink()
                    logger.info(f"Deleted old platesolve data for new target: {target_id}")
                except PermissionError:
                    logger.debug("Could not delete platesolve JSON (file in use)")
                except Exception as e:
                    logger.warning(f"Could not delete old platesolve JSON: {e}")
            
            # Reset tracking
            self.last_applied_sequence = -1
            self.last_processed_file = ""
            self.last_target_id = None
            self.min_acceptable_sequence = 0
            self.last_failed_filename = None
            
            logger.info(f"Set current target: {target_id}")
    
    def _normalize_target_id(self, target_id: str) -> str:
        """Normalize target ID for comparison (remove dashes, pluses)"""
        if not target_id:
            return ""
        return target_id.replace('-', '').replace('+', '').upper()
    
    def _extract_target_from_filename(self, filename: str) -> Optional[str]:
        """Extract target ID from filename"""
        basename = Path(filename).name
        # Match pattern: TARGETID_FILTER_YYYYMMDD_HHMMSS_XXs_NNNNN.fits
        # or: TARGETID_YYYYMMDD_HHMMSS_XXs_NNNNN.fits
        match = re.match(r'^(.+?)_[A-Z]?_?\d{8}_', basename)
        if match:
            return match.group(1)
        # Fallback pattern without filter
        match = re.match(r'^(.+?)_\d{8}_', basename)
        return match.group(1) if match else None
    
    def check_json_file_ready(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        try:
            if not self.json_file_path.exists():
                logger.debug(f"Platesolve JSON file not found: {self.json_file_path}")
                return False, None
            
            mod_time = self.json_file_path.stat().st_mtime
            age_seconds = time.time() - mod_time
            max_age = self.platesolve_config.get('file_max_age_seconds', 200)
            
            if age_seconds > max_age:
                logger.debug(f"Platesolve JSON file is {age_seconds}s old! (max {max_age} s)")
                return False, None
            
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
                
            logger.debug(f"    JSON contents - fitsname: {data.get('fitsname', {}).get('0', 'MISSING')}")
            logger.debug(f"    JSON file mtime: {self.json_file_path.stat().st_mtime}, current time: {time.time()}")
            logger.debug(f"Platesolve JSON file ready (age: {age_seconds:.0f} s)")
            return True, data
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in platesolve file: {e}")
            return False, None
        except KeyboardInterrupt as e:
            logger.debug(f"Interrupted by user: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error reading JSON platesolve file: {e}")
            return False, None
        
    def is_platesolve_for_current_target(self, data: Dict[str, Any]) -> bool:
        """Check if platesolve data is for the current target"""
        try:
            # If no target set, accept anything (backwards compatibility)
            if not self.current_target_id:
                logger.debug("No current target set - accepting platesolve")
                return True
            
            # Check if platesolve is from current session
            if self.session_start_time is not None:
                try:
                    json_mtime = self.json_file_path.stat().st_mtime
                    if json_mtime < self.session_start_time:
                        logger.debug(f"Platesolve predates current session - rejecting "
                                   f"(JSON age: {time.time() - json_mtime:.1f}s, "
                                   f"session age: {time.time() - self.session_start_time:.1f}s)")
                        return False
                except Exception as e:
                    logger.warning(f"Could not check platesolve file time: {e}")
            
            # Extract target from platesolve filename
            solved_filename = data.get('fitsname', {}).get("0", "")
            if not solved_filename:
                logger.debug("No filename in platesolve data")
                return False
            
            solved_target = self._extract_target_from_filename(solved_filename)
            if not solved_target:
                logger.debug("Could not extract target from platesolve filename")
                return False
            
            # Normalize both for comparison
            solved_norm = self._normalize_target_id(solved_target)
            current_norm = self._normalize_target_id(self.current_target_id)
            
            if solved_norm != current_norm:
                logger.warning(f"Platesolve target mismatch! "
                             f"Expected: {self.current_target_id}, "
                             f"Got: {solved_target} "
                             f"(from file: {Path(solved_filename).name})")
                return False
            
            logger.debug(f"Platesolve target matches: {solved_target}")
            return True
            
        except Exception as e:
            logger.warning(f"Error validating platesolve target: {e}")
            return False  # Reject on validation errors
    
    
    
    def process_platesolve_data(self, data: Dict[str, Any]) -> Tuple[float, float, float, float]:
    
        try:
            ra_offset_deg = float(data['ra_offset']["0"])
            dec_offset_deg = float(data['dec_offset']["0"])
            rot_offset_deg = float(data['theta_offset']["0"])
            base_settle_time = float(data['exptime']["0"])
            
            # Check for platesolve failure (exact zeros indicate failed solve)
            if ra_offset_deg == 0.0 and dec_offset_deg == 0.0:
                current_filename = data.get('fitsname', {}).get("0", "")
                if current_filename == self.last_failed_filename:
                    logger.debug("Already processed this failed solve")
                    raise PlatesolveCorrectorError("Previously processed failed solve")
                self.last_failed_filename = current_filename
                logger.debug("Platesolve failure detected: exact zero offsets - skipping this solve")
                raise PlatesolveCorrectorError("Platesolve returned zero offsets - solve failed, waiting for next")
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset_arcsec = math.sqrt(ra_offset_arcsec**2 + dec_offset_arcsec**2)
            
            logger.debug(f"Raw offsets: RA={ra_offset_arcsec:.2f}\" ({ra_offset_deg:.8f}°), Dec={dec_offset_arcsec:.2f}\" ({dec_offset_deg:.8f}°), "
                        f"Rot={rot_offset_deg:.6f}°, Total={total_offset_arcsec:.4f}\"")
            
            thresholds = self.platesolve_config.get('correction_thresholds', {})
            min_threshold = thresholds.get('min_arcsec', 1.0)
            small_threshold = thresholds.get('small_offset', 1.0)
            large_threshold = thresholds.get('large_offset', 5.0)
            
            if total_offset_arcsec < min_threshold:
                scale_factor = 0.0
                settle_time = 2.0
                logger.debug("Offset below minimum threshold, no correction")
            elif total_offset_arcsec < small_threshold:
                scale_factor = 0.0
                settle_time = base_settle_time * 5.0
                logger.debug("Small offset, no correction applied")
            elif total_offset_arcsec > large_threshold:
                scale_factor = 1.0  # CHANGED from 0.9 - apply full correction
                settle_time = base_settle_time * 5.0
                logger.debug("Large offset, full correction applied")
            else:
                scale_factor = self.platesolve_config.get('correction_scale_factor', 1.0)
                settle_time = base_settle_time * 7.0
                logger.debug("Normal offset, full correction applied")
                
            ra_offset_deg *= scale_factor
            dec_offset_deg *= scale_factor
            
            if abs(rot_offset_deg) > 5.0:
                logger.debug(f"Large rotation offset ({rot_offset_deg:.2f}°), setting to 0°")
                rot_offset_deg = 0.0
            else:
                rot_offset_deg *= 0.5       # Scale Factor
            
            settle_limits = self.platesolve_config.get('settle_time', {})
            min_settle = settle_limits.get('min', 10)
            max_settle = settle_limits.get('max', 140)
            settle_time = max(min_settle, min(max_settle, settle_time))
            
            return ra_offset_deg, dec_offset_deg, rot_offset_deg, settle_time
        
        except KeyError as e:
            logger.error(f"Missing key in platesolve data: {e}")
            raise PlatesolveCorrectorError(f"Invalid platesolve data format: missing {e}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid data type in platesolve data: {e}")
            raise PlatesolveCorrectorError(f"Invalid platesolve data values: {e}")
        except Exception as e:
            logger.error(f"Error processing platesolve data: {e}")
            raise PlatesolveCorrectorError(f"Failed to process platesolve data: {e}")
        
    def apply_single_correction(self, timeout_seconds: Optional[float] = None,
                                latest_captured_sequence: Optional[int] = None) -> CorrectionResult:
        try:
            if not self.telescope_driver.is_connected():
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0, 
                    rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0, 
                    reason="Telescope not connected"
                )
                
            file_ready, data = self.check_json_file_ready()
            
            if not file_ready:
                if timeout_seconds and timeout_seconds > 0:
                    logger.info(f"Waiting up to {timeout_seconds} s for platesolve data...")
                    start_time = time.time()
                    check_interval = self.platesolve_config.get('check_interval_seconds', 5)
                    
                    while True:
                        file_ready, data = self.check_json_file_ready()
                        if file_ready:
                            break
                        elapsed = time.time() - start_time
                        remaining = timeout_seconds - elapsed
                        if remaining <= 0:
                            break
                        logger.debug(f"Waiting for platesolve file... {elapsed:.1f} / {timeout_seconds} s elapsed")
                        time.sleep(min(check_interval, remaining))
                        
                if not file_ready:
                    return CorrectionResult(
                        applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0, 
                        rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0, 
                        reason="No recent platesolve data available"
                    )
            
            # **NEW: Validate target BEFORE processing**
            if not self.is_platesolve_for_current_target(data):
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                    rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                    reason="Platesolve is for different target - rejecting"
                )
            
            current_filename = data.get('fitsname', {}).get("0", "")
            
            # Check 1: Exact filename match (prevents duplicate processing)
            if current_filename == self.last_processed_file:
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                    rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                    reason="Already processed this solution"
                )
            
            # Check 2: Target ID tracking (reset sequence on target change)
            current_basename = Path(current_filename).name
            target_match = re.match(r'^(.+?)_\d{8}_', current_basename)
            current_target_id = target_match.group(1) if target_match else None
            
            # Extract sequence from basename
            current_seq = extract_sequence_from_filename(current_basename)
            logger.debug(f"    Reading current_basename as: {current_basename}")
            logger.debug(f"    Reading current_target_id as: {current_target_id}")
            logger.debug(f"    Reading current_seq as: {current_seq}")
            
            # If target changed, reset sequence tracking
            if current_target_id and current_target_id != self.last_target_id:
                self.last_target_id = current_target_id
                self.last_applied_sequence = -1
                logger.info(f"New target detected in platesolve: {current_target_id}")
            
            # Check 3: Sequence number (only if same target)
            if current_target_id and current_target_id == self.last_target_id:
                if current_seq <= self.last_applied_sequence:
                    return CorrectionResult(
                        applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                        rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                        reason=f"Already applied correction for sequence {self.last_applied_sequence}"
                    )
                
            if current_seq < self.min_acceptable_sequence:
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=0.0, dec_offset_arcsec=0.0,
                    rotation_offset_deg=0.0, total_offset_arcsec=0.0, settle_time=0.0,
                    reason=f"Solve too old: frame {current_seq} captured before last correction (min: {self.min_acceptable_sequence})"
                )
            
            ra_offset_deg, dec_offset_deg, rot_offset_deg, settle_time = self.process_platesolve_data(data)
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset_arcsec = math.sqrt(ra_offset_arcsec**2 + dec_offset_arcsec**2)
            
            # Store last known values if enabled
            if self.store_last_measurements:
                self.last_total_offset_arcsec = total_offset_arcsec
                self.last_ra_offset_arcsec = ra_offset_arcsec
                self.last_dec_offset_arcsec = dec_offset_arcsec
                self.last_rotation_offset_deg = rot_offset_deg
                self.last_measurement_time = time.time()
            
            min_correction = self.platesolve_config.get('correction_thresholds', {}).get('min_arcsec', 1.0)
            min_rotation = 0.1
            
            coordinate_correction_needed = total_offset_arcsec >= min_correction
            rotation_correction_needed = self.rotator_driver and abs(rot_offset_deg) >= min_rotation
            
            # Suppress coord correction briefly after rotator move
            try:
                last_rot = getattr(self.rotator_driver, "last_rotation_move_ts", 0.0)
                if (time.time() - last_rot) < 0.8:
                    coordinate_correction_needed = False
                    logger.debug("Skipping RA/Dec correction (recent rotator move).")
            except Exception:
                pass
            
            if not coordinate_correction_needed and not rotation_correction_needed:
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=ra_offset_arcsec,
                    dec_offset_arcsec=dec_offset_arcsec, rotation_offset_deg=rot_offset_deg,
                    total_offset_arcsec=total_offset_arcsec, settle_time=settle_time, 
                    reason=f"Offsets below thresholds: coord={total_offset_arcsec:.2f}\", rot={abs(rot_offset_deg):.2f}°"
                )
            
            corrections_applied = []
            coordinate_success = True
            rotation_success = True
            
            if coordinate_correction_needed:
                logger.info(f"Applying correction: RA={ra_offset_arcsec:.2f}\", Dec={dec_offset_arcsec:.2f}\", Total={total_offset_arcsec:.2f}\"")
                coordinate_success = self.telescope_driver.apply_coordinate_correction(ra_offset_deg, dec_offset_deg)
                if coordinate_success:
                    corrections_applied.append("coordinates")
                else:
                    logger.error("Coordinate correction failed")
                    
            if rotation_correction_needed:
                logger.info(f"Applying platesolve de-rotation: {rot_offset_deg:+.2f}°")
                try:
                    rotation_success = self.rotator_driver.apply_rotation_correction(rot_offset_deg)
                except Exception as e:
                    logger.error(f"Rotation correction call failed: {e}")
                    rotation_success = False

                if rotation_success:
                    corrections_applied.append("rotation")
                else:
                    logger.error("Rotation correction failed")
                    
            overall_success = coordinate_success and rotation_success
            
            if overall_success and corrections_applied:
                self.last_processed_file = current_filename
                self.last_applied_sequence = current_seq  # Use extracted sequence
                self.last_target_id = current_target_id   # Update target tracking
                
                # Delete platesolve JSON after successful solve
                try:
                    if self.json_file_path.exists():
                        self.json_file_path.unlink()
                        logger.debug("Deleted platesolve JSON after successful correction")
                except PermissionError:
                    logger.debug("Could not delete platesolve JSON (file in use)")
                except Exception as e:
                    logger.debug(f"Could not delete platesolve JSON: {e}")
                
                if latest_captured_sequence is not None:
                    self.min_acceptable_sequence = latest_captured_sequence + 1
                    logger.debug(f"Set min acceptable seq to {self.min_acceptable_sequence} (latest captured was {latest_captured_sequence})")
                else:
                    self.min_acceptable_sequence = current_seq + 1
                    logger.debug(f"Set min acceptable seq to {self.min_acceptable_sequence} based on solved seq (no capture info)")
                
                               
                logger.info(f"Applied correction for target={current_target_id}, seq={current_seq}")
                
                return CorrectionResult(
                    applied=True, ra_offset_arcsec=ra_offset_arcsec, 
                    dec_offset_arcsec=dec_offset_arcsec, rotation_offset_deg=rot_offset_deg,
                    total_offset_arcsec=total_offset_arcsec, settle_time=settle_time, 
                    reason="Correction applied successfully",
                    rotation_applied=rotation_correction_needed and rotation_success
                )
                
            else:
                failure_reasons = []
                if not coordinate_success:
                    failure_reasons.append("coordinate correction failed")
                if not rotation_success:
                    failure_reasons.append("rotation correction failed")
                    
                return CorrectionResult(
                    applied=False, ra_offset_arcsec=ra_offset_arcsec, 
                    dec_offset_arcsec=dec_offset_arcsec, rotation_offset_deg=rot_offset_deg,
                    total_offset_arcsec=total_offset_arcsec, settle_time=settle_time, 
                    reason="; ".join(failure_reasons), rotation_applied=False
                )
        
        except PlatesolveCorrectorError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in correction: {e}")    
            raise PlatesolveCorrectorError(f"Correction failed: {e}")
        
        
    def run_correction_loop(self, max_runtime_seconds: Optional[float] = None) -> bool:
        
        logger.info("Starting platesolve correction loop")
        logger.info(f"Monitoring file: {self.json_file_path}")
        
        if self.rotator_driver:
            logger.debug(f"Rotation corrections enabled")
        else:
            logger.debug(f"Rotation corrections disabled (no rotator)")
        
        if not self.telescope_driver.is_connected():
            logger.error("Cannot start correction loop - telescope not connected")
            return False
        
        start_time = time.time()
        check_interval = self.platesolve_config.get('check_interval_seconds', 5)
        timeout_limit = self.platesolve_config.get('timeout_seconds', 600)
        
        try:
            while True:
                if max_runtime_seconds and (time.time() - start_time) > max_runtime_seconds:
                    logger.info("Correction loop reached time limit")
                    break
                
                try:
                    result = self.apply_single_correction()
                    
                    if result.applied:
                        correction_types = []
                        if result.total_offset_arcsec > 0:
                            correction_types.append(f"coord: {result.total_offset_arcsec:.2f}\"")
                        if result.rotation_applied:
                            correction_types.append(f"rot: {result.rotation_offset_deg:+.2f}°")
                                                
                        logger.info(f"Corrections applied: {', '.join(correction_types)} - {result.reason}")
                        self.cumulative_zero_time = 0
                        
                    elif "threshold" in result.reason or "Already processed" in result.reason:
                        logger.debug(result.reason)
                        
                    else:
                        self.cumulative_zero_time += check_interval
                        logger.debug(f"No correction data ({self.cumulative_zero_time} s total)")
                        
                except PlatesolveCorrectorError as e:
                    logger.error(f"Correction error: {e}")
                    self.cumulative_zero_time += check_interval
                    
                if self.cumulative_zero_time > timeout_limit:
                    logger.warning(f"Correction loop timeout after {timeout_limit} s without valid data")
                    break
                
                # TODO: Add exit condition checks here when imaging module is ready
                # - check target altitude vs min_alitude
                # - check twilight conditions
                # - check if imaging should continue
                
                time.sleep(check_interval)
        
        except KeyboardInterrupt as e:
            logger.info(f"Correction loop interrupted by user: {e}")        
            return True
        except Exception as e:
            logger.error(f"Unexpected error in correction loop: {e}")
            return False
        
    def get_correction_status(self) -> Dict[str, Any]:
        try:
            file_ready, data = self.check_json_file_ready()
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'telescope_connected': self.telescope_driver.is_connected(),
                'rotator_connected': self.rotator_driver.is_connected() if self.rotator_driver else False,
                'rotator_enabled': self.rotator_driver is not None,
                'json_file_exists': self.json_file_path.exists(),
                'json_file_ready': file_ready,
                'last_processed_file': self.last_processed_file,
                'cumulative_zero_time': self.cumulative_zero_time,
                # Add last known values
                'last_total_offset_arcsec': self.last_total_offset_arcsec,
                'last_ra_offset_arcsec': self.last_ra_offset_arcsec,
                'last_dec_offset_arcsec': self.last_dec_offset_arcsec,
                'last_rotation_offset_deg': self.last_rotation_offset_deg,
                'last_measurement_time': self.last_measurement_time,
                'last_measurement_age_seconds': (time.time() - self.last_measurement_time) if self.last_measurement_time else None
            }
            
            if self.rotator_driver:
                try:
                    rotator_info = self.rotator_driver.get_rotator_info()
                    status['rotator_position'] = rotator_info.get('position_deg')
                    status['rotator_safe'] = rotator_info.get('position_safe', True)
                except Exception as e:
                    status['rotator_error'] = str(e)
            
            
            if file_ready and data:
                try:
                    ra_offset_deg, dec_offset_deg, rot_offset_deg, settle_time = self.process_platesolve_data(data)
                    ra_offset_arcsec = ra_offset_deg * 3600.0
                    dec_offset_arcsec = dec_offset_deg * 3600.0
                    total_offset_arcsec = math.sqrt(ra_offset_arcsec**2 + dec_offset_arcsec**2)
                    
                    status.update({
                        'pending_ra_offset_arcsec': ra_offset_arcsec,
                        'pending_dec_offset_arcsec': dec_offset_arcsec,
                        'pending_total_offset_arcsec': total_offset_arcsec,
                        'pending_rotation_offset_deg': rot_offset_deg,
                        'calculated_settle_time': settle_time
                    })
                except Exception as e:
                    status['data_error'] = str(e)
            
            return status
        
        except Exception as e:
            logger.error(f"Error getting correction status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            
    def reset_correction_status(self):
        self.last_processed_file = ""
        self.cumulative_zero_time = 0
        logger.info("Correction state reset")
        
def create_platesolve_corrector(telescope_driver, config_loader, rotator_driver=None):
    
    try:
        return PlatesolveCorrector(telescope_driver, config_loader, rotator_driver)
    except Exception as e:
        logger.error(f"Failed to create platesolve correction: {e}")
        raise PlatesolveCorrectorError(f"Cannot create corrector: {e}")
        
            
            