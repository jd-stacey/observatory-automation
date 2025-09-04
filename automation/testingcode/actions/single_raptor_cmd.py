from alpaca.telescope import Telescope
from alpaca.filterwheel import FilterWheel
from alpaca.camera import Camera
import sys
import time


device_info = {
"scope_address": "127.0.0.1:11111",
"scope_num": 0,
"cam_fw_address": "127.0.0.1:11113",
"cam_nums": [0,1],
"fw_num": 0
}
    
print('='*50)
print('WARNING: THIS SCRIPT WILL PERFORM PHYSICAL ACTIONS (E.G. MOVE THE TELESCOPE)')
print('Ensure area is clear and it is safe to perform actions.')
print('='*50)

confirm = input("Type 'YES' to proceed: ").strip().upper()
if confirm != 'YES':
    print('Aborting - no actions taken.')
    sys.exit(0)
    
T = None
cameras = []
FW = None

try:
    print('Connecting to telescope...')
    T = Telescope(
    address=device_info["scope_address"],
    device_number=device_info["scope_num"]
    )
    T.Connected = True
    time.sleep(1)
    print(f"Telescope Connected: {T.Connected}")
    
    print('Connecting cameras...')
    for cam_num in device_info['cam_nums']:
        try:
            C = Camera(
            address=device_info['cam_fw_address'],
            device_number=cam_num
            )
            C.Connected = True
            time.sleep(0.5)
            cam_name = C.Name
            cameras.append({'device': C, 'name': cam_name, 'num': cam_num})
            print(f"Camera {cam_num} Connected: {C.Connected}")
        except Exception as e:
            print(f"Camera {cam_num} ERROR: {e}")
            
    print('Connecting filter wheel...')
    try:
        FW = FilterWheel(
        address=device_info['cam_fw_address'],
        device_number=device_info['fw_num']
        )
        FW.Connected = True
        time.sleep(0.5)
        print(f"Filter Wheel Connected: {FW.Connected}")
        
    except Exception as e:
        print(f"Filter Wheel ERROR: {e}")
        FW = None
        
    print('\n--- AVAILABLE DEVICES ---')
    if T and T.Connected:
        print('1. Telescope (T)')
        
    for i, cam in enumerate(cameras):
        if cam['device'].Connected:
            print(f'{i+2}. Camera: {cam["name"]} (C)')
    
    if FW and FW.Connected:
        print(f'{len(cameras)+2}. Filter Wheel (FW)')
        
    while True:
        print("\nSelect Device (or 'quit'):")
        choice = input('> ').strip()
        
        if choice.lower() == 'quit':
            break
        
        try:
            choice_num = int(choice)
            if choice_num == 1 and T.Connected:
                selected_device = T
                device_name = 'Telescope'
                var_name = 'T'
            
            elif 2 <= choice_num <= len(cameras)+1:
                cam_index = choice_num - 2
                if cam_index < len(cameras) and cameras[cam_index]['device'].Connected:
                    selected_device = cameras[cam_index]['device']
                    device_name = f"Camera ({cameras[cam_index]['name']})"
                    var_name = 'C'
                else:
                    print('Invalid Camera Selection')
                    continue
            
            elif choice_num == len(cameras)+2 and FW and FW.Connected:
                selected_device = FW
                device_name = 'Filter Wheel'
                var_name = 'FW'
            else:
                print('Invalid Selection')
                continue
                
            print(f"Selected: {device_name}")
            print(f"Enter Command (e.g. T.Park() or 'back'):")
            command = input('> ').strip()
            
            if command.lower() == 'back':
                continue
                
            if not command:
                continue
                
            if any(danger in command.lower() for danger in ['import', 'exec', 'eval', '__']):
                print('Command not allowed.')
                continue
            
            if command.startswith(var_name + '.'):
                command = command.replace(var_name, 'selected_device')
            else:
                command = f"selected_device.{command}"
                
            print(f"Executing {command.replace('selected_device', var_name)}")
            result = eval(command)
            
            if result is not None:
                print(f'Result: {result}')
            else:
                print('Command Executed')
                
        except ValueError:
            print("Enter a number or 'quit'")
        except Exception as e:
            print(f"ERROR: {e}")
                
    
except Exception as e:
    print(f'ERROR: {e}')
    
finally:
    print('\nDisconnecting')
    
    if T:
        try:
            T.Connected = False
            time.sleep(0.5)
            print('Telescope disconnected')
        except:
            print('Telescope disconnect error')
            
    # for cam in cameras:
        # try:
            # cam['device'].Connected = False
            # print(f"Camera {cam['name']} disconnected")
        # except:
            # print(f"Camera {cam['name']} disconnection error")
            
    # if FW:
        # try:
            # FW.Connected = False
            # print('Filter Wheel disconnected')
        # except:
            # print('Filter Wheel disconnection error')
            
# time.sleep(1)
print('\n--- PROGRAM TERMINATED ---')
    
    