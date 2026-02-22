"""
state.py
--------
Global editor state shared across all GUI panels.

EditorState is the single object that every panel reads from and writes to.
It holds the active scene, the currently selected object, the active tool,
and housekeeping flags like dirty (unsaved changes) and the last solve result.

No Dear PyGui calls live here — this is pure Python state management.
Panels import this module and call its functions; they never hold their own
copies of scene data.

Tool names
----------
"select"        — click to select/move objects
"add_node"      — click canvas to place a node
"add_element"   — click two nodes to connect them
"add_support"   — click a node to assign a support
"add_load"      — click a node or element to assign a load
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path

from ..model.scene import Scene
from ..model.node import Node
from ..solver.bridge import SolveResult


# Valid tool names
TOOLS = ("select", "add_node", "add_element", "add_support", "add_load")


@dataclass
class SelectionState:
    """
    Tracks what is currently selected in the editor.

    Attributes
    ----------
    object_type : str or None
        One of "node", "element", "support", "point_load",
        "distributed_load", or None if nothing is selected.
    object_id : int or None
        The ID of the selected object within the scene.
    """

    object_type: Optional[str] = None
    object_id: Optional[int] = None

    def clear(self) -> None:
        """Deselect everything."""
        self.object_type = None
        self.object_id = None

    def set(self, object_type: str, object_id: int) -> None:
        """Select an object by type and ID."""
        self.object_type = object_type
        self.object_id = object_id

    @property
    def is_empty(self) -> bool:
        """True if nothing is selected."""
        return self.object_id is None


@dataclass
class EditorState:
    """
    The single source of truth for all editor UI state.

    Attributes
    ----------
    scene : Scene
        The structural model currently open in the editor.
    selection : SelectionState
        The currently selected object.
    active_tool : str
        The currently active tool. One of TOOLS.
    dirty : bool
        True if the scene has unsaved changes.
    file_path : Path or None
        The path of the currently open file. None if unsaved.
    solve_result : SolveResult or None
        The result of the last solve. None if not yet solved or scene changed.
    pending_element_node : int or None
        When add_element tool is active and the first node has been clicked,
        this holds its ID until the second node is clicked.
    """

    scene: Scene = field(default_factory=Scene)
    selection: SelectionState = field(default_factory=SelectionState)
    active_tool: str = "select"
    dirty: bool = False
    file_path: Optional[Path] = None
    solve_result: Optional[SolveResult] = None
    pending_element_node: Optional[int] = None

    # ------------------------------------------------------------------ tools

    def set_tool(self, tool: str) -> None:
        """
        Switch the active tool.

        Clears any pending element node when switching away from add_element.

        Raises ValueError if the tool name is not recognized.
        """
        if tool not in TOOLS:
            raise ValueError(f"Unknown tool: {tool!r}. Must be one of {TOOLS}.")
        if tool != "add_element":
            self.pending_element_node = None
        self.active_tool = tool

    # --------------------------------------------------------------- selection

    def select(self, object_type: str, object_id: int) -> None:
        """Select an object and switch to the select tool."""
        self.selection.set(object_type, object_id)
        self.active_tool = "select"

    def deselect(self) -> None:
        """Clear the current selection."""
        self.selection.clear()

    def selected_object(self) -> Optional[Any]:
        """
        Return the currently selected scene object, or None.

        Looks up the object from the scene using the selection state.
        Returns the actual dataclass instance (Node, Element, etc.).
        """
        if self.selection.is_empty:
            return None
        t = self.selection.object_type
        oid = self.selection.object_id
        if t == "node":
            return self.scene.get_node(oid)
        if t == "element":
            return self.scene.get_element(oid)
        if t == "support":
            return self.scene.get_support_by_id(oid)
        if t == "point_load":
            return self.scene.get_point_load(oid)
        if t == "distributed_load":
            return self.scene.get_distributed_load(oid)
        return None

    # ------------------------------------------------------------------- scene

    def mark_dirty(self) -> None:
        """Mark the scene as having unsaved changes and clear solve result."""
        self.dirty = True
        self.solve_result = None

    def mark_clean(self) -> None:
        """Mark the scene as saved."""
        self.dirty = False

    def new_scene(self) -> None:
        """Replace the current scene with a fresh empty one."""
        self.scene = Scene()
        self.selection.clear()
        self.active_tool = "select"
        self.dirty = False
        self.file_path = None
        self.solve_result = None
        self.pending_element_node = None

    def load_scene(self, scene: Scene, path: Path) -> None:
        """Replace the current scene with a loaded one."""
        self.scene = scene
        self.selection.clear()
        self.active_tool = "select"
        self.dirty = False
        self.file_path = path
        self.solve_result = None
        self.pending_element_node = None

    # ------------------------------------------------------------------ solve

    def store_solve_result(self, result: SolveResult) -> None:
        """Store the result of a solve attempt."""
        self.solve_result = result

    @property
    def has_results(self) -> bool:
        """True if a successful solve result is available."""
        return self.solve_result is not None and self.solve_result.success

    # --------------------------------------------------------------- title bar

    @property
    def window_title(self) -> str:
        """
        Return a window title string reflecting current file and dirty state.

        Examples: "anaStruct GUI", "scene.json — anaStruct GUI",
                  "scene.json* — anaStruct GUI"
        """
        base = "anaStruct GUI"
        if self.file_path is None:
            name = "untitled"
        else:
            name = self.file_path.name
        dirty_marker = "*" if self.dirty else ""
        return f"{name}{dirty_marker} — {base}"