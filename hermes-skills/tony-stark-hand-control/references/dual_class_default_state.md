# Shared Defaults and Shell-Portability Notes

This dated note records two contributor lessons from earlier development revisions. It is not a current runtime specification or an environment-specific runbook.

## Shared defaults across UI and worker objects

When a user-interface object exposes settings that a separate worker object consumes, both construction order and ownership must be explicit.

A safe design should:

- define one canonical set of defaults;
- initialize the worker before any runtime path reads those settings;
- initialize UI controls from the same values;
- propagate accepted changes through a bounded setter or configuration object;
- test worker construction independently from cameras, networks, and a graphical display;
- reject unknown setting names rather than silently creating misspelled attributes.

Duplicating literal defaults in two classes creates drift. Prefer a shared immutable configuration record or constants module when practical. Focused tests should cover initial values, updates, invalid values, and construction order.

## Shell and platform boundaries

Commands that cross Bash, PowerShell, and `cmd.exe` can be rewritten by the invoking shell. Quoting, variable expansion, path conversion, encoding, and execution-policy behavior differ by environment.

Contributor utilities should avoid embedding developer-specific home paths or copied process-control commands. Prefer:

- repository-relative paths;
- argument arrays through `subprocess` instead of nested shell strings;
- temporary files created with standard-library helpers when a script file is required;
- explicit UTF-8 encoding where supported;
- non-destructive diagnostics before process termination or filesystem deletion;
- tests that use temporary directories and controlled executables.

Do not bypass platform security controls as a default troubleshooting step. Any elevated or destructive operation requires clear ownership and impact verification.

## Validation boundary

Current source, repository tests, and exact-head CI results take precedence over this historical note. Host-specific observations should be reproduced on the stated operating system before becoming contributor guidance.