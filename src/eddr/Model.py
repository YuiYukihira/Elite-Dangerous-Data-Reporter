

from queue import Empty
from typing import NamedTuple, Protocol, runtime_checkable

from eddr.JournalReader import JournalReader

@runtime_checkable
class PluginModel(Protocol):
    """Objects that are valid plugin models"""

    def process_event(self, event, first_read:bool):
        ...

class Model:
    def __init__(self, journal_paths:list[str], journal_reader:JournalReader|None=None):
        self.journal_reader = journal_reader if journal_reader else JournalReader(journal_paths)
        self.journal_paths = journal_reader.journal_paths if journal_reader else journal_paths

        self.plugins: dict[str, PluginModel] = {}

        self.first_read = True

    def add_plugin_model(self, plugin_name:str, plugin_model:PluginModel):
        assert isinstance(plugin_model, PluginModel), "plugin_model must be a valid PluginModel"
        self.plugins[plugin_name] = plugin_model

    def read_journals(self):
        self.journal_reader.read_journals()

        while True:
            try:
                event = self.journal_reader.processable_items.get_nowait()
                for plugin in self.plugins.values():
                    plugin.process_event(event, self.first_read)
            except Empty:
                break
        self.first_read = False

    class ActiveJournalInfo(NamedTuple):
        fid: str
        journal_file: str

    def generate_info_active_journals(self) -> list['Model.ActiveJournalInfo']|None:
        active = self.journal_reader.get_latest_active_journals()
        if active is None:
            return None
        return [
            self.ActiveJournalInfo(
                fid=fid,
                journal_file=journal
            )
            for fid, journal in active.items()
        ]