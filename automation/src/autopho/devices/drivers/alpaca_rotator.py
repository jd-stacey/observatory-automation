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
    
logger = logging.getLogger(__name__)

class AlpacaRotatorError(Exception):
    pass

class AlpacaRotatorDriver:
    
    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise AlpacaRotatorError("Alpaca library not available - please install")
        
        self.rotator = None
        self.config = None
        self.connected = False
        self.last_rotation_move_ts = 0.0
        self.rotator_sign = 1          # overridden from field_rotation.yaml during init
        self._platesolve_sign = 1      # overridden from field_rotation.yaml during init
        self._platesolve_clamp_deg = 5.0  # hard default; leave as-is unless you add to YAML later

        
        
    def connect(self, config: Dict[str, Any]) -> bool:
        try:
            self.config = config
            address = config.get('address', '127.0.0.1:11112')          
            device_number = config.get('device_number', 0)
            mechanical_limits = config.get('mechanical_limits', {})
            self.min_limit = mechanical_limits.get('min_deg', 94.0)   
            self.max_limit = mechanical_limits.get('max_deg', 320.0)
            
            logger.debug(f"Connecting to Alpaca Rotator at {address}, device {device_number}")
            
            self.rotator = Rotator(
                address=address,
                device_number=device_number
            )
            
            
            if not self.is_connected():
            # if not self.rotator.Connected:
                self.rotator.Connected = True
                time.sleep(0.5)
                
            if self.is_connected():
            # if self.rotator.Connected:
                rotator_name = self.rotator.Name
                logger.debug(f"Successfully connected to rotator: {rotator_name}")
                self.connected = True
                
                current_pos = self.get_position()
                logger.debug(f"Current rotator position: {current_pos:.2f}°")
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
        try:
            if not self.rotator:
                return False
            
            # Since .Connected is unreliable, testing a position call to see if connected
            # logic: if we can get a position, we're functionally connected to the rotator
            _ = self.rotator.Position
            self.connected = True
            return True
            
            # OLD CODE
            # is_hw_connected = self.rotator.Connected
            # if not is_hw_connected:
            #     self.connected = False
            # else:
            #     self.connected = True    
            # return is_hw_connected and self.connected
        except Exception as e:
            logger.error(f"Rotator connection test failed: {e}")
            self.connected = False
            return False
        
    def get_position(self):
        if not self.is_connected():
            raise AlpacaRotatorError("Cannot get position - rotator not connected")
        
        try:
            position = self.rotator.Position
            # logger.debug(f"Current rotator position: {position:.2f}°")
            return position
        
        except Exception as e:
            raise AlpacaRotatorError(f"Failed to get position: {e}")
        
        
    def check_position_safety(self, target_position: float) -> Tuple[bool, str]:
        limits_config = self.config.get('limits', {})
        warning_margin = limits_config.get('warning_margin_deg', 30.0)
        emergency_margin = limits_config.get('emergency_margin_deg', 10.0)
        
        
        if target_position <= (self.min_limit + emergency_margin):
            return False, f"Position {target_position:.2f}° within emergency margin ({emergency_margin}°) of min limit {self.min_limit}°"
        if target_position >= (self.max_limit - emergency_margin):
            return False, f"Position {target_position:.2f}° within emergency margin ({emergency_margin}°) of max limit {self.max_limit}°"
        
        if target_position <= (self.min_limit + warning_margin):
            return True, f"Warning: {target_position:.2f}° approaching minimum limit {self.min_limit}°"
        if target_position >= (self.max_limit - warning_margin):
            return True, f"Warning: {target_position:.2f}° approaching maximum limit {self.max_limit}°"
        
        return True, "Position is safe"
    
            
    def initialize_position(self) -> bool:
        if not self.is_connected():
            logger.error("Cannot initialize - rotator not connected")
            return False
        
        try:
            init_config = self.config.get('initialization', {})
            strategy = init_config.get('strategy', 'midpoint')
            
            current_pos = self.get_position()
            
            if strategy == 'midpoint':
                mid_point = (self.min_limit + self.max_limit) / 2.0
                target_pos = mid_point
                logger.debug(f"Initializing to midpoint position: {target_pos:.2f}°")
                
            elif strategy == 'safe_position':
                target_pos = init_config.get('safe_position_deg', 220.0)
                logger.debug(f"Initializing to configured safe position: {target_pos:.2f}°")
                
            else:
                logger.debug(f"No initialization needed, staying at current position: {current_pos:.2f}°")
                return True
            
            position_diff = abs(current_pos - target_pos)
            
            if position_diff < 2.0:
                logger.info(f"Already within 2° of target position ({current_pos:.2f}°), no movement needed")
                return True
            
            is_safe, safety_msg = self.check_position_safety(target_pos)
            if not is_safe:
                logger.error(f"Cannot initialize to unsafe position: {safety_msg}")
                return False
        
            return self.move_to_position(target_pos)
        
        except Exception as e:
            logger.error(f"Rotator initialization failed: {e}")
            return False
        
    def move_to_position(self, position_deg: float) -> bool:
        if not self.is_connected():
            logger.error("Cannot move - rotator not connected")
            return False
        
        try:
            is_safe, safety_msg = self.check_position_safety(position_deg)
            if not is_safe:
                logger.error(f"Refusing unsafe move: {safety_msg}")
                return False
            elif "Warning" in safety_msg:
                logger.warning(safety_msg)
                
            logger.info(f"Moving rotator to position: {position_deg:.2f}°")
            
            self.rotator.MoveAbsolute(position_deg)
            
            while self.rotator.IsMoving:
                logger.debug(f"    Rotating...currently at {self.rotator.Position:.2f}°")
                time.sleep(0.5)
                
            settle_time = self.config.get('settle_time', 2.0)
            logger.info(f"Rotation complete, settling for {settle_time} s")
            time.sleep(settle_time)
            
            final_pos = self.get_position()
            logger.info(f"Rotator positioned at: {final_pos:.2f}°")
            
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

            logger.info(f"Applying platesolve de-rotation: sky Δ={rotation_offset_deg:+.2f}°, "
                        f"mech Δ={mech_delta:+.2f}° (from {current_pos:.2f}° → {target_pos:.2f}°)")
            self.rotator.MoveAbsolute(target_pos)
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
            # ---------------------------------------------------------
            
            
            final_pos = self.get_position()
            logger.debug(f"Rotator now at {final_pos:.2f}°")
            return True

        except Exception as e:
            logger.error(f"Rotation correction failed: {e}")
            return False
        
    def is_moving(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self.rotator.IsMoving
        except Exception as e:
            logger.error(f"Cannot check moving status: {e}")
            return False
        
    def halt(self) -> bool:
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
        if not self.is_connected():
            return {'connected': False}
        
        try:
            current_pos = self.get_position()
            is_safe, safety_status = self.check_position_safety(current_pos)
            
            info={
                'connected': True,
                "name": self.rotator.Name,
                "description": getattr(self.rotator, 'Description', 'Unknown'),
                "position_deg": current_pos,
                "is_moving": self.rotator.IsMoving,
                'can_reverse': getattr(self.rotator, 'CanReverse', False),
                # "step_size": getattr(self.rotator, 'StepSize', None),                 # Dont use - not implemented on driver
                # "target_position": getattr(self.rotator, 'TargetPosition', None),     # Dont use - not implemented on driver
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
            # ---- NEW: wire calibration values from field_rotation.yaml into the driver ----
            cal = field_rotation_config.get('calibration', {})
            self.rotator_sign = int(cal.get('rotator_sign', self.rotator_sign))
            self._platesolve_sign = int(cal.get('platesolve_sign', self._platesolve_sign))
            # optional: keep a hard-coded clamp unless you later add one to YAML
            # self._platesolve_clamp_deg = float(field_rotation_config.get('platesolve', {}).get('clamp_deg', self._platesolve_clamp_deg))
            # ------------------------------------------------------------------------------

            self.field_tracker = FieldRotationTracker(
                self, observatory_config, field_rotation_config
            )
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
        """Check if wrap management is needed"""
        if hasattr(self, 'field_tracker'):
            return self.field_tracker.check_wrap_needed()
        return False
    
    def tracking_notify_exposure_start(self):
        if hasattr(self, 'field_tracker'):
            self.field_tracker.notify_exposure_start()

    def tracking_notify_exposure_end(self):
        if hasattr(self, 'field_tracker'):
            self.field_tracker.notify_exposure_end()
    
        

class FieldRotationTracker:

    """Continuous field rotation tracking during exposures"""

    

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
        
        self.in_exposure = False
        self.pending_flip = False

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

        """Check if rotator will hit limits soon"""

        if not self.fr_config['wrap_management']['enabled']:
            return False      

        lookahead_min = self.fr_config['wrap_management']['lookahead_minutes']
        future_time = Time.now() + lookahead_min * u.minute

        future_pa = self.calculate_required_pa(future_time)
        if future_pa is None:
            return False

        future_pos = self.pa_to_rotator_position(future_pa)
        margin = self.fr_config['wrap_management']['flip_margin_deg']

        return (future_pos < self.rotator.min_limit + margin or 
                future_pos > self.rotator.max_limit - margin)

    

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

        """Main tracking loop - runs during exposures only"""

        update_rate = self.fr_config['tracking']['update_rate_hz']
        move_threshold = self.fr_config['tracking']['move_threshold_deg']
        settle_time = self.fr_config['tracking']['settle_time_sec']
        sleep_interval = 1.0 / update_rate

        import time as _t  # add once here

        while not self.stop_event.is_set():
            try:
                if not self.rotator.is_connected() or not self.target_coord:
                    time.sleep(sleep_interval)
                    continue

                # Calculate required position
                required_pa = self.calculate_required_pa()
                if required_pa is None:
                    time.sleep(sleep_interval)
                    continue

                required_position = self.pa_to_rotator_position(required_pa)
                current_position = self.rotator.get_position()

                # Calculate shortest rotation
                error = (required_position - current_position + 180) % 360 - 180

####            ################## TEMP 
                logger.debug(f"err={error:.3f}°, thr={move_threshold}°, move={abs(error) > move_threshold}")

                # Defer or perform a 180° reference flip if we’re about to hit limits
                if self.check_wrap_needed():
                    if self.in_exposure:
                        self.pending_flip = True       # defer to after exposure
                        logger.info("[field-rot] deferring 180° flip until exposure end")
                    else:
                        self.reference_pa = (self.reference_pa + 180.0) % 360.0
                        logger.info("[field-rot] immediate 180° flip to avoid limits")
                        # Optional: recompute required position immediately after flip
                        required_pa = self.calculate_required_pa()
                        required_position = self.pa_to_rotator_position(required_pa)
                        current_position = self.rotator.get_position()
                        error = (required_position - current_position + 180) % 360 - 180

                # Only move if error exceeds threshold AND cooldown has expired
                if _t.time() >= getattr(self, "_cooldown_until", 0.0):
                    if abs(error) > move_threshold:
                        target_position = current_position + error

                        # Safety check
                        is_safe, _ = self.rotator.check_position_safety(target_position)
                        if is_safe:
                            self.rotator.rotator.MoveAbsolute(target_position)
                            if settle_time > 0:
                                time.sleep(settle_time)

                            # set a short cooldown (e.g., 0.3 s) to avoid spamming near-identical MoveAbsolute
                            self._cooldown_until = _t.time() + 0.3

            except Exception as e:
                logger.warning(f"Tracking loop error: {e}")

            time.sleep(sleep_interval)

    
    
    def notify_exposure_start(self):
        self.in_exposure = True

    def notify_exposure_end(self):
        self.in_exposure = False
        if self.pending_flip:
            self.reference_pa = (self.reference_pa + 180.0) % 360.0
            self.pending_flip = False
            logger.info("[field-rot] executed deferred 180° flip after exposure")
    
    
            
            
                
    