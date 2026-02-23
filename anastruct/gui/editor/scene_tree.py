"""
scene_tree.py
-------------
Left-side scene tree panel.

Lists all objects in the scene grouped by type. Clicking a row
selects that object and syncs with the canvas and inspector.

Like the inspector, this panel rebuilds every frame — simple and
always in sync with scene state without manual bookkeeping.

Object groups (in order):
    Nodes
    Elements
    Supports
    Point Loads
    Distributed Loads
"""

import dearpygui.dearpygui as dpg

from .state import EditorState


PANEL_WIDTH = 220
TREE_TAG = "scene_tree_panel"

# Colours for type labels
C_NODE    = (100, 160, 230, 255)
C_ELEMENT = (200, 200, 200, 255)
C_SUPPORT = (80,  180, 100, 255)
C_LOAD_P  = (220, 120,  60, 255)
C_LOAD_D  = (220, 180,  60, 255)
C_SELECTED_BG = (60, 80, 120, 120)


class SceneTree:
    """
    Scene tree panel.

    Parameters
    ----------
    state : EditorState
        Global editor state. SceneTree reads scene and mutates selection.
    """

    def __init__(self, state: EditorState) -> None:
        self.state = state

    # ------------------------------------------------------------------ build

    def build(self) -> None:
        """
        Create the scene tree child window.

        Call once during GUI setup inside a dpg window context.
        """
        with dpg.child_window(
            tag=TREE_TAG,
            width=PANEL_WIDTH,
            border=True,
            autosize_y=True,
        ):
            dpg.add_text("Scene", color=(180, 180, 180, 255))

    # ----------------------------------------------------------------- render

    def render(self) -> None:
        """
        Rebuild the scene tree to reflect current scene contents.

        Call every frame inside the Dear PyGui render loop.
        """
        dpg.delete_item(TREE_TAG, children_only=True)

        scene = self.state.scene

        _tree_header("Nodes", len(scene.nodes), parent=TREE_TAG)
        for node in scene.nodes:
            selected = (
                self.state.selection.object_type == "node"
                and self.state.selection.object_id == node.id
            )
            _tree_row(
                label=f"  Node {node.id}  ({node.x:.1f}, {node.y:.1f})",
                color=C_NODE,
                selected=selected,
                callback=lambda nid=node.id: self.state.select("node", nid),
                parent=TREE_TAG,
            )

        dpg.add_spacing(count=2, parent=TREE_TAG)

        _tree_header("Elements", len(scene.elements), parent=TREE_TAG)
        for element in scene.elements:
            selected = (
                self.state.selection.object_type == "element"
                and self.state.selection.object_id == element.id
            )
            type_tag = "T" if element.element_type == "truss" else "G"
            _tree_row(
                label=f"  [{type_tag}] {element.node_start_id}→{element.node_end_id}",
                color=C_ELEMENT,
                selected=selected,
                callback=lambda eid=element.id: self.state.select("element", eid),
                parent=TREE_TAG,
            )

        dpg.add_spacing(count=2, parent=TREE_TAG)

        _tree_header("Supports", len(scene.supports), parent=TREE_TAG)
        for support in scene.supports:
            selected = (
                self.state.selection.object_type == "support"
                and self.state.selection.object_id == support.id
            )
            _tree_row(
                label=f"  {support.support_type.upper()}  @ node {support.node_id}",
                color=C_SUPPORT,
                selected=selected,
                callback=lambda sid=support.id: self.state.select("support", sid),
                parent=TREE_TAG,
            )

        dpg.add_spacing(count=2, parent=TREE_TAG)

        _tree_header("Point Loads", len(scene.point_loads), parent=TREE_TAG)
        for load in scene.point_loads:
            selected = (
                self.state.selection.object_type == "point_load"
                and self.state.selection.object_id == load.id
            )
            _tree_row(
                label=f"  Fx={load.Fx:.1f} Fy={load.Fy:.1f} @ {load.node_id}",
                color=C_LOAD_P,
                selected=selected,
                callback=lambda lid=load.id: self.state.select("point_load", lid),
                parent=TREE_TAG,
            )

        dpg.add_spacing(count=2, parent=TREE_TAG)

        _tree_header("Distributed Loads", len(scene.distributed_loads), parent=TREE_TAG)
        for load in scene.distributed_loads:
            selected = (
                self.state.selection.object_type == "distributed_load"
                and self.state.selection.object_id == load.id
            )
            _tree_row(
                label=f"  q={load.q:.1f}kN/m  el.{load.element_id}",
                color=C_LOAD_D,
                selected=selected,
                callback=lambda lid=load.id: self.state.select("distributed_load", lid),
                parent=TREE_TAG,
            )

        # Empty scene hint
        total = (
            len(scene.nodes) + len(scene.elements)
            + len(scene.supports) + len(scene.point_loads)
            + len(scene.distributed_loads)
        )
        if total == 0:
            dpg.add_spacing(count=4, parent=TREE_TAG)
            dpg.add_text(
                "  Scene is empty.\n  Use the toolbar\n  to add objects.",
                parent=TREE_TAG,
                color=(120, 120, 120, 255),
            )


# ------------------------------------------------------------------ helpers

def _tree_header(title: str, count: int, parent: str) -> None:
    """Draw a section header with object count."""
    dpg.add_text(
        f"{title}  ({count})",
        parent=parent,
        color=(160, 160, 160, 255),
    )
    dpg.add_separator(parent=parent)


def _tree_row(
    label: str,
    color: tuple,
    selected: bool,
    callback,
    parent: str,
) -> None:
    """
    Draw a single selectable row in the scene tree.

    Uses a Dear PyGui selectable widget so the entire row is clickable.
    Color is applied to a text label drawn beside it.
    """
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_selectable(
            label=label,
            default_value=selected,
            callback=callback,
            width=PANEL_WIDTH - 16,
        )