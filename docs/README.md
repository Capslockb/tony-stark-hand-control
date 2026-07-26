# Documentation

User-facing documentation for Tony Stark Hand Control.

## Table of contents

| File | What it covers |
|---|---|
| [installation.md](installation.md) | Platform status and setup: Windows primary, with experimental Linux/macOS source-install guidance |
| [calibration.md](calibration.md) | How to print the checkerboard, run the calibration, interpret the numbers |
| [gestures.md](gestures.md) | Full gesture reference with diagrams — engage, click, swipe |
| [3d_room_mapping.md](3d_room_mapping.md) | Manual room anchors and JSON persistence; experimental live stereo coordinates remain unvalidated pending Issue #6 |
| [performance.md](performance.md) | Every GUI knob explained, with trade-offs |
| [troubleshooting.md](troubleshooting.md) | Common issues + fixes |
| [architecture.md](architecture.md) | How the code is organized, data flow, performance characteristics |
| [ollama_integration.md](ollama_integration.md) | Optional cloud / local LLM gesture recognition |
| [test_results.md](test_results.md) | Historical test results captured for the v1.0.0 release |

## Diagrams

The repository currently ships these SVG assets:

- [images/architecture.svg](images/architecture.svg) — overall system architecture
- [images/gestures.svg](images/gestures.svg) — gesture reference with stylized hands
- [images/3d_room.svg](images/3d_room.svg) — example of the 3D room view

The previously documented `docs/generate_architecture.py`, `docs/generate_gestures.py`, and `docs/generate_3d_room.py` commands are not present in the current tree. The diagrams therefore cannot currently be regenerated from committed source scripts. Any future diagram change should include a reviewable source or reproducible generation step before the assets are described as auto-generated.

## For contributors

See [../CONTRIBUTING.md](../CONTRIBUTING.md) for the contribution workflow.
