import os
import re
import threading
import traceback
import urllib.parse
from datetime import UTC, datetime
from typing import cast

import requests
from sqlmodel import Session, col, select
from watchdog.events import (
    DirCreatedEvent,
    DirModifiedEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from eddr.controller.eddn import EDDNController
from eddr.controller.find import FindController
from eddr.controller.overview import OverviewController
from eddr.controller.route import RouteController
from eddr.db import (
    Carrier,
    CMDRLocation,
    CMDRLocationCarrier,
    CMDRLocationStation,
    CMDRLocationSuperCruise,
    CMDRLocationUnknown,
    CMDRStatus,
    engine,
)
from eddr.journal_reader import JournalEntry, JournalReader
from eddr.journal_schemas.base import JournalEntryKind
from eddr.journal_schemas.carrier_jump import CarrierJump
from eddr.journal_schemas.fsd_jump import FSDJump
from eddr.journal_schemas.loadout import FuelCapacity, Loadout
from eddr.journal_schemas.location import Location
from eddr.models import Model
from eddr.utils import APP_VERSION, open_file, parse_version_str
from eddr.view import ConfirmationPopup, View

JOURNAL_PATTERN = r"Journal\.\d{4}-\d{2}-\d{2}T\d{6}\.\d{2}\.log$"


class JournalEventHandler(FileSystemEventHandler):
    def __init__(self, controller: "Controller"):
        self.controller = controller

    def on_modified(
        self,
        event: DirModifiedEvent
        | FileModifiedEvent
        | DirCreatedEvent
        | FileCreatedEvent,
    ) -> None:
        assert isinstance(event.src_path, str)
        if event.is_directory:
            return
        if not re.fullmatch(JOURNAL_PATTERN, os.path.basename(event.src_path)):
            return
        print(f"file updated: {event.src_path}")
        self.controller._schedule_journal_update(event.src_path)

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self.on_modified(event)


class Controller:
    def __init__(self, journal_dirs: list[str], model: Model, view: View):
        self.journal_dirs = journal_dirs
        self.journal_reader = JournalReader(self._process_journal_msg)

        self.model = model
        self.view = view
        self.view.set_state("loading")

        self.overview = OverviewController(self)
        self.eddn = EDDNController(self)
        self.find = FindController(self)
        self.route = RouteController(self)

        self.update_pending_for_journal: dict[str, bool] = {}

        self._observer = Observer()
        self._observer.daemon = True

        self.warm_up = True

        self._check_version()

        threading.Thread(target=self._warm_up_journals, daemon=True).start()

    def _check_version(self):
        try:
            res = requests.get(
                "https://api.github.com/repos/YuiYukihira/Elite-Dangerous-Data-Reporter/releases/latest"
            )
            res.raise_for_status()
        except requests.RequestException as e:
            print(f"Error: Could not get latest version: {e}")
            return
        latest_version_str = res.json().get("tag_name")
        if not isinstance(latest_version_str, str):
            return
        latest_version = parse_version_str(latest_version_str)
        if not latest_version:
            return

        if APP_VERSION < latest_version:

            def _open_release_page():
                open_file(
                    "https://github.com/YuiYukihira/Elite-Dangerous-Data-Reporter/releases/latest"
                )

            ConfirmationPopup(
                self.view.root,
                "Update Available",
                f"New version available: {latest_version}\nGo to release page?",
                _open_release_page,
            )

    def _warm_up_journals(self):
        try:
            self._read_all_journals()
        except Exception:
            print(f"Exception while warming up journals:\n{traceback.format_exc()}")
        finally:
            self.warm_up = False
            self.view.add_callback(self.update_active_journals)
            self._observer.start()

    def _read_all_journals(self):
        handler = JournalEventHandler(self)

        journal_files = []
        for journal_dir in self.journal_dirs:
            self._observer.schedule(handler, journal_dir, recursive=False)

            files = os.listdir(journal_dir)
            files = sorted(files)
            journal_files += [
                os.path.join(journal_dir, i)
                for i in files
                if re.fullmatch(JOURNAL_PATTERN, i)
            ]

        print(f"Starting to read journals... {datetime.now(UTC)}")

        def update_progress(index: int, total: int):
            self.view.loading_view.progress["value"] = (index / total) * 100
            self.view.loading_view.counter.configure(text=f"{index}/{total}")

        for index, journal_file in enumerate(journal_files):
            self.view.add_callback(update_progress, index, len(journal_files))
            try:
                self.journal_reader.update_journal_file(journal_file)
            except Exception:
                print(
                    f"Exception while reading {journal_file}:\n{traceback.format_exc()}"
                )
        print(f"Journals processed {datetime.now(UTC)}")

    def _schedule_journal_update(self, journal_path: str):
        self.view.add_callback(self._schedule_debounced_journal_update, journal_path)

    def _schedule_debounced_journal_update(self, journal_path: str):
        if self.update_pending_for_journal.get(journal_path, False):
            return
        self.update_pending_for_journal[journal_path] = True
        self.view.add_callback(self._update_journal, journal_path)

    def _update_journal(self, journal_path: str):
        try:
            self.journal_reader.update_journal_file(journal_path)
            self.update_active_journals()
        finally:
            self.update_pending_for_journal[journal_path] = False

    def _process_journal_msg(self, msg: JournalEntry):
        with Session(engine) as db:
            if msg.entry.root.event == JournalEntryKind.CarrierStats:
                carrier_info = db.get(Carrier, msg.entry.root.CarrierID)
                if not carrier_info:
                    carrier_info = Carrier(
                        market_id=msg.entry.root.CarrierID,
                        callsign=msg.entry.root.Callsign,
                        name=msg.entry.root.Name,
                    )
                else:
                    carrier_info.name = msg.entry.root.Name
                db.add(carrier_info)
                db.commit()

            if not msg.active:
                return

            cmdr = db.get(CMDRStatus, msg.fid)
            is_selected_cmdr = (
                self.get_name_from_fid(msg.fid) == self.model.selected_cmdr_name.get()
            )
            cmdr_updated = False

            if not cmdr:
                cmdr = CMDRStatus(
                    fid=msg.fid,
                    name="Unknown CMDR",
                    location=CMDRLocation(root=CMDRLocationUnknown()),
                    last_updated=msg.entry.root.timestamp,
                    current_ship_slef=Loadout(
                        timestamp=datetime.now(UTC),
                        Ship="",
                        ShipID=0,
                        ShipName="",
                        ShipIdent="",
                        UnladenMass=0,
                        CargoCapacity=0,
                        MaxJumpRange=0,
                        FuelCapacity=FuelCapacity(Main=0.0, Reserve=0.0),
                        Rebuy=0,
                        Modules=[],
                    ),
                    gameversion="",
                    gamebuild="",
                    horizons=True,
                    odyssey=False,
                )

            if msg.entry.root.event == JournalEntryKind.Heading:
                cmdr.gameversion = msg.entry.root.gameversion
                cmdr.gamebuild = msg.entry.root.build
                cmdr_updated = True
            if msg.entry.root.event == JournalEntryKind.LoadGame:
                cmdr.horizons = msg.entry.root.Horizons
                cmdr.odyssey = msg.entry.root.Odyssey is True
            elif msg.entry.root.event == JournalEntryKind.Commander:
                cmdr.name = msg.entry.root.Name
                cmdr_updated = True
            elif msg.entry.root.event == JournalEntryKind.Location:
                self._process_location(cmdr, msg.fid, msg.entry.root)
                cmdr_updated = True
            elif msg.entry.root.event == JournalEntryKind.FSDJump:
                self._process_fsd_or_carrier_jump(cmdr, msg.fid, msg.entry.root)
                cmdr_updated = True
            elif (
                msg.entry.root.event == JournalEntryKind.SuperCruiseEntry
                or msg.entry.root.event == JournalEntryKind.Undocked
            ):
                assert not isinstance(cmdr.location.root, CMDRLocationUnknown)
                cmdr.location = CMDRLocation(
                    root=CMDRLocationSuperCruise(
                        system_name=cmdr.location.root.system_name,
                        system_address=cmdr.location.root.system_address,
                        system_coords=cmdr.location.root.system_coords,
                    )
                )
                cmdr_updated = True
            elif msg.entry.root.event == JournalEntryKind.SuperCruiseExit:
                pass
            elif msg.entry.root.event == JournalEntryKind.Docked:
                assert not isinstance(cmdr.location.root, CMDRLocationUnknown)
                if msg.entry.root.StationType == "FleetCarrier":
                    cmdr.location = CMDRLocation(
                        root=CMDRLocationCarrier(
                            system_name=cmdr.location.root.system_name,
                            system_address=cmdr.location.root.system_address,
                            system_coords=cmdr.location.root.system_coords,
                            callsign=cast(str, msg.entry.root.StationName),
                            market_id=cast(int, msg.entry.root.MarketID),
                        )
                    )
                else:
                    cmdr.location = CMDRLocation(
                        root=CMDRLocationStation(
                            system_name=cmdr.location.root.system_name,
                            system_address=cmdr.location.root.system_address,
                            system_coords=cmdr.location.root.system_coords,
                            name=cast(str, msg.entry.root.StationName),
                            market_id=cast(int, msg.entry.root.MarketID),
                        )
                    )
                cmdr_updated = True
            elif msg.entry.root.event == JournalEntryKind.Loadout:
                cmdr.current_ship_slef = msg.entry.root
                cmdr_updated = True

            db.add(cmdr)
            db.commit()

            if cmdr_updated and is_selected_cmdr:
                self.view.add_callback(self.overview._selected_cmdr_updated)

            self.eddn.process_entry(msg)
            self.route.process_journal_event(msg)

    def _process_fsd_or_carrier_jump(
        self, cmdr: CMDRStatus, fid: str, msg: FSDJump | CarrierJump
    ):
        cmdr.location = CMDRLocation(
            root=CMDRLocationSuperCruise(
                system_name=msg.StarSystem,
                system_address=msg.SystemAddress,
                system_coords=msg.StarPos,
            )
        )

    def _process_location(self, cmdr: CMDRStatus, fid: str, msg: Location):
        if msg.Docked and msg.StationType == "FleetCarrier":
            cmdr.location = CMDRLocation(
                root=CMDRLocationCarrier(
                    system_name=msg.StarSystem,
                    system_address=msg.SystemAddress,
                    system_coords=msg.StarPos,
                    callsign=cast(str, msg.StationName),
                    market_id=cast(int, msg.MarketID),
                )
            )
        elif msg.Docked:
            cmdr.location = CMDRLocation(
                root=CMDRLocationStation(
                    system_name=msg.StarSystem,
                    system_address=msg.SystemAddress,
                    system_coords=msg.StarPos,
                    name=cast(str, msg.StationName),
                    market_id=cast(int, msg.MarketID),
                )
            )
        else:
            cmdr.location = CMDRLocation(
                root=CMDRLocationSuperCruise(
                    system_name=msg.StarSystem,
                    system_address=msg.SystemAddress,
                    system_coords=msg.StarPos,
                )
            )

    def get_name_from_fid(self, fid: str) -> str | None:
        with Session(engine) as db:
            name = db.exec(
                select(CMDRStatus.name).where(CMDRStatus.fid == fid).limit(1)
            ).first()
            return name

    def update_active_journals(self):
        active_fids = self.journal_reader.active_fids()
        with Session(engine) as db:
            names = db.exec(
                select(CMDRStatus.name).where(col(CMDRStatus.fid).in_(active_fids))
            ).all()

            self.view.overview.cmdr_selector_combobox.configure(values=list(names))

            if len(names) == 0:
                self.view.set_state("inactive")
                return
            self.view.set_state("overview")
            if len(names) == 1:
                self.view.model.selected_cmdr_name.set(names[0])
                return
            if self.view.model.selected_cmdr_name.get() not in names:
                self.view.model.selected_cmdr_name.set(names[0])

    def open_system_on_inara(self, system_name: str):
        params = urllib.parse.urlencode({"search": system_name})
        open_file(f"https://inara.cz/elite/starsystem/?{params}")
