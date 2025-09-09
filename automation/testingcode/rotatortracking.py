#!/usr/bin/env python3
"""
rotator_track_test.py

Command a field de-rotator (Alpaca Rotator) to track a fixed RA/Dec by
following the parallactic angle in real time.

Works with older Astropy (no angle_utilities / no SkyCoord.parallactic_angle).
"""

import time
import logging
import threading
import numpy as np
from typing import Dict, Any, Tuple
from datetime import datetime, timezone

# ----- Alpaca Rotator import -----
try:
    from alpaca.rotator import Rotator
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# ----- Astropy imports (old-version friendly) -----
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, Angle

logger = logging.getLogger(__name__)

class AlpacaRotatorError(Exception):
    pass

class AlpacaRotatorDriver:
    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise AlpacaRotatorError("Alpaca library not available - please install")
        self.rotator = None
        self.config = None
        self.connected = False

        # tracking runtime fields
        self._track_stop_evt = None
        self._track_thread = None
        self._tracking_cfg = {}

        # defaults for limits (overridden by connect(config))
        self.min_limit = 0.0
        self.max_limit = 360.0

    # ---------------- Connection & basic ops ----------------

    def connect(self, config: Dict[str, Any]) -> bool:
        try:
            self.config = config
            address = config.get('address', '127.0.0.1:11112')
            device_number = config.get('device_number', 0)
            mechanical_limits = config.get('mechanical_limits', {})
            self.min_limit = mechanical_limits.get('min_deg', 94.0)
            self.max_limit = mechanical_limits.get('max_deg', 320.0)

            logger.debug(f"Connecting to Alpaca Rotator at {address}, device {device_number}")
            self.rotator = Rotator(address=address, device_number=device_number)

            if not self.is_connected():
                self.rotator.Connected = True
                time.sleep(0.5)

            if self.is_connected():
                rotator_name = self.rotator.Name
                logger.info(f"Connected to rotator: {rotator_name}")
                self.connected = True
                current_pos = self.get_position()
                logger.info(f"Current rotator position: {current_pos:.2f}°")
                logger.info(f"Mechanical limits: {self.min_limit:.1f}° to {self.max_limit:.1f}°")
                return True
            else:
                logger.error("Failed to establish rotator connection")
                return False
        except Exception as e:
            logger.error(f"Rotator connection error: {e}")
            self.connected = False
            return False

    def disconnect(self) -> bool:
        try:
            self.stop_tracking()
            if self.rotator and self.connected:
                self.rotator.Connected = False
                logger.info('Rotator disconnected')
            self.connected = False
            return True
        except Exception as e:
            logger.error(f"Rotator disconnect error: {e}")
            return False

    def is_connected(self) -> bool:
        try:
            if not self.rotator:
                return False
            _ = self.rotator.Position  # probe property to verify comms
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Rotator connection test failed: {e}")
            self.connected = False
            return False

    def get_position(self) -> float:
        if not self.is_connected():
            raise AlpacaRotatorError("Cannot get position - rotator not connected")
        try:
            position = self.rotator.Position
            logger.debug(f"Current rotator position: {position:.2f}°")
            return position
        except Exception as e:
            raise AlpacaRotatorError(f"Failed to get position: {e}")

    # ---------------- Limits & safety ----------------

    def check_position_safety(self, target_position: float) -> Tuple[bool, str]:
        limits_config = self.config.get('limits', {})
        warning_margin = limits_config.get('warning_margin_deg', 30.0)
        emergency_margin = limits_config.get('emergency_margin_deg', 10.0)

        if target_position <= (self.min_limit + emergency_margin):
            return False, (f"Position {target_position:.2f}° within emergency margin "
                           f"({emergency_margin}°) of min limit {self.min_limit}°")
        if target_position >= (self.max_limit - emergency_margin):
            return False, (f"Position {target_position:.2f}° within emergency margin "
                           f"({emergency_margin}°) of max limit {self.max_limit}°")

        if target_position <= (self.min_limit + warning_margin):
            return True, (f"Warning: {target_position:.2f}° approaching minimum limit "
                          f"{self.min_limit}°")
        if target_position >= (self.max_limit - warning_margin):
            return True, (f"Warning: {target_position:.2f}° approaching maximum limit "
                          f"{self.max_limit}°")
        return True, "Position is safe"

    def move_to_position(self, position_deg: float) -> bool:
        if not self.is_connected():
            logger.error("Cannot move - rotator not connected")
            return False
        try:
            is_safe, safety_msg = self.check_position_safety(position_deg)
            if not is_safe:
                logger.error(f"Refusing unsafe move: {safety_msg}")
                return False
            elif "Warning" in safety_msg:
                logger.warning(safety_msg)

            logger.info(f"Moving rotator to position: {position_deg:.2f}°")
            self.rotator.MoveAbsolute(position_deg)

            while self.rotator.IsMoving:
                logger.debug(f"    Rotating... currently at {self.rotator.Position:.2f}°")
                time.sleep(0.5)

            settle_time = self.config.get('settle_time', 1.0)
            logger.info(f"Rotation complete, settling for {settle_time} s")
            time.sleep(settle_time)

            final_pos = self.get_position()
            logger.info(f"Rotator positioned at: {final_pos:.2f}°")
            return True
        except Exception as e:
            logger.error(f"Rotation failed: {e}")
            return False

    def initialize_position(self) -> bool:
        if not self.is_connected():
            logger.error("Cannot initialize - rotator not connected")
            return False
        try:
            init_config = self.config.get('initialization', {})
            strategy = init_config.get('strategy', 'midpoint')
            current_pos = self.get_position()

            if strategy == 'midpoint':
                target_pos = (self.min_limit + self.max_limit) / 2.0
                logger.debug(f"Initializing to midpoint position: {target_pos:.2f}°")
            elif strategy == 'safe_position':
                target_pos = init_config.get('safe_position_deg', 220.0)
                logger.debug(f"Initializing to configured safe position: {target_pos:.2f}°")
            else:
                logger.debug(f"No initialization needed, staying at {current_pos:.2f}°")
                return True

            if abs(current_pos - target_pos) < 2.0:
                logger.info(f"Already within 2° of target position ({current_pos:.2f}°), no move")
                return True

            is_safe, safety_msg = self.check_position_safety(target_pos)
            if not is_safe:
                logger.error(f"Cannot initialize to unsafe position: {safety_msg}")
                return False
            return self.move_to_position(target_pos)
        except Exception as e:
            logger.error(f"Rotator initialization failed: {e}")
            return False

    # ---------------- Tracking helpers ----------------

    def _compute_parallactic_deg(self,
                                 ra_deg: float,
                                 dec_deg: float,
                                 lon_deg: float,
                                 lat_deg: float,
                                 alt_m: float) -> float:
        """
        Parallactic angle q in degrees (old-Astropy compatible).
        tan(q) = sin(HA) / (tan(lat)*cos(dec) - sin(dec)*cos(HA))
        """
        # Use Astropy Time for LST (works across versions)
        now = Time.now()  # UTC by default
        coord = SkyCoord(ra=ra_deg*u.deg, dec=dec_deg*u.deg, frame="icrs")
        loc = EarthLocation(lon=lon_deg*u.deg, lat=lat_deg*u.deg, height=alt_m*u.m)

        lst = now.sidereal_time('apparent', longitude=loc.lon)  # Angle
        ha = (lst - coord.ra).wrap_at(360*u.deg)                # hour angle (Angle)

        ha_rad  = ha.radian
        dec_rad = coord.dec.radian
        lat_rad = loc.lat.radian

        q = np.arctan2(np.sin(ha_rad),
                       np.tan(lat_rad)*np.cos(dec_rad) - np.sin(dec_rad)*np.cos(ha_rad))
        # normalize to [0, 360)
        return (np.degrees(q) % 360.0)

    def _demand_angle_deg(self,
                          ra_deg: float,
                          dec_deg: float,
                          lon_deg: float,
                          lat_deg: float,
                          alt_m: float,
                          pa_offset_deg: float = 0.0,
                          flip_sign: bool = False) -> float:
        pa_deg = self._compute_parallactic_deg(ra_deg, dec_deg, lon_deg, lat_deg, alt_m)
        angle = pa_offset_deg + (-pa_deg if flip_sign else pa_deg)
        return angle % 360.0

    def start_tracking(self,
                       target_ra_deg: float,
                       target_dec_deg: float,
                       site_lon_deg: float,
                       site_lat_deg: float,
                       site_alt_m: float,
                       pa_offset_deg: float = 0.0,
                       flip_sign: bool = False,
                       update_hz: float = 4.0,
                       min_command_step_deg: float = 0.05) -> bool:
        if not self.is_connected():
            logger.error("Cannot start rotator tracking - not connected")
            return False

        self._tracking_cfg = dict(
            ra_deg=target_ra_deg, dec_deg=target_dec_deg,
            lon_deg=site_lon_deg, lat_deg=site_lat_deg, alt_m=site_alt_m,
            pa_offset_deg=pa_offset_deg, flip_sign=flip_sign,
            update_dt=max(0.001, 1.0/update_hz), min_step=min_command_step_deg
        )

        # stop any existing tracking thread
        self.stop_tracking()
        self._track_stop_evt = threading.Event()
        self._track_thread = threading.Thread(target=self._tracking_loop,
                                              name="RotatorTracking", daemon=True)
        self._track_thread.start()
        logger.info("Rotator tracking started")
        return True

    def stop_tracking(self) -> None:
        evt = getattr(self, "_track_stop_evt", None)
        th  = getattr(self, "_track_thread", None)
        if evt is not None:
            evt.set()
        if th is not None:
            th.join(timeout=1.0)
        self._track_stop_evt = None
        self._track_thread = None

    def _tracking_loop(self):
        cfg = self._tracking_cfg
        last_cmd = None

        while self._track_stop_evt and not self._track_stop_evt.is_set():
            try:
                if not self.is_connected():
                    logger.warning("Rotator disconnected during tracking; pausing updates")
                    time.sleep(cfg["update_dt"])
                    continue

                demand = self._demand_angle_deg(cfg["ra_deg"], cfg["dec_deg"],
                                                cfg["lon_deg"], cfg["lat_deg"], cfg["alt_m"],
                                                cfg["pa_offset_deg"], cfg["flip_sign"])

                is_safe, msg = self.check_position_safety(demand)
                if not is_safe:
                    logger.error(f"Tracking demand unsafe ({demand:.2f}°): {msg}")
                else:
                    if "Warning" in msg:
                        logger.warning(msg)

                    # wrap-aware delta between last command and demand
                    if last_cmd is None:
                        delta = 999.0
                    else:
                        delta = abs((demand - last_cmd + 540) % 360 - 180)

                    if delta >= cfg["min_step"]:
                        self.rotator.MoveAbsolute(demand)
                        last_cmd = demand
                        logger.debug(f"Track cmd: {demand:.3f}°")
            except Exception as e:
                logger.error(f"Rotator tracking loop error: {e}")

            time.sleep(cfg["update_dt"])

    # ---------------- Optional helpers ----------------

    def is_moving(self) -> bool:
        if not self.is_connected():
            return False
        try:
            return self.rotator.IsMoving
        except Exception as e:
            logger.error(f"Cannot check moving status: {e}")
            return False

    def halt(self) -> bool:
        if not self.is_connected():
            logger.warning("Cannot halt - rotator not connected")
            return False
        try:
            logger.warning("Halting rotator...")
            self.rotator.Halt()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Halt failed: {e}")
            return False

    def get_rotator_info(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {'connected': False}
        try:
            current_pos = self.get_position()
            is_safe, safety_status = self.check_position_safety(current_pos)
            info = {
                'connected': True,
                "name": self.rotator.Name,
                "description": getattr(self.rotator, 'Description', 'Unknown'),
                "position_deg": current_pos,
                "is_moving": self.rotator.IsMoving,
                'can_reverse': getattr(self.rotator, 'CanReverse', False),
                "mechanical_limits": {'min': self.min_limit, 'max': self.max_limit},
                "position_safe": is_safe,
                "safety_status": safety_status
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get rotator info: {e}")
            return {'connected': True, "error": str(e)}


# ---------------- CLI test harness ----------------
def _parse_ra_to_deg(s: str) -> float:
    """
    Accepts:
      - decimal hours (e.g., '12.5')
      - sexagesimal 'hh:mm:ss' or 'hh mm ss'
      - decimal degrees with suffix 'deg' (e.g., '187.5deg')
    Returns degrees (0..360).
    """
    s = s.strip().lower()
    if s.endswith("deg"):
        ang = Angle(s.replace("deg", "").strip(), unit=u.deg)
        return ang.wrap_at(360*u.deg).degree
    # try hours (sexagesimal or decimal)
    try:
        ang = Angle(s, unit=u.hourangle)
        return ang.wrap_at(360*u.deg).degree
    except Exception:
        # try degrees as plain number
        ang = Angle(float(s), unit=u.deg)
        return ang.wrap_at(360*u.deg).degree

def _parse_dec_to_deg(s: str) -> float:
    """
    Accepts:
      - decimal degrees (e.g., '-23.5')
      - sexagesimal '±dd:mm:ss' or '±dd mm ss'
    Returns degrees (-90..+90).
    """
    return Angle(s.strip(), unit=u.deg).degree


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S"
    )

    parser = argparse.ArgumentParser(
        description="Quick test: de-rotate (track) for a fixed RA/Dec using an Alpaca Rotator."
    )
    # Rotator / Alpaca
    parser.add_argument("--address", default="127.0.0.1:11112",
                        help="Alpaca rotator address (host:port)")
    parser.add_argument("--device-number", type=int, default=0,
                        help="Rotator device number")
    parser.add_argument("--min-deg", type=float, default=94.0,
                        help="Mechanical min limit (deg)")
    parser.add_argument("--max-deg", type=float, default=320.0,
                        help="Mechanical max limit (deg)")

    # Site
    parser.add_argument("--lon", required=True, type=float,
                        help="Site longitude (deg, +East)")
    parser.add_argument("--lat", required=True, type=float,
                        help="Site latitude (deg, +North)")
    parser.add_argument("--alt", type=float, default=700.0,
                        help="Site altitude (m)")

    # Target
    parser.add_argument("--ra", required=True,
                        help="Target RA (e.g. '12:34:56', '12.5', or '187.5deg')")
    parser.add_argument("--dec", required=True,
                        help="Target Dec (e.g. '-23:45:00' or '-23.75')")

    # Tracking params
    parser.add_argument("--pa-offset", type=float, default=0.0,
                        help="Instrument PA offset to add (deg)")
    parser.add_argument("--flip-sign", action="store_true",
                        help="Invert sign of parallactic angle")
    parser.add_argument("--hz", type=float, default=4.0,
                        help="Update frequency (Hz)")
    parser.add_argument("--min-step", type=float, default=0.01,
                        help="Min command step (deg)")

    # Logging
    parser.add_argument("--debug", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Build config and connect
    driver = AlpacaRotatorDriver()
    ok = driver.connect({
        "address": args.address,
        "device_number": args.device_number,
        "mechanical_limits": {"min_deg": args.min_deg, "max_deg": args.max_deg},
        "limits": {"warning_margin_deg": 30.0, "emergency_margin_deg": 10.0},
        "initialization": {"strategy": "none"},
        "settle_time": 1.0,
    })
    if not ok:
        sys.exit("Failed to connect to rotator")

    # Parse target coords
    ra_deg  = _parse_ra_to_deg(args.ra)
    dec_deg = _parse_dec_to_deg(args.dec)
    logger.info(f"Target ICRS: RA={ra_deg/15.0:.6f} h ({ra_deg:.6f} deg), Dec={dec_deg:.6f} deg")

    # Start tracking
    driver.start_tracking(
        target_ra_deg=ra_deg,
        target_dec_deg=dec_deg,
        site_lon_deg=args.lon,
        site_lat_deg=args.lat,
        site_alt_m=args.alt,
        pa_offset_deg=args.pa_offset,
        flip_sign=args.flip_sign,
        update_hz=args.hz,
        min_command_step_deg=args.min_step
    )

    try:
        logger.info("Tracking? Press Ctrl+C to stop.")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Stopping tracking (Ctrl+C)")
    finally:
        driver.stop_tracking()
        driver.disconnect()
