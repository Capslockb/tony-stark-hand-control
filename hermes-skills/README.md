# Contributor Audit Materials

This directory contains dated design notes and optional contributor utilities created while Tony Stark Hand Control was being developed and reviewed. The application does not require these files at installation or runtime.

The current source tree, repository tests, and user documentation are authoritative. Material under this directory is archival context and may describe behavior or assumptions that have since changed.

## Contents

```text
hermes-skills/
└── tony-stark-hand-control/
    ├── SKILL.md                  # historical reference index
    ├── references/               # dated design and audit notes
    │   ├── 3d_reconstruction.md
    │   ├── accessibility_overlay.md
    │   ├── adaptive_pacing_and_gpu.md
    │   ├── audit_2026_06.md
    │   ├── audit_2026_06_04_pass2.md
    │   ├── audit_2026_06_04_pass3.md
    │   ├── audit_2026_06_04_pass4.md
    │   ├── audit_2026_06_04_pass5.md
    │   ├── audit_2026_06_04_pass6.md
    │   ├── audit_2026_06_04_pass7.md
    │   ├── camera_troubleshooting.md
    │   ├── dual_class_default_state.md
    │   ├── gui_and_intent.md
    │   ├── multicamera_fusion.md
    │   ├── ollama_integration.md
    │   ├── smoothing_and_aspect.md
    │   └── stream_cut_fallback.md
    └── scripts/
        ├── audit_app.py
        ├── create_desktop_shortcut.ps1
        ├── multistream_bench.py
        └── synthetic_stereo_test.py
```

## Reference notes

The audit-pass documents are historical snapshots, not current specifications or proof that a capability works. Performance, platform-support, privacy, architecture, and validation claims should be checked against the exact current source and its associated test results.

## Optional utilities

The scripts are contributor tools rather than application entry points. Some are host-dependent and may access cameras, a graphical desktop, or platform-specific APIs. Review their source before running them.

Until the audit helper's default locator is corrected, pass the application path explicitly from the repository root:

```bash
python hermes-skills/tony-stark-hand-control/scripts/audit_app.py ./tony_stark_hud_control.py
```

For repository-wide test discovery, use:

```bash
python -m unittest discover tests -v
```

## License

Same as the main project: MIT.
