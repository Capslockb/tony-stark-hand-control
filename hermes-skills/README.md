# Associated Hermes Skills

This directory contains the Hermes Agent skills that produced and audit-tested the Tony Stark Hand Control codebase. They're included so future maintainers (or curious readers) can see the full history of design decisions, pitfalls discovered during audits, and reusable patterns.

## What's in here

```
hermes-skills/
└── tony-stark-hand-control/
    ├── SKILL.md                  # main skill entry point
    ├── references/               # 17 deep-dive reference docs
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
        ├── audit_app.py            # 77-test regression harness
        ├── create_desktop_shortcut.ps1
        ├── multistream_bench.py     # cv2 micro-benchmark utility
        └── synthetic_stereo_test.py # synthetic 3D reconstruction test
```

## How to use this

### As a reference (read-only)

The `SKILL.md` is the entry point. It has a "Reference map" section that lists every reference doc with a one-line description. The 7 audit passes (`audit_2026_06_04_pass2.md` through `audit_2026_06_04_pass7.md`) document the bugs found, the fixes applied, and the lessons learned — read them in order if you want to understand how the current code came to be.

### As a skill for Hermes Agent (re-runnable)

If you have Hermes Agent installed, the `SKILL.md` is a real skill that the agent can use to:
- Run `scripts/audit_app.py` against the current `tony_stark_hud_control.py` to verify the 77-test regression suite
- Run `scripts/multistream_bench.py` to benchmark the multi-cam hot path
- Apply the audit fixes in pass2-pass7 if they regress

To install the skill:

```bash
# From a Hermes-enabled shell
mkdir -p ~/AppData/Local/hermes/skills
cp -r hermes-skills/tony-stark-hand-control ~/AppData/Local/hermes/skills/
```

Then in any Hermes session: `hermes skill view tony-stark-hand-control`.

### As documentation for re-applying the patterns

Many of the patterns here are general-purpose and apply to other GUI apps:

- `stream_cut_fallback.md` — chunked-patch pattern for large files
- `gui-app-startup` umbrella skill is referenced (and lives elsewhere in the Hermes skill tree)
- `dual_class_default_state.md` — class-construction-order pitfall
- `adaptive_pacing_and_gpu.md` — adaptive loop pacing

If you're building a similar Python GUI app, these references are the most reusable parts.

## License

Same as the main project: MIT.
