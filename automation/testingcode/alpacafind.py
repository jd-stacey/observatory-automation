##### RAPTORTCU VERSION #####

from alpaca import discovery, management
from alpaca.camera import Camera

# ACC is the accessories-only server to control cover, rotator, focuser etc does not include scope control
# Autoslew includes these acccessories and also scope control

# Filter wheel not alpaca compatible? Dome? Camera? etc

servers = discovery.search_ipv4()
print(servers)

for server in servers:
    print(f"At {server}:")
    print(f"    v{management.apiversions(server)} server")
    print(f"    {management.description(server)['ServerName']}")
    devs = management.configureddevices(server)
    for dev in devs:
        device_type_lower = dev['DeviceType'].lower()
        if device_type_lower == "camera":
            try:
                C = Camera(server, dev['DeviceNumber'])
                c_name = C.Name
                print(f"    {dev['DeviceType']}[{dev['DeviceNumber']}]:  {dev['DeviceName']} - {c_name}")
            except:
                print(f"    {dev['DeviceType']}[{dev['DeviceNumber']}]:  {dev['DeviceName']}")
        else:
            print(f"    {dev['DeviceType']}[{dev['DeviceNumber']}]:  {dev['DeviceName']}")

