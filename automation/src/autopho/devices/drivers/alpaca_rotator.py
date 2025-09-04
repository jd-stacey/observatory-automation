import time
import logging
from typing import Dict, Any, Optional, Tuple


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
            logger.debug(f"Current rotator position: {position:.2f}°")
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
        if not self.is_connected():
            logger.error("Cannot apply rotation correction - rotator not connected")
            return False
        
        try:
            current_pos = self.get_position()
            
            if abs(rotation_offset_deg) > 5.0:
                logger.warning(f"Large rotation offset ({rotation_offset_deg:.2f}°) - setting to 0°")
                rotation_offset_deg = 0.0
            else:
                rotation_offset_deg *= 0.5      # Scale factor
                
            if abs(rotation_offset_deg) < 0.1:
                logger.debug(f"Rotation correction too small ({rotation_offset_deg:.4f}°), skipping")
                return True
            
            new_position = current_pos + rotation_offset_deg
            
            is_safe, safety_msg = self.check_position_safety(new_position)
            
            if not is_safe:
                logger.warning(f"Cannot apply rotation correction: {safety_msg}")
                logger.info("Continuing without rotation correction - field will rotate naturally")
                return True
            logger.info(f"Applying rotation correction: {rotation_offset_deg:+.2f}°"
                        f"(from {current_pos:.2f}° to {new_position:.2f}°)")
            
            return self.move_to_position(new_position)
        
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
        
        
        
    
            
            
                
    