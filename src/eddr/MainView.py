import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

class MainView:
    def __init__(self, root:tk.Tk):
        self.root = root

        style = ttk.Style(self.root)
        # Remove the focus border around tabs
        style.layout("Tab",
                    [('Notebook.tab', {'sticky': 'nswe', 'children':
                        [('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children':
                            [('Notebook.label', {'side': 'top', 'sticky': ''})],
                        })],
                    })]
                    )

        self.sheet_colors = {
            'table_bg':    '#1c1c1e',  # main window surface
            'header_bg':   "#202021",  # secondary surface
            'header_fg':   '#f3f3f5',  # light text
            'index_bg':    '#202021',  # secondary surface
            'index_fg':    "#C2C2C4",  # dim light text
            'top_left_bg':  '#202021',  # secondary surface
            'cell_bg':     '#1c1c1e',  # main window surface
            'cell_fg':     '#f3f3f5',  # light text
            'selected_bg': '#0a84ff',  # Fluent accent blue
            'selected_fg': '#ffffff',  # white text on selection
        }

        style = ttk.Style()
        style.element_create('Danger.TButton', 'from', 'sun-valley-dark', 'Button.TButton')
        style.layout('Danger.TButton', style.layout('Button.TButton'))
        style.configure('Danger.TButton', foreground='red')

        # Topbar
        self.top_bar = ttk.Frame(self.root)
        self.top_bar.pack(side='top', fill='x')

        # Clock
        self.clock_utc = ttk.Label(self.top_bar, width=8)
        self.clock_utc.pack(side='right', anchor='ne')

        # Version
        self.label_version = ttk.Label(self.top_bar)
        self.label_version.pack(side='left', anchor='nw', padx=10)

        self.tab_controller = ttk.Notebook(root)
        self.tab_controller.pack(expand=True, fill='both')

        self.plugins: dict[str, Any] = {}

    def add_plugin_view(self, plugin_name:str, view):
        self.plugins[plugin_name] = view