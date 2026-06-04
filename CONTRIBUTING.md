# Contributing

This is a personal project, but pull requests are welcome. Here's the workflow:

## Development setup

```bash
git clone https://github.com/Capslockb/tony-stark-hand-control.git
cd tony-stark-hand-control
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt
```

## Running tests

```bash
python -m unittest discover tests
# or with pytest
pytest -q
```

The full audit suite (77 assertions) lives in `tests/test_app.py`. It is self-contained — it does not require a real camera or GUI to run.

## Code style

- PEP 8, 4-space indentation
- `snake_case` for functions/files, `PascalCase` for classes
- Type hints encouraged but not required
- Docstrings on all public methods (`"""..."""`)

## Commit style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add 3D anchor export to OBJ`
- `fix: clamp velocity in One-Euro predictor`
- `docs: clarify calibration reprojection threshold`
- `chore: bump MediaPipe to 0.10.x`
- `refactor: extract room map anchor picking into a class`

## Pull request checklist

- [ ] Tests pass (`pytest -q`)
- [ ] Lint clean (no warnings)
- [ ] New public methods have docstrings
- [ ] New features documented in `docs/`
- [ ] No new dependencies unless justified in the PR description
- [ ] One feature per PR

## Release process

1. Bump version in `tony_stark_hud_control.py` (`__version__`)
2. Add a `CHANGELOG.md` entry under a new heading
3. Tag the commit: `git tag v1.x.y`
4. Push the tag: `git push origin v1.x.y`
5. GitHub Actions builds the Windows .exe and attaches it to the release

## Reporting issues

- **Bugs**: open a GitHub issue with steps to reproduce
- **Security**: see `SECURITY.md` for the private disclosure process
- **Questions**: open a discussion (not an issue)
