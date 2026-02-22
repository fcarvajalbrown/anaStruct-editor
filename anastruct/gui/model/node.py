"""
node.py
-------
Represents a single point in 2D space within the structural model.

A Node is the fundamental building block of the scene. Elements connect
pairs of nodes, and supports/loads are applied to nodes by their ID.
"""

from dataclasses import dataclass, field
import uuid


def _new_id() -> int:
    """Generate a unique integer ID for a new node."""
    return uuid.uuid4().int & 0xFFFF


@dataclass
class Node:
    """
    A 2D point in world space.

    Attributes
    ----------
    x : float
        Horizontal position in meters (or consistent unit).
    y : float
        Vertical position in meters (or consistent unit).
    id : int
        Unique identifier. Auto-generated if not provided.
        Matches the node_id used by anastruct's SystemElements.
    """

    x: float
    y: float
    id: int = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        """Serialize the node to a JSON-compatible dictionary."""
        return {"id": self.id, "x": self.x, "y": self.y}

    @staticmethod
    def from_dict(data: dict) -> "Node":
        """Deserialize a node from a dictionary produced by to_dict()."""
        return Node(id=data["id"], x=data["x"], y=data["y"])

    def __repr__(self) -> str:
        return f"Node(id={self.id}, x={self.x}, y={self.y})"