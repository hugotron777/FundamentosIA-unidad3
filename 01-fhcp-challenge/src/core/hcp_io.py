"""Lectura de instancias HCP y lectura/escritura de tours (formato TSPLIB)."""
import hashlib
from .graph import Instance


def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def read_hcp(path: str) -> Instance:
    """Lee un archivo .hcp (EDGE_LIST). Etiquetas 1..n -> índices 0..n-1."""
    name, n, edges, in_edges = path, None, set(), False
    with open(path, encoding="utf-8") as f:
        for linea in f:
            t = linea.strip()
            if not t:
                continue
            if in_edges:
                if t in ("-1", "EOF"):
                    break
                u, v = (int(x) for x in t.split()[:2])
                if not (1 <= u <= n and 1 <= v <= n):
                    raise ValueError(f"Arista fuera de rango: {u} {v} (n={n})")
                if u != v:
                    edges.add((min(u, v) - 1, max(u, v) - 1))
                continue
            clave = t.split(":")[0].strip().upper()
            valor = t.split(":", 1)[1].strip() if ":" in t else ""
            if clave == "NAME":
                name = valor
            elif clave == "DIMENSION":
                n = int(valor)
            elif clave == "EDGE_DATA_SECTION":
                if n is None:
                    raise ValueError("DIMENSION debe aparecer antes de las aristas")
                in_edges = True
    if n is None or not in_edges:
        raise ValueError("Archivo HCP inválido: falta DIMENSION o EDGE_DATA_SECTION")
    adj = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    return Instance(name=name, n=n, adj=tuple(frozenset(a) for a in adj),
                    m=len(edges), sha256=file_hash(path))


def write_tour(path: str, route, name="Solucion propuesta", comment="Tour encontrado"):
    """Escribe un TOUR (índices 0..n-1 -> etiquetas 1..n, sin repetir el inicio)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"NAME : {name}\nCOMMENT : {comment}\nTYPE : TOUR\n")
        f.write(f"DIMENSION : {len(route)}\nTOUR_SECTION\n")
        for v in route:
            f.write(f"{v + 1}\n")
        f.write("-1\nEOF\n")


def read_tour(path: str):
    """Lee un TOUR y devuelve la ruta con índices 0..n-1."""
    ruta, en_tour = [], False
    with open(path, encoding="utf-8") as f:
        for linea in f:
            t = linea.strip()
            if not t:
                continue
            if en_tour:
                if t in ("-1", "EOF"):
                    break
                ruta.append(int(t) - 1)
            elif t.upper().startswith("TOUR_SECTION"):
                en_tour = True
    return ruta
