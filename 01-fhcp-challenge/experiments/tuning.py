"""Ajuste de parámetros (barrido pequeño) con semillas DISTINTAS a las del benchmark final.

Uso: python -m experiments.tuning --out results/tuning.csv
     python -m experiments.tuning --out results/tuning_sa.csv --algs sa --evals 100000 \
         --grid '{"t0": [0.1, 0.5, 1.0, 2.0, 3.0], "t_end": [0.01, 0.02, 0.05, 0.1]}'
Métrica: fitness final medio normalizado por n (menor es mejor), promedio sobre instancias y semillas.
"""
import argparse, csv, json, itertools, os, time
from src.core import read_hcp, Config
from src.algorithms import REGISTRY

INSTANCIAS = ["data/instances/graph1.hcp", "data/instances/graph24.hcp"]
SEMILLAS = [100, 101, 102]          # el benchmark final usa 0..9
EVALS, TOPE = 30_000, 8.0

GRIDS = {
    "sa": {"t0": [0.3, 0.6, 1.0, 2.0], "t_end": [0.02, 0.05, 0.15]},
    "sa_2opt": {"t0": [0.3, 0.6, 1.0, 2.0], "t_end": [0.02, 0.05, 0.15]},
    "ga": {"pop_size": [50, 100, 200], "pm": [0.1, 0.3, 0.6]},
    "aco": {"ants": [5, 10, 20], "beta": [2.0, 3.0, 5.0]},
    "bee": {"sources": [10, 20, 50], "limit": [100, 500, 2000]},
    "de": {"pop_size": [20, 50, 100], "F": [0.3, 0.5, 0.8], "CR": [0.1, 0.9]},
    "pso": {"swarm": [20, 50], "w": [0.4, 0.7, 0.9], "vmax": [0.2, 0.5, 1.0]},
}


def evaluar(alg, params, grafos, evals=EVALS):
    tot, k = 0.0, 0
    for g in grafos:
        for s in SEMILLAS:
            r = REGISTRY[alg](g, Config(evals, TOPE, dict(params)), s)
            tot += r.best_fitness / g.n
            k += 1
    return tot / k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--algs", nargs="*", default=list(GRIDS))
    ap.add_argument("--instances", nargs="*", default=INSTANCIAS)
    ap.add_argument("--evals", type=int, default=EVALS, help="presupuesto de evaluaciones por corrida")
    ap.add_argument("--grid", default=None, help="rejilla en JSON que reemplaza a la de GRIDS (un solo algoritmo)")
    a = ap.parse_args()
    if a.grid:
        GRIDS[a.algs[0]] = json.loads(a.grid)
    grafos = [read_hcp(p) for p in a.instances]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algoritmo", "parametros", "fitness_norm_medio"])
        for alg in a.algs:
            claves = list(GRIDS[alg])
            for vals in itertools.product(*GRIDS[alg].values()):
                params = dict(zip(claves, vals))
                t = time.time()
                m = evaluar(alg, params, grafos, a.evals)
                w.writerow([alg, str(params), f"{m:.5f}"])
                f.flush()
                print(f"{alg} {params} -> {m:.4f} ({time.time()-t:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
