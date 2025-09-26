import sys
import logging
from rich.logging import RichHandler
import argparse
from pathlib import Path
from datetime import datetime, timezone
import time


sys.path.insert(0, str(Path(__file__).parent / 'src'))

from autopho.config.loader import ConfigLoader, ConfigurationError
from autopho.targets.resolver import TICTargetResolver, TargetResolutionError, TargetInfo
from autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver, AlpacaTelescopeError
from autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver, AlpacaCoverError
from autopho.devices.drivers.alpaca_filterwheel import AlpacaFilterWheelDriver, AlpacaFilterWheelError
from autopho.devices.camera import CameraManager, CameraError
from autopho.targets.observability import ObservabilityChecker, ObservabilityError
from autopho.platesolving.corrector import PlatesolveCorrector, PlatesolveCorrectorError
from autopho.devices.drivers.alpaca_rotator import AlpacaRotatorDriver, AlpacaRotatorError
from autopho.imaging.session import ImagingSession, ImagingSessionError

def setup_logging(log_level: str, log_dir: Path, log_name: str = None):
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if log_name is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_name = f"{timestamp}_session.log"
        
    logfile = log_dir / log_name
    
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True, 
        show_path=True
        )
    
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.setLevel(numeric_level)
    
    
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]"
    ))
    file_handler.setLevel(logging.DEBUG)
        
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler]
    )
    
    return logfile

def wait_for_observing_conditions(target_info, obs_checker, ignore_twilight=False, poll_interval=60.0):
    """Simple waiting function for observing conditions"""
    logger = logging.getLogger(__name__)
    
    if ignore_twilight:
        logger.info("Twilight checks disabled - proceeding immediately")
        return True
    
    logger.info("="*60)
    logger.info("WAITING FOR OBSERVING CONDITIONS")
    logger.info("="*60)
    logger.info(f"Target: {target_info.tic_id}")
    logger.info(f"Coordinates: RA={target_info.ra_j2000_hours:.6f}h, Dec={target_info.dec_j2000_deg:.6f}°")
    
    start_time = datetime.now(timezone.utc)
    max_wait_hours = 16  # Don't wait more than 16 hours
    
    while (datetime.now(timezone.utc) - start_time).total_seconds() < (max_wait_hours * 3600):
        try:
            obs_status = obs_checker.check_target_observability(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg,
                ignore_twilight=False
            )
            
            if obs_status.observable:
                logger.info("="*60)
                logger.info("OBSERVING CONDITIONS MET - PROCEEDING")
                logger.info("="*60)
                return True
            
            # Show current status
            logger.info(f"Sun: {obs_status.sun_altitude:.1f}°, Target: {obs_status.target_altitude:.1f}°")
            logger.info(f"Waiting reasons: {'; '.join(obs_status.reasons)}")
            
            # Check if we're in a hopeless situation
            if (obs_status.sun_altitude < -10 and obs_status.target_altitude < 0):
                elapsed_hours = (datetime.now(timezone.utc) - start_time).total_seconds() / 3600
                if elapsed_hours > 2:
                    logger.warning("Target remains below horizon well into night")
                    logger.warning("Target likely not observable tonight - consider different target")
                    return False
            
            logger.info(f"Next check in {poll_interval/60:.1f} minutes...")
            
        except Exception as e:
            logger.warning(f"Error checking observing conditions: {e}")
            logger.info(f"Retrying in {poll_interval} seconds...")
        
        time.sleep(poll_interval)
    
    logger.error(f"Timeout after {max_wait_hours} hours - giving up")
    return False

