import os
import json
import platform
from typing import Dict
from dataclasses import is_dataclass

# locals
from InstallRelease.utils import logger, EnhancedJSONEncoder, FilterDataclass


def platform_path(paths: dict, alt: str = ""):
    """provide path base on platform"""

    system = platform.system().lower()

    if os.environ.get("installState") == "test":
        return alt

    elif paths.get(system):
        p = paths.get(system)

        if not os.path.exists(os.path.dirname(p)):
            os.makedirs(os.path.dirname(p))
        return p
    else:
        logger.error(f"No state dir path set for {system}")
        exit(1)


class State:

    state: dict = {}
    cache: object

    def __init__(self, file_path: str, obj):
        self.state_file = file_path
        self.load(obj)

    def load(self, obj):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                _s = json.load(f)
                if len(_s) == 0:
                    return
                for k in _s:
                    if is_dataclass(obj):
                        self.state[k] = FilterDataclass(_s[k], obj=obj)

    def save(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=4, cls=EnhancedJSONEncoder)

    def get(self, key: str) -> Dict:
        return self.state[key]

    def set(self, key: str, value):
        self.state[key] = value

    def __getitem__(self, key: str) -> Dict:
        return self.state[key]

    def __setitem__(self, key: str, value: Dict):
        self.state[key] = value
        self.save()

    def __delitem__(self, key: str):
        del self.state[key]
        self.save()

    def __contains__(self, key: str) -> bool:
        return key in self.state

    def __len__(self) -> int:
        return len(self.state)

    def __repr__(self) -> str:
        return repr(self.state)

    def __eq__(self, other: object) -> bool:
        return self.state == other

    def __ne__(self, other: object) -> bool:
        return self.state != other
