"""
test_serializer.py
------------------
Tests for io/serializer.py and io/deserializer.py.

Covers:
- Save produces a valid JSON file
- Load reconstructs an identical Scene
- Full round-trip with all object types present
"""

import json
import pytest
from pathlib import Path

from gui.model.scene import Scene
from gui.model.node import Node
from gui.model.element import Element
from gui.model.support import Support
from gui.model.load import PointLoad, DistributedLoad
from gui.io.serializer import save
from gui.io.deserializer import load


def _full_scene() -> Scene:
    """Scene with every object type populated."""
    scene = Scene(name="serializer_test")
    scene.add_node(Node(x=0, y=0, id=1))
    scene.add_node(Node(x=5, y=0, id=2))
    scene.add_node(Node(x=5, y=5, id=3))
    scene.add_element(Element(node_start_id=1, node_end_id=2, id=10))
    scene.add_element(Element(node_start_id=2, node_end_id=3, id=11, element_type="truss"))
    scene.add_support(Support(node_id=1, support_type="fixed", id=20))
    scene.add_support(Support(node_id=3, support_type="roller_x", id=21))
    scene.add_point_load(PointLoad(node_id=2, Fx=5.0, Fy=-10.0, id=30))
    scene.add_distributed_load(DistributedLoad(element_id=10, q=-8.0, direction="y", id=40))
    return scene


class TestSerializer:

    def test_save_creates_file(self, tmp_path):
        path = tmp_path / "scene.json"
        save(_full_scene(), path)
        assert path.exists()

    def test_save_produces_valid_json(self, tmp_path):
        path = tmp_path / "scene.json"
        save(_full_scene(), path)
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_structure(self, tmp_path):
        path = tmp_path / "scene.json"
        save(_full_scene(), path)
        with open(path) as f:
            data = json.load(f)
        assert "name" in data
        assert "nodes" in data
        assert "elements" in data
        assert "supports" in data
        assert "loads" in data

    def test_round_trip_counts(self, tmp_path):
        original = _full_scene()
        path = tmp_path / "scene.json"
        save(original, path)
        restored = load(path)
        assert len(restored.nodes) == len(original.nodes)
        assert len(restored.elements) == len(original.elements)
        assert len(restored.supports) == len(original.supports)
        assert len(restored.point_loads) == len(original.point_loads)
        assert len(restored.distributed_loads) == len(original.distributed_loads)

    def test_round_trip_node_coordinates(self, tmp_path):
        original = _full_scene()
        path = tmp_path / "scene.json"
        save(original, path)
        restored = load(path)
        for orig_node in original.nodes:
            restored_node = restored.get_node(orig_node.id)
            assert restored_node is not None
            assert restored_node.x == orig_node.x
            assert restored_node.y == orig_node.y

    def test_round_trip_element_properties(self, tmp_path):
        original = _full_scene()
        path = tmp_path / "scene.json"
        save(original, path)
        restored = load(path)
        for orig_el in original.elements:
            rest_el = restored.get_element(orig_el.id)
            assert rest_el is not None
            assert rest_el.element_type == orig_el.element_type
            assert rest_el.EA == orig_el.EA
            assert rest_el.EI == orig_el.EI

    def test_round_trip_support_types(self, tmp_path):
        original = _full_scene()
        path = tmp_path / "scene.json"
        save(original, path)
        restored = load(path)
        for orig_sup in original.supports:
            rest_sup = restored.get_support(orig_sup.node_id)
            assert rest_sup is not None
            assert rest_sup.support_type == orig_sup.support_type

    def test_round_trip_loads(self, tmp_path):
        original = _full_scene()
        path = tmp_path / "scene.json"
        save(original, path)
        restored = load(path)
        orig_pl = original.point_loads[0]
        rest_pl = restored.get_point_load(orig_pl.id)
        assert rest_pl is not None
        assert rest_pl.Fx == orig_pl.Fx
        assert rest_pl.Fy == orig_pl.Fy
        orig_dl = original.distributed_loads[0]
        rest_dl = restored.get_distributed_load(orig_dl.id)
        assert rest_dl is not None
        assert rest_dl.q == orig_dl.q
        assert rest_dl.direction == orig_dl.direction

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load(tmp_path / "nonexistent.json")

    def test_load_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json at all {{{")
        with pytest.raises(Exception):
            load(path)

    def test_name_preserved(self, tmp_path):
        path = tmp_path / "scene.json"
        save(_full_scene(), path)
        restored = load(path)
        assert restored.name == "serializer_test"