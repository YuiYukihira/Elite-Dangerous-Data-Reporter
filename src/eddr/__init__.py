import importlib
import tkinter as tk
from argparse import ArgumentParser
import os
import sys
from tkinter import ttk
from typing import Any, Callable

import sv_ttk

from eddr.utility import getJournalPath, getPluginPaths
from eddr.JournalReader import JournalReader
from eddr.Model import Model, PluginModel
from eddr.config import WINDOW_SIZE
from eddr.Controller import Controller, PluginController
from eddr.MainView import MainView


class AppBuilder:
    def __init__(self, plugin_name:str, model:Model, view:MainView, controller:Controller):
        self.model = model
        self.view = view
        self.controller = controller
        self.plugin_name = plugin_name

    def add_model(self, model_init:Callable[[Model], PluginModel]):
        self.model.add_plugin_model(self.plugin_name, model_init(self.model))

    def add_view(self, view_init:Callable[[MainView], Any]):
        self.view.add_plugin_view(self.plugin_name, view_init(self.view))

    def add_controller(self, controller_init:Callable[[Controller], PluginController]):
        self.controller.add_plugin_controller(self.plugin_name, controller_init(self.controller))

def main() -> None:
    parser = ArgumentParser()
    parser.add_argument('-p', '--paths',
                        nargs='+', dest='paths', default=None,
                        help='Journal paths: override journal path(s)')
    args = parser.parse_args()
    env_journal_paths = os.getenv('EDDR_JOURNAL_PATHS')
    if args.paths:
        journal_paths = args.paths
    elif env_journal_paths is not None and env_journal_paths.strip():
        journal_paths = [path.strip() for path in env_journal_paths.split(';') if path.strip()]
        if not journal_paths:
            journal_paths = None
    else:
        journal_path = getJournalPath()
        journal_paths = [journal_path] if journal_path else None
    assert journal_paths is not None, f'No default journal path for platform {sys.platform}, please specify one with --paths or the EDDR_JOURNAL_PATHS environment variable'
    for journal_path in journal_paths:
        assert os.path.exists(journal_path), f'Journal path {journal_path} does not exist, please specify one with --paths or the EDDR_JOURNAL_PATHS environnment variable'

    if sys.platform == 'darwin':
        jr = JournalReader.load_from_cache(version=JournalReader.version_hash(), journal_paths=journal_paths)
        model = Model(journal_paths, journal_reader=jr)
    else:
        #try:
        #    import pyi_splash
        #    pyi_splash.update_text('Reading journals...')

        #    jr = JournalReader.load_from_cache(version=JournalReader.version_hash(), journal_paths=journal_paths)
        #    model = Model(journal_paths, journal_reader=jr)

        #    pyi_splash.close()
        #except ModuleNotFoundError:
        jr = JournalReader.load_from_cache(version=JournalReader.version_hash(), journal_paths=journal_paths)
        model = Model(journal_paths, journal_reader=jr)

    env_journal_paths = os.getenv('EDDR_JOURNAL_PATHS')
    if args.paths:
        journal_paths = args.paths
    elif env_journal_paths is not None and env_journal_paths.strip():
        journal_paths = [path.strip() for path in env_journal_paths.split(';') if path.strip()]
        if not journal_paths:
            journal_paths = None
    else:
        journal_path = getJournalPath()
        journal_paths = [journal_path] if journal_path else None
    assert journal_paths is not None, f'No default journal path for platform {sys.platform}, please specify one with --paths or the EDDR_JOURNAL_PATHS environment variable'
    for journal_path in journal_paths:
        assert os.path.exists(journal_path), f'Journal path {journal_path} does not exist, please specify one with --paths or the EDDR_JOURNAL_PATHS environnment variable'

    if sys.platform == 'darwin':
        jr = JournalReader.load_from_cache(version=JournalReader.version_hash(), journal_paths=journal_paths)
        model = Model(journal_paths, journal_reader=jr)
    else:
        #try:
        #    import pyi_splash
        #    pyi_splash.update_text('Reading journals...')

        #    jr = JournalReader.load_from_cache(version=JournalReader.version_hash(), journal_paths=journal_paths)
        #    model = Model(journal_paths, journal_reader=jr)

        #    pyi_splash.close()
        #except ModuleNotFoundError:
        jr = JournalReader.load_from_cache(version=JournalReader.version_hash(), journal_paths=journal_paths)
        model = Model(journal_paths, journal_reader=jr)

    root = tk.Tk()
    sv_ttk.use_dark_theme()
    root.title('Elite Dangerous Data Reporter')
    root.geometry(WINDOW_SIZE)

    view = MainView(root)
    controller = Controller(model, view)

    plugin_paths = getPluginPaths()
    plugins = []
    for plugin_path in plugin_paths:
        if not os.path.exists(plugin_path):
            continue
        plugins += [os.path.join(plugin_path, plugin_dir) for plugin_dir in os.listdir(plugin_path)]

    for plugin in plugins:
        name = os.path.basename(plugin)

        builder = AppBuilder(name, model, view, controller)

        spec = importlib.util.spec_from_file_location(name, os.path.join(plugin, '__init__.py'))
        plugin_module = importlib.util.module_from_spec(spec)
        sys.modules[name] = plugin_module
        spec.loader.exec_module(plugin_module)
        assert hasattr(plugin_module, 'init_plugin'), 'Your plugin must have a init_plugin function'

        plugin_module.init_plugin(builder)

    controller.start()

    root.mainloop()

if __name__ == '__main__':
    main()