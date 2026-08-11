# Roadmap

This roadmap records current product direction, not a shipping guarantee. Milestones and target quarters are planning aids; scope and timing may change as implementation, validation, dependencies, privacy, licensing, security, and platform constraints become clearer. Material changes should remain visible in the commit history.

> **Status legend:** 🔒 in progress · 🎯 next · 💭 considering

---

## v1.1.0 — UX polish and platform parity

**Planning target: Q3 2026**

### 🎯 Two-hand tracking

The current application path is designed around one tracked hand. A reviewed two-hand implementation would need independent tracking and smoothing state, deterministic primary-hand arbitration, gesture-conflict handling, disengage/reset behavior, and tests covering crossed or occluded hands. MediaPipe configuration alone is not sufficient to establish reliable two-hand behavior.

### 🎯 Linux and macOS parity

Windows is the primary tested path. Linux and macOS need platform-specific focus discovery, overlay behavior, packaging, permissions, and accessibility validation before either platform can be described as feature-equivalent. Any prototype work outside this repository must be imported, reviewed, tested, and documented here before it counts as project support.

### 🎯 Bundled-model installer

The installer currently obtains the hand-landmark model at install or first-run time. A self-contained package requires a reviewed model source and version, licensing and redistribution confirmation, reproducible packaging, update behavior, integrity checks, and validation for every supported build target. Do not treat bundling as complete merely because the packaging tool can include data files.

### 🎯 Per-gesture hook system

A future hook system may allow reviewed actions after a gesture is confirmed. Before shell commands, network requests, or Python callbacks can be enabled, the project needs a versioned schema, explicit permissions, input validation, failure isolation, safe defaults, auditability, and clear handling of untrusted configuration. Hook execution must not be coupled to the current gesture-runtime fixes.

### 🎯 Command-line launch flags

Potential launch options include calibration, initial engagement state, overlay control, and camera selection. Exact names and behavior remain subject to review. Parsing, invalid-input handling, platform behavior, and interaction with the single-instance lock require deterministic tests.

---

## v1.2.0 — Experimental depth and spatial interaction

**Planning target: Q4 2026**

### 🎯 Monocular relative depth or pose

MediaPipe exposes image landmarks whose `z` value is relative to the wrist and uses roughly the same scale as normalized image `x`. It also exposes hand-world landmarks in metres relative to the hand's geometric centre. Neither output directly provides camera-referenced, metric hand translation, and camera intrinsics alone cannot recover absolute depth from a single view.

The first safe milestone is therefore an explicitly experimental relative-depth or pose view. Any later camera-referenced 3D position requires a documented scale or pose prior, a separate depth-estimation method, or another reviewed source of metric reference, plus validation across hands, distances, cameras, and occlusion. Monocular output must not be presented as measurement-grade or used for automation or safety decisions until that validation exists.

### 🎯 Phone as a second camera

A companion-device workflow remains a proposal, not a shipped capability. It requires a defined and authenticated transport, explicit user consent, camera and network lifecycle handling, latency and synchronization limits, calibration behavior, mobile platform support, and privacy documentation. Website or mobile copy must not imply that a phone can already be used as a virtual camera.

### 🎯 Room-map-driven gesture zones

Spatial gesture zones depend on trustworthy 3D coordinates. The current live stereo path remains experimental while the calibration and reconstruction convention tracked in Issue #6 is unresolved. Zone-triggered actions require validated coordinates, deterministic boundary behavior, user-visible arming and cancellation, action permissions, and protections against accidental activation before they can be enabled.

---

## v2.0.0 — Voice and extensibility

**Planning target: Q1 2027**

### 🎯 Wake-word and voice intent

A future on-device wake-word detector requires reviewed licensing, supported-platform evidence, microphone permission handling, clear recording indicators, cancellation controls, and privacy documentation. Intent extraction must use a documented provider interface and safe action boundary; naming a third-party engine or model service does not constitute implementation support.

### 🎯 Narrow sign-language vocabulary

The hand-landmark pipeline is a starting point, not a ready-made sign-language recognizer. Many signs require temporal motion, two-hand coordination, handedness, and sometimes body or face context. Start with a narrowly defined, user-tested vocabulary and an on-device temporal classifier; do not describe isolated landmark poses as general ASL recognition.

### 🎯 Plugin SDK

A plugin interface needs a stable versioned contract, capability and permission boundaries, dependency isolation, failure containment, compatibility testing, and clear trust guidance before third-party packages can extend gesture, calibration, or room-map behavior. Package discovery alone is not a safe plugin architecture.

---

## Considering — not committed

These are exploratory ideas without an assigned milestone. They require design and validation before promotion into a versioned plan.

- 💭 Native mobile remote controls beyond a reviewed phone-camera workflow
- 💭 Webcam-only calibration using reviewed visual markers rather than a printed checkerboard
- 💭 Head-tracking companion mode for accessibility
- 💭 Opt-in calibration synchronization with an explicit privacy and threat model
- 💭 Steam Deck and handheld-PC layout support
- 💭 OBS or virtual-camera integration
- 💭 Wayland-native focus discovery and overlay support; the current selection overlay is Windows-specific

---

## How this document is maintained

- New ideas begin under **Considering**.
- A feature moves into a versioned milestone only after its scope, dependencies, review boundary, and validation plan are documented.
- Shipped work is recorded in `CHANGELOG.md` with links to the implementing pull request and validation evidence.
- Withdrawn or materially changed plans remain visible in history rather than disappearing without explanation.
- The roadmap is reviewed during minor-release planning and whenever implementation evidence invalidates a capability claim.

## Proposing roadmap work

Open an issue describing the user need, the smallest safe scope, dependencies, validation plan, and platform or privacy constraints before starting implementation. This reduces duplicate work and keeps runtime, CI, website, mobile, security, and architecture changes in separately reviewable pull requests.
