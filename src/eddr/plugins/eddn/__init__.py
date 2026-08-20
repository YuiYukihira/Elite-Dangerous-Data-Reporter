
from queue import Empty, Queue
from typing import Any

import requests


class EDDNPlugin:
    def __init__(self):
        pass

    def create_model(self, parent):
        self.model = EDDNModel(self, parent)
        return self.model

    def create_controller(self, parent):
        self.controller = EDDNController(self, parent)
        return self.controller

class EDDNModel:
    def __init__(self, plugin: EDDNPlugin, parent):
        self.plugin = plugin
        self.parent = parent

        self.game_version: dict[str, str] = {}
        self.build: dict[str, str] = {}
        self.has_horizons: dict[str, bool] = {}
        self.has_odyssey: dict[str, bool|None] = {}
        self.last_locations: dict[str, dict[str, Any]] = {}

        self.eddn_queue = Queue()

    def process_event(self, event, first_read:bool):
        if event['event'] == 'Location':
            self.process_location(event)
        elif event['event'] == 'LoadGame':
            self.process_load_game(event)
        elif event['event'] == 'Fileheader':
            self.process_file_header(event)
        elif event['event'] == 'Market' and not first_read:
            self.process_market(event)

    def process_location(self, location):
        self.last_locations[location['FID']] = {
            'star_system': location['StarSystem'],
            'system_address': location['SystemAddress'],
            'star_pos': location['StarPos'],
        }

    def process_load_game(self, load_game):
        self.has_horizons[load_game['FID']] = load_game['Horizons']
        self.has_odyssey[load_game['FID']] = load_game.get('Odyssey', None)

    def process_file_header(self, file_header):
        self.game_version[file_header['FID']] = file_header['gameversion']
        self.build[file_header['FID']] = file_header['build']

    def process_market(self, market_event):
        market_id = market_event['MarketID']

        market = self.parent.journal_reader.read_market_for_fid(market_event['FID'])
        if not (market['event'] == 'Market' and market['timestamp'] == market_event['timestamp'] and market['MarketID'] == market_id):
            return

        market_msg = {}
        market_msg['$schemaRef'] = "https://eddn.edcd.io/schemas/commodity/3"
        market_msg['header'] = {
            'uploaderID': self.parent.plugins['core'].cmdr_names[market_event['FID']],
            'gameversion': self.game_version[market_event['FID']],
            'gamebuild': self.build[market_event['FID']],
            'softwareName': 'EDDR',
            'softwareVersion': '0.1.0',
        }
        market_msg['message'] = {
            'horizons': self.has_horizons[market_event['FID']],
            'odyssey': self.has_odyssey[market_event['FID']],
            'timestamp': market_event['timestamp'],
            'systemName': market_event['StarSystem'],
            'stationName': market_event['StationName'],
            'stationType': market_event['StationType'],
            'marketId': market_id,
        }
        market_msg['message']['commodities'] = []

        for commodity in market['Items']:
            if commodity['Category'] == '$MARKET_category_non_marketable':
                continue
            if commodity.get('Legality', '') != '':
                continue

            new_commodity = {
                'name': commodity['Name'].removeprefix('$').removesuffix('_name;'),
                'meanPrice': commodity['MeanPrice'],
                'buyPrice': commodity['BuyPrice'],
                'stock': commodity['Stock'],
                'stockBracket': commodity['StockBracket'],
                'sellPrice': commodity['SellPrice'],
                'demand': commodity['Demand'],
                'demandBracket': commodity['DemandBracket'],
            }

            market_msg['message']['commodities'].append(new_commodity)
        self.eddn_queue.put(market_msg)

class EDDNController:
    def __init__(self, plugin: EDDNPlugin, parent):
        self.plugin = plugin
        self.parent = parent

    def on_redraw_fast(self):
        pass

    def on_journal_update(self):
        pass

    def on_start(self):
        print('EDDN plugin started!')

        self.parent.view.root.after(0, self._drain_eddn_queue)

    def _drain_eddn_queue(self):
        while True:
            try:
                msg = self.plugin.model.eddn_queue.get_nowait()
                self.parent.view.root.after(0, lambda: self.send_to_eddn(msg, 0))
            except Empty:
                break

        self.parent.view.root.after(1000, self._drain_eddn_queue)

    def send_to_eddn(self, msg, attempt:int):
        r = requests.post('https://eddn.edcd.io:4430/upload/', json=msg)
        if r.status_code == 400 or r.status_code == 426:
            print(f"EDDN not happy: {r.text}")
        elif r.status_code != 200:
            if attempt < 5:
                print(f'Couldn\'t send msg after 5 attempts: {msg}')
                return
            self.parent.view.root.after(60000, lambda *args: self.send_to_eddn(msg, attempt + 1))


def init_plugin(builder):
    plugin = EDDNPlugin()

    builder.add_model(plugin.create_model)
    builder.add_controller(plugin.create_controller)