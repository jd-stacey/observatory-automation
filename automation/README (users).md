# T2 Automation Software - User Guide (Being Drafted....)
## At Start-up
### 1. Connect Wi-Fi internet to 'eduroam' network.
<img src="img/eduroam.png" width=200/>

### 2. Ensure Autoslew <img src="img/autoslew.png" width="30" style="vertical-align: text-bottom;"/> and ASA ACC <img src="img/acc.png" width="30" style="vertical-align: text-bottom;"/> are running.
<img src="img/autoslewss.png" height="200"/>   <img src="img/accss.png" height="200"/>

### 3. Open ASCOM Remote <img src="img/ascomremote.png" width="30" style="vertical-align: text-bottom;"/> and ensure drivers are connected and the Remote Server is Up.
<img src="img/ascomremoteconnected.png"/>

If drivers are not connected, e.g.:

<img src="img/ascomremotenotconnected.png"/>

Press 'Connect' and wait for confirmation messages (Note: the filter wheel must not be connected to ANY other software, i.e. ensure MaximDL, NINA etc are closed, or it will not connect), e.g.:

<img src="img/ascomremoteconnectmsgs.png"/>

Then press 'Start' and wait for confirmation messages, e.g.:

<img src="img/ascomremoteconnectmsgs2.png"/>

### 4. Open a Command Prompt from the Start Menu
<img src="img/cmd.png"/>

### 5. In the terminal window, type:
```powershell
conda activate drivescope
```
The prompt prefix should change to (drivescope), e.g.:
```powershell
(drivescope) C:\Users\asa
```

### 6. Change directories to the automation folder, by either (depending on which folder you start in):
```powershell
cd Documents\JS\automation
cd automation
```
Hints: You can use 'TAB' to auto-complete. E.g. if u type 'cd doc' and hit 'TAB' it should autocomplete the rest of the folder/file name. Type 'dir' to see the contents of the folder you are currently in. Type 'cd ..' to go up a folder in the structure.

Your final command prompt should look like this:
```powershell
(drivescope) C:\Users\asa\Documents\JS\automation>
```
# Taking a Single Image (Determining Exposure Time)
You may wish to take a single image (or a series of single images) to confirm you have the correct target and to determine the optimal exposure time for your target.

### Important Notes:
- Cover operations: This program will NOT close the covers after an image is taken, you must close the covers manually if there are no further observations.
- Telescope parking: This program will NOT park the telescope after an image is taken, it will turn its motors off, but it will remain at its location.
- Camera coolers: This program will NOT initiate the camera's coolers.

The program to take a single image is called via:
```powershell
python t2_singleimage.py [TARGET] [OPTIONS]
```
## Basic Usage

### Using TIC ID
Any of these formats are acceptable:
```powershell
python t2_singleimage.py 123456789
python t2_singleimage.py TIC123456789
python t2_singleimage.py TIC-123456789
```
Target coordinates will be determined via TIC look-up. The exposure time must be entered using command line arguments.

### Command Line Arguments
Command line arguments can be used for additional customization and to override program defaults.

| Option | Description | Default |
|--------|-----------|---------|
|`-h` or `--help` | Displays help message and exits | `-` |
|`--exposure-time` (Required) | Exposure time in seconds for the image | `-` |
|`--coords` | Resolves target based on J2000 coordinates ("RA_DEG DEC_DEG") instead of TIC ID | `-` |
|`--current-position` | Take image at current position (no telescope slewing, no observability checks) | `False` |
|`--filter` | Selects the filter to use (L/B/G/R/C/I/H) | `C` |
|`--log-level` | Terminal display logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
|`--ignore-twilight` | Bypass twilight (Sun Altitude) checks for daytime testing | `False` |

Notes:
- Filter options: L=Lum, B=Blue, G=Green, R=Sloan-r, C=Clear, I=Sloan-i, H=H-alpha
- Observability: The program will check that the target is above 30° altitude and confirm that the Sun's altitude is low enough to allow observations. Using the `--ignore-twilight` command line argument will bypass Sun altitude checks and should only be used for daytime testing purposes with the dome closed. The program will terminate if either observability condition is not met.

#### Examples
To observe a TIC target with 5 second exposure time:
```powershell
python t2_singleimage.py 123456789 --exposure-time 5.0
```
To observe a TIC target with 10 second exposure time using the Lum filter:
```powershell
python t2_singleimage.py 123456789 --exposure-time 10.0 --filter L
```
- To observe a target without a TIC ID via its J2000 coordinates (RA and Dec in decimal degrees) with 20 second exposure time with the Clear filter (Clear is the default):
```powershell
python t2_singleimage.py --coords "256.263748 -42.17295" --exposure-time 20.0
```

#### Determining Optimal Exposure Time
Images are saved to the following directory (based on the observation date):
```
P:\Photometry\YYYY\YYYYMMDD\T2\singleimages

e.g.:
P:\Photometry\2025\20250930\T2\singleimages
```
Use File Explorer <img src="img/fileexplorer.png" width="30" style="vertical-align: text-bottom;"/> to navigate to the image directory and find the .fits file (P: drive is also called 'photometryshare').

