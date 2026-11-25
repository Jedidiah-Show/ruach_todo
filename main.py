import os
from datetime import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.utils import escape_markup, platform as kivy_platform

from gcal_sync import sync_tasks_to_google_calendar
from todo_logic import (
    add_task,
    clear_completed,
    count_remaining,
    edit_task,
    get_filtered_tasks,
    is_task_due,
    load_settings,
    load_tasks,
    remove_task,
    save_settings,
    save_tasks,
    SCHEDULE_HINT,
)


def rgba(hex_color: str, alpha: float = 1.0) -> list[float]:
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return [r, g, b, alpha]


THEMES = {
    "light": {
        "bg_app": "#E2E8F0",
        "bg_banner": "#312E81",
        "bg_banner_badge": "#4338CA",
        "bg_banner_btn": "#1E1B4B",
        "bg_card": "#F8FAFC",
        "bg_topbar": "#EEF2FF",
        "bg_row": "#FFFFFF",
        "bg_row_done": "#F1F5F9",
        "bg_row_edit": "#EEF2FF",
        "bg_input": "#FFFFFF",
        "fg_on_dark": "#FFFFFF",
        "fg_on_dark_muted": "#C7D2FE",
        "fg_primary": "#0F172A",
        "fg_done": "#64748B",
        "fg_muted": "#475569",
        "accent": "#4F46E5",
        "success": "#059669",
        "danger": "#DC2626",
        "neutral": "#475569",
    },
    "dark": {
        "bg_app": "#0B1120",
        "bg_banner": "#1E1B4B",
        "bg_banner_badge": "#312E81",
        "bg_banner_btn": "#0F172A",
        "bg_card": "#111827",
        "bg_topbar": "#1E293B",
        "bg_row": "#1E293B",
        "bg_row_done": "#172033",
        "bg_row_edit": "#26285A",
        "bg_input": "#0F172A",
        "fg_on_dark": "#F8FAFC",
        "fg_on_dark_muted": "#C7D2FE",
        "fg_primary": "#F1F5F9",
        "fg_done": "#94A3B8",
        "fg_muted": "#94A3B8",
        "accent": "#6366F1",
        "success": "#10B981",
        "danger": "#EF4444",
        "neutral": "#334155",
    },
}


def set_bg(widget, hex_color: str):
    """Paint a widget background, replacing (and unbinding) any previous one."""
    canvas = widget.canvas.before
    canvas.clear()
    with canvas:
        Color(*rgba(hex_color))
        rect = Rectangle(pos=widget.pos, size=widget.size)

    old_update = getattr(widget, "_ruach_bg_update", None)
    if old_update is not None:
        widget.unbind(pos=old_update, size=old_update)

    def _update(_inst, _val):
        rect.pos = widget.pos
        rect.size = widget.size

    widget._ruach_bg_update = _update
    widget.bind(pos=_update, size=_update)


def make_btn(
    text: str,
    bg_hex: str,
    fg_hex: str = "#FFFFFF",
    width_dp: int | None = None,
    height_dp: int = 40,
) -> Button:
    return Button(
        text=text,
        background_normal="",
        background_color=rgba(bg_hex),
        color=rgba(fg_hex),
        font_size=dp(13),
        bold=True,
        size_hint_x=None if width_dp else 1,
        width=dp(width_dp) if width_dp else dp(90),
        size_hint_y=None,
        height=dp(height_dp),
    )


class RuachTodoApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks: list[dict] = []
        self.settings: dict = {"theme": "light"}
        self.current_filter: str = "all"
        self.editing_index: int | None = None
        self.tasks_file: str = ""
        self.settings_file: str = ""
        self._notification_warning_shown = False

    def build(self):
        self.title = "Ruach To-do"
        os.makedirs(self.user_data_dir, mode=0o700, exist_ok=True)
        try:
            os.chmod(self.user_data_dir, 0o700)
        except OSError:
            pass
        self.tasks_file = os.path.join(self.user_data_dir, "tasks.json")
        self.settings_file = os.path.join(self.user_data_dir, "settings.json")

        self.settings = load_settings(self.settings_file)
        self.tasks = load_tasks(self.tasks_file)

        self.root_box = BoxLayout(orientation="vertical")

        # --- Banner ---
        self.banner = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(74),
            padding=[dp(12), dp(8)],
            spacing=dp(8),
        )
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ruach_ai.png")
        self.logo_badge = None
        self.banner_logo = None
        if os.path.exists(logo_path):
            self.banner_logo = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(dp(56), dp(56)),
            )
            self.banner.add_widget(self.banner_logo)
        else:
            self.logo_badge = Label(
                text="R",
                bold=True,
                font_size=dp(20),
                size_hint=(None, None),
                size=(dp(40), dp(40)),
            )
            self.banner.add_widget(self.logo_badge)

        title_col = BoxLayout(orientation="vertical", size_hint_x=1)
        self.title_lbl = Label(
            text="Ruach To-do",
            font_size=dp(18),
            bold=True,
            halign="left",
            valign="middle",
        )
        self.title_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.sub_lbl = Label(
            text="Stay focused on what matters",
            font_size=dp(11),
            halign="left",
            valign="middle",
        )
        self.sub_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        title_col.add_widget(self.title_lbl)
        title_col.add_widget(self.sub_lbl)
        self.banner.add_widget(title_col)

        self.counter_lbl = Label(
            text="0 undone • 0 done",
            font_size=dp(12),
            bold=True,
            size_hint=(None, None),
            size=(dp(150), dp(34)),
        )
        self.banner.add_widget(self.counter_lbl)

        self.theme_btn = make_btn("Dark", "#1E1B4B", "#FFFFFF", width_dp=68, height_dp=38)
        self.theme_btn.bind(on_release=lambda _b: self.toggle_theme())
        self.banner.add_widget(self.theme_btn)

        self.root_box.add_widget(self.banner)

        # --- Body Container ---
        self.body = BoxLayout(
            orientation="vertical",
            padding=[dp(10), dp(10)],
            spacing=dp(10),
        )

        # --- Task Card ---
        self.list_card = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        self.top_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            padding=[dp(4), dp(2)],
            spacing=dp(6),
        )
        self.filter_btns: dict[str, Button] = {}
        for mode, label in [("all", "All"), ("active", "Active"), ("done", "Done")]:
            b = make_btn(label, "#FFFFFF", "#475569", width_dp=62, height_dp=32)
            b.bind(on_release=lambda _btn, m=mode: self.set_filter(m))
            self.filter_btns[mode] = b
            self.top_bar.add_widget(b)

        self.search_input = TextInput(
            hint_text="Search title or notes...",
            multiline=False,
            size_hint_y=None,
            height=dp(34),
            font_size=dp(13),
        )
        self.search_input.bind(text=lambda _w, _v: self.refresh_display(persist=False))
        self.top_bar.add_widget(self.search_input)

        self.clear_search_btn = make_btn("×", "#475569", "#FFFFFF", width_dp=34, height_dp=34)
        self.clear_search_btn.bind(on_release=lambda _b: self.clear_search())
        self.top_bar.add_widget(self.clear_search_btn)

        self.list_card.add_widget(self.top_bar)

        self.status_lbl = Label(
            text="Ready",
            font_size=dp(11),
            size_hint_y=None,
            height=dp(20),
            halign="left",
            valign="middle",
        )
        self.status_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.list_card.add_widget(self.status_lbl)

        self.scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        self.rows_box = GridLayout(
            cols=1,
            spacing=dp(8),
            size_hint_y=None,
            padding=[dp(2), dp(2)],
        )
        self.rows_box.bind(minimum_height=self.rows_box.setter("height"))
        self.scroll.add_widget(self.rows_box)
        self.list_card.add_widget(self.scroll)

        self.body.add_widget(self.list_card)

        # --- Controls Card (Title, Description, Schedule Time) ---
        self.controls_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(172),
            padding=[dp(10), dp(8)],
            spacing=dp(8),
        )

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        self.task_input = TextInput(
            hint_text="Task title...",
            multiline=False,
            font_size=dp(14),
        )
        self.task_input.bind(on_text_validate=lambda _w: self.on_add())
        title_row.add_widget(self.task_input)

        self.add_btn = make_btn("Add task", "#4F46E5", "#FFFFFF", width_dp=100, height_dp=40)
        self.add_btn.bind(on_release=lambda _b: self.on_add())
        title_row.add_widget(self.add_btn)
        self.controls_card.add_widget(title_row)

        meta_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))
        self.desc_input = TextInput(
            hint_text="Description / notes (optional)...",
            multiline=False,
            font_size=dp(13),
        )
        self.desc_input.bind(on_text_validate=lambda _w: self.on_add())
        meta_row.add_widget(self.desc_input)

        self.schedule_input = TextInput(
            hint_text=SCHEDULE_HINT,
            multiline=False,
            font_size=dp(12),
            size_hint_x=None,
            width=dp(175),
        )
        self.schedule_input.bind(on_text_validate=lambda _w: self.on_add())
        meta_row.add_widget(self.schedule_input)
        self.controls_card.add_widget(meta_row)

        bottom_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))
        self.clear_done_btn = make_btn("Clear completed", "#475569", "#FFFFFF", height_dp=38)
        self.clear_done_btn.bind(on_release=lambda _b: self.on_clear_completed())
        bottom_row.add_widget(self.clear_done_btn)
        self.gcal_btn = make_btn("Sync GCal", "#059669", "#FFFFFF", width_dp=100, height_dp=38)
        if kivy_platform == "android":
            # The desktop OAuth flow needs a browser and localhost callback.
            self.gcal_btn.disabled = True
            self.gcal_btn.text = "GCal: desktop"
        self.gcal_btn.bind(on_release=lambda _b: self.on_sync_gcal())
        bottom_row.add_widget(self.gcal_btn)
        self.test_notify_btn = make_btn("Test notice", "#7C3AED", "#FFFFFF", width_dp=86, height_dp=38)
        self.test_notify_btn.bind(on_release=lambda _b: self.on_test_notification())
        bottom_row.add_widget(self.test_notify_btn)
        self.controls_card.add_widget(bottom_row)

        self.body.add_widget(self.controls_card)
        self.root_box.add_widget(self.body)

        self.apply_theme()
        self._apply_responsive_layout()
        Window.bind(width=self._apply_responsive_layout, height=self._apply_responsive_layout)

        msg = f"Loaded {len(self.tasks)} saved task(s)" if self.tasks else "Ready"
        self.refresh_display(msg, persist=False)
        Clock.schedule_interval(self.check_due_notifications, 30)
        Clock.schedule_once(self.check_due_notifications, 2)
        Clock.schedule_once(lambda _dt: self._request_notification_permission(), 1)
        return self.root_box

    # ------------------------------------------------------------------
    # Theme and responsive layout
    # ------------------------------------------------------------------
    def current_palette(self) -> dict:
        theme_name = self.settings.get("theme", "light")
        return THEMES.get(theme_name, THEMES["light"])

    def toggle_theme(self):
        self.settings["theme"] = "dark" if self.settings.get("theme") == "light" else "light"
        save_settings(self.settings, self.settings_file)
        self.apply_theme()
        self.status_lbl.text = f"Switched to {self.settings['theme'].title()} Mode"

    def apply_theme(self):
        p = self.current_palette()
        is_dark = self.settings.get("theme") == "dark"

        set_bg(self.root_box, p["bg_app"])
        set_bg(self.banner, p["bg_banner"])
        set_bg(self.counter_lbl, p["bg_banner_badge"])
        set_bg(self.list_card, p["bg_card"])
        set_bg(self.top_bar, p["bg_topbar"])
        set_bg(self.controls_card, p["bg_card"])
        if self.logo_badge is not None:
            set_bg(self.logo_badge, p["bg_banner_badge"])
            self.logo_badge.color = rgba(p["fg_on_dark"])

        self.title_lbl.color = rgba(p["fg_on_dark"])
        self.sub_lbl.color = rgba(p["fg_on_dark_muted"])
        self.counter_lbl.color = rgba(p["fg_on_dark"])
        self.status_lbl.color = rgba(p["fg_muted"])

        self.theme_btn.text = "Light" if is_dark else "Dark"
        self.theme_btn.background_color = rgba(p["bg_banner_btn"])
        self.add_btn.background_color = rgba(p["accent"])
        self.clear_done_btn.background_color = rgba(p["neutral"])
        self.clear_search_btn.background_color = rgba(p["neutral"])
        self.gcal_btn.background_color = rgba(p["success"])
        self.test_notify_btn.background_color = rgba("#7C3AED")

        for inp in (self.search_input, self.task_input, self.desc_input, self.schedule_input):
            inp.background_color = rgba(p["bg_input"])
            inp.foreground_color = rgba(p["fg_primary"])
            inp.cursor_color = rgba(p["accent"])

        self.update_filter_buttons()
        self.render_rows()

    def _apply_responsive_layout(self, *_args):
        """Keep the banner and controls usable on phone-sized windows."""
        compact = Window.width < dp(560)
        self.banner.height = dp(64) if compact else dp(80)
        self.banner.padding = [dp(8), dp(6)] if compact else [dp(12), dp(8)]
        if self.banner_logo is not None:
            self.banner_logo.size = (dp(46), dp(46)) if compact else (dp(60), dp(60))
        self.counter_lbl.width = dp(104) if compact else dp(150)
        self.counter_lbl.font_size = dp(10) if compact else dp(12)
        self.sub_lbl.text = "" if compact else "Stay focused on what matters"
        self.theme_btn.width = dp(58) if compact else dp(68)

        self.body.padding = [dp(8), dp(8)] if compact else [dp(10), dp(10)]
        self.controls_card.height = dp(172) if compact else dp(176)
        self.schedule_input.width = dp(140) if compact else dp(175)
        self.schedule_input.font_size = dp(11) if compact else dp(12)
        self.gcal_btn.width = dp(78) if compact else dp(100)
        self.test_notify_btn.width = dp(58) if compact else dp(86)
        self.test_notify_btn.text = "Notify" if compact else "Test notice"
        self.add_btn.width = dp(82) if compact else dp(100)
        for btn in self.filter_btns.values():
            btn.width = dp(52) if compact else dp(62)

    def update_filter_buttons(self):
        p = self.current_palette()
        for mode, btn in self.filter_btns.items():
            if mode == self.current_filter:
                btn.background_color = rgba(p["accent"])
                btn.color = rgba("#FFFFFF")
            else:
                btn.background_color = rgba(p["bg_row"])
                btn.color = rgba(p["fg_muted"])

    def set_filter(self, mode: str):
        self.current_filter = mode
        self.editing_index = None
        self.update_filter_buttons()
        self.refresh_display(f"Showing {mode} tasks", persist=False)

    def clear_search(self):
        self.search_input.text = ""
        self.refresh_display(f"Showing {self.current_filter} tasks", persist=False)

    # ------------------------------------------------------------------
    # Task actions
    # ------------------------------------------------------------------
    def on_add(self):
        msg = add_task(
            self.tasks,
            self.task_input.text,
            self.desc_input.text,
            self.schedule_input.text,
        )
        saved = "added to to-dos" in msg
        if saved:
            self.task_input.text = ""
            self.desc_input.text = ""
            self.schedule_input.text = ""
        self.refresh_display(msg, persist=saved)

    def on_toggle(self, idx: int, active: bool):
        if 0 <= idx < len(self.tasks):
            self.tasks[idx]["done"] = active
            msg = (
                f"{self.tasks[idx]['title']} is marked completed"
                if active
                else f"{self.tasks[idx]['title']} marked as pending"
            )
            self.refresh_display(msg, persist=True)

    def start_edit(self, idx: int):
        self.editing_index = idx
        self.refresh_display(f"Editing task #{idx + 1}", persist=False)

    def commit_edit(self, idx: int, new_title: str, new_desc: str, new_sched: str):
        msg = edit_task(self.tasks, idx, new_title, new_desc, new_sched)
        saved = msg.startswith("Updated ")
        if saved:
            self.editing_index = None
        self.refresh_display(msg, persist=saved)

    def on_delete(self, idx: int):
        if self.editing_index == idx:
            self.editing_index = None
        elif self.editing_index is not None and self.editing_index > idx:
            self.editing_index -= 1
        msg = remove_task(self.tasks, idx)
        self.refresh_display(msg, persist="has been deleted" in msg)

    def on_clear_completed(self):
        done_count = sum(1 for t in self.tasks if t["done"])
        if done_count == 0:
            self.refresh_display("No completed tasks to clear", persist=False)
            return

        p = self.current_palette()
        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
        set_bg(content, p["bg_card"])
        confirm_lbl = Label(
            text=f"Remove {done_count} completed task(s)?",
            color=rgba(p["fg_primary"]),
        )
        content.add_widget(confirm_lbl)
        btns = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
        cancel_b = make_btn("Cancel", p["neutral"], "#FFFFFF", height_dp=40)
        confirm_b = make_btn("Clear", p["danger"], "#FFFFFF", height_dp=40)
        btns.add_widget(cancel_b)
        btns.add_widget(confirm_b)
        content.add_widget(btns)

        popup = Popup(
            title="Clear Completed Tasks",
            content=content,
            size_hint=(0.85, None),
            height=dp(180),
            auto_dismiss=False,
        )

        def _confirm(_b):
            popup.dismiss()
            self.editing_index = None
            removed_count, msg = clear_completed(self.tasks)
            self.refresh_display(msg, persist=removed_count > 0)

        cancel_b.bind(on_release=lambda _b: popup.dismiss())
        confirm_b.bind(on_release=_confirm)
        popup.open()

    def refresh_display(self, status_msg: str = "", persist: bool = False):
        if persist and not save_tasks(self.tasks, self.tasks_file):
            status_msg = f"{status_msg} (Save failed)".strip()
        remaining = count_remaining(self.tasks)
        completed = len(self.tasks) - remaining
        self.counter_lbl.text = f"{remaining} undone • {completed} done"
        self.status_lbl.text = (status_msg[:160] + "…") if len(status_msg) > 160 else (status_msg or "Ready")
        self.render_rows()

    def render_rows(self):
        p = self.current_palette()
        self.rows_box.clear_widgets()
        visible = get_filtered_tasks(self.tasks, self.current_filter, self.search_input.text)

        if not visible:
            empty_lbl = Label(
                text="No matching tasks.",
                color=rgba(p["fg_muted"]),
                font_size=dp(14),
                size_hint_y=None,
                height=dp(48),
            )
            self.rows_box.add_widget(empty_lbl)
            return

        for idx, task in visible:
            is_done = task["done"]
            is_editing = self.editing_index == idx
            desc = task.get("description", "")
            sched = task.get("schedule", "")
            has_details = bool(desc or sched)

            row_bg = p["bg_row_edit"] if is_editing else (p["bg_row_done"] if is_done else p["bg_row"])
            row_height = dp(116) if is_editing else (dp(80) if has_details else dp(56))

            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=row_height,
                padding=[dp(8), dp(6)],
                spacing=dp(6),
            )
            set_bg(row, row_bg)

            num_lbl = Label(
                text=f"{idx + 1}.",
                color=rgba(p["fg_muted"]),
                font_size=dp(12),
                bold=True,
                size_hint_x=None,
                width=dp(22),
            )
            row.add_widget(num_lbl)

            if is_editing:
                edit_col = BoxLayout(orientation="vertical", spacing=dp(4))
                edit_title = TextInput(
                    text=task["title"],
                    hint_text="Task title",
                    multiline=False,
                    font_size=dp(13),
                    size_hint_y=None,
                    height=dp(34),
                    background_color=rgba(p["bg_input"]),
                    foreground_color=rgba(p["fg_primary"]),
                )
                edit_sub_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(6))
                edit_desc = TextInput(
                    text=desc,
                    hint_text="Description",
                    multiline=False,
                    font_size=dp(12),
                    background_color=rgba(p["bg_input"]),
                    foreground_color=rgba(p["fg_primary"]),
                )
                edit_sched = TextInput(
                    text=sched,
                    hint_text="Schedule",
                    multiline=False,
                    font_size=dp(11),
                    size_hint_x=None,
                    width=dp(118),
                    background_color=rgba(p["bg_input"]),
                    foreground_color=rgba(p["fg_primary"]),
                )
                edit_sub_row.add_widget(edit_desc)
                edit_sub_row.add_widget(edit_sched)
                edit_col.add_widget(edit_title)
                edit_col.add_widget(edit_sub_row)
                row.add_widget(edit_col)

                save_b = make_btn("Save", p["success"], "#FFFFFF", width_dp=56, height_dp=38)
                save_b.bind(
                    on_release=lambda _b, i=idx, wt=edit_title, wd=edit_desc, ws=edit_sched: self.commit_edit(
                        i, wt.text, wd.text, ws.text
                    )
                )
                row.add_widget(save_b)
            else:
                chk = CheckBox(
                    active=is_done,
                    size_hint_x=None,
                    width=dp(28),
                )
                chk.bind(active=lambda _w, val, i=idx: self.on_toggle(i, val))
                row.add_widget(chk)

                text_col = BoxLayout(orientation="vertical", spacing=dp(2))
                display_title = escape_markup(task["title"])
                if is_done:
                    display_title = f"[s]{display_title}[/s]"
                title_lbl = Label(
                    text=display_title,
                    markup=True,
                    color=rgba(p["fg_done"] if is_done else p["fg_primary"]),
                    font_size=dp(14),
                    bold=True,
                    halign="left",
                    valign="middle",
                )
                title_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
                text_col.add_widget(title_lbl)

                if has_details:
                    parts = []
                    if sched:
                        parts.append(f"Due: {escape_markup(sched)}")
                    if desc:
                        parts.append(escape_markup(desc))
                    detail_lbl = Label(
                        text="  •  ".join(parts),
                        markup=True,
                        color=rgba(p["fg_muted"]),
                        font_size=dp(12),
                        halign="left",
                        valign="middle",
                    )
                    detail_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
                    text_col.add_widget(detail_lbl)

                row.add_widget(text_col)

                edit_b = make_btn("Edit", p["neutral"], "#FFFFFF", width_dp=50, height_dp=36)
                edit_b.bind(on_release=lambda _b, i=idx: self.start_edit(i))
                row.add_widget(edit_b)

            del_b = make_btn("Del", p["danger"], "#FFFFFF", width_dp=46, height_dp=36)
            del_b.bind(on_release=lambda _b, i=idx: self.on_delete(i))
            row.add_widget(del_b)

            self.rows_box.add_widget(row)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _send_notification(self, title: str, message: str) -> bool:
        """Send a desktop notification; return True only if the platform accepted it."""
        try:
            from plyer import notification

            notification.notify(
                title=title,
                message=message,
                app_name="Ruach To-do",
                timeout=10,
            )
            return True
        except Exception as exc:
            Logger.warning("RuachTodo: notification failed: %s", exc)
            return False

    def _request_notification_permission(self):
        """Android 13+ requires runtime permission before notifications can show."""
        if kivy_platform != "android":
            return
        try:
            from android.permissions import request_permissions, Permission, check_permission
        except Exception as exc:
            Logger.warning("RuachTodo: cannot request notification permission: %s", exc)
            return

        wanted = []
        for name in ("POST_NOTIFICATIONS", "VIBRATE"):
            perm = getattr(Permission, name, None)
            if perm is not None and not check_permission(perm):
                wanted.append(perm)
        if wanted:
            request_permissions(wanted, self._on_permission_result)
        elif not hasattr(Permission, "POST_NOTIFICATIONS"):
            # Older p4a builds may not expose the constant; ask by string instead.
            request_permissions(["android.permission.POST_NOTIFICATIONS"], self._on_permission_result)

    def _on_permission_result(self, permissions, grants):
        if all(grants):
            self.status_lbl.text = "Notification permission granted"
        else:
            self.status_lbl.text = "Notification permission denied — enable it in Settings"

    def on_test_notification(self):
        ok = self._send_notification(
            "Ruach To-do",
            "Notifications are working. You're all set!",
        )
        msg = "Test notification sent" if ok else "Notification failed — check system settings"
        self.refresh_display(msg, persist=False)

    def check_due_notifications(self, _dt):
        now = datetime.now()
        due = [task for task in self.tasks if is_task_due(task, now)]
        if not due:
            return

        sent = 0
        failed = 0
        first_title = ""
        for task in due:
            body = task.get("description") or f"Scheduled for {task.get('schedule')}"
            if self._send_notification(f"Ruach To-do: {task['title']}", body):
                # Only mark as notified once delivery succeeded, so a failed
                # notification is retried on the next check instead of being lost.
                task["notified"] = True
                sent += 1
                if not first_title:
                    first_title = task["title"]
            else:
                failed += 1

        if sent:
            status = f"Due now: {first_title}"
            if sent > 1:
                status += f" (+{sent - 1} more)"
            if failed:
                status += f"; {failed} failed"
            self.refresh_display(status, persist=True)
        else:
            status = "Notification unavailable — check notification permissions"
            if not self._notification_warning_shown:
                self._notification_warning_shown = True
                self.refresh_display(status, persist=False)

    def on_sync_gcal(self):
        try:
            synced, msg = sync_tasks_to_google_calendar(self.tasks, self.user_data_dir)
            # Persist even when nothing was newly synced: the sync may have
            # assigned/cleared event IDs or deleted stale events.
            self.refresh_display(msg, persist=True)
        except Exception as exc:
            self.refresh_display(f"GCal error: {exc}", persist=False)


if __name__ == "__main__":
    RuachTodoApp().run()
