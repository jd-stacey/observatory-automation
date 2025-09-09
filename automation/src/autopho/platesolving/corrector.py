import json
import time
import math
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger=logging.getLogger(__name__)

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
    
    def __init__(self, telescope_driver, config_loader, rotator_driver=None):
        self.telescope_driver = telescope_driver
        self.config_loader = config_loader
        self.last_processed_file = ""
        self.cumulative_zero_time = 0
        self.rotator_driver = rotator_driver
                
        self.paths_config = config_loader.get_config('paths')
        self.platesolve_config = config_loader.get_config('platesolving')
        
        self.json_file_path = Path(self.paths_config['platesolve_json'])
        
        if rotator_driver:
            logger.info("PlatesolveCorrector initialized with rotator support")
        else:
            logger.info("PlatesolveCorrector initialized without rotator")
        
    def check_json_file_ready(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        try:
            if not self.json_file_path.exists():
                logger.debug(f"Platesolve JSON file not found: {self.json_file_path}")
                return False, None
            
            mod_time = self.json_file_path.stat().st_mtime
            age_seconds = time.time() - mod_time
            max_age = self.platesolve_config.get('file_max_age_seconds', 200)
            
            if age_seconds > max_age:
                logger.warning(f"Platesolve JSON file is {age_seconds}s old! (max {max_age} s)")
                return False, None
            
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
                
            logger.debug(f"Platesolve JSON file ready (age: {age_seconds:.0f} s)")
            return True, data
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in platesolve file: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error reading JSON platesolve file: {e}")
            return False, None
        
    def process_platesolve_data(self, data: Dict[str, Any]) -> Tuple[float, float, float, float]:
        
        try:
            ra_offset_deg = float(data['ra_offset']["0"])
            dec_offset_deg = float(data['dec_offset']["0"])
            rot_offset_deg = float(data['theta_offset']["0"])
            base_settle_time = float(data['exptime']["0"])
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset_arcsec = math.sqrt(ra_offset_arcsec**2 + dec_offset_arcsec**2)
            
            logger.debug(f"Raw offsets: RA={ra_offset_arcsec:.2f}\", Dec={dec_offset_arcsec:.2f}\","
                         f"Rot={rot_offset_deg:.2f}° , Total={total_offset_arcsec:.2f}\"")
            
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
                scale_factor = 0.9
                settle_time = base_settle_time * 5.0
                logger.debug("Large offset, reduced correction applied")
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
        
    def apply_single_correction(self, timeout_seconds: Optional[float] = None) -> CorrectionResult:
        try:
            if not self.telescope_driver.is_connected():
                return CorrectionResult(
                    applied=False,
                    ra_offset_arcsec=0.0,
                    dec_offset_arcsec=0.0, 
                    rotation_offset_deg=0.0,
                    total_offset_arcsec=0.0, 
                    settle_time=0.0, 
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
                        
                        
                    
                    # while (time.time() - start_time) < timeout_seconds:
                    #     time.sleep(check_interval)
                    #     file_ready, data = self.check_json_file_ready()
                    #     if file_ready:
                    #         break
                        
                if not file_ready:
                    return CorrectionResult(
                    applied=False,
                    ra_offset_arcsec=0.0,
                    dec_offset_arcsec=0.0, 
                    rotation_offset_deg=0.0,
                    total_offset_arcsec=0.0, 
                    settle_time=0.0, 
                    reason="No recent platesolve data available"
                )
            
            current_filename = data.get('fitsname', {}).get("0", "")
            
            if current_filename == self.last_processed_file:
                return CorrectionResult(
                    applied=False,
                    ra_offset_arcsec=0.0,
                    dec_offset_arcsec=0.0, 
                    rotation_offset_deg=0.0,
                    total_offset_arcsec=0.0, 
                    settle_time=0.0, 
                    reason="Already processed this solution"
                )
                
            ra_offset_deg, dec_offset_deg, rot_offset_deg, settle_time = self.process_platesolve_data(data)
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset_arcsec = math.sqrt(ra_offset_arcsec**2 + dec_offset_arcsec**2)
            
            min_correction = self.platesolve_config.get('correction_thresholds', {}).get('min_arcsec', 1.0)
            min_rotation = 0.1
            
            coordinate_correction_needed = total_offset_arcsec >= min_correction
            rotation_correction_needed = self.rotator_driver and abs(rot_offset_deg) >= min_rotation
            
            if not coordinate_correction_needed and not rotation_correction_needed:
                return CorrectionResult(
                    applied=False,
                    ra_offset_arcsec=ra_offset_arcsec,
                    dec_offset_arcsec=dec_offset_arcsec, 
                    rotation_offset_deg=rot_offset_deg,
                    total_offset_arcsec=total_offset_arcsec, 
                    settle_time=settle_time, 
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
                # Actively de-rotate using the platesolver's theta (this MOVES the rotator)
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
                corrections_text = " and".join(corrections_applied)
                logger.info(f"Applied {corrections_text} corrections successfully") #, settling for {settle_time} s
                # time.sleep(settle_time)
                
                return CorrectionResult(
                    applied=True, 
                    ra_offset_arcsec=ra_offset_arcsec, 
                    dec_offset_arcsec=dec_offset_arcsec, 
                    rotation_offset_deg=rot_offset_deg,
                    total_offset_arcsec=total_offset_arcsec, 
                    settle_time=settle_time, 
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
                    applied=False, 
                    ra_offset_arcsec=ra_offset_arcsec, 
                    dec_offset_arcsec=dec_offset_arcsec, 
                    rotation_offset_deg=rot_offset_deg,
                    total_offset_arcsec=total_offset_arcsec, 
                    settle_time=settle_time, 
                    reason="; ".join(failure_reasons),
                    rotation_applied=False
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
                'cumulative_zero_time': self.cumulative_zero_time
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
        
            
            