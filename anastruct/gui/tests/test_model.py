"""
test_model.py
-------------
Tests for Node, Element, Support, PointLoad, DistributedLoad, and Scene.

Covers:
- Dataclass construction and defaults
- to_dict() / from_dict() round-trips for every type
- Scene CRUD operations and cascading deletes
- Scene validation via is_solvable()
"""

import pytest
from gui.model.node import Node
from gui.model.element import Element
from gui.model.support import Support
from gui.model.load import PointLoad, DistributedLoad
from gui.model.scene import Scene


# ------------------------------------------------------------------ Node

class TestNode:
    def test_construction(self):
        n = Node(x=0.0, y=0.0)
        assert n.x == 0.0
        assert n.y == 0.0
        assert isinstance(n.id, int)

    def test_explicit_id(self):
        n = Node(x=1.0, y=2.0, id=42)
        assert n.id == 42

    def test_round_trip(self):
        n = Node(x=3.5, y=7.2, id=99)
        assert Node.from_dict(n.to_dict()) == n

    def test_unique_ids(self):
        ids = {Node(x=0, y=i).id for i in range(100)}
        assert len(ids) == 100


# --------------------------------------------------------------- Element

class TestElement:
    def test_construction_defaults(self):
        e = Element(node_start_id=1, node_end_id=2)
        assert e.EA == 15000.0
        assert e.EI == 5000.0
        assert e.element_type == "general"

    def test_truss_type(self):
        e = Element(node_start_id=1, node_end_id=2, element_type="truss")
        assert e.element_type == "truss"

    def test_round_trip(self):
        e = Element(node_start_id=10, node_end_id=20, EA=1000, EI=200, element_type="truss", id=5)
        assert Element.from_dict(e.to_dict()) == e


# --------------------------------------------------------------- Support

class TestSupport:
    def test_default_type(self):
        s = Support(node_id=1)
        assert s.support_type == "hinged"

    def test_all_types(self):
        for t in ("fixed", "hinged", "roller_x", "roller_y", "spring"):
            s = Support(node_id=1, support_type=t)
            assert s.support_type == t

    def test_round_trip(self):
        s = Support(node_id=3, support_type="fixed", id=7)
        assert Support.from_dict(s.to_dict()) == s

    def test_spring_fields(self):
        s = Support(node_id=1, support_type="spring", k=1000.0, translation=2)
        d = s.to_dict()
        assert d["k"] == 1000.0
        assert d["translation"] == 2


# ------------------------------------------------------------ PointLoad

class TestPointLoad:
    def test_defaults(self):
        p = PointLoad(node_id=1)
        assert p.Fx == 0.0
        assert p.Fy == 0.0
        assert p.load_case == "default"

    def test_round_trip(self):
        p = PointLoad(node_id=2, Fx=10.0, Fy=-5.0, load_case="live", id=11)
        assert PointLoad.from_dict(p.to_dict()) == p

    def test_type_key_in_dict(self):
        p = PointLoad(node_id=1)
        assert p.to_dict()["type"] == "point"


# ------------------------------------------------------- DistributedLoad

class TestDistributedLoad:
    def test_defaults(self):
        d = DistributedLoad(element_id=1)
        assert d.q == 0.0
        assert d.direction == "y"
        assert d.load_case == "default"

    def test_round_trip(self):
        d = DistributedLoad(element_id=3, q=-10.0, direction="x", load_case="wind", id=99)
        assert DistributedLoad.from_dict(d.to_dict()) == d

    def test_type_key_in_dict(self):
        d = DistributedLoad(element_id=1)
        assert d.to_dict()["type"] == "distributed"


# ----------------------------------------------------------------- Scene

def _simple_scene() -> Scene:
    """Build a minimal valid scene: 2 nodes, 1 element, 1 support, 1 load."""
    scene = Scene(name="test")
    n1 = scene.add_node(Node(x=0, y=0, id=1))
    n2 = scene.add_node(Node(x=5, y=0, id=2))
    scene.add_element(Element(node_start_id=n1.id, node_end_id=n2.id, id=10))
    scene.add_support(Support(node_id=n1.id, support_type="fixed"))
    scene.add_point_load(PointLoad(node_id=n2.id, Fy=-10.0))
    return scene


class TestScene:

    # --- add / get

    def test_add_and_get_node(self):
        scene = Scene()
        n = scene.add_node(Node(x=1, y=2, id=1))
        assert scene.get_node(1) is n

    def test_duplicate_node_raises(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        with pytest.raises(ValueError):
            scene.add_node(Node(x=1, y=1, id=1))

    def test_add_element_missing_node_raises(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        with pytest.raises(ValueError):
            scene.add_element(Element(node_start_id=1, node_end_id=99, id=10))

    # --- cascading delete

    def test_remove_node_cascades(self):
        scene = _simple_scene()
        scene.remove_node(2)
        assert scene.get_node(2) is None
        assert len(scene.elements) == 0
        assert len(scene.point_loads) == 0

    def test_remove_element_cascades_distributed_load(self):
        scene = _simple_scene()
        dl = scene.add_distributed_load(DistributedLoad(element_id=10, q=-5.0))
        scene.remove_element(10)
        assert scene.get_element(10) is None
        assert scene.get_distributed_load(dl.id) is None

    # --- support replacement

    def test_support_replacement(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        scene.add_support(Support(node_id=1, support_type="hinged"))
        scene.add_support(Support(node_id=1, support_type="fixed"))
        assert len(scene.supports) == 1
        assert scene.get_support(1).support_type == "fixed"

    # --- point load replacement

    def test_point_load_replacement_same_case(self):
        scene = _simple_scene()
        scene.add_point_load(PointLoad(node_id=2, Fy=-20.0, load_case="default"))
        loads_on_2 = [p for p in scene.point_loads if p.node_id == 2]
        assert len(loads_on_2) == 1
        assert loads_on_2[0].Fy == -20.0

    def test_point_load_different_cases_coexist(self):
        scene = _simple_scene()
        scene.add_point_load(PointLoad(node_id=2, Fy=-20.0, load_case="wind"))
        loads_on_2 = [p for p in scene.point_loads if p.node_id == 2]
        assert len(loads_on_2) == 2

    # --- is_solvable

    def test_solvable(self):
        ok, msg = _simple_scene().is_solvable()
        assert ok
        assert msg == "OK"

    def test_not_solvable_no_loads(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        scene.add_node(Node(x=5, y=0, id=2))
        scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
        scene.add_support(Support(node_id=1))
        ok, msg = scene.is_solvable()
        assert not ok
        assert "load" in msg.lower()

    def test_not_solvable_no_supports(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        scene.add_node(Node(x=5, y=0, id=2))
        scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
        scene.add_point_load(PointLoad(node_id=2, Fy=-10.0))
        ok, msg = scene.is_solvable()
        assert not ok
        assert "support" in msg.lower()

    # --- round-trip

    def test_scene_round_trip(self):
        scene = _simple_scene()
        scene.add_distributed_load(DistributedLoad(element_id=10, q=-5.0, id=50))
        restored = Scene.from_dict(scene.to_dict())
        assert restored.name == scene.name
        assert len(restored.nodes) == len(scene.nodes)
        assert len(restored.elements) == len(scene.elements)
        assert len(restored.supports) == len(scene.supports)
        assert len(restored.point_loads) == len(scene.point_loads)
        assert len(restored.distributed_loads) == len(scene.distributed_loads)

    def test_clear(self):
        scene = _simple_scene()
        scene.clear()
        assert len(scene.nodes) == 0
        assert len(scene.elements) == 0
        assert scene.name == "test"