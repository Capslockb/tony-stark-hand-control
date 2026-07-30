# Historical Audit Index

This file is retained for compatibility with older links. It is a contributor-facing index of dated design and audit notes; it is not an executable application component, a current specification, or validation evidence.

Use the current source tree, repository tests, public documentation, and exact-head CI results when assessing present behavior.

## Reference groups

### Application structure and interaction

- `references/gui_and_intent.md` — GUI structure and intent-detection notes.
- `references/smoothing_and_aspect.md` — smoothing and aspect-ratio handling.
- `references/accessibility_overlay.md` — Windows focus-overlay implementation notes.
- `references/dual_class_default_state.md` — initialization-order pitfalls.

### Camera and processing pipeline

- `references/camera_troubleshooting.md` — camera probing and feed-quality notes.
- `references/multicamera_fusion.md` — multi-camera processing concepts.
- `references/adaptive_pacing_and_gpu.md` — pacing and processing-mode notes.
- `references/3d_reconstruction.md` — calibration and reconstruction design notes.

### Optional integrations

- `references/ollama_integration.md` — historical notes for the optional Ollama snapshot classifier.

### Dated audit records

- `references/audit_2026_06.md`
- `references/audit_2026_06_04_pass2.md`
- `references/audit_2026_06_04_pass3.md`
- `references/audit_2026_06_04_pass4.md`
- `references/audit_2026_06_04_pass5.md`
- `references/audit_2026_06_04_pass6.md`
- `references/audit_2026_06_04_pass7.md`

These files record observations from particular revisions and environments. They may include superseded implementations, host-specific measurements, and incomplete experiments.

## Contributor utilities

- `scripts/audit_app.py` — host-dependent application audit helper.
- `scripts/multistream_bench.py` — OpenCV micro-benchmark helper.
- `scripts/synthetic_stereo_test.py` — synthetic reconstruction helper.
- `scripts/create_desktop_shortcut.ps1` — Windows shortcut helper.

Some utilities require cameras, a graphical desktop, Windows APIs, or optional dependencies. A helper run does not replace repository-wide tests.

## Validation

The repository-wide test entry point is:

```bash
python -m unittest discover tests -v
```

Claims about performance, supported platforms, privacy, resource usage, or runtime correctness should be tied to the exact source revision and reproducible validation evidence.
