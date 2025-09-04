import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from astroquery.mast import Catalogs
    from astroquery.gaia import Gaia
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    ASTRO_AVAILABLE = True
except ImportError:
    ASTRO_AVAILABLE = False
    
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
    
class TargetResolutionError(Exception):
    pass

class TICTargetResolver:
    
    def __init__(self):
        if not ASTRO_AVAILABLE:
            raise TargetResolutionError(f"Required astronomy packages not available. Please install.")
        
        Gaia.MAIN_GAIA_TABLE = 'gaiadr3.gaia_source'
        Gaia.ROW_LIMIT = 50
        
    def resolve_tic_id(self, tic_id: str):
        logger.debug(f"Checking against TIC catalog: {tic_id}")
        clean_tic = self._clean_tic_id(tic_id)
        
        try:
            tic_data = self._query_tic_catalog(clean_tic)
            gaia_data = self._cross_match_gaia(tic_data)
            target_info = self._build_target_info(clean_tic, tic_data, gaia_data)
            logger.info(f"Successfully resolved {tic_id}: RA={target_info.ra_j2000_hours:.6f} h, "
                        f"Dec={target_info.dec_j2000_deg:.6f}°, G={target_info.gaia_g_mag:.2f}")
            return target_info
        except Exception as e:
            logger.error(f"Failed to resolve {tic_id}: {e}")
            raise TargetResolutionError(f"Cannot resolve TIC ID {tic_id}: {e}")
        
    def _clean_tic_id(self, tic_id: str):
        tic_id = str(tic_id).strip()
        
        if tic_id.upper().startswith('TIC'):
            tic_id = tic_id[3:].strip()
        
        clean_id = "".join(c for c in tic_id if c.isdigit())
        
        if not clean_id:
            raise TargetResolutionError(f"Invalid TIC ID format: {tic_id}")
        
        return clean_id
    
    def _query_tic_catalog(self, tic_id: str):
        logger.debug(f"Querying TIC catalog for ID: {tic_id}")
        
        try:
            tic_table = Catalogs.query_criteria(
                catalog='Tic',
                ID=int(tic_id)
            )
            
            if len(tic_table) == 0:
                raise TargetResolutionError(f"TIC ID {tic_id} not found in catalog")
            
            tic_row = tic_table[0]
            
            tic_data = {
                'tic_id': tic_id,
                'ra_deg': float(tic_row.get('ra', 0)),
                'dec_deg': float(tic_row.get('dec', 0)),
                'tess_mag': float(tic_row.get('Tmag', 99)) if tic_row.get('Tmag') else None,
                'gaia_id': str(tic_row.get('GAIA', '')) if tic_row.get('GAIA') else None,
                'object_type': str(tic_row.get('objType', '')) if tic_row.get('objType') else None,
                'pm_ra': float(tic_row.get('pmRA', 0)) if tic_row.get('pmRA') else None,
                'pm_dec': float(tic_row.get('pmDEC', 0)) if tic_row.get('pmDEC') else None
            }
            logger.debug(f"TIC query successful: RA={tic_data['ra_deg']:.6f}°, Dec={tic_data['dec_deg']:.6f}°")
            
            return tic_data
        
        except Exception as e:
            raise TargetResolutionError(f"TIC catalog query failed: {e}")
        
        
    def _cross_match_gaia(self, tic_data: Dict[str, Any]):
        logger.debug("Cross-matching with Gaia catalog")
        
        try:
            coord = SkyCoord(
                ra=tic_data['ra_deg'] * u.degree,
                dec=tic_data['dec_deg'] * u.degree,
                frame='icrs'
            )
            
            gaia_table = Gaia.cone_search_async(
                coordinate=coord, 
                radius=5 * u.arcsec
            ).get_results()
            
            if len(gaia_table) == 0:
                logger.warning(f"No Gaia sources found near TIC position")
                return {
                    'gaia_g_mag': 15.0,
                    'gaia_source_id': None
                }
            gaia_table.sort('phot_g_mean_mag')
            gaia_row = gaia_table[0]
            
            gaia_data = {
                'gaia_g_mag': float(gaia_row['phot_g_mean_mag']),
                'gaia_source_id': str(gaia_row['source_id']),
                'gaia_ra_deg': float(gaia_row['ra']),
                'gaia_dec_deg': float(gaia_row['dec'])
            }
            logger.debug(f"Gaia cross-match successful: G={gaia_data['gaia_g_mag']:.2f}")
            return gaia_data
        
        except Exception as e:
            logger.warning(f"Gaia cross-match failed: {e}")
            return {
                'gaia_g_mag': 15.0,
                'gaia_source_id': None
            }
            
    def _build_target_info(self, tic_id: str, tic_data: Dict[str, Any],
                           gaia_data: Dict[str, Any]):
        coord_diff = ((gaia_data['gaia_ra_deg'] - tic_data['ra_deg']) ** 2 +
                      (gaia_data['gaia_dec_deg'] - tic_data['dec_deg']) ** 2) ** 0.5
        
        if coord_diff < 2.0 / 3600.0:
            ra_deg = gaia_data['gaia_ra_deg']
            dec_deg = gaia_data['gaia_dec_deg']
            logger.debug(f"Using Gaia coordinates (close match)")
            
        else:
            ra_deg = tic_data['ra_deg']
            dec_deg = tic_data['dec_deg']
            
        ra_hours = ra_deg / 15.0
        
        return TargetInfo(
            tic_id=f"TIC-{tic_id}",
            ra_j2000_hours=ra_hours,
            dec_j2000_deg=dec_deg,
            gaia_g_mag=gaia_data.get('gaia_g_mag'),
            gaia_source_id=gaia_data.get('gaia_source_id'),
            tess_mag=tic_data.get('tess_mag'),
            object_type=tic_data.get('object_type'),
            proper_motion_ra=tic_data.get('pm_ra'),
            proper_motion_dec=tic_data.get('pm_dec')
        )
        
    def create_target_json(self, target_info: TargetInfo):
        
        now = datetime.now()
        
        return {
            "tic_id": target_info.tic_id,
            "ra_j2000_hours": target_info.ra_j2000_hours,
            "dec_j2000_deg": target_info.dec_j2000_deg,
            "gaia_g_mag": target_info.gaia_g_mag,
            "session_id": now.strftime("%Y%m%d_%H%M%S"),
            "timestamp": now.isoformat(),
            "gaia_source_id":target_info.gaia_source_id ,
            "tess_mag": target_info.tess_mag,
            "object_type": target_info.object_type
        }
    

def resolve_target(tic_id: str):
    resolver = TICTargetResolver()
    return resolver.resolve_tic_id(tic_id)

    