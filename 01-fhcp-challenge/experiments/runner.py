"""Corre un algoritmo sobre una instancia con N semillas y guarda un CSV.

Uso:
  python -m experiments.runner --instance data/instances/ejemplo6.hcp \
      --algorithm random_search --seeds 10 --max-iter 5000 --out results/rs_ejemplo6.csv
"""
import argparse, csv, os
from src.core import read_hcp, validate, Config, write_tour
from src.algorithms import REGISTRY

CAMPOS = ["algoritmo", "instancia", "n", "m", "sha256", "semilla", "fitness",
          "exito", "valido_independiente", "tiempo_s", "iteraciones"]


def correr(instancia, algoritmo, semillas, cfg, guardar_tours=None):
    inst, run = read_hcp(instancia), REGISTRY[algoritmo]
    filas = []
    for s in range(semillas):
        r = run(inst, cfg, s)
        v = validate(inst, r.best_route)          # validación independiente del algoritmo
        filas.append({"algoritmo": algoritmo, "instancia": inst.name, "n": inst.n,
                      "m": inst.m, "sha256": inst.sha256[:12], "semilla": s,
                      "fitness": r.best_fitness, "exito": int(r.best_fitness == 0),
                      "valido_independiente": int(v["es_hamiltoniano"]),
                      "tiempo_s": round(r.time, 4), "iteraciones": r.iterations})
        if guardar_tours and r.best_fitness == 0:
            write_tour(os.path.join(guardar_tours, f"{algoritmo}_{inst.name}_s{s}.tour"), r.best_route)
    return filas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instance", required=True)
    p.add_argument("--algorithm", required=True, choices=sorted(REGISTRY))
    p.add_argument("--seeds", type=int, default=10)
    p.add_argument("--max-iter", type=int, default=10_000)
    p.add_argument("--time-limit", type=float, default=None)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    cfg = Config(max_iterations=a.max_iter, time_limit=a.time_limit)
    filas = correr(a.instance, a.algorithm, a.seeds, cfg)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    ok = sum(r["exito"] for r in filas)
    print(f"{a.algorithm} en {filas[0]['instancia']}: {ok}/{len(filas)} éxitos -> {a.out}")


if __name__ == "__main__":
    main()
