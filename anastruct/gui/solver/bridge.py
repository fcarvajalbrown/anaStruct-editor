"""
bridge.py
---------
The sole point of contact between the GUI and the anastruct library.

Translates a Scene instance into anastruct SystemElements API calls,
runs the solver, and returns the results as a SolveResult object.

No other file in gui/ should import from anastruct directly.

ID mapping
----------
anastruct assigns node IDs sequentially (starting at 1) as elements are
added via add_element(). Our Scene uses arbitrary integer IDs (UUID-derived).
This module builds a mapping:

    node_map : dict[our_node_id -> anastruct_node_id]

by tracking which anastruct node ID is assigned to each of our nodes
as elements are inserted. This mapping is also stored in SolveResult
so the GUI can correlate result data back to scene objects.
"""

from dataclasses import dataclass, field
from typing import Optional

from anastruct.fem.system import SystemElements

from ..model.scene import Scene
from ..model.support import SupportType


@dataclass
class SolveResult:
    """
    Container for the results returned by anastruct after a successful solve.

    Attributes
    ----------
    node_map : dict[int, int]
        Maps our Node.id -> anastruct internal node ID.
    element_map : dict[int, int]
        Maps our Element.id -> anastruct internal element ID.
    system : SystemElements
        The fully solved anastruct SystemElements instance.
        Use this to call .show_results(), .get_node_results(), etc.
    error : str or None
        If solving failed, contains the error message. None on success.
    """

    node_map: dict = field(default_factory=dict)
    element_map: dict = field(default_factory=dict)
    system: Optional[SystemElements] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """True if the solve completed without error."""
        return self.error is None and self.system is not None


def solve(scene: Scene) -> SolveResult:
    """
    Translate a Scene into anastruct calls, solve, and return results.

    Parameters
    ----------
    scene : Scene
        The structural model to solve. Must pass scene.is_solvable().

    Returns
    -------
    SolveResult
        Contains the solved SystemElements instance and ID mappings.
        On failure, SolveResult.success is False and .error holds the message.
    """
    solvable, reason = scene.is_solvable()
    if not solvable:
        return SolveResult(error=reason)

    try:
        ss = SystemElements()
        node_map: dict[int, int] = {}
        element_map: dict[int, int] = {}

        # --------------------------------------------------------- add elements
        # anastruct creates nodes implicitly when elements are added.
        # We track which anastruct node ID gets assigned to each of our nodes
        # by inspecting ss.node_map after each add_element() call.

        for element in scene.elements:
            start_node = scene.get_node(element.node_start_id)
            end_node = scene.get_node(element.node_end_id)

            if start_node is None or end_node is None:
                return SolveResult(
                    error=f"Element id={element.id} references a missing node."
                )

            kwargs = {
                "location": [
                    [start_node.x, start_node.y],
                    [end_node.x, end_node.y],
                ],
                "EA": element.EA,
            }

            # EI is irrelevant for truss elements
            if element.element_type == "general":
                kwargs["EI"] = element.EI

            if element.element_type == "truss":
                kwargs["element_type"] = "truss"

            ss.add_element(**kwargs)

            # anastruct numbers elements from 1 sequentially
            anastruct_element_id = len(ss.element_map)
            element_map[element.id] = anastruct_element_id

            # map our node IDs to anastruct node IDs using vertex coordinates
            for our_id, (our_x, our_y) in [
                (element.node_start_id, (start_node.x, start_node.y)),
                (element.node_end_id, (end_node.x, end_node.y)),
            ]:
                if our_id not in node_map:
                    anastruct_node_id = ss.find_node_id(vertex=[our_x, our_y])
                    if anastruct_node_id is not None:
                        node_map[our_id] = anastruct_node_id

        # -------------------------------------------------------- add supports
        for support in scene.supports:
            anastruct_nid = node_map.get(support.node_id)
            if anastruct_nid is None:
                return SolveResult(
                    error=f"Support references node id={support.node_id} "
                          f"which has no mapped anastruct node."
                )

            _apply_support(ss, anastruct_nid, support.support_type, support.k, support.translation)

        # ------------------------------------------------------- add point loads
        for load in scene.point_loads:
            anastruct_nid = node_map.get(load.node_id)
            if anastruct_nid is None:
                return SolveResult(
                    error=f"PointLoad references node id={load.node_id} "
                          f"which has no mapped anastruct node."
                )
            ss.point_load(node_id=anastruct_nid, Fx=load.Fx, Fy=load.Fy)

        # ------------------------------------------------- add distributed loads
        for load in scene.distributed_loads:
            anastruct_eid = element_map.get(load.element_id)
            if anastruct_eid is None:
                return SolveResult(
                    error=f"DistributedLoad references element id={load.element_id} "
                          f"which has no mapped anastruct element."
                )
            ss.q_load(q=load.q, element_id=anastruct_eid, direction=load.direction)

        # ----------------------------------------------------------------- solve
        ss.solve()

        return SolveResult(node_map=node_map, element_map=element_map, system=ss)

    except Exception as exc:
        return SolveResult(error=str(exc))


def _apply_support(
    ss: SystemElements,
    node_id: int,
    support_type: SupportType,
    k: float,
    translation: int,
) -> None:
    """
    Call the correct anastruct support method for the given support type.

    Parameters
    ----------
    ss : SystemElements
        The anastruct system to apply the support to.
    node_id : int
        The anastruct-internal node ID.
    support_type : SupportType
        One of "fixed", "hinged", "roller_x", "roller_y", "spring".
    k : float
        Spring stiffness. Only used when support_type is "spring".
    translation : int
        Spring direction. Only used when support_type is "spring".
    """
    if support_type == "fixed":
        ss.add_support_fixed(node_id=node_id)
    elif support_type == "hinged":
        ss.add_support_hinged(node_id=node_id)
    elif support_type == "roller_x":
        ss.add_support_roll(node_id=node_id, direction="x")
    elif support_type == "roller_y":
        ss.add_support_roll(node_id=node_id, direction="y")
    elif support_type == "spring":
        ss.add_support_spring(node_id=node_id, translation=translation, k=k)
    else:
        raise ValueError(f"Unknown support type: {support_type!r}")