"""Interface gráfica do VideoLocal (CustomTkinter)."""

from __future__ import annotations

import itertools
import os
import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import APP_NAME, __version__
from . import downloader as dl
from .platforms import PLATFORMS, Platform, parse_link
from .settings import Settings, resource_path

# ── Paleta: cada cor é um par (tema claro, tema escuro) ──────────────────────
BG = ("#f2f4f8", "#0d0f13")
SURFACE = ("#ffffff", "#16191f")
FIELD = ("#eef1f6", "#1e222a")
BORDER = ("#dde2ea", "#282d37")
TEXT = ("#131926", "#eef1f6")
MUTED = ("#647084", "#8a93a3")
ACCENT = ("#3563ff", "#4f7cff")
ACCENT_HOVER = ("#2a50d6", "#6a90ff")
SUCCESS = ("#14805a", "#3ecf8e")
DANGER = ("#d1291d", "#ff6b5e")
WARN_BG = ("#fff6e0", "#2a2313")
WARN_TEXT = ("#7a5410", "#f0c36a")

FONT = "Segoe UI"
FONT_BOLD = "Segoe UI Semibold"
ICONS = "Segoe MDL2 Assets"  # fonte de ícones que acompanha o Windows 10/11

# Glifos da Segoe MDL2 Assets
I_SETTINGS, I_SUN, I_MOON, I_PASTE, I_LINK = "", "", "", "", ""
I_FOLDER, I_CANCEL, I_DELETE, I_RETRY, I_PLAY, I_VIDEO, I_AUDIO = "", "", "", "", "", "", ""
I_DOWNLOAD = ""

THUMB = (144, 81)
THEMES = {"Claro": "light", "Escuro": "dark", "Sistema": "system"}

QUEUED, RUNNING, DONE, ERROR, CANCELLED = "queued", "running", "done", "error", "cancelled"
_ids = itertools.count(1)


@dataclass
class Job:
    url: str
    platform: Platform
    choice: dl.Choice
    destination: Path
    id: int = field(default_factory=lambda: next(_ids))
    cancel: threading.Event = field(default_factory=threading.Event)


def font(size: int, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_BOLD if bold else FONT, size=size)


def icon_button(master, glyph: str, command, size: int = 34, **kwargs) -> ctk.CTkButton:
    options = dict(
        width=size, height=size, corner_radius=8, text=glyph, font=ctk.CTkFont(family=ICONS, size=15),
        fg_color="transparent", hover_color=FIELD, text_color=MUTED, command=command,
    )
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def option_menu(master, values, command, width: int = 150) -> ctk.CTkOptionMenu:
    return ctk.CTkOptionMenu(
        master, values=list(values), command=command, width=width, height=36, corner_radius=8, font=font(13),
        dropdown_font=font(13), fg_color=FIELD, button_color=FIELD, button_hover_color=BORDER, text_color=TEXT,
        dropdown_fg_color=SURFACE, dropdown_hover_color=FIELD, dropdown_text_color=TEXT,
    )


def rounded(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=radius, fill=255)
    result = image.convert("RGBA")
    result.putalpha(mask)
    return result


