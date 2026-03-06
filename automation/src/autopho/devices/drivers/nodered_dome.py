# Need to:
#   * reconfigure all commands to check for in between statuses like already_opening, already_closing etc
#   * double-check all http response nodes are now in place (can ignore the UI ones - not relevant for script calls)
#   * consider error/catch nodes but maybe not necessary


import time
import logging
import requests
from typing import Optional, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)


class DomeError(Exception):
    pass


class DomeDriver:
    """
    Driver for dome control via Node-RED HTTP endpoints.
    
    Communicates with the Node-RED instance running on the dome TCU over the
    observatory network. Node-RED translates HTTP commands to serial commands
    on COM3 (9600-8N1) to the dome hardware.
    
    Serial state characters from dome hardware:
        "0" = both panels closed
        "1" = right open, left closed
        "2" = left open, right closed
        "3" = both panels open
        "a" = left panel opening
        "A" = left panel closing
        "b" = right panel opening
        "B" = right panel closing
        "x" = left already open
        "X" = left already closed
        "y" = right already open
        "Y" = right already closed

    Known HTTP endpoints (all require HTTP response nodes):
        GET  /dome/state            - read-only status (custom addition - http response node already added)
        PUT  /dome/true             - open both panels
        PUT  /dome/false            - close both panels
        PUT  /dome/left/true        - open left panel
        PUT  /dome/left/false       - close left panel
        PUT  /dome/right/true       - open right panel
        PUT  /dome/right/false      - close right panel
        PUT  /dome/abort            - set abort flag (clears after 10s)
        PUT  /dome/locked           - lock dome (TBC - confirm with team)
        PUT  /dome/reset            - reset motor (TBC - confirm with team)
    """

    # Panel state constants (as returned by Node-RED global.dome)
    # These are defined by the dome hardware serial protocol - not configurable
    STATE_OPEN = "open"
    STATE_CLOSED = "closed"
    STATE_OPENING = "opening"
    STATE_CLOSING = "closing"
    STATE_ALREADY_OPEN = "already_open"
    STATE_ALREADY_CLOSED = "already_closed"
    STATE_UNKNOWN = "unknown"

    def __init__(self):
        self.config = None
        self.base_url = None
        self.connected = False
        self.dome_id = None

        # Timeouts - set from devices.yaml in connect(), defaults provided here
        self.timeout_status = 5         # status reads (s)
        self.timeout_abort = 15         # abort has 10s delay in Node-RED flow (s)
        self.timeout_move = 60          # max wait for panel movement to complete (s)
        self.timeout_command = 5        # general command timeout (s)
        self.poll_interval = 2.0        # polling interval during movement waits (s)
        self.max_retries = 3            # retries on failed status reads

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, config: Dict[str, Any]) -> bool:
        """Connect to the dome TCU Node-RED instance and verify reachability."""
        try:
            self.config = config

            # Network
            host = config.get('host', '192.168.249.27')
            port = config.get('port', 1880)
            self.base_url = f"http://{host}:{port}"
            self.dome_id = config.get('dome_id', 'DOME')

            # Timeouts and polling - all from devices.yaml with safe defaults
            self.timeout_status  = config.get('timeout_status',  5)
            self.timeout_abort   = config.get('timeout_abort',   15)
            self.timeout_move    = config.get('timeout_move',    60)
            self.timeout_command = config.get('timeout_command', 5)
            self.poll_interval   = config.get('poll_interval',   2.0)
            self.max_retries     = config.get('max_retries',     3)

            logger.info(f"Connecting to dome {self.dome_id} via Node-RED at {self.base_url}")

            # Verify reachability by reading dome state
            state = self._get_raw_state()
            if state is not None:
                self.connected = True
                logger.info(f"Successfully connected to dome TCU. "
                            f"Left: {state.get('left', '?')} | "
                            f"Right: {state.get('right', '?')}")
                return True
            else:
                logger.error("Dome TCU reachable but returned no state data")
                self.connected = False
                return False

        except Exception as e:
            logger.error(f"Dome connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the dome TCU."""
        try:
            self.connected = False
            self.base_url = None
            logger.info("Dome driver disconnected")
            return True
        except Exception as e:
            logger.error(f"Dome disconnect error: {e}")
            return False

    def is_connected(self) -> bool:
        """Check whether the dome TCU is reachable and returning valid state."""
        if not self.connected or not self.base_url:
            return False
        try:
            state = self._get_raw_state()
            return state is not None
        except Exception as e:
            logger.error(f"Dome connection check error: {e}")
            return False

    # ------------------------------------------------------------------
    # Status / State
    # ------------------------------------------------------------------

    def _get_raw_state(self) -> Optional[Dict[str, Any]]:
        """
        Internal - fetch raw dome state dict from Node-RED /dome/state endpoint.
        Returns None on failure.
        
        Expected response:
            {
                "left": "closed",
                "right": "closed",
                "closed": true,
                "lastChars": ["0", "0", ...]
            }
        """
        try:
            r = requests.get(
                f"{self.base_url}/dome/state",
                timeout=self.timeout_status
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            logger.error("Dome state request timed out")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Dome state connection error - TCU unreachable")
            return None
        except requests.exceptions.JSONDecodeError:
            logger.error("Dome state returned invalid JSON")
            return None
        except Exception as e:
            logger.error(f"Dome state request failed: {e}")
            return None

    def get_state(self) -> Dict[str, Any]:
        """
        Get current dome state. Returns a dict with left, right, closed fields.
        Returns a safe default dict with STATE_UNKNOWN values on failure.
        """
        if not self.connected:
            raise DomeError("Cannot get state - dome not connected")

        state = self._get_raw_state()
        if state is None:
            return {
                "left": self.STATE_UNKNOWN,
                "right": self.STATE_UNKNOWN,
                "closed": False,
                "lastChars": []
            }
        return state

    def get_left_state(self) -> str:
        """Get the current state of the left panel."""
        return self.get_state().get('left', self.STATE_UNKNOWN)

    def get_right_state(self) -> str:
        """Get the current state of the right panel."""
        return self.get_state().get('right', self.STATE_UNKNOWN)

    def is_closed(self) -> bool:
        """Returns True only if both panels are confirmed closed."""
        return self.get_state().get('closed', False)

    def is_open(self) -> bool:
        """Returns True only if both panels are confirmed open."""
        state = self.get_state()
        return (state.get('left') == self.STATE_OPEN and
                state.get('right') == self.STATE_OPEN)

    def is_moving(self) -> bool:
        """Returns True if either panel is currently opening or closing."""
        state = self.get_state()
        moving_states = {self.STATE_OPENING, self.STATE_CLOSING}
        return (state.get('left') in moving_states or
                state.get('right') in moving_states)

    def get_dome_info(self) -> Dict[str, Any]:
        """Get full dome status info dict, matching telescope driver pattern."""
        if not self.connected:
            return {'connected': False}
        try:
            state = self.get_state()
            return {
                "connected": True,
                "left": state.get('left', self.STATE_UNKNOWN),
                "right": state.get('right', self.STATE_UNKNOWN),
                "closed": state.get('closed', False),
                "is_open": self.is_open(),
                "is_moving": self.is_moving(),
                "last_serial_chars": state.get('lastChars', [])
            }
        except Exception as e:
            logger.error(f"Failed to get dome info: {e}")
            return {"connected": True, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal HTTP command helper
    # ------------------------------------------------------------------

    def _send_command(self, endpoint: str, timeout: Optional[int] = None) -> bool:
        """
        Internal - send a PUT command to a Node-RED dome endpoint.
        Returns True on HTTP 200, False on any failure.
        
        NOTE: Command endpoints currently have no HTTP response nodes wired
        in Node-RED - they will hang until response nodes are added by the team.
        Do not call movement commands until this is confirmed resolved.
        """
        if not self.connected:
            raise DomeError(f"Cannot send command {endpoint} - dome not connected")
        if timeout is None:
            timeout = self.timeout_command
        try:
            r = requests.put(
                f"{self.base_url}{endpoint}",
                timeout=timeout
            )
            r.raise_for_status()
            logger.debug(f"Command {endpoint} → {r.status_code}")
            return r.status_code == 200
        except requests.exceptions.Timeout:
            logger.error(f"Command {endpoint} timed out after {timeout}s")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"Command {endpoint} connection error")
            return False
        except Exception as e:
            logger.error(f"Command {endpoint} failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Polling helper
    # ------------------------------------------------------------------

    def _wait_for_state(
        self,
        target_left: str,
        target_right: str,
        timeout: Optional[int] = None,
        poll_interval: Optional[float] = None
    ) -> bool:
        """
        Poll dome state until both panels reach target states or timeout.
        Used after issuing movement commands to confirm completion.
        """
        if timeout is None:
            timeout = self.timeout_move
        if poll_interval is None:
            poll_interval = self.poll_interval
        logger.info(f"Waiting for dome state: left={target_left}, right={target_right}")
        start = time.time()
        while time.time() - start < timeout:
            state = self.get_state()
            left = state.get('left')
            right = state.get('right')
            logger.debug(f"  Dome state: left={left} | right={right}")
            if left == target_left and right == target_right:
                logger.info("Target dome state reached")
                return True
            time.sleep(poll_interval)
        logger.warning(f"Dome state timeout after {timeout}s - "
                       f"left={left}, right={right}")
        return False

    # ------------------------------------------------------------------
    # Dome commands
    # NOTE: These will hang until HTTP response nodes are added to Node-RED.
    #       Confirm with team before calling any of these methods.
    #       Pre/post state checks are included for safety.
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """
        Open both dome panels.
        Checks current state before commanding and polls for completion.
        """
        if not self.is_connected():
            logger.error("Cannot open dome - not connected")
            return False
        try:
            state = self.get_state()
            if state.get('closed') is False and self.is_open():
                logger.info("Dome already open - no action taken")
                return True

            logger.info("Opening dome (both panels)...")
            success = self._send_command("/dome/true")
            if not success:
                return False
            return self._wait_for_state(self.STATE_OPEN, self.STATE_OPEN)

        except Exception as e:
            logger.error(f"Dome open failed: {e}")
            return False

    def close(self) -> bool:
        """
        Close both dome panels.
        Checks current state before commanding and polls for completion.
        """
        if not self.is_connected():
            logger.error("Cannot close dome - not connected")
            return False
        try:
            if self.is_closed():
                logger.info("Dome already closed - no action taken")
                return True

            logger.info("Closing dome (both panels)...")
            success = self._send_command("/dome/false")
            if not success:
                return False
            return self._wait_for_state(self.STATE_CLOSED, self.STATE_CLOSED)

        except Exception as e:
            logger.error(f"Dome close failed: {e}")
            return False

    def open_left(self) -> bool:
        """Open left panel only."""
        if not self.is_connected():
            logger.error("Cannot open left panel - not connected")
            return False
        try:
            if self.get_left_state() == self.STATE_OPEN:
                logger.info("Left panel already open - no action taken")
                return True

            logger.info("Opening left panel...")
            success = self._send_command("/dome/left/true")
            if not success:
                return False
            right_state = self.get_right_state()    # right panel unchanged
            return self._wait_for_state(self.STATE_OPEN, right_state)

        except Exception as e:
            logger.error(f"Open left panel failed: {e}")
            return False

    def close_left(self) -> bool:
        """Close left panel only."""
        if not self.is_connected():
            logger.error("Cannot close left panel - not connected")
            return False
        try:
            if self.get_left_state() == self.STATE_CLOSED:
                logger.info("Left panel already closed - no action taken")
                return True

            logger.info("Closing left panel...")
            success = self._send_command("/dome/left/false")
            if not success:
                return False
            right_state = self.get_right_state()    # right panel unchanged
            return self._wait_for_state(self.STATE_CLOSED, right_state)

        except Exception as e:
            logger.error(f"Close left panel failed: {e}")
            return False

    def open_right(self) -> bool:
        """Open right panel only."""
        if not self.is_connected():
            logger.error("Cannot open right panel - not connected")
            return False
        try:
            if self.get_right_state() == self.STATE_OPEN:
                logger.info("Right panel already open - no action taken")
                return True

            logger.info("Opening right panel...")
            success = self._send_command("/dome/right/true")
            if not success:
                return False
            left_state = self.get_left_state()      # left panel unchanged
            return self._wait_for_state(left_state, self.STATE_OPEN)

        except Exception as e:
            logger.error(f"Open right panel failed: {e}")
            return False

    def close_right(self) -> bool:
        """Close right panel only."""
        if not self.is_connected():
            logger.error("Cannot close right panel - not connected")
            return False
        try:
            if self.get_right_state() == self.STATE_CLOSED:
                logger.info("Right panel already closed - no action taken")
                return True

            logger.info("Closing right panel...")
            success = self._send_command("/dome/right/false")
            if not success:
                return False
            left_state = self.get_left_state()      # left panel unchanged
            return self._wait_for_state(left_state, self.STATE_CLOSED)

        except Exception as e:
            logger.error(f"Close right panel failed: {e}")
            return False

    def abort(self) -> bool:
        """
        Send abort command to dome.
        Sets dome_abort global flag in Node-RED for 10 seconds, blocking movement.
        Note: Node-RED flow has a 10s delay before returning 200.
        """
        if not self.is_connected():
            logger.error("Cannot abort - dome not connected")
            return False
        try:
            logger.warning("Sending dome abort command...")
            return self._send_command("/dome/abort", timeout=self.timeout_abort)
        except Exception as e:
            logger.error(f"Dome abort failed: {e}")
            return False

    def reset_motor(self) -> bool:
        """
        Reset dome motor.
        NOTE: Confirm exact hardware behaviour with team before using.
        """
        if not self.is_connected():
            logger.error("Cannot reset motor - dome not connected")
            return False
        try:
            logger.warning("Sending dome motor reset command...")
            return self._send_command("/dome/reset")
        except Exception as e:
            logger.error(f"Dome motor reset failed: {e}")
            return False

    def set_locked(self, locked: bool = True) -> bool:
        """
        Set dome locked state.
        NOTE: Exact behaviour of /dome/locked endpoint TBC - confirm with team.
        """
        if not self.is_connected():
            logger.error("Cannot set lock - dome not connected")
            return False
        try:
            logger.info(f"Setting dome locked = {locked}")
            # TODO: confirm endpoint and method with team
            return self._send_command("/dome/locked")
        except Exception as e:
            logger.error(f"Dome lock command failed: {e}")
            return False