def main():
    parser = argparse.ArgumentParser(
        description="T2 Automated Photometry"
    )
    parser.add_argument(
        "tic_id",
        nargs='?',
        help="TID ID to observe (e.g. TIC-123456789 or 123456789)"
    )
    parser.add_argument(
        "--filter",
        default='C',
        choices=["C", "B", "G", "R", "L", "I", "H", "c", "b", "g", "r", "l", "i", "h"],
        help="Filter selection: C=Clear, B=Blue, G=Green, R=Sloan-r, L=Lum, I=Sloan-i, H=H-alpha (default: C)"  
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
        help="Session duration in hours"
    )
    
    parser.add_argument(
        '--max-exposures', 
        type=int, 
        help="Maximum exposures to take"
    )
    
    parser.add_argument(
        '--exposure-time', 
        type=float, 
        help="Override calculated exposure time (seconds)"
    )
    
    parser.add_argument(
        '--correction-interval', 
        type=int, 
        default=5,
        help="Apply correction every N exposures (default: 5)"
    )
    
    parser.add_argument(
        '--coords', 
        help="Manual coordinates: 'RA_HOURS DEC_DEGREES (overrides TIC lookup)"
    )
    
    parser.add_argument(
        '--test-acquisition',
        action='store_true',
        help="Test acquisition flow without taking images (for daytime testing)"
    )
    
    parser.add_argument(
        '--no-park',
        action='store_true',
        help="Skip parking telescope at end of session (default: auto-park)"
    )
    
    args = parser.parse_args()
    
    if not args.tic_id and not args.coords:
        parser.error("Must provide either tic_id or --coords")
    if args.tic_id and args.coords:
        parser.error("Cannot use both tic_id and --coords - choose one")
    
    try:
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()
        log_dir = Path(config_loader.get_config("paths")["logs"])
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if args.tic_id:    
            log_name = f"{timestamp}_{args.tic_id}.log"
        elif args.coords:
            log_name = f"{timestamp}_MANUAL.log"
        else:
            log_name = f"{timestamp}_session.log"
    
        logfile = setup_logging(args.log_level, log_dir, log_name)
        logger = logging.getLogger(__name__)
        logger.info(f"Logging to {logfile}")
    except Exception as e:
        logger.error(f"Logging setup error: {e}")
           
    logging.getLogger('astroquery').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    logger.info("="*75)
    logger.info(" "*27+"AUTOMATED PHOTOMETRY")
    logger.info("="*75)
    
    
    telescope_driver = None
    rotator_driver = None
    cover_driver = None
    filter_driver = None
    camera_manager = None
    corrector = None
    
    try:
        logger.info("Loading configuration...")
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()
        logger.info('Configuration loaded successfully')
        
        # logger.info(f"Resolving target: {args.tic_id}")
        # target_resolver = TICTargetResolver(config_loader)
        # target_info = target_resolver.resolve_tic_id(args.tic_id)
        
        if args.coords:
            logger.info(f"Using manual coordinates: {args.coords}")
            # Parse coordinates
            try:
                coords_parts = args.coords.strip().split()
                if len(coords_parts) != 2:
                    raise ValueError("Expected 'RA_DEGREES DEC_DEGREES'")
                ra_hours = float(coords_parts[0]) / 15.0
                dec_deg = float(coords_parts[1])
                
                # Validate ranges
                if not (0 <= ra_hours < 24):
                    raise ValueError(f"RA must be 0-360 degrees, got {float(coords_parts[0])}")
                if not (-90 <= dec_deg <= 90):
                    raise ValueError(f"Dec must be -90 to +90 degrees, got {dec_deg}")
                    
                # Create manual TargetInfo (no TIC data)
                target_info = TargetInfo(
                    tic_id=f"MANUAL-{ra_hours:.3f}h_{dec_deg:+.3f}d",
                    ra_j2000_hours=ra_hours,
                    dec_j2000_deg=dec_deg,
                    gaia_g_mag=12.0,  # Default for exposure calculation
                    magnitude_source="manual-default"
                )
                logger.info(f"Manual target: RA={ra_hours:.6f} h, Dec={dec_deg:.6f}°")
                
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid coordinates format '{args.coords}': {e}")
                logger.error("Use format: --coords 'RA_HOURS DEC_DEGREES' (e.g., '12.345 -67.890')")
                return 1
        else:
            logger.info(f"Resolving target: {args.tic_id}")
            target_resolver = TICTargetResolver(config_loader)
            target_info = target_resolver.resolve_tic_id(args.tic_id)
        
        
        exposure_time = config_loader.get_exposure_time(target_info.gaia_g_mag, args.filter.upper())
        logger.info(f"Calculated exposure time: {exposure_time} s for G={target_info.gaia_g_mag:.2f}, filter={args.filter.upper()}")
        
        # target_json_data = target_resolver.create_target_json(target_info)
        
        logger.info("Checking target observability...")
        try:
            observatory_config = config_loader.get_config('observatory')
            checker = ObservabilityChecker(observatory_config)
            obs_status = checker.check_target_observability(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg,
                ignore_twilight=args.ignore_twilight
            )
        
            logger.info(f"Current target altitude: {obs_status.target_altitude:.1f}°")
            logger.info(f"Current sun altitude: {obs_status.sun_altitude:.1f}°")
            if obs_status.airmass:
                logger.debug(f"Airmass: {obs_status.airmass:.2f}")
                
            # If immediately observable, great
            if obs_status.observable:
                logger.info("Target is immediately observable")
            else:
                # Show what conditions are not met
                logger.info("Current observability status:")
                for reason in obs_status.reasons:
                    logger.info(f"  {reason}")
                
                # If dry run, continue regardless
                if args.dry_run:
                    logger.warning("Target not currently observable, but continuing with dry run")
                else:
                    # Wait for conditions
                    logger.info("Waiting for observing conditions...")
                    if not wait_for_observing_conditions(target_info, checker, args.ignore_twilight):
                        logger.error("Target will not be observable - aborting")
                        return 1
                
        except ObservabilityError as e:
            logger.error(f"Observability check error: {e}")
            return 1
        
        
        # if config_loader.write_target_json(target_json_data):
        #     pass
            
        # else:
        #     logger.warning("Platesolver has no JSON to read target info. Continuing...")
        
        camera_manager = None
        if not args.dry_run:
            logger.info('Discovering cameras...')
            camera_manager = CameraManager()
            camera_configs = config_loader.get_camera_configs()
            
            if camera_manager.discover_cameras(camera_configs):
                logger.info('Camera discovery sucsessful:')
                for camera_status in camera_manager.list_all_cameras():
                    logger.info(f"{camera_status['role'].upper()} camera: {camera_status['name']} "
                                f"(ID: {camera_status['device_id']})")
            else:
                logger.error('Camera discovery failed')
                return 1
            
        if not args.dry_run:
            logger.info('Connecting to telescope...')
            telescope_driver = AlpacaTelescopeDriver()
            telescope_config = config_loader.get_telescope_config()
            
            if not telescope_driver.connect(telescope_config):
                logger.error('Failed to connect to telescope')
                return 1
            
            tel_info = telescope_driver.get_telescope_info()
            logger.info(f"Connected to :{tel_info.get('name', 'Unknown telescope')}")
            logger.info(f"Current position: RA={tel_info.get('ra_hours', 0):.6f} h, "
                        f"Dec={tel_info.get('dec_degrees', 0):.6f}°")
            
            
            rotator_driver = None
            logger.info("Connecting to rotator...")
            try:
                rotator_driver = AlpacaRotatorDriver()
                rotator_config = config_loader.get_rotator_config()
                
                if rotator_driver.connect(rotator_config):
                    rot_info = rotator_driver.get_rotator_info()
                    logger.info(f"Connected to: {rot_info.get('name', 'Unknown rotator')} - Current position: {rot_info.get('position_deg', 0):.2f}°")
                    
                    if rotator_driver.initialize_position():
                        logger.info("Rotator initialized to safe position")
                    else:
                        logger.warning('Rotator initialization failed - continuing')
                else:
                    logger.warning('Failed to connect to rotator - continuing without')
                    rotator_driver = None
            except AlpacaRotatorError as e:
                logger.warning(f"Rotator connection failed: {e} - continuing without")        
                rotator_driver = None
            except Exception as e:  # Catch any other rotator connection issues
                logger.warning(f"Unexpected rotator error: {e} - continuing without")
                rotator_driver = None
            
            
            cover_driver = None
            logger.info("Connecting to cover...")
            try:
                cover_driver = AlpacaCoverDriver()
                cover_config = config_loader.get_cover_config()
                if cover_config and cover_driver.connect(cover_config):
                    cover_info = cover_driver.get_cover_info()
                    logger.info(f"Connected to: {cover_info.get('name', 'Unknown cover')} - State: {cover_info.get('cover_state', 'Unknown')}")
                else:
                    logger.warning("Failed to connected to cover - continuing without")
                    cover_driver = None
            except AlpacaCoverError as e:
                logger.warning(f"Cover connection failed: {e} - continuing without")
                cover_driver = None
            
            logger.info('Turning telescope motor on...') 
            motor_success = telescope_driver.motor_on()
            if not motor_success:
                logger.error('Failed to turn telescope motor on')
                telescope_driver.disconnect()
                return 1
                        
            
            
            filter_driver = None
            logger.info("Connecting to filter wheel...")
            try:
                filter_driver = AlpacaFilterWheelDriver()
                filter_config = config_loader.get_filter_wheel_config()
                
                if filter_config and filter_driver.connect(filter_config):
                    filter_info = filter_driver.get_filter_info()
                    logger.info(f"Connected to filter wheel: {filter_info.get('total_filters', 0)} filters")
                    logger.info(f"Filters: {filter_info.get('all_filters', [])}")
                    logger.info(f"Current filter: {filter_info.get('filter_name', 'Unknown')}")
                    
                    if filter_driver.change_filter(args.filter.upper()):
                        logger.info(f"Filter set to: {args.filter.upper()}")
                    else:
                        logger.warning(f"Failed to change to filter {args.filter.upper()} - continuing with current filter")
                else:
                    logger.warning(f"Failed to connect to filter wheel - continuing with current filter")
                    filter_driver = None
            except AlpacaFilterWheelError as e:
                logger.warning(f"Filter wheel connection failed: {e} - continuing with current filter")
                filter_driver = None
            except Exception as e:
                logger.warning(f"Unexpected filter wheel error: {e} - continuing with current filter")
            

            
            logger.info("Slewing to target coordinates...")
            slew_success = telescope_driver.slew_to_coordinates(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg
            )
            
            if not slew_success:
                logger.error('Failed to slew to target')
                telescope_driver.motor_off()
                telescope_driver.disconnect()
                return 1
            
            logger.info('Telescope positioned at target coordinates')
            
            
            # Now open cover once telescope is in position
            if cover_driver:
                logger.info("Opening cover...")
                if not cover_driver.open_cover():
                    logger.error("Failed to open cover - aborting observation")
                    return 1
                logger.info("Cover opened successfully")
            
            
            logger.info("Initialising platesolve corrector...")
            try:
                corrector = PlatesolveCorrector(telescope_driver, config_loader, rotator_driver)
                logger.info("Platesolve corrector initialised and ready for imaging loop")
                
                # Checks for latest platesolve info on initialization
                # logger.info("Checking for existing platesolve data...")
                # correction_result = corrector.apply_single_correction(timeout_seconds=10)
                # if correction_result.applied:
                #     logger.info(f"Initial correction applied: {correction_result.reason}")
                # else:
                #     logger.info(f"No initial correction needed: {correction_result.reason}")
                    
                
            except PlatesolveCorrectorError as e:
                logger.warning(f"Corrector initialisation failed: {e}")
                logger.info("Continuing without platesolve correction capability")
                corrector = None
            
           
            logger.info(f"Starting imaging session...")
                     
            
            try:
                
                session = ImagingSession(
                    camera_manager=camera_manager, 
                    corrector=corrector,
                    config_loader=config_loader,
                    target_info=target_info, 
                    filter_code=args.filter.upper(),
                    ignore_twilight=args.ignore_twilight,
                    exposure_override=args.exposure_time
                )
                session.correction_interval = args.correction_interval
                session_success = session.start_imaging_loop(
                    max_exposures=args.max_exposures,
                    duration_hours=args.duration,
                    telescope_driver=telescope_driver
                )
                if session_success:
                    logger.info(f"Imaging session completed successfully")
                else:
                    logger.error("Imaging session failed")
                    return 1
            except ImagingSessionError as e:
                logger.error(f"Imaging session error: {e}")
                return 1
            except Exception as e:
                logger.error(f"Unexpected imaging session error: {e}")
                return 1
                        
            
        else:
            logger.info('DRY RUN: Skipping telescope operations')
            logger.info(f"  Would start telescope motor")
            logger.info(f"  Would slew to: RA={target_info.ra_j2000_hours:.6f} h, "
                        f"Dec={target_info.dec_j2000_deg:.6f}°")
            logger.info(f"  Would use exposure time: {exposure_time} s")
            logger.info("DRY RUN: Skipping cover operations")
            logger.info(f"  Would open cover after telescope slews to target")
            logger.info(f"DRY RUN: Skipping filter wheel operations")
            logger.info(f"  Would set filter to {args.filter.upper()}")
            logger.info("DRY RUN: Skipping rotator operations")
            logger.info("DRY RUN: Skipping camera/imaging operations")
            if args.test_acquisition:
                try:
                    session = ImagingSession(
                        camera_manager=None,  # No camera needed for test
                        corrector=None,       # No corrector needed for test
                        config_loader=config_loader,
                        target_info=target_info, 
                        filter_code=args.filter.upper(),
                        ignore_twilight=args.ignore_twilight,
                        exposure_override=args.exposure_time
                    )
                except ImagingSessionError:
                    logger.warning("Could not create session for testing - continuing with dry run")
                    session = None
            
        if args.test_acquisition and session:
            logger.info("Running acquisition flow test...")
            test_success = session.test_acquisition_flow(simulate_corrections=True)
            if test_success:
                logger.info("Acquisition test completed successfully")
                return 0
            else:
                logger.error("Acquisition test failed")
                return 1
            
        logger.info("="*75)
        logger.info(" "*30+"SESSION SUMMARY")
        logger.info("="*75)
        logger.info(f"Target: {target_info.tic_id}")
        logger.info(f"Coordinates: RA={target_info.ra_j2000_hours:.6f} h, Dec={target_info.dec_j2000_deg:.6f}°")
        logger.info(f"Target altitude: {obs_status.target_altitude:.1f}°")
        logger.info(f"Sun altitude: {obs_status.sun_altitude:.1f}°")
        logger.info(f"Target observable: {obs_status.observable}")
        if target_info.tess_mag:
            logger.info(f"Gaia G magnitude: {target_info.gaia_g_mag:.2f} (TESS magnitude: {target_info.tess_mag:.2f})")
        else:
            logger.info(f"Gaia G magnitude: {target_info.gaia_g_mag:.2f}")
        logger.info(f"Calculated exposure time: {exposure_time} s")
        if args.exposure_time:
            logger.info(f"Override exposure time used: {args.exposure_time} s")
        logger.info(f"Filter: {args.filter.upper()}")
        
        logger.info("="*75)
        logger.info(" "*30+"SESSION COMPLETE")
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
        logger.error(f"Telelscope error: {e}")
        return 1
    except AlpacaRotatorError as e:
        logger.error(f"Rotator error: {e}")
        return 1
    except AlpacaCoverError as e:
        logger.error(f"Cover error: {e}")
        return 1
    except PlatesolveCorrectorError as e:
        logger.error(f"Platesolve corrector error: {e}")
        return 1
    except ImagingSessionError as e:
        logger.error(f"Imaging session error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info(f"Operation cancelled by user keyboard interrupt")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(f"Full traceback", exc_info=True)
        return 1
    finally:
        try:
            if camera_manager:
                logger.info("Shutting down camera coolers...")
                camera_manager.shutdown_all_coolers()
            if cover_driver:
                logger.info("Closing cover...")
                cover_driver.close_cover()
            if filter_driver:
                filter_driver.disconnect()
            if telescope_driver:
                if not args.no_park:
                    logger.info("Parking telescope...")
                    telescope_driver.park()
                else:
                    logger.info("Skipping telescope parking (--no-park specified)")
                    
                logger.info("Turning telescope motor off...")
                telescope_driver.motor_off()
                telescope_driver.disconnect()
            logger.info("="*75)
            logger.info(" "*29+"PROGRAM TERMINATED")
            logger.info("="*75)
        except Exception as e:
            logger.error(f"Disconnection error: {e}")
            logger.info("="*75)
            logger.info(" "*29+"PROGRAM TERMINATED")
            logger.info("="*75)
            pass
        
if __name__ == '__main__':
    sys.exit(main())
        


