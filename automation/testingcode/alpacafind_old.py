from alpaca import discovery, management

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
        print(f"    {dev['DeviceType']}[{dev['DeviceNumber']}]:  {dev['DeviceName']}")

