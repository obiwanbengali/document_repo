"""Pathway-level graph construction, metrics, community detection and set similarity.

Every function here is a pure transformation over DataFrames / graphs with no database
or filesystem access, which is what makes this module the unit-testable core of the
workbench (see ``tests/``).

Determinism
-----------
All community detection is seeded and all outputs are sorted, so repeated runs over
unchanged inputs produce byte-identical tables.
"""

from __future__ import annotations

import logging
from typing import Any, Final, Iterable, Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd

LOGGER: Final = logging.getLogger(__name__)

#: Seed used for every randomised algorithm so runs are reproducible.
RANDOM_SEED: Final = 42

#: Edge attribute treated as the strength of a pathway-to-pathway relationship.
WEIGHT_ATTRIBUTE: Final = "transition_count"


# --------------------------------------------------------------------------------------
# Edge construction
# --------------------------------------------------------------------------------------
def aggregate_pathway_edges(transfers: pd.DataFrame) -> pd.DataFrame:
    """Aggregate resolved pathway transfers into a directed pathway-level edge list.

    Args:
        transfers: Unpivoted transfer rows. Must contain ``source_pathway_key``,
            ``resolved_pathway_key``, ``question_key``, ``answer_number``,
            ``source_order`` and ``branch``. Callers are expected to have already
            filtered to rows that resolved to a pathway.

    Returns:
        One row per (source, target) pair with columns:

        * ``transition_count`` -- unpivoted transfer records producing the edge. This
          counts branch slots (T1..T4), so a single answer offering the same target on
          all four branches contributes 4.
        * ``branches`` -- distinct (question, answer, branch) combinations producing
          the edge.
        * ``answer_branches`` -- distinct (question, answer) pairs, ignoring which
          T-slot carried the value.
        * ``source_question_count`` -- distinct source questions producing the edge.
        * ``source_order_count`` -- distinct source order positions producing the edge.

        Sorted by source then target.
    """
    required = {
        "source_pathway_key",
        "resolved_pathway_key",
        "question_key",
        "answer_number",
        "source_order",
        "branch",
    }
    missing = required - set(transfers.columns)
    if missing:
        raise ValueError(f"transfers is missing required columns: {sorted(missing)}")

    if transfers.empty:
        return pd.DataFrame(
            columns=[
                "source_pathway_key", "target_pathway_key", "transition_count",
                "branches", "answer_branches", "source_question_count",
                "source_order_count",
            ]
        )

    working = transfers.copy()
    working["_branch_key"] = (
        working["question_key"].astype(str)
        + "|" + working["answer_number"].astype(str)
        + "|" + working["branch"].astype(str)
    )
    working["_answer_key"] = (
        working["question_key"].astype(str) + "|" + working["answer_number"].astype(str)
    )

    grouped = (
        working.groupby(["source_pathway_key", "resolved_pathway_key"], dropna=False)
        .agg(
            transition_count=("branch", "size"),
            branches=("_branch_key", "nunique"),
            answer_branches=("_answer_key", "nunique"),
            source_question_count=("question_key", "nunique"),
            source_order_count=("source_order", "nunique"),
        )
        .reset_index()
        .rename(columns={"resolved_pathway_key": "target_pathway_key"})
    )
    return grouped.sort_values(
        ["source_pathway_key", "target_pathway_key"], ignore_index=True
    )


def build_pathway_graph(
    edges: pd.DataFrame,
    node_attributes: pd.DataFrame | None = None,
) -> nx.DiGraph:
    """Build the directed pathway graph from an aggregated edge list.

    Args:
        edges: Output of :func:`aggregate_pathway_edges`.
        node_attributes: Optional frame indexed by ``pathway_key`` whose columns become
            node attributes. Pathways present here but absent from ``edges`` are added
            as isolated nodes, so pathways with no transfers still appear in the graph.

    Returns:
        A ``networkx.DiGraph``. Self loops are preserved: a pathway transferring to
        itself is a real structure in this data, not an artefact to clean away.
    """
    graph = nx.DiGraph()

    if node_attributes is not None and not node_attributes.empty:
        if "pathway_key" not in node_attributes.columns:
            raise ValueError("node_attributes must contain a 'pathway_key' column")
        for record in node_attributes.to_dict("records"):
            key = record.pop("pathway_key")
            graph.add_node(key, **record)

    attribute_columns = [
        column
        for column in (
            "transition_count", "branches", "answer_branches",
            "source_question_count", "source_order_count",
        )
        if column in edges.columns
    ]
    for record in edges.to_dict("records"):
        source = record["source_pathway_key"]
        target = record["target_pathway_key"]
        graph.add_edge(
            source,
            target,
            **{column: record[column] for column in attribute_columns},
        )
    return graph


