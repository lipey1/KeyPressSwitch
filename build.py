"""Gera enter.ico e compila KeyPressSwitch.exe com PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICO = ROOT / "enter.ico"
PNG = ROOT / "enter.png"
DIST = ROOT / "dist"


def make_ico() -> None:
    if not PNG.is_file():
        raise FileNotFoundError(f"Imagem nao encontrada: {PNG}")

    sys.path.insert(0, str(ROOT))
    from main import write_app_ico

    write_app_ico(ICO)
    print(f"ICO gerado: {ICO}")


def run_pyinstaller() -> None:
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "KeyPressSwitch",
        "--icon",
        str(ICO),
        "--add-data",
        f"{PNG}{sep}.",
        "--add-data",
        f"{ICO}{sep}.",
        "--hidden-import",
        "PIL._tkinter_finder",
        str(ROOT / "main.py"),
    ]
    print("Executando:", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    make_ico()
    run_pyinstaller()
    exe = DIST / "KeyPressSwitch.exe"
    if exe.is_file():
        print(f"\nBuild OK: {exe}")
    else:
        raise SystemExit("Build falhou: exe nao encontrado em dist/")


if __name__ == "__main__":
    main()
