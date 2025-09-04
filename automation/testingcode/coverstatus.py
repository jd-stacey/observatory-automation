from alpaca.covercalibrator import CoverCalibrator
import time

try:
    C = CoverCalibrator("127.0.0.1:11112", 0)
    C.Connect()
    time.sleep(1)
    C.Connected = True
    time.sleep(1)
    print(f"Connected: {C.Connected}")
    print(f"Name: {C.Name}")
    print(f"Description: {C.Description}")
    # print(f"CoverState: {C.CoverState}")
    # print(f"DeviceState: {C.DeviceState}")
    print(f"Supported Action: {C.SupportedActions}")
    # print(f"Brightness: {C.Brightness}")
    # print(f"Max Brightness: {C.MaxBrightness}")
    
except Exception as e:
    print(f"ERROR: {e}")
    
    
try:
    print(f'CoverState: {C.CoverState}')
except Exception as e:
    print(f"CoverState Error: {e}")
    
try:
    print(C.Action('coverstatus', ''))
    print('Opening...')
    C.OpenCover()
    t = 0
    while t < 20:
        print(C.Action('coverstatus', '')+f"    CoverState: {C.CoverState}")
        t += 1
        time.sleep(0.1)
    time.sleep(5)
except Exception as e:
    print(f"CoverStatus Error: {e}")
    
try:
    print('-'*50)
    print(C.Action('coverstatus', ''))
    print('Closing...')
    C.CloseCover()
    t = 0
    while t < 20:
        print(C.Action('coverstatus', '')+f"    CoverState: {C.CoverState}")
        t += 1
        time.sleep(0.1)
    time.sleep(1)
    print('Final'+C.Action('coverstatus', '')+f"    CoverState: {C.CoverState}")
except Exception as e:
    print(f"CoverStatus Error: {e}")

