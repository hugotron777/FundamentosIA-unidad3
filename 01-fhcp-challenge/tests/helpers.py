import random
from src.core.graph import Instance


def instancia_plantada(n, extra, seed=0):
    """Grafo con un ciclo hamiltoniano plantado (existe solución) + `extra` aristas al azar."""
    rng = random.Random(f"plantada-{seed}")  # semilla con sal: evita coincidir con la semilla de un algoritmo
    orden = list(range(n))
    rng.shuffle(orden)
    aristas = {(min(orden[i], orden[(i + 1) % n]), max(orden[i], orden[(i + 1) % n])) for i in range(n)}
    while len(aristas) < n + extra:
        u, v = rng.sample(range(n), 2)
        aristas.add((min(u, v), max(u, v)))
    adj = [set() for _ in range(n)]
    for u, v in aristas:
        adj[u].add(v)
        adj[v].add(u)
    return Instance(f"plantada{n}", n, tuple(frozenset(a) for a in adj), len(aristas))


def ciclo_plantado(n, extra, seed=0):
    """El ciclo hamiltoniano plantado por instancia_plantada (misma semilla)."""
    rng = random.Random(f"plantada-{seed}")
    orden = list(range(n))
    rng.shuffle(orden)
    return orden
