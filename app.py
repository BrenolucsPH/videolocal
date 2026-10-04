from __future__ import annotations

import os
import queue
import re
import shutil
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

APP_NAME = "VideoLocal"
BG = "#f5f7fb"
CARD = "#ffffff"
INK = "#17233c"
MUTED = "#68758d"
BLUE = "#315efb"
GREEN = "#16845b"

class VideoLocalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VideoLocal — downloads com autorização")
        self.geometry("760x670")
        self.minsize(680, 610)
        self.configure(bg=BG)
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_requested = threading.Event()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "VideoLocal"))
        self.format_choice = tk.StringVar(value="MP4 • 1080p (quando disponível)")
        self.url = tk.StringVar()
        self.ffmpeg_path = self._load_ffmpeg_path()
        self.ffmpeg_status = tk.StringVar(value=self._ffmpeg_status_text())
        self.status = tk.StringVar(value="Pronto para começar")
        self.progress_value = tk.DoubleVar(value=0)
        self._style()
        self._build()
        self.after(120, self._poll_events)
        if yt_dlp is None:
            self.after(300, lambda: messagebox.showerror(
                "Configuração necessária",
                "O yt-dlp não está instalado. Feche o aplicativo e abra iniciar.bat para configurar a dependência oficial do projeto."
            ))

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", padding=9, fieldbackground=CARD, foreground=INK)
        style.configure("Horizontal.TProgressbar", troughcolor="#e8edf6", background=BLUE, bordercolor="#e8edf6", lightcolor=BLUE, darkcolor=BLUE)

    def _build(self):
        outer = tk.Frame(self, bg=BG, padx=34, pady=28)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="VideoLocal", bg=BG, fg=INK, font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(outer, text="Seus vídeos autorizados, no formato que você precisa.", bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w", pady=(3, 20))

        card = tk.Frame(outer, bg=CARD, padx=24, pady=22, highlightthickness=1, highlightbackground="#e6eaf2")
        card.pack(fill="x")
        self._label(card, "LINK DO YOUTUBE")
        entry = tk.Entry(card, textvariable=self.url, font=("Segoe UI", 11), relief="flat", bg="#f7f9fc", fg=INK, insertbackground=INK)
        entry.pack(fill="x", ipady=11, pady=(7, 18))
        entry.configure(highlightthickness=1, highlightbackground="#dfe5ef", highlightcolor=BLUE)

        self._label(card, "FORMATO E QUALIDADE")
        formats = ["MP4 • 1080p (quando disponível)", "MP4 • 720p (quando disponível)", "MP3 • áudio", "WEBM • melhor qualidade disponível"]
        ttk.Combobox(card, textvariable=self.format_choice, values=formats, state="readonly", font=("Segoe UI", 10)).pack(fill="x", pady=(7, 17))

        ffmpeg_row = tk.Frame(card, bg=CARD)
        ffmpeg_row.pack(fill="x", pady=(0, 17))
        tk.Label(ffmpeg_row, textvariable=self.ffmpeg_status, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, anchor="w")
        tk.Button(ffmpeg_row, text="Localizar FFmpeg", command=self._choose_ffmpeg, font=("Segoe UI", 9, "bold"), bg="#edf1ff", fg=BLUE, relief="flat", padx=12, pady=8, cursor="hand2").pack(side="right")

        self._label(card, "SALVAR EM")
        path_row = tk.Frame(card, bg=CARD)
        path_row.pack(fill="x", pady=(7, 0))
        path_entry = tk.Entry(path_row, textvariable=self.output_dir, font=("Segoe UI", 10), relief="flat", bg="#f7f9fc", fg=INK)
        path_entry.pack(side="left", fill="x", expand=True, ipady=10)
        path_entry.configure(highlightthickness=1, highlightbackground="#dfe5ef", highlightcolor=BLUE)
        tk.Button(path_row, text="Escolher pasta", command=self._choose_folder, font=("Segoe UI", 9, "bold"), bg="#edf1ff", fg=BLUE, relief="flat", padx=14, pady=9, cursor="hand2").pack(side="left", padx=(10, 0))

        notice = tk.Frame(outer, bg="#fff8e9", padx=15, pady=12, highlightthickness=1, highlightbackground="#f4e4bf")
        notice.pack(fill="x", pady=(15, 0))
        tk.Label(notice, text="Uso responsável", bg="#fff8e9", fg="#76551b", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(notice, text="Baixe somente vídeos que você enviou, tem autorização para baixar ou cujo download seja permitido pelo serviço e pela lei. Não use para conteúdo protegido por DRM.", wraplength=650, justify="left", bg="#fff8e9", fg="#76551b", font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

        action = tk.Frame(outer, bg=BG)
        action.pack(fill="x", pady=(18, 12))
        self.download_btn = tk.Button(action, text="Baixar vídeo", command=self._start, font=("Segoe UI", 11, "bold"), bg=BLUE, fg="white", activebackground="#244de0", activeforeground="white", relief="flat", padx=24, pady=12, cursor="hand2")
        self.download_btn.pack(side="left")
        self.cancel_btn = tk.Button(action, text="Cancelar", command=self._cancel, state="disabled", font=("Segoe UI", 10), bg="#edf0f5", fg=INK, relief="flat", padx=18, pady=12, cursor="hand2")
        self.cancel_btn.pack(side="left", padx=10)

        tk.Label(outer, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 7))
        ttk.Progressbar(outer, variable=self.progress_value, maximum=100, mode="determinate").pack(fill="x")
        footer = "Usa yt-dlp do PyPI e um runtime JavaScript, como Deno; FFmpeg é necessário para MP3."
        tk.Label(outer, text=footer, bg=BG, fg="#8791a3", font=("Segoe UI", 8), wraplength=690, justify="left").pack(anchor="w", pady=(16, 0))

    @staticmethod
    def _label(parent, text):
        tk.Label(parent, text=text, bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")

    def _choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.home()))
        if selected:
            self.output_dir.set(selected)

    @staticmethod
    def _ffmpeg_config_file() -> Path:
        return Path(__file__).resolve().parent / "ffmpeg_path.txt"

    def _local_ffmpeg_path(self) -> str:
        project_dir = Path(__file__).resolve().parent
        for relative_path in (
            Path("bin") / "ffmpeg.exe",
            Path("ffmpeg.exe"),
            Path("ffmpeg") / "bin" / "ffmpeg.exe",
            Path("tools") / "ffmpeg" / "bin" / "ffmpeg.exe",
        ):
            candidate = project_dir / relative_path
            if candidate.is_file():
                return str(candidate)
        return ""

    def _save_ffmpeg_path(self, ffmpeg_path: str):
        project_dir = Path(__file__).resolve().parent
        selected_path = Path(ffmpeg_path).resolve()
        try:
            saved_path = selected_path.relative_to(project_dir).as_posix()
        except ValueError:
            saved_path = str(selected_path)
        self._ffmpeg_config_file().write_text(saved_path, encoding="utf-8")

    def _load_ffmpeg_path(self) -> str:
        project_dir = Path(__file__).resolve().parent
        try:
            saved_path = self._ffmpeg_config_file().read_text(encoding="utf-8").strip()
            if saved_path:
                configured_path = Path(saved_path)
                if not configured_path.is_absolute():
                    configured_path = project_dir / configured_path
                if configured_path.is_file():
                    return str(configured_path)
        except OSError:
            pass

        local_path = self._local_ffmpeg_path()
        if local_path:
            try:
                self._save_ffmpeg_path(local_path)
            except OSError:
                pass
            return local_path
        return shutil.which("ffmpeg") or ""

    def _find_ffmpeg(self) -> str:
        if self.ffmpeg_path and Path(self.ffmpeg_path).is_file():
            return self.ffmpeg_path
        local_path = self._local_ffmpeg_path()
        if local_path:
            return local_path
        return shutil.which("ffmpeg") or ""

    def _ffmpeg_status_text(self) -> str:
        return "FFmpeg pronto" if getattr(self, "ffmpeg_path", "") or shutil.which("ffmpeg") else "FFmpeg não configurado (necessário para MP3)"

    def _choose_ffmpeg(self):
        selected = filedialog.askopenfilename(
            title="Selecione ffmpeg.exe",
            filetypes=[("Executável FFmpeg", "ffmpeg.exe"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return
        if Path(selected).name.lower() != "ffmpeg.exe":
            messagebox.showwarning("Arquivo inválido", "Selecione o arquivo ffmpeg.exe que veio dentro do pacote FFmpeg.")
            return
        self.ffmpeg_path = selected
        try:
            self._save_ffmpeg_path(selected)
        except OSError as exc:
            messagebox.showerror("Não foi possível salvar", f"Não consegui guardar o caminho do FFmpeg:\n{exc}")
            self.ffmpeg_path = ""
            return
        self.ffmpeg_status.set("FFmpeg pronto para MP3")

    @staticmethod
    def _valid_youtube_url(value: str) -> bool:
        try:
            parsed = urlparse(value.strip())
            host = (parsed.hostname or "").lower().rstrip(".")
            return parsed.scheme == "https" and (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")) and bool(parsed.path.strip("/"))
        except ValueError:
            return False

    def _start(self):
        if yt_dlp is None:
            messagebox.showerror("Dependência ausente", "Abra iniciar.bat para instalar a dependência necessária.")
            return
        link = self.url.get().strip()
        if not self._valid_youtube_url(link):
            messagebox.showwarning("Confira o link", "Cole um endereço HTTPS válido do YouTube ou youtu.be.")
            return
        destination = Path(self.output_dir.get()).expanduser()
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Pasta indisponível", f"Não foi possível usar essa pasta:\n{exc}")
            return

        choice = self.format_choice.get()
        if not any(shutil.which(runtime) for runtime in ("deno", "node", "bun", "qjs")):
            messagebox.showerror("Runtime JavaScript necessário", "O yt-dlp precisa de um runtime JavaScript para suporte completo ao YouTube. Instale Deno pelo site oficial e abra o aplicativo novamente.")
            return
        ffmpeg_executable = self._find_ffmpeg()
        if choice.startswith("MP3") and not ffmpeg_executable:
            if messagebox.askyesno(
                "FFmpeg necessário para MP3",
                "Baixe o arquivo ffmpeg-master-latest-win64-gpl.zip, extraia o ZIP e use o botão Localizar FFmpeg para escolher bin\\ffmpeg.exe. Não é necessário alterar o PATH do Windows.\n\nQuer abrir a página oficial de releases do projeto yt-dlp?",
            ):
                webbrowser.open("https://github.com/yt-dlp/FFmpeg-Builds/releases")
            return
        self.cancel_requested.clear()
        self.progress_value.set(0)
        self.status.set("Conectando…")
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.worker = threading.Thread(target=self._download, args=(link, destination, choice), daemon=True)
        self.worker.start()

    def _download(self, link: str, destination: Path, choice: str):
        def hook(data):
            if self.cancel_requested.is_set():
                raise yt_dlp.utils.DownloadCancelled("Cancelado pelo usuário")
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                percent = (data.get("downloaded_bytes", 0) / total * 100) if total else 0
                self.events.put(("progress", min(percent, 99), "Baixando…"))
            elif data.get("status") == "finished":
                self.events.put(("progress", 100, "Finalizando arquivo…"))

        opts = {
            "outtmpl": str(destination / "%(title).160B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
            "progress_hooks": [hook],
            "ignoreerrors": False,
            "retries": 3,
            "socket_timeout": 20,
        }
        if self._find_ffmpeg():
            opts["ffmpeg_location"] = str(Path(self._find_ffmpeg()).parent)
        if choice.startswith("MP4"):
            quality = "1080" if "1080p" in choice else "720"
            opts.update({"format": f"bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/b[height<={quality}][ext=mp4]/bv*[height<={quality}]+ba/b[height<={quality}]", "merge_output_format": "mp4"})
        elif choice.startswith("MP3"):
            opts.update({"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]})
        else:
            opts.update({"format": "bv*[ext=webm]+ba[ext=webm]/b[ext=webm]/bv*+ba/best", "merge_output_format": "webm"})
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([link])
            self.events.put(("done", "Download concluído", "Arquivo salvo na pasta escolhida."))
        except Exception as exc:
            if self.cancel_requested.is_set():
                self.events.put(("done", "Download cancelado", "A solicitação de cancelamento foi concluída."))
            else:
                error = re.sub(r"\x1b\[[0-9;]*m", "", str(exc))[-900:]
                self.events.put(("error", "Não foi possível concluir", error or "Verifique o link e tente novamente."))

    def _cancel(self):
        self.cancel_requested.set()
        self.cancel_btn.configure(state="disabled")
        self.status.set("Cancelando…")

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.progress_value.set(event[1])
                    self.status.set(event[2])
                elif kind == "done":
                    self._reset(event[1])
                    self.progress_value.set(100 if event[1] == "Download concluído" else 0)
                    if event[1] == "Download concluído":
                        messagebox.showinfo(event[1], event[2])
                    else:
                        self.status.set(event[1])
                elif kind == "error":
                    self._reset(event[1])
                    messagebox.showerror(event[1], event[2])
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def _reset(self, status):
        self.status.set(status)
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.worker = None

if __name__ == "__main__":
    VideoLocalApp().mainloop()



