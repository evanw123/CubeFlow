# CubeFlow

CubeFlow is an end-to-end computer-vision application for scanning, validating,
solving, and visualizing a physical 3×3 Rubik's Cube.

## Live Demo

**[Try CubeFlow →](https://cubeflow.onrender.com/)**

No installation is required. Allow camera access, calibrate the six cube colors,
and scan a physical Rubik's Cube directly in your browser.

## Features

- Browser-based webcam scanning with a responsive 3×3 guide
- Six-color session calibration
- Real-time color recognition and stability detection
- Guided six-face scanning
- Manual sticker correction
- Physical cube-state legality validation
- Standard Kociemba solving
- Experimental CFOP solving
- Interactive 3D solution playback
- Standard and CFOP move-by-move visualization

## Research

I evaluated CubeFlow across 15 trials under five lighting and calibration
conditions to study how changes in illumination affect color recognition.

Recalibration improved sticker-recognition accuracy from:

- **53.7% → 97.1%** under dim lighting
- **79.0% → 95.2%** under bright directional lighting

[Read the full research paper](research/CubeFlow_Research_Paper.pdf)

## How It Works

1. The browser accesses the user's webcam through `getUserMedia`.
2. A 3×3 guide identifies the nine Rubik's Cube sticker regions.
3. JavaScript samples the sticker colors and sends compact color measurements
   to the Python backend.
4. CubeFlow classifies the stickers using session-specific calibration.
5. The user captures all six faces using a guided orientation sequence.
6. The reconstructed state is checked for physical legality.
7. The cube is solved using either the standard solver or experimental CFOP path.
8. The solution can be explored through an interactive browser-based 3D viewer.

## Local Installation

Python 3.11 or newer is recommended.

```bash
python3.11 -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
