import json
import time
import os
from datetime import datetime
from pathlib import Path
import random

JSON_FILE = Path(r"P:\temp\wcssolution_2.json")

def update_json(ra_deg, dec_deg, theta_deg=0.0, exptime=5.0):
    data = {
        "fitsname": {"0": f"test_{int(time.time()*1000)}.fits"},
        "file_datetime": {"0": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")},
        "calc_datetime": {"0": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")},
        "field_ra": {"0": 180.0},
        "field_dec": {"0": -78.0},
        "ra_offset": {"0": ra_deg},
        "dec_offset": {"0": dec_deg},
        "theta_offset": {"0": theta_deg},
        "exptime": {"0": exptime},
    }
    
    tmp_path = JSON_FILE.with_suffix(".tmp")
    
    with open(tmp_path, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, JSON_FILE)
        
def random_offset_stream(iterations: int = 30, delay: float = 2.0):
    print(f"Creating {iterations} json files with a {delay} second delay between")
    for i in range(iterations):
        ra_offset = random.uniform(-0.005, 0.005)
        dec_offset = random.uniform(-0.005, 0.005)
        if random.random() < 0.2:
            theta_offset = random.uniform(-10, 10)
        else:
            theta_offset = random.uniform(-0.5, 0.5)
            
        update_json(ra_offset, dec_offset, theta_offset)
        print(f"JSON file {i+1} created...sleeping for {delay} seconds...")
        time.sleep(delay)


if __name__ == "__main__":
    random_offset_stream(iterations=50, delay=2)

# def main():
#     print("Test generator: 1=small, 2=medium, 3=large, 4=zero, 5=auto")
#     choice = input("Pick: ").strip()
#     if choice == "1":
#         create_json(0.001389, 0.001389)
#     elif choice == "2":
#         create_json(0.002778, -0.001389)
#     elif choice == "3":
#         create_json(-0.005556, 0.008333)
#     elif choice == "4":
#         create_json(0.0, 0.0)
#     elif choice == "5":
        
            
#     else:
#         print('Invalid')
        
