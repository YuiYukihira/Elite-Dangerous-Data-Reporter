import json
import threading
import traceback
import urllib.parse
from typing import TYPE_CHECKING

import requests
from sqlmodel import Session

from eddr.db import Carrier, CMDRLocationKind, CMDRStatus, engine
from eddr.utils import open_file

if TYPE_CHECKING:
    from eddr.controller import Controller


class FindController:
    def __init__(self, parent: "Controller"):
        self.parent = parent
        self.view = self.parent.view.find_view
        self.model = self.parent.model.find

        self.view.find_button.configure(command=self._do_find)
        self.view.system_contextmenu.add_command(
            label="Copy",
            command=lambda: self.parent.view.copy_to_clipboard(
                self.model.results_system.get()
            ),
        )
        self.view.system_contextmenu.add_command(
            label="Open (Inara)",
            command=lambda: self.parent.open_system_on_inara(
                self.model.results_system.get()
            ),
        )

        self.view.location_contextmenu.add_command(
            label="Copy",
            command=lambda: self.parent.view.copy_to_clipboard(
                self.model.results_location.get()
            ),
        )
        self.view.location_contextmenu.add_command(
            label="Open (Inara)", command=self._open_location_on_inara
        )

    def _open_location_on_inara(self):
        search_string = urllib.parse.urlencode(
            {"search": self.model.results_location_ref}
        )
        open_file(f"https://inara.cz/elite/station/?{search_string}")

    def _do_find(self):
        cmdr = self.parent.model.selected_cmdr
        if not cmdr or cmdr.location.root.location_type == CMDRLocationKind.Unknown:
            return

        self.view._lookup_type_combobox.configure(state="disabled")
        self.view.find_button.configure(state="disabled")
        self.view.find_progress.pack(
            after=self.view.find_button,
            side="top",
            fill="x",
            expand=False,
            padx=5,
            pady=5,
        )

        search_type = self.model.lookup_type.get()
        search_params = self._get_search_params(cmdr, search_type)
        search_string = json.dumps(search_params)

        if self.model.last_search_params == search_string:
            self.view._lookup_type_combobox.configure(state="normal")
            self.view.find_button.configure(state="normal")
            self.view.find_progress.pack_forget()
            return

        def _do_query():
            res = requests.post(
                "https://www.spansh.co.uk/api/stations/search/save",
                data=search_string,
                timeout=30,
            )
            if res.status_code != 200:
                raise Exception(f"Spansh not happy: {res.text}")
            res = res.json()
            ref_string = res["search_reference"]
            res = requests.get(
                f"https://www.spansh.co.uk/api/stations/search/recall/{ref_string}",
                timeout=30,
            )
            if res.status_code != 200:
                raise Exception(f"Spansh not happy: {res.text}")
            res = res.json()["results"]
            if not res:
                return
            closest = res[0]

            carrier_name = closest.get("carrier_name", None)

            if carrier_name:
                with Session(engine) as db:
                    carrier = db.get(Carrier, closest["market_id"])
                    if not carrier:
                        carrier = Carrier(
                            market_id=closest["market_id"],
                            callsign=closest["name"],
                            name=carrier_name,
                        )
                    else:
                        carrier.callsign = closest["name"]
                        carrier.name = carrier_name
                    db.add(carrier)
                    db.commit()

            def update_ui():
                self.model.results_type = "FleetCarrier" if carrier_name else "Station"
                self.model.results_system.set(closest["system_name"])
                self.model.results_location.set(
                    f"{carrier_name} ({closest['name']})"
                    if carrier_name
                    else closest["name"]
                )
                self.model.results_location_ref = (
                    closest["name"]
                    if carrier_name
                    else f"{closest['name']} [{closest['system_name']}]"
                )

                self.view.find_progress.pack_forget()
                self.view.system_frame.pack(
                    after=self.view.find_button,
                    side="top",
                    fill="x",
                    expand=False,
                    padx=5,
                    pady=5,
                )
                self.view.location_frame.pack(
                    after=self.view.system_frame,
                    side="top",
                    fill="x",
                    expand=False,
                    padx=5,
                    pady=5,
                )
                self.view._lookup_type_combobox.configure(state="normal")
                self.view.find_button.configure(state="normal")

            self.model.last_search_params = search_string

            self.parent.view.add_callback(update_ui)

        threading.Thread(target=self._run_query, args=(_do_query,), daemon=True).start()

    def _run_query(self, fn):
        try:
            fn()
        except Exception:
            traceback.print_exc()
        finally:

            def update_ui():
                self.view.find_progress.pack_forget()
                self.view._lookup_type_combobox.configure(state="normal")
                self.view.find_button.configure(state="normal")

            self.view.parent.add_callback(update_ui)

    def _get_search_params(self, cmdr: CMDRStatus, search_type: str):
        assert cmdr.location.root.location_type != CMDRLocationKind.Unknown
        search_params = {
            "sort": [
                {"distance": {"direction": "asc"}},
                {"distance_to_arrival": {"direction": "asc"}},
            ],
            "size": 10,
            "page": 0,
            "reference_coords": {
                "x": cmdr.location.root.system_coords[0],
                "y": cmdr.location.root.system_coords[1],
                "z": cmdr.location.root.system_coords[2],
            },
        }

        if search_type == "Refuel":
            search_params["filters"] = {"services": [{"name": {"value": ["Refuel"]}}]}
        elif search_type == "RRR":
            search_params["filters"] = {
                "services": [{"name": {"value": ["Refuel", "Repair", "Restock"]}}]
            }
        elif search_type == "Material Trader (Encoded)":
            search_params["filters"] = {"material_trader": {"value": ["Encoded"]}}
        elif search_type == "Material Trader (Manufactured)":
            search_params["filters"] = {"material_trader": {"value": ["Manufactured"]}}
        elif search_type == "Material Trader (Raw)":
            search_params["filters"] = {"material_trader": {"value": ["Raw"]}}
        elif search_type == "Tech Broker (Guardian)":
            search_params["filters"] = {"technology_broker": {"value": ["Guardian"]}}
        elif search_type == "Tech Broker (Human)":
            search_params["filters"] = {"technology_broker": {"value": ["Human"]}}
        elif search_type == "DSSA Carrier":
            search_params["filters"] = {"is_dssa_carrier": {"value": True}}
        elif search_type == "Exploration Carrier":
            search_params["filters"] = {
                "carrier_docking_access": {"value": ["All"]},
                "updated_at": {
                    "comparison": "<=>",
                    "value": ["now-1d", "now"],
                },
                "services": [
                    {
                        "name": {
                            "value": [
                                "Refuel",
                                "Repair",
                                "Universal Cartographics",
                                "Vista Genomics",
                            ]
                        }
                    }
                ],
            }
        elif search_type == "Interstellar Factor":
            search_params["filters"] = {
                "services": [{"name": {"value": ["Interstellar Factors Contact"]}}]
            }
        return search_params
