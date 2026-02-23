"""
toolbar.py
----------
Top toolbar panel.

Contains two groups of controls:
    Left  : tool buttons (Select, Add Node, Add Element, Add Support, Add Load)
    Right : action buttons (New, Open, Save, Save As, Solve, Show Results)

The toolbar mutates EditorState directly for tool switching.
File I/O and solving are handled here via calls to io/ and solver/.

Dirty flag handling
-------------------
New and Open check state.dirty and show a confirmation popup before
discarding unsaved changes.
"""

import dearpygui.dearpygui as dpg
from pathlib import Path

from .state import EditorState, TOOLS
from .results import ResultsPanel
from ..solver.bridge import solve
from ..io.serializer import save
from ..io.deserializer import load


TOOLBAR_TAG = "toolbar_panel"
CONFIRM_TAG = "confirm_discard_popup"

# Tool button labels and their state keys
TOOL_BUTTONS = [
    ("Select",      "select"),
    ("Add Node",    "add_node"),
    ("Add Element", "add_element"),
    ("Add Support", "add_support"),
    ("Add Load",    "add_load"),
]


class Toolbar:
    """
    Top toolbar panel.

    Parameters
    ----------
    state : EditorState
        Global editor state.
    results_panel : ResultsPanel
        The results panel instance, called to show results after solve.
    """

    def __init__(self, state: EditorState, results_panel: ResultsPanel) -> None:
        self.state = state
        self.results_panel = results_panel
        self._pending_action = None  # action to run after confirm discard

    # ------------------------------------------------------------------ build

    def build(self) -> None:
        """
        Create the toolbar widget group.

        Call once during GUI setup inside a dpg window context.
        """
        with dpg.group(tag=TOOLBAR_TAG, horizontal=True):

            # ---- tool buttons
            for label, tool_key in TOOL_BUTTONS:
                dpg.add_button(
                    tag=f"tool_btn_{tool_key}",
                    label=label,
                    width=100,
                    callback=lambda tk=tool_key: self._set_tool(tk),
                )

            dpg.add_separator()

            # ---- file actions
            dpg.add_button(
                label="New",
                width=60,
                callback=self._on_new,
            )
            dpg.add_button(
                label="Open",
                width=60,
                callback=self._on_open,
            )
            dpg.add_button(
                label="Save",
                width=60,
                callback=self._on_save,
            )
            dpg.add_button(
                label="Save As",
                width=70,
                callback=self._on_save_as,
            )

            dpg.add_separator()

            # ---- solve actions
            dpg.add_button(
                label="Solve",
                width=70,
                callback=self._on_solve,
            )
            dpg.add_button(
                label="Results",
                width=70,
                callback=self._on_show_results,
            )

        # Confirmation popup (hidden until needed)
        with dpg.window(
            tag=CONFIRM_TAG,
            label="Unsaved Changes",
            modal=True,
            show=False,
            width=320,
            height=110,
            no_resize=True,
        ):
            dpg.add_text("You have unsaved changes.\nDiscard and continue?")
            dpg.add_spacing(count=2)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Discard",
                    width=100,
                    callback=self._on_confirm_discard,
                )
                dpg.add_button(
                    label="Cancel",
                    width=100,
                    callback=lambda: dpg.configure_item(CONFIRM_TAG, show=False),
                )

    # ----------------------------------------------------------------- render

    def render(self) -> None:
        """
        Update tool button highlight states every frame.

        Active tool button gets a tinted background.
        """
        for _, tool_key in TOOL_BUTTONS:
            tag = f"tool_btn_{tool_key}"
            if not dpg.does_item_exist(tag):
                continue
            if self.state.active_tool == tool_key:
                dpg.bind_item_theme(tag, _get_active_theme())
            else:
                dpg.bind_item_theme(tag, 0)  # reset to default theme

    # ------------------------------------------------------------------ tools

    def _set_tool(self, tool_key: str) -> None:
        """Switch the active tool."""
        self.state.set_tool(tool_key)

    # ----------------------------------------------------------------- file IO

    def _on_new(self) -> None:
        """Start a new scene, confirming if there are unsaved changes."""
        if self.state.dirty:
            self._pending_action = self._do_new
            dpg.configure_item(CONFIRM_TAG, show=True)
        else:
            self._do_new()

    def _do_new(self) -> None:
        """Actually create a new scene."""
        self.state.new_scene()

    def _on_open(self) -> None:
        """Open a scene file, confirming if there are unsaved changes."""
        if self.state.dirty:
            self._pending_action = self._do_open
            dpg.configure_item(CONFIRM_TAG, show=True)
        else:
            self._do_open()

    def _do_open(self) -> None:
        """Show a file dialog and load the selected scene."""
        dpg.add_file_dialog(
            label="Open Scene",
            default_path=".",
            callback=self._on_file_open_selected,
            cancel_callback=lambda: None,
            width=600,
            height=400,
            file_count=1,
            extensions=[".json"],
        )

    def _on_file_open_selected(self, sender, app_data) -> None:
        """Called when the user confirms a file in the open dialog."""
        selections = app_data.get("selections", {})
        if not selections:
            return
        path = Path(list(selections.values())[0])
        try:
            scene = load(path)
            self.state.load_scene(scene, path)
        except Exception as exc:
            _show_error(f"Failed to open file:\n{exc}")

    def _on_save(self) -> None:
        """Save to the current file path, or fall back to Save As."""
        if self.state.file_path is None:
            self._on_save_as()
        else:
            self._do_save(self.state.file_path)

    def _on_save_as(self) -> None:
        """Show a file dialog and save to the selected path."""
        dpg.add_file_dialog(
            label="Save Scene As",
            default_path=".",
            default_filename="scene.json",
            callback=self._on_file_save_selected,
            cancel_callback=lambda: None,
            width=600,
            height=400,
        )

    def _on_file_save_selected(self, sender, app_data) -> None:
        """Called when the user confirms a path in the save dialog."""
        path_str = app_data.get("file_path_name", "")
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix != ".json":
            path = path.with_suffix(".json")
        self._do_save(path)

    def _do_save(self, path: Path) -> None:
        """Actually write the scene to disk."""
        try:
            save(self.state.scene, path)
            self.state.file_path = path
            self.state.mark_clean()
        except Exception as exc:
            _show_error(f"Failed to save file:\n{exc}")

    # ------------------------------------------------------------------ solve

    def _on_solve(self) -> None:
        """
        Run the solver on the current scene.

        Shows a warning popup if the scene is not solvable.
        On success, stores the result and opens the results window.
        On failure, shows the error message.
        """
        solvable, reason = self.state.scene.is_solvable()
        if not solvable:
            _show_error(f"Cannot solve:\n{reason}")
            return

        result = solve(self.state.scene)
        self.state.store_solve_result(result)

        if result.success:
            self.results_panel.show()
        else:
            _show_error(f"Solver error:\n{result.error}")

    def _on_show_results(self) -> None:
        """Re-open the results window if a successful result exists."""
        if not self.state.has_results:
            _show_error("No results available.\nRun Solve first.")
            return
        self.results_panel.show()

    # --------------------------------------------------------- confirm discard

    def _on_confirm_discard(self) -> None:
        """User confirmed discarding unsaved changes."""
        dpg.configure_item(CONFIRM_TAG, show=False)
        if self._pending_action is not None:
            self._pending_action()
            self._pending_action = None


# ------------------------------------------------------------------ helpers

_active_theme_tag = None


def _get_active_theme() -> int:
    """
    Return a Dear PyGui theme that tints a button to show it is active.

    Created once and reused.
    """
    global _active_theme_tag
    if _active_theme_tag is not None and dpg.does_item_exist(_active_theme_tag):
        return _active_theme_tag

    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(
                dpg.mvThemeCol_Button,
                (50, 100, 180, 255),
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonHovered,
                (70, 120, 200, 255),
            )
    _active_theme_tag = theme
    return _active_theme_tag


def _show_error(message: str) -> None:
    """Show a simple modal error popup."""
    tag = "error_popup"
    if dpg.does_item_exist(tag):
        dpg.delete_item(tag)
    with dpg.window(
        tag=tag,
        label="Error",
        modal=True,
        width=340,
        height=130,
        no_resize=True,
    ):
        dpg.add_text(message, color=(220, 80, 60, 255))
        dpg.add_spacing(count=2)
        dpg.add_button(
            label="OK",
            width=80,
            callback=lambda: dpg.delete_item(tag),
        )