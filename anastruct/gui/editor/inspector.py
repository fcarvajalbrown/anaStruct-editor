"""
inspector.py
------------
Right-side property inspector panel.

Displays and edits the properties of the currently selected object.
Rebuilds its contents every frame based on EditorState.selection,
so it always reflects the current selection without manual sync.

Each object type gets its own _draw_*_inspector() method.
All edits call state.mark_dirty() and update the scene directly.

Dear PyGui immediate-mode pattern
----------------------------------
We do NOT store widget tags for each field. Instead we delete and
recreate the inspector group every frame. This is simpler than
maintaining a registry of tags and updating values manually.
The performance cost is negligible for a property panel this size.
"""

import dearpygui.dearpygui as dpg

from .state import EditorState
from ..model.node import Node
from ..model.element import Element
from ..model.support import Support, SupportType
from ..model.load import PointLoad, DistributedLoad


# Panel width matches the right sidebar defined in main.py
PANEL_WIDTH = 280

# Tag for the child window that contains the inspector
INSPECTOR_TAG = "inspector_panel"


class Inspector:
    """
    Property inspector panel.

    Parameters
    ----------
    state : EditorState
        Global editor state. Inspector reads selection and mutates scene.
    """

    def __init__(self, state: EditorState) -> None:
        self.state = state

    # ------------------------------------------------------------------ build

    def build(self) -> None:
        """
        Create the inspector child window.

        Call once during GUI setup inside a dpg window context.
        """
        with dpg.child_window(
            tag=INSPECTOR_TAG,
            width=PANEL_WIDTH,
            border=True,
            autosize_y=True,
        ):
            dpg.add_text("Nothing selected.", tag="inspector_empty_label")

    # ----------------------------------------------------------------- render

    def render(self) -> None:
        """
        Rebuild the inspector contents to match the current selection.

        Call every frame inside the Dear PyGui render loop.
        """
        # Clear previous contents
        dpg.delete_item(INSPECTOR_TAG, children_only=True)

        obj = self.state.selected_object()
        if obj is None:
            dpg.add_text(
                "Nothing selected.\n\nClick an object\nto inspect it.",
                parent=INSPECTOR_TAG,
                color=(140, 140, 140, 255),
            )
            return

        t = self.state.selection.object_type

        if t == "node":
            self._draw_node_inspector(obj)
        elif t == "element":
            self._draw_element_inspector(obj)
        elif t == "support":
            self._draw_support_inspector(obj)
        elif t == "point_load":
            self._draw_point_load_inspector(obj)
        elif t == "distributed_load":
            self._draw_distributed_load_inspector(obj)

    # --------------------------------------------------- node inspector

    def _draw_node_inspector(self, node: Node) -> None:
        """Inspector panel for a selected Node."""
        _section_header("Node", parent=INSPECTOR_TAG)
        _readonly_field("ID", str(node.id), parent=INSPECTOR_TAG)
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Position", parent=INSPECTOR_TAG)

        dpg.add_input_float(
            label="X (m)",
            tag="insp_node_x",
            default_value=node.x,
            width=PANEL_WIDTH - 80,
            step=0.5,
            format="%.3f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_node(node.id, x=v),
        )
        dpg.add_input_float(
            label="Y (m)",
            tag="insp_node_y",
            default_value=node.y,
            width=PANEL_WIDTH - 80,
            step=0.5,
            format="%.3f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_node(node.id, y=v),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_button(
            label="Delete Node",
            width=PANEL_WIDTH - 16,
            parent=INSPECTOR_TAG,
            callback=lambda: self._delete_node(node.id),
        )

    # ----------------------------------------------- element inspector

    def _draw_element_inspector(self, element: Element) -> None:
        """Inspector panel for a selected Element."""
        _section_header("Element", parent=INSPECTOR_TAG)
        _readonly_field("ID", str(element.id), parent=INSPECTOR_TAG)
        _readonly_field(
            "Nodes",
            f"{element.node_start_id} → {element.node_end_id}",
            parent=INSPECTOR_TAG,
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Type", parent=INSPECTOR_TAG)
        dpg.add_radio_button(
            items=["general", "truss"],
            tag="insp_el_type",
            default_value=element.element_type,
            horizontal=True,
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_element(element.id, element_type=v),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Stiffness", parent=INSPECTOR_TAG)
        dpg.add_input_float(
            label="EA",
            tag="insp_el_EA",
            default_value=element.EA,
            width=PANEL_WIDTH - 80,
            step=1000.0,
            format="%.1f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_element(element.id, EA=v),
        )
        dpg.add_input_float(
            label="EI",
            tag="insp_el_EI",
            default_value=element.EI,
            width=PANEL_WIDTH - 80,
            step=500.0,
            format="%.1f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_element(element.id, EI=v),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_button(
            label="Delete Element",
            width=PANEL_WIDTH - 16,
            parent=INSPECTOR_TAG,
            callback=lambda: self._delete_element(element.id),
        )

    # ----------------------------------------------- support inspector

    def _draw_support_inspector(self, support: Support) -> None:
        """Inspector panel for a selected Support."""
        _section_header("Support", parent=INSPECTOR_TAG)
        _readonly_field("Node ID", str(support.node_id), parent=INSPECTOR_TAG)
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Type", parent=INSPECTOR_TAG)
        dpg.add_radio_button(
            items=["fixed", "hinged", "roller_x", "roller_y", "spring"],
            tag="insp_sup_type",
            default_value=support.support_type,
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_support(support.node_id, support_type=v),
        )

        # Spring fields — only shown when type is spring
        if support.support_type == "spring":
            dpg.add_separator(parent=INSPECTOR_TAG)
            dpg.add_text("Spring parameters", parent=INSPECTOR_TAG)
            dpg.add_input_float(
                label="k (stiffness)",
                tag="insp_sup_k",
                default_value=support.k,
                width=PANEL_WIDTH - 80,
                step=500.0,
                format="%.1f",
                parent=INSPECTOR_TAG,
                callback=lambda s, v: self._update_support(support.node_id, k=v),
            )
            dpg.add_input_int(
                label="direction",
                tag="insp_sup_trans",
                default_value=support.translation,
                min_value=1,
                max_value=3,
                width=PANEL_WIDTH - 80,
                parent=INSPECTOR_TAG,
                callback=lambda s, v: self._update_support(
                    support.node_id, translation=v
                ),
            )

        dpg.add_separator(parent=INSPECTOR_TAG)
        dpg.add_button(
            label="Remove Support",
            width=PANEL_WIDTH - 16,
            parent=INSPECTOR_TAG,
            callback=lambda: self._delete_support(support.node_id),
        )

    # ------------------------------------------- point load inspector

    def _draw_point_load_inspector(self, load: PointLoad) -> None:
        """Inspector panel for a selected PointLoad."""
        _section_header("Point Load", parent=INSPECTOR_TAG)
        _readonly_field("Node ID", str(load.node_id), parent=INSPECTOR_TAG)
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Force components (kN)", parent=INSPECTOR_TAG)
        dpg.add_input_float(
            label="Fx",
            tag="insp_pl_Fx",
            default_value=load.Fx,
            width=PANEL_WIDTH - 80,
            step=1.0,
            format="%.2f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_point_load(load.id, Fx=v),
        )
        dpg.add_input_float(
            label="Fy",
            tag="insp_pl_Fy",
            default_value=load.Fy,
            width=PANEL_WIDTH - 80,
            step=1.0,
            format="%.2f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_point_load(load.id, Fy=v),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Load case", parent=INSPECTOR_TAG)
        dpg.add_input_text(
            label="##lc_pl",
            tag="insp_pl_lc",
            default_value=load.load_case,
            width=PANEL_WIDTH - 80,
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_point_load(load.id, load_case=v),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_button(
            label="Delete Load",
            width=PANEL_WIDTH - 16,
            parent=INSPECTOR_TAG,
            callback=lambda: self._delete_point_load(load.id),
        )

    # ---------------------------------------- distributed load inspector

    def _draw_distributed_load_inspector(self, load: DistributedLoad) -> None:
        """Inspector panel for a selected DistributedLoad."""
        _section_header("Distributed Load", parent=INSPECTOR_TAG)
        _readonly_field("Element ID", str(load.element_id), parent=INSPECTOR_TAG)
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_input_float(
            label="q (kN/m)",
            tag="insp_dl_q",
            default_value=load.q,
            width=PANEL_WIDTH - 80,
            step=1.0,
            format="%.2f",
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_distributed_load(load.id, q=v),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Direction", parent=INSPECTOR_TAG)
        dpg.add_radio_button(
            items=["y", "x", "element"],
            tag="insp_dl_dir",
            default_value=load.direction,
            horizontal=True,
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_distributed_load(
                load.id, direction=v
            ),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_text("Load case", parent=INSPECTOR_TAG)
        dpg.add_input_text(
            label="##lc_dl",
            tag="insp_dl_lc",
            default_value=load.load_case,
            width=PANEL_WIDTH - 80,
            parent=INSPECTOR_TAG,
            callback=lambda s, v: self._update_distributed_load(
                load.id, load_case=v
            ),
        )
        dpg.add_separator(parent=INSPECTOR_TAG)

        dpg.add_button(
            label="Delete Load",
            width=PANEL_WIDTH - 16,
            parent=INSPECTOR_TAG,
            callback=lambda: self._delete_distributed_load(load.id),
        )

    # ---------------------------------------------------------- mutations

    def _update_node(self, node_id: int, **kwargs) -> None:
        """Apply field edits to a node and mark the scene dirty."""
        node = self.state.scene.get_node(node_id)
        if node is None:
            return
        for k, v in kwargs.items():
            setattr(node, k, v)
        self.state.mark_dirty()

    def _delete_node(self, node_id: int) -> None:
        """Delete the selected node and deselect."""
        self.state.scene.remove_node(node_id)
        self.state.deselect()
        self.state.mark_dirty()

    def _update_element(self, element_id: int, **kwargs) -> None:
        """Apply field edits to an element and mark the scene dirty."""
        element = self.state.scene.get_element(element_id)
        if element is None:
            return
        for k, v in kwargs.items():
            setattr(element, k, v)
        self.state.mark_dirty()

    def _delete_element(self, element_id: int) -> None:
        """Delete the selected element and deselect."""
        self.state.scene.remove_element(element_id)
        self.state.deselect()
        self.state.mark_dirty()

    def _update_support(self, node_id: int, **kwargs) -> None:
        """Apply field edits to a support and mark the scene dirty."""
        support = self.state.scene.get_support(node_id)
        if support is None:
            return
        for k, v in kwargs.items():
            setattr(support, k, v)
        self.state.mark_dirty()

    def _delete_support(self, node_id: int) -> None:
        """Remove the support on the given node and deselect."""
        self.state.scene.remove_support(node_id)
        self.state.deselect()
        self.state.mark_dirty()

    def _update_point_load(self, load_id: int, **kwargs) -> None:
        """Apply field edits to a point load and mark the scene dirty."""
        load = self.state.scene.get_point_load(load_id)
        if load is None:
            return
        for k, v in kwargs.items():
            setattr(load, k, v)
        self.state.mark_dirty()

    def _delete_point_load(self, load_id: int) -> None:
        """Delete the selected point load and deselect."""
        self.state.scene.remove_point_load(load_id)
        self.state.deselect()
        self.state.mark_dirty()

    def _update_distributed_load(self, load_id: int, **kwargs) -> None:
        """Apply field edits to a distributed load and mark the scene dirty."""
        load = self.state.scene.get_distributed_load(load_id)
        if load is None:
            return
        for k, v in kwargs.items():
            setattr(load, k, v)
        self.state.mark_dirty()

    def _delete_distributed_load(self, load_id: int) -> None:
        """Delete the selected distributed load and deselect."""
        self.state.scene.remove_distributed_load(load_id)
        self.state.deselect()
        self.state.mark_dirty()


# ------------------------------------------------------------------ helpers

def _section_header(title: str, parent: str) -> None:
    """Draw a bold section title at the top of an inspector panel."""
    dpg.add_text(title, parent=parent, color=(200, 200, 200, 255))
    dpg.add_separator(parent=parent)


def _readonly_field(label: str, value: str, parent: str) -> None:
    """Draw a read-only label/value pair."""
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_text(f"{label}:", color=(160, 160, 160, 255))
        dpg.add_text(value, color=(220, 220, 220, 255))