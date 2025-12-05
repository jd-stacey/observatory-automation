---
title: T2 Automation Guide (Users)
---


# T2 Automation Software - User Guide (Drafting...)
## At Start-up (RaptorTCU) - For Both Photometry and Spectroscopy
### 1. Connect Wi-Fi internet to 'eduroam' network.
<img src="img/eduroam.png" width=180/>

### 2. Ensure Autoslew <img src="img/autoslew.png" width="30" style="vertical-align: text-bottom;"/> and ASA ACC <img src="img/acc.png" width="30" style="vertical-align: text-bottom;"/> are running.
<img src="img/autoslewss.png" height="200"/>   <img src="img/accss.png" height="200"/>

### 3. Open ASCOM Remote <img src="img/ascomremote.png" width="30" style="vertical-align: text-bottom;"/> and ensure drivers are connected and the Remote Server is Up.
<img src="img/ascomremoteconnected.png" width="170"/>

<!-- <div style="page-break-after: always;"></div> -->

If drivers are not connected, e.g. if you see:

<img src="img/ascomremotenotconnected.png" width="150"/>

Press 'Connect' and wait for confirmation messages (Note: the filter wheel must not be connected to ANY other software, i.e. ensure MaximDL, NINA etc are closed, or it will not connect), e.g.:

<img src="img/ascomremoteconnectmsgs.png"/>

Then press 'Start' and wait for confirmation messages, e.g.:

<img src="img/ascomremoteconnectmsgs2.png"/>

### 4. Open a Command Prompt from the Start Menu <img src="img/cmd.png" width="200" style="vertical-align: text-bottom;"/>


### 5. In the terminal window, type:
```bash
conda activate drivescope
```
The prompt prefix should change to (drivescope), e.g.:
```bash
(drivescope) C:\Users\asa>
```

### 6. Change directories to the automation folder, by either (depending on which folder you start in):
```bash
cd Documents\JS\automation
cd automation
```
Hints: You can use 'TAB' to auto-complete. E.g. if u type 'cd doc' and hit 'TAB' it should autocomplete the rest of the folder/file name. Type 'dir' to see the contents of the folder you are currently in. Type 'cd ..' to go up a folder in the structure.

<!-- <div style="page-break-after: always;"></div> -->

Your final command prompt should look like this:
```bash
(drivescope) C:\Users\asa\Documents\JS\automation>
```

<div style="page-break-after: always;"></div>

# Taking a Single Image (Determining Exposure Time)
You may wish to take a single image (or a series of single images) to confirm you have the correct target and to determine the optimal exposure time for your target.

### Important Notes:
- Cover operations: This program will NOT close the covers after an image is taken, you must close the covers manually if there are no further observations.
- Telescope parking: This program will NOT park the telescope after an image is taken, it will turn its motors off, but it will remain at its location.
- Camera coolers: This program will NOT initiate the camera's coolers.

The program to take a single image is called via:
```bash
python t2_singleimage.py [TARGET] [OPTIONS]
```
## Basic Usage

### Using TIC ID
Any of these formats are acceptable:
```bash
python t2_singleimage.py 123456789 [OPTIONS]
python t2_singleimage.py TIC123456789 [OPTIONS]
python t2_singleimage.py TIC-123456789 [OPTIONS]
```
Target coordinates will be determined via TIC look-up. **The exposure time must be entered using command line arguments.**

### Command Line Arguments
Command line arguments can be used for additional customization and to override program defaults.

| Option | Description | Default |
|--------|-----------|:---------:|
|`-h` or `--help` | Displays help message and exits | `-` |
|`--exposure-time` (**Required**) | Exposure time in seconds for the image | `-` |
|`--coords` | Resolves target based on J2000 coordinates ("RA_DEG DEC_DEG") instead of TIC ID | `-` |
|`--current-position` | Take image at current position (no telescope slewing, no observability checks) | `False` |
|`--filter` | Selects the filter to use (L/B/G/R/C/I/H) | `C` |
|`--log-level` | Terminal display logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
|`--ignore-twilight` | Bypass twilight (Sun Altitude) checks for daytime testing | `False` |

