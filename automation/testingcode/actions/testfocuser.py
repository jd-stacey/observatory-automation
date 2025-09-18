import sys
import os

import logging
from time import sleep


driver_path = os.path.abspath(
    os.path.join(__file__, "..", "..", "..", "src", "autopho", "devices", "drivers")
)
if driver_path not in sys.path:
    sys.path.insert(0, driver_path)

from alpaca_focuser import AlpacaFocuserDriver, AlpacaFocuserError

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

def test_focuser():

    driver = AlpacaFocuserDriver()
    config = {"address": "127.0.0.1:11112", 
              "device_number": 0,
              "focus_positions": {'L': 15200,
                                  'B': None,
                                  'V': None,
                                  'R': None,
                                  'C': 15155,
                                  'I': None,
                                  'H': None,
                                  'spectro': 18433
                                  }
    }
              

    print("Connecting to focuser...")
    if not driver.connect(config):
        print("Failed to connect.")
        return

    print("Connection successful!")
    info = driver.get_focuser_info()
    print(f"Initial info: {info}")

    # Test move within limits
    limits = info["limits"]
    # if "min" in limits and "max" in limits:
    #     mid_position = (limits["min"] + limits["max"]) // 2
    #     print(f"Moving to middle position: {mid_position}")
    #     driver.move_to_position(mid_position)
    #     sleep(1)  # optional pause

    
    print("Testing move to spectro focus position...")
    driver.set_position_from_filter('SpeCtro')
    
    print("Testing move back to Lum focus position...")
    driver.set_position_from_filter('l')
    
    print("Testing fake filter_code position...")
    driver.set_position_from_filter('QqQ')
    
    
    # Test halt (should be no-op if not moving)
    print("Halting focuser (if moving)...")
    driver.halt()

    # Test refreshing info
    refreshed_info = driver.get_focuser_info(refresh=True)
    print(f"Refreshed info: {refreshed_info}")

    # Test unsafe move
    unsafe_position = limits["max"] + 100
    print(f"Attempting unsafe move to {unsafe_position}")
    driver.move_to_position(unsafe_position)

    print("Test complete.")

if __name__ == "__main__":
    test_focuser()
