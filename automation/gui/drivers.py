# ------------------------------------------------------------------------------
#  drivers.py  -  Thin wrappers around existing driver classes.
#
#  Rules:
#    - Always call the driver method.
#    - Each wrapper holds one driver instance and exposes simple
#      get_*/connect/disconnect/action methods for the UI to call.
#    - All methods are safe to call from a background thread.
#    - Returns plain dicts so the UI has no driver dependency.
# ------------------------------------------------------------------------------

import logging
from typing import Optional, Dict, Any

from config import DEVICE_CONFIGS

logger = logging.getLogger(__name__)

# -- Try importing driver modules -----------------------------------------------
try:
    from src.autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver, AlpacaTelescopeError
    HAS_TELESCOPE = True
except ImportError:
    HAS_TELESCOPE = False
    logger.warning("alpaca_telescope not found - telescope driver unavailable")

try:
    from src.autopho.devices.drivers.alpaca_rotator import AlpacaRotatorDriver, AlpacaRotatorError
    HAS_ROTATOR = True
except ImportError:
    HAS_ROTATOR = False
    logger.warning("alpaca_rotator not found - rotator driver unavailable")

try:
    from src.autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver, AlpacaCoverError
    HAS_COVER = True
except ImportError:
    HAS_COVER = False
    logger.warning("alpaca_cover not found - cover driver unavailable")

try:
    from src.autopho.devices.drivers.nodered_dome import DomeDriver, DomeError
    HAS_DOME = True
except ImportError:
    HAS_DOME = False
    logger.warning("nodered_dome not found - dome driver unavailable")

try:
    from src.autopho.devices.drivers.alpaca_focuser import AlpacaFocuserDriver, AlpacaFocuserError
    HAS_FOCUSER = True
except ImportError:
    HAS_FOCUSER = False
    logger.warning("alpaca_focuser not found - focuser driver unavailable")
    
# ------------------------------------------------------------------------------
#  Telescope
# ------------------------------------------------------------------------------

