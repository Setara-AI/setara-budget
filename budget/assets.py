"""
Assets - the folder system, the option sets, and the approval ledger.

The shape on disk is the shape of the process:

    <project>/
      01_script/                     the screenplay as delivered
      02_work/                       everything unapproved lives here
        characters/<NAME>/r1/opt_01.png ... opt_05.png
        locations/<NAME>/r1/...
        props/<NAME>/r1/...
        shots/<scene>/<shot>/plates/r1/...
        shots/<scene>/<shot>/clips/r1/...
      03_approved/                   the canonical library - one file per asset
        characters/<NAME>/<NAME>_v2.png
        ...
      04_delivery/
      ledger.json                    every option, every round, every decision

Two rules the code enforces rather than trusts:

  * Nothing enters 03_approved except through `approve()`, which requires a
    selected option. An approved asset is a fact with a name attached.
  * A rejection opens the NEXT round rather than overwriting the last one, so
    round 1 stays on disk and the revision count in the budget is a real count,
    not an estimate. That is the same accounting the estimate charges for.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum


class Kind(str, Enum):
    CHARACTER = "characters"
    LOCATION = "locations"
    PROP = "props"
    SHOT_PLATE = "shot_plates"
    CLIP = "clips"


class Status(str, Enum):
    PENDING = "pending"          # nothing generated yet
    GENERATED = "generated"      # options exist, nobody has looked
    IN_REVIEW = "in_review"      # with a reviewer
    APPROVED = "approved"        # selected, locked, copied to 03_approved
    REJECTED = "rejected"        # this round failed; the next round is open


WORK = "02_work"
APPROVED = "03_approved"
SCRIPT = "01_script"
DELIVERY = "04_delivery"
LEDGER = "ledger.json"


def slug(name: str) -> str:
    """A filesystem-safe, human-readable folder name."""
    keep = [c if (c.isalnum() or c in " -_") else " " for c in name.strip()]
    cleaned = "_".join("".join(keep).split())
    return cleaned.upper() or "UNNAMED"


@dataclass
class Decision:
    round: int
    action: str                  # generated | submitted | approved | rejected
    at: str
    by: str = ""
    note: str = ""
    option: str = ""


@dataclass
class Asset:
    id: str
    kind: Kind
    name: str
    scene: int | None = None
    shot: int | None = None
    status: Status = Status.PENDING
    round: int = 1
    options: dict = field(default_factory=dict)      # {round: [option filenames]}
    selected: str = ""                               # chosen option filename
    approved_path: str = ""
    history: list = field(default_factory=list)

    @property
    def rounds_used(self) -> int:
        return max([1] + [int(r) for r in self.options])

    @property
    def option_count(self) -> int:
        return sum(len(v) for v in self.options.values())

    def options_this_round(self) -> list:
        return list(self.options.get(str(self.round), []))


def asset_id(kind: Kind, name: str, scene=None, shot=None) -> str:
    parts = [kind.value, slug(name)]
    if scene is not None:
        parts.append(f"s{scene:03d}")
    if shot is not None:
        parts.append(f"sh{shot:03d}")
    return "/".join(parts)


# ---------------------------------------------------------------------------
# Paths (pure - no filesystem needed, so the layout is testable on its own)
# ---------------------------------------------------------------------------

def work_dir(asset: Asset, round_no: int | None = None) -> str:
    round_no = round_no or asset.round
    if asset.kind in (Kind.SHOT_PLATE, Kind.CLIP):
        leaf = "plates" if asset.kind is Kind.SHOT_PLATE else "clips"
        return os.path.join(WORK, "shots", f"scene_{asset.scene:03d}",
                            f"shot_{asset.shot:03d}", leaf, f"r{round_no}")
    return os.path.join(WORK, asset.kind.value, slug(asset.name), f"r{round_no}")


def approved_dir(asset: Asset) -> str:
    if asset.kind in (Kind.SHOT_PLATE, Kind.CLIP):
        leaf = "plates" if asset.kind is Kind.SHOT_PLATE else "clips"
        return os.path.join(APPROVED, "shots", f"scene_{asset.scene:03d}",
                            f"shot_{asset.shot:03d}", leaf)
    return os.path.join(APPROVED, asset.kind.value, slug(asset.name))


def approved_name(asset: Asset, extension: str) -> str:
    stem = slug(asset.name)
    if asset.kind in (Kind.SHOT_PLATE, Kind.CLIP):
        stem = f"scene_{asset.scene:03d}_shot_{asset.shot:03d}_{stem}"
    return f"{stem}_v{asset.round}{extension}"


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

class Library:
    """The project folder plus its ledger. Every state change goes through here."""

    def __init__(self, root: str, today: str | None = None):
        self.root = root
        self.today = today or date.today().isoformat()
        self.assets: dict[str, Asset] = {}
        self._load()

    # -- persistence ------------------------------------------------------
    @property
    def ledger_path(self) -> str:
        return os.path.join(self.root, LEDGER)

    def _load(self):
        if not os.path.exists(self.ledger_path):
            return
        with open(self.ledger_path) as fh:
            raw = json.load(fh)
        for record in raw.get("assets", []):
            record = dict(record)
            record["kind"] = Kind(record["kind"])
            record["status"] = Status(record["status"])
            record["history"] = [Decision(**d) for d in record.get("history", [])]
            self.assets[record["id"]] = Asset(**record)

    def save(self):
        os.makedirs(self.root, exist_ok=True)
        payload = {
            "updated": self.today,
            "assets": [
                {**asdict(a), "kind": a.kind.value, "status": a.status.value}
                for a in self.assets.values()
            ],
        }
        with open(self.ledger_path, "w") as fh:
            json.dump(payload, fh, indent=2)

    def scaffold(self):
        """Create the folder skeleton."""
        for folder in (SCRIPT, WORK, APPROVED, DELIVERY):
            os.makedirs(os.path.join(self.root, folder), exist_ok=True)
        for kind in (Kind.CHARACTER, Kind.LOCATION, Kind.PROP):
            os.makedirs(os.path.join(self.root, WORK, kind.value), exist_ok=True)
            os.makedirs(os.path.join(self.root, APPROVED, kind.value), exist_ok=True)
        os.makedirs(os.path.join(self.root, WORK, "shots"), exist_ok=True)
        os.makedirs(os.path.join(self.root, APPROVED, "shots"), exist_ok=True)
        return self.root

    # -- assets -----------------------------------------------------------
    def register(self, kind: Kind, name: str, scene=None, shot=None) -> Asset:
        key = asset_id(kind, name, scene, shot)
        if key not in self.assets:
            self.assets[key] = Asset(id=key, kind=kind, name=name, scene=scene, shot=shot)
        return self.assets[key]

    def get(self, key: str) -> Asset:
        return self.assets[key]

    def _log(self, asset: Asset, action: str, by="", note="", option=""):
        asset.history.append(Decision(round=asset.round, action=action, at=self.today,
                                      by=by, note=note, option=option))

    def add_options(self, asset: Asset, filenames: list, by: str = "") -> Asset:
        """Record the option set generated for this asset's current round."""
        if not filenames:
            raise ValueError("an option set cannot be empty")
        asset.options[str(asset.round)] = list(filenames)
        asset.status = Status.GENERATED
        asset.selected = ""
        self._log(asset, "generated", by=by, note=f"{len(filenames)} options")
        return asset

    def submit(self, asset: Asset, by: str = "") -> Asset:
        if asset.status is Status.PENDING:
            raise ValueError(f"{asset.id} has nothing to review yet")
        asset.status = Status.IN_REVIEW
        self._log(asset, "submitted", by=by)
        return asset

    def approve(self, asset: Asset, option: str, by: str = "", note: str = "",
                copy_file: bool = True) -> Asset:
        """Lock one option. This is the ONLY way into 03_approved."""
        available = asset.options_this_round()
        if option not in available:
            raise ValueError(f"{option!r} is not an option in round {asset.round} "
                             f"of {asset.id} ({available})")
        asset.selected = option
        asset.status = Status.APPROVED
        destination_dir = approved_dir(asset)
        extension = os.path.splitext(option)[1] or ".png"
        asset.approved_path = os.path.join(destination_dir, approved_name(asset, extension))
        if copy_file:
            self._copy_into_approved(asset, option)
        self._log(asset, "approved", by=by, note=note, option=option)
        return asset

    def reject(self, asset: Asset, by: str = "", note: str = "") -> Asset:
        """Fail this round and open the next one. Round N stays on disk."""
        asset.status = Status.REJECTED
        self._log(asset, "rejected", by=by, note=note)
        asset.round += 1
        asset.status = Status.PENDING
        asset.selected = ""
        return asset

    def _copy_into_approved(self, asset: Asset, option: str):
        source = os.path.join(self.root, work_dir(asset), option)
        if not os.path.exists(source):
            return                                  # ledger-only run (planning, tests)
        destination = os.path.join(self.root, asset.approved_path)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)

    # -- views ------------------------------------------------------------
    def by_status(self) -> dict:
        counts = {status: 0 for status in Status}
        for asset in self.assets.values():
            counts[asset.status] += 1
        return counts

    def outstanding(self) -> list:
        return [a for a in self.assets.values() if a.status is not Status.APPROVED]

    def revision_rounds_used(self) -> int:
        """Actual rounds burnt so far - the number to check the budget against."""
        return sum(a.rounds_used - 1 for a in self.assets.values())

    def options_generated(self) -> int:
        return sum(a.option_count for a in self.assets.values())

    def progress(self) -> dict:
        total = len(self.assets)
        approved = sum(1 for a in self.assets.values() if a.status is Status.APPROVED)
        return {
            "assets": total,
            "approved": approved,
            "outstanding": total - approved,
            "percent": (approved / total) if total else 0.0,
            "options_generated": self.options_generated(),
            "extra_rounds": self.revision_rounds_used(),
        }


def seed_from_breakdown(library: Library, breakdown, include_shots_for=None) -> Library:
    """Register every character, location and prop the script implies.

    include_shots_for: an optional plan, to also register per-shot plates and clips.
    """
    for name in breakdown.characters:
        library.register(Kind.CHARACTER, name)
    for name in breakdown.locations:
        library.register(Kind.LOCATION, name)
    for name in breakdown.props:
        library.register(Kind.PROP, name)

    if include_shots_for is not None:
        for scene_plan in include_shots_for.scenes:
            number = scene_plan.scene.scene.number
            for shot in range(1, scene_plan.shots + 1):
                label = f"{scene_plan.scene.scene.location} shot {shot}"
                library.register(Kind.SHOT_PLATE, label, scene=number, shot=shot)
                library.register(Kind.CLIP, label, scene=number, shot=shot)
    return library
