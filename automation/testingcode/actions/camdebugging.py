from alpaca.camera import Camera
import time

address = "127.0.0.1:11113"
id = 0

try:
    cam = Camera(address, id)
    print(f"Connected: {cam.Connected}")
except Exception as e:
    print(f"Error creating Camera Object: {e}")

try:
    if not cam.Connected:
        cam.Connected = True
        print(f"Connected: {cam.Connected}")
except Exception as e:
    print(f"Connection error: {e}")

try:
    cam.StartExposure(1.0, True)
    time.sleep(0.05)
except Exception as e:
    print(f" Error starting exposure: {e}")
    
try:
    cs = cam.CameraState
    cs_name = cs.name if hasattr(cs, 'Name') else str(cs)
except Exception as e:
    cs_name = f"Error reading CameraState: {e}"
    
try:
    ir = bool(cam.ImageReady)
except Exception as e:
    ir = f"Error reading ImageReady: {e}"
    
try:
    nx = cam.NumX    
    ny = cam.NumY
except Exception as e:
    nx = ny = None
    
print(f"CamState = {cs_name}, ImageRead={ir}, NumX={nx}, NumY={ny}")