# --------------------------------------------------------------------------------------
# Graph metrics
# --------------------------------------------------------------------------------------
def graph_summary(graph: nx.DiGraph) -> dict[str, Any]:
    """Compute whole-graph structural metrics.

    Self loops are excluded from the reciprocity calculation (a self loop is trivially
    its own reverse) but are reported separately and are retained everywhere else.
    """
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    self_loops = list(nx.selfloop_edges(graph))

    reciprocal_pairs = sorted(
        {
            (min(u, v), max(u, v))
            for u, v in graph.edges()
            if u != v and graph.has_edge(v, u)
        }
    )

    weakly = list(nx.weakly_connected_components(graph)) if node_count else []
    strongly = list(nx.strongly_connected_components(graph)) if node_count else []
    non_trivial_scc = [component for component in strongly if len(component) > 1]

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": nx.density(graph) if node_count > 1 else 0.0,
        "self_loop_count": len(self_loops),
        "reciprocal_pair_count": len(reciprocal_pairs),
        "reciprocal_edge_count": len(reciprocal_pairs) * 2,
        "weakly_connected_components": len(weakly),
        "largest_weakly_connected_component": max((len(c) for c in weakly), default=0),
        "strongly_connected_components": len(strongly),
        "non_trivial_strongly_connected_components": len(non_trivial_scc),
        "largest_strongly_connected_component": max((len(c) for c in strongly), default=0),
        "isolated_node_count": sum(
            1 for node in graph.nodes() if graph.degree(node) == 0
        ),
        "total_transition_count": int(
            sum(data.get(WEIGHT_ATTRIBUTE, 0) for _, _, data in graph.edges(data=True))
        ),
    }


def node_metrics(graph: nx.DiGraph) -> pd.DataFrame:
    """Compute per-node centrality and degree metrics.

    Betweenness is computed **unweighted**: the edge weight here is a transition count,
    where a larger value means a stronger relationship, but ``networkx`` interprets
    edge weights as distances, where larger means further apart. Feeding counts in as
    distances would invert the meaning, so the unweighted form is used and the weighted
    view is provided through the degree columns and PageRank instead.

    PageRank does use the transition count, where a larger weight correctly means more
    probability flow.
    """
    if graph.number_of_nodes() == 0:
        return pd.DataFrame(
            columns=[
                "pathway_key", "in_degree", "out_degree", "total_degree",
                "weighted_in_degree", "weighted_out_degree", "weighted_total_degree",
                "betweenness_centrality", "pagerank", "self_loop",
                "successor_count", "predecessor_count",
            ]
        )

    betweenness = nx.betweenness_centrality(graph, normalized=True, seed=RANDOM_SEED)
    try:
        pagerank = nx.pagerank(graph, weight=WEIGHT_ATTRIBUTE)
    except nx.PowerIterationFailedConvergence:  # pragma: no cover - defensive
        LOGGER.warning("PageRank did not converge; retrying unweighted.")
        pagerank = nx.pagerank(graph, weight=None)

    self_loop_nodes = {u for u, v in nx.selfloop_edges(graph)}

    records = []
    for node in graph.nodes():
        records.append(
            {
                "pathway_key": node,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "total_degree": graph.degree(node),
                "weighted_in_degree": graph.in_degree(node, weight=WEIGHT_ATTRIBUTE),
                "weighted_out_degree": graph.out_degree(node, weight=WEIGHT_ATTRIBUTE),
                "weighted_total_degree": graph.degree(node, weight=WEIGHT_ATTRIBUTE),
                "betweenness_centrality": betweenness[node],
                "pagerank": pagerank[node],
                "self_loop": node in self_loop_nodes,
                "successor_count": len(set(graph.successors(node)) - {node}),
                "predecessor_count": len(set(graph.predecessors(node)) - {node}),
            }
        )
    return pd.DataFrame(records).sort_values("pathway_key", ignore_index=True)


