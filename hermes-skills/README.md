# Contributor Audit Materials

This directory preserves historical audit notes and optional maintenance utilities used while developing and reviewing Tony Stark Hand Control. It is not required to install or run the application.

Treat the current source, tests, and user documentation as authoritative. The reference notes are historical snapshots and may describe behavior, assumptions, or fixes that have since changed.

## What's in here

```
hermes-skills/
└── tony-stark-hand-control/
    ├── SKILL.md                  # legacy reference index
    ├── references/               # historical design and audit notes
    │   ├── 3d_reconstruction.md
    │   ├── accessibility_overlay.md
    │   ├── adaptive_pacing_and_gpu.md
    │   ├── audit_2026_06.md              # audit pass 1
    │   ├── audit_2026_06_04_pass2.md     # audit pass 2
    │   ├── audit_2026_06_04_pass3.md     # audit pass 3
    │   ├── audit_2026_06_04_pass4.md     # audit pass 4
    │   ├── audit_2026_06_04_pass5.md     # audit pass 5
    │   ├── audit_2026_06_04_pass6.md     # audit pass 6
    │   ├── audit_2026_06_04_pass7.md     # audit pass 7
    │   ├── camera_troubleshooting.md
    │   ├── dual_class_default_state.md
    │   ├── gui_and_intent.md
    │   ├── multicamera_fusion.md
    │   ├── ollama_integration.md
    │   ├── smoothing_and_aspect.md
    │   └── stream_cut_fallback.md
    └── scripts/
        ├── audit_app.py            # host-dependent live audit helper
        ├── create_desktop_shortcut.ps1
        ├── multistream_bench.py     # OpenCV micro-benchmark utility
        └── synthetic_stereo_test.py # synthetic 3D reconstruction test
```

## Using the material

### Historical references

`SKILL.md` indexes the reference files. The audit-pass documents record findings and attempted corrections from particular points in the project's history. Read them as supporting context, not as current specifications or proof that a capability is working.

Do not copy historical performance, platform-support, privacy, test-count, or architecture claims into public documentation without checking them against the current tree and an exact-head validation run.

### Optional maintenance utilities

The scripts are contributor tools rather than application entry points. Some are host-dependent and may access cameras, GUI facilities, or platform-specific APIs. Review a script before running it and do not treat a successful helper run as a substitute for repository-wide tests.

Until [Issue #2](https://github.com/Capslockb/tony-stark-hand-control/issues/2) corrects the audit helper's default locator, pass the application path explicitly from the repository root:

```bash
python hermes-skills/tony-stark-hand-control/scripts/audit_app.py ./tony_stark_hud_control.py
```

For the repository-wide deterministic test entry point, use:

```bash
python -m unittest discover tests -v
```

Useful reusable references include:

- `stream_cut_fallback.md` — chunked changes for large files
- `dual_class_default_state.md` — class-construction-order pitfalls
- `adaptive_pacing_and_gpu.md` — adaptive loop-pacing notes

## License

Same as the main project: MIT.
