'''For Alpaca connection and operation of the covers - status, open, close, halt, get info etc'''

import time
import logging
from typing import Dict, Any

try:
    from alpaca.covercalibrator import CoverCalibrator
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
# Setup logging
logger = logging.getLogger(__name__)

class AlpacaCoverError(Exception):
    pass

# Setup main driver class
class AlpacaCoverDriver:
    def __init__(self):
        # Ensure alpyca is installed
        if not ALPACA_AVAILABLE:
            raise AlpacaCoverError("Alpaca library not available. Please install.")
        self.config = None
        
    def _connect_temp(self):
        '''Temporarily connect to the Cover'''
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
            # .Connected status is notoriously unreliable - using another attribute to confirm connection
            # If we can get the .Name, we are functionally connected to the Cover driver.
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
        # Generally not required to formally disconnect from the cover driver - will happen automatically when program ends
        return True
    
    def get_cover_state(self) -> str:
        '''Return status (open or closed or error) of the covers, based on the in-built SupportedAction "coverstatus"'''
        if not self.config:
            return 'Unknown'
        
        try:
            cover = self._connect_temp()
            status_code = cover.Action("coverstatus", "")
            # 1 (as a string) = Closed, 2 (as a string) = Open
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
        '''Open the covers, if they are not already open'''
        
        if not self.config:
            logger.error('Cannot open cover - not configured')
            return False
        try:
            # Check status - if already open, skip and return True
            current_state = self.get_cover_state()
            if current_state == "Open":
                logger.debug("Cover already open")
                return True
            # If status is in error, log error and return False
            elif current_state == "Error":
                logger.error("Cover in error state - cannot open")
                return False
            # Otherwise open the covers
            logger.debug("Opening cover...")
            cover = self._connect_temp()
            
            # Alpaca function call
            cover.OpenCover()
            
            # Max timeout from devices.yaml (not currently implemented)
            operation_timeout = self.config.get('operation_timeout', 30.0)
            # Settle/wait time from devices.yaml - time to allow the covers to open
            settle_time = self.config.get('settle_time', 15.0)
            
            logger.debug(f"Waiting {settle_time} s for cover to open")
            time.sleep(settle_time)
            
            # Check final status, if Open, log and return True, otherwise still return True but log warning to manually check
            final_state = self.get_cover_state()
            if final_state == "Open":
                logger.debug("Cover opened successfully")
                return True
            else:
                logger.warning(f"Cover operation completed but state is: {final_state}")
                logger.warning("Manual verification recommended")
                return True
            
        except Exception as e:
            # If opening fails, try again (connection can be finicky)
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
        '''Close the covers, if they are not already closed'''
        if not self.config:
            logger.error('Cannot close cover - not configured')
            return False
        try:
            # Get current status - if already closed, skip and return True
            current_state = self.get_cover_state()
            if current_state == "Closed":
                logger.info("Cover already closed")
                return True

            # Otherwise, close the covers
            logger.debug("Closing cover...")
            cover = self._connect_temp()
            
            # Alpaca function call
            cover.CloseCover()
            # Get wait time from devices.yaml
            settle_time = self.config.get('settle_time', 15.0)
            
            logger.debug(f"Waiting {settle_time} s for cover to close...")
            time.sleep(settle_time)
            
            # Check final status, if Closed, log and return True, otherwise still return True but log warning to manually check
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
        '''Stop the covers mid-open or mid-close'''
        if not self.config:
            logger.warning("Cannot halt cover - not configured")
            return False
        try:
            logger.warning("Halting cover movement...")
            cover = self._connect_temp()
            # Alpaca function call
            cover.HaltCover()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Cover halt failed: {e}")
            return False
    
    def get_cover_info(self) -> Dict[str, Any]:
        '''Get Alpaca information about the cover (name, description etc), return as dictionary'''
        if not self.config:
            return {'connected': False}
        try:
            cover = self._connect_temp()
            # Get current status (open, closed, error)
            current_state = self.get_cover_state()
            
            info = {
                'connected': True,        
                'name': cover.Name,                                         # Alpaca function call
                'description': getattr(cover, 'Description', 'Unknown'),    # Alapca function call
                'cover_state': current_state,
                'address': self.config.get('address', 'Unknown'),           # From devices.yaml
                'device_number': self.config.get('device_number', 'Unknown')# From devices.yaml
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get cover info: {e}")
            return {'connected': False, 'error': str(e)}
                               
        
            