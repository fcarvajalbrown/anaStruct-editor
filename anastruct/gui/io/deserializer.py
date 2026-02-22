"""
deserializer.py
---------------
Reads a Scene from a .json file on disk.
"""

import json
from pathlib import Path

from ..model.scene import Scene


def load(path: str | Path) -> Scene:
    """
    Deserialize a Scene from a JSON file.

    Parameters
    ----------
    path : str or Path
        Source file path.

    Returns
    -------
    Scene
        The reconstructed scene.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is not valid JSON or the schema is unrecognized.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Scene.from_dict(data)