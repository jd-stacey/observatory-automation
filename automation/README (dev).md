# At Start-up
### 1. Connect Wi-Fi internet to 'eduroam' network.
<img src="img/eduroam.png" width=200/>

### 2. Open ASCOM Remote <img src="img/ascomremote.png" width=30/> and ensure drivers are connected and the Remote Server is Up.
<img src="img/ascomremoteconnected.png"/>

If drivers are not connected, e.g.:

<img src="img/ascomremotenotconnected.png"/>

press 'Connect' and wait for confirmation messages (Note: the filter wheel must not be connected to ANY other software, i.e. ensure MaximDL, NINA etc are closed, or it will not connect):

<img src="img/ascomremoteconnectmsgs.png"/>

then press 'Start' and wait for confirmation messages, e.g.:

<img src="img/ascomremoteconnectmsgs2.png"/>

### 3. Open a Command Prompt from the Start Menu
<img src="img/cmd.png"/>

### 4. In the terminal window, type:
```powershell
conda activate drivescope
```
The prompt prefix should change to (drivescope), e.g.:
```powershell
(drivescope) C:\Users\asa
```

### 5. Now change directories to the automation folder, by either (depending on which folder you start in):
```powershell
cd Documents\JS\automation
cd automation
```
Hints: You can use 'TAB' to auto-complete. E.g. if u type 'cd doc' and hit 'TAB' it should autocomplete the rest of the folder/file name. Type 'dir' to see the contents of the folder you are currently in.

Your final command prompt should look like this:
```powershell
(drivescope) C:\Users\asa\Documents\JS\automation>
```

<img src="img/"/>

# Configuration files (`*.yaml`)

**Directory**: `automation\config\`

**Structure** :

```
automation/
├── config
│   ├── devices.yaml
│   ├── exposures.yaml
│   ├── field_rotation.yaml
│   ├── headers.yaml
│   ├── observatory.yaml
│   ├── paths.yaml
│   └── platesolving.yaml
```

| File | Description |
|------|-------------|
| `devices.yaml` | Addresses, hardware limits, defaults etc for telescope, cameras, cover, rotator, filter wheel & focuser  |
| `exposures.yaml` | Defaults for photometry exposures (based on Gaia G-mag) and filter scaling  |
| `field_rotation.yaml` | Defaults for field rotator (photometry only) including minimum threshold and update rate |
| `headers.yaml` | Some default headers and values for `.fits` creation  |
| `observatory.yaml` | Defaults for observatory location (long, lat, alt) and altitude limits for telescope (30°) and Sun (-12°) |
| `paths.yaml` | Default filepaths for images, logs and `.json` files |
| `platesolving.yaml` | Defaults for platesolving/correcting and spectroscopy imaging (e.g. exp time, duration, correction interval etc)  |

# Spectroscopy Mode

Three main operating modes:
1. **Single Target Mode** - Observe a specific TIC catalog target or manual coordinates
2. **Mirror Mode** - Continuously monitor another telescope's position and mirror its targets
3. **Dry Run Mode** - Simulate operations without hardware movements for testing purposes only

## Basic Usage
### Basic Command Structure
```powershell
python spectro_main_9.py [MODE] [TARGET] [OPTIONS]
```
For CLI help:
```powershell
python spectro_main_9.py -h
python spectro_main_9.py --help
```
### Operating Modes
#### 1. To Observe a specific TIC catalog target
```powershell
python spectro_main_9.py tic 123456789
```
#### 2. Manual Coordinates
```powershell
python spectro_main_9.py coords "44.5 -30.2"
```
*Note: Coordinates are in degrees (RA DEC)°
#### 2. Mirror Mode (Continuous Monitoring)
```powershell
python spectro_main_9.py mirror [OPTIONAL FILEPATH TO JSON FILE]
```
*Note: default mirror json filepath is `spectro_mirror_file` in `paths.yaml`
### Command Line Options
| Option | Description | Default |
|--------|-------------|---------|
|`--config-dir` | Configuration directory | `config` |
|`--log-level` | Terminal display logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
|`--dry-run` | Simulate without hardware movement or imaging | `False` |
|`--ignore-twilight` | Bypass twilight (Sun Altitude) checks for daytime testing (will also prevent shutdown) | `False` |
|`--poll-interval` | How often to check mirror file for new targets (seconds) | `10.0` |
|`--duration` | Session duration (hours) | *From `platesolving.yaml` config* |
|`--exposure-time` | Override exposure time (seconds) | *From `platesolving.yaml` config* (see below) |

#### Exposure Time Heirarchy
The system determines exposure time using this priority order:
1. `--exposure-time` command line argument (highest)
2. `spectro_acquisition.exposure_time` in `platesolving.yaml` config
3. Calculated from target magnitude (Gaia G-mag)
4. Default fallback (currently 120.0 s)

### Example Command: Observe a single TIC target for 2 hours with 30s exposures showing DEBUG level on-screen logging:
```powershell
python spectro_main_9.py tic 123456789 --duration 2.0 --exposure-time 30.0 --log-level DEBUG
```


## Mirror Mode Operations

### Basic Workflow
1. **Monitor** - Continuously polls the mirror json file every `--poll-interval` seconds
2. **Detect** - New timestamp triggers target acquisition
3. **Validate** - Checks target observability and coordinate validity
4. **Slew** - Moves telescope to new position
5. **Image** - Runs acquisition + science sequence
6. **Repeat** - Returns to monitoring for next target

#### Failed Target Handling
- Invalid coordinates are logged and skipped
- Unobservable targets are marked as failed
- Failed targets are cached to prevent retry loops
- System continues monitoring for new valid targets

#### Mirror File Format
The system monitors the json file (default path is `spectro_mirror_file` from `paths.yaml`) for telescope position updates, e.g:
```json
{
    "latest_move" : {
        "timestamp": "2025-09-23T19:10:15.344000+00:00",
        ...
        "ra_deg": 123.456789,
        "dec_deg": -45.678123
    }
}
```

#### Acquisition Phase
- **Purpose**: Achieve precise target centering for spectroscopy
- **Exposure**: Generally short, but requires sufficient exp. for platesolver to work
- **Corrections**: Applied every frame where available until within threshold
- **Completion**: Switches to science mode when target star appropriately positioned

#### Science Phase
- **Purpose**: Collect spectroscopic data
- **Exposure**: Full exposure time based on input values, config or magnitudes
- **Corrections**: Applied every N frames (from `correction_interval` in `platesolving.yaml` config)
- **Duration**: Runs until session time limit (e.g. `--duration`) or observability ends


```
```








