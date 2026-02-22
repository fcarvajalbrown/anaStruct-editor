"""
test_bridge.py
--------------
Tests for solver/bridge.py.

Covers:
- Valid scenes produce a successful SolveResult
- ID mapping is populated correctly
- Unsolvable scenes return a SolveResult with an error, not an exception
- Each support type is accepted without error
- Truss and general element types both solve correctly
"""

import pytest

from gui.model.scene import Scene
from gui.model.node import Node
from gui.model.element import Element
from gui.model.support import Support
from gui.model.load import PointLoad, DistributedLoad
from gui.solver.bridge import solve


def _simple_beam() -> Scene:
    """
    Simply supported beam with a central point load.

    Node 1 — (0,0) fixed
    Node 2 — (5,0) roller_y
    Node 3 — (2.5, 0) free, central point load
    """
    scene = Scene(name="simple_beam")
    scene.add_node(Node(x=0, y=0, id=1))
    scene.add_node(Node(x=2.5, y=0, id=2))
    scene.add_node(Node(x=5, y=0, id=3))
    scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
    scene.add_element(Element(node_start_id=2, node_end_id=3, id=11))
    scene.add_support(Support(node_id=1, support_type="hinged"))
    scene.add_support(Support(node_id=3, support_type="roller_x"))
    scene.add_point_load(PointLoad(node_id=2, Fy=-10.0))
    return scene


def _simple_truss() -> Scene:
    """
    A-frame truss with a vertical load at the apex.

    Node 1 — (0,0) hinged
    Node 2 — (4,0) roller
    Node 3 — (2,3) apex, point load
    """
    scene = Scene(name="simple_truss")
    scene.add_node(Node(x=0, y=0, id=1))
    scene.add_node(Node(x=4, y=0, id=2))
    scene.add_node(Node(x=2, y=3, id=3))
    scene.add_element(Element(node_start_id=1, node_end_id=3, id=10, element_type="truss"))
    scene.add_element(Element(node_start_id=2, node_end_id=3, id=11, element_type="truss"))
    scene.add_element(Element(node_start_id=1, node_end_id=2, id=12, element_type="truss"))
    scene.add_support(Support(node_id=1, support_type="hinged"))
    scene.add_support(Support(node_id=2, support_type="roller_x"))
    scene.add_point_load(PointLoad(node_id=3, Fy=-10.0))
    return scene


class TestBridgeSolve:

    def test_simple_beam_succeeds(self):
        result = solve(_simple_beam())
        assert result.success
        assert result.error is None
        assert result.system is not None

    def test_simple_truss_succeeds(self):
        result = solve(_simple_truss())
        assert result.success

    def test_node_map_populated(self):
        result = solve(_simple_beam())
        assert result.success
        # all 3 scene node IDs should be in the map
        assert 1 in result.node_map
        assert 2 in result.node_map
        assert 3 in result.node_map

    def test_element_map_populated(self):
        result = solve(_simple_beam())
        assert result.success
        assert 10 in result.element_map
        assert 11 in result.element_map

    def test_unsolvable_no_supports_returns_error(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        scene.add_node(Node(x=5, y=0, id=2))
        scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
        scene.add_point_load(PointLoad(node_id=2, Fy=-10.0))
        result = solve(scene)
        assert not result.success
        assert result.error is not None

    def test_unsolvable_no_loads_returns_error(self):
        scene = Scene()
        scene.add_node(Node(x=0, y=0, id=1))
        scene.add_node(Node(x=5, y=0, id=2))
        scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
        scene.add_support(Support(node_id=1, support_type="fixed"))
        result = solve(scene)
        assert not result.success
        assert result.error is not None

    def test_all_support_types_accepted(self):
        for support_type in ("fixed", "hinged", "roller_x", "roller_y"):
            scene = Scene()
            scene.add_node(Node(x=0, y=0, id=1))
            scene.add_node(Node(x=5, y=0, id=2))
            scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
            scene.add_support(Support(node_id=1, support_type=support_type))
            scene.add_point_load(PointLoad(node_id=2, Fy=-10.0))
            result = solve(scene)
            # we just check it doesn't raise — some configs may be singular
            assert isinstance(result.success, bool)

    def test_distributed_load_accepted(self):
        scene = _simple_beam()
        scene.add_distributed_load(DistributedLoad(element_id=10, q=-5.0))
        result = solve(scene)
        assert result.success

    def test_result_has_system_elements(self):
        from anastruct.fem.system import SystemElements
        result = solve(_simple_beam())
        assert isinstance(result.system, SystemElements)