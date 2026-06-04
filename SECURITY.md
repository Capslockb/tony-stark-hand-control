# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Privacy

This is a **local-first** application. The hand-tracking pipeline does not transmit any data off the device. Specifically:

- **No telemetry.** The app does not phone home, report usage, or check for updates.
- **No network calls** in the hand-tracking code path.
- **Camera feeds** stay in memory and on disk on your local machine. They are not uploaded anywhere.
- **Calibration data** (`calibration.npz`) and **room maps** (`room_map.json`) are stored locally and are not transmitted.
- **The Ollama tab** is **off by default**. If you enable it and configure a cloud endpoint (e.g. `https://ollama.com`), the frames you submit will be sent to that endpoint. The app does not submit anything unless you have explicitly enabled Ollama and clicked Save.

## What data lives where

| File | Where | What |
|---|---|---|
| `calibration.npz` | Next to the script | Camera intrinsics + extrinsics. May be fingerprintable. |
| `room_map.json` | Next to the script | Your 3D room anchors (walls, zones, hotspots). |
| `tony_stark_*.lock` | `%TEMP%` | Single-instance lock file. Always empty. |
| No logs | — | The app does not log camera frames, gestures, or any PII. |

## Reporting a Vulnerability

This is a personal project without a public security budget, but I take reports seriously. If you find a vulnerability:

1. **Do NOT open a public GitHub issue.** Email me privately at: see the latest commit author email.
2. Include: a description, reproduction steps, and your assessment of severity.
3. I will respond within 7 days with a triage.
4. Critical issues will get a fix within 30 days.

## Disclosure timeline

- Day 0: report received
- Day 7: triage decision
- Day 30: fix for critical issues; advisory published here
- Day 90: public disclosure (if applicable)

## Threat model

This app is designed for personal use on a trusted machine. It is **not** designed for:

- Multi-user shared systems where camera feeds could be a privacy concern
- Hostile environments where a malicious actor could install a modified version
- Air-gapped networks that need explicit offline-only behavior (the app is offline by default, but the Ollama tab could leak frames if misconfigured)

If you need any of these, please audit the code and build from source.
