"""
canvas.py
---------
Canvas rendering and mouse interaction for the editor.

Responsibilities:
- Maintain pan offset and zoom scale
- Convert between screen space and world space
- Draw grid, nodes, elements, supports, and loads on a Dear PyGui drawlist
- Route mouse clicks to the correct handler based on the active tool
- Handle node dragging when the select tool is active

Coordinate conventions
----------------------
World space  : meters, Y increases upward (structural convention)
Screen space : pixels, Y increases downward (Dear PyGui convention)

The world_to_screen() and screen_to_world() functions handle this flip.
World Y is negated when converting to screen so structures appear right-side up.

Usage
-----
    canvas = Canvas(state)
    canvas.build()          # call once during GUI setup to create dpg items
    canvas.render()         # call every frame inside the Dear PyGui render loop
"""

import dearpygui.dearpygui as dpg
from dataclasses import dataclass, field
from typing import Optional

from .state import EditorState
from ..model.node import Node
from ..model.element import Element
from ..model.support import Support
from ..model.load import PointLoad, DistributedLoad


# ------------------------------------------------------------------ colours
# All colours are (R, G, B, A) tuples in 0-255 range for Dear PyGui

C_BACKGROUND    = (245, 245, 245, 255)
C_GRID_MINOR    = (210, 210, 210, 255)
C_GRID_MAJOR    = (170, 170, 170, 255)
C_ORIGIN        = (100, 100, 100, 255)
C_NODE          = (30,  90, 180, 255)
C_NODE_HOVER    = (60, 140, 220, 255)
C_NODE_SELECTED = (220,  60,  60, 255)
C_ELEMENT       = (50,  50,  50, 255)
C_ELEMENT_SEL   = (220,  60,  60, 255)
C_ELEMENT_PEND  = (100, 160, 220, 180)  # pending second node in add_element
C_SUPPORT_FIXED = (40, 160,  80, 255)
C_SUPPORT_HINGE = (40, 160,  80, 255)
C_SUPPORT_ROLL  = (40, 160,  80, 255)
C_LOAD_POINT    = (200,  80,  20, 255)
C_LOAD_DIST     = (200, 140,  20, 255)
C_LABEL         = (60,  60,  60, 255)

# ------------------------------------------------------------------ sizes
NODE_RADIUS        = 6.0
NODE_RADIUS_HOVER  = 8.0
SUPPORT_SIZE       = 14.0
LOAD_ARROW_LEN     = 40.0
LOAD_ARROW_HEAD    = 8.0
GRID_CELL_PX       = 60    # pixels per grid cell at zoom=1.0
SNAP_THRESHOLD_PX  = 12    # pixels within which a click snaps to a node


@dataclass
class CanvasTransform:
    """
    Holds the pan and zoom state of the canvas viewport.

    Attributes
    ----------
    pan_x, pan_y : float
        Pan offset in screen pixels.
    zoom : float
        Zoom scale factor. 1.0 = 1 grid cell = GRID_CELL_PX pixels.
    origin_x, origin_y : float
        Screen-space position of the canvas widget's top-left corner.
        Updated each frame from Dear PyGui.
    """
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    origin_x: float = 0.0
    origin_y: float = 0.0

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """
        Convert world coordinates (meters) to screen coordinates (pixels).

        World Y is negated so that positive Y points upward on screen.
        """
        sx = self.origin_x + self.pan_x + wx * self.zoom * GRID_CELL_PX
        sy = self.origin_y + self.pan_y - wy * self.zoom * GRID_CELL_PX
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """
        Convert screen coordinates (pixels) to world coordinates (meters).
        """
        wx = (sx - self.origin_x - self.pan_x) / (self.zoom * GRID_CELL_PX)
        wy = -(sy - self.origin_y - self.pan_y) / (self.zoom * GRID_CELL_PX)
        return wx, wy

    def zoom_in(self) -> None:
        """Increase zoom by 20%, capped at 5.0."""
        self.zoom = min(5.0, self.zoom * 1.2)

    def zoom_out(self) -> None:
        """Decrease zoom by 20%, floored at 0.1."""
        self.zoom = max(0.1, self.zoom / 1.2)


