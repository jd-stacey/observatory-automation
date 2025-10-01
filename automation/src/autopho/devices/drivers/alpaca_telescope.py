import time
import logging
from typing import Tuple, Optional, Dict, Any
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u

try:
    from alpaca.telescope import Telescope
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class AlpacaTelescopeError(Exception):
    pass

class AlpacaTelescopeDriver:
    
    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise AlpacaTelescopeError(f"Alpaca library not available. Please install.")
        
        self.telescope = None
        self.config = None
        self.connected = False
        
    def connect(self, config: Dict[str, Any]):
        try:
            self.config = config
            address = config.get('address', '127.0.0.1:11111')  
            device_number = config.get('device_number', 0)
            
            logger.info(f"Connecting to Alpaca Telescope at {address}, device {device_number}")
            
            self.telescope = Telescope(
                address=address,
                device_number=device_number
            )
            
            if not self.telescope.Connected:
                self.telescope.Connected  = True
                time.sleep(1)
                
            if self.telescope.Connected:
                telescope_name = self.telescope.Name
                logger.info(f"Successfully connected to telescope: {telescope_name}")
                self.connected = True
                return True
            else:
                logger.error(f"Failed to establish telescope connection")
                return False
                
        except Exception as e:
            logger.error(f"Telescope connection error: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        try:
            if self.telescope and self.connected:
                self.telescope.Connected = False
                logger.info("Telescope disconnected")
            self.connected = False
            return True
        
        except Exception as e:
            logger.error(f"Telescope disconnect error: {e}")
            return False
        
    def is_connected(self):
        try:
            if not self.telescope:
                return False
            
            is_hw_connected = self.telescope.Connected
            if not is_hw_connected:
                self.connected = False
            
            return is_hw_connected and self.connected
        
        except Exception as e:
            logger.error(f"Connection check error: {e}")
            return False
        
    def slew_to_coordinates(self, ra_hours: float, dec_deg: float):
        
        if not self.is_connected():
            logger.error(f"Cannot slew - telescope not connected")
            return False
        
        try:
            logger.info(f"Slewing to RA={ra_hours:.6f} h ({ra_hours*15:.6f}°), Dec={dec_deg:.6f}°")
            
            if self.telescope.AtPark and self.telescope.CanUnpark:
                logger.info("Unparking telescope...")
                self.telescope.Unpark()
                time.sleep(0.5)
                
            j2000 = SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox='J2000')
            jnow = j2000.transform_to(SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox=Time.now()).frame)
            
            
            self.telescope.SlewToCoordinatesAsync(jnow.ra.hour, jnow.dec.deg)
            
            logger.info(f"Slewing telescope...")
            while self.telescope.Slewing:
                logger.debug(f"    Telescope Slewing?: {self.telescope.Slewing}...")
                time.sleep(0.5)
                
            settle_time = self.config.get('settle_time', 2.0)
            logger.info(f"Slew complete. Settling for {settle_time} s")
            time.sleep(settle_time)
            
            return True
        except Exception as e:
            logger.error(f"Slew failed: {e}")
            return False
        
    def get_coordinates(self):
        if not self.is_connected():
            raise AlpacaTelescopeError("Cannot get coordinates - telescope not connected")
        
        try:
            ra_hours = self.telescope.RightAscension
            dec_deg = self.telescope.Declination
            
            jnow = SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox=Time.now())
            
            j2000 = jnow.transform_to(SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox='J2000').frame)
            
            return j2000.ra.hour, j2000.dec.deg
        except Exception as e:
            raise AlpacaTelescopeError(f"Failed to get coordinates: {e}")
        
    def sync_to_coordinates(self):
        '''Not sure we can even do this'''
        pass
    
    def motor_on(self):
        if not self.is_connected():
            raise AlpacaTelescopeError("Cannot turn motor on - telescope not connected")
        try:
            logger.debug('Turning telescope motor on...')
            self.telescope.Action('telescope:motoron', "")
            time.sleep(0.5)
            logger.info('Telescope motor successfully turned on')
            return True
        except Exception as e:
            raise AlpacaTelescopeError(f"Failed to turn telescope motor on: {e}")
            
        
    def motor_off(self):
        if not self.is_connected():
            raise AlpacaTelescopeError("Cannot turn motor on - telescope not connected")
        try:
            logger.debug('Turning telescope motor off...')
            self.telescope.Action('telescope:motoroff', "")
            time.sleep(0.5)
            logger.info('Telescope motor successfully turned off')
            return True
        except Exception as e:
            logger.error(f"Failed to turn telescope motor off: {e}")
            return False
    
    def is_slewing(self):
        if not self.is_connected():
            return False
        try:
            return self.telescope.Slewing
        except Exception as e:
            logger.error(f"Cannot check slewing status: {e}")
            return False
        
    def is_parked(self):
        if not self.is_connected():
            return False
        try:
            return self.telescope.AtPark
        except Exception as e:
            logger.error(f"Cannot check park status: {e}")
            return False
        
    def park(self, max_wait=60):
        if not self.is_connected():
            logger.info("Cannot park - telescope not connected")
            return False
        try:
            logger.info("Parking telescope...")
            self.telescope.Park()
            start = time.time()
            while not self.is_parked() and (time.time() - start < max_wait):
                time.sleep(0.1)
            if self.is_parked():
                logger.info("Telescope parked")
                return True                
            else:
                logger.warning("Park timed out")
                return False
        except Exception as e:
            logger.error(f"Park failed: {e}")
            return False
            
    def unpark(self):
        if not self.is_connected():
            logger.info("Cannot unpark - telescope not connected")
            return False
        try:
            logger.info("Unparking telescope...")
            self.telescope.Unpark()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Unpark failed: {e}")
            return False
            
    def abort_slew(self):
        if not self.is_connected():
            return False
        try:
            logger.warning("Aborting slew...")
            self.telescope.AbortSlew()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Abort slew failed: {e}")
            return False
        
    def apply_coordinate_correction(self, ra_offset_deg: float, dec_offset_deg: float):
        
        if not self.is_connected():
            logger.error("Cannot apply correction - telescope not connected")
            return False
        
        try:
            import math
            current_ra_hours, current_dec_deg = self.get_coordinates()
            logger.info(f"Current position: RA={current_ra_hours:.6f} h, Dec={current_dec_deg} deg")
            
            new_ra_hours = current_ra_hours + (ra_offset_deg / (15.0 * math.cos(math.radians(current_dec_deg))))
            new_dec_deg = current_dec_deg + dec_offset_deg
            
            # new_ra_hours = new_ra_hours % 24.0
            if new_ra_hours < 0:
                new_ra_hours += 24.0
            new_dec_deg = max (-90, min(90.0, new_dec_deg))
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset = (ra_offset_arcsec**2 + dec_offset_arcsec**2) ** 0.5
            
            logger.info(f"Applying correction: RA offset={ra_offset_arcsec:.2f}\", "
                        f"Dec offset={dec_offset_arcsec:.2f}\", Total={total_offset:.2f}\"")
            
            success = self.slew_to_coordinates(new_ra_hours, new_dec_deg)
            
            if success:
                logger.info("Coordinate correction applied successfully")
                
            return success
        except Exception as e:
            logger.error(f"Coordinate correction failed: {e}")
            return False
        
    def get_telescope_info(self):
        if not self.is_connected():
            return {'connected': False}
        
        try:
            info = {
                "connected": True,
                "name": self.telescope.Name,
                "description": getattr(self.telescope, 'Description', 'Unknown'),
                "ra_hours": self.telescope.RightAscension,
                "dec_degrees": self.telescope.Declination,
                "altitude": getattr(self.telescope, 'Altitude', None),
                "azimuth": getattr(self.telescope, 'Azimuth', None),
                "is_slewing": self.telescope.Slewing,
                "is_parked": self.telescope.AtPark,
                "can_park": getattr(self.telescope, 'CanPark', False),
                "can_slew": getattr(self.telescope, 'CanSlew', False),
                "can_sync": getattr(self.telescope, 'CanSync', False)
            }
            return info
        
        except Exception as e:
            logger.error(f"Failed to get telescope info: {e}")
            return {"connected": True, "error": str(e)}