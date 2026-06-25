import json
import queue
import threading
import time
import tkinter as tk
from tkinter import colorchooser
from tkinter import font as tkfont

from constants import (
    COLOR_TRANSPARENT,
    DEFAULT_INST_IDS,
    GRID_COLUMNS,
    MAX_INSTRUMENTS,
    SETTINGS_DEFAULTS,
    UI_POLL_INTERVAL_MS,
    DOUBLE_CLICK_MAX_PIXELS,
    DOUBLE_CLICK_MAX_SECONDS,
)
from okx_client import search_instruments
from price_stream import PriceStream
from settings import load_settings, normalize_instruments, save_settings

WINDOW_WIDTH = 440


class FloatingWindow:
    def __init__(self, root, inst_ids=None):
        self.root = root
        self.settings = load_settings()
        self.instruments = normalize_instruments(
            self.settings["instruments"],
            inst_ids or DEFAULT_INST_IDS,
        )
        self.settings["instruments"] = self.instruments
        self.inst_ids = [instrument["instId"] for instrument in self.instruments]

        self._last_prices = {inst_id: None for inst_id in self.inst_ids}
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._last_click_at = 0
        self._last_click_x = None
        self._last_click_y = None
        self._last_press_serial = None
        self._status_state = "connecting"
        self._status_text = "连接"
        self._settings_window = None
        self._layout_ready = False

        self._events = queue.Queue()
        self._price_stream = PriceStream(self.instruments, self._events)

        self._setup_window()
        self._build_ui()
        self._price_stream.start()
        self._poll_events()

    def _setup_window(self):
        self.root.title("OKX Price")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry(self._window_geometry())
        self.root.configure(bg=COLOR_TRANSPARENT)
        self.root.attributes("-alpha", self.settings["alpha"])
        self.root.wm_attributes("-transparentcolor", COLOR_TRANSPARENT)

        self.root.bind("<ButtonPress-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)

        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            activebackground="#222222",
            activeforeground=self.settings["fg_default"],
        )
        self.context_menu.add_command(label="设置", command=self._show_settings)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="退出", command=self._quit)
        self.root.bind("<ButtonRelease-3>", self._show_context_menu)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    def _build_ui(self):
        self.rows = {}
        self.badge_font = tkfont.Font(family="Microsoft YaHei", size=8, weight="bold")
        self.name_font = tkfont.Font(family="Microsoft YaHei", size=10, weight="bold")
        self.sub_font = tkfont.Font(family="Microsoft YaHei", size=7)
        self.price_font = tkfont.Font(family="Consolas", size=17, weight="bold")
        self.percent_font = tkfont.Font(family="Consolas", size=9, weight="bold")

        self.content_frame = tk.Frame(
            self.root,
            bg=self.settings["bg"],
            highlightbackground=self.settings["border"],
            highlightcolor=self.settings["border"],
            highlightthickness=1,
            bd=0,
        )
        self.content_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.top_bar = tk.Frame(self.content_frame, bg=self.settings["bg"], height=20)
        self.top_bar.pack(fill="x", padx=10, pady=(5, 0))
        self.top_bar.pack_propagate(False)

        self.label_brand = tk.Label(
            self.top_bar,
            text="OKX",
            font=self.badge_font,
            bg=self.settings["bg"],
            fg=self.settings["accent"],
        )
        self.label_brand.pack(side="left")

        self.label_status_dot = tk.Label(
            self.top_bar,
            text="●",
            font=self.badge_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_muted"],
        )
        self.label_status_dot.pack(side="right", padx=(5, 0))

        self.label_status = tk.Label(
            self.top_bar,
            text="连接",
            font=self.badge_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_muted"],
        )
        self.label_status.pack(side="right")

        self.prices_frame = tk.Frame(
            self.content_frame,
            bg=self.settings["bg"],
            height=self._price_frame_height(),
        )
        self.prices_frame.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.prices_frame.pack_propagate(False)

        self._build_price_cards()
        self._bind_drag_recursive(self.root)
        self._bind_context_menu_recursive(self.root)
        self._bind_double_click_recursive(self.root)

    def _window_geometry(self):
        height = 126 if len(self.instruments) <= GRID_COLUMNS else 208
        return f"{WINDOW_WIDTH}x{height}+100+100"

    def _price_frame_height(self):
        return 88 if len(self.instruments) <= GRID_COLUMNS else 170

    def _resize_for_cards(self):
        if self._layout_ready:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
        else:
            x = 100
            y = 100
            self._layout_ready = True
        height = 126 if len(self.instruments) <= GRID_COLUMNS else 208
        self.root.geometry(f"{WINDOW_WIDTH}x{height}+{x}+{y}")
        self.prices_frame.config(height=self._price_frame_height())

    def _build_price_cards(self):
        for child in self.prices_frame.winfo_children():
            child.destroy()
        self.rows = {}
        self._resize_for_cards()

        for column in range(GRID_COLUMNS):
            self.prices_frame.grid_columnconfigure(column, weight=1, uniform="price")
        row_count = (len(self.instruments) + GRID_COLUMNS - 1) // GRID_COLUMNS
        self.prices_frame.grid_rowconfigure(0, weight=1, uniform="price")
        self.prices_frame.grid_rowconfigure(
            1,
            weight=1 if row_count > 1 else 0,
            minsize=0,
            uniform="price" if row_count > 1 else "",
        )

        for index, instrument in enumerate(self.instruments):
            inst_id = instrument["instId"]
            row_index = index // GRID_COLUMNS
            column = index % GRID_COLUMNS
            panel_key = "panel" if index % 2 == 0 else "panel_alt"
            frame = tk.Frame(self.prices_frame, bg=self.settings[panel_key])
            frame.grid(
                row=row_index,
                column=column,
                columnspan=GRID_COLUMNS if len(self.instruments) == 1 else 1,
                sticky="nsew",
                padx=(0 if column == 0 else 6, 0),
                pady=(0 if row_index == 0 else 6, 0),
            )

            label_name = tk.Label(
                frame,
                text=self._display_name(inst_id),
                font=self.name_font,
                bg=frame["bg"],
                fg=self.settings["fg_default"],
                anchor="w",
            )
            label_name.pack(fill="x", padx=10, pady=(6, 0))

            label_symbol = tk.Label(
                frame,
                text=self._display_subtitle(instrument),
                font=self.sub_font,
                bg=frame["bg"],
                fg=self.settings["fg_muted"],
                anchor="w",
            )
            label_symbol.pack(fill="x", padx=10)

            quote_row = tk.Frame(frame, bg=frame["bg"])
            quote_row.pack(fill="x", padx=10, pady=(0, 5))

            label_price = tk.Label(
                quote_row,
                text="--",
                font=self.price_font,
                bg=frame["bg"],
                fg=self.settings["fg_default"],
                anchor="w",
            )
            label_price.pack(side="left", fill="x", expand=True)

            label_change = tk.Label(
                quote_row,
                text="0.00%",
                font=self.percent_font,
                bg=frame["bg"],
                fg=self.settings["fg_muted"],
                anchor="e",
                width=7,
            )
            label_change.pack(side="right", padx=(8, 0))

            for widget in (frame, label_name, label_symbol, quote_row, label_price, label_change):
                widget.bind("<ButtonPress-1>", self._on_drag_start)
                widget.bind("<B1-Motion>", self._on_drag_motion)
                widget.bind("<ButtonRelease-3>", self._show_context_menu)
                widget.bind("<Double-Button-1>", self._on_double_click, add="+")

            self.rows[inst_id] = {
                "frame": frame,
                "index": index,
                "quote_row": quote_row,
                "name": label_name,
                "symbol": label_symbol,
                "price": label_price,
                "change": label_change,
            }

    def _on_drag_start(self, event):
        if event.serial == self._last_press_serial:
            return None
        self._last_press_serial = event.serial

        now = time.monotonic()
        if (
            self._last_click_x is not None
            and now - self._last_click_at <= DOUBLE_CLICK_MAX_SECONDS
            and abs(event.x_root - self._last_click_x) <= DOUBLE_CLICK_MAX_PIXELS
            and abs(event.y_root - self._last_click_y) <= DOUBLE_CLICK_MAX_PIXELS
        ):
            self._quit()
            return "break"

        self._last_click_at = now
        self._last_click_x = event.x_root
        self._last_click_y = event.y_root
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()
        return None

    def _on_drag_motion(self, event):
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def _show_settings(self):
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self._settings_window = window
        window.title("设置")
        window.geometry("430x650+160+120")
        window.resizable(False, False)
        window.configure(bg=self.settings["bg"])
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", window.destroy)

        title_font = tkfont.Font(family="Microsoft YaHei", size=11, weight="bold")
        text_font = tkfont.Font(family="Microsoft YaHei", size=9)

        header = tk.Label(
            window,
            text="显示",
            font=title_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            anchor="w",
        )
        header.pack(fill="x", padx=14, pady=(12, 6))

        alpha_frame = tk.Frame(window, bg=self.settings["bg"])
        alpha_frame.pack(fill="x", padx=14, pady=(2, 10))

        tk.Label(
            alpha_frame,
            text="透明度",
            font=text_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_muted"],
            width=10,
            anchor="w",
        ).pack(side="left")

        alpha_value = tk.StringVar(value=f"{int(self.settings['alpha'] * 100)}%")
        alpha_scale = tk.Scale(
            alpha_frame,
            from_=35,
            to=100,
            orient="horizontal",
            showvalue=False,
            length=170,
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            troughcolor=self.settings["panel"],
            highlightthickness=0,
            activebackground=self.settings["accent"],
            command=lambda value: self._set_alpha(float(value) / 100, alpha_value),
        )
        alpha_scale.set(int(self.settings["alpha"] * 100))
        alpha_scale.pack(side="left", fill="x", expand=True)

        tk.Label(
            alpha_frame,
            textvariable=alpha_value,
            font=text_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            width=5,
            anchor="e",
        ).pack(side="right")

        self._build_instrument_settings(window, title_font, text_font)
        self._build_color_settings(window, title_font, text_font, alpha_scale, alpha_value)

    def _build_instrument_settings(self, parent, title_font, text_font):
        section = tk.Frame(parent, bg=self.settings["bg"])
        section.pack(fill="x", padx=14, pady=(2, 6))

        tk.Label(
            section,
            text=f"币对（最多 {MAX_INSTRUMENTS} 个）",
            font=title_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._selected_pairs_frame = tk.Frame(section, bg=self.settings["bg"])
        self._selected_pairs_frame.pack(fill="x")
        self._render_selected_instruments()

        search_row = tk.Frame(section, bg=self.settings["bg"])
        search_row.pack(fill="x", pady=(8, 4))

        self._instrument_search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_row,
            textvariable=self._instrument_search_var,
            font=text_font,
            bg=self.settings["panel"],
            fg=self.settings["fg_default"],
            insertbackground=self.settings["fg_default"],
            relief="flat",
        )
        search_entry.pack(side="left", fill="x", expand=True, ipady=4)
        search_entry.bind("<Return>", lambda _event: self._start_instrument_search())

        tk.Button(
            search_row,
            text="搜索",
            font=text_font,
            command=self._start_instrument_search,
        ).pack(side="right", padx=(8, 0))

        self._instrument_status_var = tk.StringVar(value="输入 BTC、ETH、SOL 或完整币对")
        tk.Label(
            section,
            textvariable=self._instrument_status_var,
            font=text_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_muted"],
            anchor="w",
        ).pack(fill="x")

        self._instrument_results_frame = tk.Frame(section, bg=self.settings["bg"], height=72)
        self._instrument_results_frame.pack(fill="x", pady=(4, 0))
        self._instrument_results_frame.pack_propagate(False)

    def _build_color_settings(self, parent, title_font, text_font, alpha_scale, alpha_value):
        tk.Label(
            parent,
            text="颜色",
            font=title_font,
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 4))

        color_items = [
            ("背景", "bg"),
            ("卡片 1", "panel"),
            ("卡片 2", "panel_alt"),
            ("边框", "border"),
            ("主文字", "fg_default"),
            ("副文字", "fg_muted"),
            ("上涨", "fg_up"),
            ("下跌", "fg_down"),
            ("错误", "fg_error"),
            ("强调", "accent"),
        ]

        grid = tk.Frame(parent, bg=self.settings["bg"])
        grid.pack(fill="both", expand=True, padx=14)
        self._settings_color_buttons = {}

        for label, key in color_items:
            row = tk.Frame(grid, bg=self.settings["bg"])
            row.pack(fill="x", pady=3)

            tk.Label(
                row,
                text=label,
                font=text_font,
                bg=self.settings["bg"],
                fg=self.settings["fg_muted"],
                width=10,
                anchor="w",
            ).pack(side="left")

            value = tk.Label(
                row,
                text=self.settings[key],
                font=text_font,
                bg=self.settings["bg"],
                fg=self.settings["fg_default"],
                width=9,
                anchor="w",
            )
            value.pack(side="left", padx=(0, 8))

            button = tk.Button(
                row,
                text="",
                width=8,
                bg=self.settings[key],
                activebackground=self.settings[key],
                relief="flat",
                command=lambda color_key=key, value_label=value: self._choose_color(
                    color_key,
                    value_label,
                ),
            )
            button.pack(side="right")
            self._settings_color_buttons[key] = button

        actions = tk.Frame(parent, bg=self.settings["bg"])
        actions.pack(fill="x", padx=14, pady=(8, 14))

        tk.Button(
            actions,
            text="恢复默认",
            font=text_font,
            command=lambda: self._reset_settings(alpha_scale, alpha_value),
        ).pack(side="left")

        tk.Button(
            actions,
            text="完成",
            font=text_font,
            command=parent.destroy,
        ).pack(side="right")

    def _render_selected_instruments(self):
        frame = getattr(self, "_selected_pairs_frame", None)
        if frame is None or not frame.winfo_exists():
            return
        for child in frame.winfo_children():
            child.destroy()

        for index, instrument in enumerate(self.instruments):
            row = tk.Frame(frame, bg=self.settings["panel"] if index % 2 == 0 else self.settings["panel_alt"])
            row.pack(fill="x", pady=(0 if index == 0 else 3, 0))

            tk.Label(
                row,
                text=f"{instrument['instId']}  {instrument['instType']}",
                font=("Microsoft YaHei", 9),
                bg=row["bg"],
                fg=self.settings["fg_default"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=8, pady=4)

            tk.Button(
                row,
                text="删除",
                font=("Microsoft YaHei", 8),
                command=lambda inst_id=instrument["instId"]: self._remove_instrument(inst_id),
            ).pack(side="right", padx=4, pady=3)

    def _start_instrument_search(self):
        query = self._instrument_search_var.get()
        if not query.strip():
            self._instrument_status_var.set("请输入想搜索的币种或币对")
            return
        self._instrument_status_var.set("搜索中...")
        for child in self._instrument_results_frame.winfo_children():
            child.destroy()

        def worker():
            results = search_instruments(query, limit=4)
            self.root.after(0, lambda: self._render_instrument_results(results))

        threading.Thread(target=worker, daemon=True).start()

    def _render_instrument_results(self, results):
        frame = getattr(self, "_instrument_results_frame", None)
        if frame is None or not frame.winfo_exists():
            return
        for child in frame.winfo_children():
            child.destroy()

        if not results:
            self._instrument_status_var.set("没搜到，试试 BTC-USDT 或 BTC")
            return

        self._instrument_status_var.set("点击结果即可加入")
        for index, instrument in enumerate(results):
            row = index // 2
            column = index % 2
            button = tk.Button(
                frame,
                text=f"{instrument['instId']}  {instrument['instType']}",
                font=("Microsoft YaHei", 8),
                anchor="w",
                command=lambda item=instrument: self._add_instrument(item),
            )
            button.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0),
                pady=(0 if row == 0 else 4, 0),
            )
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

    def _add_instrument(self, instrument):
        if any(item["instId"] == instrument["instId"] for item in self.instruments):
            self._instrument_status_var.set("已经在列表里了")
            return
        if len(self.instruments) >= MAX_INSTRUMENTS:
            self._instrument_status_var.set(f"最多只能添加 {MAX_INSTRUMENTS} 个")
            return
        self._set_instruments(self.instruments + [instrument])
        self._instrument_status_var.set("已添加")

    def _remove_instrument(self, inst_id):
        if len(self.instruments) <= 1:
            self._instrument_status_var.set("至少保留 1 个")
            return
        instruments = [
            instrument
            for instrument in self.instruments
            if instrument["instId"] != inst_id
        ]
        self._set_instruments(instruments)
        self._instrument_status_var.set("已删除")

    def _set_instruments(self, instruments):
        self.instruments = normalize_instruments(instruments)
        self.inst_ids = [instrument["instId"] for instrument in self.instruments]
        self._last_prices = {inst_id: None for inst_id in self.inst_ids}
        self.settings["instruments"] = self.instruments
        save_settings(self.settings)

        self._price_stream.stop()
        while True:
            try:
                self._events.get_nowait()
            except queue.Empty:
                break

        self._price_stream = PriceStream(self.instruments, self._events)
        self._price_stream.start()
        self._build_price_cards()
        self._apply_theme()
        self._render_selected_instruments()

    def _set_alpha(self, alpha, label_var=None):
        self.settings["alpha"] = min(1.0, max(0.35, alpha))
        self.root.attributes("-alpha", self.settings["alpha"])
        if label_var is not None:
            label_var.set(f"{int(self.settings['alpha'] * 100)}%")
        save_settings(self.settings)

    def _choose_color(self, key, value_label):
        _rgb, color = colorchooser.askcolor(
            color=self.settings[key],
            title="选择颜色",
            parent=self._settings_window,
        )
        if not color:
            return
        self.settings[key] = color
        value_label.config(text=color)
        if key in getattr(self, "_settings_color_buttons", {}):
            self._settings_color_buttons[key].config(bg=color, activebackground=color)
        self._apply_theme()
        save_settings(self.settings)

    def _reset_settings(self, alpha_scale, alpha_value):
        self.settings.update(json.loads(json.dumps(SETTINGS_DEFAULTS)))
        self._set_instruments(self.settings["instruments"])
        alpha_scale.set(int(self.settings["alpha"] * 100))
        alpha_value.set(f"{int(self.settings['alpha'] * 100)}%")
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.destroy()
            self._settings_window = None
            self._show_settings()
        self._apply_theme()
        save_settings(self.settings)

    def _apply_theme(self):
        self.root.attributes("-alpha", self.settings["alpha"])
        self.root.configure(bg=COLOR_TRANSPARENT)
        self.content_frame.config(
            bg=self.settings["bg"],
            highlightbackground=self.settings["border"],
            highlightcolor=self.settings["border"],
        )
        self.top_bar.config(bg=self.settings["bg"])
        self.prices_frame.config(bg=self.settings["bg"])
        self.label_brand.config(bg=self.settings["bg"], fg=self.settings["accent"])
        self.label_status.config(bg=self.settings["bg"], fg=self.settings["fg_muted"])

        for row in self.rows.values():
            panel_key = "panel" if row["index"] % 2 == 0 else "panel_alt"
            panel_color = self.settings[panel_key]
            row["frame"].config(bg=panel_color)
            row["quote_row"].config(bg=panel_color)
            row["name"].config(bg=panel_color, fg=self.settings["fg_default"])
            row["symbol"].config(bg=panel_color, fg=self.settings["fg_muted"])
            row["price"].config(bg=panel_color)
            row["change"].config(bg=panel_color)

        self.context_menu.config(
            bg=self.settings["bg"],
            fg=self.settings["fg_default"],
            activeforeground=self.settings["fg_default"],
        )
        self._update_status(self._status_state, self._status_text)

    def _on_double_click(self, _event):
        self._quit()

    def _quit(self):
        self._price_stream.stop()
        self.root.destroy()

    def _display_name(self, inst_id):
        return self._short_text(inst_id.split("-")[0], 12)

    def _display_subtitle(self, instrument):
        parts = instrument["instId"].split("-")
        subtitle = "-".join(parts[1:]) if len(parts) >= 2 else instrument["instType"]
        return self._short_text(f"{subtitle} {instrument['instType']}", 18)

    def _short_text(self, text, max_len):
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "..."

    def _format_price(self, price):
        if price >= 100:
            return f"{price:,.2f}"
        if price >= 1:
            return f"{price:,.4f}".rstrip("0").rstrip(".")
        return f"{price:.8f}".rstrip("0").rstrip(".")

    def _format_change_pct(self, change_pct):
        if change_pct is None:
            return ""
        sign = "+" if change_pct > 0 else ""
        return f"{sign}{change_pct:.2f}%"

    def _bind_context_menu_recursive(self, widget):
        widget.bind("<ButtonRelease-3>", self._show_context_menu)
        for child in widget.winfo_children():
            self._bind_context_menu_recursive(child)

    def _bind_drag_recursive(self, widget):
        widget.bind("<ButtonPress-1>", self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)
        for child in widget.winfo_children():
            self._bind_drag_recursive(child)

    def _bind_double_click_recursive(self, widget):
        widget.bind("<Double-Button-1>", self._on_double_click, add="+")
        for child in widget.winfo_children():
            self._bind_double_click_recursive(child)

    def _price_color(self, inst_id, new_price):
        last_price = self._last_prices.get(inst_id)
        if last_price is None:
            return self.settings["fg_default"]
        if new_price > last_price:
            return self.settings["fg_up"]
        if new_price < last_price:
            return self.settings["fg_down"]
        return self.settings["fg_default"]

    def _change_color(self, change_pct):
        if change_pct is None:
            return self.settings["fg_muted"]
        if change_pct > 0:
            return self.settings["fg_up"]
        if change_pct < 0:
            return self.settings["fg_down"]
        return self.settings["fg_muted"]

    def _poll_events(self):
        handled = 0
        while handled < 50:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event["type"] == "price":
                self._update_price(
                    event["inst_id"],
                    event["price"],
                    event["source"],
                    event.get("change_pct"),
                )
            elif event["type"] == "status":
                self._update_status(event["state"], event["text"])
            handled += 1
        self.root.after(UI_POLL_INTERVAL_MS, self._poll_events)

    def _update_price(self, inst_id, price, source, change_pct):
        row = self.rows.get(inst_id)
        if row is None:
            return
        last_price = self._last_prices.get(inst_id)
        if change_pct is None:
            if last_price:
                change_pct = (price - last_price) / last_price * 100
            else:
                change_pct = 0.0
        row["price"].config(text=self._format_price(price), fg=self._price_color(inst_id, price))
        row["change"].config(
            text=self._format_change_pct(change_pct),
            fg=self._change_color(change_pct),
        )
        self._last_prices[inst_id] = price
        self._update_status("connected" if source == "WS" else "fallback", source)

    def _update_status(self, state, text):
        self._status_state = state
        self._status_text = text
        color_by_state = {
            "connected": self.settings["fg_up"],
            "fallback": self.settings["accent"],
            "connecting": self.settings["fg_muted"],
            "error": self.settings["fg_error"],
        }
        self.label_status.config(text=text)
        self.label_status_dot.config(fg=color_by_state.get(state, self.settings["fg_muted"]))