def edge_table(graph: nx.DiGraph) -> pd.DataFrame:
    """Return the graph's edges as a sorted DataFrame, including self-loop flags."""
    records = []
    for source, target, data in graph.edges(data=True):
        record = {"source_pathway_key": source, "target_pathway_key": target}
        record.update(data)
        record["is_self_loop"] = source == target
        record["is_reciprocal"] = source != target and graph.has_edge(target, source)
        records.append(record)
    if not records:
        return pd.DataFrame(
            columns=["source_pathway_key", "target_pathway_key", "is_self_loop",
                     "is_reciprocal"]
        )
    return pd.DataFrame(records).sort_values(
        ["source_pathway_key", "target_pathway_key"], ignore_index=True
    )


def undirected_projection(graph: nx.DiGraph) -> nx.Graph:
    """Collapse the directed graph to a weighted undirected graph.

    Reciprocal edges have their transition counts summed. Self loops are dropped
    because they contribute nothing to community structure and several community
    algorithms treat them inconsistently.
    """
    projected = nx.Graph()
    projected.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        if source == target:
            continue
        weight = float(data.get(WEIGHT_ATTRIBUTE, 1) or 1)
        if projected.has_edge(source, target):
            projected[source][target]["weight"] += weight
        else:
            projected.add_edge(source, target, weight=weight)
    return projected


