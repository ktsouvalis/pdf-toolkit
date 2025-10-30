# PDF Toolkit: Shrink, Split, and Merge PDFs

Shrink scanned PDFs, split PDFs, and merge PDFs using PyMuPDF and Pillow. Includes:
- Shrink scanned PDFs by re-rasterizing pages as JPEG (best for image-only scans)
- Split PDFs every N pages or at specific page numbers
- Merge multiple PDFs in a chosen order
- One GUI app with three tabs: Shrink, Split, Merge

## Install

Requirements: Python 3.13+.

Using requirements.txt:

```bash
pip install -r requirements.txt
```

Directly:

```bash
pip install pymupdf pillow
```

Tkinter note (for GUI):
- Windows/macOS usually ship with Tkinter.
- Linux may need: Debian/Ubuntu `sudo apt-get install python3-tk`, Fedora `sudo dnf install python3-tkinter`.

## GUI (Shrink, Split & Merge)

Launch the GUI:

```bash
python pdf_toolkit_gui.py
```

What you can do:
- Shrink tab: choose input/output, pick a preset (Light/Medium/Aggressive) or set custom DPI and JPEG quality, optionally grayscale, and run with a progress bar.
- Split tab: choose input and output folder, then either:
  - Split every N pages (e.g., every 3 pages), or
  - Split at 1-based pages (comma-separated, e.g., `5,10` to make parts [1-4], [5-9], [10-end]).
- Merge tab: add two or more PDFs, reorder as needed, pick an output path, and merge with progress.

## CLI: Shrink

```bash
python shrink_scanned_pdf.py input.pdf
```

- Default output: `input.shrink.pdf`
- Options: `--dpi` (default 150), `--quality` 1-100 (default 60), `--grayscale`, presets `--light` (200,75), `--medium` (150,60), `--aggressive` (120,50)

Examples:

```bash
python shrink_scanned_pdf.py input.pdf --light
python shrink_scanned_pdf.py input.pdf --aggressive --grayscale
python shrink_scanned_pdf.py input.pdf --dpi 200 --quality 70 out.pdf
```

## CLI: Split

Split every N pages:

```bash
python split_pdf.py input.pdf --every 3
```

Split at specific 1-based pages (comma-separated numbers that define the first pages of the new parts):

```bash
python split_pdf.py input.pdf --split-at 5,10 --outdir out --prefix mydoc
```

This creates parts like `mydoc_part01.pdf`, `mydoc_part02.pdf`, etc. If `--prefix` isn’t given, the input basename is used.

## CLI: Merge

Merge two or more PDFs in order:

```bash
python merge_pdf.py output.pdf input1.pdf input2.pdf [input3.pdf ...]
```

- The output directory is created if needed.
- Metadata from the first input is preserved when possible.

## How shrinking works

- Each page is rendered to a bitmap at the chosen DPI.
- The bitmap is encoded as JPEG and re-embedded in a new PDF page of the original size.
- Basic metadata is preserved when possible.

## Tips (shrink)

- DPI 120–200 is typical for scans; 150 is a good default.
- JPEG quality 50–75 balances size and readability.
- Grayscale helps for text-heavy black/white documents.

## Output samples (shrink)

```
Input : input.pdf (12.3 MB)
Output: input.shrink.pdf (3.8 MB)
Saved : 8.5 MB  (69.1% reduction)
```

## Troubleshooting

- ImportError: fitz or PIL
  - Install deps: `pip install -r requirements.txt`
- Tkinter not found
  - Install Tk support (see Linux note) or use CLI instead.
- Large PDFs (shrink)
  - Use lower `--dpi` and/or lower `--quality`.
- Low savings (shrink)
  - Source may already be JPEG-compressed similarly.
- Split points
  - Use 1-based numbers. `5,10` produces [1-4], [5-9], [10-end].

## Executables (Windows)

Build the GUI locally with PyInstaller:

```bash
pyinstaller PDF-Toolkit-GUI.spec
```

Or using the helper script (Windows cmd.exe):

```cmd
python build.py --no-increment
```

The GUI EXE will be placed under `dist/` as a single file, with the version in its name. Example:

- `PDF-Toolkit-GUI-1.2.exe`

## Build & versioning (automated)

A small helper `build.py` automates simple build-version management and building with PyInstaller.

- What it does:
  - Maintains a `build/VERSION` file with MAJOR.MINOR (text).
  - Generates `build/versionfile.txt` (VSVersionInfo format) which the `.spec` references to embed Windows VERSIONINFO into the EXE.
  - Generates a small `version.py` at project root with `__version__ = 'MAJOR.MINOR'` so the app can display the version.
  - Optionally runs `pyinstaller <spec>` to produce the executable.

- Typical commands (from project root, on Windows cmd.exe):

Generate version resources only (don't run PyInstaller):

```cmd
python build.py --generate-only
```

Bump the build number and build the GUI exe (default spec `PDF-Toolkit-GUI.spec`):

```cmd
python build.py
```

Build without incrementing the build counter (useful for reproducible builds), and optionally clean previous outputs:

```cmd
python build.py --no-increment --clean-dist
```

Version bumping flags

- `--bump-major` — increment MAJOR; reset MINOR to 0. Example: 1.2 -> 2.0
- `--bump-minor` — increment MINOR; Example: 1.2 -> 1.3

Examples:

```cmd

# bump minor, then build the GUI
python build.py --bump-minor

# bump major, then build the GUI
python build.py --bump-major
```

Notes:
- By default `build.py` increments the last (BUILD) number. The bump flags allow you to promote minor, or major versions with sensible resets of lower fields.
- `--no-increment` cannot be combined with `--bump-minor`, or `--bump-major`.

## What to commit to git (recommended)

New/modified files that you SHOULD commit:

- `build.py` — the build helper script.
- `PDF-Toolkit-GUI.spec` — spec used to build the GUI EXE and embed version info.
- `README.md` — docs for build flags and support policy.
- `build/VERSION` — if you want the repository to track the current build/version number (recommended for a visible baseline). If you prefer to track versions with tags/releases instead, you can avoid committing `build/VERSION` and keep it generated locally or by CI.

Files you should NOT commit (generated or build artifacts):

- `build/versionfile.txt` (generated by `build.py`) — generated at build time.
- `version.py` (generated by `build.py`) — generated; avoid committing to prevent noisy commits every build.
- `dist/`, `build/` directories produced by PyInstaller (except `build/VERSION`).
- Python cache and virtual env files: `__pycache__/`, `*.pyc`, `.venv/`, `env/`, etc.


## Putting it together (example workflow)

1. Edit code. Write tests. Commit your changes.
2. Run a local build to test:

```cmd
python build.py --generate-only    # generate version resources, do not build exe
python build.py                   # bump build and run pyinstaller (GUI only)
```

3. Test the produced exe under `dist/` (double-click to verify no console window). If everything looks good, commit `build/VERSION`, tag a release and create a PR.