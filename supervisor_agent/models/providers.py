# supervisor_agent/models/providers.py
from dataclasses import dataclass


@dataclass
class Provider:
    name: str
