from alpaca.rotator import Rotator
import time

last_mech = None
last_time = None

try:
    rot = Rotator("127.0.0.1:11111", 0)
    print(f"Connected: {rot.Connected}")
    
    while True:
        pos = rot.Position
        mech = rot.MechanicalPosition
        now = time.time()
        
        if last_mech is not None:
            dt = now - last_mech
            drift = (mech - last_mech) / dt
            print(f"SkyPA={pos:.6f}  Mech={mech:.6f}  Drift={drift:.8f}")
        else:
            print(f"SkyPA={pos:.6f}  Mech={mech:.6f} Drift=--")
            
        last_mech = mech
        last_time = now
        time.sleep(2)
    
    
except Exception as e:
    print(f"ERROR: {e}")