# --------------------------------------------------------------------------------------
# Community detection
# --------------------------------------------------------------------------------------
def detect_communities(graph: nx.DiGraph) -> dict[str, dict[str, int]]:
    """Run the available community-detection algorithms on the undirected projection.

    Returns:
        Mapping of algorithm name to ``{node: community_id}``. Community ids are
        renumbered so that id 0 is the largest community, which keeps ids stable
        against the arbitrary ordering the algorithms emit.

        The returned communities are **graph-derived communities**: they are a property
        of the transfer topology only. They are not clinical families and carry no
        clinical endorsement.
    """
    projection = undirected_projection(graph)
    results: dict[str, dict[str, int]] = {}

    if projection.number_of_nodes() == 0:
        return results

    # Louvain via python-louvain, when installed.
    try:
        import community as community_louvain  # type: ignore[import-untyped]

        partition = community_louvain.best_partition(
            projection, weight="weight", random_state=RANDOM_SEED
        )
        results["louvain"] = _renumber_by_size(partition)
    except ImportError:
        LOGGER.warning("python-louvain not installed; skipping the Louvain partition.")
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Louvain community detection failed: %s", exc)

    # Louvain as implemented in networkx (available from 3.0) as an independent check.
    if hasattr(nx.community, "louvain_communities"):
        try:
            communities = nx.community.louvain_communities(
                projection, weight="weight", seed=RANDOM_SEED
            )
            results["networkx_louvain"] = _renumber_by_size(
                _membership_from_sets(communities)
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("networkx Louvain failed: %s", exc)

    # Greedy modularity maximisation (Clauset-Newman-Moore).
    try:
        communities = nx.community.greedy_modularity_communities(
            projection, weight="weight"
        )
        results["greedy_modularity"] = _renumber_by_size(
            _membership_from_sets(communities)
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Greedy modularity community detection failed: %s", exc)

    return results


#: Community-detection methods :func:`partition_undirected` can run. ``strongly_connected``
#: is handled by :func:`detect_community_methods` because it needs edge direction.
UNDIRECTED_METHODS: Final[tuple[str, ...]] = (
    "louvain",
    "networkx_louvain",
    "leiden",
    "greedy_modularity",
    "label_propagation",
)


class CommunityMethodUnavailableError(RuntimeError):
    """Raised when a community-detection method's library is not installed.

    Distinguished from a failure so that a caller can record "not available" rather
    than "produced no communities" -- in an evidence base those mean different things.
    """


def partition_undirected(
    projection: nx.Graph,
    method: str,
    *,
    resolution: float = 1.0,
) -> dict[str, int]:
    """Partition an undirected weighted graph with one named method.

    Phase 2 compares several algorithms deliberately: no single community algorithm is
    treated as ground truth, so each is exposed individually rather than hidden behind
    a "best" choice.

    Args:
        projection: Undirected graph whose edges carry a ``weight`` attribute.
        method: One of :data:`UNDIRECTED_METHODS`.
        resolution: Resolution parameter, used by Leiden only. 1.0 is the
            modularity-equivalent default.

    Returns:
        ``{node: community_id}``, renumbered so id 0 is the largest community.

    Raises:
        ValueError: If ``method`` is not recognised.
        CommunityMethodUnavailableError: If the method's library is not installed.
    """
    if method not in UNDIRECTED_METHODS:
        raise ValueError(
            f"Unknown undirected community method {method!r}. "
            f"Known: {list(UNDIRECTED_METHODS)}."
        )
    if projection.number_of_nodes() == 0:
        return {}

    if method == "louvain":
        try:
            import community as community_louvain  # type: ignore[import-untyped]
        except ImportError as exc:
            raise CommunityMethodUnavailableError(
                "python-louvain is not installed."
            ) from exc
        partition = community_louvain.best_partition(
            projection, weight="weight", random_state=RANDOM_SEED
        )
        return _renumber_by_size(partition)

    if method == "networkx_louvain":
        communities = nx.community.louvain_communities(
            projection, weight="weight", seed=RANDOM_SEED
        )
        return _renumber_by_size(_membership_from_sets(communities))

    if method == "leiden":
        return _renumber_by_size(_leiden_partition(projection, resolution=resolution))

    if method == "greedy_modularity":
        communities = nx.community.greedy_modularity_communities(projection, weight="weight")
        return _renumber_by_size(_membership_from_sets(communities))

    # label_propagation. The asynchronous variant accepts a seed, so it is used in
    # preference to the semi-synchronous one, which is not seedable and would make the
    # run non-reproducible.
    communities = nx.community.asyn_lpa_communities(
        projection, weight="weight", seed=RANDOM_SEED
    )
    return _renumber_by_size(_membership_from_sets(communities))


def _leiden_partition(projection: nx.Graph, *, resolution: float) -> dict[str, int]:
    """Run the Leiden algorithm via ``leidenalg``.

    Leiden is included because it repairs a known Louvain defect -- Louvain can emit
    internally disconnected communities -- so agreement between the two is meaningful
    evidence rather than two runs of the same idea.

    Raises:
        CommunityMethodUnavailableError: If ``leidenalg``/``igraph`` is not installed.
    """
    try:
        import igraph  # type: ignore[import-untyped]
        import leidenalg  # type: ignore[import-untyped]
    except ImportError as exc:
        raise CommunityMethodUnavailableError(
            "leidenalg and igraph are not installed; Leiden was not run."
        ) from exc

    nodes = sorted(projection.nodes())
    index = {node: position for position, node in enumerate(nodes)}
    edges = []
    weights = []
    for source, target, data in projection.edges(data=True):
        edges.append((index[source], index[target]))
        weights.append(float(data.get("weight", 1.0) or 1.0))

    igraph_graph = igraph.Graph(n=len(nodes), edges=edges, directed=False)
    partition = leidenalg.find_partition(
        igraph_graph,
        leidenalg.RBConfigurationVertexPartition,
        weights=weights or None,
        resolution_parameter=resolution,
        seed=RANDOM_SEED,
        n_iterations=-1,  # iterate to convergence, which makes the result seed-stable
    )
    return {
        nodes[position]: community
        for position, community in enumerate(partition.membership)
    }


def strongly_connected_communities(graph: nx.DiGraph) -> dict[str, int]:
    """Treat each strongly connected component as a community.

    This is not a community-detection algorithm and is not expected to compete with
    one. It is included because a strongly connected component is the strongest
    possible structural claim about a set of pathways -- every member can reach every
    other by transfers -- so it bounds what any partition could legitimately split.
    """
    if graph.number_of_nodes() == 0:
        return {}
    components = sorted(
        (sorted(component) for component in nx.strongly_connected_components(graph)),
        key=lambda component: (-len(component), component[0]),
    )
    return _renumber_by_size(_membership_from_sets(components))


def detect_community_methods(
    graph: nx.DiGraph,
    methods: Sequence[str],
    *,
    leiden_resolution: float = 1.0,
) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    """Run several community-detection methods over one pathway graph.

    Args:
        graph: The directed pathway graph.
        methods: Method names. ``strongly_connected`` runs on the directed graph;
            everything else runs on the undirected projection.
        leiden_resolution: Resolution parameter passed to Leiden.

    Returns:
        ``(partitions, unavailable)`` where ``partitions`` maps method name to
        ``{node: community_id}`` and ``unavailable`` maps a method name that could not
        run to the reason. A method is never dropped silently: it appears in exactly
        one of the two mappings.
    """
    partitions: dict[str, dict[str, int]] = {}
    unavailable: dict[str, str] = {}
    projection = undirected_projection(graph)

    for method in methods:
        try:
            if method == "strongly_connected":
                partitions[method] = strongly_connected_communities(graph)
            else:
                partitions[method] = partition_undirected(
                    projection, method, resolution=leiden_resolution
                )
        except CommunityMethodUnavailableError as exc:
            LOGGER.warning("Community method %r unavailable: %s", method, exc)
            unavailable[method] = str(exc)
        except Exception as exc:  # noqa: BLE001 - one failed method must not lose the rest
            LOGGER.warning(
                "Community method %r failed: %s: %s", method, type(exc).__name__, exc
            )
            unavailable[method] = f"{type(exc).__name__}: {exc}"
    return partitions, unavailable


def adjusted_rand_index(
    membership_a: Mapping[str, Any],
    membership_b: Mapping[str, Any],
) -> float:
    """Return the adjusted Rand index between two partitions of the same nodes.

    Used to quantify how much a candidate family set changes when a weighting or an
    algorithm changes. 1.0 means identical partitions, 0.0 means the agreement is no
    better than chance, and negative values mean worse than chance.

    Only nodes present in both mappings are compared, because a method that did not
    place a node cannot agree or disagree about it.

    Returns:
        The adjusted Rand index, or NaN when fewer than two nodes are shared.
    """
    shared = sorted(set(membership_a) & set(membership_b))
    if len(shared) < 2:
        return float("nan")

    labels_a = [membership_a[node] for node in shared]
    labels_b = [membership_b[node] for node in shared]
    contingency = (
        pd.crosstab(pd.Series(labels_a, dtype="object"), pd.Series(labels_b, dtype="object"))
        .to_numpy()
        .astype(np.float64)
    )

    def choose2(values: np.ndarray) -> np.ndarray:
        return values * (values - 1.0) / 2.0

    sum_cells = float(choose2(contingency).sum())
    sum_rows = float(choose2(contingency.sum(axis=1)).sum())
    sum_columns = float(choose2(contingency.sum(axis=0)).sum())
    total_pairs = float(choose2(np.array([float(len(shared))]))[0])

    expected = sum_rows * sum_columns / total_pairs
    maximum = 0.5 * (sum_rows + sum_columns)
    if maximum == expected:
        # Both partitions are trivial (all nodes in one community, or all singletons).
        # The index is undefined there; 1.0 is returned only when they truly match.
        return 1.0 if sum_cells == maximum else 0.0
    return float((sum_cells - expected) / (maximum - expected))


def undirected_hop_distances(graph: nx.DiGraph, *, max_hops: int) -> pd.DataFrame:
    """Return unordered pathway pairs within ``max_hops`` of each other.

    Direction is dropped for the distance calculation because a transfer route in
    either direction makes two pathways structurally adjacent, which is what a family
    boundary question is about. Direction is preserved separately by the direct-edge
    and reverse-edge flags the caller adds.

    All-pairs distances are not exported: at 838 nodes that is ~350k rows of mostly
    unrelated pairs. The cutoff is a reporting decision, stated in configuration.

    Args:
        graph: The directed pathway graph.
        max_hops: Largest shortest-path length to include. Must be at least 1.

    Returns:
        Frame with ``pathway_key_a``, ``pathway_key_b`` (``a < b``) and
        ``shortest_path_hops``, sorted.
    """
    if max_hops < 1:
        raise ValueError(f"max_hops must be at least 1, got {max_hops}.")
    projection = undirected_projection(graph)
    records: dict[tuple[str, str], int] = {}
    for node in projection.nodes():
        lengths = nx.single_source_shortest_path_length(projection, node, cutoff=max_hops)
        for other, hops in lengths.items():
            if other == node:
                continue
            key = (node, other) if node < other else (other, node)
            existing = records.get(key)
            if existing is None or hops < existing:
                records[key] = hops
    if not records:
        return pd.DataFrame(columns=["pathway_key_a", "pathway_key_b", "shortest_path_hops"])
    frame = pd.DataFrame(
        [
            {"pathway_key_a": pair[0], "pathway_key_b": pair[1], "shortest_path_hops": hops}
            for pair, hops in records.items()
        ]
    )
    return frame.sort_values(["pathway_key_a", "pathway_key_b"], ignore_index=True)


def _membership_from_sets(communities: Iterable[Iterable[str]]) -> dict[str, int]:
    """Convert an iterable of node sets into a ``{node: community_id}`` mapping."""
    membership: dict[str, int] = {}
    for index, nodes in enumerate(communities):
        for node in nodes:
            membership[node] = index
    return membership


def _renumber_by_size(membership: Mapping[str, int]) -> dict[str, int]:
    """Renumber community ids so id 0 is the largest community.

    Ties are broken by the sorted first member, making the numbering deterministic.
    """
    groups: dict[int, list[str]] = {}
    for node, community_id in membership.items():
        groups.setdefault(community_id, []).append(node)
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), sorted(item[1])[0]))
    remapped: dict[str, int] = {}
    for new_id, (_, nodes) in enumerate(ordered):
        for node in nodes:
            remapped[node] = new_id
    return remapped


