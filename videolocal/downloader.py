"""Camada de download: traduz as escolhas da interface em opções do yt-dlp."""

from __future__ import annotations

import io
import re
import shutil
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

try:
    import yt_dlp
    from yt_dlp.utils import DownloadCancelled
except ImportError:  # tratado na interface com uma mensagem clara
    yt_dlp = None

    class DownloadCancelled(Exception):
        pass

from .platforms import Platform
from .settings import app_dir

VIDEO_FORMATS = ("MP4", "WEBM")
VIDEO_QUALITIES = ("Melhor disponível", "2160p (4K)", "1440p", "1080p", "720p", "480p")
AUDIO_FORMATS = ("MP3", "M4A")
AUDIO_QUALITIES = ("320 kbps", "192 kbps", "128 kbps")
COOKIE_BROWSERS = {"Nenhum": "", "Firefox": "firefox", "Chrome": "chrome", "Edge": "edge", "Brave": "brave"}

_JS_RUNTIMES = {"deno": "deno", "node": "node", "bun": "bun", "qjs": "quickjs"}
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PART_SUFFIX = re.compile(r"\.f[\w-]+\.\w+$")


class _SilentLogger:
    """O app não tem console (no .exe nem existe stderr); os erros chegam por exceção."""

    def debug(self, message): ...
    def info(self, message): ...
    def warning(self, message): ...
    def error(self, message): ...


@dataclass(frozen=True)
class Choice:
    """O que o usuário pediu: vídeo ou áudio, em qual formato e qualidade."""

    kind: str  # "Vídeo" | "Áudio"
    fmt: str
    quality: str

    @property
    def is_audio(self) -> bool:
        return self.kind == "Áudio"

    @property
    def label(self) -> str:
        return f"{self.fmt} • {self.quality}"


def find_ffmpeg(configured: str = "") -> str:
    """Procura o ffmpeg.exe: caminho salvo, pasta do app e, por fim, o PATH."""
    if configured and Path(configured).is_file():
        return configured
    base = app_dir()
    for relative in ("bin/ffmpeg.exe", "ffmpeg.exe", "ffmpeg/bin/ffmpeg.exe", "tools/ffmpeg/bin/ffmpeg.exe"):
        candidate = base / relative
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffmpeg") or ""


def js_runtimes() -> dict[str, dict]:
    """Runtimes JavaScript instalados, no formato esperado pelo yt-dlp.

    O yt-dlp só habilita o Deno por padrão; Node, Bun e QuickJS precisam ser
    informados explicitamente, senão são ignorados mesmo estando no PATH.
    """
    return {name: {} for exe, name in _JS_RUNTIMES.items() if shutil.which(exe)}


def build_options(choice: Choice, platform: Platform, destination: Path, ffmpeg: str, cookies_browser: str = "") -> dict:
    opts: dict = {
        "outtmpl": str(destination / "%(title).120B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "windowsfilenames": True,
        "ignoreerrors": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 20,
        "js_runtimes": js_runtimes(),
        "logger": _SilentLogger(),
    }
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)

    if choice.is_audio:
        codec = choice.fmt.lower()
        bitrate = re.sub(r"\D", "", choice.quality) or "192"
        opts["format"] = "ba[ext=m4a]/ba/b" if codec == "m4a" else "ba/b"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": bitrate}]
        return opts

    # "res" no yt-dlp é a MENOR dimensão do vídeo, então "res:1080" funciona
    # tanto para vídeos deitados (1920x1080) quanto em pé (1080x1920, Reels).
    height = re.match(r"\d+", choice.quality)
    sort = [f"res:{height.group()}"] if height else []
    # Sem FFmpeg não dá para juntar faixas separadas: pede um arquivo único.
    opts["format"] = "bv*+ba/b" if ffmpeg else "b"
    if choice.fmt == "WEBM" and platform.key == "youtube":
        opts["prefer_free_formats"] = True
        opts["merge_output_format"] = "webm/mkv"
    else:
        # H.264 + AAC é a combinação que toca em qualquer player e editor.
        sort += ["vcodec:h264", "acodec:aac", "ext:mp4:m4a"]
        opts["merge_output_format"] = "mp4"
    opts["format_sort"] = sort
    return opts


