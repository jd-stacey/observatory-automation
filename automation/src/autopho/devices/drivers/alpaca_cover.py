import time
import logging
from typing import Dict, Any

try:
    from alpaca.covercalibrator import CoverCalibrator
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class AlpacaCoverError(Exception):
    pass

class AlpacaCoverDriver:
    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise AlpacaCoverError("Alpaca library not available. Please install.")
        self.config = None
        
    def _connect_temp(self):
        address = self.config.get('address', '127.0.0.1:11112')
        device_number = self.config.get('device_number', 0)
        cover = CoverCalibrator(address=address, device_number=device_number)
        cover.Connect()
        time.sleep(2)
        return cover
    
    def connect(self, config: Dict[str, Any]) -> bool:
        try:
            self.config = config
            address = self.config.get('address', '127.0.0.1:11112')
            device_number = self.config.get('device_number', 0)
            
            logger.debug(f"Testing cover connection at {address}, device {device_number}")
            
            test_cover = self._connect_temp()
            
            try:
                name = test_cover.Name
                logger.debug(f"Cover connection test successful: {name}")
                return True
            except Exception as e:
                logger.error(f"Cover connection test failed: {e}")
                return False
        except Exception as e:
            logger.error(f"Cover connection error: {e}")
            return False
            
    def disconnect(self) -> bool:
        '''Placeholder if required later'''
        return True
    
    def get_cover_state(self) -> str:
        if not self.config:
            return 'Unknown'
        
        try:
            cover = self._connect_temp()
            status_code = cover.Action("coverstatus", "")
            if status_code == '1':
                return "Closed"
            elif status_code == '2':
                return "Open"
            else:
                logger.warning(f"Unknown cover status code: {status_code}")
        except Exception as e:
            logger.error(f"Failed to get cover status: {e}")
            return "Error"
            
    def open_cover(self) -> bool:
        if not self.config:
            logger.error('Cannot open cover - not configured')
            return False
        try:
            current_state = self.get_cover_state()
            if current_state == "Open":
                logger.debug("Cover already open")
                return True
            elif current_state == "Error":
                logger.error("Cover in error state - cannot open")
                return False
            
            logger.debug("Opening cover...")
            cover = self._connect_temp()
            cover.OpenCover()
            
            operation_timeout = self.config.get('operation_timeout', 30.0)
            settle_time = self.config.get('settle_time', 15.0)
            
            logger.debug(f"Waiting {settle_time} s for cover to open")
            time.sleep(settle_time)
            
            final_state = self.get_cover_state()
            if final_state == "Open":
                logger.debug("Cover opened successfully")
                return True
            else:
                logger.warning(f"Cover operation completed but state is: {final_state}")
                logger.warning("Manual verification recommended")
                return True
            
        except Exception as e:
            try:
                logger.debug("Retrying cover open...")
                cover = self._connect_temp()
                cover.OpenCover()
                time.sleep(self.config.get('settle_time', 15.0))
                logger.warning("Cover retry completed - manual verification recommended")
                return True
            except Exception as retry_e:
                logger.error(f"Cover open return failed: {retry_e}")
    
    
    def close_cover(self) -> bool:
        if not self.config:
            logger.error('Cannot close cover - not configured')
            return False
        try:
            current_state = self.get_cover_state()
            if current_state == "Closed":
                logger.info("Cover already closed")
                return True

            logger.debug("Closing cover...")
            cover = self._connect_temp()
            cover.CloseCover()
            settle_time = self.config.get('settle_time', 15.0)
            
            logger.debug(f"Waiting {settle_time} s for cover to close...")
            time.sleep(settle_time)
            
            final_state = self.get_cover_state()
            if final_state == "Closed":
                logger.info("Cover closed successfully")
                return True
            else:
                logger.warning(f"Cover operation completed but state is: {final_state}")
                logger.warning("Manual verification recommended")
                return True
        except Exception as e:
            logger.error(f"Failed to close cover: {e}")
            return False
    
    def halt_cover(self) -> bool:
        if not self.config:
            logger.warning("Cannot halt cover - not configured")
            return False
        try:
            logger.warning("Halting cover movement...")
            cover = self._connect_temp()
            cover.HaltCover()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Cover halt failed: {e}")
            return False
    def get_cover_info(self) -> Dict[str, Any]:
        if not self.config:
            return {'connected': False}
        try:
            cover = self._connect_temp()
            current_state = self.get_cover_state()
            
            info = {
                'connected': True,
                'name': cover.Name,
                'description': getattr(cover, 'Description', 'Unknown'),
                'cover_state': current_state,
                'address': self.config.get('address', 'Unknown'),
                'device_number': self.config.get('device_number', 'Unknown')
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get cover info: {e}")
            return {'connected': False, 'error': str(e)}
                               
        
            