class Canvas:
    """
    Manages the Dear PyGui drawlist canvas and all mouse interaction.

    Parameters
    ----------
    state : EditorState
        The global editor state. Canvas reads and mutates this directly.
    tag : str
        Dear PyGui tag for the drawlist widget. Must be unique in the window.
    width, height : int
        Initial canvas size in pixels.
    """

    def __init__(
        self,
        state: EditorState,
        tag: str = "canvas_drawlist",
        width: int = 900,
        height: int = 600,
    ) -> None:
        self.state = state
        self.tag = tag
        self.width = width
        self.height = height
        self.transform = CanvasTransform(
            pan_x=width / 2,
            pan_y=height / 2,
        )
        self._hover_node_id: Optional[int] = None
        self._dragging: bool = False
        self._drag_start_world: Optional[tuple[float, float]] = None

    # ------------------------------------------------------------------ build

    def build(self) -> None:
        """
        Create the Dear PyGui drawlist widget and register mouse handlers.

        Call this once during GUI setup inside a dpg window context.
        """
        with dpg.drawlist(
            tag=self.tag,
            width=self.width,
            height=self.height,
        ):
            pass  # content is drawn dynamically in render()

        # Mouse handlers — registered on the drawlist item
        with dpg.item_handler_registry(tag=f"{self.tag}_handlers"):
            dpg.add_item_clicked_handler(
                button=dpg.mvMouseButton_Left,
                callback=self._on_left_click,
            )
            dpg.add_item_clicked_handler(
                button=dpg.mvMouseButton_Middle,
                callback=self._on_middle_click,
            )
        dpg.bind_item_handler_registry(self.tag, f"{self.tag}_handlers")

    # ----------------------------------------------------------------- render

    def render(self) -> None:
        """
        Clear and redraw the entire canvas.

        Call this every frame inside the Dear PyGui render loop.
        """
        # Update canvas origin from widget position
        pos = dpg.get_item_pos(self.tag)
        self.transform.origin_x = pos[0]
        self.transform.origin_y = pos[1]

        # Handle middle-mouse pan and scroll zoom every frame
        self._handle_pan()
        self._handle_scroll()

        # Update hover node
        mx, my = dpg.get_mouse_pos(local=False)
        self._hover_node_id = self._find_node_at_screen(mx, my)

        # Clear drawlist
        dpg.delete_item(self.tag, children_only=True)

        # Draw layers bottom to top
        self._draw_background()
        self._draw_grid()
        self._draw_elements()
        self._draw_supports()
        self._draw_loads()
        self._draw_nodes()
        self._draw_pending_element_line()
        self._draw_cursor_hint()

    # --------------------------------------------------------------- drawing

    def _draw_background(self) -> None:
        """Fill the canvas background."""
        dpg.draw_rectangle(
            pmin=(self.transform.origin_x, self.transform.origin_y),
            pmax=(self.transform.origin_x + self.width,
                  self.transform.origin_y + self.height),
            fill=C_BACKGROUND,
            color=C_BACKGROUND,
            parent=self.tag,
        )

    def _draw_grid(self) -> None:
        """Draw minor and major grid lines and the world origin crosshair."""
        t = self.transform
        cell = t.zoom * GRID_CELL_PX
        major_every = 5  # major line every 5 cells

        # vertical lines
        x_start = int((t.origin_x - t.pan_x - t.origin_x) / cell) - 1
        x_end = x_start + int(self.width / cell) + 2
        for ix in range(x_start, x_end):
            sx = t.origin_x + t.pan_x + ix * cell
            color = C_GRID_MAJOR if ix % major_every == 0 else C_GRID_MINOR
            thickness = 1.5 if ix % major_every == 0 else 0.5
            dpg.draw_line(
                p1=(sx, t.origin_y),
                p2=(sx, t.origin_y + self.height),
                color=color, thickness=thickness, parent=self.tag,
            )

        # horizontal lines
        y_start = int((t.origin_y - t.pan_y - t.origin_y) / cell) - 1
        y_end = y_start + int(self.height / cell) + 2
        for iy in range(y_start, y_end):
            sy = t.origin_y + t.pan_y + iy * cell
            color = C_GRID_MAJOR if iy % major_every == 0 else C_GRID_MINOR
            thickness = 1.5 if iy % major_every == 0 else 0.5
            dpg.draw_line(
                p1=(t.origin_x, sy),
                p2=(t.origin_x + self.width, sy),
                color=color, thickness=thickness, parent=self.tag,
            )

        # origin crosshair
        ox, oy = t.world_to_screen(0, 0)
        dpg.draw_line(
            p1=(ox - 10, oy), p2=(ox + 10, oy),
            color=C_ORIGIN, thickness=1.5, parent=self.tag,
        )
        dpg.draw_line(
            p1=(ox, oy - 10), p2=(ox, oy + 10),
            color=C_ORIGIN, thickness=1.5, parent=self.tag,
        )

    def _draw_nodes(self) -> None:
        """Draw all nodes as circles with ID labels."""
        t = self.transform
        for node in self.state.scene.nodes:
            sx, sy = t.world_to_screen(node.x, node.y)
            is_selected = (
                self.state.selection.object_type == "node"
                and self.state.selection.object_id == node.id
            )
            is_hover = self._hover_node_id == node.id

            if is_selected:
                color = C_NODE_SELECTED
                radius = NODE_RADIUS_HOVER
            elif is_hover:
                color = C_NODE_HOVER
                radius = NODE_RADIUS_HOVER
            else:
                color = C_NODE
                radius = NODE_RADIUS

            dpg.draw_circle(
                center=(sx, sy), radius=radius,
                fill=color, color=color, parent=self.tag,
            )
            dpg.draw_text(
                pos=(sx + radius + 3, sy - radius - 3),
                text=str(node.id),
                color=C_LABEL, size=11, parent=self.tag,
            )

    def _draw_elements(self) -> None:
        """Draw all elements as lines between their nodes."""
        t = self.transform
        for element in self.state.scene.elements:
            n_start = self.state.scene.get_node(element.node_start_id)
            n_end = self.state.scene.get_node(element.node_end_id)
            if n_start is None or n_end is None:
                continue

            s1 = t.world_to_screen(n_start.x, n_start.y)
            s2 = t.world_to_screen(n_end.x, n_end.y)

            is_selected = (
                self.state.selection.object_type == "element"
                and self.state.selection.object_id == element.id
            )
            color = C_ELEMENT_SEL if is_selected else C_ELEMENT
            thickness = 3.0 if is_selected else 2.0

            dpg.draw_line(
                p1=s1, p2=s2,
                color=color, thickness=thickness, parent=self.tag,
            )

            # element type label at midpoint
            mid_x = (s1[0] + s2[0]) / 2
            mid_y = (s1[1] + s2[1]) / 2
            if element.element_type == "truss":
                dpg.draw_text(
                    pos=(mid_x + 4, mid_y - 12),
                    text="T", color=C_LABEL, size=10, parent=self.tag,
                )

    def _draw_supports(self) -> None:
        """Draw support symbols at their nodes."""
        t = self.transform
        for support in self.state.scene.supports:
            node = self.state.scene.get_node(support.node_id)
            if node is None:
                continue
            sx, sy = t.world_to_screen(node.x, node.y)
            self._draw_support_symbol(sx, sy, support.support_type)

    def _draw_support_symbol(
        self, sx: float, sy: float, support_type: str
    ) -> None:
        """Draw a support symbol centered below the node screen position."""
        s = SUPPORT_SIZE
        y_base = sy + NODE_RADIUS + 2

        if support_type == "fixed":
            # filled rectangle
            dpg.draw_rectangle(
                pmin=(sx - s, y_base),
                pmax=(sx + s, y_base + s),
                fill=C_SUPPORT_FIXED,
                color=C_SUPPORT_FIXED,
                parent=self.tag,
            )
        elif support_type == "hinged":
            # triangle
            dpg.draw_triangle(
                p1=(sx, y_base),
                p2=(sx - s, y_base + s),
                p3=(sx + s, y_base + s),
                fill=C_SUPPORT_HINGE,
                color=C_SUPPORT_HINGE,
                parent=self.tag,
            )
        elif support_type in ("roller_x", "roller_y"):
            # triangle + circle to indicate roller
            dpg.draw_triangle(
                p1=(sx, y_base),
                p2=(sx - s, y_base + s),
                p3=(sx + s, y_base + s),
                fill=C_SUPPORT_ROLL,
                color=C_SUPPORT_ROLL,
                parent=self.tag,
            )
            dpg.draw_circle(
                center=(sx, y_base + s + 4),
                radius=4,
                fill=C_SUPPORT_ROLL,
                color=C_SUPPORT_ROLL,
                parent=self.tag,
            )
        elif support_type == "spring":
            # zigzag line
            points = [
                (sx,       y_base),
                (sx + s/2, y_base + s * 0.25),
                (sx - s/2, y_base + s * 0.5),
                (sx + s/2, y_base + s * 0.75),
                (sx,       y_base + s),
            ]
            for i in range(len(points) - 1):
                dpg.draw_line(
                    p1=points[i], p2=points[i + 1],
                    color=C_SUPPORT_ROLL, thickness=2.0,
                    parent=self.tag,
                )

    def _draw_loads(self) -> None:
        """Draw point load arrows and distributed load indicators."""
        t = self.transform
        for load in self.state.scene.point_loads:
            node = self.state.scene.get_node(load.node_id)
            if node is None:
                continue
            sx, sy = t.world_to_screen(node.x, node.y)
            self._draw_point_load_arrow(sx, sy, load.Fx, load.Fy)

        for load in self.state.scene.distributed_loads:
            element = self.state.scene.get_element(load.element_id)
            if element is None:
                continue
            n1 = self.state.scene.get_node(element.node_start_id)
            n2 = self.state.scene.get_node(element.node_end_id)
            if n1 is None or n2 is None:
                continue
            s1 = t.world_to_screen(n1.x, n1.y)
            s2 = t.world_to_screen(n2.x, n2.y)
            self._draw_distributed_load(s1, s2, load.q)

    def _draw_point_load_arrow(
        self, sx: float, sy: float, Fx: float, Fy: float
    ) -> None:
        """Draw an arrow indicating a point load direction and presence."""
        length = LOAD_ARROW_LEN
        head = LOAD_ARROW_HEAD

        if Fy != 0:
            direction = 1 if Fy > 0 else -1
            tip = (sx, sy - direction * NODE_RADIUS)
            tail = (sx, tip[1] - direction * length)
            dpg.draw_arrow(
                p1=tail, p2=tip,
                color=C_LOAD_POINT, thickness=2.0,
                size=head, parent=self.tag,
            )
            dpg.draw_text(
                pos=(sx + 6, (tip[1] + tail[1]) / 2),
                text=f"{abs(Fy):.1f}kN",
                color=C_LOAD_POINT, size=10, parent=self.tag,
            )

        if Fx != 0:
            direction = 1 if Fx > 0 else -1
            tip = (sx + direction * NODE_RADIUS, sy)
            tail = (tip[0] + direction * length, sy)
            dpg.draw_arrow(
                p1=tail, p2=tip,
                color=C_LOAD_POINT, thickness=2.0,
                size=head, parent=self.tag,
            )
            dpg.draw_text(
                pos=((tip[0] + tail[0]) / 2, sy - 14),
                text=f"{abs(Fx):.1f}kN",
                color=C_LOAD_POINT, size=10, parent=self.tag,
            )

    def _draw_distributed_load(
        self,
        s1: tuple[float, float],
        s2: tuple[float, float],
        q: float,
    ) -> None:
        """Draw small arrows along an element to indicate a distributed load."""
        if q == 0:
            return
        direction = 1 if q > 0 else -1
        num_arrows = 5
        for i in range(num_arrows + 1):
            t_param = i / num_arrows
            mx = s1[0] + t_param * (s2[0] - s1[0])
            my = s1[1] + t_param * (s2[1] - s1[1])
            arrow_len = 20
            dpg.draw_arrow(
                p1=(mx, my - direction * arrow_len),
                p2=(mx, my),
                color=C_LOAD_DIST, thickness=1.5,
                size=5, parent=self.tag,
            )
        # magnitude label at midpoint
        dpg.draw_text(
            pos=((s1[0] + s2[0]) / 2 + 4, (s1[1] + s2[1]) / 2 - 24),
            text=f"{abs(q):.1f}kN/m",
            color=C_LOAD_DIST, size=10, parent=self.tag,
        )

    def _draw_pending_element_line(self) -> None:
        """
        When add_element tool is active and the first node is selected,
        draw a ghost line from that node to the current mouse position.
        """
        if (
            self.state.active_tool != "add_element"
            or self.state.pending_element_node is None
        ):
            return
        node = self.state.scene.get_node(self.state.pending_element_node)
        if node is None:
            return
        sx, sy = self.transform.world_to_screen(node.x, node.y)
        mx, my = dpg.get_mouse_pos(local=False)
        dpg.draw_line(
            p1=(sx, sy), p2=(mx, my),
            color=C_ELEMENT_PEND, thickness=1.5,
            parent=self.tag,
        )

    def _draw_cursor_hint(self) -> None:
        """Draw a small hint text in the bottom-left showing the active tool."""
        hints = {
            "select":      "SELECT — click to select, drag to move",
            "add_node":    "ADD NODE — click to place",
            "add_element": "ADD ELEMENT — click first node, then second",
            "add_support": "ADD SUPPORT — click a node",
            "add_load":    "ADD LOAD — click a node or element",
        }
        text = hints.get(self.state.active_tool, "")
        dpg.draw_text(
            pos=(self.transform.origin_x + 8,
                 self.transform.origin_y + self.height - 20),
            text=text,
            color=C_LABEL, size=11, parent=self.tag,
        )

    # --------------------------------------------------------- mouse handlers

    def _on_left_click(self, sender, app_data) -> None:
        """Route a left click to the correct tool handler."""
        mx, my = dpg.get_mouse_pos(local=False)
        tool = self.state.active_tool

        if tool == "select":
            self._tool_select(mx, my)
        elif tool == "add_node":
            self._tool_add_node(mx, my)
        elif tool == "add_element":
            self._tool_add_element(mx, my)
        elif tool == "add_support":
            self._tool_add_support(mx, my)
        elif tool == "add_load":
            self._tool_add_load(mx, my)

    def _on_middle_click(self, sender, app_data) -> None:
        """Middle click resets pan and zoom to default."""
        self.transform.pan_x = self.width / 2
        self.transform.pan_y = self.height / 2
        self.transform.zoom = 1.0

    def _handle_pan(self) -> None:
        """Pan the canvas with middle-mouse drag."""
        if dpg.is_mouse_button_down(dpg.mvMouseButton_Middle):
            dx, dy = dpg.get_mouse_drag_delta(dpg.mvMouseButton_Middle)
            self.transform.pan_x += dx
            self.transform.pan_y += dy

    def _handle_scroll(self) -> None:
        """Zoom in/out with the scroll wheel."""
        scroll = dpg.get_mouse_wheel()
        if scroll > 0:
            self.transform.zoom_in()
        elif scroll < 0:
            self.transform.zoom_out()

    # ------------------------------------------------------------------ tools

    def _tool_select(self, sx: float, sy: float) -> None:
        """Select the object under the cursor, or deselect if empty space."""
        node_id = self._find_node_at_screen(sx, sy)
        if node_id is not None:
            self.state.select("node", node_id)
            return

        element_id = self._find_element_at_screen(sx, sy)
        if element_id is not None:
            self.state.select("element", element_id)
            return

        self.state.deselect()

    def _tool_add_node(self, sx: float, sy: float) -> None:
        """Place a new node at the clicked world position."""
        wx, wy = self.transform.screen_to_world(sx, sy)
        wx, wy = self._snap_to_grid(wx, wy)
        node = Node(x=round(wx, 4), y=round(wy, 4))
        self.state.scene.add_node(node)
        self.state.mark_dirty()
        self.state.select("node", node.id)

    def _tool_add_element(self, sx: float, sy: float) -> None:
        """
        First click selects start node; second click selects end node
        and creates the element.
        """
        node_id = self._find_node_at_screen(sx, sy)
        if node_id is None:
            return  # must click on an existing node

        if self.state.pending_element_node is None:
            # first click — store start node
            self.state.pending_element_node = node_id
        else:
            # second click — create element
            if node_id == self.state.pending_element_node:
                return  # can't connect a node to itself
            element = Element(
                node_start_id=self.state.pending_element_node,
                node_end_id=node_id,
            )
            self.state.scene.add_element(element)
            self.state.pending_element_node = None
            self.state.mark_dirty()
            self.state.select("element", element.id)

    def _tool_add_support(self, sx: float, sy: float) -> None:
        """
        Click a node to assign a default hinged support.
        The inspector is used to change the support type afterward.
        """
        node_id = self._find_node_at_screen(sx, sy)
        if node_id is None:
            return
        support = Support(node_id=node_id, support_type="hinged")
        self.state.scene.add_support(support)
        self.state.mark_dirty()
        self.state.select("support", support.id)

    def _tool_add_load(self, sx: float, sy: float) -> None:
        """
        Click a node to assign a default downward point load of 10 kN.
        The inspector is used to change magnitude and direction afterward.
        """
        node_id = self._find_node_at_screen(sx, sy)
        if node_id is not None:
            load = PointLoad(node_id=node_id, Fy=-10.0)
            self.state.scene.add_point_load(load)
            self.state.mark_dirty()
            self.state.select("point_load", load.id)
            return

        element_id = self._find_element_at_screen(sx, sy)
        if element_id is not None:
            load = DistributedLoad(element_id=element_id, q=-10.0)
            self.state.scene.add_distributed_load(load)
            self.state.mark_dirty()
            self.state.select("distributed_load", load.id)

    # ------------------------------------------------------------ hit testing

    def _find_node_at_screen(
        self, sx: float, sy: float
    ) -> Optional[int]:
        """
        Return the ID of the node closest to the screen position,
        within SNAP_THRESHOLD_PX. Returns None if no node is close enough.
        """
        best_id = None
        best_dist = SNAP_THRESHOLD_PX
        for node in self.state.scene.nodes:
            nx, ny = self.transform.world_to_screen(node.x, node.y)
            dist = ((sx - nx) ** 2 + (sy - ny) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_id = node.id
        return best_id

    def _find_element_at_screen(
        self, sx: float, sy: float
    ) -> Optional[int]:
        """
        Return the ID of the element whose line passes closest to the
        screen position, within SNAP_THRESHOLD_PX.
        """
        best_id = None
        best_dist = SNAP_THRESHOLD_PX
        for element in self.state.scene.elements:
            n1 = self.state.scene.get_node(element.node_start_id)
            n2 = self.state.scene.get_node(element.node_end_id)
            if n1 is None or n2 is None:
                continue
            s1 = self.transform.world_to_screen(n1.x, n1.y)
            s2 = self.transform.world_to_screen(n2.x, n2.y)
            dist = _point_to_segment_dist(sx, sy, s1[0], s1[1], s2[0], s2[1])
            if dist < best_dist:
                best_dist = dist
                best_id = element.id
        return best_id

    # ------------------------------------------------------------------ snap

    def _snap_to_grid(self, wx: float, wy: float) -> tuple[float, float]:
        """Snap world coordinates to the nearest 1.0m grid point."""
        return round(wx), round(wy)


# ------------------------------------------------------------------ helpers

def _point_to_segment_dist(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """
    Return the minimum distance from point (px, py) to line segment (a, b).
    """
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    closest_x = ax + t * dx
    closest_y = ay + t * dy
    return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5