import tkinter as tk
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from queue import Empty, Queue
from tkinter import BooleanVar, StringVar, Tk, ttk
from typing import Any, Literal

from eddr.components import SuggestionBox
from eddr.models import Model
from eddr.utils import APP_VERSION


class View:
    def __init__(self, root: Tk, model: Model):
        self.root = root
        self.model = model

        style = ttk.Style(self.root)
        # Remove the focus border around tabs
        style.layout(
            "Tab",
            [
                (
                    "Notebook.tab",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Notebook.padding",
                                {
                                    "side": "top",
                                    "sticky": "nswe",
                                    "children": [
                                        (
                                            "Notebook.label",
                                            {"side": "top", "sticky": ""},
                                        )
                                    ],
                                },
                            )
                        ],
                    },
                )
            ],
        )

        self.sheet_colors = {
            "table_bg": "#1c1c1e",  # main window surface
            "header_bg": "#202021",  # secondary surface
            "header_fg": "#f3f3f5",  # light text
            "index_bg": "#202021",  # secondary surface
            "index_fg": "#C2C2C4",  # dim light text
            "top_left_bg": "#202021",  # secondary surface
            "cell_bg": "#1c1c1e",  # main window surface
            "cell_fg": "#f3f3f5",  # light text
            "selected_bg": "#0a84ff",  # Fluent accent blue
            "selected_fg": "#ffffff",  # white text on selection
        }

        style = ttk.Style()
        style.element_create(
            "Danger.TButton", "from", "sun-valley-dark", "Button.TButton"
        )
        style.layout("Danger.TButton", style.layout("Button.TButton"))
        style.configure("Danger.TButton", foreground="red")

        # Topbar
        self.top_bar = ttk.Frame(self.root)
        self.top_bar.pack(side="top", fill="x")

        # Version
        self.version = ttk.Label(self.top_bar, text=str(APP_VERSION))
        self.version.pack(side="left", anchor="nw")

        # Clock
        self.clock_utc = ttk.Label(self.top_bar, width=8)
        self.clock_utc.pack(side="right", anchor="ne")
        self.root.after(0, self._update_clock)

        self.tab_controller = ttk.Notebook(self.root)
        # self.tab_controller.pack(expand=True, fill="both")

        self.loading_view = LoadingView(self)
        self.inactive_view = InactiveView(self)
        self.overview = OverviewView(self)
        self.find_view = FindView(self)
        self.route_view = RouteView(self)

        self._callbacks: Queue[
            tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]
        ] = Queue()
        self.root.after(0, self._drain_ui_callbacks)

    def add_callback(self, cb: Callable[..., Any], *args, **kwargs):
        self._callbacks.put_nowait((cb, args, kwargs))

    def copy_to_clipboard(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _drain_ui_callbacks(self):
        while True:
            try:
                callback, args, kwargs = self._callbacks.get_nowait()
            except Empty:
                break
            try:
                callback(*args, **kwargs)
            except Exception:
                print(f"Exception while running callback:\n{traceback.format_exc()}")
        self.root.after(50, self._drain_ui_callbacks)

    def set_state(self, state: Literal["loading", "inactive", "overview"]):
        self.loading_view.frame.pack_forget()
        self.inactive_view.frame.pack_forget()
        self.tab_controller.pack_forget()

        if state == "loading":
            self.loading_view.frame.pack(side="top", fill="both", expand=True)
        elif state == "inactive":
            self.inactive_view.frame.pack(side="top", fill="both", expand=True)
        elif state == "overview":
            self.tab_controller.pack(side="top", fill="both", expand=True)

    def _update_clock(self):
        now = datetime.now(UTC)
        self.clock_utc.configure(text=now.strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)


class LoadingView:
    def __init__(self, parent: View):
        self.parent = parent

        self.frame = ttk.Frame(self.parent.root)
        self.frame.pack(side="top", fill="x", expand=False)

        self.loading_label = ttk.Label(
            self.frame,
            text="Catching up on your journals,\nthis could take a while...",
            justify="center",
        )
        self.loading_label.pack(side="top", expand=False, padx=5, pady=5, anchor="n")

        self.progress = ttk.Progressbar(
            self.frame, orient="horizontal", mode="determinate", length=250
        )
        self.progress.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.counter = ttk.Label(self.frame, text="", justify="center")
        self.counter.pack(side="top", expand=False, padx=5, pady=5, anchor="n")
        self.last_events = ttk.Label(self.frame, text="", justify="center")
        self.last_events.pack(side="top", expand=False, padx=5, pady=5, anchor="n")


class InactiveView:
    def __init__(self, parent: View):
        self.parent = parent

        self.frame = ttk.Frame(self.parent.root)
        self.frame.pack(side="top", fill="x", expand=True)

        self.label = ttk.Label(self.frame, text="No active CMDRs", justify="center")
        self.label.pack(side="top", expand=False, anchor="center")


class OverviewView:
    def __init__(self, parent: View):
        self.parent = parent

        self.tab = ttk.Frame(self.parent.tab_controller)
        self.parent.tab_controller.add(self.tab, text="Overview")

        self._cmdr_selector_frame = ttk.Frame(self.tab)
        self._cmdr_selector_frame.pack(
            side="top", fill="x", expand=False, padx=5, pady=5
        )
        self._cmdr_selector_label = ttk.Label(
            self._cmdr_selector_frame, text="Commander:"
        )
        self._cmdr_selector_label.pack(side="left", padx=(0, 5))
        self.cmdr_selector_combobox = ttk.Combobox(
            self._cmdr_selector_frame,
            textvariable=self.parent.model.selected_cmdr_name,
            values=[],
            state="readonly",
        )
        self.cmdr_selector_combobox.pack(side="left", fill="x", expand=False)

        self.ship_name = StringVar(value="")
        self.ship_frame = ttk.LabelFrame(self.tab, text="Ship")
        self.ship_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self._ship_label = ttk.Label(self.ship_frame, textvariable=self.ship_name)
        self._ship_label.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.ship_contextmenu = tk.Menu(self.parent.root, tearoff=0)
        self.ship_frame.bind(
            "<Button-3>",
            lambda event: self.ship_contextmenu.post(event.x_root, event.y_root),
        )
        self._ship_label.bind(
            "<Button-3>",
            lambda event: self.ship_contextmenu.post(event.x_root, event.y_root),
        )

        self.system_name = StringVar(value="")
        self.system_frame = ttk.LabelFrame(self.tab, text="System")
        self.system_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self._system_label = ttk.Label(self.system_frame, textvariable=self.system_name)
        self._system_label.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.system_contextmenu = tk.Menu(self.parent.root, tearoff=0)
        self.system_frame.bind(
            "<Button-3>",
            lambda event: self.system_contextmenu.post(event.x_root, event.y_root),
        )
        self._system_label.bind(
            "<Button-3>",
            lambda event: self.system_contextmenu.post(event.x_root, event.y_root),
        )

        self.location_name = StringVar(value="")
        self.location_frame = ttk.LabelFrame(self.tab, text="Location")
        self.location_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self._location_label = ttk.Label(
            self.location_frame, textvariable=self.location_name
        )
        self._location_label.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.location_contextmenu = tk.Menu(self.parent.root, tearoff=0)
        self.location_frame.bind(
            "<Button-3>",
            lambda event: self.location_contextmenu.post(event.x_root, event.y_root),
        )
        self._location_label.bind(
            "<Button-3>",
            lambda event: self.location_contextmenu.post(event.x_root, event.y_root),
        )

        self.silent_on = BooleanVar(value=False)
        self.silent_checkbox = ttk.Checkbutton(
            self.tab, text="Silent Mode", variable=self.silent_on
        )
        self.silent_checkbox.pack(side="top", fill="x", expand=False, padx=5, pady=5)


class FindView:
    def __init__(self, parent: View):
        self.parent = parent

        self.tab = ttk.Frame(self.parent.tab_controller)
        self.parent.tab_controller.add(self.tab, text="Find")

        self._lookup_type_frame = ttk.Frame(self.tab)
        self._lookup_type_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self._lookup_type_label = ttk.Label(self._lookup_type_frame, text="Type:")
        self._lookup_type_label.pack(side="left", padx=(0, 5))
        self._lookup_type_combobox = ttk.Combobox(
            self._lookup_type_frame,
            textvariable=self.parent.model.find.lookup_type,
            values=[
                "Refuel",
                "RRR",
                "Material Trader (Encoded)",
                "Material Trader (Manufactured)",
                "Material Trader (Raw)",
                "Tech Broker (Guardian)",
                "Tech Broker (Human)",
                "DSSA Carrier",
                "Exploration Carrier",
                "Interstellar Factor",
            ],
            state="readonly",
        )
        self._lookup_type_combobox.pack(side="left", fill="x")

        self.find_button = ttk.Button(self.tab, text="Find")
        self.find_button.pack(side="top", fill="x", expand=False, padx=5, pady=5)

        self.find_progress = ttk.Progressbar(
            self.tab, orient="horizontal", mode="indeterminate", length=300
        )
        self.find_progress.start()

        self.system_frame = ttk.LabelFrame(self.tab, text="System")
        self._system_label = ttk.Label(
            self.system_frame, textvariable=self.parent.model.find.results_system
        )
        self._system_label.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.system_contextmenu = tk.Menu(self.parent.root, tearoff=0)
        self.system_frame.bind(
            "<Button-3>",
            lambda event: self.system_contextmenu.post(event.x_root, event.y_root),
        )
        self._system_label.bind(
            "<Button-3>",
            lambda event: self.system_contextmenu.post(event.x_root, event.y_root),
        )

        self.location_frame = ttk.LabelFrame(self.tab, text="Location")
        self._location_label = ttk.Label(
            self.location_frame, textvariable=self.parent.model.find.results_location
        )
        self._location_label.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.location_contextmenu = tk.Menu(self.parent.root, tearoff=0)
        self.location_frame.bind(
            "<Button-3>",
            lambda event: self.location_contextmenu.post(event.x_root, event.y_root),
        )
        self._location_label.bind(
            "<Button-3>",
            lambda event: self.location_contextmenu.post(event.x_root, event.y_root),
        )


class RouteView:
    def __init__(self, parent: View):
        self.parent = parent

        self.tab = ttk.Frame(self.parent.tab_controller)
        self.parent.tab_controller.add(self.tab, text="Route")

        self._destination_frame = ttk.Frame(self.tab)
        self._destination_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self._destination_label = ttk.Label(
            self._destination_frame, text="Destination:"
        )
        self._destination_label.pack(side="left", padx=(0, 5))
        self.destination_input = SuggestionBox(
            self._destination_frame, textvariable=self.parent.model.route.destination
        )
        self.destination_input.pack(side="left", fill="x", expand=False)
        self.button = ttk.Button(self.tab, text="Route")
        self.button.pack(side="top", fill="x", expand=False, padx=5, pady=5)

        self.progress = ttk.Progressbar(
            self.tab, orient="horizontal", mode="indeterminate", length=300
        )
        self.progress.start()

        self.results = ttk.Frame(self.tab)
        self.next_system_frame = ttk.LabelFrame(self.results, text="Next System")
        self.next_system_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.next_system = ttk.Label(self.next_system_frame, text="")
        self.next_system.pack(side="top", fill="x", expand=False, padx=5, pady=5)

        self.jump_counter_frame = ttk.LabelFrame(self.results, text="Progress")
        self.jump_counter_frame.pack(side="top", fill="x", expand=False, padx=5, pady=5)
        self.jump_counter = ttk.Label(self.jump_counter_frame, text="")
        self.jump_counter.pack(side="top", fill="x", expand=False, padx=5, pady=5)

        self.refuel = ttk.Label(self.results, text="⛽ Refuel")
        self.neutron = ttk.Label(self.results, text="✨ Neutron")


class ConfirmationPopup:
    def __init__(
        self,
        root: Tk,
        title: str,
        message: str,
        on_confirm: Callable,
        on_cancel: Callable | None = None,
    ):
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        root.bell()

        self.popup = tk.Toplevel(root)
        self.popup.transient(root)
        self.popup.title(title)
        self.frame = ttk.Frame(self.popup, padding=12)
        self.frame.pack(fill="both", expand=True)

        tk.Label(self.frame, bitmap="question").grid(row=0, column=0, padx=8, pady=8)
        ttk.Label(self.frame, text=message, wraplength=400, justify="center").grid(
            row=0, column=1, padx=8, pady=8
        )

        self.buttons = ttk.Frame(self.frame)
        self.buttons.grid(row=1, column=0, columnspan=2, padx=(8, 0))

        self.confirm = ttk.Button(
            self.buttons, text="Yes", command=self._on_confirm
        ).pack(side="left", ipadx=8, padx=8, pady=(8, 0))
        self.cancel = ttk.Button(self.buttons, text="No", command=self._on_cancel).pack(
            side="left", ipadx=8, padx=8, pady=(8, 0)
        )

        self.popup.attributes("-topmost", True)
        self.popup.focus_set()

    def _on_confirm(self):
        self.popup.destroy()
        self.on_confirm()

    def _on_cancel(self):
        self.popup.destroy()
        if self.on_cancel:
            self.on_cancel()
