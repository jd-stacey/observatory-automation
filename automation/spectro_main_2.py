import sys
import logging
from rich.logging import RichHandler
import argparse
from pathlib import Path
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from autopho.config.loader import ConfigLoader, ConfigurationError
from autopho.targets.resolver import TICTargetResolver, TargetInfo
from autopho.devices.drivers.alpaca_telescope import AlpacaTelescopeDriver
from autopho.devices.drivers.alpaca_cover import AlpacaCoverDriver
from autopho.devices.camera import CameraManager, CameraError
from autopho.targets.observability import ObservabilityChecker
from autopho.platesolving.corrector import PlatesolveCorrector
from autopho.imaging.session import ImagingSession, ImagingSessionError


def setup_logging(log_level: str = "INFO"):
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True, show_path=True)]
    )


class TelescopeMirror:
    """Handles mirroring coordinates from another telescope via JSON file"""

    def __init__(self, mirror_file: str):
        self.mirror_file = Path(mirror_file)
        self.last_timestamp = None
        self.last_coordinates = None

    def check_for_new_target(self) -> Optional[Dict[str, Any]]:
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
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if self.last_timestamp is None or timestamp > self.last_timestamp:
                ra_deg = latest_move.get('ra_deg')
                dec_deg = latest_move.get('dec_deg')
                if ra_deg is not None and dec_deg is not None:
                    ra_hours = ra_deg / 15.0
                    new_target = {
                        'timestamp': timestamp,
                        'ra_hours': ra_hours,
                        'dec_deg': dec_deg,
                        'ra_deg': ra_deg,
                        'source': 'mirrored_telescope'
                    }
                    self.last_timestamp = timestamp
                    self.last_coordinates = (ra_hours, dec_deg)
                    return new_target
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error reading mirror file: {e}")
        return None

    def get_current_target(self) -> Optional[Dict[str, Any]]:
        if self.last_coordinates:
            return {
                'ra_hours': self.last_coordinates[0],
                'dec_deg': self.last_coordinates[1],
                'source': 'mirrored_telescope'
            }
        return None


class SpectroscopyImagingSession(ImagingSession):
    """Imaging session using only the guide camera for spectroscopy"""

    def __init__(self, camera_manager, corrector, config_loader, target_info: TargetInfo,
                 ignore_twilight: bool = False, exposure_override: Optional[float] = None):
        super().__init__(camera_manager, corrector, config_loader, target_info,
                         filter_code='C', ignore_twilight=ignore_twilight,
                         exposure_override=exposure_override)
        self.logger = logging.getLogger(__name__)
        # Use guide camera only
        self.main_camera = camera_manager.get_guide_camera()
        if not self.main_camera:
            raise ImagingSessionError("Guide camera not found for spectroscopy")
        if not self.main_camera.connected and not self.main_camera.connect():
            raise ImagingSessionError("Failed to connect to guide camera")

    def run_simulated_acquisition(self):
        """Simulate acquisition + science frames (5x2s each)"""
        self.logger.info("Starting simulated acquisition/science sequence...")
        for phase in ["acquisition", "science"]:
            self.logger.info(f"Phase: {phase}")
            for i in range(5):
                self.logger.info(f"  Frame {i+1}/5, exposure 2s")
                time.sleep(0.1)  # fast-forward in simulation


