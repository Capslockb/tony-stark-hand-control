# Two-Class Default-State Pitfall & Windows+git-bash PowerShell Workaround

Two reusable patterns that surfaced during the Tony Stark hand control project. Both are
generic enough to apply to any Tkinter/PyQt desktop GUI that splits state between a UI
class and a worker class, and to any Windows host where git-bash is the default shell.

---

## 1. Two-class default-state pitfall (HandControlApp / HandProcessor)

### Symptom
The app crashes on first frame with `AttributeError: 'HandProcessor' object has no
attribute 'one_euro_min_cutoff'`. The slider in the GUI reads its value from
`self.one_euro_min_cutoff` (on the App) — that attribute *is* set. But the filter
inside `HandProcessor.smooth()` reads `self.one_euro_min_cutoff` (on the Processor) —
that attribute is *not* set on the Processor instance, only on the App.

### Why it happens
A common pattern is:

- UI class (`HandControlApp`) owns the user-facing settings and the widgets that
  bind to them. Defaults set in `__init__` so the sliders have values to display.
- Worker class (`HandProcessor`) does the actual math and reads the same settings.

If you set the defaults only on the UI class, the worker crashes on first use. If you
set the defaults only on the worker class, the UI's `DoubleVar(value=...)` lines crash
during widget construction (before `__init__` finishes).

The "obvious" fix is to make the UI's `_set_attr` propagate to the worker. That
*does* work for live changes after startup, but it does nothing for the first frame
which runs before any slider has been touched.

### Fix (do all three)
1. **Set defaults in the worker class `__init__`**, with the same values as the UI
   class. This makes the worker safe to use standalone (e.g., in tests).
2. **Set defaults in the UI class `__init__`**, with the same values. This makes
   the slider widgets safe to construct before the worker is created.
3. **Propagate from UI to worker on every `__init__` end** and on every slider
   change via `_set_attr`. This keeps them in sync.

```python
class HandProcessor:
    def __init__(self):
        # ... model setup ...
        # Defaults — must match HandControlApp defaults below
        self.one_euro_min_cutoff = 2.5
        self.one_euro_beta = 0.05
        self.cursor_ema_alpha = 0.55

class HandControlApp:
    def _set_attr(self, name, value):
        setattr(self, name, value)
        # Propagate to the worker for shared tunables
        if (name in ('one_euro_min_cutoff', 'one_euro_beta', 'cursor_ema_alpha')
                and getattr(self, 'hand_proc', None) is not None):
            setattr(self.hand_proc, name, value)
```

### Detection
When you change a default in one class, **grep for the same name in the other
class**. If a `self.<name>` is read in the worker but only set in the UI (or
vice versa), it will crash on first use or first widget construction. The console
error is always the same: `AttributeError: '<ClassName>' object has no attribute
'<name>'`.

### Why this happened in this project
The smoothing patches (patches 19-21) added `one_euro_min_cutoff`, `one_euro_beta`,
and `cursor_ema_alpha` to `HandControlApp` so the sliders had values. The filter
in `HandProcessor.smooth()` was patched to read those names. The first
reconstruction attempt crashed on frame 1 because `HandProcessor.__init__` never
set them. The synthetic-smoke-test pattern (build the object in isolation, check
attrs) would have caught it before launch.

### Synthetic smoke test pattern (cheap, catches this class of bug)
Before declaring a class ready, build it in isolation and assert the attributes the
runtime code will read:

```python
hp = HandProcessor.__new__(HandProcessor)   # bypass normal init that needs camera
HandProcessor.__init__(hp)                  # but run __init__ explicitly
assert hp.one_euro_min_cutoff == 2.5
assert hp.one_euro_beta == 0.05
assert hp.cursor_ema_alpha == 0.55
print("HandProcessor defaults present.")
```

The 30 seconds this takes is worth it. The cost of *not* having it is a runtime
crash that the user has to hit, then patch, then restart.

---

## 2. Windows + git-bash PowerShell `$`-stripping workaround

### Symptom
`terminal('powershell -Command "Get-ChildItem | Where-Object {$_.Length -gt 0}"')`
returns nothing or errors with `Where-Object: Missing argument in parameter list`.
The actual command never reached PowerShell. The `$` was stripped by MSYS (git-bash's
argument-mangling layer) before the command went to `powershell.exe`.

### Why
git-bash / MSYS sees a `$` in a string and interprets it as a variable. Inside a
double-quoted bash string, `$_` becomes the empty string before the shell hands
the command to PowerShell. Any complex PowerShell one-liner with `$var`, `$_`, or
`$()` will break. Backticks and other PowerShell special chars get mangled too.

### Workaround: write the PowerShell to a file, then run the file
```python
script = r'''
$d = Get-PSDrive C
$freeGB = [math]::Round($d.Free/1GB,2)
Write-Output ("Free: {0} GB" -f $freeGB)
'''
with open(r'C:\Users\Bernardo\check_disk.ps1', 'w') as f:
    f.write(script)
out = terminal('powershell -NoProfile -ExecutionPolicy Bypass '
               '-File "C:\\Users\\Bernardo\\check_disk.ps1"')
```

`r'...'''...'''` (raw triple-quoted string) preserves every PowerShell special char
including the unicode characters. `-NoProfile` skips the user profile (faster,
deterministic). `-ExecutionPolicy Bypass` allows running unsigned scripts.

### Alternative: `cmd //c` for batch files
Same pattern but for `.cmd`/`.bat`:
```python
cmd = r'''
@echo off
echo Step 1
takeown /f "C:\some\path" /r /d y >nul 2>&1
rmdir /s /q "C:\some\path"
'''
with open(r'C:\Users\Bernardo\free.cmd', 'w') as f:
    f.write(cmd)
out = terminal(r'cmd //c "C:\Users\Bernardo\free.cmd"')
```

**`cmd //c` (double slash) is required** when calling from git-bash. The single-slash
form `cmd /c` gets MSYS-rewritten because MSYS thinks anything starting with `/` is a
POSIX path. `//` survives the rewriter and reaches cmd as `/c`.

### Even more careful: PS5.1 ASCII-only
If you write the `.ps1` file from a Python string, **avoid em-dashes, smart quotes,
curly braces used as glyphs, or any non-ASCII character**. Windows PowerShell 5.1
(the default on Windows 10) has a parser that chokes on non-ASCII in `.ps1` files
even when the BOM is correct. Stick to ASCII in your `.ps1` content; if the
displayed text needs unicode, encode it in `Write-Output` as `[char]0x2014` etc.

### Reading traceback in a *previous* completed-process output
If the only console output for a crash is from a *previous* run that already
exited, the traceback is in the `process(action='log', session_id=<old_id>)` log.
When the user says "the app crashed" and there is no current process, the answer
is in the last completed-process's output. Use `process list` to find any
`exit_code` other than 0, then `process log` on that session.

This is the only way to get the actual stack trace when the foreground process
is gone and the new one hasn't been started yet.
