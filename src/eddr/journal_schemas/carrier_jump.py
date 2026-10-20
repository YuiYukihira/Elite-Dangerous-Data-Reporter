from typing import Literal

from pydantic import Field

from eddr.journal_schemas.base import JournalEntryBase, JournalEntryKind


class CarrierJump(JournalEntryBase):
    event: Literal[JournalEntryKind.CarrierJump] = JournalEntryKind.CarrierJump
    StarSystem: str
    SystemAddress: int
    StarPos: tuple[float, float, float]
    Docked: bool = Field(default=False)
    StationName: str | None = Field(default=None)
    StationType: str | None = Field(default=None)
    MarketID: int | None = Field(default=None)
