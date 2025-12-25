"""Athlete model and gear catalog storage.

Handles athlete profile and equipment (gear) data storage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mykrok.lib.paths import (
    get_athlete_dir,
    get_athlete_json_path,
    get_avatar_path,
    get_gear_json_path,
)


@dataclass
class Athlete:
    """Represents a Strava athlete."""

    id: int
    username: str
    firstname: str | None = None
    lastname: str | None = None
    profile_url: str | None = None
    city: str | None = None
    country: str | None = None

    @classmethod
    def from_strava_athlete(cls, strava_athlete: Any) -> Athlete:
        """Create an Athlete from a stravalib athlete object.

        Args:
            strava_athlete: Athlete object from stravalib.

        Returns:
            Athlete instance.
        """
        return cls(
            id=strava_athlete.id,
            username=strava_athlete.username or f"athlete{strava_athlete.id}",
            firstname=strava_athlete.firstname,
            lastname=strava_athlete.lastname,
            profile_url=strava_athlete.profile,
            city=strava_athlete.city,
            country=strava_athlete.country,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert athlete to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "username": self.username,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "profile_url": self.profile_url,
            "city": self.city,
            "country": self.country,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Athlete:
        """Create an Athlete from a dictionary.

        Args:
            data: Dictionary with athlete data.

        Returns:
            Athlete instance.
        """
        return cls(
            id=data["id"],
            username=data["username"],
            firstname=data.get("firstname"),
            lastname=data.get("lastname"),
            profile_url=data.get("profile_url"),
            city=data.get("city"),
            country=data.get("country"),
        )


def save_athlete_profile(data_dir: Path, athlete: Athlete) -> Path:
    """Save athlete profile to athlete.json.

    Args:
        data_dir: Base data directory.
        athlete: Athlete instance to save.

    Returns:
        Path to athlete.json file.
    """
    athlete_dir = get_athlete_dir(data_dir, athlete.username)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    profile_path = get_athlete_json_path(athlete_dir)
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(athlete.to_dict(), f, indent=2)

    return profile_path


def load_athlete_profile(athlete_dir: Path) -> Athlete | None:
    """Load athlete profile from athlete.json.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Athlete instance or None if file doesn't exist.
    """
    profile_path = get_athlete_json_path(athlete_dir)

    if not profile_path.exists():
        return None

    with open(profile_path, encoding="utf-8") as f:
        data = json.load(f)

    return Athlete.from_dict(data)


def get_existing_avatar_path(athlete_dir: Path) -> Path | None:
    """Find existing avatar file with any extension.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to existing avatar or None.
    """
    for ext in ("jpg", "jpeg", "png", "gif", "webp"):
        avatar = get_avatar_path(athlete_dir, ext)
        if avatar.exists():
            return avatar
    return None


@dataclass
class Gear:
    """Represents a piece of equipment (bike or shoes)."""

    id: str
    name: str
    type: str  # "bike" or "shoes"
    brand: str | None = None
    model: str | None = None
    distance_m: float = 0.0
    primary: bool = False
    retired: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert gear to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "brand": self.brand,
            "model": self.model,
            "distance_m": self.distance_m,
            "primary": self.primary,
            "retired": self.retired,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Gear:
        """Create Gear from a dictionary.

        Args:
            data: Dictionary with gear data.

        Returns:
            Gear instance.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            brand=data.get("brand"),
            model=data.get("model"),
            distance_m=data.get("distance_m", 0.0),
            primary=data.get("primary", False),
            retired=data.get("retired", False),
        )


@dataclass
class GearCatalog:
    """Collection of all gear for an athlete."""

    items: list[Gear] = field(default_factory=list)

    def add_or_update(self, gear: Gear) -> None:
        """Add or update a gear item.

        Args:
            gear: Gear to add or update.
        """
        for i, existing in enumerate(self.items):
            if existing.id == gear.id:
                self.items[i] = gear
                return
        self.items.append(gear)

    def get(self, gear_id: str) -> Gear | None:
        """Get gear by ID.

        Args:
            gear_id: Gear ID.

        Returns:
            Gear instance or None.
        """
        for item in self.items:
            if item.id == gear_id:
                return item
        return None

    def to_dict(self) -> list[dict[str, Any]]:
        """Convert catalog to list of dictionaries.

        Returns:
            List of gear dictionaries.
        """
        return [g.to_dict() for g in self.items]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> GearCatalog:
        """Create GearCatalog from list of dictionaries.

        Args:
            data: List of gear dictionaries.

        Returns:
            GearCatalog instance.
        """
        catalog = cls()
        for item_data in data:
            catalog.items.append(Gear.from_dict(item_data))
        return catalog


def save_gear_catalog(data_dir: Path, username: str, catalog: GearCatalog) -> Path:
    """Save gear catalog to gear.json.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        catalog: Gear catalog to save.

    Returns:
        Path to gear.json file.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    gear_path = get_gear_json_path(athlete_dir)
    with open(gear_path, "w", encoding="utf-8") as f:
        json.dump(catalog.to_dict(), f, indent=2)

    return gear_path


def load_gear_catalog(data_dir: Path, username: str) -> GearCatalog:
    """Load gear catalog from gear.json.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        GearCatalog instance (empty if file doesn't exist).
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    gear_path = get_gear_json_path(athlete_dir)

    if not gear_path.exists():
        return GearCatalog()

    with open(gear_path, encoding="utf-8") as f:
        data = json.load(f)

    return GearCatalog.from_dict(data)


def update_gear_from_strava(
    data_dir: Path,
    username: str,
    gear_list: list[dict[str, Any]],
) -> GearCatalog:
    """Update gear catalog with data from Strava API.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        gear_list: List of gear dictionaries from Strava.

    Returns:
        Updated GearCatalog.
    """
    catalog = load_gear_catalog(data_dir, username)

    for gear_data in gear_list:
        gear = Gear(
            id=gear_data["id"],
            name=gear_data["name"],
            type=gear_data["type"],
            brand=gear_data.get("brand"),
            model=gear_data.get("model"),
            distance_m=gear_data.get("distance_m", 0.0),
            primary=gear_data.get("primary", False),
            retired=gear_data.get("retired", False),
        )
        catalog.add_or_update(gear)

    save_gear_catalog(data_dir, username, catalog)
    return catalog