Open the .fits file in MaxIm DL <img src="img/maximdl.png" width="30" style="vertical-align: text-bottom;"/> by right-clicking the file and selecting 'Open With -> MaxIm DL' <img src="img/openwithmaximdl.png" height="20" style="vertical-align: text-bottom;"/>.

Enable crosshairs by right-clicking in your image and selecting 'Crosshairs -> Visible'.

<img src="img/maximdlcrosshairs.png" width="300"/>

You will likely need to zoom out to see your full image (use mouse wheel or the zoom buttons at the top <img src="img/maximdlzoom.png" height="20" style="vertical-align: text-bottom;"/>).

Open the information window by clicking the information icon at the top <img src="img/maximdlinfo.png" height="20" style="vertical-align: text-bottom;"/>, or via 'Ctrl + I' or via 'View -> Information Window'.

<img src="img/maximdlinfowindow.png" width="140"/>

Position the aperture over your target star (make sure to select the correct star, it might not be the one at/near the crosshair centre) and measure the maximum count (ideal is around 10,000-30,000). You can adjust the size of the aperture by right-clicking the image and selecting 'Set Aperture Radius'.

<img src="img/maximdlexp.png" width="500"/>

If counts are not appropriate, repeat procedure (take a new image) with a different exposure time. If the counts are too high, reduce the exposure time, if the counts are too low, increase the exposure time (remember a target's counts will usually increase as it rises in the sky, less atmosphere to see through). 

Once you have an optimised exposure time, you can proceed to Automated (Continuous) Photometry.

Close MaxIm DL.

# Automated (Continuous) Photometry

Automated Photometry has one primary mode, where targets are resolved based on their TIC ID.

The program is called via:
```powershell
python -u main.py [TARGET] [OPTIONS]
```

## Basic Usage

### Using TIC ID
Any of these formats are acceptable:
```powershell
python -u main.py 123456789
python -u main.py TIC123456789
python -u main.py TIC-123456789
```

Target coordinates and magnitude will be determined via TIC look-up and default exposure time calculated based on Gaia G-mag. The exposure time can (and should) be overridden using command line arguments.

### Command Line Arguments
Command line arguments can be used for additional customization and to override program defaults.

| Option | Description | Default |
|--------|-----------|---------|
|`-h` or `--help` | Displays help message and exits | `-` |
|`--coords` | Resolves target based on J2000 coordinates ("RA_DEG DEC_DEG") instead of TIC ID | `-` |
|`--filter` | Selects the filter to use (L/B/G/R/C/I/H) | `C` |
|`--exposure-time` | Override exposure time (seconds) | Calc from Gaia G-mag |
|`--log-level` | Terminal display logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
|`--duration` | Session duration (hours) | `-` |
|`--max-exposures` | Maximum number of exposures to take | `-` |
|`--ignore-twilight` | Bypass twilight (Sun Altitude) checks for daytime testing | `False` |
|`--no-park` | Skip telescope parking at end of session | Auto-park |

Notes:
- Filter options: L=Lum, B=Blue, G=Green, R=Sloan-r, C=Clear, I=Sloan-i, H=H-alpha
- Parking: The telescope will automatically slew back to home position at the end of the session, using the `--no-park` argument will leave it at its observing position (covers will still close and camera coolers will be turned off).
- Twilight: the telescope will automatically stop taking images once the target becomes unobservable due to either falling below 30° altitude or due to the Sun's position. Using `--ignore-twilight` will ignore the Sun's position and it will continue imaging indefinitely as long as the target remains above 30° altitude (regardless of the time of day or whether the dome is open or closed).
#### Examples

- To observe a TIC target with 10 second exposure time:
```powershell
python -u main.py 123456789 --exposure-time 10.0
```
- To observe a TIC target with 30 second exposure time with the Lum filter:
```powershell
python -u main.py 123456789 --exposure-time 30.0 --filter L
```
- To observe a target without a TIC ID via its J2000 coordinates (RA and Dec in decimal degrees) with 20 second exposure time with the Clear filter (Clear is the default):
```powershell
python -u main.py --coords "256.263748 -42.17295" --exposure-time 20.0
```
- To observe a TIC target with 5 second exposure time and more detailed console logging:
```powershell
python -u main.py 123456789 --exposure-time 5.0 --log-level DEBUG
```
### On Observability
If your target is not immediately observable (hasn't risen about 30° altitude yet, or it is not quite twilight) the program will automatically keep checking for observability at regular intervals (60 seconds) and will automatically start observations once observability conditions are satisfied. E.g.:

<img src="img/observability.png"/>

<img src="img/"/>


### Platesolving...

### Field Rotator and Rotator Flips...

### Mirror/Log Parsing...

## Troubleshooting
