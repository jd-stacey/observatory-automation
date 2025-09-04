from alpaca.telescope import Telescope
import time

def main():
    device_info = {
    "device_type": "Telescope",
    "device_number": 0,
    "ip": "127.0.0.1:11111",
    "port": 11111
    }
    driver_name="ASCOM.AlpacaDynamic1.Telescope"
    
    
    try:
    
        telescope = Telescope(
        address=device_info["ip"],
        # port=device_info["port"],
        device_number=device_info["device_number"],
        )
            
        print('Checking telescope connection...')
        connected = telescope.Connected
        print(f"Connected: {connected}")
        
        if not connected:
            print('Connecting...')
            telescope.Connected = True
            time.sleep(1)
            connected = telescope.Connected
            print(f"Connected: {connected}")
            
        # telescope.SlewToCoordinatesAsync(10.8,-70.5)
        
        # telescope_name = await telescope.get_name()
        # print(f"Telescope Name: {telescope_name}")
        
        # tracking = await telescope.get_tracking()
        # print(f"Tracking Enabled: {tracking}")
        
        # ra = await telescope.get_right_ascension()
        # dec = await telescope.get_declination()
        # print(f'Current Coords: RA - {ra} deg, Dec: {dec} deg')
        
        telescope.Connected = False
        print('Disconnected.')
    
    except Exception as e:
        print(f'Error: {e}')
        pass

    


main()


    
    
  