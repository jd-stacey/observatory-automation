from alpaca.telescope import Telescope
import sys
import time


device_info = {
"device_type": "Telescope",
"device_number": 0,
"ip": "127.0.0.1:11111",
"port": 11111
}
    
print('='*50)
print('WARNING: THIS SCRIPT WILL MOVE THE TELESCOPE')
print('Ensure area is clear and it is safe to slew the telescope.')
print('='*50)

confirm = input("Type 'YES' to proceed: ").strip().upper()
if confirm != 'YES':
    print('Aborting - telescope not moved.')
    sys.exit(0)
    
try:
    T = Telescope(
        address=device_info["ip"],
        device_number=device_info["device_number"],
        )
        
    print('Checking telescope connection...')
    connected = T.Connected
    print(f"Connected: {connected}")
    
    if not connected:
        print('Connecting to telescope...')
        T.Connected = True
        time.sleep(1)
        connected = T.Connected
        print(f"Connected: {connected}")
        
    if connected:
        alt = 40.0
        az = 180.0
        
        print(f"Slewing to SCP at Alt={alt:.2f} deg, Az={az:.2f} deg ...")
        T.SlewToAltAzAsync(az, alt)
        
        while T.Slewing:
            print('...slewing...')
            time.sleep(1)
            
        T.SetPark()
        time.sleep(1)
        
        if T.AtPark:
            print('Telescope parked.')
        else:
            print('Telescope not parked')
        
except Exception as e:
    print(f'Error: {e}')
    
finally:
    try:
        T.Connected = False
        time.sleep(1)
        print("\n--- DISCONNECTED ---")
    except:
        print("\n---DISCONNECTION ERROR ---")
    