import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import pytz
import numpy as np

try:
    from astropy.coordinates import SkyCoord, EarthLocation, AltAz, get_sun
    from astropy.time import Time
    import astropy.units as u
    ASTRO_AVAILABLE = True
except ImportError:
    ASTRO_AVAILABLE = False
# Set up logging    
logger = logging.getLogger(__name__)


@dataclass
class ObservabilityStatus:
    observable: bool
    target_altitude: float
    target_azimuth: float
    sun_altitude: float
    sun_azimuth: float
    reasons: list
    check_time: datetime
    airmass: Optional[float] = None
    
class ObservabilityError(Exception):
    pass
# Set up observability checker class
class ObservabilityChecker:
    
    def __init__(self, observatory_config: Dict[str, Any]):
        if not ASTRO_AVAILABLE:
            raise ObservabilityError("Required astronomy packages not available: please install astropy")   # Ensure astropy installed
        self.config = observatory_config
        self.location = self._setup_location()
        
    def _setup_location(self):
        '''Get current location information from observatory.yaml'''
        try:
            lat = self.config['latitude']
            lon = self.config['longitude']
            alt = self.config.get('altitude', 0)
            
            location = EarthLocation(
                lat=lat * u.degree,
                lon=lon * u.degree,
                height=alt * u.meter
            )
            
            logger.debug(f"Observatory Location: Lat={lat:.6f}°, Lon={lon:.6f}°, Alt={alt} m")
            return location
        
        except KeyError as e:
            raise ObservabilityError(f"Missing observatory location parameter: {e}")
        except Exception as e:
            raise ObservabilityError(f"Failed to setup observatory location: {e}")
        
    def check_target_observability(self, ra_hours: float, dec_deg: float,
                                   check_time: Optional[datetime] = None, 
                                   ignore_twilight: bool = False) -> ObservabilityStatus:
        '''Check the current observability of a set of target coordinates (RA in decimal HOURS, Dec in decimal degrees)
        based on the position of the target above a minimum altitude and the position (altitude) of the Sun
        the Sun's position can be ignored via the use of ignore_twilight (usually just for daytime testing purposes)'''
        # If no time is entered, use now
        if check_time is None:
            check_time = datetime.now(timezone.utc)
        elif check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=timezone.utc)
            
        logger.debug(f"Checking observability at {check_time.isoformat()}")
        
        try:
            # Set target coordinate system
            target_coord = SkyCoord(
                ra=ra_hours * u.hour,
                dec=dec_deg * u.degree,
                frame='icrs'    # J2000
            )
            astro_time = Time(check_time)
            
            altaz_frame = AltAz(obstime=astro_time, location=self.location)
            target_altaz = target_coord.transform_to(altaz_frame)
            # Get sun position info
            sun_coord = get_sun(astro_time)
            sun_altaz = sun_coord.transform_to(altaz_frame)
            # Get target position info
            target_alt = target_altaz.alt.degree
            target_az = target_altaz.az.degree
            sun_alt = sun_altaz.alt.degree
            sun_az = sun_altaz.az.degree
            # Get airmass (just for logging purposes)
            airmass = None
            if target_alt > 0:
                zenith_angle = 90.0 - target_alt
                if zenith_angle < 80:
                    airmass = 1.0 / np.cos(np.radians(zenith_angle))
                    
            reasons = []
            observable = True
            # If target is below minimum required altitude, its not observable
            min_alt = self.config.get('min_altitude', 30.0) # from observatory.yaml
            if target_alt < min_alt:
                observable = False
                reasons.append(f"Target altitude {target_alt:.1f}° is below minimum {min_alt}°")
            # If Sun is above required twilight altitude, target is not observable (unless ignore_twilight is used)
            if not ignore_twilight:
                twilight_limit = self.config.get('twilight_altitude', -18.0)    # from observatory.yaml
                if sun_alt > twilight_limit:
                    observable = False
                    sun_condition = "day" if sun_alt > 0 else "twilight"
                    reasons.append(f"Sun altitude {sun_alt:.1f}° is above limit {twilight_limit}° ({sun_condition})")
                    
            if observable:
                reasons.append("Target is observable")
                if ignore_twilight and sun_alt > self.config.get('twilight_altitude', -18.0):
                    reasons.append("(twilight check ignored for testing)")
                
            logger.debug(f"Target: alt={target_alt:.1f}°, az={target_az:.1f}° | Sun: alt={sun_alt:.1f}°, az={sun_az:.1f}°")
            logger.debug(f"Observable: {observable}, Reasons: {reasons}")
            
            return ObservabilityStatus(
                observable=observable,
                target_altitude=target_alt,
                target_azimuth=target_az,
                sun_altitude=sun_alt,
                sun_azimuth=sun_az,
                reasons=reasons,
                check_time=check_time,
                airmass=airmass
            )
        
        except Exception as e:
            logger.error(f"Observability calculation failed: {e}")
            raise ObservabilityError(f"Failed to check observability: {e}")
        
    def get_next_observable_time(self, ra_hours: float, dec_deg: float,
                                 start_time: Optional[datetime] = None,
                                 max_hours: float = 24.0) -> Optional[datetime]:
        '''This is generally pretty rubbish - but testing determining future observability'''
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        elif start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
            
        logger.debug(f"Searching for next observable time starting {start_time.isoformat()}")
        
        check_interval_minutes = 15
        max_checks = int((max_hours * 60) / check_interval_minutes)
        
        current_time = start_time
        
        for i in range(max_checks):
            status = self.check_target_observability(ra_hours, dec_deg, current_time)
            
            if status.observable:
                logger.info(f"Target becomes observable at {current_time.isoformat()}")
                return current_time
        logger.warning(f"Target not observable within next {max_hours} hours")
        return None
    
    def get_observable_duration(self, ra_hours: float, dec_deg: float,
                                start_time: Optional[datetime] = None,
                                max_hours: float = 12.0) -> float:
        '''Check how long a target might be observable for - testing'''
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        elif start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
            
        current_status = self.check_target_observability(ra_hours, dec_deg, start_time)
        if not current_status.observable:
            return 0.0
        
        logger.debug(f"Calculating observable duration from {start_time.isoformat()}")
        
        check_interval_minutes = 10
        max_checks = int((max_hours * 60) / check_interval_minutes)
        
        from datetime import timedelta
        current_time = start_time
        
        for i in range(max_checks):
            current_time += timedelta(minutes=check_interval_minutes)
            status = self.check_target_observability(ra_hours, dec_deg, current_time)
            
            if not status.observable:
                duration_hours = i * (check_interval_minutes / 60.0)
                logger.info(f"Target observable for {duration_hours:.1f} hours")
                return duration_hours
            
        logger.info(f"Target still observable after {max_hours} hours")
        return max_hours
    
    def check_target_observability_static(observatory_config: Dict[str, Any],
                                   ra_hours: float, dec_deg: float,
                                   ignore_twilight: bool = False) -> ObservabilityStatus:
        
        checker = ObservabilityChecker(observatory_config)
        return checker.check_target_observability(ra_hours, dec_deg, ignore_twilight=ignore_twilight)