"""Reconhecimento das plataformas suportadas a partir do link colado."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    color: str  # cor de destaque usada no selo da interface
    hosts: tuple[str, ...]

    def matches(self, host: str) -> bool:
        return any(host == h or host.endswith("." + h) for h in self.hosts)


YOUTUBE = Platform("youtube", "YouTube", "#ff3b30", ("youtube.com", "youtu.be", "youtube-nocookie.com"))
TWITTER = Platform("twitter", "X (Twitter)", "#8b98a5", ("twitter.com", "x.com"))
INSTAGRAM = Platform("instagram", "Instagram", "#e1306c", ("instagram.com", "instagr.am"))

PLATFORMS: tuple[Platform, ...] = (YOUTUBE, TWITTER, INSTAGRAM)


def parse_link(text: str) -> tuple[str, Platform] | None:
    """Normaliza o texto colado e devolve (url_https, plataforma).

    Aceita links sem esquema ("x.com/..."), converte http em https e recusa
    qualquer host fora da lista — a comparação é feita pelo hostname já
    interpretado, então "youtube.com.exemplo.net" não passa.
    """
    value = (text or "").strip()
    if not value or any(ch.isspace() for ch in value):
        return None
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not host:
        return None
    if not parsed.path.strip("/"):
        return None  # só o domínio, sem apontar para um vídeo
    for platform in PLATFORMS:
        if platform.matches(host):
            return parsed._replace(scheme="https").geturl(), platform
    return None
