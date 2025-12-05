import sys
import logging
from rich.logging import RichHandler
import argparse
from pathlib import Path
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from autopho.config.loader import ConfigLoader, ConfigurationError
from autopho.targets.resolver import TICTargetResolver, TargetResolutionError, TargetInfo
from autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver, AlpacaTelescopeError
from autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver, AlpacaCoverError
from autopho.devices.drivers.alpaca_filterwheel import AlpacaFilterWheelDriver, AlpacaFilterWheelError
from autopho.devices.camera import CameraManager, CameraError
from autopho.targets.observability import ObservabilityChecker, ObservabilityError
from autopho.platesolving.corrector import PlatesolveCorrector, PlatesolveCorrectorError
from autopho.imaging.session import ImagingSession, ImagingSessionError

def setup_logging(log_level: str = "INFO"):
    """Setup logging with Rich handler for better console output"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(rich_tracebacks=True,
                        markup=True, 
                        show_path=True
                        )
        ]
    )

class TelescopeMirror:
    """Handles mirroring coordinates from another telescope via JSON file"""
    
    def __init__(self, mirror_file: str):
        self.mirror_file = Path(mirror_file)
        self.last_timestamp = None
        self.last_coordinates = None
        
    def check_for_new_target(self) -> Optional[Dict[str, Any]]:
        """Check if there's a new target from the mirrored telescope"""
        try:
            if not self.mirror_file.exists():
                return None
                
            with open(self.mirror_file, 'r') as f:
                data = json.load(f)
            
            latest_move = data.get('latest_move')
            if not latest_move:
                return None
                
            timestamp_str = latest_move.get('timestamp')
            if not timestamp_str:
                return None
                
            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # Check if this is a new target
            if self.last_timestamp is None or timestamp > self.last_timestamp:
                ra_deg = latest_move.get('ra_deg')
                dec_deg = latest_move.get('dec_deg')
                
                if ra_deg is not None and dec_deg is not None:
                    # Convert degrees to hours for RA (our system uses hours)
                    ra_hours = ra_deg / 15.0
                    
                    new_target = {
                        'timestamp': timestamp,
                        'ra_hours': ra_hours,
                        'dec_deg': dec_deg,
                        'ra_deg': ra_deg,  # Keep original for logging
                        'source': 'mirrored_telescope'
                    }
                    
                    self.last_timestamp = timestamp
                    self.last_coordinates = (ra_hours, dec_deg)
                    return new_target
                    
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error reading mirror file: {e}")
            
        return None
    
    def get_current_target(self) -> Optional[Dict[str, Any]]:
        """Get the current target info without checking for updates"""
        if self.last_coordinates:
            return {
                'ra_hours': self.last_coordinates[0],
                'dec_deg': self.last_coordinates[1],
                'source': 'mirrored_telescope'
            }
        return None

