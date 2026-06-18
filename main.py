"""
KeyPress Switch - segura uma tecla pressionada enquanto estiver ativo.

- Define uma keybind de "switch" (mouse OU teclado) que liga/desliga.
- Define uma tecla do teclado que fica pressionada enquanto ativo.
- Overlay fixo no canto superior esquerdo mostrando ATIVO/INATIVO e a tecla.
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

import pystray
from PIL import Image, ImageDraw, ImageTk
from pynput import keyboard, mouse

CONFIG_VERSION = 1
APP_NAME = "KeyPress Switch"
AUTHOR_NAME = "Felipe Estrela"
GITHUB_URL = "https://github.com/lipey1"
ICON_FILE = "enter.png"
ICON_ICO = "enter.ico"
APP_ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
TRAY_RENDER_SIZE = 32
TRAY_ICO_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32)]
MUTEX_NAME = "Global\\KeyPressSwitch_SingleInstance"
_instance_guard = None


def ensure_single_instance() -> None:
    """Impede mais de uma instancia do app rodando ao mesmo tempo."""
    global _instance_guard

    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            user32.MessageBoxW(
                None,
                "O KeyPress Switch ja esta em execucao.\n"
                "Verifique o icone na bandeja do sistema (setinha).",
                APP_NAME,
                0x10 | 0x40000,  # MB_ICONERROR | MB_TOPMOST
            )
            sys.exit(1)
        _instance_guard = mutex
        return

    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 47293))
        sock.listen(1)
    except OSError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_NAME,
            "O KeyPress Switch ja esta em execucao.",
            parent=root,
        )
        root.destroy()
        sys.exit(1)
    _instance_guard = sock


def resource_path(name: str) -> Path:
    """Caminho do recurso em dev ou dentro do exe (PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / name


def enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def pin_overlay_win32(hwnd: int) -> None:
    """Mantem overlay no topo (nao funciona em fullscreen exclusivo de jogos)."""
    import ctypes
    from ctypes import wintypes

    GWL_EXSTYLE = -20
    WS_EX_TOPMOST = 0x00000008
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040

    user32 = ctypes.windll.user32
    handle = wintypes.HWND(hwnd)
    style = user32.GetWindowLongW(handle, GWL_EXSTYLE)
    # Nao usar WS_EX_LAYERED aqui — conflita com o -alpha do Tk e trava o repaint.
    user32.SetWindowLongW(
        handle,
        GWL_EXSTYLE,
        (style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        & ~0x00080000,
    )
    user32.SetWindowPos(
        handle,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


def write_app_ico(dest: Path | None = None) -> Path:
    """Gera .ico multi-resolucao a partir do PNG (barra de tarefas e exe)."""
    dest = dest or resource_path(ICON_ICO)
    src = Image.open(resource_path(ICON_FILE)).convert("RGBA")
    bbox = src.getbbox()
    if bbox:
        src = src.crop(bbox)
    side = max(src.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
    base = square.resize((256, 256), Image.Resampling.LANCZOS)
    sizes = [(s, s) for s in APP_ICO_SIZES]
    dest.parent.mkdir(parents=True, exist_ok=True)
    base.save(dest, format="ICO", sizes=sizes)
    return dest


_base_icon: Image.Image | None = None
_tray_cache: dict[bool, "_TrayIco"] = {}


class _TrayIco:
    """Wrapper: pystray salva ICO; forcamos multi-resolucao para a bandeja."""

    __slots__ = ("_img",)

    def __init__(self, img: Image.Image):
        self._img = img

    def save(self, fp, format=None, **kwargs):
        if (format or "").upper() == "ICO":
            self._img.save(fp, format="ICO", sizes=TRAY_ICO_SIZES)
        else:
            self._img.save(fp, format=format, **kwargs)


def load_app_icon(size: int = 64) -> Image.Image:
    global _base_icon
    if _base_icon is None:
        src = Image.open(resource_path(ICON_FILE)).convert("RGBA")
        bbox = src.getbbox()
        if bbox:
            src = src.crop(bbox)
        side = max(src.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
        _base_icon = square
    icon = _base_icon.copy()
    if icon.size != (size, size):
        icon = icon.resize((size, size), Image.Resampling.LANCZOS)
    return icon


def _render_tray_frame(active: bool) -> Image.Image:
    """Renderiza no tamanho nativo da bandeja (evita downscale borrado)."""
    size = TRAY_RENDER_SIZE
    src = load_app_icon(512)
    img = src.resize((size, size), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)

    dot = max(11, (size * 2) // 5)
    margin = 0
    x1 = size - dot - margin
    y1 = margin
    x2 = size - margin
    y2 = y1 + dot

    fill = (50, 220, 70, 255) if active else (235, 55, 55, 255)
    draw.ellipse((x1, y1, x2, y2), fill=fill, outline=(255, 255, 255, 255), width=2)
    return img


def make_tray_icon(active: bool = False) -> _TrayIco:
    if active not in _tray_cache:
        _tray_cache[active] = _TrayIco(_render_tray_frame(active))
    return _tray_cache[active]


def config_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "KeyPressSwitch" / "config.json"


def serialize_kb_key(key):
    char = getattr(key, "char", None)
    if char:
        return {"kind": "char", "value": char}
    name = getattr(key, "name", None)
    if name:
        return {"kind": "name", "value": name}
    return None


def deserialize_kb_key(data):
    if not data:
        return None
    kind = data.get("kind")
    value = data.get("value")
    if kind == "char" and value:
        return keyboard.KeyCode.from_char(value)
    if kind == "name" and value:
        try:
            return keyboard.Key[value]
        except KeyError:
            return None
    return None


def serialize_switch(switch_type, switch_norm):
    if switch_type is None:
        return None
    if switch_type == "keyboard":
        return {"type": "keyboard", "norm": switch_norm}
    if switch_type == "mouse":
        return {"type": "mouse", "button": switch_norm.name}
    return None


def deserialize_switch(data):
    if not data:
        return None, None, "—"
    stype = data.get("type")
    if stype == "keyboard":
        norm = data.get("norm")
        if not norm:
            return None, None, "—"
        key = deserialize_kb_key({"kind": "name", "value": norm})
        if key is None:
            key = deserialize_kb_key({"kind": "char", "value": norm})
        label = key_to_label(key) if key else norm.upper()
        return "keyboard", norm, label
    if stype == "mouse":
        button_name = data.get("button")
        try:
            button = mouse.Button[button_name]
        except (KeyError, TypeError):
            return None, None, "—"
        return "mouse", button, key_to_label(button)
    return None, None, "—"


def load_config_file() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config_file(data: dict) -> None:
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def key_to_label(key) -> str:
    """Rotulo legivel para uma tecla/botao capturado."""
    if isinstance(key, mouse.Button):
        return f"Mouse {key.name}"
    char = getattr(key, "char", None)
    if char:
        return char.upper()
    name = getattr(key, "name", None)
    if name:
        return name.upper()
    return str(key)


def normalize_kb(key) -> str:
    """Chave de comparacao estavel para teclas de teclado."""
    char = getattr(key, "char", None)
    if char:
        return char.lower()
    name = getattr(key, "name", None)
    if name:
        return name.lower()
    return str(key)


class KeyHolder:
    """Mantem uma tecla pressionada reenviando keydown (emula auto-repeat)."""

    def __init__(self, interval: float = 0.03):
        self._kb = keyboard.Controller()
        self._interval = interval
        self._thread = None
        self._stop = threading.Event()
        self._key = None

    def start(self, key):
        self.stop()
        self._key = key
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                self._kb.press(self._key)
            except Exception:
                pass
            time.sleep(self._interval)

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None
        if self._key is not None:
            try:
                self._kb.release(self._key)
            except Exception:
                pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.lock = threading.Lock()

        # Estado da configuracao
        self.switch_type = None      # "keyboard" | "mouse"
        self.switch_norm = None      # str normalizado (teclado) ou Button (mouse)
        self.switch_label = "—"
        self.hold_key = None         # objeto de tecla a segurar
        self.hold_label = "—"

        # Estado de execucao
        self.active = False
        self.capture = None          # None | "switch" | "hold"
        self.switch_down = False     # evita toggles repetidos (auto-repeat)

        self.holder = KeyHolder()
        self.tray_icon = None
        self.in_tray = False
        self._closing = False
        self._last_tray_active = None
        self._overlay_tick = 0
        self._last_overlay_key = None

        self._build_gui()
        self._build_overlay()
        self._load_config()
        self._start_listeners()
        self._poll()

    # ---------------- GUI principal ----------------
    def _build_gui(self):
        self.root.title(APP_NAME)
        self.root.geometry("380x330")
        self.root.resizable(False, False)
        self._set_window_icon()

        frm = ttk.Frame(self.root, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Tecla de Switch (liga/desliga)").grid(
            row=0, column=0, sticky="w"
        )
        self.lbl_switch = ttk.Label(frm, text="—", foreground="#0a58ca")
        self.lbl_switch.grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.btn_switch = ttk.Button(
            frm, text="Definir switch", command=lambda: self._set_capture("switch")
        )
        self.btn_switch.grid(row=1, column=1, sticky="e")

        ttk.Separator(frm).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(frm, text="Tecla a segurar (teclado)").grid(
            row=3, column=0, sticky="w"
        )
        self.lbl_hold = ttk.Label(frm, text="—", foreground="#0a58ca")
        self.lbl_hold.grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.btn_hold = ttk.Button(
            frm, text="Definir tecla", command=lambda: self._set_capture("hold")
        )
        self.btn_hold.grid(row=4, column=1, sticky="e")

        ttk.Separator(frm).grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

        self.lbl_status = ttk.Label(
            frm, text="INATIVO", font=("Segoe UI", 14, "bold"), foreground="#888"
        )
        self.lbl_status.grid(row=6, column=0, sticky="w")

        self.show_overlay = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frm,
            text="Mostrar overlay",
            variable=self.show_overlay,
            command=self._toggle_overlay_visibility,
        ).grid(row=6, column=1, sticky="e")

        self.lbl_hint = ttk.Label(
            frm, text="Configure as teclas e use o switch.", foreground="#666"
        )
        self.lbl_hint.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Button(
            frm, text="Minimizar para bandeja", command=self._hide_to_tray
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Separator(frm).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 8))

        credit = ttk.Frame(frm)
        credit.grid(row=10, column=0, columnspan=2, sticky="ew")
        ttk.Label(credit, text=f"Criado por {AUTHOR_NAME}", foreground="#666").pack(
            side="left"
        )
        link = tk.Label(
            credit,
            text="GitHub",
            fg="#0a58ca",
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        link.pack(side="right")
        link.bind("<Button-1>", lambda _e: webbrowser.open(GITHUB_URL))

        frm.columnconfigure(0, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.root.bind("<Unmap>", self._on_unmap)

    def _set_window_icon(self):
        try:
            if sys.platform == "win32":
                ico = resource_path(ICON_ICO)
                if not ico.is_file():
                    write_app_ico(ico)
                self.root.iconbitmap(default=str(ico))
                return
            png = resource_path(ICON_FILE)
            if png.is_file():
                photo = ImageTk.PhotoImage(load_app_icon(64))
                self.root.iconphoto(True, photo)
                self._window_icon = photo
        except (tk.TclError, OSError):
            pass

    # ---------------- Overlay ----------------
    def _build_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        try:
            self.overlay.attributes("-alpha", 0.85)
        except tk.TclError:
            pass
        self.overlay.geometry("+8+8")
        self.overlay.configure(bg="#222")

        self.ov_label = tk.Label(
            self.overlay,
            text="INATIVO",
            font=("Segoe UI", 12, "bold"),
            fg="#ff5555",
            bg="#222",
            padx=10,
            pady=6,
        )
        self.ov_label.pack()
        self.overlay.update_idletasks()
        self.overlay.after(50, self._pin_overlay)

    def _pin_overlay(self):
        if sys.platform != "win32" or not self.show_overlay.get():
            return
        try:
            if not self.overlay.winfo_viewable():
                return
            pin_overlay_win32(self.overlay.winfo_id())
        except (tk.TclError, OSError):
            pass

    def _sync_overlay(self, active: bool, hold_label: str):
        if not self.show_overlay.get():
            return
        try:
            if not self.overlay.winfo_viewable():
                return
        except tk.TclError:
            return

        if active:
            text, fg = f"ATIVO  [{hold_label}]", "#55ff55"
        else:
            text, fg = f"INATIVO  [{hold_label}]", "#ff5555"

        self.ov_label.config(text=text, fg=fg)
        self.overlay.update_idletasks()
        w = self.ov_label.winfo_reqwidth()
        h = self.ov_label.winfo_reqheight()
        self.overlay.geometry(f"{w}x{h}+8+8")
        self.overlay.attributes("-topmost", True)
        self.overlay.lift()

        overlay_key = (active, hold_label)
        if overlay_key != self._last_overlay_key:
            self._last_overlay_key = overlay_key
            self.overlay.after(10, self._pin_overlay)

    def _toggle_overlay_visibility(self):
        self._last_overlay_key = None
        if self.show_overlay.get():
            self.overlay.deiconify()
            self.overlay.after(50, self._pin_overlay)
        else:
            self.overlay.withdraw()
        self._save_config()

    # ---------------- Persistencia ----------------
    def _load_config(self):
        data = load_config_file()
        if data.get("version") != CONFIG_VERSION:
            return

        stype, snorm, slabel = deserialize_switch(data.get("switch"))
        self.switch_type = stype
        self.switch_norm = snorm
        self.switch_label = slabel

        hold_key = deserialize_kb_key(data.get("hold"))
        if hold_key is not None:
            self.hold_key = hold_key
            self.hold_label = key_to_label(hold_key)

        if "show_overlay" in data:
            self.show_overlay.set(bool(data["show_overlay"]))

        if self.show_overlay.get():
            self.overlay.deiconify()
            self.overlay.after(50, self._pin_overlay)
        else:
            self.overlay.withdraw()

    def _save_config(self):
        data = {
            "version": CONFIG_VERSION,
            "switch": serialize_switch(self.switch_type, self.switch_norm),
            "hold": serialize_kb_key(self.hold_key),
            "show_overlay": self.show_overlay.get(),
        }
        save_config_file(data)

    # ---------------- Bandeja do sistema (Windows) ----------------
    def _ensure_tray(self):
        if self.tray_icon is not None:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Abrir", self._tray_open, default=True),
            pystray.MenuItem("Sair", self._tray_quit),
        )
        self.tray_icon = pystray.Icon(
            "keypress",
            make_tray_icon(False),
            APP_NAME,
            menu,
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _hide_to_tray(self):
        if self.in_tray:
            return
        self.in_tray = True
        self.root.withdraw()
        self._ensure_tray()
        self._update_tray_icon()

    def _restore_from_tray(self):
        self.in_tray = False
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def _on_unmap(self, event):
        if event.widget is not self.root or self.in_tray or self._closing:
            return
        if self.root.state() == "iconic":
            self.root.after(50, self._hide_to_tray)

    def _tray_open(self, icon=None, item=None):
        self.root.after(0, self._restore_from_tray)

    def _tray_quit(self, icon=None, item=None):
        self.root.after(0, self._on_close)

    def _update_tray_icon(self):
        if self.tray_icon is None:
            return
        with self.lock:
            active = self.active
        if active == self._last_tray_active:
            return
        self._last_tray_active = active
        self.tray_icon.icon = make_tray_icon(active)
        self.tray_icon.title = f"{APP_NAME} — {'ATIVO' if active else 'INATIVO'}"

    # ---------------- Captura de teclas ----------------
    def _set_capture(self, mode: str):
        with self.lock:
            self.capture = mode
        msg = (
            "Pressione tecla ou botao do mouse..."
            if mode == "switch"
            else "Pressione a tecla a segurar..."
        )
        self.lbl_hint.config(text=msg)

    # ---------------- Listeners ----------------
    def _start_listeners(self):
        self.kb_listener = keyboard.Listener(
            on_press=self._on_kb_press, on_release=self._on_kb_release
        )
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.kb_listener.start()
        self.mouse_listener.start()

    def _on_kb_press(self, key):
        with self.lock:
            if self.capture == "switch":
                self.switch_type = "keyboard"
                self.switch_norm = normalize_kb(key)
                self.switch_label = key_to_label(key)
                self.capture = None
                self.root.after(0, self._save_config)
                return
            if self.capture == "hold":
                self.hold_key = key
                self.hold_label = key_to_label(key)
                self.capture = None
                # Se estava ativo, reinicia a segurar a nova tecla
                if self.active:
                    self.holder.start(self.hold_key)
                self.root.after(0, self._save_config)
                return
            if (
                self.switch_type == "keyboard"
                and normalize_kb(key) == self.switch_norm
                and not self.switch_down
            ):
                self.switch_down = True
                self._toggle_locked()

    def _on_kb_release(self, key):
        with self.lock:
            if (
                self.switch_type == "keyboard"
                and normalize_kb(key) == self.switch_norm
            ):
                self.switch_down = False

    def _on_mouse_click(self, x, y, button, pressed):
        if not pressed:
            return
        with self.lock:
            if self.capture == "switch":
                self.switch_type = "mouse"
                self.switch_norm = button
                self.switch_label = key_to_label(button)
                self.capture = None
                self.root.after(0, self._save_config)
                return
            if self.switch_type == "mouse" and button == self.switch_norm:
                self._toggle_locked()

    # ---------------- Logica do switch ----------------
    def _toggle_locked(self):
        """Deve ser chamado com self.lock adquirido."""
        if self.hold_key is None:
            return
        self.active = not self.active
        if self.active:
            self.holder.start(self.hold_key)
        else:
            self.holder.stop()

    # ---------------- Loop de atualizacao da GUI ----------------
    def _poll(self):
        with self.lock:
            active = self.active
            switch_label = self.switch_label
            hold_label = self.hold_label

        self.lbl_switch.config(text=switch_label)
        self.lbl_hold.config(text=hold_label)

        if active:
            self.lbl_status.config(text="ATIVO", foreground="#1a7f37")
        else:
            self.lbl_status.config(text="INATIVO", foreground="#888")

        self._sync_overlay(active, hold_label)
        self._update_tray_icon()

        self._overlay_tick += 1
        if self._overlay_tick % 40 == 0:
            self._pin_overlay()

        self.root.after(50, self._poll)

    def _on_close(self):
        self._closing = True
        self._save_config()
        self.holder.stop()
        try:
            self.kb_listener.stop()
            self.mouse_listener.stop()
        except Exception:
            pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()


def main():
    ensure_single_instance()
    enable_windows_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
