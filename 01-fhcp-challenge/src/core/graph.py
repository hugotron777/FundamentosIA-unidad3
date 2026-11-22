"""Representación del grafo de una instancia HCP.

Convención: internamente los vértices van de 0 a n-1; las etiquetas 1..n del
archivo HCP/TOUR se convierten solo al leer y al escribir (hcp_io.py).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Instance:
    name: str
    n: int
    adj: tuple          # adj[v] = frozenset de vecinos (grafo no dirigido)
    m: int              # número de aristas distintas
    sha256: str = ""    # hash del archivo (catálogo, T2.1)

    def has_edge(self, u: int, v: int) -> bool:
        return v in self.adj[u]

    def degree(self, v: int) -> int:
        return len(self.adj[v])
