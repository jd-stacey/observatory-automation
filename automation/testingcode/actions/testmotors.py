from alpaca.telescope import Telescope
import time

try:
    T = Telescope(address='127.0.0.1:11111', device_number=0)
    T.Connected = True
    time.sleep(1)
    print('Connected')
except Exception as e:
    print(f"Connection Error: {e}")
    
try:
    print(T.SupportedActions)
except Exception as e:
    print(f"Supp Error: {e}")


# try:
#     print('Motor Status...')
#     print(T.Action('motstat',"get"))
# except Exception as e:
#     print(f"MotStat Error: {e}")


##### TEST MOTORS ON AND OFF #####    
try:
    print('Testing motors on...')
    T.Action('telescope:motoron','')
    time.sleep(1)
except Exception as e:
    print(f"Motor On Error: {e}")
print('Waiting 5 seconds...')
time.sleep(5)    
try:
    print(f'\nTesting motors off...')
    T.Action('telescope:motoroff','')
    time.sleep(1)
except Exception as e:
    print(f"Motor Off Error: {e}")