def modularity_score(graph: nx.DiGraph, membership: Mapping[str, int]) -> float:
    """Return the modularity of a partition on the undirected projection."""
    projection = undirected_projection(graph)
    groups: dict[int, set[str]] = {}
    for node, community_id in membership.items():
        if node in projection:
            groups.setdefault(community_id, set()).add(node)
    covered = set().union(*groups.values()) if groups else set()
    leftover = set(projection.nodes()) - covered
    partition: list[set[str]] = [nodes for _, nodes in sorted(groups.items())]
    partition.extend({node} for node in sorted(leftover))
    if not partition:
        return float("nan")
    return float(nx.community.modularity(projection, partition, weight="weight"))


# --------------------------------------------------------------------------------------
# Cohesion: internal vs external edges for any grouping of pathways
# --------------------------------------------------------------------------------------
def group_cohesion(
    graph: nx.DiGraph,
    membership: Mapping[str, Any],
    *,
    group_label: str = "group_id",
) -> pd.DataFrame:
    """Measure how self-contained each group of pathways is in the transfer graph.

    This is the shared engine behind symptom-group cohesion, clinical-area cohesion and
    graph-community cohesion, so all three use an identical definition.

    An edge is *internal* to a group when both endpoints belong to that group. An edge
    is *outgoing* when the source belongs and the target does not, and *incoming* when
    the reverse holds. Self loops count as internal.

    Because a pathway may belong to several groups (clinical areas in particular), this
    accepts a mapping to either a single group or an iterable of groups.

    Args:
        graph: The directed pathway graph.
        membership: Mapping of ``pathway_key`` to a group id, or to an iterable of
            group ids for overlapping groupings.
        group_label: Name given to the group column in the result.

    Returns:
        One row per group with internal/outgoing/incoming edge counts and the
        internal-edge percentage, which is
        ``internal / (internal + outgoing) * 100`` -- the share of edges *leaving the
        group's pathways* that stay inside the group. Groups whose pathways have no
        outgoing-or-internal edges get NaN rather than a misleading 0 or 100.
    """
    expanded: dict[str, set[Any]] = {}
    for node, groups in membership.items():
        if groups is None:
            continue
        if isinstance(groups, (str, bytes)) or not isinstance(groups, Iterable):
            expanded[node] = {groups}
        else:
            values = {value for value in groups if value is not None}
            if values:
                expanded[node] = values

    all_groups = sorted(
        {group for groups in expanded.values() for group in groups},
        key=lambda value: (str(type(value)), str(value)),
    )
    group_members: dict[Any, set[str]] = {group: set() for group in all_groups}
    for node, groups in expanded.items():
        for group in groups:
            group_members[group].add(node)

    records = []
    for group in all_groups:
        members = group_members[group]
        present = {node for node in members if node in graph}
        internal = outgoing = incoming = 0
        internal_weight = outgoing_weight = 0
        for node in present:
            for _, target, data in graph.out_edges(node, data=True):
                weight = int(data.get(WEIGHT_ATTRIBUTE, 0) or 0)
                if target in members:
                    internal += 1
                    internal_weight += weight
                else:
                    outgoing += 1
                    outgoing_weight += weight
            for source, _, _ in graph.in_edges(node, data=True):
                if source not in members:
                    incoming += 1

        boundary_total = internal + outgoing
        records.append(
            {
                group_label: group,
                "pathway_count": len(members),
                "pathways_in_graph": len(present),
                "internal_edges": internal,
                "outgoing_edges": outgoing,
                "incoming_edges": incoming,
                "internal_transition_count": internal_weight,
                "outgoing_transition_count": outgoing_weight,
                "internal_edge_percentage": (
                    round(100.0 * internal / boundary_total, 2)
                    if boundary_total
                    else float("nan")
                ),
            }
        )
    return pd.DataFrame(records)


