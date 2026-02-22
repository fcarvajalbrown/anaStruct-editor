"""
scene.py
--------
The Scene is the single source of truth for the entire structural model.

It holds all nodes, elements, supports, and loads, and provides
helper methods for adding, removing, and querying objects by ID.

The GUI reads and mutates the Scene exclusively through this interface.
The serializer and bridge both receive a Scene instance as input.

Design rules enforced here:
- Node IDs are unique across the scene.
- An element cannot reference a node ID that does not exist in the scene.
- Only one support per node is allowed; assigning a second replaces the first.
- Only one point load per node per load case is allowed; assigning a second replaces the first.
"""

from dataclasses import dataclass, field
from typing import Optional

from .node import Node
from .element import Element
from .support import Support
from .load import PointLoad, DistributedLoad


@dataclass
class Scene:
    """
    Container for the entire structural model.

    Attributes
    ----------
    nodes : list[Node]
        All nodes in the scene, in insertion order.
    elements : list[Element]
        All elements in the scene, in insertion order.
    supports : list[Support]
        All supports in the scene. At most one per node.
    point_loads : list[PointLoad]
        All point loads in the scene.
    distributed_loads : list[DistributedLoad]
        All distributed loads in the scene.
    name : str
        Optional human-readable name for the scene.
    """

    nodes: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    supports: list = field(default_factory=list)
    point_loads: list = field(default_factory=list)
    distributed_loads: list = field(default_factory=list)
    name: str = "untitled"

    # ------------------------------------------------------------------ nodes

    def add_node(self, node: Node) -> Node:
        """
        Add a node to the scene.

        Raises ValueError if a node with the same ID already exists.
        """
        if self.get_node(node.id) is not None:
            raise ValueError(f"Node with id={node.id} already exists.")
        self.nodes.append(node)
        return node

    def remove_node(self, node_id: int) -> None:
        """
        Remove a node and all elements, supports, and loads that reference it.

        Raises ValueError if the node does not exist.
        """
        if self.get_node(node_id) is None:
            raise ValueError(f"Node with id={node_id} not found.")
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.elements = [
            e for e in self.elements
            if e.node_start_id != node_id and e.node_end_id != node_id
        ]
        self.supports = [s for s in self.supports if s.node_id != node_id]
        self.point_loads = [p for p in self.point_loads if p.node_id != node_id]

    def get_node(self, node_id: int) -> Optional[Node]:
        """Return the Node with the given ID, or None if not found."""
        return next((n for n in self.nodes if n.id == node_id), None)

    # --------------------------------------------------------------- elements

    def add_element(self, element: Element) -> Element:
        """
        Add an element to the scene.

        Raises ValueError if either referenced node does not exist,
        or if an element with the same ID already exists.
        """
        if self.get_element(element.id) is not None:
            raise ValueError(f"Element with id={element.id} already exists.")
        if self.get_node(element.node_start_id) is None:
            raise ValueError(f"Start node id={element.node_start_id} not found.")
        if self.get_node(element.node_end_id) is None:
            raise ValueError(f"End node id={element.node_end_id} not found.")
        self.elements.append(element)
        return element

    def remove_element(self, element_id: int) -> None:
        """
        Remove an element and any distributed loads applied to it.

        Raises ValueError if the element does not exist.
        """
        if self.get_element(element_id) is None:
            raise ValueError(f"Element with id={element_id} not found.")
        self.elements = [e for e in self.elements if e.id != element_id]
        self.distributed_loads = [
            d for d in self.distributed_loads if d.element_id != element_id
        ]

    def get_element(self, element_id: int) -> Optional[Element]:
        """Return the Element with the given ID, or None if not found."""
        return next((e for e in self.elements if e.id == element_id), None)

    # --------------------------------------------------------------- supports

    def add_support(self, support: Support) -> Support:
        """
        Add a support to the scene.

        If a support already exists on the same node, it is replaced.
        """
        self.supports = [s for s in self.supports if s.node_id != support.node_id]
        self.supports.append(support)
        return support

    def remove_support(self, node_id: int) -> None:
        """Remove the support on the given node, if any."""
        self.supports = [s for s in self.supports if s.node_id != node_id]

    def get_support(self, node_id: int) -> Optional[Support]:
        """Return the Support on the given node, or None if not found."""
        return next((s for s in self.supports if s.node_id == node_id), None)

    # ------------------------------------------------------------ point loads

    def add_point_load(self, load: PointLoad) -> PointLoad:
        """
        Add a point load to the scene.

        If a point load already exists on the same node and load case,
        it is replaced.

        Raises ValueError if the referenced node does not exist.
        """
        if self.get_node(load.node_id) is None:
            raise ValueError(f"Node id={load.node_id} not found.")
        self.point_loads = [
            p for p in self.point_loads
            if not (p.node_id == load.node_id and p.load_case == load.load_case)
        ]
        self.point_loads.append(load)
        return load

    def remove_point_load(self, load_id: int) -> None:
        """Remove a point load by its ID."""
        self.point_loads = [p for p in self.point_loads if p.id != load_id]

    def get_point_load(self, load_id: int) -> Optional[PointLoad]:
        """Return the PointLoad with the given ID, or None if not found."""
        return next((p for p in self.point_loads if p.id == load_id), None)

    # ------------------------------------------------------- distributed loads

    def add_distributed_load(self, load: DistributedLoad) -> DistributedLoad:
        """
        Add a distributed load to the scene.

        Raises ValueError if the referenced element does not exist.
        """
        if self.get_element(load.element_id) is None:
            raise ValueError(f"Element id={load.element_id} not found.")
        self.distributed_loads.append(load)
        return load

    def remove_distributed_load(self, load_id: int) -> None:
        """Remove a distributed load by its ID."""
        self.distributed_loads = [d for d in self.distributed_loads if d.id != load_id]

    def get_distributed_load(self, load_id: int) -> Optional[DistributedLoad]:
        """Return the DistributedLoad with the given ID, or None if not found."""
        return next((d for d in self.distributed_loads if d.id == load_id), None)

    # ----------------------------------------------------------------- utility

    def clear(self) -> None:
        """Remove all objects from the scene, keeping the name."""
        self.nodes.clear()
        self.elements.clear()
        self.supports.clear()
        self.point_loads.clear()
        self.distributed_loads.clear()

    def is_solvable(self) -> tuple[bool, str]:
        """
        Check whether the scene meets the minimum requirements to be solved.

        Returns a (bool, message) tuple. If False, message explains why.
        """
        if len(self.nodes) < 2:
            return False, "At least 2 nodes are required."
        if len(self.elements) < 1:
            return False, "At least 1 element is required."
        if len(self.supports) < 1:
            return False, "At least 1 support is required."
        if len(self.point_loads) + len(self.distributed_loads) < 1:
            return False, "At least 1 load is required."
        return True, "OK"

    def to_dict(self) -> dict:
        """Serialize the entire scene to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "elements": [e.to_dict() for e in self.elements],
            "supports": [s.to_dict() for s in self.supports],
            "loads": (
                [p.to_dict() for p in self.point_loads]
                + [d.to_dict() for d in self.distributed_loads]
            ),
        }

    @staticmethod
    def from_dict(data: dict) -> "Scene":
        """Deserialize a Scene from a dictionary produced by to_dict()."""
        scene = Scene(name=data.get("name", "untitled"))
        for n in data.get("nodes", []):
            scene.nodes.append(Node.from_dict(n))
        for e in data.get("elements", []):
            scene.elements.append(Element.from_dict(e))
        for s in data.get("supports", []):
            scene.supports.append(Support.from_dict(s))
        for load in data.get("loads", []):
            if load["type"] == "point":
                scene.point_loads.append(PointLoad.from_dict(load))
            elif load["type"] == "distributed":
                scene.distributed_loads.append(DistributedLoad.from_dict(load))
        return scene

    def __repr__(self) -> str:
        return (
            f"Scene('{self.name}', "
            f"{len(self.nodes)} nodes, "
            f"{len(self.elements)} elements, "
            f"{len(self.supports)} supports, "
            f"{len(self.point_loads)} point loads, "
            f"{len(self.distributed_loads)} distributed loads)"
        )