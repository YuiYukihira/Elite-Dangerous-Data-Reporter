import base64
import gzip
import json
import urllib.parse
from typing import TYPE_CHECKING

from eddr.db import CMDRLocationKind
from eddr.utils import APP_VERSION, open_file

if TYPE_CHECKING:
    from eddr.controller import Controller


class OverviewController:
    def __init__(self, parent: "Controller"):
        self.parent = parent

        self.parent.model.selected_cmdr_name.trace_add(
            "write", lambda *args: self._selected_cmdr_updated()
        )
        self.parent.view.overview.system_contextmenu.add_command(
            label="Copy",
            command=lambda: self.parent.view.copy_to_clipboard(
                self.parent.view.overview.system_name.get()
            ),
        )
        self.parent.view.overview.system_contextmenu.add_command(
            label="Open (Inara)",
            command=lambda: self.parent.open_system_on_inara(
                self.parent.view.overview.system_name.get()
            ),
        )

        self.parent.view.overview.location_contextmenu.add_command(
            label="Copy",
            command=lambda: self.parent.view.copy_to_clipboard(
                self.parent.view.overview.location_name.get()
            ),
        )
        self.parent.view.overview.location_contextmenu.add_command(
            label="Open (Inara)", command=self._open_location_on_inara
        )

        self.parent.view.overview.ship_contextmenu.add_command(
            label="Copy SLEF", command=self._copy_ship_slef
        )
        self.parent.view.overview.ship_contextmenu.add_command(
            label="Open (EDSY)", command=self._open_ship_on_EDSY
        )
        self.parent.view.overview.ship_contextmenu.add_command(
            label="Open (Coriolis)", command=self._open_ship_on_coriolis
        )

    def _copy_ship_slef(self):
        cmdr = self.parent.model.selected_cmdr
        if not cmdr:
            return

        slef = {
            "header": {
                "appName": "Elite Dangerous Data Reporter",
                "appVersion": str(APP_VERSION),
                "appURL": "https://github.com/YuiYukihira/Elite-Dangerous-Data-Reporter",
            },
            "data": cmdr.current_ship_slef.model_dump(mode="json"),
        }

        self.parent.view.copy_to_clipboard(json.dumps([slef]))

    def _open_ship_on_EDSY(self):
        cmdr = self.parent.model.selected_cmdr
        if not cmdr:
            return
        compressed = gzip.compress(
            str.encode(cmdr.current_ship_slef.model_dump_json(), encoding="utf-8")
        )
        encoded = base64.urlsafe_b64encode(compressed)
        url_params = urllib.parse.urlencode({"I": encoded.decode("utf-8")})
        open_file(f"https://edsy.org/#/{url_params}")

    def _open_ship_on_coriolis(self):
        cmdr = self.parent.model.selected_cmdr
        if not cmdr:
            return
        compressed = gzip.compress(
            str.encode(cmdr.current_ship_slef.model_dump_json(), encoding="utf-8")
        )
        encoded = base64.urlsafe_b64encode(compressed)
        url_params = urllib.parse.urlencode({"data": encoded.decode("utf-8")})
        open_file(f"https://coriolis.io/import?{url_params}")

    def _open_location_on_inara(self):
        cmdr = self.parent.model.selected_cmdr
        assert cmdr is not None
        assert (
            cmdr.location.root.location_type == CMDRLocationKind.Station
            or cmdr.location.root.location_type == CMDRLocationKind.Carrier
        )

        if cmdr.location.root.location_type == CMDRLocationKind.Carrier:
            search_string = cmdr.location.root.callsign
        else:
            search_string = (
                f"{cmdr.location.root.name} [{cmdr.location.root.system_name}]"
            )
        search_string = urllib.parse.urlencode({"search": search_string})

        open_file(f"https://inara.cz/elite/station/?{search_string}")

    def _selected_cmdr_updated(self):
        selected_cmdr = self.parent.model.selected_cmdr

        self.parent.view.overview.system_frame.pack_forget()
        self.parent.view.overview.location_frame.pack_forget()

        if not selected_cmdr:
            return

        self.parent.view.overview.ship_name.set(
            f"{selected_cmdr.current_ship_slef.ShipName} ({selected_cmdr.current_ship_slef.ShipIdent})"
        )
        self.parent.view.overview.silent_on.set(selected_cmdr.silent)

        if selected_cmdr.location.root.location_type == CMDRLocationKind.Unknown:
            return

        self.parent.view.overview.system_frame.pack(
            after=self.parent.view.overview._cmdr_selector_frame,
            side="top",
            fill="x",
            expand=False,
            padx=5,
            pady=5,
        )
        self.parent.view.overview.system_name.set(
            selected_cmdr.location.root.system_name
        )

        if selected_cmdr.location.root.location_type == CMDRLocationKind.Station:
            self.parent.view.overview.location_frame.pack(
                after=self.parent.view.overview.system_frame,
                side="top",
                fill="x",
                expand=False,
                padx=5,
                pady=5,
            )
            self.parent.view.overview.location_name.set(
                selected_cmdr.location.root.name
            )
        elif selected_cmdr.location.root.location_type == CMDRLocationKind.Carrier:
            self.parent.view.overview.location_frame.pack(
                after=self.parent.view.overview.system_frame,
                side="top",
                fill="x",
                expand=False,
                padx=5,
                pady=5,
            )
            carrier_name = (
                self.parent.model.get_carrier_name_by_market_id(
                    selected_cmdr.location.root.market_id
                )
                or selected_cmdr.location.root.callsign
            )
            self.parent.view.overview.location_name.set(carrier_name)