def community_summary(
    graph: nx.DiGraph,
    membership: Mapping[str, int],
    *,
    algorithm: str,
) -> pd.DataFrame:
    """Summarise a community partition using :func:`group_cohesion`."""
    summary = group_cohesion(graph, membership, group_label="community_id")
    if summary.empty:
        return summary
    summary.insert(0, "algorithm", algorithm)
    summary = summary.rename(columns={"outgoing_edges": "external_edges"})
    return summary.sort_values(
        ["pathway_count", "community_id"], ascending=[False, True], ignore_index=True
    )


# --------------------------------------------------------------------------------------
# Set similarity
# --------------------------------------------------------------------------------------
def jaccard_similarity(
    membership: pd.DataFrame,
    *,
    entity_column: str,
    feature_column: str,
    min_intersection: int = 1,
) -> pd.DataFrame:
    """Compute pairwise intersection, union and Jaccard similarity between entities.

    Implemented as a boolean matrix product rather than pairwise Python loops: with ~800
    pathways and a few thousand features the matrix is small, and the product gives all
    intersection counts in one deterministic step.

    Only pairs with ``intersection >= min_intersection`` are returned. With the default
    of 1 that means every emitted row represents genuine overlap; the ~330k all-zero
    pairs are omitted rather than padding the output. Pass ``min_intersection=0`` to get
    the full cartesian upper triangle.

    Args:
        membership: Long-format frame of entity/feature pairs. Duplicate pairs are
            de-duplicated first, so the result is a set comparison.
        entity_column: Column holding the entity (e.g. ``pathway_key``).
        feature_column: Column holding the feature (e.g. ``question_key``).
        min_intersection: Minimum shared features for a pair to be emitted.

    Returns:
        Frame with ``<entity>_a``, ``<entity>_b``, ``set_size_a``, ``set_size_b``,
        ``intersection_count``, ``union_count`` and ``jaccard_similarity``, restricted
        to the upper triangle (``a < b``) and sorted by descending similarity.
    """
    for column in (entity_column, feature_column):
        if column not in membership.columns:
            raise ValueError(f"membership is missing required column {column!r}")

    pairs = (
        membership[[entity_column, feature_column]]
        .dropna()
        .drop_duplicates()
    )
    entities = sorted(pairs[entity_column].unique())
    features = sorted(pairs[feature_column].unique())

    empty = pd.DataFrame(
        columns=[
            f"{entity_column}_a", f"{entity_column}_b", "set_size_a", "set_size_b",
            "intersection_count", "union_count", "jaccard_similarity",
        ]
    )
    if len(entities) < 2 or not features:
        return empty

    entity_index = {value: position for position, value in enumerate(entities)}
    feature_index = {value: position for position, value in enumerate(features)}

    matrix = np.zeros((len(entities), len(features)), dtype=np.float32)
    matrix[
        pairs[entity_column].map(entity_index).to_numpy(dtype=np.int64),
        pairs[feature_column].map(feature_index).to_numpy(dtype=np.int64),
    ] = 1.0

    intersection = matrix @ matrix.T
    sizes = matrix.sum(axis=1)

    row_positions, column_positions = np.triu_indices(len(entities), k=1)
    intersection_counts = intersection[row_positions, column_positions]

    keep = intersection_counts >= max(min_intersection, 0)
    if min_intersection <= 0:
        keep = np.ones_like(intersection_counts, dtype=bool)
    row_positions = row_positions[keep]
    column_positions = column_positions[keep]
    intersection_counts = intersection_counts[keep]

    if row_positions.size == 0:
        return empty

    size_a = sizes[row_positions]
    size_b = sizes[column_positions]
    union_counts = size_a + size_b - intersection_counts

    entity_array = np.array(entities, dtype=object)
    result = pd.DataFrame(
        {
            f"{entity_column}_a": entity_array[row_positions],
            f"{entity_column}_b": entity_array[column_positions],
            "set_size_a": size_a.astype(np.int64),
            "set_size_b": size_b.astype(np.int64),
            "intersection_count": intersection_counts.astype(np.int64),
            "union_count": union_counts.astype(np.int64),
        }
    )
    result["jaccard_similarity"] = np.where(
        result["union_count"] > 0,
        result["intersection_count"] / result["union_count"],
        0.0,
    ).round(6)
    return result.sort_values(
        ["jaccard_similarity", f"{entity_column}_a", f"{entity_column}_b"],
        ascending=[False, True, True],
        ignore_index=True,
    )


