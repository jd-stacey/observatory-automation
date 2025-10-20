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
    
# Set up logging
logger = logging.getLogger(__name__)

class AlpacaTelescopeError(Exception):
    pass

# Set up telescope driver class
class AlpacaTelescopeDriver:
    
    def __init__(self):
        # Check if Alpyca installed
        if not ALPACA_AVAILABLE:
            raise AlpacaTelescopeError(f"Alpaca library not available. Please install.")
        
        self.telescope = None
        self.config = None
        self.connected = False
        
    def connect(self, config: Dict[str, Any]):
        '''Connect to the telescope'''
        try:
            # Config details from devices.yaml
            self.config = config
            address = config.get('address', '127.0.0.1:11111')  
            device_number = config.get('device_number', 0)
            
            logger.info(f"Connecting to Alpaca Telescope at {address}, device {device_number}")
            
            # Initialise Telescope driver from Alpaca library
            self.telescope = Telescope(
                address=address,
                device_number=device_number
            )
            
            # .Connected is reliable for the telescope
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
        '''Disconnect from the telescope'''
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
        '''Check the connected status of the telescope (.Connected is reliable here)'''
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
        '''Move the telescope to a set of target coordinates (RA in decimal HOURS, Dec in decimal degrees)
        Automatically converts J2000 coordinates to JNow coordinates (telescope uses JNow coordinate system for movements and positions)'''
        if not self.is_connected():
            logger.error(f"Cannot slew - telescope not connected")
            return False
        
        try:
            logger.info(f"Slewing to RA={ra_hours:.6f} h ({ra_hours*15:.6f}°), Dec={dec_deg:.6f}°")
            # If telescope is Parked - Unpark it via Alpaca function call
            if self.telescope.AtPark and self.telescope.CanUnpark:
                logger.info("Unparking telescope...")
                self.telescope.Unpark()     # Alpaca function call
                time.sleep(0.5)
                
            # Convert J2000 coordinates to JNow coordinates
            j2000 = SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox='J2000')
            jnow = j2000.transform_to(SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox=Time.now()).frame)
            
            # Don't initiate another move if the telescope is current slewing - wait for it to stop slewing first
            while self.telescope.Slewing:
                logger.debug(f"    Telescope is currently slewing - waiting for it to stop... {self.telescope.Slewing}...")
                time.sleep(0.5)
            
            # Start the move via Alpaca function call
            self.telescope.SlewToCoordinatesAsync(jnow.ra.hour, jnow.dec.deg)
            # Log that the scope is slewing
            logger.info(f"Slewing telescope...")
            while self.telescope.Slewing:
                logger.debug(f"    Telescope Slewing?: {self.telescope.Slewing}...")
                time.sleep(0.5)
            # Settle if necessary (time from devices.yaml)    
            settle_time = self.config.get('settle_time', 2.0)
            logger.info(f"Slew complete. Settling for {settle_time} s")
            time.sleep(settle_time)
            
            return True
        except Exception as e:
            logger.error(f"Slew failed: {e}")
            return False
        
    def get_coordinates(self):
        '''Get the current J2000 coordinates the telescope is pointing at (returns RA in decimal HOURS and Dec in decimal degrees)'''
        if not self.is_connected():
            raise AlpacaTelescopeError("Cannot get coordinates - telescope not connected")
        
        try:
            # Get RA and Dec position from Alpaca function calls (Note - these are in JNow coordinates, not J2000)
            ra_hours = self.telescope.RightAscension
            dec_deg = self.telescope.Declination
            # Convert coordinates from JNow to J2000 and return them (RA in decimal HOURS, Dec in decimal degrees)
            jnow = SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox=Time.now())
            j2000 = jnow.transform_to(SkyCoord(ra=ra_hours*u.hourangle, dec=dec_deg*u.deg, frame='fk5', equinox='J2000').frame)
            return j2000.ra.hour, j2000.dec.deg
        except Exception as e:
            raise AlpacaTelescopeError(f"Failed to get coordinates: {e}")
        
    def sync_to_coordinates(self):
        '''Not sure we can even do this - dealt with using Tracking instead'''
        pass
    
    def motor_on(self):
        '''Turn on the telescopes motors'''
        if not self.is_connected():
            raise AlpacaTelescopeError("Cannot turn motor on - telescope not connected")
        try:
            logger.debug('Turning telescope motor on...')
            # Use in-built SupportedAction to turn the motors on with brief pause for implementation
            self.telescope.Action('telescope:motoron', "")
            time.sleep(0.5)
            logger.info('Telescope motor successfully turned on')
            return True
        except Exception as e:
            raise AlpacaTelescopeError(f"Failed to turn telescope motor on: {e}")
            
        
    def motor_off(self):
        '''Turn off the telescopes motors'''
        if not self.is_connected():
            raise AlpacaTelescopeError("Cannot turn motor on - telescope not connected")
        try:
            logger.debug('Turning telescope motor off...')
            # Use in-built SupportedAction to turn the motors off with brief pause for implementation
            self.telescope.Action('telescope:motoroff', "")
            time.sleep(0.5)
            logger.info('Telescope motor successfully turned off')
            return True
        except Exception as e:
            logger.error(f"Failed to turn telescope motor off: {e}")
            return False
    
    def is_slewing(self):
        ''''Get the current slewing state of the telescope'''
        if not self.is_connected():
            return False
        try:
            return self.telescope.Slewing       # Alpaca function call
        except Exception as e:
            logger.error(f"Cannot check slewing status: {e}")
            return False
        
    def is_parked(self):
        '''Get the current Parked status of the telescope'''
        if not self.is_connected():
            return False
        try:
            return self.telescope.AtPark    # Alpaca function call
        except Exception as e:
            logger.error(f"Cannot check park status: {e}")
            return False
        
    def park(self, max_wait=60):
        '''Park the telescope to its Park position'''
        if not self.is_connected():
            logger.info("Cannot park - telescope not connected")
            return False
        try:
            logger.info("Parking telescope...")
            self.telescope.Park()   # Alpaca function call
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
        '''Take the telescope out of Park position (can sometimes prevent some telescope operations)'''
        if not self.is_connected():
            logger.info("Cannot unpark - telescope not connected")
            return False
        try:
            logger.info("Unparking telescope...")
            self.telescope.Unpark()     # Alapca function call
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Unpark failed: {e}")
            return False
            
    def abort_slew(self):
        '''Immediately stop the telescope from slewing'''
        if not self.is_connected():
            return False
        try:
            logger.warning("Aborting slew...")
            self.telescope.AbortSlew()  # Alpaca function call
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Abort slew failed: {e}")
            return False
        
    def apply_coordinate_correction(self, ra_offset_deg: float, dec_offset_deg: float):
        '''Apply coordinate corrections from the external platesolver where both RA and Dec offsets are provided in decimal degrees'''
        
        if not self.is_connected():
            logger.error("Cannot apply correction - telescope not connected")
            return False
        
        try:
            import math
            # Get the current position of the telescope (in RA Hours and Dec degrees)
            current_ra_hours, current_dec_deg = self.get_coordinates()
            logger.info(f"Current position: RA={current_ra_hours:.6f} h, Dec={current_dec_deg} deg")
            # Calculate the new position of the telescope by adding the offsets from the external platesolver (converting RA degrees to hours)
            # the external platesolver currently deals with the dec component of RA offsets so cos term not included here
            new_ra_hours = current_ra_hours + (ra_offset_deg / 15.0) #(ra_offset_deg / (15.0 * math.cos(math.radians(current_dec_deg))))
            new_dec_deg = current_dec_deg + dec_offset_deg
            
            # Confirm accuracy of new position
            if new_ra_hours < 0:
                new_ra_hours += 24.0
            new_dec_deg = max (-90, min(90.0, new_dec_deg))
            # Convert to arcsecs (just for logging and reporting purposes)
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            total_offset = (ra_offset_arcsec**2 + dec_offset_arcsec**2) ** 0.5
            
            logger.info(f"Applying correction: RA offset={ra_offset_arcsec:.2f}\", "
                        f"Dec offset={dec_offset_arcsec:.2f}\", Total={total_offset:.2f}\"")
            # Initiate the telescope slew to the new coordinates
            success = self.slew_to_coordinates(new_ra_hours, new_dec_deg)
            
            if success:
                logger.info("Coordinate correction applied successfully")
                
            return success
        except Exception as e:
            logger.error(f"Coordinate correction failed: {e}")
            return False
        
    def get_telescope_info(self):
        '''Get information about the telescope'''
        if not self.is_connected():
            return {'connected': False}
        # If connected, create and return the info dictionary
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