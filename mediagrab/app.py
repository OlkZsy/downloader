"""Графический интерфейс MediaGrab (Tkinter).

Раскладка повторяет эскиз:
  * слева — панель выбора сервиса;
  * сверху — строка для ссылки, кнопка загрузки «➜» и кнопка «…»
    выбора папки (папка запоминается между запусками);
  * под строкой — переключатель mp3/mp4, активный формат подсвечен
    зелёным; по клику выезжает панелька выбора качества;
  * ниже — история загрузок и статус текущих: завершённые с галочкой.
"""

import os
import subprocess
import sys
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
        self.row_entries = {}    # id строки таблицы -> dict записи истории
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
        # Ctrl+V/C/X/A на любой раскладке клавиатуры (см. _on_ctrl_key)
        entry.bind("<Control-KeyPress>", self._on_ctrl_key)
        entry.bind("<Shift-Insert>", lambda _e: self._paste_into_entry())
        self.bind("<Control-KeyPress>", self._on_ctrl_key_global)

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
        self.tree.bind("<Button-3>", self._show_context_menu)
        if sys.platform == "darwin":  # у macOS правая кнопка — Button-2
            self.tree.bind("<Button-2>", self._show_context_menu)
            self.tree.bind("<Control-Button-1>", self._show_context_menu)

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
    # буфер обмена на любой раскладке
    # ------------------------------------------------------------------
    # Стандартные привязки Tk (Ctrl+V и т. п.) работают только на
    # латинской раскладке. Управляющий код нажатой клавиши (event.char)
    # от раскладки не зависит: Ctrl+V всегда даёт \x16, Ctrl+C — \x03,
    # Ctrl+X — \x18, Ctrl+A — \x01.
    def _on_ctrl_key(self, event):
        char = event.char
        if char == "\x16":
            return self._paste_into_entry()
        if char == "\x03":
            self.url_entry.event_generate("<<Copy>>")
            return "break"
        if char == "\x18":
            self.url_entry.event_generate("<<Cut>>")
            return "break"
        if char == "\x01":
            self.url_entry.select_range(0, "end")
            self.url_entry.icursor("end")
            return "break"
        return None

    def _on_ctrl_key_global(self, event):
        # Ctrl+V, когда фокус не в строке ввода — вставляем в неё
        if event.char == "\x16" and event.widget is not self.url_entry:
            self.url_entry.focus_set()
            return self._paste_into_entry()
        return None

    def _paste_into_entry(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return "break"
        self._clear_placeholder()
        try:
            self.url_entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass  # нет выделения
        self.url_entry.insert("insert", text.strip())
        self.url_entry.configure(fg=TEXT)
        return "break"

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
        self.row_entries[item] = entry

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
                name = os.path.basename(payload) if payload else entry["url"]
                self._update_statusbar(f"Готово: {name}")
                del self.tasks[task_id]
            elif event == "error":
                self.tree.set(item, "status", STATUS_ERROR)
                self.tree.item(item, tags=("error",))
                self.config_store.update_history(
                    entry, "error",
                    error=payload.get("message"),
                    hint=payload.get("hint"),
                    report_path=payload.get("report_path"))
                self._update_statusbar(
                    "Ошибка. Правый клик по строке → «Почему не "
                    "скачалось…» — причина и отчёт")
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
            item = self.tree.insert(
                "", "end",
                values=(record.get("url", ""), record.get("service", ""),
                        record.get("format", ""), text),
                tags=(tag,))
            self.row_entries[item] = record

    def _on_history_doubleclick(self, _event):
        selection = self.tree.selection()
        if selection:
            url = self.tree.set(selection[0], "url")
            self._clear_placeholder()
            self.url_var.set(url)
            self.url_entry.configure(fg=TEXT)
            self.url_entry.focus_set()

    # ------------------------------------------------------------------
    # контекстное меню истории (правый клик)
    # ------------------------------------------------------------------
    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        entry = self.row_entries.get(item)
        if entry is None:
            return
        menu = tk.Menu(self, tearoff=0)
        if entry.get("status") == "done" and entry.get("file"):
            menu.add_command(
                label="Открыть",
                command=lambda: self._open_file(entry["file"]))
            menu.add_command(
                label="Показать в папке",
                command=lambda: self._reveal_file(entry["file"]))
            menu.add_separator()
        if entry.get("status") == "error" and entry.get("error"):
            menu.add_command(
                label="Почему не скачалось…",
                command=lambda: self._show_error_details(entry))
            menu.add_separator()
        menu.add_command(
            label="Копировать ссылку",
            command=lambda: self._copy_url(entry.get("url", "")))
        is_active = any(t["item"] == item for t in self.tasks.values())
        if not is_active:
            menu.add_command(
                label="Удалить из истории", foreground=ERROR,
                activeforeground=ERROR,
                command=lambda: self._delete_history_row(item, entry))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_url(self, url: str):
        self.clipboard_clear()
        self.clipboard_append(url)
        self._update_statusbar("Ссылка скопирована в буфер обмена")

    def _resolve_file(self, filepath: str):
        if not filepath:
            return None
        if not os.path.isabs(filepath):
            # старые записи истории хранили только имя файла
            filepath = os.path.join(self.config_store.download_dir, filepath)
        return filepath if os.path.exists(filepath) else None

    def _open_file(self, filepath: str):
        path = self._resolve_file(filepath)
        if not path:
            messagebox.showinfo(
                "MediaGrab", "Файл не найден — возможно, он был "
                "перемещён или удалён.")
            return
        self._open_in_system(path)

    def _reveal_file(self, filepath: str):
        path = self._resolve_file(filepath)
        if not path:
            messagebox.showinfo(
                "MediaGrab", "Файл не найден — возможно, он был "
                "перемещён или удалён.")
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            self._open_in_system(os.path.dirname(path))

    @staticmethod
    def _open_in_system(path: str):
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 — открытие файла системой
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _delete_history_row(self, item, entry):
        self.config_store.remove_history(entry)
        self.row_entries.pop(item, None)
        self.tree.delete(item)

    # ------------------------------------------------------------------
    # окно «почему не скачалось»
    # ------------------------------------------------------------------
    def _show_error_details(self, entry: dict):
        win = tk.Toplevel(self)
        win.title("Почему не скачалось")
        win.configure(bg=BG)
        win.geometry("600x430")
        win.transient(self)

        tk.Label(win, text=entry.get("url", ""), bg=BG, fg=MUTED,
                 wraplength=560, justify="left",
                 font=("TkDefaultFont", 9)).pack(
            anchor="w", padx=16, pady=(12, 2))

        tk.Label(win, text="Что можно сделать", bg=BG, fg=ACCENT_DARK,
                 font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", padx=16, pady=(8, 2))
        tk.Label(win, text=entry.get("hint") or "Причина неизвестна.",
                 bg=BG, fg=TEXT, wraplength=560, justify="left").pack(
            anchor="w", padx=16)

        tk.Label(win, text="Текст ошибки", bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", padx=16, pady=(12, 2))
        text = tk.Text(win, height=5, wrap="word", bg=CARD, fg=ERROR,
                       relief="solid", bd=1, font=("TkDefaultFont", 9))
        text.insert("1.0", entry.get("error") or "")
        text.configure(state="disabled")
        text.pack(fill="x", padx=16)

        report_path = entry.get("report_path") or ""
        if report_path:
            tk.Label(win, text=f"Полный отчёт: {report_path}", bg=BG,
                     fg=MUTED, wraplength=560, justify="left",
                     font=("TkDefaultFont", 8)).pack(
                anchor="w", padx=16, pady=(6, 0))

        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill="x", padx=16, pady=14)
        tk.Button(buttons, text="Скопировать отчёт", bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2", padx=10,
                  command=lambda: self._copy_report(entry)).pack(side="left")
        if report_path:
            tk.Button(buttons, text="Открыть папку отчётов", bg=CARD,
                      fg=TEXT, relief="solid", bd=1, cursor="hand2",
                      padx=10,
                      command=lambda: self._open_in_system(
                          os.path.dirname(report_path))).pack(
                side="left", padx=8)
        tk.Button(buttons, text="Закрыть", bg=CARD, fg=TEXT,
                  relief="solid", bd=1, cursor="hand2", padx=10,
                  command=win.destroy).pack(side="right")

    def _copy_report(self, entry: dict):
        report = ""
        path = entry.get("report_path") or ""
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    report = fh.read()
            except OSError:
                report = ""
        if not report:
            report = "\n".join(filter(None, [
                "MediaGrab — ошибка загрузки",
                f"Ссылка: {entry.get('url', '')}",
                f"Сервис: {entry.get('service', '')}",
                f"Формат: {entry.get('format', '')}",
                f"Ошибка: {entry.get('error', '')}",
            ]))
        self.clipboard_clear()
        self.clipboard_append(report)
        self._update_statusbar(
            "Отчёт скопирован — можно вставить в сообщение разработчику")

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
