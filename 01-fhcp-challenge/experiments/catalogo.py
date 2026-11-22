"""Genera el catálogo de instancias (T2.1): nombre, n, m, grados y hash SHA-256.

Uso:  python -m experiments.catalogo CARPETA_CON_HCP salida.csv
"""
import csv, glob, os, re, sys
from src.core import read_hcp


def clave(p):
    m = re.findall(r"(\d+)", os.path.basename(p))
    return int(m[0]) if m else 0


def main(carpeta, salida):
    filas = []
    for p in sorted(glob.glob(os.path.join(carpeta, "*.hcp")), key=clave):
        g = read_hcp(p)
        grados = [len(a) for a in g.adj]
        filas.append({"archivo": os.path.basename(p), "n": g.n, "m": g.m,
                      "grado_min": min(grados), "grado_max": max(grados),
                      "sha256": g.sha256})
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} instancias -> {salida}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
