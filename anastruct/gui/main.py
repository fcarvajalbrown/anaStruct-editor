"""
main.py
-------
Entry point for the anaStruct GUI editor.

Wires all panels together into a single Dear PyGui window and runs
the render loop.

Layout
------
    ┌─────────────────────────────────────────────────┐
    │  Toolbar (tool buttons + file/solve actions)     │
    ├──────────────┬──────────────────────┬────────────┤
    │  Scene Tree  │      Canvas          │ Inspector  │
    │  (left)      │      (center)        │ (right)    │
    └──────────────┴──────────────────────┴────────────┘

------

Made by Felipe Carvajal Brown (@fcarvajalbrown) — 2026

Run from the repo root (anastruct-editor/anastruct/):
    python -m gui.main
"""

import dearpygui.dearpygui as dpg

from .editor.canvas import Canvas
from .editor.inspector import Inspector
from .editor.results import ResultsPanel
from .editor.scene_tree import SceneTree
from .editor.state import EditorState
from .editor.toolbar import Toolbar

# Window dimensions
WINDOW_WIDTH  = 1400
WINDOW_HEIGHT = 820
TOOLBAR_HEIGHT = 40
TREE_WIDTH     = 220
INSPECTOR_WIDTH = 280
CANVAS_WIDTH = WINDOW_WIDTH - TREE_WIDTH - INSPECTOR_WIDTH - 16
CANVAS_HEIGHT = WINDOW_HEIGHT - TOOLBAR_HEIGHT - 40


def main() -> None:
    """Initialize Dear PyGui, build all panels, and run the render loop."""

    # ------------------------------------------------------------------ setup
    dpg.create_context()
    dpg.create_viewport(
        title="anaStruct GUI",
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        resizable=True,
    )
    dpg.setup_dearpygui()

    # ------------------------------------------------------------------ state
    state = EditorState()

    # ----------------------------------------------------------------- panels
    results_panel = ResultsPanel(state)
    canvas        = Canvas(state, width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
    toolbar       = Toolbar(state, results_panel)
    inspector     = Inspector(state)
    scene_tree    = SceneTree(state)

    # Build texture registry outside any window
    results_panel.build()

    # ----------------------------------------------------------------- window
    with dpg.window(
        tag="main_window",
        label="anaStruct GUI",
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        no_title_bar=True,
        no_resize=True,
        no_move=True,
        no_scrollbar=True,
        pos=(0, 0),
    ):
        # ---- toolbar row
        toolbar.build()
        dpg.add_separator()
        dpg.add_spacer(height=4)

        # ---- main row: tree | canvas | inspector
        with dpg.group(horizontal=True):

            # left: scene tree
            scene_tree.build()

            # center: canvas
            canvas.build()

            # right: inspector
            inspector.build()

    # ----------------------------------------------------------------- theme
    _apply_global_theme()

    # -------------------------------------------------------------- render loop
    dpg.set_primary_window("main_window", True)
    dpg.show_viewport()

    while dpg.is_dearpygui_running():
        # Update window title to reflect dirty/file state
        dpg.set_viewport_title(state.window_title)

        # Render all panels
        toolbar.render()
        canvas.render()
        scene_tree.render()
        inspector.render()

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


# ------------------------------------------------------------------- theme

def _apply_global_theme() -> None:
    """Apply a dark theme with subtle structural engineering aesthetics."""
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            # Background colours
            dpg.add_theme_color(
                dpg.mvThemeCol_WindowBg,       (30,  33,  40, 255))
            dpg.add_theme_color(
                dpg.mvThemeCol_ChildBg,        (26,  28,  35, 255))
            dpg.add_theme_color(
                dpg.mvThemeCol_PopupBg,        (36,  39,  48, 255))

            # Text
            dpg.add_theme_color(
                dpg.mvThemeCol_Text,           (210, 213, 220, 255))

            # Borders
            dpg.add_theme_color(
                dpg.mvThemeCol_Border,         (55,  60,  75, 255))

            # Buttons
            dpg.add_theme_color(
                dpg.mvThemeCol_Button,         (45,  75, 130, 255))
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonHovered,  (60,  95, 160, 255))
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonActive,   (35,  60, 110, 255))

            # Header (selectable highlight)
            dpg.add_theme_color(
                dpg.mvThemeCol_Header,         (45,  75, 130, 160))
            dpg.add_theme_color(
                dpg.mvThemeCol_HeaderHovered,  (60,  95, 160, 180))

            # Input fields
            dpg.add_theme_color(
                dpg.mvThemeCol_FrameBg,        (42,  45,  56, 255))
            dpg.add_theme_color(
                dpg.mvThemeCol_FrameBgHovered, (50,  55,  70, 255))

            # Separator
            dpg.add_theme_color(
                dpg.mvThemeCol_Separator,      (55,  60,  75, 255))

            # Rounding
            dpg.add_theme_style(
                dpg.mvStyleVar_FrameRounding,  4)
            dpg.add_theme_style(
                dpg.mvStyleVar_WindowRounding, 0)
            dpg.add_theme_style(
                dpg.mvStyleVar_ItemSpacing,    6, 4)

    dpg.bind_theme(global_theme)


if __name__ == "__main__":
    main()