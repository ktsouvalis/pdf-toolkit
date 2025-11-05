#!/usr/bin/env python3
"""
Linux build helper for PDF Toolkit GUI

- Reuses versioning from build.py (build/VERSION and version.py generation)
- Runs PyInstaller using the Linux spec (PDF-Toolkit-GUI-linux.spec)
- Produces the binary in dist/linux
- Optionally packages a tar.gz bundle for distribution with a .desktop file

Usage (from project root):
  python build_linux.py                 # bump version (minor), build, create tarball
  python build_linux.py --no-increment  # do not bump version
  python build_linux.py --clean         # remove dist/linux and build/pyi-linux before building
  python build_linux.py --no-tarball    # skip tarball packaging
  python build_linux.py --bump-major    # bump major (resets minor)
  python build_linux.py --bump-minor    # bump minor

Notes:
- Requires: PyInstaller installed in the current environment
- Output: dist/linux/PDF-Toolkit-GUI-<MAJOR>.<MINOR>-linux
- Tarball: dist/PDF-Toolkit-GUI-<MAJOR>.<MINOR>-linux-<arch>.tar.gz
"""
from __future__ import annotations
import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / 'dist'
LINUX_DIST = DIST_DIR / 'linux'
BUILD_DIR = ROOT / 'build'
WORK_DIR = BUILD_DIR / 'pyi-linux'
SPEC_DEFAULT = 'PDF-Toolkit-GUI-linux.spec'

# Import our Windows build helper for shared versioning utilities
# (works cross-platform; versionfile is ignored on Linux by PyInstaller)
try:
    import build as winbuild
except Exception:
    winbuild = None


def ensure_version(bump_major: bool, bump_minor: bool, no_increment: bool) -> str:
    """Read/bump version using build.py helpers and generate version.py.
    Returns textual version MAJOR.MINOR.
    """
    if not winbuild:
        # Fallback: minimal version management
        BUILD_DIR.mkdir(exist_ok=True)
        vf = BUILD_DIR / 'VERSION'
        if vf.exists():
            parts = vf.read_text(encoding='utf-8').strip().split('.')
            try:
                nums = [int(p) for p in parts]
            except Exception:
                nums = [1, 0]
        else:
            nums = [1, 0]
        if bump_major and bump_minor:
            raise SystemExit('Cannot specify both --bump-major and --bump-minor')
        if bump_major:
            nums[0] += 1; nums[1] = 0
        elif bump_minor:
            nums[1] += 1
        elif not no_increment:
            nums[1] += 1
        vf.write_text(f"{nums[0]}.{nums[1]}", encoding='utf-8')
        # write version.py (GUI reads __version__)
        (ROOT / 'version.py').write_text(
            f"# Auto-generated\n__version__ = '{nums[0]}.{nums[1]}'\n",
            encoding='utf-8'
        )
        return f"{nums[0]}.{nums[1]}"

    # Use shared helper from build.py
    nums = winbuild.read_version()
    if bump_major and bump_minor:
        raise SystemExit('Cannot specify both --bump-major and --bump-minor')
    if bump_major:
        nums[0] += 1; nums[1] = 0
        winbuild.write_version(nums)
        print('Bumped MAJOR to', '.'.join(map(str, nums)))
    elif bump_minor:
        nums[1] += 1
        winbuild.write_version(nums)
        print('Bumped MINOR to', '.'.join(map(str, nums)))
    elif not no_increment:
        nums[-1] += 1
        winbuild.write_version(nums)
        print('Bumped version to', '.'.join(map(str, nums)))
    else:
        print('Using existing version', '.'.join(map(str, nums)))

    # Generate version resources (also writes version.py for GUI)
    winbuild.generate_versionfile(nums)
    return '.'.join(str(n) for n in nums)


def run_pyinstaller(spec_path: str) -> None:
    cmd = [sys.executable, '-m', 'PyInstaller', '--distpath', str(LINUX_DIST), '--workpath', str(WORK_DIR), spec_path]
    print('Running:', ' '.join(cmd))
    env = os.environ.copy()
    env.setdefault('PYINSTALLER_CONFIG_DIR', str(WORK_DIR / '.config'))
    subprocess.check_call(cmd, cwd=str(ROOT), env=env)


