from alpaca.covercalibrator import CoverCalibrator
import time

try:
    C = CoverCalibrator("127.0.0.1:11112", 0)
    C.Connect()
    time.sleep(2)
    print(C.Action('coverstatus', ''))
    time.sleep(2)
    C.CloseCover()
    time.sleep(10)
    print(C.Action('coverstatus', ''))
    time.sleep(2)
    print(C.Action('coverstatus', ''))
    time.sleep(2)
    # time.sleep(1)
    # C.Connected = True
    # time.sleep(1)
    # print(f"Connected: {C.Connected}")
    # print(C.Action('coverstatus', ''))
except Exception as e:
    print(f"ERROR: {e}")