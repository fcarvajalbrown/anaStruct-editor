"""
serializer.py
-------------
Writes a Scene to a .json file on disk.
"""

import json
from pathlib import Path

from ..model.scene import Scene


def save(scene: Scene, path: str | Path) -> None:
    """
    Serialize a Scene to a JSON file.

    Parameters
    ----------
    scene : Scene
        The scene to save.
    path : str or Path
        Destination file path. Extension should be .json.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scene.to_dict(), f, indent=2)