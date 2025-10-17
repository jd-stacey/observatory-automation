'''For Alpaca connection and operation of the filter wheel - position, names, codes, change filter etc.
Will also interact with the joint/coordinated focus_filter_manager.py which jointly operates the filter wheel and the focuser'''

import time
import logging
from typing import Dict, Any, Optional

try:
    from alpaca.filterwheel import FilterWheel
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
#Setup logging
logger = logging.getLogger(__name__)

class AlpacaFilterWheelError(Exception):
    pass

# Set up main driver class
class AlpacaFilterWheelDriver:
    
    def __init__(self):
        # Ensure alpyca is installed
        if not ALPACA_AVAILABLE:
            raise AlpacaFilterWheelError("Alpaca library not available - please install")
        self.filter_wheel = None
        self.config = None
        self.connected = False
        self.filter_names = []
        self.filter_map = {}
        
    def connect(self, config: Dict[str, Any]) -> bool:
        '''Connect to the filter wheel using info (address etc) from devices.yaml'''
        try:
            self.config = config
            address = self.config.get('address', '127.0.0.1:11113')
            device_number = self.config.get('device_number', 0)
            logger.debug(f"Connecting to filter wheel at {address}, device {device_number}")
            
            self.filter_wheel = FilterWheel(address=address, device_number=device_number)
            
            # .Connected is generally reliable for the filter wheel, so we can use that
            # If its not showing as .Connected - set it to True
            if not self.filter_wheel.Connected:
                self.filter_wheel.Connected = True
                time.sleep(1)
                
            self.connected = self.filter_wheel.Connected
            
            # Get the filter names and build the filter map
            if self.connected:
                self.filter_names = self.filter_wheel.Names
                self._build_filter_map()
                logger.debug(f"Connected to filter wheel: {len(self.filter_names)} filters")
                logger.debug(f"Filters: {self.filter_names}")
                
            return self.connected
        except Exception as e:
            logger.error(f"Filter wheel connection failed: {e}")
            return False
        
    def _build_filter_map(self):
        '''Ensures entry of filter codes can be lower or upper case'''
        code_map = ['L', 'B', 'G', 'R', 'C', 'I', 'H']
        self.filter_map = {}
        
        for i, code in enumerate(code_map[:len(self.filter_names)]):
            self.filter_map[code.upper()] = i
            self.filter_map[code.lower()] = i
            
        logger.debug(f"Filter map: {self.filter_map}")
        
    def disconnect(self) -> bool:
        '''
        Disconnect from the filter wheel - This is important to use judiciously as the port the filter wheel is on 
        allows only one connection at a time - any other connection attempt will disrupt telescope operations
        '''
        try:
            if self.filter_wheel and self.connected:
                # Set the .Connected status to False
                self.filter_wheel.Connected = False
                self.connected = False
                logger.info("Disconnected from filter wheel")
            return True
        except Exception as e:
            logger.error(f"Filter wheel disconnect failed: {e}")
            return False
        
    def is_connected(self) -> bool:
        return self.connected
    
    def get_current_position(self) -> int:
        '''Get the current position of the filter wheel - starts from 0'''
        if not self.connected:
            raise AlpacaFilterWheelError("Cannot get position - filter wheel not connected")
        return self.filter_wheel.Position   # Returns the Alpaca call .Position
    
    def get_current_filter_name(self) -> str:
        '''Get the name of the filter at the current position - from the list of filter names'''
        pos = self.get_current_position()
        if 0 <= pos < len(self.filter_names):
            return self.filter_names[pos]
        return f"Position {pos}"
    
    def change_filter(self, filter_code: str) -> bool:
        '''Set the position of the filter based on a (usually user-entered) single letter filter code'''
        if not self.connected:
            logger.error('Cannot change filter - not connected')
            return False
        try:
            # Ensure code is within filter  map
            if filter_code.upper() not in self.filter_map:
                logger.error(f"Invalid filter code: {filter_code}")
                return False
            # Check if filter wheel is already at desired position - if it is, log and return True
            target_pos = self.filter_map[filter_code.upper()]
            current_pos = self.get_current_position()
            
            if current_pos == target_pos:
                logger.info(f"Filter already at {filter_code.upper()}: {self.filter_names[target_pos]}")
                return True
            
            logger.info(f"Changing filter from {self.get_current_filter_name()} to {filter_code.upper()}: {self.filter_names[target_pos]}")
            
            # If not at desired position - change the filter wheel to that position
            self.filter_wheel.Position = target_pos
            # Allow up to 45s, though driver will likely time itself out much quicker, usually within 5s
            timeout = time.time() + 45.0
            # Wait until the filter wheel is in the desired position
            while self.filter_wheel.Position != target_pos:
                if time.time() > timeout:
                    logger.error(f"Filter change timed out after {45} seconds")
                    return False
                time.sleep(0.5)
                
            # Settle if required (from devices.yaml)
            settle_time = self.config.get('settle_time', 2.0)
            time.sleep(settle_time)
            
            logger.debug(f"Filter changed successfully to {filter_code.upper()}")
            return True
        except Exception as e:
            logger.error(f"Filter change failed: {e}")
            return False
        
    def initialize_to_clear(self) -> bool:
        '''Set the default position of the filter wheel to Clear'''
        return self.change_filter('C')
    
    def get_filter_info(self) -> Dict[str, Any]:
        '''Get information about the filter wheel (position, name, filters etc)'''
        if not self.connected:
            return {'connected': False}
        try:
            pos = self.get_current_position()
            return {
                'connected': True,
                'position': pos,
                'filter_name': self.get_current_filter_name(),
                'total_filters': len(self.filter_names),
                'all_filters': self.filter_names
            }
        except Exception as e:
            return {'connected': True, 'error': str(e)}
        
    def get_filter_code_from_position(self, position: int) -> Optional[str]:
        '''Get the position number (starts from 0) from the filter code - matches to the filter code map'''
        code_map = ['L', 'B', 'G', 'R', 'C', 'I', 'H']
        if 0 <= position < len(code_map):
            return code_map[position]
        return None
        
    
        
                
            
        