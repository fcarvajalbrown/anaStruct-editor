"""
element.py
----------
Represents a structural element connecting two nodes in the model.

An Element is defined by its start and end node IDs, and carries the
material/section properties required by anastruct's SystemElements:
axial stiffness (EA) and flexural stiffness (EI).

Element types map directly to anastruct's element_type parameter:
- "general" : beam-column, resists both axial and bending (default)
- "truss"   : pin-jointed, resists axial force only (EI ignored)
"""

from dataclasses import dataclass, field
from typing import Literal
import uuid


def _new_id() -> int:
    """Generate a unique integer ID for a new element."""
    return uuid.uuid4().int & 0xFFFF


ElementType = Literal["general", "truss"]


@dataclass
class Element:
    """
    A structural member connecting two nodes.

    Attributes
    ----------
    node_start_id : int
        ID of the Node at the start of the element.
    node_end_id : int
        ID of the Node at the end of the element.
    EA : float
        Axial stiffness (E * A). Default matches anastruct's example value.
    EI : float
        Flexural stiffness (E * I). Ignored for truss elements.
    element_type : ElementType
        "general" for beam-columns, "truss" for pin-jointed members.
    id : int
        Unique identifier. Auto-generated if not provided.
    """

    node_start_id: int
    node_end_id: int
    EA: float = 15000.0
    EI: float = 5000.0
    element_type: ElementType = "general"
    id: int = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        """Serialize the element to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "node_start_id": self.node_start_id,
            "node_end_id": self.node_end_id,
            "EA": self.EA,
            "EI": self.EI,
            "element_type": self.element_type,
        }

    @staticmethod
    def from_dict(data: dict) -> "Element":
        """Deserialize an element from a dictionary produced by to_dict()."""
        return Element(
            id=data["id"],
            node_start_id=data["node_start_id"],
            node_end_id=data["node_end_id"],
            EA=data["EA"],
            EI=data["EI"],
            element_type=data["element_type"],
        )

    def __repr__(self) -> str:
        return (
            f"Element(id={self.id}, "
            f"{self.node_start_id} → {self.node_end_id}, "
            f"type={self.element_type}, EA={self.EA}, EI={self.EI})"
        )