Notes:
- Filter options: L=Lum, B=Blue, G=Green, R=Sloan-r, C=Clear, I=Sloan-i, H=H-alpha
- Observability: The program will check that the target is above 30° altitude and confirm that the Sun's altitude is low enough to allow observations. Using the `--ignore-twilight` command line argument will bypass Sun altitude checks and should only be used for daytime testing purposes with the dome closed. The program will terminate if either observability condition is not met.

#### Examples
- To observe a TIC target with 5 second exposure time:
```bash
python t2_singleimage.py 123456789 --exposure-time 5.0
```
- To observe a TIC target with 10 second exposure time using the Lum filter:
```bash
python t2_singleimage.py 123456789 --exposure-time 10.0 --filter L
```
- To observe a target without a TIC ID via its J2000 coordinates (RA and Dec in decimal degrees) with 20 second exposure time with the Clear filter (Clear is the default):
```bash
python t2_singleimage.py --coords "256.263748 -42.17295" --exposure-time 20.0
```

#### Determining Optimal Exposure Time
Images are saved to the following directory (based on the observation date):
```
P:\Photometry\YYYY\YYYYMMDD\T2\singleimages

e.g., P:\Photometry\2025\20250930\T2\singleimages
```
Use File Explorer <img src="img/fileexplorer.png" width="30" style="vertical-align: text-bottom;"/> to navigate to the image directory and find the .fits file (P: drive is also called 'photometryshare').

<div style="page-break-after: always;"></div>

Open the .fits file in MaxIm DL <img src="img/maximdl.png" width="30" style="vertical-align: text-bottom;"/> by right-clicking the file and selecting 'Open With -> MaxIm DL' <img src="img/openwithmaximdl.png" height="20" style="vertical-align: text-bottom;"/>.

Enable crosshairs by right-clicking in your image and selecting 'Crosshairs -> Visible'.

<img src="img/maximdlcrosshairs.png" width="350"/>

You will likely need to zoom out to see your full image (use mouse wheel or the zoom buttons at the top <img src="img/maximdlzoom.png" height="20" style="vertical-align: text-bottom;"/>).

Open the information window by clicking the information icon at the top <img src="img/maximdlinfo.png" height="20" style="vertical-align: text-bottom;"/>, or via 'Ctrl + I' or via 'View -> Information Window'.

<img src="img/maximdlinfowindow.png" width="240"/>

Position the aperture over your target star (make sure to select the correct star, it might not be the one at/near the crosshair centre) and measure the maximum count (ideal is around 10,000-30,000). You can adjust the size of the aperture by right-clicking the image and selecting 'Set Aperture Radius'.

<img src="img/maximdlexp.png" width="600"/>

