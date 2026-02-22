"""
support.py
----------
Represents a boundary condition applied to a node in the structural model.

Support types map directly to anastruct's SystemElements support methods:
- "fixed"    : add_support_fixed()    — fully restrained (Fx, Fy, Mz)
- "hinged"   : add_support_hinged()   — restrained translation (Fx, Fy), free rotation
- "roller_x" : add_support_roll()     — restrained in Y only, free to slide in X
- "roller_y" : add_support_roll()     — restrained in X only, free to slide in Y
- "spring"   : add_support_spring()   — elastic restraint with stiffness k

Only one support may be assigned per node. Assigning a second support
to the same node should replace the first — enforced at the Scene level.
"""

from dataclasses import dataclass, field
from typing import Literal
import uuid


def _new_id() -> int:
    """Generate a unique integer ID for a new support."""
    return uuid.uuid4().int & 0xFFFF


SupportType = Literal["fixed", "hinged", "roller_x", "roller_y", "spring"]


@dataclass
class Support:
    """
    A boundary condition applied to a single node.

    Attributes
    ----------
    node_id : int
        ID of the Node this support is applied to.
    support_type : SupportType
        The type of support, determining which anaStruct method is called.
    k : float
        Spring stiffness. Only used when support_type is "spring".
        Ignored for all other types.
    translation : int
        Spring translation direction for spring supports.
        1 = x-direction, 2 = y-direction, 3 = rotation.
        Only used when support_type is "spring".
    id : int
        Unique identifier. Auto-generated if not provided.
    """

    node_id: int
    support_type: SupportType = "hinged"
    k: float = 5000.0
    translation: int = 2
    id: int = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        """Serialize the support to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "node_id": self.node_id,
            "support_type": self.support_type,
            "k": self.k,
            "translation": self.translation,
        }

    @staticmethod
    def from_dict(data: dict) -> "Support":
        """Deserialize a support from a dictionary produced by to_dict()."""
        return Support(
            id=data["id"],
            node_id=data["node_id"],
            support_type=data["support_type"],
            k=data["k"],
            translation=data["translation"],
        )

    def __repr__(self) -> str:
        return f"Support(id={self.id}, node_id={self.node_id}, type={self.support_type})"