class SpectroscopySession:
    """Extended session class for spectroscopy with multi-target support"""
    
    def __init__(self, camera_manager, corrector, config_loader, 
                 telescope_driver, mirror_file: str = None,
                 filter_code: str = 'C', ignore_twilight: bool = False):
        
        self.camera_manager = camera_manager
        self.corrector = corrector
        self.config_loader = config_loader
        self.telescope_driver = telescope_driver
        self.filter_code = filter_code
        self.ignore_twilight = ignore_twilight
        
        # Multi-target and mirroring support
        self.mirror = TelescopeMirror(mirror_file) if mirror_file else None
        self.current_target = None
        self.current_session = None
        self.target_sessions = {}  # Track sessions per target
        
        # Initialize guide camera
        self.guide_camera = None
        if camera_manager:
            self.guide_camera = camera_manager.get_guide_camera()
            if not self.guide_camera:
                raise ImagingSessionError("Guide camera not found - required for spectroscopy")
                
    def start_spectroscopy_monitoring(self, poll_interval: float = 10.0):
        """Main loop for spectroscopy - monitor for new targets and manage sessions"""
        logger = logging.getLogger(__name__)
        
        logger.info("="*75)
        logger.info(" "*25+"STARTING SPECTROSCOPY MODE")
        logger.info("="*75)
        
        if self.mirror:
            logger.info(f"Monitoring mirror file: {self.mirror.mirror_file}")
        logger.info(f"Using guide camera: {self.guide_camera.name if self.guide_camera else 'None'}")
        logger.info(f"Poll interval: {poll_interval} seconds")
        
        session_start = time.time()
        
        try:
            while True:
                try:
                    # Check for new target from mirrored telescope
                    if self.mirror:
                        new_target = self.mirror.check_for_new_target()
                        if new_target:
                            logger.info("="*60)
                            logger.info(" "*20+"NEW TARGET DETECTED")
                            logger.info("="*60)
                            logger.info(f"Timestamp: {new_target['timestamp']}")
                            logger.info(f"Coordinates: RA={new_target['ra_hours']:.6f} h, "
                                       f"Dec={new_target['dec_deg']:.6f}°")
                            
                            # Stop current session if running
                            if self.current_session:
                                logger.info("Stopping current spectroscopy session...")
                                self._stop_current_session()
                            
                            # Start new session for this target
                            if self._start_new_target_session(new_target):
                                logger.info("Successfully started new target session")
                            else:
                                logger.error("Failed to start new target session")
                    
                    # Monitor current session health
                    if self.current_session:
                        # Could add session health checks here
                        pass
                    
                    # Check for termination conditions
                    elapsed_hours = (time.time() - session_start) / 3600
                    if elapsed_hours > 12:  # Max 12 hour sessions
                        logger.info("Maximum session duration reached")
                        break
                    
                    time.sleep(poll_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Spectroscopy monitoring interrupted by user")
                    break
                except Exception as e:
                    logger.error(f"Error in spectroscopy monitoring loop: {e}")
                    time.sleep(poll_interval)  # Continue monitoring despite errors
                    
        finally:
            if self.current_session:
                self._stop_current_session()
            logger.info("Spectroscopy monitoring ended")
            
    def _start_new_target_session(self, target_data: Dict[str, Any]) -> bool:
        """Start a new imaging session for the given target"""
        logger = logging.getLogger(__name__)
        
        try:
            # Create TargetInfo from coordinates
            target_info = TargetInfo(
                tic_id=f"SPECTRO-{target_data['timestamp'].strftime('%Y%m%d_%H%M%S')}",
                ra_j2000_hours=target_data['ra_hours'],
                dec_j2000_deg=target_data['dec_deg'],
                gaia_g_mag=12.0,  # Default for exposure calculation
                magnitude_source="spectro-default"
            )
            
            # Slew telescope to new target
            logger.info("Slewing to new target coordinates...")
            if not self.telescope_driver.slew_to_coordinates(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg
            ):
                logger.error("Failed to slew to target")
                return False
                
            logger.info("Telescope positioned at target coordinates")
            
            # Create new imaging session using guide camera
            # We'll modify ImagingSession to work with guide camera
            session = SpectroscopyImagingSession(
                camera_manager=self.camera_manager,
                corrector=self.corrector,
                config_loader=self.config_loader,
                target_info=target_info,
                filter_code=self.filter_code,
                ignore_twilight=self.ignore_twilight,
                use_guide_camera=True  # New parameter
            )
            
            # Start the session in a separate thread or async manner
            # For now, we'll store it and assume it runs
            self.current_target = target_data
            self.current_session = session
            self.target_sessions[target_info.tic_id] = session
            
            logger.info(f"Started spectroscopy session for target: {target_info.tic_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start new target session: {e}")
            return False
    
    def _stop_current_session(self):
        """Stop the current imaging session"""
        if self.current_session:
            # Add session termination logic here
            # For now, just clear references
            self.current_session = None
            self.current_target = None

class SpectroscopyImagingSession(ImagingSession):
    """Extended ImagingSession for spectroscopy using guide camera"""
    
    def __init__(self, camera_manager, corrector, config_loader, target_info, 
                 filter_code: str, ignore_twilight: bool = False, 
                 exposure_override: Optional[float] = None, use_guide_camera: bool = True):
        
        # Initialize parent class
        super().__init__(camera_manager, corrector, config_loader, target_info, 
                        filter_code, ignore_twilight, exposure_override)
        
        logger = logging.getLogger(__name__)
        # Override camera selection for spectroscopy
        if use_guide_camera and camera_manager:
            self.main_camera = camera_manager.get_guide_camera()
            if not self.main_camera:
                raise ImagingSessionError("Guide camera not found for spectroscopy")
            
            if not self.main_camera.connected:
                if not self.main_camera.connect():
                    raise ImagingSessionError("Failed to connect to guide camera")
        
        # Modify acquisition settings for spectroscopy/fiber centering
        if hasattr(self, 'acquisition_config'):
            # Use more aggressive acquisition for fiber centering
            self.acquisition_config.update({
                'max_total_offset_arcsec': 1.0,  # Tighter tolerance for fiber
                'max_attempts': 30,  # More attempts for precision
                'correction_interval': 1  # Check every frame during acquisition
            })
            logger.debug("Updated acquisition config for spectroscopy fiber centering")
        
        # Note: Still uses same acquisition -> science phase workflow
        # Platesolve corrections applied (without rotator component)
        logger.debug(f"Spectroscopy session: acquisition enabled={self.acquisition_enabled}")
        logger.debug(f"Using camera: {self.main_camera.name if self.main_camera else 'None'}")

def main():
    parser = argparse.ArgumentParser(
        description="T2 Automated Spectroscopy"
    )
    
    parser.add_argument(
        "target_mode",
        nargs='?',
        choices=['tic', 'coords', 'mirror'],
        help="Target mode: 'tic' for TIC ID, 'coords' for manual coordinates, 'mirror' for telescope mirroring"
    )
    
    parser.add_argument(
        "target_value",
        nargs='?', 
        help="Target value: TIC ID (e.g. TIC-123456789), coordinates ('RA_HOURS DEC_DEGREES'), or mirror file path"
    )
    
    parser.add_argument(
        "--filter",
        default='C',
        choices=["C", "B", "G", "R", "L", "I", "H", "c", "b", "g", "r", "l", "i", "h"],
        help="Filter selection (default: C)"  
    )
    
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory path (default: config)"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate observation without hardware interaction"
    )
    
    parser.add_argument(
        "--ignore-twilight",
        action="store_true",
        help="Ignore twilight conditions for daytime testing"
    )
    
    parser.add_argument(
        '--duration', 
        type=float, 
        help="Session duration in hours (for single target mode)"
    )
    
    parser.add_argument(
        '--exposure-time', 
        type=float, 
        help="Override calculated exposure time (seconds)"
    )
    
    parser.add_argument(
        '--poll-interval', 
        type=float,
        default=10.0,
        help="Polling interval for mirror mode (seconds, default: 10)"
    )
    
    parser.add_argument(
        '--no-park',
        action='store_true',
        help="Skip parking telescope at end of session"
    )
    
    args = parser.parse_args()
    
    if not args.target_mode:
        parser.error("Must specify target mode: tic, coords, or mirror")
    
    if args.target_mode in ['tic', 'coords'] and not args.target_value:
        parser.error(f"Target mode '{args.target_mode}' requires a target value")
    
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Suppress noisy loggers
    logging.getLogger('astroquery').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    
    logger.info("="*75)
    logger.info(" "*27+"AUTOMATED SPECTROSCOPY")
    logger.info("="*75)
    
    # Initialize hardware variables
    telescope_driver = None
    cover_driver = None
    filter_driver = None
    camera_manager = None
    corrector = None
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()
        logger.info('Configuration loaded successfully')
        
        # Initialize cameras (discover both main and guide)
        camera_manager = None
        if not args.dry_run:
            logger.info('Discovering cameras...')
            camera_manager = CameraManager()
            camera_configs = config_loader.get_camera_configs()
            
            if camera_manager.discover_cameras(camera_configs):
                logger.info('Camera discovery successful:')
                for camera_status in camera_manager.list_all_cameras():
                    logger.info(f"{camera_status['role'].upper()} camera: {camera_status['name']} "
                                f"(ID: {camera_status['device_id']})")
                
                # Verify guide camera is available
                guide_camera = camera_manager.get_guide_camera()
                if not guide_camera:
                    logger.error('Guide camera not found - required for spectroscopy')
                    return 1
                    
            else:
                logger.error('Camera discovery failed')
                return 1
        
        # Initialize telescope
        if not args.dry_run:
            logger.info('Connecting to telescope...')
            telescope_driver = AlpacaTelescopeDriver()
            telescope_config = config_loader.get_telescope_config()
            
            if not telescope_driver.connect(telescope_config):
                logger.error('Failed to connect to telescope')
                return 1
            
            tel_info = telescope_driver.get_telescope_info()
            logger.info(f"Connected to: {tel_info.get('name', 'Unknown telescope')}")
            logger.info(f"Current position: RA={tel_info.get('ra_hours', 0):.6f} h, "
                        f"Dec={tel_info.get('dec_degrees', 0):.6f}°")
        
        # Initialize other hardware (cover, filter wheel) - no rotator for spectroscopy
        if not args.dry_run:
            # Cover
            cover_driver = None
            logger.info("Connecting to cover...")
            try:
                cover_driver = AlpacaCoverDriver()
                cover_config = config_loader.get_cover_config()
                if cover_config and cover_driver.connect(cover_config):
                    cover_info = cover_driver.get_cover_info()
                    logger.info(f"Connected to: {cover_info.get('name', 'Unknown cover')} - "
                               f"State: {cover_info.get('cover_state', 'Unknown')}")
                else:
                    logger.warning("Failed to connect to cover - continuing without")
                    cover_driver = None
            except AlpacaCoverError as e:
                logger.warning(f"Cover connection failed: {e} - continuing without")
                cover_driver = None
            
            # Filter wheel
            filter_driver = None
            logger.info("Connecting to filter wheel...")
            try:
                filter_driver = AlpacaFilterWheelDriver()
                filter_config = config_loader.get_filter_wheel_config()
                
                if filter_config and filter_driver.connect(filter_config):
                    filter_info = filter_driver.get_filter_info()
                    logger.info(f"Connected to filter wheel: {filter_info.get('total_filters', 0)} filters")
                    logger.info(f"Current filter: {filter_info.get('filter_name', 'Unknown')}")
                    
                    if filter_driver.change_filter(args.filter.upper()):
                        logger.info(f"Filter set to: {args.filter.upper()}")
                    else:
                        logger.warning(f"Failed to change to filter {args.filter.upper()}")
                else:
                    logger.warning("Failed to connect to filter wheel")
                    filter_driver = None
            except AlpacaFilterWheelError as e:
                logger.warning(f"Filter wheel connection failed: {e}")
                filter_driver = None
            
            # Turn on telescope motor
            logger.info('Turning telescope motor on...') 
            if not telescope_driver.motor_on():
                logger.error('Failed to turn telescope motor on')
                return 1
            
            # Initialize platesolve corrector (no rotator for spectroscopy)
            logger.info("Initializing platesolve corrector...")
            try:
                corrector = PlatesolveCorrector(telescope_driver, config_loader, rotator_driver=None)
                logger.info("Platesolve corrector initialized for spectroscopy")
            except PlatesolveCorrectorError as e:
                logger.warning(f"Corrector initialization failed: {e}")
                corrector = None
        
        # Handle different target modes
        if args.target_mode == 'mirror':
            # Telescope mirroring mode
            mirror_file = args.target_value or "mirror_telescope.json"  # Default file
            logger.info(f"Starting telescope mirroring mode")
            logger.info(f"Mirror file: {mirror_file}")
            
            if not args.dry_run:
                # Open cover once
                if cover_driver:
                    logger.info("Opening cover...")
                    if not cover_driver.open_cover():
                        logger.error("Failed to open cover")
                        return 1
                    logger.info("Cover opened")
                
                # Start spectroscopy session manager
                spectro_session = SpectroscopySession(
                    camera_manager=camera_manager,
                    corrector=corrector,
                    config_loader=config_loader,
                    telescope_driver=telescope_driver,
                    mirror_file=mirror_file,
                    filter_code=args.filter.upper(),
                    ignore_twilight=args.ignore_twilight
                )
                
                spectro_session.start_spectroscopy_monitoring(args.poll_interval)
            else:
                logger.info("DRY RUN: Would monitor mirror file and manage sessions")
            
        else:
            # Single target mode (tic or coords)
            target_info = None
            
            if args.target_mode == 'tic':
                logger.info(f"Resolving TIC target: {args.target_value}")
                target_resolver = TICTargetResolver(config_loader)
                target_info = target_resolver.resolve_tic_id(args.target_value)
                
            elif args.target_mode == 'coords':
                logger.info(f"Using manual coordinates: {args.target_value}")
                try:
                    coords_parts = args.target_value.strip().split()
                    if len(coords_parts) != 2:
                        raise ValueError("Expected 'RA_HOURS DEC_DEGREES'")
                    ra_hours = float(coords_parts[0])
                    dec_deg = float(coords_parts[1])
                    
                    target_info = TargetInfo(
                        tic_id=f"SPECTRO-MANUAL-{ra_hours:.3f}h_{dec_deg:+.3f}d",
                        ra_j2000_hours=ra_hours,
                        dec_j2000_deg=dec_deg,
                        gaia_g_mag=12.0,
                        magnitude_source="manual-default"
                    )
                except (ValueError, IndexError) as e:
                    logger.error(f"Invalid coordinates: {e}")
                    return 1
            
            # Check observability
            logger.info("Checking target observability...")
            observatory_config = config_loader.get_config('observatory')
            checker = ObservabilityChecker(observatory_config)
            obs_status = checker.check_target_observability(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg,
                ignore_twilight=args.ignore_twilight
            )
            
            logger.info(f"Target altitude: {obs_status.target_altitude:.1f}°")
            logger.info(f"Observable: {obs_status.observable}")
            
            if not obs_status.observable and not args.dry_run:
                logger.error("Target is not currently observable")
                return 1
            
            # Single target spectroscopy session
            if not args.dry_run:
                # Slew to target
                logger.info("Slewing to target coordinates...")
                if not telescope_driver.slew_to_coordinates(
                    target_info.ra_j2000_hours,
                    target_info.dec_j2000_deg
                ):
                    logger.error('Failed to slew to target')
                    return 1
                
                # Open cover
                if cover_driver:
                    logger.info("Opening cover...")
                    if not cover_driver.open_cover():
                        logger.error("Failed to open cover")
                        return 1
                
                # Start imaging session with guide camera
                logger.info("Starting spectroscopy imaging session...")
                session = SpectroscopyImagingSession(
                    camera_manager=camera_manager,
                    corrector=corrector,
                    config_loader=config_loader,
                    target_info=target_info,
                    filter_code=args.filter.upper(),
                    ignore_twilight=args.ignore_twilight,
                    exposure_override=args.exposure_time,
                    use_guide_camera=True
                )
                
                # Run session
                session_success = session.start_imaging_loop(
                    duration_hours=args.duration
                )
                
                if not session_success:
                    logger.error("Spectroscopy session failed")
                    return 1
            else:
                logger.info("DRY RUN: Would run single target spectroscopy session")
        
        logger.info("="*75)
        logger.info(" "*25+"SPECTROSCOPY COMPLETE")
        logger.info("="*75)
        return 0
        
    except Exception as e:
        logger.error(f"Spectroscopy error: {e}")
        logger.debug("Full traceback", exc_info=True)
        return 1
        
    finally:
        # Cleanup
        try:
            if camera_manager:
                logger.info("Shutting down camera coolers...")
                camera_manager.shutdown_all_coolers()
            if cover_driver:
                logger.info("Closing cover...")
                cover_driver.close_cover()
            # Skip filter wheel cleanup for spectroscopy
            if telescope_driver:
                if not args.no_park:
                    logger.info("Parking telescope...")
                    telescope_driver.park()
                logger.info("Turning telescope motor off...")
                telescope_driver.motor_off()
                telescope_driver.disconnect()
                
            logger.info("="*75)
            logger.info(" "*27+"PROGRAM TERMINATED")
            logger.info("="*75)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

if __name__ == '__main__':
    sys.exit(main())