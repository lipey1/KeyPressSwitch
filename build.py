"""Gera enter.ico e compila KeyPressSwitch.exe com PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICO = ROOT / "enter.ico"
PNG = ROOT / "enter.png"
DIST = ROOT / "dist"
EXE = DIST / "KeyPressSwitch.exe"


def is_file_locked(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with open(path, "a+b"):
            pass
        return False
    except OSError:
        return True


def make_ico() -> None:
    if not PNG.is_file():
        raise FileNotFoundError(f"Imagem nao encontrada: {PNG}")

    sys.path.insert(0, str(ROOT))
    from main import write_app_ico

    write_app_ico(ICO)
    print(f"ICO gerado: {ICO}")


def run_pyinstaller(output_name: str) -> Path:
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
        output_name,
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
    return DIST / f"{output_name}.exe"


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    make_ico()

    if is_file_locked(EXE):
        print(
            "\nAVISO: KeyPressSwitch.exe esta em uso (app aberto).\n"
            "Gerando KeyPressSwitch_new.exe em vez de sobrescrever.\n"
        )
        out = run_pyinstaller("KeyPressSwitch_new")
        if not out.is_file():
            raise SystemExit("Build falhou: exe nao encontrado em dist/")
        print(f"\nBuild OK: {out}")
        print(
            "\nProximo passo:\n"
            "  1. Feche o app (icone na bandeja -> Sair)\n"
            "  2. Apague ou renomeie dist\\KeyPressSwitch.exe\n"
            "  3. Renomeie dist\\KeyPressSwitch_new.exe para KeyPressSwitch.exe\n"
            "     (ou rode python build.py de novo com o app fechado)"
        )
        return

    out = run_pyinstaller("KeyPressSwitch")
    if not out.is_file():
        raise SystemExit("Build falhou: exe nao encontrado em dist/")
    print(f"\nBuild OK: {out}")


if __name__ == "__main__":
    main()
