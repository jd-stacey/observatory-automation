from alpaca.filterwheel import FilterWheel
import time
import sys

ALPACA_ADDRESS = "127.0.0.1:11113"
WHEEL_ID = 0
DEFAULT_SLOT = 0

try:
    FW = FilterWheel(ALPACA_ADDRESS, WHEEL_ID)
except Exception as e:
    print(f"Connection Error: {e}")
    sys.exit(1)
    
   
num_slots = len(FW.Names)
print(f"Filter Wheel has {num_slots} slots")

for slot in range(num_slots):
    print(f"Moving to slot {slot}: {FW.Names[slot]}")
    FW.Position = slot
    
    while FW.Position != slot:
        time.sleep(0.5)
    print(f"Wheel now at position {FW.Position}")
    time.sleep(0.5)
    
    
print(f"Returning to default slot {DEFAULT_SLOT}: {FW.Names[DEFAULT_SLOT]}")
FW.Position = DEFAULT_SLOT
while FW.Position != DEFAULT_SLOT:
    time.sleep(0.5)
print("Wheel return to default slot")
print("--- PROGRAM EXITED ---")