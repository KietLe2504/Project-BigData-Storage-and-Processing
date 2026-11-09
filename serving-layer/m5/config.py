import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    uri: str
    database: str

    @classmethod
    def from_env(cls):
        database = os.environ.get("M5_DATABASE", "aero_m5")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", database):
            raise ValueError("M5_DATABASE must contain only letters, digits, _ or -")
        return cls(os.environ.get("M5_MONGO_URI", "mongodb://localhost:27017"), database)
