'''
Use this program to take a single image of a target, resolved by TIC ID or J2000 coordinates (or by using --current-position). 
The --exposure-time command line argument MUST be used to set exposure time (in seconds).
Binning and Gain levels are set for each camera in the config file: devices.yaml.
'''

import sys
import logging
from rich.logging import RichHandler
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from autopho.config.loader import ConfigLoader, ConfigurationError
from autopho.targets.resolver import TICTargetResolver, TargetResolutionError, TargetInfo
from autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver, AlpacaTelescopeError
from autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver, AlpacaCoverError
from autopho.devices.drivers.alpaca_filterwheel import AlpacaFilterWheelDriver, AlpacaFilterWheelError
from autopho.devices.drivers.alpaca_focuser import AlpacaFocuserDriver, AlpacaFocuserError
from autopho.devices.focus_filter_manager import FocusFilterManager, FocusFilterManagerError
from autopho.devices.camera import CameraManager, CameraError
from autopho.targets.observability import ObservabilityChecker, ObservabilityError
from autopho.imaging.fits_utils import create_fits_file
from autopho.imaging.file_manager import FileManager


def setup_logging(log_level: str, log_dir: Path, log_name: str = None):
    """Setup file and console logging for single image capture"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if log_name is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_name = f"single_{timestamp}.log"
        
    logfile = log_dir / log_name
    
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True, 
        show_path=True
    )
    
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.setLevel(numeric_level)     # set console logging level based on log_level
    
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]"
    ))
    file_handler.setLevel(logging.DEBUG)    # set file logging level to DEBUG
        
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler]
    )
    
    return logfile


def main():
    # Set up command line arguments
    parser = argparse.ArgumentParser(
        description="T2 Single Image Capture - For exposure time optimization"
    )
    parser.add_argument(
        "tic_id",
        nargs='?',
        help="TIC ID to observe (e.g. TIC-123456789 or 123456789)"
    )
    parser.add_argument(
        "--exposure-time",
        type=float,
        required=True,
        help="Exposure time in seconds"
    )
    parser.add_argument(
        "--filter",
        default='C',
        choices=["C", "B", "G", "R", "L", "I", "H", "c", "b", "g", "r", "l", "i", "h"],
        help="Filter selection: C=Clear, B=Blue, G=Green, R=Sloan-r, L=Lum, I=Sloan-i, H=H-alpha (default: C)"
    )
    parser.add_argument(
        "--coords",
        help="Manual coordinates: 'RA_DEGREES DEC_DEGREES' (overrides TIC lookup)"
    )
    parser.add_argument(
        "--ignore-twilight",
        action="store_true",
        help="Ignore twilight conditions for daytime testing"
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
        "--current-position",
        action="store_true",
        help="Capture image at telescope's current position (no slewing, skips observability checks)"
    )
    
    args = parser.parse_args()
    
    # Validation
    if args.current_position:
        # Current position mode - don't need target info
        if args.tic_id or args.coords:
            parser.error("Cannot use --current-position with tic_id or --coords")
    else:
        # Normal mode - need target
        if not args.tic_id and not args.coords:
            parser.error("Must provide either tic_id or --coords (or use --current-position)")
        if args.tic_id and args.coords:
            parser.error("Cannot use both tic_id and --coords - choose one")
    
    # Setup logging
    try:
        config_loader = ConfigLoader(args.config_dir)       # ConfigLoader from loader.py
        config_loader.load_all_configs()
        log_dir = Path(config_loader.get_config("paths")["logs"])
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        # Set up log filenames (use timestamps as differentiators)
        if args.current_position:
            log_name = f"single_{timestamp}_CURRENTPOS.log"
        elif args.tic_id:    
            log_name = f"single_{timestamp}_{args.tic_id}.log"
        elif args.coords:
            log_name = f"single_{timestamp}_MANUAL.log"
        else:
            log_name = f"single_{timestamp}.log"
    
        logfile = setup_logging(args.log_level, log_dir, log_name)
        logger = logging.getLogger(__name__)
        logger.info(f"Logging to {logfile}")
    except Exception as e:
        print(f"Logging setup error: {e}")
        return 1
    
    # Suppress verbose library logging
    logging.getLogger('astroquery').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    
    logger.info("="*75)
    logger.info(" "*25+"SINGLE IMAGE CAPTURE")
    logger.info("="*75)
    
    # initialise driver variables so finally block runs without error
    telescope_driver = None
    cover_driver = None
    filter_driver = None
    camera_manager = None
    focuser_driver = None
    
    try:
        # Load configuration files
        logger.info("Loading configuration...")
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()
        logger.info('Configuration loaded successfully')
        
        # Resolve target (unless using current position)
        if args.current_position:
            logger.info("Using telescope's current position (no target resolution)")
            # Create a generic target_info for current position - TargetInfo from resolver.py
            target_info = TargetInfo(
                tic_id="CURRENT_POSITION",
                ra_j2000_hours=0.0,  # Will be updated after telescope connection
                dec_j2000_deg=0.0,
                gaia_g_mag=12.0,
                magnitude_source="current-position"
            )
        elif args.coords:
            logger.info(f"Using manual coordinates: {args.coords}")
            try:
                coords_parts = args.coords.strip().split()
                if len(coords_parts) != 2:
                    raise ValueError("Expected 'RA_DEGREES DEC_DEGREES'")   # Ensure coords in correct format
                ra_hours = float(coords_parts[0]) / 15.0    # Convert RA in degrees to RA in HOURS
                dec_deg = float(coords_parts[1])
                # Ensure coords are valid
                if not (0 <= ra_hours < 24):
                    raise ValueError(f"RA must be 0-360 degrees, got {float(coords_parts[0])}")
                if not (-90 <= dec_deg <= 90):
                    raise ValueError(f"Dec must be -90 to +90 degrees, got {dec_deg}")
                    
                target_info = TargetInfo(           # TargetInfo from resolver.py
                    tic_id=f"MANUAL-{ra_hours:.3f}h_{dec_deg:+.3f}d",
                    ra_j2000_hours=ra_hours,
                    dec_j2000_deg=dec_deg,
                    gaia_g_mag=12.0,    # just use a default value
                    magnitude_source="manual-default"
                )
                logger.info(f"Manual target: RA={ra_hours:.6f} h ({ra_hours*15.0:.6f}°), Dec={dec_deg:.6f}°")
                
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid coordinates format '{args.coords}': {e}")
                logger.error("Use format: --coords 'RA_DEGREES DEC_DEGREES' (e.g., '123.456 -67.890')")
                return 1
        else:
            logger.info(f"Resolving target: {args.tic_id}")
            target_resolver = TICTargetResolver(config_loader)          # Set up target resolver (from resolver.py)
            target_info = target_resolver.resolve_tic_id(args.tic_id)   # Resolve target id (from resolver.py)
        
        # Check observability (skip if using current position)
        if not args.current_position:
            logger.info("Checking target observability...")
            try:
                observatory_config = config_loader.get_config('observatory')    # Observatory config from observatory.yaml
                checker = ObservabilityChecker(observatory_config)              # Set up observability checker from observability.py
                obs_status = checker.check_target_observability(                # Check target observability from observability.py
                    target_info.ra_j2000_hours,
                    target_info.dec_j2000_deg,
                    ignore_twilight=args.ignore_twilight
                )
            
                logger.info(f"Current target altitude: {obs_status.target_altitude:.1f}°")
                logger.info(f"Current sun altitude: {obs_status.sun_altitude:.1f}°")
                if obs_status.airmass:
                    logger.debug(f"Airmass: {obs_status.airmass:.2f}")      # Airmass for logging
                # Log status if not observable    
                if not obs_status.observable:
                    logger.error("Target not currently observable:")
                    for reason in obs_status.reasons:
                        logger.error(f"  {reason}")
                    logger.error("Aborting - target must be observable to capture image")
                    return 1
                
                logger.info("Target is observable - proceeding")
                    
            except ObservabilityError as e:
                logger.error(f"Observability check error: {e}")
                return 1
        else:
            logger.info("Skipping observability checks (using current position)")
            obs_status = None
        
        # Discover cameras
        logger.info('Discovering cameras...')
        camera_manager = CameraManager()                    # from camera.py
        camera_configs = config_loader.get_camera_configs() # from loader.py
        
        if camera_manager.discover_cameras(camera_configs):
            logger.info('Camera discovery successful:')
            for camera_status in camera_manager.list_all_cameras(): # from camera.py
                logger.info(f"  {camera_status['role'].upper()} camera: {camera_status['name']} "
                            f"(ID: {camera_status['device_id']})")
        else:
            logger.error('Camera discovery failed')
            return 1
        
        # Connect to main camera (disable auto-cooler initialization)
        main_camera = camera_manager.get_main_camera()  # from camera.py
        if not main_camera:
            logger.error("Main camera not found")
            return 1
        
        # Manually connect without cooler initialization for single image mode
        try:
            if not main_camera.camera.Connected:        # Alpaca call
                main_camera.camera.Connected = True     # Alpaca call
                import time
                time.sleep(0.5)
            main_camera.connected = main_camera.camera.Connected    # Alpaca call
            if main_camera.connected:
                logger.info(f"Connected to main camera: {main_camera.name} (cooler management disabled)")
            else:
                logger.error("Failed to connect to main camera")
                return 1
        except Exception as e:
            logger.error(f"Failed to connect to main camera: {e}")
            return 1
        
        # Connect to telescope
        logger.info('Connecting to telescope...')
        telescope_driver = AlpacaTelescopeDriver()                  # from alpaca_telescope.py
        telescope_config = config_loader.get_telescope_config()     # from loader.py
        
        if not telescope_driver.connect(telescope_config):          # from alpaca_telescope.py 
            logger.error('Failed to connect to telescope')
            return 1
        
        tel_info = telescope_driver.get_telescope_info()            # from alpaca_telescope.py
        logger.info(f"Connected to: {tel_info.get('name', 'Unknown telescope')}")
        logger.info(f"Current position: RA={tel_info.get('ra_hours', 0):.6f} h ({tel_info.get('ra_hours', 0)*15.0:.6f}°), "
                    f"Dec={tel_info.get('dec_degrees', 0):.6f}°")
        
        # Update target_info with values from telescope, if using current position
        if args.current_position:
            target_info.ra_j2000_hours = tel_info.get('ra_hours', 0)
            target_info.dec_j2000_deg = tel_info.get('dec_degrees', 0)
            target_info.tic_id = f"CURRENTPOS_{target_info.ra_j2000_hours:.3f}h_{target_info.dec_j2000_deg:+.3f}d"
            logger.info(f"Using current telescope position as target")
            
            # Enable telescope tracking if using --current-position
            try:
                if not telescope_driver.telescope.Tracking:     # Alpaca call, from alpaca_telescope.py
                    logger.warning("Telescope tracking disabled - re-enabling")
                    telescope_driver.telescope.Tracking = True  # Alapca call, from alpaca_telescope.py
                    import time
                    time.sleep(0.5)
                    # Confirm tracking
                    if telescope_driver.telescope.Tracking:
                        logger.info("Telescope tracking successfully enabled")
                    else:
                        logger.error("Failed to re-enable telescope tracking")
            except Exception as e:
                logger.warning(f"Tracking error: {e}")
        
        # Connect to cover
        cover_driver = None
        logger.info("Connecting to cover...")
        try:
            cover_driver = AlpacaCoverDriver()                      # from alpaca_cover.py
            cover_config = config_loader.get_cover_config()         # from loader.py
            if cover_config and cover_driver.connect(cover_config): # from alpaca_cover.py
                cover_info = cover_driver.get_cover_info()          # from alpaca_cover.py
                logger.info(f"Connected to: {cover_info.get('name', 'Unknown cover')} - State: {cover_info.get('cover_state', 'Unknown')}")
            else:
                logger.warning("Failed to connect to cover - continuing without")
                cover_driver = None
        except AlpacaCoverError as e:
            logger.warning(f"Cover connection failed: {e} - continuing without")
            cover_driver = None
        
        # Turn telescope motor on
        logger.info('Turning telescope motor on...') 
        motor_success = telescope_driver.motor_on()             # from alpaca_telescope.py
        if not motor_success:
            logger.error('Failed to turn telescope motor on')
            telescope_driver.disconnect()                       # from alpaca_telescope.py
            return 1
        
        # Connect to filter wheel and set selected filter
        filter_driver = None
        logger.info("Connecting to filter wheel...")
        try:
            filter_driver = AlpacaFilterWheelDriver()                   # from alpaca_filterwheel.py
            filter_config = config_loader.get_filter_wheel_config()     # from loader.py
            # Connect to filter wheel
            if filter_config and filter_driver.connect(filter_config):  # from alpaca_filterwheel.py
                filter_info = filter_driver.get_filter_info()           # from alpaca_filterwheel.py
                logger.info(f"Connected to filter wheel: {filter_info.get('total_filters', 0)} filters")
                logger.info(f"Current filter: {filter_info.get('filter_name', 'Unknown')}")
                # Change filter wheel to selected filter
                if filter_driver.change_filter(args.filter.upper()):    # from alpaca_filterwheel.py
                    logger.info(f"Filter set to: {args.filter.upper()}")
                else:
                    logger.warning(f"Failed to change to filter {args.filter.upper()} - continuing with current filter")
            else:
                logger.warning(f"Failed to connect to filter wheel - continuing with current filter")
                filter_driver = None
        except AlpacaFilterWheelError as e:
            logger.warning(f"Filter wheel connection failed: {e} - continuing with current filter")
            filter_driver = None
        
        # Connect to focuser
        focuser_driver = None
        logger.info("Connecting to focuser...")
        try:
            focuser_driver = AlpacaFocuserDriver()                          # from alpaca_focuser.py
            focuser_config = config_loader.get_focuser_config()             # from loader.py
            if focuser_config and focuser_driver.connect(focuser_config):   # from alpaca_focuser.py
                focuser_info = focuser_driver.get_focuser_info()            # from alpaca_focuser.py
                logger.info(f"Connected to focuser: {focuser_info.get('name', 'Unknown')}")
                logger.info(f"    Current position: {focuser_info.get('position', 'Unknown')}")
            else:
                logger.warning("Failed to connect to focuser - continuing without")
                focuser_driver = None
        except AlpacaFocuserError as e:
            logger.warning(f"Focuser connection failed: {e} - continuing without")
            focuser_driver = None
        except Exception as e:
            logger.warning(f"Unexpected focuser error: {e} - continuing without")
            focuser_driver = None
        
        # Create coordinated focus/filter manager - MUST come after filterwheel and focuser initialisation
        focus_filter_mgr = None
        logger.info("Initializing focus/filter coordination...")
        try:
            focus_filter_mgr = FocusFilterManager(filter_driver=filter_driver, focuser_driver=focuser_driver) # from focus_filter_manager.py
        except FocusFilterManagerError as e:
            logger.warning(f"Error setting up focus/filter coordination manager: {e} - continuing anyway")
            focus_filter_mgr = None
        except Exception as e:
            logger.warning(f"Unexpected focus/filter coordination error: {e}")
            focus_filter_mgr = None
        
        # Use manager to set filter from --filter argument, focuser positions drawn from devices.yaml -> focuser -> focus positions
        if focus_filter_mgr:
            logger.info(f"Setting filter to {args.filter.upper()} with focus adjustment...")
            try:
                filter_changed, focus_changed = focus_filter_mgr.change_filter_with_focus(args.filter.upper())    # from focus_filter_manager.py
                if filter_changed:
                    logger.info(f"Filter set to: {args.filter.upper()}")
                if focus_changed:
                    logger.info(f"Focus adjusted for filter {args.filter.upper()}")
                if not filter_changed and not focus_changed:
                    logger.info("Already at target focus/filter configuration")
            except FocusFilterManagerError as e:
                logger.warning(f"Focus/filter coordination failed: {e} - continuing anyway")
            except Exception as e:
                logger.warning(f"Unexpected focus/filter coordination error: {e}")
        
        
        # Slew to target (skip if using current position)
        if not args.current_position:
            logger.info("Slewing to target coordinates...")
            slew_success = telescope_driver.slew_to_coordinates(    # from alpaca_telescope.py
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg
            )
            
            if not slew_success:
                logger.error('Failed to slew to target')
                telescope_driver.motor_off()                # from alpaca_telescope.py
                telescope_driver.disconnect()               # from alpaca_telescope.py
                return 1
            
            logger.info('Telescope positioned at target coordinates')
        else:
            logger.info('Using current telescope position (no slewing)')
        
        # Open cover
        if cover_driver:
            logger.info("Opening cover...")
            if not cover_driver.open_cover():               # from alpaca_cover.py
                logger.error("Failed to open cover - aborting")
                return 1
            logger.info("Cover opened successfully")
        
        # Capture single image
        logger.info("="*75)
        logger.info(" "*25+"CAPTURING IMAGE")
        logger.info("="*75)
        logger.info(f"Exposure time: {args.exposure_time} s")
        logger.info(f"Filter: {args.filter.upper()}")
        
        # Get camera settings
        camera_config = main_camera.config                  # from camera.py (using devices.yaml)
        binning = camera_config.get('default_binning', 4)   # from devices.yaml
        gain = camera_config.get('default_gain', 100)       # from devices.yaml
        
        logger.info(f"Binning: {binning}x{binning}, Gain: {gain}")
        
        # Capture the image (with retry on timeout)
        max_retries = 3
        image_array = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Capture attempt {attempt}/{max_retries}...")
                image_array = main_camera.capture_image(    # from camera.py
                    exposure_time=args.exposure_time,
                    binning=binning,
                    gain=gain,
                    light=True
                )
                if image_array is not None:
                    break
                logger.warning(f"Attempt {attempt} returned no data, retrying...")
            except Exception as e:
                if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                    logger.warning(f"Attempt {attempt} timed out: {e}")
                    if attempt < max_retries:
                        logger.info("Retrying capture...")
                        import time
                        time.sleep(2)  # Brief pause before retry
                    else:
                        logger.error("All capture attempts failed")
                        raise
                else:
                    # Non-timeout error, don't retry
                    raise
        
        if image_array is None:
            logger.error("Camera returned no image data after all attempts")
            return 1
        
        logger.info("Image captured successfully")
        
        # Create FITS file
        logger.info("Creating FITS file...")
        hdu = create_fits_file(                 # from fits_utils.py
            image_array=image_array,
            target_info=target_info,
            camera_device=main_camera,
            config_loader=config_loader,
            filter_code=args.filter.upper(),
            exposure_time=args.exposure_time
        )
        
        # Add single image marker to header
        if hasattr(hdu, 'header'):
            hdu.header['IMGTYPE'] = ('SingleImage', 'Single test image for exposure optimization')
        
        # Setup save directory structure
        file_manager = FileManager(config_loader)   # from file_manager.py
        
        # Create singleimages subdirectory
        base_dir = file_manager.create_target_directory("singleimages") # from file_manager.py
        single_images_dir = base_dir
        single_images_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the file
        filepath = file_manager.save_fits_file(     # from file_manager.py
            hdu=hdu,
            tic_id=target_info.tic_id,
            filter_code=args.filter.upper(),
            exposure_time=args.exposure_time,
            sequence_number=1,  # Always 1 for single images
            target_dir=single_images_dir
        )
        
        if filepath:
            logger.info("="*75)
            logger.info(" "*30+"SUCCESS")
            logger.info("="*75)
            logger.info(f"Image saved to: {filepath}")
            logger.info(f"Open this file in MaxIm DL or similar to check target counts")
        else:
            logger.error("Failed to save FITS file")
            return 1
        
        # Summary
        logger.info("="*75)
        logger.info(" "*28+"IMAGE SUMMARY")
        logger.info("="*75)
        logger.info(f"Target: {target_info.tic_id}")
        logger.info(f"Coordinates: RA={target_info.ra_j2000_hours:.6f} h ({target_info.ra_j2000_hours*15.0:.6f}°), "
                    f"Dec={target_info.dec_j2000_deg:.6f}°")
        logger.info(f"Exposure time: {args.exposure_time} s")
        logger.info(f"Filter: {args.filter.upper()}")
        logger.info(f"Image size: {image_array.shape[1]}x{image_array.shape[0]}")
        logger.info(f"Binning: {binning}x{binning}")
        logger.info(f"Gain: {gain}")
        logger.info("="*75)
        logger.info("Telescope remains at target position for additional captures")
        logger.info("="*75)
        
        return 0
    
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except TargetResolutionError as e:
        logger.error(f"Target resolution error: {e}")
        return 1
    except ObservabilityError as e:
        logger.error(f"Observability error: {e}")
        return 1
    except AlpacaTelescopeError as e:
        logger.error(f"Telescope error: {e}")
        return 1
    except AlpacaCoverError as e:
        logger.error(f"Cover error: {e}")
        return 1
    except CameraError as e:
        logger.error(f"Camera error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info(f"Operation cancelled by user")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(f"Full traceback", exc_info=True)
        return 1
    finally:
        try:
            # Cleanup - but don't park telescope or close covers (save time for possible multiple single images)
            if cover_driver:
                logger.warning("Not closing cover (You will need to manually close later)")
                # cover_driver.close_cover()
            if filter_driver:
                filter_driver.disconnect()  # from alpaca_filterwheel.py
            if focuser_driver:
                focuser_driver.disconnect() # from alpaca_focuser.py
            if telescope_driver:
                logger.warning("Leaving telescope at target position (not parking)")
                logger.info("Turning telescope motor off...")
                telescope_driver.motor_off()    # from alpaca_telescope.py
                telescope_driver.disconnect()   # from alpaca_telescope.py
            logger.info("="*75)
            logger.info(" "*29+"CAPTURE COMPLETE")
            logger.info("="*75)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

if __name__ == '__main__':
    sys.exit(main())