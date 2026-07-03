"""Графический интерфейс MediaGrab (Tkinter).

Раскладка повторяет эскиз:
  * слева — панель выбора сервиса;
  * сверху — строка для ссылки, кнопка загрузки «➜» и кнопка «…»
    выбора папки (папка запоминается между запусками);
  * под строкой — переключатель mp3/mp4, активный формат подсвечен
    зелёным; по клику выезжает панелька выбора качества;
  * ниже — история загрузок и статус текущих: завершённые с галочкой.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import Config
from .engine import MP3_BITRATES, MP4_QUALITIES, DownloadManager
from . import services

# --- палитра (светлая, зелёный акцент) ---------------------------------
BG = "#f5f9f5"          # фон окна
PANEL = "#e8f2e8"       # боковая панель
CARD = "#ffffff"        # поля ввода / список
ACCENT = "#2e7d32"      # основной зелёный
ACCENT_DARK = "#1b5e20"
ACCENT_SOFT = "#c8e6c9"
TEXT = "#1c231c"
MUTED = "#5f6f5f"
ERROR = "#c62828"

AUTO_ID = "__auto__"

STATUS_QUEUED = "⏳ в очереди"
STATUS_PROCESSING = "⚙ обработка…"
STATUS_DONE = "✓ загружено"
STATUS_ERROR = "✗ ошибка"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaGrab — загрузчик mp3/mp4")
        self.geometry("1020x600")
        self.minsize(860, 480)
        self.configure(bg=BG)

        self.config_store = Config()
        self.manager = DownloadManager()
        self.selected_service = AUTO_ID
        self.current_format = self.config_store.format
        self.quality_panel_visible = False
        self.tasks = {}          # task_id -> {"item": id строки, "entry": dict истории}
        self.service_buttons = {}
        self.format_buttons = {}
        self.quality_buttons = {}

        self._build_statusbar()
        self._build_sidebar()
        self._build_main_area()
        self._load_history()
        self._check_dependencies()
        self.after(150, self._poll_events)

    # ------------------------------------------------------------------
    # построение интерфейса
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg=PANEL, width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="Сервис", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(16, 6))

        self._add_service_button(sidebar, AUTO_ID, "Авто (по ссылке)")
        for plugin in services.all_plugins():
            self._add_service_button(sidebar, plugin.id, plugin.name)

        tk.Label(sidebar, text="+ свои сервисы:\nsee docs/ADDING_SERVICES.md",
                 bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8),
                 justify="left", anchor="w").pack(
            side="bottom", fill="x", padx=14, pady=12)

    def _add_service_button(self, parent, service_id, label):
        btn = tk.Label(parent, text=label, bg=PANEL, fg=TEXT, anchor="w",
                       padx=14, pady=7, cursor="hand2",
                       font=("TkDefaultFont", 10))
        btn.pack(fill="x", padx=8, pady=2)
        btn.bind("<Button-1>",
                 lambda _e, sid=service_id: self._select_service(sid))
        self.service_buttons[service_id] = btn
        if service_id == self.selected_service:
            self._style_service_buttons()

    def _build_main_area(self):
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        # --- строка ссылки -------------------------------------------
        row = tk.Frame(main, bg=BG)
        row.pack(fill="x")

        self.url_var = tk.StringVar()
        entry = tk.Entry(row, textvariable=self.url_var,
                         font=("TkDefaultFont", 12), bg=CARD, fg=TEXT,
                         relief="solid", bd=1,
                         highlightthickness=1, highlightcolor=ACCENT,
                         highlightbackground="#b8ccb8")
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        entry.bind("<Return>", lambda _e: self._start_download())
        entry.insert(0, "")
        self.url_entry = entry
        self._set_placeholder()

        self.download_btn = tk.Button(
            row, text="➜", font=("TkDefaultFont", 14, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_DARK,
            activeforeground="white", relief="flat", cursor="hand2",
            width=4, command=self._start_download)
        self.download_btn.pack(side="left", padx=(0, 8))

        folder_btn = tk.Button(
            row, text="…", font=("TkDefaultFont", 12, "bold"),
            bg=CARD, fg=TEXT, relief="solid", bd=1, cursor="hand2",
            width=3, command=self._choose_folder)
        folder_btn.pack(side="left")

        # --- переключатель формата -----------------------------------
        fmt_row = tk.Frame(main, bg=BG)
        fmt_row.pack(fill="x", pady=(10, 0))
        tk.Frame(fmt_row, bg=BG).pack(side="left", expand=True)  # прижать вправо
        for fmt in ("mp3", "mp4"):
            btn = tk.Button(
                fmt_row, text=fmt, font=("TkDefaultFont", 11, "bold"),
                relief="flat", bd=0, cursor="hand2", width=7, pady=4,
                command=lambda f=fmt: self._select_format(f))
            btn.pack(side="left", padx=4)
            self.format_buttons[fmt] = btn

        # --- выезжающая панель качества ------------------------------
        # слот фиксирует место панели сразу под кнопками формата,
        # чтобы pack() при показе не отправлял её в конец окна
        self.quality_slot = tk.Frame(main, bg=BG)
        self.quality_slot.pack(fill="x")
        self.quality_panel = tk.Frame(self.quality_slot, bg=ACCENT_SOFT)
        self.quality_inner = tk.Frame(self.quality_panel, bg=ACCENT_SOFT)
        self.quality_inner.pack(side="right", padx=6, pady=5)
        tk.Label(self.quality_panel, text="Качество:", bg=ACCENT_SOFT,
                 fg=ACCENT_DARK, font=("TkDefaultFont", 9, "bold")).pack(
            side="right", padx=(0, 4))
        self._style_format_buttons()

        # --- история -------------------------------------------------
        tk.Label(main, text="История и статус загрузок", bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(14, 4))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, fieldbackground=CARD,
                        foreground=TEXT, rowheight=26, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL,
                        foreground=MUTED, relief="flat")
        style.map("Treeview", background=[("selected", ACCENT_SOFT)],
                  foreground=[("selected", TEXT)])

        table_frame = tk.Frame(main, bg=BG)
        table_frame.pack(fill="both", expand=True)
        columns = ("url", "service", "format", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show="headings", selectmode="browse")
        self.tree.heading("url", text="Ссылка")
        self.tree.heading("service", text="Сервис")
        self.tree.heading("format", text="Формат")
        self.tree.heading("status", text="Статус")
        self.tree.column("url", width=430, anchor="w")
        self.tree.column("service", width=120, anchor="center")
        self.tree.column("format", width=70, anchor="center")
        self.tree.column("status", width=150, anchor="center")
        scroll = ttk.Scrollbar(table_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        self.tree.tag_configure("done", foreground=ACCENT_DARK)
        self.tree.tag_configure("error", foreground=ERROR)
        self.tree.tag_configure("active", foreground=TEXT)
        self.tree.bind("<Double-1>", self._on_history_doubleclick)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar()
        tk.Label(bar, textvariable=self.status_var, bg=PANEL, fg=MUTED,
                 anchor="w", padx=12, pady=5,
                 font=("TkDefaultFont", 9)).pack(side="left", fill="x")
        self._update_statusbar()

    def _update_statusbar(self, extra: str = ""):
        text = f"Папка загрузки: {self.config_store.download_dir}"
        if extra:
            text += f"   •   {extra}"
        self.status_var.set(text)

    # ------------------------------------------------------------------
    # placeholder строки ввода
    # ------------------------------------------------------------------
    PLACEHOLDER = "Вставьте ссылку на видео или музыку…"

    def _set_placeholder(self):
        if not self.url_var.get():
            self.url_entry.configure(fg=MUTED)
            self.url_var.set(self.PLACEHOLDER)
        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        self.url_entry.bind("<FocusOut>", self._restore_placeholder)

    def _clear_placeholder(self, _event=None):
        if self.url_var.get() == self.PLACEHOLDER:
            self.url_var.set("")
            self.url_entry.configure(fg=TEXT)

    def _restore_placeholder(self, _event=None):
        if not self.url_var.get().strip():
            self.url_entry.configure(fg=MUTED)
            self.url_var.set(self.PLACEHOLDER)

    def _current_url(self) -> str:
        value = self.url_var.get().strip()
        return "" if value == self.PLACEHOLDER else value

    # ------------------------------------------------------------------
    # выбор сервиса / формата / качества / папки
    # ------------------------------------------------------------------
    def _select_service(self, service_id):
        self.selected_service = service_id
        self._style_service_buttons()

    def _style_service_buttons(self):
        for sid, btn in self.service_buttons.items():
            if sid == self.selected_service:
                btn.configure(bg=ACCENT, fg="white",
                              font=("TkDefaultFont", 10, "bold"))
            else:
                btn.configure(bg=PANEL, fg=TEXT,
                              font=("TkDefaultFont", 10))

    def _select_format(self, fmt):
        if fmt == self.current_format:
            # повторный клик по активному формату — показать/спрятать качество
            self._toggle_quality_panel()
        else:
            self.current_format = fmt
            self.config_store.format = fmt
            if not self.quality_panel_visible:
                self._toggle_quality_panel(show=True)
        self._style_format_buttons()

    def _style_format_buttons(self):
        for fmt, btn in self.format_buttons.items():
            if fmt == self.current_format:
                btn.configure(bg=ACCENT, fg="white",
                              activebackground=ACCENT_DARK,
                              activeforeground="white")
            else:
                btn.configure(bg="#d7e3d7", fg=TEXT,
                              activebackground=ACCENT_SOFT,
                              activeforeground=TEXT)
        self._rebuild_quality_buttons()

    def _toggle_quality_panel(self, show=None):
        target = (not self.quality_panel_visible) if show is None else show
        if target and not self.quality_panel_visible:
            self.quality_panel.pack(fill="x", pady=(4, 0))
            self.quality_panel_visible = True
        elif not target and self.quality_panel_visible:
            self.quality_panel.pack_forget()
            self.quality_panel_visible = False

    def _rebuild_quality_buttons(self):
        for btn in self.quality_buttons.values():
            btn.destroy()
        self.quality_buttons.clear()
        options = (MP3_BITRATES if self.current_format == "mp3"
                   else MP4_QUALITIES)
        current = self.config_store.quality_for(self.current_format)
        for value in options:
            label = f"{value} кбит/с" if self.current_format == "mp3" else value
            btn = tk.Button(
                self.quality_inner, text=label,
                font=("TkDefaultFont", 9), relief="flat", bd=0,
                cursor="hand2", padx=8, pady=2,
                bg=ACCENT if value == current else ACCENT_SOFT,
                fg="white" if value == current else ACCENT_DARK,
                command=lambda v=value: self._select_quality(v))
            btn.pack(side="left", padx=2)
            self.quality_buttons[value] = btn

    def _select_quality(self, value):
        self.config_store.set_quality(self.current_format, value)
        self._rebuild_quality_buttons()

    def _choose_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.config_store.download_dir,
            title="Куда сохранять загрузки")
        if folder:
            self.config_store.download_dir = folder
            self._update_statusbar()

    # ------------------------------------------------------------------
    # загрузка
    # ------------------------------------------------------------------
    def _start_download(self):
        url = self._current_url()
        if not url:
            messagebox.showinfo("MediaGrab", "Вставьте ссылку в строку сверху.")
            return
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showwarning(
                "MediaGrab", "Похоже, это не ссылка. Ссылка должна "
                "начинаться с http:// или https://")
            return

        if self.selected_service == AUTO_ID:
            plugin = services.detect(url)
        else:
            plugin = services.by_id(self.selected_service)
            if plugin and not plugin.matches(url):
                detected = services.detect(url)
                if detected:
                    plugin = detected  # ссылка с другого сервиса — доверяем ей

        fmt = self.current_format
        note = ""
        if plugin and fmt not in plugin.supported_formats:
            fmt = plugin.supported_formats[0]
            note = f"{plugin.name}: доступен только {fmt}"

        quality = self.config_store.quality_for(fmt)
        service_name = plugin.name if plugin else "Авто (yt-dlp)"

        entry = self.config_store.add_history(url, service_name, fmt,
                                              "queued")
        item = self.tree.insert(
            "", 0, values=(url, service_name, fmt, STATUS_QUEUED),
            tags=("active",))
        task_id = self.manager.submit(url, plugin, fmt, quality,
                                      self.config_store.download_dir)
        self.tasks[task_id] = {"item": item, "entry": entry}

        self.url_var.set("")
        self.url_entry.focus_set()
        self._update_statusbar(note or f"Загрузка добавлена: {fmt}, {quality}")

    def _poll_events(self):
        while not self.manager.events.empty():
            task_id, event, payload = self.manager.events.get_nowait()
            task = self.tasks.get(task_id)
            if not task:
                continue
            item, entry = task["item"], task["entry"]
            if event == "start":
                self.tree.set(item, "status", "0%")
            elif event == "progress":
                self.tree.set(item, "status", f"{payload:.0f}%")
            elif event == "processing":
                self.tree.set(item, "status", STATUS_PROCESSING)
            elif event == "done":
                self.tree.set(item, "status", STATUS_DONE)
                self.tree.item(item, tags=("done",))
                self.config_store.update_history(entry, "done", payload)
                self._update_statusbar(f"Готово: {payload or entry['url']}")
                del self.tasks[task_id]
            elif event == "error":
                self.tree.set(item, "status", STATUS_ERROR)
                self.tree.item(item, tags=("error",))
                self.config_store.update_history(entry, "error")
                self._update_statusbar(f"Ошибка: {payload}")
                del self.tasks[task_id]
        self.after(150, self._poll_events)

    # ------------------------------------------------------------------
    # история
    # ------------------------------------------------------------------
    def _load_history(self):
        for record in self.config_store.history:
            status = record.get("status")
            if status == "done":
                text, tag = STATUS_DONE, "done"
            elif status == "error":
                text, tag = STATUS_ERROR, "error"
            else:  # незавершённые с прошлого запуска
                text, tag = STATUS_ERROR, "error"
            self.tree.insert(
                "", "end",
                values=(record.get("url", ""), record.get("service", ""),
                        record.get("format", ""), text),
                tags=(tag,))

    def _on_history_doubleclick(self, _event):
        selection = self.tree.selection()
        if selection:
            url = self.tree.set(selection[0], "url")
            self._clear_placeholder()
            self.url_var.set(url)
            self.url_entry.configure(fg=TEXT)
            self.url_entry.focus_set()

    # ------------------------------------------------------------------
    def _check_dependencies(self):
        problems = []
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            problems.append("не установлен yt-dlp "
                            "(pip install -r requirements.txt)")
        import shutil
        if not shutil.which("ffmpeg"):
            problems.append("не найден ffmpeg — mp3 и склейка видео "
                            "работать не будут (см. README)")
        if problems:
            self._update_statusbar("⚠ " + "; ".join(problems))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
