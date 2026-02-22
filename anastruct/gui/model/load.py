"""
load.py
-------
Represents forces and distributed loads applied to the structural model.

Two load types are supported, matching anastruct's load methods directly:

PointLoad   → ss.point_load(Fx, Fy, node_id)
    Applied at a node. Can have components in both X and Y directions.

DistributedLoad → ss.q_load(q, element_id, direction)
    Applied along an element. Uniform intensity q in a given direction.

Both types carry a load_case label so the bridge can group them when
anastruct's load combination features are used in the future.
"""

from dataclasses import dataclass, field
from typing import Literal
import uuid


def _new_id() -> int:
    """Generate a unique integer ID for a new load."""
    return uuid.uuid4().int & 0xFFFF


LoadDirection = Literal["element", "x", "y"]


@dataclass
class PointLoad:
    """
    A concentrated force applied at a node.

    Attributes
    ----------
    node_id : int
        ID of the Node this load is applied to.
    Fx : float
        Horizontal force component in kN (positive = right).
    Fy : float
        Vertical force component in kN (positive = up).
    load_case : str
        Load case label, e.g. "dead", "live", "wind". Default "default".
    id : int
        Unique identifier. Auto-generated if not provided.
    """

    node_id: int
    Fx: float = 0.0
    Fy: float = 0.0
    load_case: str = "default"
    id: int = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        """Serialize the point load to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "type": "point",
            "node_id": self.node_id,
            "Fx": self.Fx,
            "Fy": self.Fy,
            "load_case": self.load_case,
        }

    @staticmethod
    def from_dict(data: dict) -> "PointLoad":
        """Deserialize a PointLoad from a dictionary produced by to_dict()."""
        return PointLoad(
            id=data["id"],
            node_id=data["node_id"],
            Fx=data["Fx"],
            Fy=data["Fy"],
            load_case=data["load_case"],
        )

    def __repr__(self) -> str:
        return (
            f"PointLoad(id={self.id}, node_id={self.node_id}, "
            f"Fx={self.Fx}, Fy={self.Fy}, case={self.load_case})"
        )


@dataclass
class DistributedLoad:
    """
    A uniformly distributed load applied along an element.

    Attributes
    ----------
    element_id : int
        ID of the Element this load is applied to.
    q : float
        Load intensity in kN/m (positive = in the specified direction).
    direction : LoadDirection
        "element" applies along the element's local axis.
        "x" and "y" apply in global directions.
    load_case : str
        Load case label. Default "default".
    id : int
        Unique identifier. Auto-generated if not provided.
    """

    element_id: int
    q: float = 0.0
    direction: LoadDirection = "y"
    load_case: str = "default"
    id: int = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        """Serialize the distributed load to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "type": "distributed",
            "element_id": self.element_id,
            "q": self.q,
            "direction": self.direction,
            "load_case": self.load_case,
        }

    @staticmethod
    def from_dict(data: dict) -> "DistributedLoad":
        """Deserialize a DistributedLoad from a dictionary produced by to_dict()."""
        return DistributedLoad(
            id=data["id"],
            element_id=data["element_id"],
            q=data["q"],
            direction=data["direction"],
            load_case=data["load_case"],
        )

    def __repr__(self) -> str:
        return (
            f"DistributedLoad(id={self.id}, element_id={self.element_id}, "
            f"q={self.q}, dir={self.direction}, case={self.load_case})"
        )