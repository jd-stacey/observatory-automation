import win32com.client

telescope = win32com.client.Dispatch("ASCOM.AlpacaDynamic1.Telescope")


print('Connecting to Telescope...')
telescope.Connected = True

print('Checking Connection Status...')
print(f'Status: {telescope.Connected}')



telescope.Connected = False
print('Disconnected from Telescope.')