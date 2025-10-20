import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from astroquery.mast import Catalogs
    ASTRO_AVAILABLE = True
except ImportError:
    ASTRO_AVAILABLE = False
# Set up logging    
logger = logging.getLogger(__name__)


@dataclass
class TargetInfo:
    tic_id: str
    ra_j2000_hours: float
    dec_j2000_deg: float
    gaia_g_mag: float
    gaia_source_id: Optional[str] = None
    tess_mag: Optional[float] = None
    object_type: Optional[str] = None
    proper_motion_ra: Optional[float] = None
    proper_motion_dec: Optional[float] = None
    magnitude_source: Optional[str] = None  # Track where G mag came from
    
class TargetResolutionError(Exception):
    pass
# Set up target resolver class
class TICTargetResolver:
    
    def __init__(self, config_loader=None):
        if not ASTRO_AVAILABLE:
            raise TargetResolutionError(f"Required astronomy packages not available. Please install.")  # Ensure astroquery installed
        
        # Default config values (fallback only)
        default_config = {
            'gaia_magnitude': {
                'default_fallback': 12.5,
                'tmag_to_gmag_offset': 0.4,
                'use_tmag_conversion': True
            }
        }
        
        if config_loader:
            try:
                exposures_config = config_loader.get_config('exposures')    # from exposures.yaml
                target_config = exposures_config.get('target_resolution', {})
                
                # Start with defaults and update if config is valid
                self.config = default_config.copy()
                if target_config and isinstance(target_config, dict):
                    if 'gaia_magnitude' in target_config and isinstance(target_config['gaia_magnitude'], dict):
                        self.config['gaia_magnitude'].update(target_config['gaia_magnitude'])
                        logger.debug("Loaded target resolution config from exposures.yaml")
                    else:
                        logger.debug("No gaia_magnitude config found, using defaults and tic lookup")
                else:
                    logger.debug("No target_resolution config found, using defaults and tic lookup")
                    
            except Exception as e:
                logger.warning(f"Could not load target resolution config, using defaults and tic lookup: {e}")
                self.config = default_config
        else:
            self.config = default_config
        
    def resolve_tic_id(self, tic_id: str):
        '''Resolve a target based on its TIC ID'''
        logger.debug(f"Resolving TIC ID: {tic_id}")
        clean_tic = self._clean_tic_id(tic_id)      # Clean the TIC ID (remove '-' etc for lookup)
        
        try:
            tic_data = self._query_tic_catalog(clean_tic)       # Check the catalog for the TIC ID
            target_info = self._build_target_info(clean_tic, tic_data)  # Return the target info and log
            
            logger.info(f"Successfully resolved {tic_id}: RA={target_info.ra_j2000_hours:.6f} h ({target_info.ra_j2000_hours*15.0:.6f}°), "
                       f"Dec={target_info.dec_j2000_deg:.6f}°, G={target_info.gaia_g_mag:.2f} "
                       f"(from {target_info.magnitude_source})")
            return target_info
            
        except Exception as e:
            logger.error(f"Failed to resolve {tic_id}: {e}")
            raise TargetResolutionError(f"Cannot resolve TIC ID {tic_id}: {e}")
        
    def _clean_tic_id(self, tic_id: str):
        '''Clean the TIC ID'''
        tic_id = str(tic_id).strip()
        
        if tic_id.upper().startswith('TIC'):
            tic_id = tic_id[3:].strip()
        
        clean_id = "".join(c for c in tic_id if c.isdigit())
        
        if not clean_id:
            raise TargetResolutionError(f"Invalid TIC ID format: {tic_id}")
        
        return clean_id
    
    def _query_tic_catalog(self, tic_id: str):
        '''Check the TIC catalog for the TIC ID and get info (coords, Gaia mag, TESS mag, etc)'''
        logger.debug(f"Querying TIC catalog for ID: {tic_id}")
        
        try:
            # Query the catalog
            tic_table = Catalogs.query_criteria(
                catalog='Tic',
                ID=int(tic_id)
            )
            
            if len(tic_table) == 0:
                raise TargetResolutionError(f"TIC ID {tic_id} not found in catalog")
            
            tic_row = tic_table[0]
            # Get the info from the data
            tic_data = {
                'tic_id': tic_id,
                'ra_deg': float(tic_row.get('ra', 0)),
                'dec_deg': float(tic_row.get('dec', 0)),
                'tess_mag': float(tic_row.get('Tmag', 99)) if tic_row.get('Tmag') else None,
                'gaia_g_mag': float(tic_row.get('GAIAmag', 99)) if tic_row.get('GAIAmag') else None,
                'gaia_id': str(tic_row.get('GAIA', '')) if tic_row.get('GAIA') else None,
                'object_type': str(tic_row.get('objType', '')) if tic_row.get('objType') else None,
                'pm_ra': float(tic_row.get('pmRA', 0)) if tic_row.get('pmRA') else None,
                'pm_dec': float(tic_row.get('pmDEC', 0)) if tic_row.get('pmDEC') else None
            }
            
            logger.debug(f"TIC query successful: RA={tic_data['ra_deg']:.6f}°, Dec={tic_data['dec_deg']:.6f}°")
            
            return tic_data
        
        except Exception as e:
            raise TargetResolutionError(f"TIC catalog query failed: {e}")
            
    def _build_target_info(self, tic_id: str, tic_data: Dict[str, Any]):
        # Convert RA from degrees to hours
        ra_hours = tic_data['ra_deg'] / 15.0
        
        # Determine Gaia G magnitude with fallback hierarchy
        gaia_g_mag, mag_source = self._get_gaia_magnitude(tic_data)
        
        return TargetInfo(
            tic_id=f"TIC-{tic_id}",
            ra_j2000_hours=ra_hours,
            dec_j2000_deg=tic_data['dec_deg'],
            gaia_g_mag=gaia_g_mag,
            gaia_source_id=tic_data.get('gaia_id'),
            tess_mag=tic_data.get('tess_mag'),
            object_type=tic_data.get('object_type'),
            proper_motion_ra=tic_data.get('pm_ra'),
            proper_motion_dec=tic_data.get('pm_dec'),
            magnitude_source=mag_source
        )
    
    def _get_gaia_magnitude(self, tic_data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Get Gaia G magnitude using fallback hierarchy:
        1. Direct GAIAmag from TIC
        2. Convert from Tmag if available
        3. Use configured default
        """
        
        # First choice: Direct Gaia magnitude from TIC
        if tic_data.get('gaia_g_mag') is not None and tic_data['gaia_g_mag'] < 50:
            logger.debug(f"Using direct GAIAmag from TIC: {tic_data['gaia_g_mag']:.2f}")
            return tic_data['gaia_g_mag'], "TIC-GAIAmag"
        
        # Second choice: Convert from TESS magnitude
        if (self.config['gaia_magnitude']['use_tmag_conversion'] and 
            tic_data.get('tess_mag') is not None and 
            tic_data['tess_mag'] < 50):
            
            converted_g = tic_data['tess_mag'] + self.config['gaia_magnitude']['tmag_to_gmag_offset']
            logger.debug(f"Converting Tmag {tic_data['tess_mag']:.2f} to Gmag {converted_g:.2f}")
            logger.warning(f"Using converted magnitude from Tmag for TIC-{tic_data['tic_id']}: "
                          f"G≈{converted_g:.2f} (T+{self.config['gaia_magnitude']['tmag_to_gmag_offset']})")
            return converted_g, "Tmag-converted"
        
        # Last resort: Use default
        default_g = self.config['gaia_magnitude']['default_fallback']
        logger.warning(f"No reliable magnitude found for TIC-{tic_data['tic_id']}, using default G={default_g}")
        return default_g, "default-fallback"
        
    def create_target_json(self, target_info: TargetInfo):
        now = datetime.now()
        
        return {
            "tic_id": target_info.tic_id,
            "ra_j2000_hours": target_info.ra_j2000_hours,
            "dec_j2000_deg": target_info.dec_j2000_deg,
            "gaia_g_mag": target_info.gaia_g_mag,
            "magnitude_source": target_info.magnitude_source,
            "session_id": now.strftime("%Y%m%d_%H%M%S"),
            "timestamp": now.isoformat(),
            "gaia_source_id": target_info.gaia_source_id,
            "tess_mag": target_info.tess_mag,
            "object_type": target_info.object_type
        }
    

def resolve_target(tic_id: str, config_loader=None):
    resolver = TICTargetResolver(config_loader)
    return resolver.resolve_tic_id(tic_id)