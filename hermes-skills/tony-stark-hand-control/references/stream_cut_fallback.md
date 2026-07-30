# Large-file change notes

This historical note records a practical maintenance lesson from editing the large single-file application module.

## Problem

Large all-at-once rewrites are difficult to review and can leave an incomplete file when an editor, network connection, or automation process fails partway through the operation.

## Safer approach

1. Make small, logically grouped changes.
2. Run a syntax check after each group.
3. Keep each commit independently reviewable.
4. Preserve the last known-good revision until the complete change is validated.
5. Prefer ordinary source patches over generated full-file replacements.

For Python syntax validation:

```bash
python -m py_compile tony_stark_hud_control.py
```

An AST parse can provide a lightweight intermediate check:

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('tony_stark_hud_control.py').read_text(encoding='utf-8'))"
```

## Review boundary

A successful syntax check proves only that the file parses. Functional changes still require focused tests and repository-wide validation. Hardware, graphical-desktop, camera, and optional-service paths should remain isolated or be tested in a controlled environment.

## Historical status

This note is retained as contributor context. It does not prescribe a particular editor, automation framework, or execution environment.
