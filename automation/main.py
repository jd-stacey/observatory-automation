import sys
import logging
from rich.logging import RichHandler
import argparse
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent / 'src'))

from autopho.config.loader import ConfigLoader, ConfigurationError
from autopho.targets.resolver import TICTargetResolver, TargetResolutionError
from autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver, AlpacaTelescopeError
from autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver, AlpacaCoverError
from autopho.devices.drivers.alpaca_filterwheel import AlpacaFilterWheelDriver, AlpacaFilterWheelError
from autopho.devices.camera import CameraManager, CameraError
from autopho.targets.observability import ObservabilityChecker, ObservabilityError
from autopho.platesolving.corrector import PlatesolveCorrector, PlatesolveCorrectorError
from autopho.devices.drivers.alpaca_rotator import AlpacaRotatorDriver, AlpacaRotatorError
from autopho.imaging.session import ImagingSession, ImagingSessionError

def setup_logging(log_level: str = "INFO"):
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
    # logging.basicConfig(
    #     level=numeric_level,
    #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    #     handlers=[
    #         logging.StreamHandler(sys.stdout),
    #     ]
    # )

def main():
    parser = argparse.ArgumentParser(
        description="T2 Automated Photometry"
    )
    parser.add_argument(
        "tic_id",
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
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
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
        
        logger.info(f"Resolving target: {args.tic_id}")
        target_resolver = TICTargetResolver()
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
        
            logger.info(f"Target altitude: {obs_status.target_altitude:.1f}°")
            logger.info(f"Sun altitude: {obs_status.sun_altitude:.1f}°")
            if obs_status.airmass:
                logger.debug(f"Airmass: {obs_status.airmass:.2f}")
                
            logger.info(f"Observability:")
            for reason in obs_status.reasons:
                if obs_status.observable:
                    logger.info(f"  {obs_status.observable}: {reason}")
                else:
                    logger.info(f"  {obs_status.observable}: {reason}")
                    
            if not obs_status.observable and not args.dry_run:
                logger.error(f"Target is not currently observable")
                
                next_time = checker.get_next_observable_time(
                    target_info.ra_j2000_hours,
                    target_info.dec_j2000_deg
                )
                if next_time:
                    logger.info(f"Target will be observable at {next_time.isoformat()}")
                    
                return 1
            
            elif not obs_status.observable and args.dry_run:
                logger.warning(f"Target not observable, but continuing with dry run")
                
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
                    duration_hours=args.duration
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
            if cover_driver:
                logger.info("Closing cover...")
                cover_driver.close_cover()
            if filter_driver:
                filter_driver.disconnect()
            if telescope_driver:
                telescope_driver.park()
                if telescope_driver.is_parked():
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
        


