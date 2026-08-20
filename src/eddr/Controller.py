

from datetime import datetime, timezone
import os
import pickle
from queue import Empty, Queue
import threading
from tkinter import TclError, Tk
import traceback
from typing import Any, Callable, Protocol, runtime_checkable

from watchdog.events import DirCreatedEvent, DirModifiedEvent, FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler

from eddr.Model import Model
from watchdog.observers import Observer

from eddr.MainView import MainView
from eddr.config import SAVE_CACHE_INTERVAL
from eddr.utility import getCachePath

class JournalEventHandler(FileSystemEventHandler):
    def __init__(self, controller: 'Controller'):
        self.controller = controller

    def on_modified(self, event: DirCreatedEvent | FileCreatedEvent | DirModifiedEvent | FileModifiedEvent):
        assert isinstance(event.src_path, str)
        if not event.is_directory and event.src_path.endswith('.log'):
            self.controller._schedule_journal_update()

    def on_created(self, event):
        return self.on_modified(event)

@runtime_checkable
class PluginController(Protocol):
    def on_journal_update(self):
        ...

    def on_redraw_fast(self):
        ...

    def on_start(self):
        ...
        
class Controller:
    def __init__(self, model:Model, view:MainView):
        self.view = view
        self.model = model
        self._ui_callbacks = Queue()
        self.view.root.after(0, self._drain_ui_callbacks)

        self.plugins: dict[str, PluginController] = {}

    def add_plugin_controller(self, name:str, plugin_controller:PluginController):
        assert isinstance(plugin_controller, PluginController)
        self.plugins[name] = plugin_controller

    def start(self):
        self._observer = Observer()
        handler = JournalEventHandler(self)
        for jp in self.model.journal_paths:
            watch_dir = jp if os.path.isdir(jp) else os.path.dirname(jp)
            self._observer.schedule(handler, watch_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()

        for plugin in self.plugins.values():
            plugin.on_start()

        self.redraw_fast()

        # initial load
        self.update_journals()
        for plugin in self.plugins.values():
            plugin.on_journal_update()

        self._start_cache_save_loop()

    def update_journals(self):
        try:
            self.model.read_journals()
        except Exception as e:
            self.view.root.destroy()
            print(e)
            raise e

    def redraw_fast(self):
        try:
            now = datetime.now(timezone.utc)
            self.update_time(now)

            for plugin in self.plugins.values():
                plugin.on_redraw_fast()
        except Exception as e:
            print(e)
            pass
        else:
            self.view.root.after(1000, self.redraw_fast)

    def update_time(self, now):
        self.view.clock_utc.configure(text=now.strftime('%H:%M:%S'))

    def _schedule_journal_update(self):
        self.queue_ui_callback(self._schedule_journal_update_on_ui)

    def _schedule_journal_update_on_ui(self):
        # debounce
        if getattr(self, '_journal_update_pending', False):
            return
        self._journal_update_pending = True
        self.view.root.after(0, self._perform_journal_update)

    def queue_ui_callback(self, callback: Callable[..., Any], *args: Any, **kwargs: Any):
        self._ui_callbacks.put((callback, args, kwargs))


    def _drain_ui_callbacks(self):
        while True:
            try:
                callback, args, kwargs = self._ui_callbacks.get_nowait()
            except Empty:
                break
            try:
                callback(*args, **kwargs)
            except Exception:
                print(f'Error running UI callback:\n{traceback.format_exc()}')
        try:
            self.view.root.after(50, self._drain_ui_callbacks)
        except TclError:
            pass

    def _perform_journal_update(self):
        self._journal_update_pending = False
        self.update_journals()
        for plugin in self.plugins.values():
            plugin.on_journal_update()

    def _schedule_cache_save(self):
        self.view.root.after(SAVE_CACHE_INTERVAL, self._start_cache_save_loop)

    def _start_cache_save_loop(self):
        self._save_cache_async(schedule_next=True)

    def _save_cache_async(self, schedule_next:bool):
        cache_path = getCachePath(self.model.journal_reader.version_hash(), self.model.journal_reader.journal_paths)
        if cache_path is not None:
            threading.Thread(target=self._save_cache, args=(cache_path, schedule_next), daemon=True).start()

    def _save_cache(self, cache_path:str, schedule_next:bool=False):
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'wb') as f:
                pickle.dump(self.model.journal_reader, f)
        except Exception as e:
            print(e)
        finally:
            if schedule_next:
                self.queue_ui_callback(self._schedule_cache_save)