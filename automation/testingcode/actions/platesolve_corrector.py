from alpaca.telescope import Telescope
import json
import os.path
import time
import sys
import math

class AlpacaPointingCorrector:
    def __init__(self, telescope_ip='127.0.0.1:11111', device_number=0):
        self.T = Telescope(
            address=telescope_ip,
            device_number=device_number
        )
        
        self.json_file_path = 'P:\\temp\\wcssolution_2.json'
        self.FILE_MODIFIED_TIME_DIFF = 200  # max age in seconds
        self.SLEEP_TIME = 5                 # wait between readings
        self.SCALE_FACTOR = 1               # correction scale factor
        self.TIMEOUT_CUTOFF = 600           # max timeout before exit
        
        self.lastfile = ""
        self.cumulative_zeroinput_time = 0
        
    def connect_telescope(self):
        try:
            if not self.T.Connected:
                print("Connecting to telescope...")
                self.T.Connected = True
                time.sleep(1)
                
            if self.T.Connected:
                print(f"Successfully connected to telescope: {self.T.Name}")
                return True
            else:
                print("Failed to connect to telescope")
                return False
        
        except Exception as e:
            print(f"Connection Error: {e}")
            
    def disconnect_telescope(self):
        try:
            if self.T.Connected:
                self.T.Connected = False
                print("Telescope disconnected")            
        except Exception as e:
            print(f"Disconnect Error: {e}")
            
    def arcsec_to_degrees(self, arcsec):
        return arcsec / 3600.0
        
    def calculate_new_coordinates(self, current_ra_hours, current_dec_deg, ra_offset_deg, dec_offset_deg):
        '''
        Calcs new RA/Dec coords from supplied offsets
        
        Args:
            current_ra_hours: Current RA in hours (from ASCOM)
            current_dec_deg: Current Dec in degrees (from ASCOM)
            ra_offset_deg: RA offset in degrees (from JSON file) - Q is this already dec-corrected? I assume so.
            dec_offset_deg: Dec offset in degrees (from JSON file)
            
        Returns:
            new_ra_hours: new RA in hours (for ASCOM)
            new_dec_deg: new Dec in degrees (for ASCOM)
        '''
        
        new_ra_hours = current_ra_hours + (ra_offset_deg / 15.0)
        new_dec_deg = current_dec_deg + dec_offset_deg
        
        # Ensure valid ranges
        new_ra_hours = new_ra_hours % 24.0
        if new_ra_hours < 0:
            new_ra_hours += 24.0
        new_dec_deg = max (-90, min(90.0, new_dec_deg))
        
        return new_ra_hours, new_dec_deg
        
    def apply_telescope_correction(self, ra_offset_deg, dec_offset_deg, settle_time):
        ''''''
        try:
            current_ra_hours = self.T.RightAscension
            current_dec_deg = self.T.Declination
            print(f"Current position: RA={current_ra_hours:.6f}h ({current_ra_hours*15:.6f}deg), Dec={current_dec_deg:.6f}deg")
            
            new_ra_hours, new_dec_deg = self.calculate_new_coordinates(current_ra_hours, current_dec_deg, ra_offset_deg, dec_offset_deg)
            
            print(f"New target: RA={new_ra_hours:.6f}h ({new_ra_hours*15:.6f}deg), Dec={new_dec_deg:.6f}deg")
            print(f"Applying corrections: RA offset={ra_offset_deg:.6f}deg, Dec offset={dec_offset_deg:.6f}deg")
            
            if self.T.AtPark:
                print("Unparking telescope...")
                self.T.Unpark()
                time.sleep(0.5)
            
            self.T.SlewToCoordinatesAsync(new_ra_hours, new_dec_deg)
            
            print('Slewing telescope...')
            while self.T.Slewing:
                time.sleep(0.5)
            
            print(f"Slew complete. Waiting for settle time: {settle_time}s")
            time.sleep(settle_time)
            
            return True
            
        except Exception as e:
            print(f"Error applying telescope correction: {e}")
            return False
            
            
    def process_platesolving_data(self, data):
        '''
        Process the platesolving JSON data and determine corrections.
        Just includes processing for RA/Dec atm - Rotation still to do.
        '''
        
        try:
            ra_offset_deg = float(data['ra_offset']["0"])
            dec_offset_deg = float(data['dec_offset']["0"])
            rot_offset = float(data['theta_offset']["0"])
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            
            settle_time = float(data['exptime']["0"])
            
            total_offset = math.sqrt(ra_offset_arcsec**2 + dec_offset_arcsec**2)
            
            print(f"Offsets: RA={ra_offset_arcsec:.2f}\" ({ra_offset_deg:.6f}deg), Dec={dec_offset_arcsec:.2f}\" ({dec_offset_deg:.6f}deg), Total={total_offset:.2f}\"")
            
            if total_offset < 1.0:
                settle_time = 2
                scale_factor = 0
            elif total_offset > 5.0:
                settle_time*= 5.0
                scale_factor = 0.5
            else:
                settle_time *= 7
                scale_factor = 1.0
                
            ra_offset_deg *= scale_factor
            dec_offset_deg *= scale_factor
            
            ra_offset_arcsec = ra_offset_deg * 3600.0
            dec_offset_arcsec = dec_offset_deg * 3600.0
            
            settle_time = max (10, min(140, settle_time))
            
            if self.lastfile == data['fitsname']["0"]:
                ra_offset_deg = 0
                dec_offset_deg = 0
                ra_offset_arcsec = 0
                dec_offset_arcsec = 0
                settle_time = 1
                print("Already applied current solution")
                
            return ra_offset_deg, dec_offset_deg, rot_offset, settle_time
        
        except Exception as e:
            print(f"Error processing platesolving data: {e}")
            return 0, 0, 0, 1
            
            
    def run_correction_loop(self):
        ''''''
        
        if not self.connect_telescope():
            return
            
        print(f"Starting pointing correction loop. Monitoring file: {self.json_file_path}")
        
        try:
            while True:
                try:
                    if not os.path.exists(self.json_file_path):
                        print(f"JSON file not found: {self.json_file_path}")
                        time.sleep(self.SLEEP_TIME)
                        continue
                    
                    mod_time = os.path.getmtime(self.json_file_path)
                    secs_elapsed = time.time() - mod_time
                    
                    if secs_elapsed > self.FILE_MODIFIED_TIME_DIFF:
                        print(f"JSON file is {round(secs_elapsed)}s old! Waiting for newer file...")
                        time.sleep(self.SLEEP_TIME)
                        continue
                        
                    print('Reading new JSON file...')
                    
                    with open(self.json_file_path) as f:
                        data = json.load(f)
                        
                    ra_offset_deg, dec_offset_deg, rot_offset, settle_time = self.process_platesolving_data(data)
                    
                    if ra_offset_deg == 0 and dec_offset_deg == 0:
                        self.cumulative_zeroinput_time += self.SLEEP_TIME
                    else:
                        self.cumulative_zeroinput_time = 0
                        
                    if self.cumulative_zeroinput_time > self.TIMEOUT_CUTOFF:
                        print(f"Correction loop timeout. Exceeded {self.TIMEOUT_CUTOFF}s")
                        break
                        
                    if abs(ra_offset_deg * 3600) > 1 or abs(dec_offset_deg * 3600) > 1:
                        success = self.apply_telescope_correction(ra_offset_deg, dec_offset_deg, settle_time)
                        if success:
                            self.lastfile = data['fitsname']["0"]
                    else:
                        print("Offsets too small, no correction applied.")
                        
                    print('Correction cycle complete.')
                
                except Exception as e:
                    print(f"Error in correction loop: {e}")
                    
                time.sleep(self.SLEEP_TIME)
        
        except KeyboardInterrupt:
            print("\nStopping correction loop...")
        finally:
            self.disconnect_telescope()
            
def main():
    corrector = AlpacaPointingCorrector(
        telescope_ip='127.0.0.1:11111',
        device_number=0
    )
    
    corrector.run_correction_loop()
    
if __name__ == "__main__":
    main()