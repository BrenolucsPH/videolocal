"""Caminhos do aplicativo e preferências salvas do usuário."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import APP_NAME

FROZEN = getattr(sys, "frozen", False)


def app_dir() -> Path:
    """Pasta onde o aplicativo vive (ao lado do .exe ou a raiz do projeto)."""
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    """Arquivos embutidos (ícones). No .exe eles ficam em sys._MEIPASS."""
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / relative


def config_file() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    return base / APP_NAME / "settings.json"


@dataclass
class Settings:
    output_dir: str = str(Path.home() / "Videos" / APP_NAME)
    kind: str = "Vídeo"
    video_format: str = "MP4"
    video_quality: str = "1080p"
    audio_format: str = "MP3"
    audio_quality: str = "192 kbps"
    theme: str = "dark"
    ffmpeg_path: str = ""
    cookies_browser: str = ""

    @classmethod
    def load(cls) -> "Settings":
        try:
            raw = json.loads(config_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        defaults = cls()
        known = {}
        for f in fields(cls):
            value = raw.get(f.name)
            # Ignora chaves desconhecidas e valores de tipo errado.
            known[f.name] = value if isinstance(value, str) else getattr(defaults, f.name)
        return cls(**known)

    def save(self) -> None:
        try:
            path = config_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass  # preferências são conveniência; nunca devem derrubar o app
