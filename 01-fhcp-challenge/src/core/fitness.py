"""Fitness y validador (independientes de cualquier algoritmo).

fitness = número de aristas faltantes en el ciclo cerrado
          (pares consecutivos + arista de cierre último->primero).
fitness == 0  <=>  la permutación es un ciclo hamiltoniano.
"""
from .graph import Instance


def fitness(inst: Instance, route) -> int:
    """Aristas faltantes. Supone que `route` es una permutación válida de 0..n-1."""
    adj, n = inst.adj, len(route)
    faltantes = 0
    for i in range(n):
        if route[(i + 1) % n] not in adj[route[i]]:
            faltantes += 1
    return faltantes


def validate(inst: Instance, route) -> dict:
    """Validación completa (permutación + aristas). Para pruebas y reporte final."""
    n = inst.n
    es_perm = len(route) == n and sorted(route) == list(range(n))
    repetidos = len(route) - len(set(route))
    ausentes = n - len(set(v for v in route if 0 <= v < n))
    faltantes = fitness(inst, route) if es_perm else None
    return {
        "es_permutacion": es_perm,
        "repetidos": repetidos,
        "vertices_ausentes": ausentes,
        "aristas_faltantes": faltantes,
        "es_hamiltoniano": es_perm and faltantes == 0,
    }
