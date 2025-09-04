from alpaca.filterwheel import FilterWheel

try:
    FW = FilterWheel("127.0.0.1:11113", 0)
    print(f"Connected: {FW.Connected}")
    print(f"Name: {FW.Name}")
    print(f"Position: {FW.Position}")
except Exception as e:
    print(f"ERROR: {e}")
    