class TelescopeWrapper:
    """Wraps AlpacaTelescopeDriver."""

    def __init__(self):
        self._driver: Optional[Any] = None
        self._cfg = DEVICE_CONFIGS["telescope"]

    @property
    def available(self) -> bool:
        return HAS_TELESCOPE

    def connect(self) -> bool:
        if not HAS_TELESCOPE:
            logger.error("Telescope driver not available")
            return False
        try:
            self._driver = AlpacaTelescopeDriver()
            ok = self._driver.connect(self._cfg)
            if not ok:
                self._driver = None
            return ok
        except AlpacaTelescopeError as e:
            logger.error(f"Telescope connect: {e}")
            self._driver = None
            return False

    def disconnect(self):
        if self._driver:
            try:
                self._driver.disconnect()
            except Exception as e:
                logger.warning(f"Telescope disconnect: {e}")
            self._driver = None

    def is_connected(self) -> bool:
        return bool(self._driver and self._driver.is_connected())

    def get_info(self) -> Dict[str, Any]:
        """Return current telescope state as a plain dict."""
        if not self.is_connected():
            return {"connected": False}
        try:
            info = self._driver.get_telescope_info()
            # Normalise keys so cards don't depend on driver internals
            return {
                "connected":    info.get("connected", 'Unknown'),
                "ra":           info.get("ra_hours", 'Unknown'),   # decimal hours
                "dec":          info.get("dec_degrees", 'Unknown'),        # decimal degrees
                "alt":          info.get("altitude", 'Unknown'),
                "az":           info.get("azimuth", 'Unknown'),
                "parked":       info.get("is_parked", False),
                "slewing":      info.get("is_slewing", False),
                "tracking":     info.get("tracking", False),
                "motor_on":     info.get("motor_on", False),
                "name":         info.get("name", "Telescope"),
            }
        except AlpacaTelescopeError as e:
            logger.warning(f"Telescope get_info: {e}")
            return {"connected": False, "error": str(e)}

    def park(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.park(max_wait=120)
        except AlpacaTelescopeError as e:
            logger.error(f"Telescope park: {e}")
            return False

    def abort_slew(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.abort_slew()
        except AlpacaTelescopeError as e:
            logger.error(f"Telescope abort: {e}")
            return False

    def motor_on(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.motor_on()
        except AlpacaTelescopeError as e:
            logger.error(f"Telescope motor_on: {e}")
            return False

    def motor_off(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.motor_off()
        except AlpacaTelescopeError as e:
            logger.error(f"Telescope motor_off: {e}")
            return False
        
    def set_tertiary_mirror(self, port: str) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.set_tertiary_mirror(port)
        except AlpacaTelescopeError as e:
            logger.error(f"Mirror switch: {e}")
            return False


# ------------------------------------------------------------------------------
#  Rotator
# ------------------------------------------------------------------------------

class RotatorWrapper:
    """Wraps AlpacaRotatorDriver."""

    def __init__(self):
        self._driver: Optional[Any] = None
        self._cfg = DEVICE_CONFIGS["rotator"]

    @property
    def available(self) -> bool:
        return HAS_ROTATOR

    def connect(self) -> bool:
        if not HAS_ROTATOR:
            logger.error("Rotator driver not available")
            return False
        try:
            self._driver = AlpacaRotatorDriver()
            ok = self._driver.connect(self._cfg)
            if not ok:
                self._driver = None
            return ok
        except AlpacaRotatorError as e:
            logger.error(f"Rotator connect: {e}")
            self._driver = None
            return False

    def disconnect(self):
        if self._driver:
            try:
                self._driver.disconnect()
            except Exception as e:
                logger.warning(f"Rotator disconnect: {e}")
            self._driver = None

    def is_connected(self) -> bool:
        return bool(self._driver and self._driver.is_connected())

    def get_info(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {"connected": False}
        try:
            info = self._driver.get_rotator_info()
            return {
                "connected":    info.get("connected", True),
                "position_deg": info.get("position_deg"),
                "moving":       info.get("is_moving", False),
                "name":         info.get("name", "Rotator"),
            }
        except AlpacaRotatorError as e:
            logger.warning(f"Rotator get_info: {e}")
            return {"connected": True, "error": str(e)}

    def halt(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.halt()
        except AlpacaRotatorError as e:
            logger.error(f"Rotator halt: {e}")
            return False
        
    def move_to(self, position_deg: float) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.move_to_position(position_deg)
        except AlpacaRotatorError as e:
            logger.error(f"Rotator move error: {e}")
            return False
        
    def get_limits(self) -> dict:
        lim = self._cfg.get("mechanical_limits", {})
        return {"min": lim.get("min_deg", 0), "max": lim.get("max_deg", 360)}
            
    


# ------------------------------------------------------------------------------
#  Cover / Calibrator
# ------------------------------------------------------------------------------

class CoverWrapper:
    """Wraps AlpacaCoverDriver."""

    def __init__(self):
        self._driver: Optional[Any] = None
        self._cfg = DEVICE_CONFIGS["cover"]
        self._connected = False

    @property
    def available(self) -> bool:
        return HAS_COVER

    def connect(self) -> bool:
        if not HAS_COVER:
            logger.error("Cover driver not available")
            return False
        try:
            self._driver = AlpacaCoverDriver()
            ok = self._driver.connect(self._cfg)
            if not ok:
                self._driver = None
            self._connected = ok
            return ok
        except AlpacaCoverError as e:
            logger.error(f"Cover connect: {e}")
            self._driver = None
            return False

    def is_connected(self) -> bool:
        return self._connected
    
    def disconnect(self):
        if self._driver:
            try:
                self._driver.disconnect()
            except Exception as e:
                logger.warning(f"Cover disconnect: {e}")
            self._driver = None

    def is_connected(self) -> bool:
        return bool(self._driver and self._driver.is_connected())

    def get_info(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {"connected": False}
        try:
            info = self._driver.get_cover_info()
            return {
                "connected":    info.get("connected", True),
                "cover_state":  info.get("cover_state", "Unknown"),
                "name":         info.get("name", "Cover"),
            }
        except AlpacaCoverError as e:
            logger.warning(f"Cover get_info: {e}")
            return {"connected": True, "error": str(e)}

    def get_cover_state(self) -> str:
        if not self.is_connected():
            return "Unknown"
        try:
            return self._driver.get_cover_state()
        except AlpacaCoverError as e:
            logger.warning(f"Cover get_state: {e}")
            return "Error"

    def open_cover(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.open_cover()
        except AlpacaCoverError as e:
            logger.error(f"Cover open: {e}")
            return False

    def close_cover(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.close_cover()
        except AlpacaCoverError as e:
            logger.error(f"Cover close: {e}")
            return False


# ------------------------------------------------------------------------------
#  Dome
# ------------------------------------------------------------------------------

class DomeWrapper:
    """Wraps DomeDriver (Node-RED)."""

    def __init__(self):
        self._driver: Optional[Any] = None
        self._cfg = DEVICE_CONFIGS["dome"]

    @property
    def available(self) -> bool:
        return HAS_DOME

    def connect(self) -> bool:
        if not HAS_DOME:
            logger.error("Dome driver not available")
            return False
        try:
            self._driver = DomeDriver()
            ok = self._driver.connect(self._cfg)
            if not ok:
                self._driver = None
            return ok
        except DomeError as e:
            logger.error(f"Dome connect: {e}")
            self._driver = None
            return False

    def disconnect(self):
        if self._driver:
            try:
                self._driver.disconnect()
            except Exception as e:
                logger.warning(f"Dome disconnect: {e}")
            self._driver = None

    def is_connected(self) -> bool:
        return bool(self._driver and self._driver.is_connected())

    def get_info(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {"connected": False}
        try:
            info = self._driver.get_dome_info()
            return {
                "connected": info.get("connected", True),
                "left":      str(info.get("left",  "unknown")).upper(),
                "right":     str(info.get("right", "unknown")).upper(),
                "closed":    info.get("closed", False),
                "is_open":   info.get("is_open", False),
                "moving":    info.get("is_moving", False),
            }
        except DomeError as e:
            logger.warning(f"Dome get_info: {e}")
            return {"connected": True, "error": str(e)}

    def open(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.open()
        except DomeError as e:
            logger.error(f"Dome open: {e}")
            return False

    def close(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.close()
        except DomeError as e:
            logger.error(f"Dome close: {e}")
            return False

    def abort(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self._driver.abort()
        except DomeError as e:
            logger.error(f"Dome abort: {e}")
            return False

    def open_left(self) -> bool:
        if not self.is_connected(): return False
        try: return self._driver.open_left()
        except DomeError as e:
            logger.error(f"Dome open_left: {e}"); return False

    def close_left(self) -> bool:
        if not self.is_connected(): return False
        try: return self._driver.close_left()
        except DomeError as e:
            logger.error(f"Dome close_left: {e}"); return False

    def open_right(self) -> bool:
        if not self.is_connected(): return False
        try: return self._driver.open_right()
        except DomeError as e:
            logger.error(f"Dome open_right: {e}"); return False

    def close_right(self) -> bool:
        if not self.is_connected(): return False
        try: return self._driver.close_right()
        except DomeError as e:
            logger.error(f"Dome close_right: {e}"); return False

# ------------------------------------------------------------------------------
#  Focuser
# ------------------------------------------------------------------------------

class FocuserWrapper:
    
    def __init__(self):
        self._driver = None
        self._cfg = DEVICE_CONFIGS["focuser"]
        self._connected = False

    @property
    def available(self): return HAS_FOCUSER

    def connect(self) -> bool:
        if not HAS_FOCUSER:
            return False
        try:
            self._driver = AlpacaFocuserDriver()
            ok = self._driver.connect(self._cfg)
            self._connected = ok
            if not ok:
                self._driver = None
            return ok
        except AlpacaFocuserError as e:
            logger.error(f"Focuser connect: {e}")
            self._driver = None
            self._connected = False
            return False

    def disconnect(self):
        if self._driver:
            try: self._driver.disconnect()
            except Exception as e: logger.warning(f"Focuser disconnect: {e}")
            self._driver = None
        self._connected = False

    def is_connected(self) -> bool:
        if not self._driver: return False
        try: return self._driver.is_connected()
        except: return False

    def get_info(self) -> dict:
        if not self.is_connected():
            return {"connected": False}
        try:
            info = self._driver.get_focuser_info(refresh=True)
            cfg  = self._cfg
            return {
                "connected":    True,
                "position":     info.get("position"),
                "is_moving":    info.get("is_moving", False),
                "limits":       info.get("limits", {}),
                "position_safe": info.get("position_safe", True),
                "photom_positions": cfg.get("photom_positions", {}),
                "spectro_position": cfg.get("spectro_position"),
            }
        except AlpacaFocuserError as e:
            logger.warning(f"Focuser get_info: {e}")
            return {"connected": True, "error": str(e)}

    def move_to(self, position: int) -> bool:
        if not self.is_connected(): return False
        try: return self._driver.move_to_position(position)
        except AlpacaFocuserError as e:
            logger.error(f"Focuser move: {e}"); return False

    def halt(self) -> bool:
        if not self.is_connected(): return False
        try: return self._driver.halt()
        except AlpacaFocuserError as e:
            logger.error(f"Focuser halt: {e}"); return False