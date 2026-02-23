"""
results.py
----------
Renders anastruct solve results inside a Dear PyGui popup window.

When the user hits Solve and a SolveResult is available, this module
opens a modal window showing anastruct's matplotlib diagrams rendered
as Dear PyGui textures.

Approach
--------
anastruct's .show_results() renders to a matplotlib figure.
We capture that figure to a PIL Image in memory, convert it to
raw RGBA bytes, and register it as a Dear PyGui static texture.
No temp files are written to disk.

Available result views (tabs):
    - Structure        : show_structure()
    - Bending Moment   : show_bending_moment()
    - Shear Force      : show_shear_force()
    - Displacement     : show_displacement()
    - Axial Force      : show_axial_force()
    - Reaction Forces  : show_reaction_force()
"""

import io
import dearpygui.dearpygui as dpg
from PIL import Image
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt

from .state import EditorState
from ..solver.bridge import SolveResult


RESULTS_WINDOW_TAG = "results_window"
TEXTURE_REGISTRY_TAG = "results_texture_registry"

# Size of each rendered figure in pixels
FIG_WIDTH_PX  = 800
FIG_HEIGHT_PX = 500
FIG_DPI       = 100


class ResultsPanel:
    """
    Modal results window showing anastruct diagram tabs.

    Parameters
    ----------
    state : EditorState
        Global editor state. ResultsPanel reads state.solve_result.
    """

    def __init__(self, state: EditorState) -> None:
        self.state = state
        self._texture_tags: list[str] = []

    # ------------------------------------------------------------------ build

    def build(self) -> None:
        """
        Create the texture registry.

        Call once during GUI setup, outside any window context.
        """
        with dpg.texture_registry(tag=TEXTURE_REGISTRY_TAG):
            pass

    # ------------------------------------------------------------------ show

    def show(self) -> None:
        """
        Open the results window for the current solve result.

        Renders all diagrams and displays them in a tabbed window.
        Closes and recreates the window if already open.
        """
        if not self.state.has_results:
            return

        # Close existing window if open
        if dpg.does_item_exist(RESULTS_WINDOW_TAG):
            dpg.delete_item(RESULTS_WINDOW_TAG)

        # Clear old textures
        for tag in self._texture_tags:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        self._texture_tags.clear()

        result = self.state.solve_result
        ss = result.system

        # Define tabs: (tab label, callable that renders the figure)
        tabs = [
            ("Structure",       lambda: ss.show_structure(show=False,      verbosity=0)),
            ("Bending Moment",  lambda: ss.show_bending_moment(show=False,  verbosity=0)),
            ("Shear Force",     lambda: ss.show_shear_force(show=False,     verbosity=0)),
            ("Displacement",    lambda: ss.show_displacement(show=False,    verbosity=0)),
            ("Axial Force",     lambda: ss.show_axial_force(show=False,     verbosity=0)),
            ("Reaction Forces", lambda: ss.show_reaction_force(show=False,  verbosity=0)),
        ]

        # Render all figures to textures before building the window
        rendered: list[tuple[str, str]] = []  # (tab_label, texture_tag)
        for i, (label, plot_fn) in enumerate(tabs):
            texture_tag = f"result_texture_{i}"
            try:
                self._render_figure(plot_fn, texture_tag)
                rendered.append((label, texture_tag))
            except Exception as exc:
                # Some diagram types may not be available for all model types
                # (e.g. bending moment for pure truss). Skip silently.
                print(f"[results] skipping '{label}': {exc}")

        if not rendered:
            self._show_error_window("No diagrams could be rendered.")
            return

        # Build the tabbed window
        with dpg.window(
            tag=RESULTS_WINDOW_TAG,
            label="Results",
            width=FIG_WIDTH_PX + 40,
            height=FIG_HEIGHT_PX + 100,
            modal=False,
            no_close=False,
        ):
            with dpg.tab_bar():
                for label, texture_tag in rendered:
                    with dpg.tab(label=label):
                        dpg.add_image(
                            texture_tag=texture_tag,
                            width=FIG_WIDTH_PX,
                            height=FIG_HEIGHT_PX,
                        )

    # --------------------------------------------------------------- internal

    def _render_figure(self, plot_fn, texture_tag: str) -> None:
        """
        Call an anastruct plot function, capture the resulting matplotlib
        figure, and register it as a Dear PyGui texture.

        Parameters
        ----------
        plot_fn : callable
            A zero-argument lambda that calls an anastruct show_*() method
            with show=False and returns a matplotlib Figure.
        texture_tag : str
            Dear PyGui tag to register the texture under.
        """
        fig = plot_fn()
        if fig is None:
            raise ValueError("plot function returned None")

        # Render figure to PNG bytes in memory
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=FIG_DPI, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        # Convert to RGBA float32 flat array (required by Dear PyGui)
        img = Image.open(buf).convert("RGBA").resize(
            (FIG_WIDTH_PX, FIG_HEIGHT_PX), Image.LANCZOS
        )
        pixels = [v / 255.0 for v in img.tobytes()]

        # Register texture
        dpg.add_static_texture(
            width=FIG_WIDTH_PX,
            height=FIG_HEIGHT_PX,
            default_value=pixels,
            tag=texture_tag,
            parent=TEXTURE_REGISTRY_TAG,
        )
        self._texture_tags.append(texture_tag)

    def _show_error_window(self, message: str) -> None:
        """Show a simple error popup if results cannot be rendered."""
        with dpg.window(
            tag=RESULTS_WINDOW_TAG,
            label="Results — Error",
            width=400,
            height=120,
            modal=True,
        ):
            dpg.add_text(message, color=(220, 80, 60, 255))
            dpg.add_button(
                label="Close",
                callback=lambda: dpg.delete_item(RESULTS_WINDOW_TAG),
            )