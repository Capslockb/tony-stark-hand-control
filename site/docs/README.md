# Documentation

User-facing documentation for Tony Stark Hand Control.

## Table of contents

| File | What it covers |
|---|---|
| [installation.md](installation.md) | Quick install for Windows / Linux / macOS, manual install, verifying the install |
| [calibration.md](calibration.md) | How to print the checkerboard, run the calibration, interpret the numbers |
| [gestures.md](gestures.md) | Full gesture reference with diagrams — engage, click, swipe |
| [3d_room_mapping.md](3d_room_mapping.md) | Interactive 3D room mapping, anchor placement, save/load |
| [performance.md](performance.md) | Every GUI knob explained, with trade-offs |
| [troubleshooting.md](troubleshooting.md) | Common issues + fixes |
| [architecture.md](architecture.md) | How the code is organized, data flow, performance characteristics |
| [ollama_integration.md](ollama_integration.md) | Optional cloud / local LLM gesture recognition |
| [test_results.md](test_results.md) | Live test results captured at the v1.0.0 release |

## Diagrams

All diagrams are auto-generated SVG (dark theme, no external assets):

- [images/architecture.svg](images/architecture.svg) — overall system architecture
- [images/gestures.svg](images/gestures.svg) — gesture reference with stylized hands
- [images/3d_room.svg](images/3d_room.svg) — example of the 3D room view

Regenerate them after a refactor:

```bash
python docs/generate_architecture.py
python docs/generate_gestures.py
python docs/generate_3d_room.py
```

## For contributors

See [../CONTRIBUTING.md](../CONTRIBUTING.md) for the contribution workflow.