def detect_arch() -> str:
    m = platform.machine().lower()
    if m in ('x86_64', 'amd64'):
        return 'x86_64'
    if m in ('aarch64', 'arm64'):
        return 'aarch64'
    if m in ('armv7l', 'armv7'):
        return 'armv7l'
    return m or 'unknown'


def find_built_binary(dist_dir: Path) -> Path | None:
    """Return the most recent executable file produced by PyInstaller in dist/linux.
    We pick the newest regular file with executable bit set.
    """
    if not dist_dir.exists():
        return None
    candidates = []
    for p in dist_dir.iterdir():
        if not p.is_file():
            continue
        try:
            st = p.stat()
            if st.st_mode & stat.S_IXUSR:
                candidates.append((st.st_mtime, p))
        except OSError:
            continue
    if not candidates:
        files = [(p.stat().st_mtime, p) for p in dist_dir.iterdir() if p.is_file()]
        if not files:
            return None
        candidates = files
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


def write_desktop_file(target_bin_name: str, out_path: Path) -> None:
    desktop = f"""[Desktop Entry]\nType=Application\nName=PDF Toolkit GUI\nComment=Shrink, Split, and Merge PDFs\nExec={target_bin_name}\nTerminal=false\nCategories=Office;Graphics;\nStartupNotify=false\n"""
    out_path.write_text(desktop, encoding='utf-8')


def make_tarball(binary_path: Path, version: str, arch: str) -> Path:
    staging_root = BUILD_DIR / 'linux_pkg'
    if staging_root.exists():
        shutil.rmtree(staging_root, ignore_errors=True)
    staging_root.mkdir(parents=True, exist_ok=True)

    top_dir = staging_root / f'PDF-Toolkit-GUI-{version}-linux-{arch}'
    top_dir.mkdir(parents=True, exist_ok=True)

    # Place binary with a user-friendly name inside the tarball
    bin_dst = top_dir / 'PDF-Toolkit-GUI'
    shutil.copy2(binary_path, bin_dst)
    try:
        bin_dst.chmod(bin_dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass

    # Add desktop entry
    desktop_path = top_dir / 'pdf-toolkit-gui.desktop'
    write_desktop_file(target_bin_name='./PDF-Toolkit-GUI', out_path=desktop_path)

    # Include README and LICENSE if present
    for fname in ('README.md', 'LICENSE'):
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, top_dir / fname)

    tar_out = DIST_DIR / f'PDF-Toolkit-GUI-{version}-linux-{arch}.tar.gz'
    DIST_DIR.mkdir(exist_ok=True)
    with tarfile.open(tar_out, 'w:gz') as tf:
        tf.add(top_dir, arcname=top_dir.name)
    print('Created tarball', tar_out)
    return tar_out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', default=SPEC_DEFAULT, help='PyInstaller spec file to use')
    ap.add_argument('--no-increment', action='store_true', help="Don't bump version (use current build/VERSION)")
    ap.add_argument('--bump-major', action='store_true', help='Bump MAJOR (resets MINOR)')
    ap.add_argument('--bump-minor', action='store_true', help='Bump MINOR')
    ap.add_argument('--clean', action='store_true', help='Remove dist/linux and build/pyi-linux before building')
    ap.add_argument('--no-tarball', action='store_true', help='Skip creating the tar.gz bundle')
    args = ap.parse_args(argv)

    if args.clean:
        for d in (LINUX_DIST, WORK_DIR, BUILD_DIR / 'linux_pkg'):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                print('Removed', d)

    version = ensure_version(bump_major=args.bump_major, bump_minor=args.bump_minor, no_increment=args.no_increment)

    # Build
    spec_path = str(ROOT / args.spec)
    try:
        run_pyinstaller(spec_path)
    except subprocess.CalledProcessError as e:
        print('PyInstaller failed with', e.returncode)
        return e.returncode

    # Locate built binary
    built = find_built_binary(LINUX_DIST)
    if not built:
        print('Error: built binary not found in dist/linux')
        return 2
    print('Built binary:', built)

    # Tarball
    if not args.no_tarball:
        arch = detect_arch()
        try:
            make_tarball(built, version=version, arch=arch)
        except Exception as e:
            print('Warning: failed to create tarball:', e)

    print('Done. Linux build in', LINUX_DIST)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
