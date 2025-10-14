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
from autopho.imaging.fits_utils import create_fits_file
from autopho.imaging.file_manager import FileManager

# Import focuser driver from the project structure
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'autopho' / 'devices' / 'drivers'))
try:
    from alpaca_focuser import AlpacaFocuserDriver, AlpacaFocuserError
except ImportError:
    # Fallback if it's in a different location
    from pathlib import Path
    import importlib.util
    focuser_path = Path(__file__).parent / 'src' / 'autopho' / 'devices' / 'drivers' / 'alpaca_focuser.py'
    if not focuser_path.exists():
        raise ImportError("Cannot find alpaca_focuser.py - please check file location")
    spec = importlib.util.spec_from_file_location("alpaca_focuser", focuser_path)
    alpaca_focuser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alpaca_focuser)
    AlpacaFocuserDriver = alpaca_focuser.AlpacaFocuserDriver
    AlpacaFocuserError = alpaca_focuser.AlpacaFocuserError


def setup_logging(log_level: str, log_dir: Path, log_name: str = None):
    """Setup logging for focus sweep"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if log_name is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_name = f"focus_sweep_{timestamp}.log"
        
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
        "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]"
    ))
    file_handler.setLevel(logging.DEBUG)
        
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler]
    )
    
    return logfile


def main():
    parser = argparse.ArgumentParser(
        description="T2 Focus Sweep - Automated focus position testing across all filters"
    )
    parser.add_argument(
        "tic_id",
        help="TIC ID to observe (e.g. TIC-123456789 or 123456789)"
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
        "--ignore-twilight",
        action="store_true",
        help="Ignore twilight conditions for daytime testing"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    try:
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()
        log_dir = Path(config_loader.get_config("paths")["logs"])
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_name = f"focus_sweep_{timestamp}_{args.tic_id}.log"
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
    logger.info(" "*25+"FOCUS SWEEP SESSION")
    logger.info("="*75)
    
    telescope_driver = None
    cover_driver = None
    filter_driver = None
    focuser_driver = None
    camera_manager = None
    
    # Track all captures for summary
    capture_log = []
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()
        logger.info('Configuration loaded successfully')
        
        # Get focus sweep configuration
        devices_config = config_loader.get_config('devices')
        if 'focuser' not in devices_config or 'focus_sweep' not in devices_config['focuser']:
            logger.error("Missing 'focus_sweep' configuration in devices.yaml under 'focuser'")
            logger.error("Please add:")
            logger.error("  focus_sweep:")
            logger.error("    range_steps: 100")
            logger.error("    step_size: 10")
            logger.error("    exposure_time: 3.0")
            logger.error("    filters: ['C', 'B', 'G', 'R', 'L', 'I', 'H']")
            return 1
        
        sweep_config = devices_config['focuser']['focus_sweep']
        focus_positions = devices_config['focuser'].get('focus_positions', {})
        
        range_steps = sweep_config.get('range_steps', 100)
        step_size = sweep_config.get('step_size', 10)
        exposure_time = sweep_config.get('exposure_time', 3.0)
        filters_to_test = sweep_config.get('filters', ['C', 'B', 'G', 'R', 'L', 'I', 'H'])
        
        logger.info(f"Focus sweep configuration:")
        logger.info(f"  Range: ±{range_steps} steps")
        logger.info(f"  Step size: {step_size}")
        logger.info(f"  Exposure time: {exposure_time}s")
        logger.info(f"  Filters: {', '.join(filters_to_test)}")
        
        # Resolve target
        logger.info(f"Resolving target: {args.tic_id}")
        target_resolver = TICTargetResolver(config_loader)
        target_info = target_resolver.resolve_tic_id(args.tic_id)
        logger.info(f"Target: {target_info.tic_id}")
        logger.info(f"Coordinates: RA={target_info.ra_j2000_hours:.6f} h, Dec={target_info.dec_j2000_deg:.6f}°")
        
        # Check observability
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
            
            if not obs_status.observable:
                logger.error("Target not currently observable:")
                for reason in obs_status.reasons:
                    logger.error(f"  {reason}")
                return 1
            
            logger.info("Target is observable - proceeding")
                
        except ObservabilityError as e:
            logger.error(f"Observability check error: {e}")
            return 1
        
        # Discover cameras
        logger.info('Discovering cameras...')
        camera_manager = CameraManager()
        camera_configs = config_loader.get_camera_configs()
        
        if camera_manager.discover_cameras(camera_configs):
            logger.info('Camera discovery successful')
        else:
            logger.error('Camera discovery failed')
            return 1
        
        # Connect to main camera (disable auto-cooler)
        main_camera = camera_manager.get_main_camera()
        if not main_camera:
            logger.error("Main camera not found")
            return 1
        
        try:
            if not main_camera.camera.Connected:
                main_camera.camera.Connected = True
                time.sleep(0.5)
            main_camera.connected = main_camera.camera.Connected
            if main_camera.connected:
                logger.info(f"Connected to camera: {main_camera.name}")
            else:
                logger.error("Failed to connect to camera")
                return 1
        except Exception as e:
            logger.error(f"Camera connection error: {e}")
            return 1
        
        # Get camera settings
        camera_config = main_camera.config
        binning = camera_config.get('default_binning', 4)
        gain = camera_config.get('default_gain', 100)
        logger.info(f"Camera settings: Binning {binning}x{binning}, Gain {gain}")
        
        # Connect to telescope
        logger.info('Connecting to telescope...')
        telescope_driver = AlpacaTelescopeDriver()
        telescope_config = config_loader.get_telescope_config()
        
        if not telescope_driver.connect(telescope_config):
            logger.error('Failed to connect to telescope')
            return 1
        
        tel_info = telescope_driver.get_telescope_info()
        logger.info(f"Connected to telescope: {tel_info.get('name', 'Unknown')}")
        
        # Connect to cover
        logger.info("Connecting to cover...")
        try:
            cover_driver = AlpacaCoverDriver()
            cover_config = config_loader.get_cover_config()
            if cover_config and cover_driver.connect(cover_config):
                logger.info("Cover connected")
            else:
                logger.warning("Cover connection failed - continuing without")
                cover_driver = None
        except AlpacaCoverError as e:
            logger.warning(f"Cover error: {e} - continuing without")
            cover_driver = None
        
        # Connect to filter wheel
        logger.info("Connecting to filter wheel...")
        filter_driver = AlpacaFilterWheelDriver()
        filter_config = config_loader.get_filter_wheel_config()
        
        if not filter_driver.connect(filter_config):
            logger.error("Failed to connect to filter wheel")
            return 1
        logger.info("Filter wheel connected")
        
        # Connect to focuser
        logger.info("Connecting to focuser...")
        focuser_driver = AlpacaFocuserDriver()
        focuser_config = devices_config.get('focuser', {})
        
        if not focuser_driver.connect(focuser_config):
            logger.error("Failed to connect to focuser")
            return 1
        
        focuser_info = focuser_driver.get_focuser_info()
        logger.info(f"Focuser connected: {focuser_info.get('name', 'Unknown')}")
        logger.info(f"Current position: {focuser_info.get('position', 'Unknown')}")
        
        # Turn telescope motor on
        logger.info('Turning telescope motor on...') 
        if not telescope_driver.motor_on():
            logger.error('Failed to turn telescope motor on')
            return 1
        
        # Slew to target
        logger.info("Slewing to target...")
        if not telescope_driver.slew_to_coordinates(
            target_info.ra_j2000_hours,
            target_info.dec_j2000_deg
        ):
            logger.error('Failed to slew to target')
            return 1
        logger.info('Telescope positioned at target')
        
        # Open cover
        if cover_driver:
            logger.info("Opening cover...")
            if not cover_driver.open_cover():
                logger.error("Failed to open cover")
                return 1
            logger.info("Cover opened")
        
        # Setup save directory
        file_manager = FileManager(config_loader)
        base_dir = file_manager.create_target_directory("focus_sweep")
        sweep_dir = base_dir / f"{target_info.tic_id}_{timestamp}"
        sweep_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving images to: {sweep_dir}")
        
        # Begin focus sweep
        logger.info("="*75)
        logger.info(" "*22+"STARTING FOCUS SWEEP")
        logger.info("="*75)
        
        total_images = 0
        for filter_code in filters_to_test:
            filter_code = filter_code.upper()
            
            # Check if we have a focus position defined for this filter
            if filter_code.lower() not in focus_positions and filter_code.upper() not in focus_positions:
                logger.warning(f"No focus position defined for filter {filter_code} - skipping")
                continue
            
            optimal_position = focus_positions.get(filter_code.lower(), focus_positions.get(filter_code.upper()))
            
            logger.info("")
            logger.info("="*75)
            logger.info(f"FILTER: {filter_code} (Optimal position: {optimal_position})")
            logger.info("="*75)
            
            # Change filter
            logger.info(f"Changing to filter {filter_code}...")
            if not filter_driver.change_filter(filter_code):
                logger.error(f"Failed to change to filter {filter_code} - skipping")
                continue
            
            # Calculate focus positions to test
            start_pos = optimal_position - range_steps
            end_pos = optimal_position + range_steps
            test_positions = list(range(start_pos, end_pos + 1, step_size))
            
            logger.info(f"Testing {len(test_positions)} focus positions: {start_pos} to {end_pos} (step {step_size})")
            
            # Loop through focus positions
            for idx, focus_pos in enumerate(test_positions, 1):
                logger.info(f"  [{idx}/{len(test_positions)}] Focus position: {focus_pos}")
                
                # Move focuser
                if not focuser_driver.move_to_position(focus_pos):
                    logger.error(f"Failed to move focuser to {focus_pos} - skipping")
                    continue
                
                # Small settle time after focus move
                time.sleep(0.5)
                
                # Capture image
                try:
                    image_array = main_camera.capture_image(
                        exposure_time=exposure_time,
                        binning=binning,
                        gain=gain,
                        light=True
                    )
                    
                    if image_array is None:
                        logger.warning(f"No image data returned for position {focus_pos}")
                        continue
                    
                    # Create FITS file
                    hdu = create_fits_file(
                        image_array=image_array,
                        target_info=target_info,
                        camera_device=main_camera,
                        config_loader=config_loader,
                        filter_code=filter_code,
                        exposure_time=exposure_time
                    )
                    
                    # Add focus sweep metadata
                    if hasattr(hdu, 'header'):
                        hdu.header['IMGTYPE'] = ('FocusSweep', 'Focus position test image')
                        hdu.header['FOCUSPOS'] = (focus_pos, 'Focuser position during exposure')
                        hdu.header['FOCUSOPT'] = (optimal_position, 'Optimal focus position for filter')
                        hdu.header['FOCUSOFF'] = (focus_pos - optimal_position, 'Offset from optimal position')
                    
                    # Save with focus position in filename
                    filename = f"{target_info.tic_id}_{filter_code}_focus{focus_pos:05d}_{timestamp}.fits"
                    filepath = sweep_dir / filename
                    
                    hdu.writeto(filepath, overwrite=True)
                    logger.info(f"    Saved: {filename}")
                    
                    # Log this capture
                    capture_log.append({
                        'filter': filter_code,
                        'focus_position': focus_pos,
                        'offset': focus_pos - optimal_position,
                        'filename': filename
                    })
                    total_images += 1
                    
                except Exception as e:
                    logger.error(f"Capture failed at position {focus_pos}: {e}")
                    continue
            
            logger.info(f"Completed filter {filter_code}: {len([c for c in capture_log if c['filter'] == filter_code])} images")
        
        # Final summary
        logger.info("")
        logger.info("="*75)
        logger.info(" "*27+"SWEEP COMPLETE")
        logger.info("="*75)
        logger.info(f"Total images captured: {total_images}")
        logger.info(f"Images saved to: {sweep_dir}")
        logger.info("")
        logger.info("Capture Summary:")
        logger.info("-"*75)
        
        for filter_code in filters_to_test:
            filter_captures = [c for c in capture_log if c['filter'] == filter_code]
            if filter_captures:
                logger.info(f"  {filter_code}: {len(filter_captures)} images")
                positions = [c['focus_position'] for c in filter_captures]
                logger.info(f"     Positions: {min(positions)} to {max(positions)}")
        
        logger.info("="*75)
        
        return 0
    
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except TargetResolutionError as e:
        logger.error(f"Target resolution error: {e}")
        return 1
    except AlpacaTelescopeError as e:
        logger.error(f"Telescope error: {e}")
        return 1
    except AlpacaFocuserError as e:
        logger.error(f"Focuser error: {e}")
        return 1
    except AlpacaFilterWheelError as e:
        logger.error(f"Filter wheel error: {e}")
        return 1
    except CameraError as e:
        logger.error(f"Camera error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info(f"Operation cancelled by user")
        logger.info(f"Captured {len(capture_log)} images before cancellation")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(f"Full traceback", exc_info=True)
        return 1
    finally:
        try:
            # Cleanup
            if cover_driver:
                logger.info("Closing cover...")
                cover_driver.close_cover()
            if filter_driver:
                logger.info("Disconnecting filter wheel...")
                filter_driver.disconnect()
            if focuser_driver:
                logger.info("Disconnecting focuser...")
                focuser_driver.disconnect()
            if telescope_driver:
                logger.info("Turning telescope motor off...")
                telescope_driver.motor_off()
                telescope_driver.disconnect()
            if camera_manager:
                logger.info("Disconnecting camera...")
                # Camera cleanup if needed
            
            logger.info("="*75)
            logger.info(" "*26+"SESSION COMPLETE")
            logger.info("="*75)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


if __name__ == '__main__':
    sys.exit(main())