def pair_count(n: int) -> int:
    """Return the number of unordered pairs in a set of ``n`` items."""
    return n * (n - 1) // 2


def describe_distribution(
    values: Sequence[float] | pd.Series,
    *,
    percentiles: Sequence[int] = (75, 90, 95, 99),
) -> dict[str, float]:
    """Summarise a numeric distribution with the percentile set used across Phase 1.

    Returns min / mean / median / requested percentiles / max, plus ``count``. Returns
    NaNs (not an exception) for an empty input so one empty metric cannot abort a run.
    """
    series = pd.Series(list(values), dtype="float64") if not isinstance(
        values, pd.Series
    ) else values.astype("float64")
    series = series.dropna()
    if series.empty:
        summary = {"count": 0, "min": float("nan"), "mean": float("nan"),
                   "median": float("nan"), "max": float("nan")}
        summary.update({f"p{p}": float("nan") for p in percentiles})
        return summary

    summary: dict[str, float] = {
        "count": int(series.size),
        "min": float(series.min()),
        "mean": round(float(series.mean()), 4),
        "median": float(series.median()),
    }
    for percentile in percentiles:
        summary[f"p{percentile}"] = round(
            float(np.percentile(series, percentile)), 4
        )
    summary["max"] = float(series.max())
    return summary
