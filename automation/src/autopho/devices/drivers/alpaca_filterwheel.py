import time
import logging
from typing import Dict, Any, Optional

try:
    from alpaca.filterwheel import FilterWheel
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class AlpacaFilterWheelError(Exception):
    pass

class AlpacaFilterWheelDriver:
    
    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise AlpacaFilterWheelError("Alpaca library not available - please install")
        self.filter_wheel = None
        self.config = None
        self.connected = False
        self.filter_names = []
        self.filter_map = {}
        
    def connect(self, config: Dict[str, Any]) -> bool:
        try:
            self.config = config
            address = self.config.get('address', '127.0.0.1:11113')
            device_number = self.config.get('device_number', 0)
            logger.debug(f"Connecting to filter wheel at {address}, device {device_number}")
            
            self.filter_wheel = FilterWheel(address=address, device_number=device_number)
            
            if not self.filter_wheel.Connected:
                self.filter_wheel.Connected = True
                time.sleep(1)
                
            self.connected = self.filter_wheel.Connected
            
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
        code_map = ['C', 'B', 'G', 'R', 'L', 'I', 'H']
        self.filter_map = {}
        
        for i, code in enumerate(code_map[:len(self.filter_names)]):
            self.filter_map[code.upper()] = i
            self.filter_map[code.lower()] = i
            
        logger.debug(f"Filter map: {self.filter_map}")
        
    def disconnect(self) -> bool:
        try:
            if self.filter_wheel and self.connected:
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
        if not self.connected:
            raise AlpacaFilterWheelError("Cannot get position - filter wheel not connected")
        return self.filter_wheel.Position
    
    def get_current_filter_name(self) -> str:
        pos = self.get_current_position()
        if 0 <= pos < len(self.filter_names):
            return self.filter_names[pos]
        return f"Position {pos}"
    
    def change_filter(self, filter_code: str) -> bool:
        if not self.connected:
            logger.error('Cannot change filter - not connected')
            return False
        try:
            if filter_code.upper() not in self.filter_map:
                logger.error(f"Invalid filter code: {filter_code}")
                return False
            
            target_pos = self.filter_map[filter_code.upper()]
            current_pos = self.get_current_position()
            
            if current_pos == target_pos:
                logger.info(f"Filter already at {filter_code.upper()}: {self.filter_names[target_pos]}")
                return True
            
            logger.info(f"Changing filter from {self.get_current_filter_name()} to {filter_code.upper()}: {self.filter_names[target_pos]}")
            
            self.filter_wheel.Position = target_pos
            timeout = time.time() + 45.0
            while self.filter_wheel.Position != target_pos:
                if time.time() > timeout:
                    logger.error(f"Filter change timed out after {45} seconds")
                    return False
                time.sleep(0.5)
                
            settle_time = self.config.get('settle_time', 2.0)
            time.sleep(settle_time)
            
            logger.debug(f"Filter changed successfully to {filter_code.upper()}")
            return True
        except Exception as e:
            logger.error(f"Filter change failed: {e}")
            return False
        
    def initialize_to_clear(self) -> bool:
        return self.change_filter('C')
    
    def get_filter_info(self) -> Dict[str, Any]:
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
        code_map = ['C', 'B', 'G', 'R', 'L', 'I', 'H']
        if 0 <= position < len(code_map):
            return code_map[position]
        return None
        
    
        
                
            
        