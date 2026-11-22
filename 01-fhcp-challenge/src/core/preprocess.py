"""Preprocesamiento por aristas forzadas (técnica usada por los ganadores del FHCP Challenge).

Un vértice de grado 2 obliga a usar sus dos aristas en cualquier ciclo hamiltoniano. Un vértice con dos
aristas forzadas no puede usar ninguna otra, así que sus demás aristas se eliminan; eso puede bajar otros
vértices a grado 2 y se repite hasta que nada cambia. Todo ciclo hamiltoniano del grafo original sigue
existiendo en el grafo reducido (solo se quitan aristas que ningún ciclo puede usar).
"""
from .graph import Instance


def reducir(instance: Instance):
    """Devuelve (instancia_reducida, aristas_forzadas_por_vértice, aristas_eliminadas)."""
    n = instance.n
    adj = [set(a) for a in instance.adj]
    forz = [set() for _ in range(n)]
    cambio, eliminadas = True, 0
    while cambio:
        cambio = False
        for v in range(n):
            if len(adj[v]) == 2:
                for w in adj[v]:
                    if w not in forz[v]:
                        forz[v].add(w)
                        forz[w].add(v)
                        cambio = True
        for v in range(n):
            if len(forz[v]) > 2:
                raise ValueError("Instancia sin ciclo hamiltoniano: un vértice tiene más de 2 aristas forzadas")
            if len(forz[v]) == 2:
                for w in list(adj[v]):
                    if w not in forz[v]:
                        adj[v].discard(w)
                        adj[w].discard(v)
                        eliminadas += 1
                        cambio = True
    m = sum(len(a) for a in adj) // 2
    red = Instance(instance.name + "_red", n, tuple(frozenset(a) for a in adj), m, instance.sha256)
    return red, forz, eliminadas
