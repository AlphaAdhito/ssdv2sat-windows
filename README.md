# ssdv2sat-windows

Windows-friendly fork of ssdv2sat with batch scripts and minor compatibility fixes for transmitting and receiving SSDV images via FM radio.

## Requirements

- Python 3.x (from https://python.org)
  - Make sure to check **"Add Python to PATH"**
- Dire Wolf
- sox
- ssdv.exe

Notes:
- `sox.exe` must be located inside the `sox-14-4-2` folder (as referenced in `config.ini`)
- `ssdv.exe` must be placed in the project root directory

## Python Setup (Required)

Python 3.8 or newer

Works with Python 3.9 / 3.10 / 3.11

1. Go to:
  https://www.python.org/downloads/windows/
  Click “Download Python 3.x”

2. When the installer opens:
  Check this box:
  Add Python to PATH
  Then click:
  Install Now
  This step is mandatory for your .bat files to work.
  To verify, open Command Prompt (type cmd on windows search) and type:
  python --version
  You should see something like:
  Python 3.11.x (or any version that you download)

3. Required Python packages
  pip install pillow


## How to Use (TX)

1. Prepare the image that you want to be sent via SSDV
2. Drag an image onto `transmit.bat`
3. Enter your callsign
4. Transmission starts automatically

## How to Use (RX)

1. Double-click `run_rx.bat`
2. Dire Wolf starts automatically (if not already running)
3. RX begins

## Notes

- These scripts are tested on Windows 10/11
- This repository contains small, Windows-specific modifications to the original `tx.py` to improve compatibility (mainly `sox.exe` invocation and path handling)

## Credit & Modifications

This project is based on the original **ssdv2sat** by hobisatelit:

https://github.com/hobisatelit/ssdv2sat  
License: GPL-3.0-or-later

The following changes were made for Windows compatibility:

- Minor modification to `tx.py` to ensure correct `sox.exe` invocation on Windows
- Added Windows `.bat` launch scripts for TX and RX
- Simplified configuration paths for portable Windows use

All core SSDV encoding/decoding logic remains unchanged and belongs to the original author.
