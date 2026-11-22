"""Búsqueda de ciclos por programación entera con cortes de conectividad."""
from time import monotonic

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


def buscar(graph, limit, seed):
    deadline = monotonic() + limit
    edges = [(u, v) for u in range(graph.n) for v in sorted(graph.adj[u]) if u < v]
    incident = [[] for _ in range(graph.n)]
    for j, (u, v) in enumerate(edges):
        incident[u].append(j)
        incident[v].append(j)

    rows = list(incident)
    lower = [2] * graph.n
    upper = [2] * graph.n
    integrality = np.ones(graph.m, dtype=np.uint8)
    bounds = Bounds(0, 1)
    costs = np.random.default_rng(seed).uniform(0, 0.001, graph.m)
    added_cuts = set()
    while monotonic() < deadline:
        row_indices = [i for i, cols in enumerate(rows) for _ in cols]
        col_indices = [j for cols in rows for j in cols]
        matrix = coo_matrix((np.ones(len(col_indices)), (row_indices, col_indices)),
                            shape=(len(rows), graph.m)).tocsc()
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        result = milp(costs, integrality=integrality, bounds=bounds,
                      constraints=LinearConstraint(matrix, lower, upper),
                      options={"time_limit": remaining, "mip_rel_gap": 10.0})
        if result.x is None:
            if result.status == 2:
                return None, "sin_ciclo"
            break

        cycle_edges = [[] for _ in range(graph.n)]
        for (u, v), value in zip(edges, result.x):
            if value > 0.5:
                cycle_edges[u].append(v)
                cycle_edges[v].append(u)
        if any(len(neighbors) != 2 for neighbors in cycle_edges):
            return None, "error_grado_subciclo"
        seen = set()
        components = []
        for start in range(graph.n):
            if start in seen:
                continue
            current, previous = start, -1
            route = []
            while current not in seen:
                route.append(current)
                seen.add(current)
                a, b = cycle_edges[current]
                current, previous = (b if a == previous else a), current
            components.append(route)
        if len(components) == 1:
            return components[0], "resuelto"

        fresh = 0
        for component in components:
            vertices = set(component)
            cut = tuple(sorted(j for u in vertices for j in incident[u]
                               if edges[j][0] not in vertices or edges[j][1] not in vertices))
            if cut in added_cuts:
                continue
            added_cuts.add(cut)
            rows.append(cut)
            lower.append(2)
            upper.append(np.inf)
            fresh += 1
        if not fresh:
            return None, "error_corte_repetido"
        costs = np.zeros(graph.m)
    return None, "tiempo agotado"
