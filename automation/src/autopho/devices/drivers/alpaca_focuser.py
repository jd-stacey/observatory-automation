'''For Alpaca connection and operation of the focuser - position, limits, change position etc.
Will also interact with the joint/coordinated focus_filter_manager.py which jointly operates the filter wheel and the focuser'''

import time
import logging
from typing import Dict, Any, Tuple, Union

try:
    from alpaca.focuser import Focuser
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
# Set up logging
logger = logging.getLogger(__name__)

class AlpacaFocuserError(Exception):
    pass

# Set up focuser driver class
class AlpacaFocuserDriver:
    def __init__(self):
        # Ensure alpyca is installed
        if not ALPACA_AVAILABLE:
            raise AlpacaFocuserError("Alpaca library not available. Please install.")
        self.config: Dict[str, Any] | None = None
        self.focuser: Focuser | None = None
        self.connected: bool = False
        self.position: int | None = None
        self.limits: Dict[str, int | str] | None = None
        self.info: Dict[str, Any] | None = None
        
    def connect(self, config: Dict[str, Any]) -> bool:
        self.config = config
        address = config.get('address', '127.0.0.1:11112')
        device_number = config.get('device_number', 0)
        logger.debug(f"Connecting to Focuser at {address}, device {device_number}")

        try:
            self.focuser = Focuser(address=address, device_number=device_number)
            if not self.is_connected():
                self.focuser.Connected = True 
                time.sleep(0.5)

            if self.is_connected():
                self.connected = True
                # populate cached state
                self.refresh_info()
                return True
            else:
                logger.error("Failed to establish focuser connection")
                return False
        except Exception as e:
            logger.error(f"Focuser connection error: {e}")
            self.connected = False
            return False
    
    def is_connected(self):
        try:
            if not self.focuser:
                return False
            # Since .Connected is unreliable, testing a position call to see if connected
            # logic: if we can get a position, we're functionally connected to the focuser
            _ = self.focuser.Position
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Focuser connection test failed: {e}")
            self.connected = False
            return False
        
    def get_position(self) -> int:
        if not self.is_connected():
            raise AlpacaFocuserError("Cannot get position - focuser not connected")
        
        try:
            position = self.focuser.Position
            return position
        except Exception as e:
            raise AlpacaFocuserError(f"Failed to get position: {e}")
        
    def move_to_position(self, target_position):
        if not self.is_connected():
            raise AlpacaFocuserError("Move failed - focuser not connected")
             
        try:
            is_safe, safety_msg = self.check_position_safety(target_position)
            if not is_safe:
                logger.error(f"Refusing unsafe move: {safety_msg}")
                return False
            logger.info(f"Moving focuser to position: {target_position}")
            
            self.focuser.Move(target_position)
            
            while self.focuser.IsMoving:
                logger.debug(f"    Moving focus position...currently at {self.focuser.Position}...")
                time.sleep(5)
            
            current_pos = self.get_position()
            logger.info(f"Focuser move complete - positioned at {current_pos}")
            return True
        except Exception as e:
            logger.error(f"Focuser Move failed: {e}")
            return False
        
    
    def halt(self) -> bool:
        if not self.is_connected():
            logger.warning("Cannot halt - focuser not connected")
            return False
        try:
            if not self.focuser.IsMoving:
                logger.info("Focuser is not currently moving")
                return False
            else:
                logger.warning("Halting focuser...")
                self.focuser.Halt()
                while self.focuser.IsMoving:
                    time.sleep(0.5)
                logger.info(f"Focuser halted at position {self.get_position()}")
                return True
        except Exception as e:
            logger.error(f"Focuser halt failed: {e}")
            return False

    
    def refresh_info(self, force: bool = True) -> Dict[str, Any]:
        """Refresh and cache the focuser state. Returns the info dict."""
        if not self.is_connected():
            self.info = {"connected": False, "error": "not connected"}
            return self.info

        if self.info is None or force:
            current_pos = self.get_position()
            limits = self.get_limits()
            is_safe, safety_status = self.check_position_safety(current_pos)

            self.info = {
                "connected": True,
                "name": self.focuser.Name,
                "description": getattr(self.focuser, "Description", "Unknown"),
                "position": current_pos,
                "is_moving": self.focuser.IsMoving,
                "step_size": getattr(self.focuser, "StepSize", None),
                "limits": limits,
                "position_safe": is_safe,
                "safety_status": safety_status,
            }

        return self.info
    
    
    def get_focuser_info(self, refresh: bool = False) -> Dict[str, Any]:
        """Return cached info unless refresh=True."""
        if refresh or self.info is None:
            return self.refresh_info(force=True)
        return self.info
    
    def get_limits(self) -> Dict[str, Union[int, str]]:
        if not self.is_connected():
            return {"error": "not connected"}
        try:
            max_step = self.focuser.MaxStep
            return {"min": 0, "max": max_step}
        except Exception as e:
            return {"error": f"Failed to get focuser limits: {e}"}
        
    
    def check_position_safety(self, target_position) -> Tuple[bool, str]:
        limits = self.get_limits()
        if "error" in limits:
            return False, limits["error"]
        
        try:
            target_position = int(target_position)
        except Exception as e:
            return False, f"Position must be an integer value"
        
        try:
            min_pos, max_pos = limits["min"], limits["max"]
            if min_pos <= target_position <= max_pos:
                return True, "Position is safe"
            else:
                return False, f"Position outside limits: ({min_pos}-{max_pos})"
        except Exception as e:
            return False, f"Position check error: {e}"
        
    def disconnect(self):
        if self.focuser:
            try:
                self.focuser.Connected = False
                self.focuser.Disconnect()
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Error while disconnecting focuser: {e}")
        self.connected = False
        self.info = None
        self.position = None
        self.limits = None
    
    def set_position_from_filter(self, filter_code):
               
        if not self.is_connected():
            logger.error("Cannot set position - focuser not connected")
            return False
        
        if not self.config or 'focus_positions' not in self.config:
            logger.error("No focus_positions found in config")
            return False
        
        focus_positions = self.config.get("focus_positions", {})
        lookup = {k.lower(): v for k, v in focus_positions.items()}
        target_pos = lookup.get(filter_code.lower())
        
        if target_pos is None:
            logger.error(f"No target position defined for filter '{filter_code}'")       
            return False
        
        logger.info(f"Setting focuser for filter '{filter_code}' to position {target_pos}")
        return self.move_to_position(target_pos)
        
    