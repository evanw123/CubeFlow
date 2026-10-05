# CubeFlow

CubeFlow is an end-to-end computer-vision application for scanning, validating,
solving, and visualizing a physical 3x3 Rubik's Cube. The hosted app acquires
the camera directly in the browser, so visitors do not need Python, OpenCV, or
a native desktop window.

## Features

- Browser webcam capture with a responsive 3x3 guide
- Six-color session calibration
- LAB color matching with the existing white HSV rule
- Seven-reading sticker histories with a five-reading stability threshold
- Guided six-face scanning and live interpreted colors
- Manual sticker correction with locked centers
- Physical cube-state validation
- Standard Kociemba solve
- Experimental PyCube-Solver-backed CFOP Beta
- Fully browser-based, rotatable 3D solution playback
- Per-browser, expiring in-memory scan sessions

## Live Demo

Deploy the repository with the included Render Blueprint, then add the resulting
`https://<service-name>.onrender.com` URL here.

## Research Results

CubeFlow was evaluated across 15 trials under five lighting and calibration
conditions.

Recalibration improved sticker-recognition accuracy from:

- 53.7% to 97.1% under dim lighting
- 79.0% to 95.2% under bright directional lighting

## Local Installation

Python 3.11 or newer is recommended.

```bash
python3.11 -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
```

## Local Web App

The browser-camera workflow is the default web experience:

```bash
source venv311/bin/activate
python app_server.py
```

Open `http://127.0.0.1:8765`, choose **Scan Cube**, and click **Start Camera**.
The browser preview, calibration, scanning, review, solving, and 3D playback all
run through the same web app.

The native scanner remains available as a local research/debug fallback:

```bash
source venv311/bin/activate
python camera_test.py
```

## Web Deployment Architecture

CubeFlow is deployed as one same-origin Python web service:

1. The browser owns webcam acquisition through `getUserMedia`.
2. Video remains local to the browser and renders at the browser's frame rate.
3. JavaScript samples nine small sticker regions at approximately 10 Hz.
4. Only compact BGR sample arrays are posted to the Python API.
5. Python applies the same LAB/HSV classifier used by the native scanner.
6. Calibration, scan history, corrections, and solve results are isolated in an
   expiring in-memory browser session.
7. The existing static web app and browser 3D viewer are served from the same
   service as the API.

The server honors `HOST`, `PORT`, and `CUBEFLOW_MODE`. In hosted mode it binds
to `0.0.0.0:$PORT`, does not launch native camera/viewer processes, and exposes
`GET /healthz` for platform health checks.

## Deploy to Render

1. Push this repository, including `render.yaml`, to GitHub.
2. In Render, choose **New > Blueprint**.
3. Connect `evanw123/CubeFlow` and approve the Blueprint.
4. Render installs `requirements-cloud.txt`, starts `app_server.py`, and checks
   `/healthz`.
5. Open the generated HTTPS URL and grant camera permission when **Start Camera**
   is clicked.

No secrets or persistent disk are required. Render supplies the public `PORT`;
the included server reads it automatically.

## Browser Camera Permissions

Webcam access requires a secure context. It works on Render's HTTPS URL and on
`localhost` during development. Permission is requested only after the user
clicks **Start Camera**. If access is denied, enable camera permission for the
site in browser settings and retry.

## Tests

```bash
PYTHONPATH=. ./venv311/bin/pytest -q
npm test --prefix webapp
```

Focused hosted-scanner tests can be run with:

```bash
PYTHONPATH=. ./venv311/bin/pytest -q \
  tests/test_browser_scanner.py \
  tests/test_web_sessions.py \
  tests/test_hosted_server.py
```

## Third-Party Attribution

- Standard solving uses the `kociemba` Python package.
- CFOP Beta vendors PyCube-Solver by saiakarsh193 under the MIT License. Its
  original README and license are preserved in `third_party/pycube_solver/`.
- OpenCV is used by the shared backend classifier. Hosted builds use
  `opencv-python-headless`; local native scanning uses `opencv-python`.

## Limitations

- Browser sessions are intentionally in memory. A Render restart clears active
  calibrations, scans, corrections, and solve results.
- The app has no accounts, so sessions do not synchronize across devices.
- Browser camera quality and color recognition still depend on lighting,
  reflections, camera white balance, and careful six-color calibration.
- CFOP remains experimental and is not the primary solve path.
- The native OpenCV scanner and pygame viewer are local development fallbacks;
  hosted operation never launches them.