class JobCard(ctk.CTkFrame):
    """Um item da lista de downloads: miniatura, título, progresso e ações."""

    def __init__(self, master, app: "App", job: Job):
        super().__init__(master, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        self.app, self.job, self.state, self.filepath = app, job, QUEUED, ""
        self._title, self._status_text = job.url, ""
        self._indeterminate = False
        self.grid_columnconfigure(1, weight=1)

        glyph = I_AUDIO if job.choice.is_audio else I_VIDEO
        # Moldura de tamanho fixo: o cartão não "pula" quando a miniatura chega.
        self.thumb_box = ctk.CTkFrame(self, width=THUMB[0], height=THUMB[1], corner_radius=8, fg_color=FIELD)
        self.thumb_box.grid(row=0, column=0, rowspan=4, padx=14, pady=14)
        self.thumb_box.grid_propagate(False)
        self.thumb = ctk.CTkLabel(
            self.thumb_box, text=glyph, font=ctk.CTkFont(family=ICONS, size=24), text_color=MUTED, fg_color="transparent",
        )
        self.thumb.place(relx=0.5, rely=0.5, anchor="center")

        self.title = ctk.CTkLabel(self, text="", font=font(14, bold=True), text_color=TEXT, anchor="w", height=20)
        self.title.grid(row=0, column=1, sticky="ew", pady=(14, 0))

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=1, column=1, sticky="w", pady=(2, 0))
        ctk.CTkLabel(meta, text="●", font=font(11), text_color=job.platform.color, height=16).pack(side="left")
        self.meta = ctk.CTkLabel(meta, text="", font=font(12), text_color=MUTED, height=16)
        self.meta.pack(side="left", padx=(5, 0))
        self._meta_extra = ""

        self.bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, fg_color=FIELD, progress_color=ACCENT)
        self.bar.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        self.bar.set(0)

        self.status = ctk.CTkLabel(self, text="", font=font(12), text_color=MUTED, anchor="w", justify="left", height=16)
        self.status.grid(row=3, column=1, sticky="ew", pady=(6, 14))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.grid(row=0, column=2, rowspan=4, padx=(10, 12))

        self.bind("<Configure>", self._on_resize)
        self._render_meta()
        self.set_state(QUEUED)

    # ── conteúdo ────────────────────────────────────────────────────────────
    def _render_meta(self):
        parts = [self.job.platform.name, self.job.choice.label]
        if self._meta_extra:
            parts.append(self._meta_extra)
        self.meta.configure(text="  •  ".join(parts))

    def set_info(self, info: dict):
        if info.get("title"):
            self._title = info["title"]
        extra = [p for p in (info.get("uploader"), dl.format_duration(info.get("duration"))) if p]
        self._meta_extra = "  •  ".join(extra)[:60]
        self._render_meta()
        self._fit_text()

    def set_thumbnail(self, image: Image.Image):
        picture = ctk.CTkImage(light_image=image, dark_image=image, size=THUMB)
        self.thumb_box.configure(fg_color="transparent")
        self.thumb.configure(image=picture, text="")

    def set_progress(self, fraction: float, text: str):
        if self.state != RUNNING:
            return
        self._stop_spinner()
        self.bar.set(fraction)
        self._set_status(text, MUTED)

    def _set_status(self, text: str, color):
        self._status_text = text
        self.status.configure(text_color=color)
        self._fit_text()

    def _on_resize(self, _event=None):
        self._fit_text()

    def _fit_text(self):
        """Corta o título e quebra o status conforme a largura real do cartão."""
        scale = self._get_widget_scaling()
        available = max(int(self.winfo_width() / scale) - THUMB[0] - 150, 160)
        max_chars = max(int(available / 7.4), 12)
        title = self._title if len(self._title) <= max_chars else self._title[: max_chars - 1].rstrip() + "…"
        self.title.configure(text=title)
        self.status.configure(text=self._status_text, wraplength=available)

    # ── estados ─────────────────────────────────────────────────────────────
    def _stop_spinner(self):
        if self._indeterminate:
            self.bar.stop()
            self.bar.configure(mode="determinate")
            self._indeterminate = False

    def set_state(self, state: str, message: str = ""):
        self.state = state
        for child in self.actions.winfo_children():
            child.destroy()
        # A barra só aparece quando há progresso para mostrar.
        if state in (RUNNING, DONE):
            self.bar.grid()
        else:
            self._stop_spinner()
            self.bar.grid_remove()
        if state == QUEUED:
            self._set_status("Na fila", MUTED)
            self._action(I_CANCEL, self._cancel)
        elif state == RUNNING:
            self.bar.configure(mode="indeterminate", progress_color=ACCENT)
            self.bar.start()
            self._indeterminate = True
            self._set_status("Conectando…", MUTED)
            self._action(I_CANCEL, self._cancel)
        elif state == DONE:
            self._stop_spinner()
            self.bar.configure(progress_color=SUCCESS)
            self.bar.set(1)
            name = Path(self.filepath).name if self.filepath else "arquivo salvo"
            self._set_status(f"Concluído  •  {name}", SUCCESS)
            if self.filepath:
                self._action(I_PLAY, self._open_file)
            self._action(I_FOLDER, self._open_folder)
            self._action(I_DELETE, self._remove)
        else:  # ERROR ou CANCELLED
            self._set_status(message, DANGER if state == ERROR else MUTED)
            self._action(I_RETRY, self._retry)
            self._action(I_DELETE, self._remove)
        self.app.refresh_queue_header()

    def _action(self, glyph: str, command):
        icon_button(self.actions, glyph, command).pack(side="left", padx=1)

    # ── ações ───────────────────────────────────────────────────────────────
    def _cancel(self):
        self.job.cancel.set()
        if self.state == QUEUED:
            self.set_state(CANCELLED, "Cancelado")
        else:
            self._set_status("Cancelando…", MUTED)

    def _retry(self):
        self.app.requeue(self)

    def _remove(self):
        self.app.remove_card(self)

    def _open_file(self):
        try:
            os.startfile(self.filepath)  # noqa: S606 — abre no player padrão do Windows
        except OSError:
            self._open_folder()

    def _open_folder(self):
        if self.filepath and Path(self.filepath).exists():
            subprocess.Popen(["explorer", "/select,", str(Path(self.filepath))])
        else:
            self.app.open_folder(self.job.destination)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app: "App"):
        super().__init__(app, fg_color=BG)
        self.app = app
        self.title("Configurações")
        self.resizable(False, False)
        self.transient(app)
        self.after(250, app.apply_icon, self)  # o CTk redefine o ícone logo após abrir

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=26, pady=22)
        ctk.CTkLabel(body, text="Configurações", font=font(20, bold=True), text_color=TEXT).pack(anchor="w")

        # Aparência
        section = self._section(body, "Aparência", "Tema da janela.")
        theme = ctk.CTkSegmentedButton(
            section, values=list(THEMES), command=self._set_theme, font=font(13), height=34, corner_radius=8,
            fg_color=FIELD, unselected_color=FIELD, unselected_hover_color=BORDER, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER, text_color=TEXT,
        )
        theme.set(next((k for k, v in THEMES.items() if v == app.settings.theme), "Escuro"))
        theme.pack(anchor="w", pady=(10, 0))

        # Sessão do navegador
        section = self._section(
            body, "Sessão do navegador",
            "Só é necessária para conteúdo que exige login, comum no Instagram e no X. O app lê os cookies "
            "do navegador escolhido apenas no momento do download e não os guarda. O Firefox é o mais confiável.",
        )
        browsers = option_menu(section, dl.COOKIE_BROWSERS, self._set_browser, width=180)
        browsers.set(next((k for k, v in dl.COOKIE_BROWSERS.items() if v == app.settings.cookies_browser), "Nenhum"))
        browsers.pack(anchor="w", pady=(10, 0))

        # FFmpeg
        section = self._section(body, "FFmpeg", "Necessário para MP3/M4A e para juntar vídeo e áudio nas melhores qualidades.")
        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        self.ffmpeg_label = ctk.CTkLabel(row, text="", font=font(12), anchor="w", wraplength=330, justify="left")
        self.ffmpeg_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="Localizar…", width=100, height=34, corner_radius=8, font=font(13), fg_color=FIELD,
            hover_color=BORDER, text_color=TEXT, command=self._choose_ffmpeg,
        ).pack(side="right")
        self._render_ffmpeg()

        # Componentes
        runtimes = ", ".join(sorted(dl.js_runtimes())) or "não encontrado (instale Node.js ou Deno para o YouTube)"
        engine = getattr(getattr(dl.yt_dlp, "version", None), "__version__", "ausente")
        self._section(body, "Componentes", f"{APP_NAME} {__version__}  •  yt-dlp {engine}\nRuntime JavaScript: {runtimes}")

        ctk.CTkButton(
            body, text="Concluir", height=40, corner_radius=10, font=font(14, bold=True), fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color="#ffffff", command=self.destroy,
        ).pack(fill="x", pady=(18, 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(60, self._present)

    def _present(self):
        self.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - self.winfo_width()) // 2
        y = self.app.winfo_rooty() + max((self.app.winfo_height() - self.winfo_height()) // 2 - 20, 0)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus()

    def _section(self, parent, title: str, description: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(14, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(inner, text=title, font=font(14, bold=True), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(inner, text=description, font=font(12), text_color=MUTED, wraplength=440, justify="left").pack(anchor="w")
        return inner

    def _set_theme(self, label: str):
        self.app.set_theme(THEMES[label])

    def _set_browser(self, label: str):
        self.app.settings.cookies_browser = dl.COOKIE_BROWSERS[label]
        self.app.settings.save()

    def _render_ffmpeg(self):
        path = dl.find_ffmpeg(self.app.settings.ffmpeg_path)
        self.ffmpeg_label.configure(text=f"Pronto  •  {path}" if path else "Não encontrado", text_color=SUCCESS if path else DANGER)

    def _choose_ffmpeg(self):
        selected = filedialog.askopenfilename(
            parent=self, title="Selecione ffmpeg.exe",
            filetypes=[("Executável FFmpeg", "ffmpeg.exe"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return
        if Path(selected).name.lower() != "ffmpeg.exe":
            messagebox.showwarning("Arquivo inválido", "Selecione o arquivo ffmpeg.exe do pacote FFmpeg.", parent=self)
            return
        self.app.settings.ffmpeg_path = str(Path(selected))
        self.app.settings.save()
        self._render_ffmpeg()
        self.app.refresh_notice()


class App(ctk.CTk):
    def __init__(self):
        self.settings = Settings.load()
        ctk.set_appearance_mode(self.settings.theme)
        super().__init__(fg_color=BG)
        self.title(APP_NAME)
        self.geometry("940x720")
        self.minsize(780, 600)
        self.apply_icon(self)

        self.events: queue.Queue = queue.Queue()
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.cards: dict[int, JobCard] = {}
        self.settings_dialog: SettingsDialog | None = None
        self._hint_default = "Compatível com " + ", ".join(p.name for p in PLATFORMS[:-1]) + f" e {PLATFORMS[-1].name}."

        self._build()
        self._sync_option_menus()
        self._on_link_change()
        self.refresh_notice()
        self.refresh_queue_header()

        threading.Thread(target=self._worker, daemon=True).start()
        self.after(80, self._poll_events)
        self.after(300, self.entry.focus)  # pronto para Ctrl+V assim que abre
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── construção ──────────────────────────────────────────────────────────
    def apply_icon(self, window):
        try:
            window.iconbitmap(str(resource_path("assets/icon.ico")))
        except Exception:
            pass

    def _build(self):
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=28, pady=(20, 14))
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(3, weight=1)

        # Cabeçalho
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        try:
            logo = Image.open(resource_path("assets/icon.png"))
            ctk.CTkLabel(header, text="", image=ctk.CTkImage(logo, logo, size=(40, 40))).pack(side="left", padx=(0, 12))
        except OSError:
            pass
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text=APP_NAME, font=font(21, bold=True), text_color=TEXT, height=26).pack(anchor="w")
        ctk.CTkLabel(titles, text="Baixe vídeos e áudios direto para o seu computador", font=font(12), text_color=MUTED, height=16).pack(anchor="w")
        icon_button(header, I_SETTINGS, self.open_settings, size=38).pack(side="right")
        self.theme_btn = icon_button(header, I_SUN, self._toggle_theme, size=38)
        self.theme_btn.pack(side="right", padx=(0, 4))
        self._render_theme_button()

        # Cartão principal
        hero = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        hero.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        inner = ctk.CTkFrame(hero, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        inner.grid_columnconfigure(0, weight=1)

        self.link_box = ctk.CTkFrame(inner, fg_color=FIELD, corner_radius=12, border_width=2, border_color=FIELD, height=52)
        self.link_box.grid(row=0, column=0, sticky="ew")
        self.link_box.grid_columnconfigure(1, weight=1)
        self.badge = ctk.CTkLabel(self.link_box, text=I_LINK, font=ctk.CTkFont(family=ICONS, size=15), text_color=MUTED, width=24)
        self.badge.grid(row=0, column=0, padx=(16, 4), pady=12)
        self.entry = ctk.CTkEntry(
            self.link_box, placeholder_text="Cole aqui o link do vídeo", font=font(14), height=30, border_width=0,
            fg_color="transparent", text_color=TEXT, placeholder_text_color=MUTED,
        )
        self.entry.grid(row=0, column=1, sticky="ew", pady=10)
        icon_button(self.link_box, I_PASTE, self._paste, hover_color=BORDER).grid(row=0, column=2, padx=(4, 9))
        self.entry.bind("<KeyRelease>", self._on_link_change)
        self.entry.bind("<<Paste>>", lambda _e: self.after(10, self._on_link_change))
        self.entry.bind("<Return>", lambda _e: self._start())
        self.entry.bind("<FocusIn>", lambda _e: self.link_box.configure(border_color=ACCENT))
        self.entry.bind("<FocusOut>", lambda _e: self.link_box.configure(border_color=FIELD))

        self.download_btn = ctk.CTkButton(
            inner, text="Baixar", width=128, height=52, corner_radius=12, font=font(15, bold=True), fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color="#ffffff", command=self._start,
        )
        self.download_btn.grid(row=0, column=1, padx=(12, 0))

        self.hint = ctk.CTkLabel(inner, text="", font=font(12), text_color=MUTED, anchor="w", justify="left", height=16)
        self.hint.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        options = ctk.CTkFrame(inner, fg_color="transparent")
        options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.kind = ctk.CTkSegmentedButton(
            options, values=["Vídeo", "Áudio"], command=self._on_kind, font=font(13), height=36, corner_radius=8,
            fg_color=FIELD, unselected_color=FIELD, unselected_hover_color=BORDER, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER, text_color=TEXT,
        )
        self.kind.pack(side="left")
        self.format_menu = option_menu(options, dl.VIDEO_FORMATS, self._on_format, width=104)
        self.format_menu.pack(side="left", padx=(10, 0))
        self.quality_menu = option_menu(options, dl.VIDEO_QUALITIES, self._on_quality, width=176)
        self.quality_menu.pack(side="left", padx=(10, 0))

        icon_button(options, I_FOLDER, lambda: self.open_folder(Path(self.settings.output_dir))).pack(side="right")
        self.folder_btn = ctk.CTkButton(
            options, text="", height=36, corner_radius=8, font=font(13), fg_color=FIELD, hover_color=BORDER,
            text_color=TEXT, anchor="w", command=self._choose_folder,
        )
        self.folder_btn.pack(side="right", padx=(10, 4))
        ctk.CTkLabel(options, text="Salvar em", font=font(12), text_color=MUTED).pack(side="right")
        self._render_folder()

        # Aviso (aparece só quando falta algo)
        self.notice = ctk.CTkFrame(root, fg_color=WARN_BG, corner_radius=12)
        self.notice.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.notice_label = ctk.CTkLabel(self.notice, text="", font=font(12), text_color=WARN_TEXT, anchor="w", justify="left")
        self.notice_label.pack(side="left", padx=(16, 8), pady=10)
        ctk.CTkButton(
            self.notice, text="Configurar", width=96, height=30, corner_radius=8, font=font(12, bold=True),
            fg_color="transparent", hover_color=BORDER, text_color=WARN_TEXT, border_width=1, border_color=WARN_TEXT,
            command=self.open_settings,
        ).pack(side="right", padx=12)

        # Lista de downloads
        queue_area = ctk.CTkFrame(root, fg_color="transparent")
        queue_area.grid(row=3, column=0, sticky="nsew", pady=(20, 0))
        queue_area.grid_columnconfigure(0, weight=1)
        queue_area.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(queue_area, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(head, text="Downloads", font=font(15, bold=True), text_color=TEXT).pack(side="left")
        self.counter = ctk.CTkLabel(head, text="", font=font(12), text_color=MUTED)
        self.counter.pack(side="left", padx=(10, 0))
        self.clear_btn = ctk.CTkButton(
            head, text="Limpar concluídos", height=30, corner_radius=8, font=font(12), fg_color="transparent",
            hover_color=FIELD, text_color=MUTED, command=self._clear_finished,
        )
        self.clear_btn.pack(side="right")

        self.list = ctk.CTkScrollableFrame(
            queue_area, fg_color="transparent", scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED,
        )
        self.list.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.list.grid_columnconfigure(0, weight=1)

        self.empty = ctk.CTkFrame(queue_area, fg_color="transparent")
        ctk.CTkLabel(self.empty, text=I_DOWNLOAD, font=ctk.CTkFont(family=ICONS, size=34), text_color=BORDER).pack()
        ctk.CTkLabel(self.empty, text="Nenhum download ainda", font=font(14, bold=True), text_color=TEXT).pack(pady=(12, 0))
        ctk.CTkLabel(self.empty, text="Cole um link acima e clique em Baixar.", font=font(12), text_color=MUTED).pack()

        # Rodapé
        ctk.CTkLabel(
            root, text="Baixe apenas conteúdo seu ou com autorização. Conteúdo protegido por DRM não é suportado.",
            font=font(11), text_color=MUTED, anchor="w",
        ).grid(row=4, column=0, sticky="ew", pady=(10, 0))

    # ── opções ──────────────────────────────────────────────────────────────
    def _sync_option_menus(self):
        s = self.settings
        if s.kind not in ("Vídeo", "Áudio"):
            s.kind = "Vídeo"
        audio = s.kind == "Áudio"
        formats, qualities = (dl.AUDIO_FORMATS, dl.AUDIO_QUALITIES) if audio else (dl.VIDEO_FORMATS, dl.VIDEO_QUALITIES)
        current_format = s.audio_format if audio else s.video_format
        current_quality = s.audio_quality if audio else s.video_quality
        self.kind.set(s.kind)
        self.format_menu.configure(values=list(formats))
        self.format_menu.set(current_format if current_format in formats else formats[0])
        self.quality_menu.configure(values=list(qualities))
        self.quality_menu.set(current_quality if current_quality in qualities else qualities[0])

    def _on_kind(self, value: str):
        self.settings.kind = value
        self._sync_option_menus()
        self.settings.save()

    def _on_format(self, value: str):
        if self.settings.kind == "Áudio":
            self.settings.audio_format = value
        else:
            self.settings.video_format = value
        self.settings.save()

    def _on_quality(self, value: str):
        if self.settings.kind == "Áudio":
            self.settings.audio_quality = value
        else:
            self.settings.video_quality = value
        self.settings.save()

    def _current_choice(self) -> dl.Choice:
        return dl.Choice(self.settings.kind, self.format_menu.get(), self.quality_menu.get())

    def _render_folder(self):
        path = Path(self.settings.output_dir)
        text = str(path)
        if len(text) > 34:
            text = "…" + os.sep + os.sep.join(path.parts[-2:])[-32:]
        self.folder_btn.configure(text=text)

    def _choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.settings.output_dir or str(Path.home()))
        if selected:
            self.settings.output_dir = str(Path(selected))
            self.settings.save()
            self._render_folder()

    def open_folder(self, folder: Path):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)  # noqa: S606
        except OSError as exc:
            self._show_hint(f"Não foi possível abrir a pasta: {exc}", error=True)

    # ── tema e configurações ────────────────────────────────────────────────
    def set_theme(self, mode: str):
        self.settings.theme = mode
        self.settings.save()
        ctk.set_appearance_mode(mode)
        self._render_theme_button()

    def _toggle_theme(self):
        self.set_theme("light" if ctk.get_appearance_mode() == "Dark" else "dark")

    def _render_theme_button(self):
        self.theme_btn.configure(text=I_SUN if ctk.get_appearance_mode() == "Dark" else I_MOON)

    def open_settings(self):
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            self.settings_dialog.focus()
            return
        self.settings_dialog = SettingsDialog(self)

    def refresh_notice(self):
        if dl.yt_dlp is None:
            text = "O componente yt-dlp não está instalado. Rode: pip install -r requirements.txt"
        elif not dl.find_ffmpeg(self.settings.ffmpeg_path):
            text = "FFmpeg não encontrado: áudio (MP3/M4A) e as melhores qualidades de vídeo ficam indisponíveis."
        else:
            self.notice.grid_remove()
            return
        self.notice_label.configure(text=text)
        self.notice.grid()

    # ── link ────────────────────────────────────────────────────────────────
    def _paste(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            return
        self.entry.delete(0, "end")
        self.entry.insert(0, text.splitlines()[0] if text else "")
        self.entry.focus()
        self._on_link_change()

    def _on_link_change(self, _event=None):
        parsed = parse_link(self.entry.get())
        if parsed:
            platform = parsed[1]
            self.badge.configure(text="●", font=font(17), text_color=platform.color)
            self._show_hint(f"Link do {platform.name} reconhecido.")
        else:
            self.badge.configure(text=I_LINK, font=ctk.CTkFont(family=ICONS, size=15), text_color=MUTED)
            self._show_hint(self._hint_default)

    def _show_hint(self, text: str, error: bool = False):
        self.hint.configure(text=text, text_color=DANGER if error else MUTED)

    # ── fila ────────────────────────────────────────────────────────────────
    def _start(self):
        if dl.yt_dlp is None:
            self._show_hint("O componente yt-dlp não está instalado.", error=True)
            return
        text = self.entry.get().strip()
        if not text:
            self._show_hint("Cole um link para começar.", error=True)
            self.entry.focus()
            return
        parsed = parse_link(text)
        if not parsed:
            self._show_hint("Link não reconhecido. Use um endereço do YouTube, X (Twitter) ou Instagram.", error=True)
            return
        url, platform = parsed
        choice = self._current_choice()
        if choice.is_audio and not dl.find_ffmpeg(self.settings.ffmpeg_path):
            self._show_hint("Para baixar áudio é preciso configurar o FFmpeg (ícone de engrenagem).", error=True)
            return
        destination = Path(self.settings.output_dir).expanduser()
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._show_hint(f"Não foi possível usar a pasta de destino: {exc}", error=True)
            return

        job = Job(url, platform, choice, destination)
        card = JobCard(self.list, self, job)
        card.pack(fill="x", pady=(0, 10), padx=(0, 6))
        self.cards[job.id] = card
        self.jobs.put(job)
        self.entry.delete(0, "end")
        self._on_link_change()
        self.refresh_queue_header()

    def requeue(self, card: JobCard):
        old = card.job
        self.cards.pop(old.id, None)
        card.job = Job(old.url, old.platform, old.choice, old.destination)  # novo id e novo sinal de cancelamento
        self.cards[card.job.id] = card
        card.set_state(QUEUED)
        self.jobs.put(card.job)

    def remove_card(self, card: JobCard):
        self.cards.pop(card.job.id, None)
        card.destroy()
        self.refresh_queue_header()

    def _clear_finished(self):
        for card in [c for c in self.cards.values() if c.state in (DONE, ERROR, CANCELLED)]:
            self.remove_card(card)

    def refresh_queue_header(self):
        if not hasattr(self, "counter"):
            return
        active = sum(1 for c in self.cards.values() if c.state in (QUEUED, RUNNING))
        finished = sum(1 for c in self.cards.values() if c.state in (DONE, ERROR, CANCELLED))
        self.counter.configure(text=f"{active} em andamento" if active else "")
        if finished:
            self.clear_btn.pack(side="right")
        else:
            self.clear_btn.pack_forget()
        if self.cards:
            self.empty.place_forget()
            self.list.grid()
        else:
            self.list.grid_remove()  # esconde também a barra de rolagem vazia
            self.empty.place(relx=0.5, rely=0.5, anchor="center")

    # ── thread de trabalho ──────────────────────────────────────────────────
    def _worker(self):
        """Processa um download por vez. Nunca toca em widgets: só publica eventos."""
        while True:
            job = self.jobs.get()
            if job.cancel.is_set():
                continue  # cancelado enquanto esperava na fila
            self.events.put(("start", job.id))
            cookies = self.settings.cookies_browser
            try:
                path = dl.run_download(
                    job.url, job.platform, job.choice, job.destination, dl.find_ffmpeg(self.settings.ffmpeg_path),
                    cookies, job.cancel,
                    on_info=lambda info, j=job: self._on_info(j, info),
                    on_progress=lambda fraction, text, j=job: self.events.put(("progress", j.id, fraction, text)),
                )
                self.events.put(("done", job.id, path))
            except BaseException as exc:  # inclui DownloadCancelled
                if job.cancel.is_set():
                    self.events.put(("cancelled", job.id))
                else:
                    message = dl.friendly_error(exc, job.platform, bool(cookies))
                    if job.platform.key == "youtube" and not dl.js_runtimes():
                        message += " (Instalar o Node.js ou o Deno melhora a compatibilidade com o YouTube.)"
                    self.events.put(("error", job.id, message))

    def _on_info(self, job: Job, info: dict):
        self.events.put(("info", job.id, info))
        if info.get("thumbnail"):
            threading.Thread(target=self._load_thumbnail, args=(job.id, info["thumbnail"]), daemon=True).start()

    def _load_thumbnail(self, job_id: int, url: str):
        image = dl.fetch_thumbnail(url, (THUMB[0] * 2, THUMB[1] * 2))
        if image is not None:
            self.events.put(("thumb", job_id, rounded(image, 16)))

    def _poll_events(self):
        try:
            while True:
                kind, job_id, *payload = self.events.get_nowait()
                card = self.cards.get(job_id)
                if card is None or not card.winfo_exists():
                    continue
                if kind == "start":
                    card.set_state(RUNNING)
                elif kind == "info":
                    card.set_info(payload[0])
                elif kind == "thumb":
                    card.set_thumbnail(payload[0])
                elif kind == "progress":
                    card.set_progress(payload[0], payload[1])
                elif kind == "done":
                    card.filepath = payload[0]
                    card.set_state(DONE)
                elif kind == "error":
                    card.set_state(ERROR, payload[0])
                elif kind == "cancelled":
                    card.set_state(CANCELLED, "Cancelado")
        except queue.Empty:
            pass
        self.after(80, self._poll_events)

    def _on_close(self):
        active = [c for c in self.cards.values() if c.state in (QUEUED, RUNNING)]
        if active and not messagebox.askyesno(
            "Downloads em andamento", "Há downloads em andamento. Deseja cancelar e sair?", parent=self,
        ):
            return
        for card in active:
            card.job.cancel.set()
        self.destroy()


def main():
    try:  # faz o Windows agrupar a janela sob o ícone do app na barra de tarefas
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VideoLocal.App")
    except Exception:
        pass
    App().mainloop()