If counts are not appropriate, repeat procedure (take a new image) with a different exposure time. If the counts are too high, reduce the exposure time, if the counts are too low, increase the exposure time (remember a target's counts will usually increase as it rises in the sky, less atmosphere to see through). 

Once you have an optimised exposure time, you can proceed to Automated (Continuous) Photometry.

Close MaxIm DL.

<div style="page-break-after: always;"></div>

# Automated (Continuous) Photometry

Automated Photometry has one primary mode, where targets are resolved based on their TIC ID.

## Basic Usage

The program is called via:
```bash
python -u main.py [TARGET] [OPTIONS]
```

### Using TIC ID
Any of these formats are acceptable:
```bash
python -u main.py 123456789
python -u main.py TIC123456789
python -u main.py TIC-123456789
```

Target coordinates and magnitude will be determined via TIC look-up and default exposure time calculated based on Gaia G-mag. The exposure time can (and should) be overridden using command line arguments (use Single Image Mode above to determine optimal exposure time).

### Command Line Arguments
Command line arguments can be used for additional customization and to override program defaults.

| Option | Description | Default |
|--------|-----------|:---------:|
|`-h` or `--help` | Displays help message and exits | `-` |
|`--coords` | Resolves target based on J2000 coordinates ("RA_DEG DEC_DEG") instead of TIC ID | `-` |
|`--filter` | Selects the filter to use (L/B/G/R/C/I/H) | `C` |
|`--exposure-time` (Recommended) | Override exposure time calculations (seconds) | `-` |
|`--log-level` | Terminal display logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
|`--duration` | Session duration (hours) | `-` |
|`--max-exposures` | Maximum number of exposures to take | `-` |
|`--ignore-twilight` | Bypass twilight (Sun Altitude) checks for daytime testing | `False` |
|`--no-park` | Skip telescope parking at end of session | `False` |

Notes:
- Filter options: L=Lum, B=Blue, G=Green, R=Sloan-r, C=Clear, I=Sloan-i, H=H-alpha
- Parking: The telescope will automatically slew back to home position at the end of the session, using the `--no-park` argument will leave it at its observing position (covers will still close and camera coolers will be turned off).
- Twilight: the telescope will automatically stop taking images once the target becomes unobservable due to either falling below 30° altitude or due to the Sun's position. Using `--ignore-twilight` will ignore the Sun's position and it will continue imaging indefinitely as long as the target remains above 30° altitude (regardless of the time of day or whether the dome is open or closed).
#### Examples

- To observe a TIC target with 10 second exposure time:
```bash
python -u main.py 123456789 --exposure-time 10.0
```
- To observe a TIC target with 30 second exposure time with the Lum filter:
```bash
python -u main.py 123456789 --exposure-time 30.0 --filter L
```
- To observe a target without a TIC ID via its J2000 coordinates (RA and Dec in decimal degrees) with 20 second exposure time with the Clear filter (Clear is the default):
```python
python -u main.py --coords "256.263748 -42.17295" --exposure-time 20.0
```
- To observe a TIC target with 5 second exposure time and more detailed console logging:
```python
python -u main.py 123456789 --exposure-time 5.0 --log-level DEBUG
```
### On Observability
If your target is not immediately observable (hasn't risen about 30° altitude yet, or it is not quite twilight) the program will automatically keep checking for observability at regular intervals (60 seconds) and will automatically start observations once observability conditions are satisfied. E.g.:

<img src="img/observability.png"/>

<div style="page-break-after: always;"></div>

### Files
Directories are automatically created and files saved according to date, e.g. (images in folders with the '_acq' suffix are used for target acquisition purposes):
```bash
P:\Photometry\YYYY\YYYYMMDD\T2\TIC123456789
```

### Platesolving/Guiding...

...
...

Gotta double-check - just run this on guestobserver@minervaphotometry?:
```bash
run_astrom_wrapper.sh
```



<div style="page-break-after: always;"></div>

# Automated Spectroscopy
Automated Spectroscopy has three primary operating modes:
- **Single Target Mode via TIC ID** - Observe a specific TIC catalog target.
- **Single Target Mode via Coordinates** - Observe a specific target via J2000 coordinates.
- **Mirror Mode** - Continuously monitor another telescope via log parsing and mirror its targets.

## Basic Usage
The program is called via:
```bash
python -u t2_spectro.py [MODE] [TARGET] [OPTIONS]
```

### Using TIC ID

Any of these formats are acceptable:
```bash
python -u t2_spectro.py tic 123456789
python -u t2_spectro.py tic TIC123456789
python -u t2_spectro.py tic TIC-123456789
```

### Using Coordinates
```bash
python -u t2_spectro.py coords "44.5 -30.2"
```
*Note: Both RA and Dec coordinates are in decimal degrees.

### Using Mirror Mode
```bash
python -u t2_spectro.py mirror
```

#### Log Parsing
To enable log parsing

Open Windows Powershell from the Start Menu <img src="img/powershell.png" width="200" style="vertical-align: text-bottom;"/>

Change to the P: drive by typing:
```bash
P:
```

Change directories to the temp folder by typing:
```bash
cd temp
```

Run the log parser by typing:
```bash
python parse_telcom_log.py
```
Leave Powershell running - it will continuously check for new spectroscopy targets and monitor dome closure messages from the other telescope.

### Command Line Arguments

Command line arguments can be used for additional customization and to override program defaults, though are generally not required in spectroscopy mode.

| Option | Description | Default |
|--------|-------------|:-------:|
|`--ignore-twilight` | Bypass twilight (Sun Altitude) checks for daytime testing (will also prevent shutdown) | `False` |
|`--exposure-time` | Override exposure time (seconds) | Set in config |
|`--duration` | Session duration (hours) | Set in config |
|`--poll-interval` | How often to check mirror file for new targets (seconds) | `10.0` |
|`--log-level` | Terminal display logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
|`--dry-run` | Simulate without hardware movement or imaging | `False` |

### Imaging and Plate-Solving During Spectroscopy

Imaging during spectroscopy is only used for plate-solving and guiding (positioning the star directly over the fibre), so the calculation of exposure times is adaptive, automatically adjusting based on responses from the external platesolver.


<div style="page-break-after: always;"></div>

# Telescope Shutdown Tool (T2shutdown.exe) <img src="img/shutdown.png" width="40" style="vertical-align: text-bottom;"/>

### DO NOT use this tool during normal telescope operations - it will perform physical actions on telescope systems.

### This tool will NOT interact with the cameras at all. 

#### If you have used the cameras in other programs (e.g. MaxIM DL) you MUST stop the coolers and disconnect the cameras in those programs manually.

## In Automated Photometry or Spectroscopy

The telescope should automatically handle shutdown procedures in both automated photometry and spectroscopy modes, closing covers, stopping the rotator and parking the telescope (unless the `--no-park` argument is used which prevents parking, or the `--ignore-twilight` argument is used which ignores sunrise) at the end of observations.

However, program errors, TCU restarts or manual observations via other programs, for example, may require manual shutdown of the telescope into a safe operating mode. The T2shutdown.exe program can be used for this purpose.

## Using the Shutdown Tool

### 1. Open the Tool
Open the tool by double-clicking the T2shutdown.exe file on the RaptorTCU Desktop.

<img src="img/shutdownexe.png"/>

<img src="img/shutdownmenu.png"/>

### 2. Initialise Connections

Ideally, Autoslew <img src="img/autoslew.png" width="30" style="vertical-align: text-bottom;"/> and ASA ACC <img src="img/acc.png" width="30" style="vertical-align: text-bottom;"/> should already be running, though the tool will try to launch them if it detects they are not running.

<div style="page-break-after: always;"></div>

Click '1. Start Autoslew & Check Connections'

<img src="img/shutdownstart.png"/>

The program will detect whether Autoslew is running (and try to launch it if it doesn't) and initialise various connections (this full process can take up to 45 seconds).

#### If any security warnings or user account alerts pop-up, make sure to click 'Yes' to allow them.
<img src="img/uac.png" width="300"/>

If successful, the system status for each device (Autoslew, Telescope, Rotator, Cover) should turn green and show their current status, e.g.:

<img src="img/shutdownstatus.png"/>

If unsuccessful, try re-checking connections by clicking '1. Start Autoslew & Check Connections' again. 

### 3. Shutdown the Telescope

Click '2. TELESCOPE SHUTDOWN'.

<img src="img/shutdownshutdown.png"/>

A series of warning messages will pop-up, if you continue past them the tool will stop the rotator, close the telescope covers, slew the telescope to its park position and turn off its motors.

<img src="img/shutdownmsg1.png" width="350"/>  <img src="img/shutdownmsg2.png" width="350"/>  

If successful, the system status for each device should update, e.g.:

<img src="img/shutdowncompletestatus.png"/>

And the Activity Log should show successful completion, e.g.:

<img src="img/shutdowncompletelog.png"/>

You can now exit the Shutdown Tool.

<div style="page-break-after: always;"></div>

# Troubleshooting

## Field Rotator and Rotator Flips...


<img src="img/"/>
