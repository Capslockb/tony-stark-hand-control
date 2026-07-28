# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Privacy

This is a **local-first** application. Camera-frame input is processed on-device by the core hand-tracking pipeline. MediaPipe's current privacy notice says that Tasks API input data is not sent to Google, while API performance and utilization metrics may be sent to Google. Specifically:

- **No repository-added application telemetry.** This project does not add its own usage reporting, analytics, or update checker. Third-party libraries may have separate current privacy behavior; review their policies before deployment.
- **Network boundaries are explicit.** The application may download the MediaPipe model when it is missing, MediaPipe Tasks may send performance and utilization metrics under Google's current notice, and the optional Ollama feature sends snapshots to the endpoint you configure.
- **Camera frames** are processed in memory by the local tracking pipeline and are not intentionally persisted or uploaded by that path.
- **Calibration data** (`calibration.npz`) and **room maps** (`room_map.json`) are stored locally and are not transmitted by the core pipeline.
- **The Ollama tab** is **off by default**. If you enable it and configure a remote endpoint, snapshots submitted through that feature are sent to the configured endpoint. Review that provider's authentication, retention, and access controls before enabling remote inference.

## What data lives where

| File | Where | What |
|---|---|---|
| `calibration.npz` | Next to the script | Camera intrinsics + extrinsics. May be fingerprintable. |
| `room_map.json` | Next to the script | Your 3D room anchors (walls, zones, hotspots). |
| `tony_stark_*.lock` | `%TEMP%` | Single-instance lock file. Always empty. |
| No application log file by default | — | The app does not intentionally persist camera frames, gestures, or personal data to a log file. |

## Reporting a Vulnerability

This is a personal project without a public security budget, but I take reports seriously. If you find a vulnerability:

1. **Do NOT open a public GitHub issue.** Email me privately at: see the latest commit author email.
2. Include: a description, reproduction steps, and your assessment of severity.
3. I will respond within 7 days with a triage.
4. Critical issues will get a fix within 30 days.

Do not include credentials, private camera frames, calibration files, room maps, private logs, or third-party personal data in public issues or pull requests. Share only the minimum reproduction details needed, and use the private reporting route for sensitive material.

## Disclosure timeline

- Day 0: report received
- Day 7: triage decision
- Day 30: fix for critical issues; advisory published here
- Day 90: public disclosure (if applicable)

## Threat model

This app is designed for personal use on a trusted machine. It is **not** designed for:

- Multi-user shared systems where camera feeds could be a privacy concern
- Hostile environments where a malicious actor could install a modified version
- Air-gapped networks that require verified offline-only behavior; first-run model download, MediaPipe metrics behavior, and optional remote Ollama inference must all be reviewed or disabled for that environment

If you need any of these, please audit the code and build from source.
