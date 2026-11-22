"""Divide por separadores de dos vértices y ensambla los caminos resultantes."""
from pathlib import Path
import subprocess
from time import monotonic

from src.core.graph import Instance
from src.core import validate
from src.core.preprocess import reducir


def ejecutar(executable, graph, seconds, seed):
    data = [f"{graph.n} {graph.m}"]
    data.extend(f"{u} {v}" for u in range(graph.n) for v in sorted(graph.adj[u]) if u < v)
    try:
        proc = subprocess.run([executable, str(round(1000 * seconds)), str(seed)],
                              input="\n".join(data), text=True, capture_output=True,
                              check=True, timeout=seconds + 1)
    except subprocess.TimeoutExpired:
        return []
    return proc.stdout.splitlines()


def partir(graph, u, v):
    pending = set(range(graph.n)) - {u, v}
    parts = []
    while pending:
        component = [pending.pop()]
        for a in component:
            neighbors = graph.adj[a] & pending
            pending.difference_update(neighbors)
            component.extend(neighbors)
        parts.append(component)
    return parts


def subgrafo(graph, component, u, v):
    labels = sorted(component) + [u, v]
    index = {a: i for i, a in enumerate(labels)}
    adj = [{index[b] for b in graph.adj[a] if b in index} for a in labels]
    a, b, aux = len(labels) - 2, len(labels) - 1, len(labels)
    adj[a].discard(b)
    adj[b].discard(a)
    adj[a].add(aux)
    adj[b].add(aux)
    adj.append({a, b})
    return Instance(graph.name, len(adj), tuple(map(frozenset, adj)), sum(map(len, adj)) // 2), labels


def buscar(graph, separators, limit, seed):
    deadline = monotonic() + limit
    frontier = Path(separators).with_name("frontera")
    decomposition = Path(separators).with_name("descomposicion")
    branching = Path(separators).with_name("ramificacion")

    def visit(current, depth):
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None, "agotado"
        reduced = reducir(current)[0]
        cut = ejecutar(separators, reduced, min(remaining, 0.18), seed + depth) if depth < 20 else []
        if cut:
            u, v = map(int, cut[0].split())
            if u >= 0:
                components = sorted(partir(reduced, u, v), key=len, reverse=True)
                if len(components) != 2:
                    return None, "error_separador"
                paths = []
                for component in components:
                    child, labels = subgrafo(reduced, component, u, v)
                    route, status = visit(child, depth + 1)
                    if route is None:
                        return None, status if status.startswith("error") else "componente_pendiente"
                    aux = route.index(len(labels))
                    path = [labels[a] for a in route[aux + 1:] + route[:aux]]
                    paths.append(path if path[0] == u else path[::-1])
                route = paths[0] + paths[1][-2:0:-1]
                if not validate(current, route)["es_hamiltoniano"]:
                    return None, "error_ensamble"
                return route, "resuelto"
        if depth == 0:
            return None, "sin_separador"
        for executable, budget in ((frontier, 0.40), (decomposition, 0.65), (branching, 0.45)):
            remaining = deadline - monotonic()
            if remaining <= 0:
                return None, "agotado"
            output = ejecutar(executable, reduced, min(remaining, budget), seed + depth)
            if output and output[0].startswith("resuelto"):
                route = list(map(int, output[1].split()))
                if not validate(current, route)["es_hamiltoniano"]:
                    return None, "error_validacion_subgrafo"
                return route, "resuelto"
        return None, "componente_pendiente"

    return visit(graph, 0)