class SpectroscopySession:
    """Manages spectroscopy sessions with optional mirror support"""

    def __init__(self, camera_manager, corrector, config_loader, telescope_driver,
                 mirror_file: str = None, ignore_twilight: bool = False,
                 dry_run: bool = False):
        self.camera_manager = camera_manager
        self.corrector = corrector
        self.config_loader = config_loader
        self.telescope_driver = telescope_driver
        self.ignore_twilight = ignore_twilight
        self.dry_run = dry_run

        self.mirror = TelescopeMirror(mirror_file) if mirror_file else None
        self.current_session = None
        self.current_target = None
        self.logger = logging.getLogger(__name__)

    def start_monitoring(self, poll_interval: float = 10.0):
        self.logger.info("="*60)
        self.logger.info("STARTING SPECTROSCOPY MONITORING")
        self.logger.info("="*60)
        if self.mirror:
            self.logger.info(f"Monitoring mirror file: {self.mirror.mirror_file}")

        try:
            while True:
                if self.mirror:
                    new_target = self.mirror.check_for_new_target()
                    if new_target:
                        self.logger.info("NEW TARGET DETECTED")
                        self.logger.info(f"RA={new_target['ra_hours']:.6f} h, Dec={new_target['dec_deg']:.6f}°")
                        if self.current_session:
                            self.logger.info("Stopping current session")
                            self.current_session = None
                        self._start_new_session(new_target)
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Monitoring interrupted by user")
        finally:
            if self.current_session:
                self.current_session = None
            self.logger.info("Spectroscopy monitoring ended")

    def _start_new_session(self, target_data: Dict[str, Any]):
        target_info = TargetInfo(
            tic_id=f"SPECTRO-{target_data['timestamp'].strftime('%Y%m%d_%H%M%S')}",
            ra_j2000_hours=target_data['ra_hours'],
            dec_j2000_deg=target_data['dec_deg'],
            gaia_g_mag=12.0,
            magnitude_source="spectro-default"
        )

        self.logger.info("Slewing telescope to target...")
        if not self.dry_run:
            if not self.telescope_driver.slew_to_coordinates(
                target_info.ra_j2000_hours, target_info.dec_j2000_deg
            ):
                self.logger.error("Failed to slew to target")
                return False

        self.logger.info("Starting spectroscopy imaging session...")
        session = SpectroscopyImagingSession(
            camera_manager=self.camera_manager,
            corrector=self.corrector,
            config_loader=self.config_loader,
            target_info=target_info,
            ignore_twilight=self.ignore_twilight
        )

        if self.dry_run:
            session.run_simulated_acquisition()
        else:
            session.start_imaging_loop(duration_hours=1)  # default 1h or configurable

        self.current_session = session
        self.current_target = target_data
        self.logger.info("Session started successfully")
        return True


def main():
    parser = argparse.ArgumentParser(description="Automated Spectroscopy")
    parser.add_argument("target_mode", choices=["tic", "coords", "mirror"])
    parser.add_argument("target_value", nargs="?", help="TIC ID, coordinates, or mirror file")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"])
    parser.add_argument("--ignore-twilight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--duration", type=float, help="Duration in hours")
    parser.add_argument("--poll-interval", type=float, default=10.0)
    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        config_loader = ConfigLoader(args.config_dir)
        config_loader.load_all_configs()

        camera_manager = None
        telescope_driver = None
        cover_driver = None
        corrector = None

        if not args.dry_run:
            logger.info("Discovering cameras...")
            camera_manager = CameraManager()
            camera_manager.discover_cameras(config_loader.get_camera_configs())

            logger.info("Connecting to telescope...")
            telescope_driver = AlpacaTelescopeDriver()
            telescope_driver.connect(config_loader.get_telescope_config())
            telescope_driver.motor_on()

            logger.info("Connecting to cover...")
            cover_driver = AlpacaCoverDriver()
            cover_driver.connect(config_loader.get_cover_config())
            cover_driver.open_cover()

            logger.info("Initializing platesolve corrector...")
            corrector = PlatesolveCorrector(telescope_driver, config_loader)

        if args.target_mode == "mirror":
            mirror_file = args.target_value or "mirror_telescope.json"
            spectro_session = SpectroscopySession(
                camera_manager, corrector, config_loader, telescope_driver,
                mirror_file=mirror_file,
                ignore_twilight=args.ignore_twilight,
                dry_run=args.dry_run
            )
            spectro_session.start_monitoring(args.poll_interval)

        else:
            # single target mode
            if args.target_mode == "tic":
                resolver = TICTargetResolver(config_loader)
                target_info = resolver.resolve_tic_id(args.target_value)
            else:
                ra, dec = map(float, args.target_value.split())
                target_info = TargetInfo(
                    tic_id=f"SPECTRO-MANUAL-{ra:.3f}h_{dec:+.3f}d",
                    ra_j2000_hours=ra,
                    dec_j2000_deg=dec,
                    gaia_g_mag=12.0,
                    magnitude_source="manual-default"
                )

            obs_checker = ObservabilityChecker(config_loader.get_config("observatory"))
            obs_status = obs_checker.check_target_observability(
                target_info.ra_j2000_hours,
                target_info.dec_j2000_deg,
                ignore_twilight=args.ignore_twilight
            )
            if not obs_status.observable and not args.dry_run:
                logger.error("Target not observable")
                return 1

            session = SpectroscopyImagingSession(
                camera_manager, corrector, config_loader, target_info,
                ignore_twilight=args.ignore_twilight
            )
            if args.dry_run:
                session.run_simulated_acquisition()
            else:
                session.start_imaging_loop(duration_hours=args.duration or 1)

        logger.info("Spectroscopy complete")
        return 0

    finally:
        if camera_manager:
            camera_manager.shutdown_all_coolers()
        if cover_driver:
            cover_driver.close_cover()
        if telescope_driver:
            telescope_driver.park()
            telescope_driver.motor_off()
            telescope_driver.disconnect()
        logger.info("Program terminated")


if __name__ == "__main__":
    sys.exit(main())