def friendly_error(exc: BaseException, platform: Platform, using_cookies: bool) -> str:
    """Converte o erro técnico do yt-dlp em uma orientação em português."""
    raw = _ANSI.sub("", str(exc)).strip()
    low = raw.lower()

    def has(*needles: str) -> bool:
        return any(n in low for n in needles)

    if has("could not copy", "cookie database", "dpapi", "failed to decrypt", "could not find", "cookies database"):
        if using_cookies:
            return ("Não foi possível ler a sessão do navegador escolhido. Feche o navegador e tente de novo, "
                    "ou selecione o Firefox em Configurações (Chrome e Edge costumam bloquear essa leitura no Windows).")
    if has("no video could be found", "there is no video in this post", "no video formats found", "no media found"):
        return "Esta publicação não contém vídeo para baixar."
    if has("login required", "log in", "sign in", "rate-limit", "rate limit", "not available to you",
           "requested content is not available", "nsfw", "age-restricted", "confirm your age", "private"):
        hint = ("Confira se a conta escolhida em Configurações tem acesso a este conteúdo."
                if using_cookies else
                "Abra Configurações e escolha o navegador em que você está conectado para usar a sua sessão.")
        return f"O {platform.name} exige login para este conteúdo (privado, restrito ou com limite de acessos). {hint}"
    if has("video unavailable", "has been removed", "does not exist", "404", "not found"):
        return "Conteúdo indisponível: o link pode estar errado ou a publicação foi removida."
    if has("drm"):
        return "Este conteúdo é protegido por DRM e não pode ser baixado."
    if has("ffmpeg", "ffprobe"):
        return "O FFmpeg é necessário para concluir este formato. Configure-o em Configurações."
    if has("timed out", "getaddrinfo", "connection", "network", "urlopen error"):
        return "Falha de conexão. Verifique a internet e tente novamente."
    if has("unsupported url"):
        return "Este link não aponta para um vídeo reconhecido."
    last_line = raw.splitlines()[-1] if raw else ""
    return re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*)?([\w-]+:\s*)?", "", last_line)[:300] or "Verifique o link e tente novamente."


def fetch_thumbnail(url: str, size: tuple[int, int]):
    """Baixa a miniatura e recorta para o tamanho do cartão. Devolve PIL.Image ou None."""
    if not url or not url.startswith("https://"):
        return None
    try:
        from PIL import Image, ImageOps

        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            data = response.read(4 * 1024 * 1024)
        image = Image.open(io.BytesIO(data)).convert("RGB")
        return ImageOps.fit(image, size, Image.LANCZOS)
    except Exception:
        return None  # miniatura é enfeite: qualquer falha vira o espaço reservado


def run_download(
    url: str,
    platform: Platform,
    choice: Choice,
    destination: Path,
    ffmpeg: str,
    cookies_browser: str,
    cancel: threading.Event,
    on_info: Callable[[dict], None],
    on_progress: Callable[[float, str], None],
) -> str:
    """Baixa um link e devolve o caminho do arquivo final.

    Roda numa thread de trabalho; os callbacks só colocam eventos numa fila.
    Lança DownloadCancelled se `cancel` for acionado.
    """
    state = {"finished_parts": 0, "best": 0.0}

    def progress_hook(data: dict) -> None:
        if cancel.is_set():
            raise DownloadCancelled("Cancelado pelo usuário")
        # Quando vídeo e áudio vêm separados, o yt-dlp nomeia cada faixa como
        # "titulo.f136.mp4"; esse sufixo indica um download em duas partes.
        split = bool(_PART_SUFFIX.search(data.get("filename") or ""))
        parts = max(2 if split else 1, state["finished_parts"] + 1)
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            fraction = min(data.get("downloaded_bytes", 0) / total, 1.0) if total else 0.0
            # Em downloads por fragmentos (HLS) o tamanho total é uma estimativa
            # que muda no caminho; a barra nunca deve andar para trás.
            overall = state["best"] = max((state["finished_parts"] + fraction) / parts, state["best"])
            details = [f"{overall * 100:.0f}%"]
            if total:
                details.append(_human_size(total))
            if data.get("speed"):
                details.append(f"{_human_size(data['speed'])}/s")
            if data.get("eta") is not None:
                details.append(f"restam {_human_time(data['eta'])}")
            on_progress(min(overall, 0.99), "Baixando  •  " + "  •  ".join(details))
        elif data.get("status") == "finished":
            state["finished_parts"] += 1

    def postprocessor_hook(data: dict) -> None:
        if data.get("status") == "started":
            name = data.get("postprocessor", "")
            if name == "Merger":
                on_progress(0.99, "Juntando vídeo e áudio…")
            elif name == "ExtractAudio":
                on_progress(0.99, "Convertendo áudio…")

    opts = build_options(choice, platform, destination, ffmpeg, cookies_browser)
    opts["progress_hooks"] = [progress_hook]
    opts["postprocessor_hooks"] = [postprocessor_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        # Duas etapas com uma única consulta ao site: primeiro os metadados
        # (para preencher o cartão), depois o download a partir deles.
        info = ydl.extract_info(url, download=False, process=False)
        if cancel.is_set():
            raise DownloadCancelled("Cancelado pelo usuário")
        on_info({
            "title": info.get("title") or "",
            "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id") or "",
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail") or _first_thumbnail(info),
        })
        result = ydl.process_ie_result(info, download=True)

    entries = [e for e in (result.get("entries") or [result]) if e]
    for entry in reversed(entries):
        for item in entry.get("requested_downloads") or ():
            if item.get("filepath"):
                return item["filepath"]
    return ""


def _first_thumbnail(info: dict) -> str:
    thumbs = info.get("thumbnails") or []
    return (thumbs[-1].get("url") or "") if thumbs else ""


def _human_size(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return ""


def _human_time(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_duration(seconds) -> str:
    return _human_time(seconds) if isinstance(seconds, (int, float)) and seconds > 0 else ""
