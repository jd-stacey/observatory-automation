from alpaca.filterwheel import FilterWheel
from alpaca.exceptions import *
from datetime import datetime
import sys
import time

ALPACA_ADDRESS = "127.0.0.1:11113"
FILTERWHEEL_ID = 0

def get_filterwheel_status():
    FW = None
    status = {
    'timestamp': datetime.now().isoformat()
    }
    
    try:
        FW = FilterWheel(ALPACA_ADDRESS, FILTERWHEEL_ID)
        FW.Connected = True
        time.sleep(1)
        
        properties = {
        'Connected': lambda: FW.Connected,
        'Name': lambda: FW.Name,
        'Description': lambda: FW.Description,
        'Position': lambda: FW.Position,
        'Names': lambda: FW.Names,
        'FocusOffsets': lambda: FW.FocusOffsets,
        'DriverInfo': lambda: FW.DriverInfo,
        'DriverVersion': lambda: FW.DriverVersion,
        'SupportedActions': lambda: FW.SupportedActions
        }
        
        for prop_name, prop_func in properties.items():
            try:
                status[prop_name] = prop_func()
                if prop_name == 'Connected' and status[prop_name] != True:
                    status['connection_failed'] = True
                    break
            except Exception as e:
                status[prop_name] = f"ERROR: {str(e)}"
                if prop_name == 'Connected':
                    status['connection_failed'] = True
                    break
                

                
    except Exception as e:
        status["general_error"] = f"General Error: {str(e)}"
    
    finally:
        if FW:
            try:
                FW.Connected = False
                time.sleep(1)
            except:
                pass
                
    return status

def format_filterwheel_status(status):
    if 'connection_failed' in status:
        print(f"DEVICE NOT CONNECTED - Skipping Detailed Status")
        connected_status = status.get('Connected', 'Unknown')
        print(f"Connection Status: {connected_status}")
        sys.exit(1)
    
    timestamp = status.get('timestamp', 'Unknown')
    
    print(f"\n{'='*50}")
    print(f"FILTER WHEEL STATUS - {timestamp}")
    print(f"{'='*50}")
    
    if 'general_error' in status:
        print(f"GENERAL ERROR: {status['general_error']}")
        return
        
    basic_props = {
    'Connected': 'Connected',
    'Name': 'Device Name',
    'Description': 'Description',
    'Position': 'Position',
    'DeviceState': 'DeviceState'
    }
    
    print("BASIC INFO")
    for prop_key, disp_name in basic_props.items():
        value = status.get(prop_key, 'Not Available')
        print(f"{disp_name:15} {value}")
        
    current_pos = status.get('Position', 'Unknown')
    filter_names = status.get('Names', 'Unknown')
    focus_offsets = status.get('FocusOffsets', 'Unknown')
    
    if isinstance(filter_names, list):
        print(f"Available Filters ({len(filter_names)}):")
        for i, name in enumerate(filter_names):
            current = " <---- CURRENT" if (isinstance(current_pos, int) and i == current_pos) else ""
            print(f"    [{i}] {name}{current}")
    else:
        print(f"Filter Names:   {filter_names}")
        
    if isinstance(focus_offsets, list):
        print(f"Focus Offsets:")
        for i, offset in enumerate(focus_offsets):
            current = " <---- CURRENT" if (isinstance(current_pos, int) and i == current_pos) else ""
            print(f"    [{i}] {offset}{current}")
    else:
        print(f"Focus Offsets:   {focus_offsets}")
        
        
    handled_props = set(basic_props.keys())
    handled_props.update(['Names', 'FocusOffsets', 'timestamp', 'general_error'])
    
    other_props = {k: v for k, v in status.items() if k not in handled_props}
    
    if other_props:
        print(f"\nOTHER PROPERTIES:")
        for prop_key, val in sorted(other_props.items()):
            print(f"{prop_key:15} {val}")
                
def get_current_filter_info(status):
    current_pos = status.get('Position')
    filter_names = status.get('Names')
    focus_offsets = status.get('FocusOffsets')
    
    if (isinstance(current_pos, int) and
    isinstance(filter_names, list) and
    isinstance(focus_offsets, list) and
    0 <= current_pos < len(filter_names)
    ):
        print(f"\nCURRENT FILTER DETAILS:")
        print(f"Position:       {current_pos}")
        print(f"Filter Name:    {filter_names[current_pos]}")
        if current_pos < len(focus_offsets):
            print(f"Focus Offset:   {focus_offsets[current_pos]}")
        else:
            print(f"Focus Offse: No data available")
    else:
        print("CURRENT FILTER: Unable to determine details")
        if not isinstance(current_pos, int):
            print(f"Reason: Invalid position data - {current_pos}")
            
            
def main():
    print(f"\n{'='*50}")
    print("Filter Wheel Status Monitor (Alpyca)")
    print("="*50)
    
    try:
        status = get_filterwheel_status()
        format_filterwheel_status(status)
        get_current_filter_info(status)
        
        print(f"\n{'='*50}")
        print('Status check completed')
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        
    finally:
        print("\n--- PROGRAM EXITED ---")
        
if __name__ == '__main__':
    main()