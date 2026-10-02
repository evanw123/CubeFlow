# CubeFlow

CubeFlow is an end-to-end computer-vision system for scanning, validating,
solving, and visualizing a physical 3×3 Rubik's Cube.

## Features

- Six-color camera calibration
- Webcam-based sticker recognition
- Guided six-face scanning
- Manual correction interface
- Physical cube-state validation
- Standard two-phase solving
- CFOP solving integration
- Interactive 3D solution playback

## Research

CubeFlow was evaluated across 15 trials under five lighting and calibration
conditions.

Recalibration improved sticker-recognition accuracy from:

- 53.7% to 97.1% under dim lighting
- 79.0% to 95.2% under bright directional lighting

## Running CubeFlow

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app_server.py
