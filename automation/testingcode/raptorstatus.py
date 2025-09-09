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
        T = Telescope(
        address=device_info["ip"],
        # port=device_info["port"],
        device_number=device_info["device_number"],
        )
        
        print('='*50)
        print('TELESCOPE STATUS (READ-ONLY)')
        print('='*50)
        
        print('Checking telescope connection...')
        connected = T.Connected
        print(f"Connected: {connected}")
        
        if not connected:
            print('Connecting to telescope for status check...')
            T.Connected = True
            time.sleep(1)
            connected = T.Connected
            print(f"Connected: {connected}")
            
        if connected:
            print('\n--- TELESCOPE STATUS ---')
            
            try:
                name = T.Name
                print(f"Name: {name}")
            except:
                print("Name: Unable to retrieve")


            try:
                description = T.Description
                print(f"Description: {description}")
            except:
                print("Description: Unable to retrieve")
            
            try:
                eq_system = T.EquatorialSystem
                print(f"Eq. System: {eq_system}")
            except:
                print("Eq. System: Unable to retrieve")
                
                
            try:
                align_mode = T.AlignmentMode
                print(f"Align. Mode: {align_mode}")
            except:
                print("Align. Mode: Unable to retrieve")
                
            print('\n--- POSITION ---')
            
            try:
                ra = T.RightAscension
                dec = T.Declination
                print(f"Current RA: {ra:.8f} hours")
                print(f"Current Dec: {dec:.8f} deg")
            except Exception as e:
                print(f"Position: Unable to retrieve ({e})")
                
            try:
                alt = T.Altitude
                az = T.Azimuth
                print(f"Current Altitude: {alt:.6f} deg")
                print(f"Current Azimuth: {az:.6f} deg")
            except Exception as e:
                print(f"Alt/Az: Unable to retrieve ({e})")
                
                
            try:
                track_rate = T.TrackingRate
                print(f"Track. Rate: {track_rate}")
            except:
                print("Track. Rate: Unable to retrieve")
                
                
            try:
                track_rates = T.TrackingRates
                print(f"Track. Rates: {track_rates}")
            except:
                print("Track. Rates: Unable to retrieve")
            
            print('\n--- OPERATIONAL STATUS ---') 

            try:
                tracking = T.Tracking
                print(f"Tracking: {tracking}")
            except Exception as e:
                print(f"Tracking Status: Unable to retrieve ({e})")    
                    
            try:
                target_ra = T.TargetRightAscension
                target_dec = T.TargetDeclination
                print(f"Current/Last Target: RA {target_ra:.8f} hours, DEC {target_dec:.8f} deg")
            except Exception as e:
                print(f"Current/Last Target: Unable to retrieve ({e})")
            
            try:
                parked = T.AtPark
                print(f"At Park: {parked}")
            except Exception as e:
                print(f"Park Status: Unable to retrieve ({e})")
                
            try:
                at_home = T.AtHome
                print(f"At Home: {at_home}")
            except Exception as e:
                print(f"Home Status: Unable to retrieve ({e})")
                
            try:
                slewing = T.Slewing
                print(f"Currently Slewing: {slewing}")
            except Exception as e:
                print(f"Slewing Status: Unable to retrieve ({e})")
            
            try:
                pulseguiding = T.IsPulseGuiding
                print(f"Currently Pulse Guiding: {pulseguiding}")
            except Exception as e:
                print(f"Pulse Guiding Status: Unable to retrieve ({e})")
            
            
            print('\n--- SITE INFORMATION ---')    
            
            try:
                lat = T.SiteLatitude
                long = T.SiteLongitude
                ele = T.SiteElevation
                print(f"Current Latitude: {lat:.6f} deg")
                print(f"Current Longitude: {long:.6f} deg")
                print(f"Current Elevation: {ele:.1f} m")
            except Exception as e:
                print(f"Alt/Az: Unable to retrieve ({e})")
                
            try:
                sidereal_time = T.SiderealTime
                print(f"Sidereal Time: {sidereal_time:.6f} hours")
            except Exception as e:
                print(f"Sidereal Time: Unable to retrieve ({e})")
                
            try:
                utc_date = T.UTCDate
                print(f"UTC Date: {utc_date}")
            except Exception as e:
                print(f"UTC Date: Unable to retrieve ({e})")
            
                      
            
            
            print(f"\n--- CAPABILITIES ---")
            
            try:
                can_slew = T.CanSlew
                print(f"Can Slew to Eq. Coords : {can_slew}")
            except Exception as e:
                print(f"Can Slew to Eq. Coords: Unable to retrieve ({e})")
                
            try:
                can_slew_altaz = T.CanSlewAltAz
                print(f"Can Slew to Alt/Az Coords : {can_slew_altaz}")
            except Exception as e:
                print(f"Can Slew to Alt/Az Coords: Unable to retrieve ({e})")    
            
            try:
                can_slew_async = T.CanSlewAsync
                print(f"Can Slew Async (Eq.): {can_slew_async}")
            except Exception as e:
                print(f"Can Slew Async (Eq.): Unable to retrieve ({e})")
            
            try:
                can_slew_altaz_async = T.CanSlewAltAzAsync
                print(f"Can Slew Async (Alt/Az): {can_slew_altaz_async}")
            except Exception as e:
                print(f"Can Slew Async (Alt/Az): Unable to retrieve ({e})")
            
            
            try:
                can_sync_eq = T.CanSync
                print(f"Can Sync Eq.: {can_sync_eq}")
            except Exception as e:
                print(f"Can Sync Eq: Unable to retrieve ({e})")
            
            try:
                can_sync_altaz= T.CanSyncAltAz
                print(f"Can Sync Alt/Az: {can_sync_altaz}")
            except Exception as e:
                print(f"Can Sync Alt/Az: Unable to retrieve ({e})")
            
            try:
                can_pulseguide = T.CanPulseGuide
                print(f"Can Pulse Guide: {can_pulseguide}")
            except Exception as e:
                print(f"Can Pulse Guide: Unable to retrieve ({e})")
            
            try:
                can_park = T.CanPark
                print(f"Can Park: {can_park}")
            except Exception as e:
                print(f"Can Park: Unable to retrieve ({e})")
                
            try:
                can_unpark = T.CanUnpark
                print(f"Can Unpark: {can_unpark}")
            except Exception as e:
                print(f"Can Unpark: Unable to retrieve ({e})")
            
            try:
                can_set_park = T.CanSetPark
                print(f"Can Set Park: {can_set_park}")
            except Exception as e:
                print(f"Can Set Park: Unable to retrieve ({e})")
            
            try:
                can_find_home = T.CanFindHome
                print(f"Can Find Home: {can_find_home}")
            except Exception as e:
                print(f"Can Find Home: Unable to retrieve ({e})")    
            
            try:
                can_set_tracking = T.CanSetTracking
                print(f"Can Set Tracking: {can_set_tracking}")
            except Exception as e:
                print(f"Can Set Tracking: Unable to retrieve ({e})")
            
                       
            # try:
                # can_set_pier = T.CanSetPierSide
                # print(f"Can Set Pier Side: {can_set_pier}")
            # except Exception as e:
                # print(f"Can Set Pier Side: Unable to retrieve ({e})")
            
                       
            # try:
                # pier_side = T.SideOfPier
                # print(f"Pier Side: {pier_side}")
            # except Exception as e:
                # print(f"Pier Side: Unable to retrieve ({e})")
            
            
            print("\n--- SUPPORTED ACTIONS (how do i find out what these do?) ---")
            try:
                actions = T.SupportedActions
                for i, action in enumerate(actions):
                    print(f"{i+1:2d}. {action}")
                    
            except:
                print("Supported Actions: Unable to retrieve")
            
            
        else:
            print(f"Cannot retrieve status - telescope not connected")
            
        
        # Disconnect always last
        try:
            T.Connected = False
            time.sleep(1)
            print("\n--- DISCONNECTED ---")
        except:
            print("\n---DISCONNECTION ERROR ---")
                
    except Exception as e:
        print(f"Error: {e}")
        
        
if __name__ == "__main__":
    main()