#"http://127.0.0.1:1880/dome/true" - open dome
#"http://127.0.0.1:1880/dome/false" - close dome
#"http://127.0.0.1:1880/dome/left/true" - open left panel
#"http://127.0.0.1:1880/dome/left/false" - close left panel
#"http://127.0.0.1:1880/dome/right/true" - open right panel
#"http://127.0.0.1:1880/dome/right/false" - close right panel
#"http://127.0.0.1:1880/status" - ??? get left/right panel status i guess
#"http://127.0.0.1:1880/dome/reset" - reset motor
#192.168.249.27 - telcom 7 ip

'''
Would like to (on Telcom7):
    * add error/catch nodes after every dome flow returning 500 or whatever on failure
                (so we know when something fails - though will still ahve to constantly poll statuses as well)
'''
    
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from autopho.devices.drivers.nodered_dome import DomeDriver, DomeError

config_path = Path(__file__).parent.parent / 'config' / 'devices.yaml'
with open(config_path) as f:
    devices = yaml.safe_load(f)
dome_config = devices['dome']

driver = DomeDriver()
connected = driver.connect(devices['dome'])

# Connected
print(f"\n--- Connection ---")
print(f"Connected       : {connected}")
print(f"Is Connected    : {driver.is_connected()}")

# Raw state
print(f"\n--- Raw State ---")
state = driver.get_state()
print(f"Full state dict : {state}")

# Individual panel states
print(f"\n--- Panel States ---")
print(f"Left panel      : {driver.get_left_state()}")
print(f"Right panel     : {driver.get_right_state()}")

# Boolean status checks
print(f"\n--- Status Checks ---")
print(f"Is closed       : {driver.is_closed()}")
print(f"Is open         : {driver.is_open()}")
print(f"Is moving       : {driver.is_moving()}")

# Full info dict
print(f"\n--- Dome Info ---")
info = driver.get_dome_info()
for k, v in info.items():
    print(f"  {k:20s} : {v}")

# Last serial chars from hardware
print(f"\n--- Serial History ---")
print(f"Last chars      : {state.get('lastChars', [])}")

# Disconnect
print(f"\n--- Disconnect ---")
disconnected = driver.disconnect()
print(f"Disconnected    : {disconnected}")
print(f"Is Connected    : {driver.is_connected()}")

# Confirm state calls fail gracefully when disconnected - this is supposed to fail
print(f"\n--- State while disconnected (should fail gracefully) ---")
try:
    state = driver.get_state()
    print(f"State           : {state}")
except DomeError as e:
    print(f"DomeError caught (expected): {e}")

# Reconnect
print(f"\n--- Reconnect ---")
reconnected = driver.connect(devices['dome'])
print(f"Reconnected     : {reconnected}")
print(f"Is Connected    : {driver.is_connected()}")
print(f"Left panel      : {driver.get_left_state()}")
print(f"Right panel     : {driver.get_right_state()}")
