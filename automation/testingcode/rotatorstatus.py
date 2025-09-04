from alpaca.rotator import Rotator
import time

try:
    R = Rotator("127.0.0.1:11112", 0)
    print(f"Connected: {R.Connected}")
    print(f"Name: {R.Name}")
    print(f"Description: {R.Description}")
    print(f"Position (° Counter-clockwise): {R.Position:.6f}°")
    print(f"Mechanical Position (° Counter-clockwise from mech. index): {R.MechanicalPosition:.6f}°")
    print(f"Is Moving: {R.IsMoving}")
    print(f"Can Reverse: {R.CanReverse}")  
    print(f"Supported Action: {R.SupportedActions}")
    
except Exception as e:
    print(f"ERROR: {e}")
    
try:
    print(f"Step Size: {R.StepSize}")
    pass
except Exception as e:
    print(f"StepSize ERROR: {e}")
    
try:
    print(f"Target Position: {R.TargetPosition}")
    pass
except Exception as e:
    print(f"TargetPos ERROR: {e}")
    

try:
    print(f"Is installed?: {R.Action('isinstalled','')}")
    print(type(R.Action('isinstalled', '')))
    pass
except Exception as e:
    print(f"isinstalled ERROR: {e}")

# try:
#     print(f"Device State: {R.DeviceState}")
#     pass
# except Exception as e:
#     print(f"DevState ERROR: {e}")
    
    
# try:
#     print(f'Connected? {R.Connected}')
#     R.Connect()
#     while R.Connecting:
#         print('Connecting...')
#         print(R.Connected)
#         time.sleep(0.01)
#     #time.sleep(1)
#     R.Connected = True
#     time.sleep(0.5)
#     R.Connected = True
#     time.sleep(0.5)
#     print(f'Connected Now? {R.Connected}')
# except Exception as e:
#     print(f"Connect ERROR: {e}")