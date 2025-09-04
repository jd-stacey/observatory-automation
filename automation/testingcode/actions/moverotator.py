from alpaca.rotator import Rotator
import time

try:
    R = Rotator("127.0.0.1:11111", 0)
    print(f"Current Position: {R.Position}°")
    print(f"{R.Connected}")
    print(f"{R.IsMoving}")
    R.MoveAbsolute(-13)
    while R.IsMoving:
        print(f'Rotating...Now at {R.Position:.2f}°...')
        time.sleep(2)
    print(f"Final Position: {R.Position}°")
except Exception as e:
    print(f"ERROR: {e}")