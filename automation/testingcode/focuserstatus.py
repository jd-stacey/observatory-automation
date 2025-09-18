from alpaca.focuser import Focuser
import time

try:
    
    F = Focuser("127.0.0.1:11112", 0)
    # F.Connect()
    # F.Disconnect()
    print(f"Connecting?: {F.Connecting}")
    
    print("-"*25)
    timeout = 0
    while F.Connecting:
        print(f"{timeout} | Connecting?: {F.Connecting} | Connected?: {F.Connected}")
        time.sleep(0.5)
        timeout += 0.5
        if timeout >= 15:
            break
        else:
            continue
    
    print(f"Connected: {F.Connected}")
    # F.Connected = True
    time.sleep(1)
    print(f"Connected (2nd try): {F.Connected}")
    print(f"Name: {F.Name}")
    print(f"Description: {F.Description}")
    print(f"Position: {F.Position}")
    print(f"Position Type: {type(F.Position)}")
    print(f"Is Moving?: {F.IsMoving}")
    print(f"Is Moving Type: {type(F.IsMoving)}")
    print(f"Absolute via .Move()?: {F.Absolute}")
    print(f"Abs type: {type(F.Absolute)}")
    print(f"Step Size: {F.StepSize}")
    print(f"Step Size Type: {type(F.StepSize)}")
    print(f"Max Step: {F.MaxStep}")
    print(f"MaxStep Type: {type(F.MaxStep)}")
    print(f"Max Increment: {F.MaxIncrement}")
    # print(f"Temperature: {F.Temperature}")
    print(f"Supported Action: {F.SupportedActions}")
    F.Disconnect()
except Exception as e:
    print(f"ERROR: {e}")
    
    
# try:
#     print(f'DeviceState: {F.DeviceState}')
# except Exception as e:
#     print(f"DeviceState Error: {e}")
    
    
try:
    print(f'TempComp Available: {F.TempCompAvailable}')
except Exception as e:
    print(f"TempComp Available Error: {e}")
    
try:
    print(f'TempComp: {F.TempComp}')
except Exception as e:
    print(f"TempComp Error: {e}")
    
    
try:
    print(f'Temperature: {F.Temperature}')
except Exception as e:
    print(f"Temperature Error: {e}")
    
try:
    print(f"Is Installed: {F.Action('isinstalled', '')}")
    print(f"Is Installed Type: {type(F.Action('isinstalled', ''))}")
except Exception as e:
    print(f"Is Installed Error: {e}")


# try:
#     print(f"Vel Speed: {F.Action('velspeed', '')}")
# except Exception as e:
#     print(f"Vel Speed Error: {e}")

# try:
#     print(f"Image Plane Info: {F.Action('imageplane_info', '')}")
# except Exception as e:
#     print(f"Image Plane Info Error: {e}")

# try:
#     print(f"Fans Status: {F.Action('fansstatus', '')}")
# except Exception as e:
#     print(f"Fans Status Error: {e}")



# print(f"2nd Connecting?: {F.Connecting}")
# time.sleep(1)
# print(f"3rd Connected: {F.Connected}")
# F.Connected = True
# time.sleep(1)
# print(f"Connected (4th try): {F.Connected}")