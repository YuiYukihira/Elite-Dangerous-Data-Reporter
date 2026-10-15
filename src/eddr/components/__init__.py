import tkinter as tk
from collections.abc import Callable
from tkinter import StringVar, ttk
from typing import cast


class SuggestionBox(ttk.Combobox):
    def _tk(self, cls, parent):
        obj = cls(parent)
        obj.destroy()
        if cls is tk.Toplevel:
            obj._w = self.tk.call("ttk::combobox::PopdownWindow", self)
        else:
            obj._w = "{}.{}".format(parent._w, "f.l")
        return obj

    def __init__(self, parent, **kwargs):
        if kwargs.get("textvariable") is None:
            kwargs["textvariable"] = StringVar(value="")
        super().__init__(parent, **kwargs)
        self.textvariable = kwargs["textvariable"]
        self.popdown = self._tk(tk.Toplevel, parent)
        self.listbox = self._tk(tk.Listbox, self.popdown)

        self.bind("<KeyPress>", self._on_keypress, "+")
        self.listbox.bind("<Up>", self._on_keypress)

        self.on_debounced_keypress = cast(
            Callable[..., bool] | None, kwargs.get("on_debounced_keypressed", None)
        )
        self.timer: str | None = None
        self.textvariable.trace_add("write", lambda *_: self._var_written())

    def configure(self, *args, **kwargs):
        if on_debounced_keypress := kwargs.get("on_debounced_keypress", None):
            self.on_debounced_keypress = on_debounced_keypress
            kwargs.pop("on_debounced_keypress")
        return super().configure(*args, **kwargs)

    def _on_keypress(self, event):
        if event.widget == self:
            if event.keysym == "Down":
                self.after(0, self.listbox.focus_set)
            else:
                curselection = self.listbox.curselection()
                if event.keysym == "Up" and curselection[0] == 0:
                    self.popdown.withdraw()

    def _var_written(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
        self.timer = self.after(500, self._on_debounced_keypress)

    def _on_debounced_keypress(self):
        self.timer = None
        if self.on_debounced_keypress is not None and self.on_debounced_keypress():
            self.event_generate("<Down>")
            # self.listbox.focus_set()
            # self.focus_set()
