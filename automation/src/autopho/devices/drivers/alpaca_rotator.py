import threading
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
from astropy.time import Time
import astropy.units as u
import time
import logging
from typing import Dict, Any, Optional, Tuple
from astroplan import Observer


try:
    from alpaca.rotator import Rotator
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
# Set up logging
logger = logging.getLogger(__name__)

class AlpacaRotatorError(Exception):
    pass

# Set up rotator driver class
class AlpacaRotatorDriver:
    
    def __init__(self):
        # ensure Alpyca library installed
        if not ALPACA_AVAILABLE:
            raise AlpacaRotatorError("Alpaca library not available - please install")
        
        self.rotator = None
        self.config = None
        self.connected = False
        self.last_rotation_move_ts = 0.0
        self.rotator_sign = 1          # overridden from field_rotation.yaml during init
        self._platesolve_sign = 1      # overridden from field_rotation.yaml during init
        self._platesolve_clamp_deg = 5.0  # hard default - leave as-is unless added to YAML later

        
    def connect(self, config: Dict[str, Any]) -> bool:
        '''Connect to the rotator and get current position and limits'''
        try:
            self.config = config        # from devices.yaml
            address = config.get('address', '127.0.0.1:11112')          
            device_number = config.get('device_number', 0)
            mechanical_limits = config.get('mechanical_limits', {})
            self.min_limit = mechanical_limits.get('min_deg', 94.0)   
            self.max_limit = mechanical_limits.get('max_deg', 320.0)
            
            logger.debug(f"Connecting to Alpaca Rotator at {address}, device {device_number}")
            
            # initialise rotator class from Alpaca library
            self.rotator = Rotator(address=address, device_number=device_number)
            
            if not self.is_connected():
                self.rotator.Connected = True
                time.sleep(0.5)
                
            if self.is_connected():
                rotator_name = self.rotator.Name
                logger.debug(f"Successfully connected to rotator: {rotator_name}")
                self.connected = True
                
                current_pos = self.get_position()
                logger.debug(f"Current rotator position: {current_pos:.6f}°")
                logger.debug(f"Mechanical limits: {self.min_limit:.1f}° to {self.max_limit:.1f}°")
                
                return True 
            else:
                logger.error("Failed to establish rotator connection")
                return False
        except Exception as e:
            logger.error(f"Rotator connection error: {e}")
            self.connected = False
            return False
        
    def disconnect(self):
        '''Disconnect from the rotator'''
        try:
            if self.rotator and self.connected:
                self.rotator.Connected = False
                logger.info('Rotator disconnected')
            self.connected = False
            return True
        
        except Exception as e:
            logger.error(f"Rotator disconnect error: {e}")
            return False
        
    def is_connected(self):
        '''Get connected status (T/F) based on a Position call (since .Connected is unreliable)'''
        try:
            if not self.rotator:
                return False
            
            # Since .Connected is unreliable, testing a position call to see if connected
            # logic: if we can get a position, we're functionally connected to the rotator
            _ = self.rotator.Position
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"Rotator connection test failed: {e}")
            self.connected = False
            return False
        
    def get_position(self):
        '''Get the current position of the rotator'''
        if not self.is_connected():
            raise AlpacaRotatorError("Cannot get position - rotator not connected")
        
        try:
            # Alpaca function call
            position = self.rotator.Position
            return position
        except Exception as e:
            raise AlpacaRotatorError(f"Failed to get position: {e}")
        
        
    def check_position_safety(self, target_position: float) -> Tuple[bool, str]:
        '''Check the safety of a target rotator position (within mechanical limits)'''
        # Get mechanical limits from devices.yaml
        limits_config = self.config.get('limits', {})
        warning_margin = limits_config.get('warning_margin_deg', 30.0)      # when to 'warn' mechanical limit is approaching (but still process req)
        emergency_margin = limits_config.get('emergency_margin_deg', 10.0)  # when to reject requests
        
        
        # If target position is outside emergency limits - return False and reject requests to move to target position
        if target_position <= (self.min_limit + emergency_margin):
            return False, f"Position {target_position:.6f}° within emergency margin ({emergency_margin}°) of min limit {self.min_limit}°"
        if target_position >= (self.max_limit - emergency_margin):
            return False, f"Position {target_position:.6f}° within emergency margin ({emergency_margin}°) of max limit {self.max_limit}°"
        
        # Otherwise, if target position is within warning limits - log a warning but still return True and process move requests
        if target_position <= (self.min_limit + warning_margin):
            return True, f"Warning: {target_position:.6f}° approaching minimum limit {self.min_limit}°"
        if target_position >= (self.max_limit - warning_margin):
            return True, f"Warning: {target_position:.6f}° approaching maximum limit {self.max_limit}°"
        
        # Any other target position is fine
        return True, "Position is safe"
    
            
    def initialize_position(self) -> bool:
        '''Move the rotator to a safe starting position in the middle of the min and max mechanical limits'''
        if not self.is_connected():
            logger.error("Cannot initialize - rotator not connected")
            return False
        
        try:
            # Get config info from devices.yaml
            init_config = self.config.get('initialization', {})
            # Get the initialisation strategy from devices.yaml (should be either 'midpoint' or 'safe_postion')
            strategy = init_config.get('strategy', 'midpoint')
            # Get the current position of the rotator
            current_pos = self.get_position()
            
            # If the strategy is 'midpoint' set the rotator to the midpoint between the min and max mechanical limits of the rotator
            if strategy == 'midpoint':
                mid_point = (self.min_limit + self.max_limit) / 2.0
                target_pos = mid_point
                logger.debug(f"Initializing to midpoint position: {target_pos:.2f}°")
            # If the strategy is 'safe_position' set the rotator to the position defined in devices.yaml (safe_position_deg)
            elif strategy == 'safe_position':
                target_pos = init_config.get('safe_position_deg', 220.0)
                logger.debug(f"Initializing to configured safe position: {target_pos:.2f}°")
            else:
                logger.debug(f"No initialization needed, staying at current position: {current_pos:.2f}°")
                return True
            
            # If the target position is within 2° of the current position - dont bother moving
            position_diff = abs(current_pos - target_pos)
            if position_diff < 2.0:
                logger.info(f"Already within 2° of target position ({current_pos:.2f}°), no movement needed")
                return True
            
            # Confirm safety of target position
            is_safe, safety_msg = self.check_position_safety(target_pos)
            if not is_safe:
                logger.error(f"Cannot initialize to unsafe position: {safety_msg}")
                return False
            # With safety confirmed, move to the target rotator position        
            return self.move_to_position(target_pos)
        
        except Exception as e:
            logger.error(f"Rotator initialization failed: {e}")
            return False
        
    def move_to_position(self, position_deg: float) -> bool:
        '''Move the rotator to a target position'''
        if not self.is_connected():
            logger.error("Cannot move - rotator not connected")
            return False
        
        try:
            # Confirm safety of target position
            is_safe, safety_msg = self.check_position_safety(position_deg)
            if not is_safe:
                logger.error(f"Refusing unsafe move: {safety_msg}")
                return False
            elif "Warning" in safety_msg:
                logger.warning(safety_msg)
                
            logger.info(f"Moving rotator to position: {position_deg:.6f}°")
            
            # If save, move the rotator via Alpaca function call
            self.rotator.MoveAbsolute(position_deg)
            
            # Log movements while the rotator is still moving
            while self.rotator.IsMoving:
                logger.debug(f"    Rotating...currently at {self.rotator.Position:.6f}°")
                time.sleep(0.5)
                
            # If a settle time is set in devices.yaml - wait for that time after a rotator move
            settle_time = self.config.get('settle_time', 2.0)
            logger.info(f"Rotation complete, settling for {settle_time} s")
            time.sleep(settle_time)
            # Get and report current (final) position of the rotator
            final_pos = self.get_position()
            logger.info(f"Rotator positioned at: {final_pos:.6f}°")
            
            return True
        except Exception as e:
            logger.error(f"Rotation failed: {e}")
            return False
        
    def apply_rotation_correction(self, rotation_offset_deg: float) -> bool:
        """
        Actively de-rotate the camera by the platesolver's reported sky-PA delta (deg).
        Positive rotation_offset_deg means: "rotate image by +theta to match reference".
        We convert sky PA delta → mechanical angle delta using rotator_sign, then MoveAbsolute.
        """
        if not self.is_connected():
            logger.error("Cannot apply rotation correction - rotator not connected")
            return False

        try:
            current_pos = self.get_position()

            # Map sky PA delta to mechanical delta:
            # mech = sign * (sky_pa + mechanical_zero) => Δmech = sign * Δsky
            rotator_sign = getattr(self, "rotator_sign", +1)
            mech_delta = rotator_sign * float(rotation_offset_deg)

            # Optional clamp to ignore wild solves
            clamp_deg = float(getattr(self, "_platesolve_clamp_deg", 5.0))
            if abs(mech_delta) > clamp_deg:
                logger.warning(f"Rotation correction clamped from {mech_delta:+.2f}° to "
                            f"{clamp_deg if mech_delta > 0 else -clamp_deg:+.2f}°")
                mech_delta = clamp_deg if mech_delta > 0 else -clamp_deg

            target_pos = current_pos + mech_delta

            # Wrap / limit safety
            is_safe, safety_msg = self.check_position_safety(target_pos)
            if not is_safe:
                logger.warning(f"Rotation correction refused: {safety_msg}")
                return False

            logger.info(f"Applying platesolve de-rotation: sky Δ={rotation_offset_deg:+.6f}°, "
                        f"mech Δ={mech_delta:+.6f}° (from {current_pos:.6f}° → {target_pos:.6f}°)")
            
            # Rotator position move
            if hasattr(self, 'field_tracker') and self.field_tracker:
                success = self.field_tracker._execute_tracking_move(target_pos)
            else:
                self.rotator.MoveAbsolute(target_pos)
                time.sleep(1)
                success = True
            if not success:
                    logger.warning("Platesolve rotation correction failed")
                    return False

            self.last_rotation_move_ts = time.time()

            # minimal settle (configurable)
            settle_time = float(self.config.get('settle_time', 0.0))
            if settle_time > 0:
                time.sleep(settle_time)

            # --- RESYNC TRACKER STATE AFTER A DISCRETE THETA MOVE ---
            try:
                if hasattr(self, "field_tracker") and self.field_tracker:
                    # 1) short cooldown so the next tick doesn't immediately re-command
                    #    (use max with settle_time if you have a non-zero settle)
                    cooldown = max(0.3, float(self.config.get('settle_time', 0.0)))
                    self.field_tracker._cooldown_until = time.time() + cooldown

                    # 2) refresh tracker’s last commanded PA to the *current* setpoint
                    #    so future platesolve feedback compares to this baseline
                    pa_now = self.field_tracker.calculate_required_pa(Time.now())
                    if pa_now is not None:
                        self.field_tracker._last_pa_cmd = float(pa_now)
            except Exception:
                pass
            
            # Get and log current (final) position of the rotator
            final_pos = self.get_position()
            logger.debug(f"Rotator now at {final_pos:.6f}°")
            return True

        except Exception as e:
            logger.error(f"Rotation correction failed: {e}")
            return False
        
    def is_moving(self) -> bool:
        '''Get moving status of the rotator via Alpaca function call'''
        if not self.is_connected():
            return False
        try:
            # Alpaca function call
            return self.rotator.IsMoving
        except Exception as e:
            logger.error(f"Cannot check moving status: {e}")
            return False
        
    def halt(self) -> bool:
        '''Immediately stop the rotator'''
        if not self.is_connected():
            logger.warning("Cannot halt - rotator not connected")
            return False
        try:
            logger.warning("Halting rotator...")
            self.rotator.Halt()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Halt failed: {e}")
            return False
        
    def get_rotator_info(self) -> Dict[str, Any]:
        '''Get current info about the rotator'''
        if not self.is_connected():
            return {'connected': False}
        
        try:
            # Get current position and safety status of that position
            current_pos = self.get_position()
            is_safe, safety_status = self.check_position_safety(current_pos)
            
            # Get and return information dictionary
            info={
                'connected': True,
                "name": self.rotator.Name,
                "description": getattr(self.rotator, 'Description', 'Unknown'),
                "position_deg": current_pos,
                "is_moving": self.rotator.IsMoving,
                'can_reverse': getattr(self.rotator, 'CanReverse', False),
                # "step_size": getattr(self.rotator, 'StepSize', None),                 # Do not use - not implemented on driver
                # "target_position": getattr(self.rotator, 'TargetPosition', None),     # Do not use - not implemented on driver
                "mechanical_limits": {'min': self.min_limit, 'max': self.max_limit},
                "position_safe": is_safe,
                "safety_status": safety_status
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get rotator info: {e}")
            return {'connected': True, "error": str(e)}
        
    def initialize_field_rotation(self, observatory_config, field_rotation_config):
        """Initialize field rotation tracker"""
        try:
            # Get calibration values from field_rotation.yaml for the driver
            cal = field_rotation_config.get('calibration', {})
            self.rotator_sign = int(cal.get('rotator_sign', self.rotator_sign))
            self._platesolve_sign = int(cal.get('platesolve_sign', self._platesolve_sign))
            # optional: keep a hard-coded clamp unless one is added later to YAML
            # self._platesolve_clamp_deg = float(field_rotation_config.get('platesolve', {}).get('clamp_deg', self._platesolve_clamp_deg))

            # Initialise the tracker
            self.field_tracker = FieldRotationTracker(self, observatory_config, field_rotation_config)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize field rotation: {e}")
            return False

    def set_tracking_target(self, ra_hours, dec_deg, reference_pa_deg=None):
        """Set target for field rotation tracking"""
        if hasattr(self, 'field_tracker'):
            self.field_tracker.set_target(ra_hours, dec_deg, reference_pa_deg)

    def start_field_tracking(self):
        """Start continuous field rotation"""
        if hasattr(self, 'field_tracker'):
            self.field_tracker.start_tracking()
            return True
        return False

    def stop_field_tracking(self):
        """Stop continuous field rotation"""
        if hasattr(self, 'field_tracker'):
            self.field_tracker.stop_tracking()
            return True
        return False

    def apply_platesolve_feedback(self, theta_offset_deg):
        """Apply platesolve rotation feedback to calibration"""
        if not hasattr(self, 'field_tracker'):
            return False
            
        try:
            platesolve_sign = getattr(self, '_platesolve_sign', 1)
            correction = platesolve_sign * theta_offset_deg
            self.field_tracker.mechanical_zero += correction
            logger.info(f"Updated mechanical zero: {correction:+.3f}° -> {self.field_tracker.mechanical_zero:.3f}°")
            return True
        except Exception as e:
            logger.error(f"Failed to apply platesolve feedback: {e}")
            return False

    def check_wrap_status(self):
        """Check if wrap management is needed for rotator flips"""
        if hasattr(self, 'field_tracker'):
            return self.field_tracker.check_wrap_needed()
        return False

class FieldRotationTracker:
    """Continuous field rotation tracking with immediate 180° flip capability"""

    def __init__(self, rotator_driver, observatory_config, field_rotation_config):
        self.rotator = rotator_driver
        self.obs_config = observatory_config
        self.fr_config = field_rotation_config
        self._cooldown_until = 0.0

        # Observatory location
        self.location = EarthLocation(
            lat=observatory_config['latitude'] * u.deg,
            lon=observatory_config['longitude'] * u.deg,
            height=observatory_config.get('altitude', 0) * u.m
        )

        # create astroplan Observer for parallactic angle calculations
        self.observer = Observer(location=self.location)
        
        # Tracking state
        self.target_coord = None  # J2000 SkyCoord
        self.reference_pa = None  # Fixed detector PA
        self.is_tracking = False
        self.tracking_thread = None
        self.stop_event = threading.Event()

        # Calibration parameters
        self.rotator_sign = field_rotation_config['calibration']['rotator_sign']
        self.mechanical_zero = field_rotation_config['calibration']['mechanical_zero_deg']

        logger.debug("FieldRotationTracker initialized")

    def set_target(self, ra_hours, dec_deg, reference_pa_deg=None):
        """Set target coordinates and (if not supplied) freeze the current view as reference PA."""
        self.target_coord = SkyCoord(
            ra=ra_hours * u.hour,
            dec=dec_deg * u.deg,
            frame='icrs'  # J2000
        )

        if reference_pa_deg is not None:
            # user/config explicitly sets the desired detector PA wrt sky
            self.reference_pa = float(reference_pa_deg)
        else:
            # Freeze to the *current* view so the first command is a no-op.
            t0 = Time.now()
            q0 = self.observer.parallactic_angle(t0, self.target_coord).to(u.deg).value  # east-of-north
            mech0 = self.rotator.get_position()
            # mech = sign * (sky_pa + mechanical_zero)  =>  sky_pa = (mech / sign) - mechanical_zero
            sky_pa0 = (mech0 / self.rotator_sign) - self.mechanical_zero
            self.reference_pa = sky_pa0 + q0
            logger.info(f"[field-rot] reference_pa frozen at start: {self.reference_pa:.3f}°")

        logger.debug(f"Tracking target set: RA={ra_hours:.4f} h Dec={dec_deg:.4f}°")

    def calculate_required_pa(self, obs_time=None):
        """Calculate sky PA that keeps detector fixed to the frozen reference."""
        if not self.target_coord:
            return None

        if obs_time is None:
            obs_time = Time.now()

        q = self.observer.parallactic_angle(obs_time, self.target_coord).to(u.deg).value

        if self.reference_pa is None:
            # One-time bootstrap in case set_target() was not called with freeze logic
            mech = self.rotator.get_position()
            q0 = self.observer.parallactic_angle(Time.now(), self.target_coord).to(u.deg).value
            sky_pa0 = (mech / self.rotator_sign) - self.mechanical_zero
            self.reference_pa = sky_pa0 + q0
            logger.info(f"[field-rot] reference_pa auto-bootstrapped: {self.reference_pa:.3f}°")

        # Hold frozen ref forever: desired sky PA = ref - q(now)
        return self.reference_pa - q

    def pa_to_rotator_position(self, sky_pa_deg):
        """Convert sky PA to rotator mechanical position"""
        return self.rotator_sign * (sky_pa_deg + self.mechanical_zero)

    def check_wrap_needed(self):
        """Check if immediate 180° flip is needed"""
        if not self.fr_config['wrap_management']['enabled']:
            return False
            
        # Don't trigger flip if we're in cooldown (already flipping or just finished)
        import time as _t
        if _t.time() < getattr(self, "_cooldown_until", 0.0):
            return False

        current_pos = self.rotator.get_position()
        margin = self.fr_config['wrap_management']['flip_margin_deg']
        
        # Simple proximity check - flip if we're within margin of either limit
        near_min_limit = current_pos < (self.rotator.min_limit + margin)
        near_max_limit = current_pos > (self.rotator.max_limit - margin)
        
        if near_min_limit or near_max_limit:
            logger.info(f"[wrap-check] Immediate flip needed: pos={current_pos:.1f}°, "
                       f"limits=[{self.rotator.min_limit:.1f}°, {self.rotator.max_limit:.1f}°], "
                       f"margin={margin:.1f}°")
            return True
            
        return False

    def start_tracking(self):
        """Start continuous tracking thread"""
        if self.is_tracking:
            return

        self.stop_event.clear()
        self.is_tracking = True
        self.tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.tracking_thread.start()
        logger.info("Field rotation tracking started")

    def stop_tracking(self):
        """Stop tracking thread"""
        self.stop_event.set()
        if self.tracking_thread:
            self.tracking_thread.join(timeout=2.0)
        self.is_tracking = False
        logger.info("Field rotation tracking stopped")

    def _tracking_loop(self):
        """Main tracking loop with immediate flip capability"""
        # Get config vals from field_rotation.yaml
        update_rate = self.fr_config['tracking']['update_rate_hz']
        move_threshold = self.fr_config['tracking']['move_threshold_deg']
        sleep_interval = 1.0 / update_rate

        import time as _t

        while not self.stop_event.is_set():
            try:
                if not self.rotator.is_connected() or not self.target_coord:
                    time.sleep(sleep_interval)
                    continue

                # Skip if rotator is currently moving
                if self.rotator.is_moving():
                    time.sleep(sleep_interval)
                    continue

                # Check for immediate flip need FIRST
                if self.check_wrap_needed():
                    logger.info("[field-rot] Executing immediate 180° flip")
                    success = self._execute_180_flip()
                    if success:
                        logger.info("[field-rot] Flip completed, resuming normal tracking")
                    else:
                        logger.error("[field-rot] Flip failed, will retry next cycle")
                    continue  # Skip normal tracking this cycle
                
                # Skip if we're in cooldown period (after flip or regular move)
                if _t.time() < getattr(self, "_cooldown_until", 0.0):
                    time.sleep(sleep_interval)
                    continue

                # Normal tracking logic
                required_pa = self.calculate_required_pa()
                if required_pa is None:
                    time.sleep(sleep_interval)
                    continue

                required_position = self.pa_to_rotator_position(required_pa)
                current_position = self.rotator.get_position()

                # Proper angle difference calculation with wraparound
                raw_error = required_position - current_position
                
                # Normalize to [-180, +180] range
                if raw_error > 180:
                    error = raw_error - 360
                elif raw_error < -180:
                    error = raw_error + 360
                else:
                    error = raw_error

                # Debug logging with stricter threshold to avoid spam
                if abs(error) > move_threshold and abs(error) < 15.0:
                    logger.debug(f"[field-rot] err={error:.6f}°, thresh={move_threshold}°, req_pos={required_position:.6f}°")

                # Only move if error exceeds threshold and error is reasonable
                if abs(error) > move_threshold and abs(error) < 20.0:
                    target_position = current_position + error

                    # Safety check
                    is_safe, safety_msg = self.rotator.check_position_safety(target_position)
                    if is_safe:
                        logger.debug(f"[field-rot] Moving rotator: {current_position:.6f}° → {target_position:.6f}° (Δ={error:+.6f}°)")
                        
                        # Use the existing position-based move method
                        success = self._execute_tracking_move(target_position)
                        
                        if success:
                            # Set minimal cooldown to prevent immediate re-commanding
                            cooldown_time = 0.5  # Short cooldown for normal moves
                            self._cooldown_until = _t.time() + cooldown_time
                        else:
                            logger.warning("[field-rot] Tracking move failed, will retry next cycle")
                            
                    else:
                        logger.warning(f"[field-rot] Unsafe rotator move rejected: {safety_msg}")

                elif abs(error) >= 30.0:
                    logger.error(f"[field-rot] Rejecting huge error: {error:.6f}° - possible calculation bug")

            except Exception as e:
                logger.warning(f"[field-rot] Tracking loop error: {e}")

            time.sleep(sleep_interval)

    def _execute_180_flip(self) -> bool:
        """Execute an immediate 180° flip of the rotator with atomic PA update and position move"""
        try:
            import time as _t
            
            # 1. Set extended cooldown to pause normal tracking during flip
            flip_duration_estimate = 60.0  # Conservative estimate for 180° move + settling, adjust if flips take longer (based on max rotator speed setting in ASA ACC)
            self._cooldown_until = _t.time() + flip_duration_estimate
            
            # 2. Get current state
            current_pos = self.rotator.get_position()
            current_pa = self.calculate_required_pa()
            
            if current_pa is None:
                logger.error("[field-rot] Cannot calculate PA for flip")
                return False
            
            logger.info(f"[field-rot] Starting 180° flip from pos={current_pos:.3f}°, pa={current_pa:.3f}°")
            
            # 3. Update reference PA (this changes all future calculations)
            old_reference_pa = self.reference_pa
            self.reference_pa = (self.reference_pa + 180.0) % 360.0
            
            # 4. Calculate new target position based on updated reference
            new_target_pa = self.calculate_required_pa()
            new_target_pos = self.pa_to_rotator_position(new_target_pa)
            
            logger.info(f"[field-rot] Flip: ref_pa {old_reference_pa:.3f}° → {self.reference_pa:.3f}°")
            logger.info(f"[field-rot] Moving to pos={new_target_pos:.3f}° (pa={new_target_pa:.3f}°)")
            
            # 5. Execute the physical move
            success = self._execute_flip_move(new_target_pos)
            
            if success:
                final_pos = self.rotator.get_position()
                logger.info(f"[field-rot] 180° flip complete: {current_pos:.3f}° → {final_pos:.3f}°")
                
                # Set shorter cooldown for normal tracking to resume
                self._cooldown_until = _t.time() + 2.0  # Brief settle period
            else:
                # Revert reference_pa on failure to prevent system getting stuck
                self.reference_pa = old_reference_pa
                logger.error("[field-rot] Flip failed, reverted reference PA")
                
            return success
            
        except Exception as e:
            logger.error(f"[field-rot] Flip execution error: {e}")
            return False

    def _execute_flip_move(self, target_position: float) -> bool:
        """Execute 180° flip move with position-based completion checking"""
        try:
            current_pos_start = self.rotator.get_position()
            move_distance = abs(target_position - current_pos_start)
            
            # Use extended timeout for large moves (180° flips)
            if move_distance > 120.0:  # Definitely a flip move
                timeout_duration = self.fr_config['wrap_management'].get('flip_timeout_duration', 45.0)  # timeout for 180° move, from field_rotation.yaml
                position_tolerance = 1.0  # Looser tolerance for big moves
            else:
                # Fallback for smaller moves
                timeout_duration = max(15.0, move_distance / 2.0 + 5.0)
                position_tolerance = 0.2
            
            logger.debug(f"[field-rot] Flip move: {move_distance:.1f}° in max {timeout_duration:.0f}s")
            
            # Start the move via Alpaca function call
            self.rotator.rotator.MoveAbsolute(target_position)
            
            # Wait for completion using position-based checking
            timeout_start = time.time()
            last_progress_log = timeout_start
            
            while time.time() - timeout_start < timeout_duration:
                current_pos = self.rotator.get_position()
                
                # Check if we've reached target within tolerance
                if abs(current_pos - target_position) <= position_tolerance:
                    logger.debug(f"[field-rot] Flip move reached target: {current_pos:.3f}°")
                    
                    # Brief settling period for large moves
                    time.sleep(1.0)
                    
                    final_pos = self.rotator.get_position()
                    logger.debug(f"[field-rot] Flip move complete: {current_pos_start:.3f}° → {final_pos:.3f}°")
                    return True
                
                # Progress logging every 10 seconds to avoid spam
                current_time = time.time()
                if current_time - last_progress_log > 10.0:
                    remaining_distance = abs(target_position - current_pos)
                    logger.debug(f"[field-rot] Flip progress: at {current_pos:.3f}°, {remaining_distance:.1f}° to go")
                    last_progress_log = current_time
                
                time.sleep(0.5)  # Check every 500ms
            
            # Timeout occurred
            final_pos = self.rotator.get_position()
            distance_moved = abs(final_pos - current_pos_start)
            remaining_distance = abs(target_position - final_pos)
            
            logger.error(f"[field-rot] Flip timeout after {timeout_duration:.0f}s: "
                        f"moved {distance_moved:.1f}°, {remaining_distance:.1f}° remaining")
            return False
            
        except Exception as e:
            logger.error(f"[field-rot] Flip move execution failed: {e}")
            return False

    def _execute_tracking_move(self, target_position: float) -> bool:
        """Execute a tracking move with position-based completion (unchanged from original)"""
        try:
            current_pos_start = self.rotator.get_position()
            move_distance = abs(target_position - current_pos_start)
            
            # Calculate reasonable timeout based on move distance
            # Assume conservative 2.5°/s + overhead
            min_timeout = 5.0
            estimated_time = move_distance / 2.5  # Conservative 2.5°/s estimate
            timeout_duration = max(min_timeout, estimated_time + 3.0)
            
            # logger.debug(f"[field-rot] Move distance: {move_distance:.3f}°, timeout: {timeout_duration:.1f} s")
            
            # Start the move via Alapca function call
            self.rotator.rotator.MoveAbsolute(target_position)
            
            # Wait for position to stabilize near target
            timeout_start = time.time()
            position_tolerance = 0.1  # Must be larger than the rotator's positioning error
            last_pos = current_pos_start
            stall_count = 0
            
            while time.time() - timeout_start < timeout_duration:
                current_pos = self.rotator.get_position()
                
                # Check if we've reached target
                if abs(current_pos - target_position) <= position_tolerance:
                    # Position reached, wait a bit more for stabilization
                    time.sleep(0.1)
                    
                    # Apply settle time after movement completes, from field_rotation.yaml
                    settle_time = self.fr_config['tracking']['settle_time_sec']
                    if settle_time > 0:
                        time.sleep(settle_time)
                        
                    logger.debug(f"[field-rot] Move successful: {current_pos_start:.6f}° → {current_pos:.6f}°")
                    return True
                
                # Check for stalled movement
                if abs(current_pos - last_pos) < 0.001:  # Less than 0.001° change
                    stall_count += 1
                    if stall_count > 20:  # 1 second of no movement (20 * 50ms)
                        logger.warning(f"[field-rot] Rotator appears stalled at {current_pos:.6f}°, target was {target_position:.6f}°")
                        return False
                else:
                    stall_count = 0
                    
                last_pos = current_pos
                time.sleep(0.05)  # Check every 50ms
            
            # Timeout - log the failure with more detail
            final_pos = self.rotator.get_position()
            actual_moved = abs(final_pos - current_pos_start)
            logger.warning(f"[field-rot] Move timeout: target={target_position:.6f}°, start={current_pos_start:.6f}°, "
                        f"final={final_pos:.6f}°, moved={actual_moved:.6f}° in {timeout_duration:.1f} s")
            return False
            
        except Exception as e:
            logger.error(f"[field-rot] Tracking move execution failed: {e}")
            return False
    
    
            
            
                
    