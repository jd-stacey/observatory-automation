# Project Structure

```
automation/
├── config
│   ├── devices.yaml
│   ├── exposures.yaml
│   ├── headers.yaml
│   ├── observatory.yaml
│   ├── paths.yaml
│   └── platesolving.yaml
├── sessions
│   ├── solver_status.json
│   └── target.json
├── src
│   └── autopho
│       ├── __pycache__
│       │   └── __init__.cpython-39.pyc
│       ├── config
│       │   ├── __pycache__
│       │   │   └── loader.cpython-39.pyc
│       │   └── loader.py
│       ├── devices
│       │   ├── __pycache__
│       │   │   └── camera.cpython-39.pyc
│       │   ├── drivers
│       │   │   ├── __pycache__
│       │   │   │   ├── alpaca_cover.cpython-39.pyc
│       │   │   │   ├── alpaca_filterwheel.cpython-39.pyc
│       │   │   │   ├── alpaca_rotator.cpython-39.pyc
│       │   │   │   └── alpaca_telescope.cpython-39.pyc
│       │   │   ├── alpaca_cover.py
│       │   │   ├── alpaca_filterwheel.py
│       │   │   ├── alpaca_rotator.py
│       │   │   └── alpaca_telescope.py
│       │   └── camera.py
│       ├── imaging
│       │   ├── __pycache__
│       │   │   ├── __init__.cpython-39.pyc
│       │   │   ├── file_manager.cpython-39.pyc
│       │   │   ├── fits_utils.cpython-39.pyc
│       │   │   └── session.cpython-39.pyc
│       │   ├── __init__.py
│       │   ├── file_manager.py
│       │   ├── fits_utils.py
│       │   └── session.py
│       ├── platesolving
│       │   ├── __pycache__
│       │   │   └── corrector.cpython-39.pyc
│       │   ├── corrector_OLD.py
│       │   └── corrector.py
│       ├── targets
│       │   ├── __pycache__
│       │   │   ├── observability.cpython-39.pyc
│       │   │   └── resolver.cpython-39.pyc
│       │   ├── observability.py
│       │   └── resolver.py
│       ├── utils
│       ├── __init__.py
│       └── main.py
├── main.py
├── README.md
├── requirements.txt
└── test_camera_capture.py
```
