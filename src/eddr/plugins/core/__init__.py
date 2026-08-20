
from tkinter import StringVar, ttk

import humanize


class CorePlugin:
    def __init__(self):
        pass

    def create_model(self, parent):
        self.model = CoreModel(self, parent)
        return self.model

    def create_view(self, parent):
        self.view = CoreView(self, parent)
        return self.view

    def create_controller(self, parent):
        self.controller = CoreController(self, parent)
        return self.controller

class CoreView:
    def __init__(self, plugin: CorePlugin, parent):
        self.plugin = plugin
        self.parent = parent

        self.tab_overview = ttk.Frame(self.parent.tab_controller)
        self.parent.tab_controller.add(self.tab_overview, text='Overview')

        self.frame_commander = ttk.Frame(self.tab_overview)
        self.frame_commander.grid(row=0, column=0, sticky='ew', pady=10)
        self.label_commander = ttk.Label(self.frame_commander, text='Commander:')
        self.label_commander.pack(side='left', padx=10)

        self.combobox_commander_var = StringVar(value='Waiting for game...')
        self.combobox_commander = ttk.Combobox(self.frame_commander, textvariable=self.combobox_commander_var, values=[])
        self.combobox_commander.pack(side='left')

        self.frame_location = ttk.Frame(self.tab_overview)
        self.frame_location.grid(row=2, column=0, padx=10, sticky='w')

        self.labelframe_system = ttk.LabelFrame(self.frame_location, text='System')
        self.labelframe_system.pack(side='left')
        self.label_system = ttk.Label(self.labelframe_system, text='')
        self.label_system.pack(side='left', padx=10, pady=10)

        self.labelframe_sublocation = ttk.LabelFrame(self.frame_location, text='Location')
        self.labelframe_sublocation.pack(side='left', padx=10, pady=10)
        self.label_sublocation = ttk.Label(self.labelframe_sublocation, text='')
        self.label_sublocation.pack(side='left', padx=10, pady=10)

    def update_active_cmdrs(self, cmdrs:list[str]):
        self.combobox_commander.configure(values=cmdrs)
        if len(cmdrs) == 1:
            self.combobox_commander_var.set(cmdrs[0])
        elif len(cmdrs) == 0:
            self.combobox_commander_var.set('Waiting for game...')

class CoreModel:
    def __init__(self, plugin: CorePlugin, parent):
        self.plugin = plugin
        self.parent = parent

        self.cmdr_names: dict[str, str] = {}
        self.cmdr_location: dict[str, dict] = {}

    def process_event(self, event, first_read:bool):
        if event['event'] == 'LoadGame':
            if not first_read or event['FID'] not in self.cmdr_names.keys():
                self.cmdr_names[event['FID']] = event['Commander']
        elif event['event'] == 'Location':
            self.cmdr_location[event['FID']] = {
                'system': event['StarSystem'],
                'sublocation_type': event.get('BodyType', None),
                'sublocation': event.get('Body', None),
            }
        elif event['event'] == 'FSDJump':
            self.cmdr_location[event['FID']] = { 
                'system': event['StarSystem'],
                'sublocation_type': None,
                'sublocation': None,
            }
        elif event['event'] == 'ApproachBody':
            self.cmdr_location[event['FID']] = {
                'system': event['StarSystem'],
                'sublocation_type': 'Planet',
                'sublocation': event['Body'],
            }
        elif event['event'] == 'LeaveBody':
            self.cmdr_location[event['FID']] = {
                'system': event['StarSystem'],
                'sublocation_type': None,
                'sublocation': None,
            }
        elif event['event'] == 'SupercruiseEntry':
            self.cmdr_location[event['FID']] = {
                'system': event['StarSystem'],
                'sublocation_type': None,
                'sublocation': None,
            }
        elif event['event'] == 'SupercruiseExit':
            self.cmdr_location[event['FID']] = {
                'system': event['StarSystem'],
                'sublocation_type': event['BodyType'],
                'sublocation': event['Body'],
            }
        elif event['event'] == 'CarrierJump':
            self.cmdr_location[event['FID']] = {
                'system': event['StarSystem'],
                'sublocation_type': 'FleetCarrier',
                'sublocation': event['StationName'],
            }

    def fid_from_name(self, search_name:str) -> str|None:
        for fid, name in self.cmdr_names.items():
            if search_name == name:
                return fid
        return None

    def get_active_cmdrs(self):
        active_journals = self.parent.generate_info_active_journals()
        if active_journals is None:
            return []
        return [self.cmdr_names[journal.fid] for journal in active_journals]

class CoreController:
    def __init__(self, plugin: CorePlugin, parent):
        self.plugin = plugin
        self.parent = parent

        self.plugin.view.combobox_commander_var.trace_add('write', lambda *args: self.set_watched_cmdr())

    def on_start(self):
        print('Core plugin started!')

    def on_redraw_fast(self):
        pass

    def on_journal_update(self):
        self.plugin.view.update_active_cmdrs(self.plugin.model.get_active_cmdrs())
        self.set_watched_cmdr()

    def set_watched_cmdr(self):
        selected_cmdr_name = self.plugin.view.combobox_commander_var.get()
        selected_cmdr_fid = self.plugin.model.fid_from_name(selected_cmdr_name)
        if selected_cmdr_fid is None:
            self.plugin.view.label_system.configure(text='')
            self.plugin.view.labelframe_sublocation.configure(text='Location')
            self.plugin.view.label_sublocation.configure(text='')
            return
        
        self.plugin.view.label_system.configure(text=self.plugin.model.cmdr_location[selected_cmdr_fid]['system'])
        if self.plugin.model.cmdr_location[selected_cmdr_fid]['sublocation_type'] is None:
            self.plugin.view.labelframe_sublocation.configure(text='Location')
            self.plugin.view.label_sublocation.configure(text='Supercruise')
            
        self.plugin.view.labelframe_sublocation.configure(text=self.sublocation_type_friendly(self.plugin.model.cmdr_location[selected_cmdr_fid]['sublocation_type']))
        self.plugin.view.label_sublocation.configure(text=self.plugin.model.cmdr_location[selected_cmdr_fid]['sublocation'])

    def sublocation_type_friendly(self, type:str) -> str:
        map = {
            'Null': 'Location',
            'Star': 'Star',
            'Planet': 'Planet',
            'PlanetaryRing': 'Ring',
            'Stellar Ring': 'Belt',
            'Station': 'Station',
            'AsteroidCluster': 'Cluster',
            'Fleet Carrier': 'Carrier',
        }
        return map.get(type, 'Location')

def init_plugin(builder):
    plugin = CorePlugin()

    builder.add_model(plugin.create_model)
    builder.add_view(plugin.create_view)
    builder.add_controller(plugin.create_controller)