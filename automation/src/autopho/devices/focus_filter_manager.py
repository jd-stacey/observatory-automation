"""
Coordinated Filter Wheel and Focuser Management
Handles synchronized filter changes with automatic focus adjustments
"""

import logging
from typing import Optional, Tuple
from autopho.devices.drivers.alpaca_filterwheel import AlpacaFilterWheelDriver, AlpacaFilterWheelError
from autopho.devices.drivers.alpaca_focuser import AlpacaFocuserDriver, AlpacaFocuserError

logger = logging.getLogger(__name__)

class FocusFilterManagerError(Exception):
    """Exception raised for focus/filter coordination errors"""
    pass


class FocusFilterManager:
    """Manages coordinated filter wheel and focuser operations"""
    
    def __init__(self, filter_driver: Optional[AlpacaFilterWheelDriver] = None,
                 focuser_driver: Optional[AlpacaFocuserDriver] = None):
        """
        Initialize the manager with optional filter and focuser drivers
        
        Args:
            filter_driver: Connected filter wheel driver (optional)
            focuser_driver: Connected focuser driver (optional)
        """
        self.filter_driver = filter_driver
        self.focuser_driver = focuser_driver
        self.logger = logging.getLogger(__name__)
        
        # Track current state
        self.current_filter = None
        self.current_focus_position = None
        
        # Initialize current state if drivers connected
        if self.filter_driver and self.filter_driver.is_connected():
            try:
                self.current_filter = self.filter_driver.get_current_filter_name()
            except Exception as e:
                self.logger.warning(f"Could not get initial filter state: {e}")
        
        if self.focuser_driver and self.focuser_driver.is_connected():
            try:
                self.current_focus_position = self.focuser_driver.get_position()
            except Exception as e:
                self.logger.warning(f"Could not get initial focus position: {e}")
    
    def change_filter_with_focus(self, filter_code: str, 
                                  skip_if_same: bool = True) -> Tuple[bool, bool]:
        """
        Change filter and adjust focus position in one coordinated operation
        
        Args:
            filter_code: Target filter code (e.g., 'C', 'B', 'G', 'R', etc.)
            skip_if_same: Skip FILTER change if already at target, but always verify focus
            
        Returns:
            Tuple of (filter_changed, focus_changed) booleans
            
        Raises:
            FocusFilterManagerError: If operation fails critically
        """
        filter_code = filter_code.upper()
        filter_changed = False
        focus_changed = False
        
        # Check if we have required drivers
        if not self.filter_driver:
            self.logger.warning("No filter wheel driver available")
            return False, False
        
        if not self.focuser_driver:
            self.logger.warning("No focuser driver available - filter will change without focus adjustment")
        
        # Check if already at target filter
        skip_filter_change = False
        if skip_if_same:
            try:
                current = self.filter_driver.get_current_filter_name()
                current_code = None
                if current and len(current) > 0:
                    # Extract code from filter name (e.g., "Sloan r'" -> 'R')
                    for code in ['L', 'B', 'G', 'R', 'C', 'I', 'H']:
                        if code.lower() in current.lower():
                            current_code = code
                            break
                
                if current_code == filter_code:
                    self.logger.info(f"Already at filter {filter_code}, skipping filter change")
                    self.current_filter = current_code
                    skip_filter_change = True
                    # Note: We do NOT return here - we still need to check/adjust focus!
            except Exception as e:
                self.logger.warning(f"Could not check current filter: {e}")
        
        # Step 1: Change filter (if needed)
        if not skip_filter_change:
            self.logger.info(f"Changing filter to {filter_code}...")
            try:
                if self.filter_driver.change_filter(filter_code):
                    filter_changed = True
                    self.current_filter = filter_code
                    self.logger.info(f"Filter changed to {filter_code}")
                else:
                    self.logger.error(f"Filter change to {filter_code} failed")
                    raise FocusFilterManagerError(f"Failed to change filter to {filter_code}")
            except AlpacaFilterWheelError as e:
                self.logger.error(f"Filter wheel error: {e}")
                raise FocusFilterManagerError(f"Filter wheel error: {e}")
        
        # Step 2: Adjust focus if focuser available
        if self.focuser_driver and self.focuser_driver.is_connected():
            try:
                # Use the focuser's built-in filter->position mapping
                self.logger.info(f"Adjusting focus for filter {filter_code}...")
                if self.focuser_driver.set_position_from_filter(filter_code):
                    focus_changed = True
                    self.current_focus_position = self.focuser_driver.get_position()
                    self.logger.info(f"Focus adjusted to {self.current_focus_position}")
                else:
                    self.logger.warning(f"Focus adjustment failed for filter {filter_code}")
                    # Don't raise error - filter change succeeded, focus is just not optimal
            except AlpacaFocuserError as e:
                self.logger.warning(f"Focuser error during adjustment: {e}")
                # Don't raise error - filter change succeeded
            except Exception as e:
                self.logger.warning(f"Unexpected error during focus adjustment: {e}")
        else:
            self.logger.debug("No focuser available for focus adjustment")
        
        return filter_changed, focus_changed
    
    def get_current_state(self) -> dict:
        """Get current filter and focus state"""
        state = {
            'filter_code': self.current_filter,
            'focus_position': self.current_focus_position,
            'filter_available': self.filter_driver is not None and self.filter_driver.is_connected(),
            'focuser_available': self.focuser_driver is not None and self.focuser_driver.is_connected()
        }
        return state
    
    def initialize_to_clear_with_focus(self) -> bool:
        """Initialize to Clear filter with appropriate focus"""
        self.logger.info("Initializing to Clear filter with focus adjustment...")
        try:
            filter_changed, focus_changed = self.change_filter_with_focus('C', skip_if_same=False)
            if filter_changed:
                self.logger.info("Initialized to Clear filter successfully")
                return True
            else:
                self.logger.warning("Failed to initialize to Clear filter")
                return False
        except FocusFilterManagerError as e:
            self.logger.error(f"Initialization failed: {e}")
            return False