"""Corre una metaheurística sobre muchos grafos del FHCP (del más chico al más grande) en paralelo.

Uso:
  python -m experiments.masivo --algorithm aco_ls --time-limit 30 --workers 12
  python -m experiments.masivo --max-n 1000          # solo grafos de hasta 1000 vértices

Escribe una fila por grafo en results/masivo/resultados.csv (se puede interrumpir y reanudar:
los grafos que ya están en el CSV se saltan) y guarda cada ciclo válido en results/masivo/tours/.
"""
import argparse, csv, os, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from src.core import read_hcp, validate, write_tour, Config
from src.algorithms import REGISTRY

CAMPOS = ["archivo", "n", "m", "algoritmo", "semilla", "faltantes", "resuelto", "segundos", "evaluaciones"]


def _resolver(ruta, algoritmo, semilla, max_evals, limite, dir_tours):
    g = read_hcp(ruta)
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    t0 = time.perf_counter()
    r = REGISTRY[algoritmo](g, Config(max_evals, limite, {}), semilla)
    seg = time.perf_counter() - t0
    ok = validate(g, r.best_route)["es_hamiltoniano"]
    if ok:
        write_tour(os.path.join(dir_tours, f"{nombre}.tour"), r.best_route, name=f"{algoritmo} {nombre}")
    return {"archivo": os.path.basename(ruta), "n": g.n, "m": g.m, "algoritmo": algoritmo, "semilla": semilla,
            "faltantes": r.best_fitness, "resuelto": int(ok), "segundos": round(seg, 3),
            "evaluaciones": r.iterations}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogo", default="data/catalogo_fhcp.csv")
    ap.add_argument("--instancias", default="data/instances")
    ap.add_argument("--algorithm", default="aco_ls", choices=sorted(REGISTRY))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-evals", type=int, default=100_000)
    ap.add_argument("--time-limit", type=float, default=30.0, help="segundos por grafo")
    ap.add_argument("--max-n", type=int, default=None, help="ignorar grafos con más vértices")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--salida", default="results/masivo")
    a = ap.parse_args()

    dir_tours = os.path.join(a.salida, "tours")
    os.makedirs(dir_tours, exist_ok=True)
    csv_path = os.path.join(a.salida, "resultados.csv")
    hechos = set()
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            hechos = {r["archivo"] for r in csv.DictReader(f)}

    with open(a.catalogo, encoding="utf-8") as f:
        filas = sorted(csv.DictReader(f), key=lambda r: int(r["n"]))
    pendientes = [r["archivo"] for r in filas
                  if r["archivo"] not in hechos and (a.max_n is None or int(r["n"]) <= a.max_n)]
    print(f"{len(hechos)} grafos ya hechos, {len(pendientes)} pendientes", flush=True)

    nuevo = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f, \
            ProcessPoolExecutor(max_workers=a.workers) as ex:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        futuros = {ex.submit(_resolver, os.path.join(a.instancias, arch), a.algorithm, a.seed,
                             a.max_evals, a.time_limit, dir_tours): arch for arch in pendientes}
        resueltos = 0
        for i, fut in enumerate(as_completed(futuros), 1):
            try:
                fila = fut.result()
            except Exception as e:                       # un grafo que falle no detiene la corrida
                print(f"[{i}/{len(pendientes)}] {futuros[fut]}: ERROR {e}", flush=True)
                continue
            w.writerow(fila)
            f.flush()
            resueltos += fila["resuelto"]
            print(f"[{i}/{len(pendientes)}] {fila['archivo']} n={fila['n']} faltantes={fila['faltantes']} "
                  f"{'SÍ' if fila['resuelto'] else 'no'} {fila['segundos']} s | resueltos: {resueltos}",
                  flush=True)


if __name__ == "__main__":
    main()
