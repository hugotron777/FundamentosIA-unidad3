"""Benchmark: algoritmos x instancias x semillas con el MISMO presupuesto para todos.

Presupuesto por corrida: --max-evals evaluaciones de fitness O --time-limit segundos (lo primero que ocurra).
Escribe una fila por corrida (CSV) y el historial de mejoras (JSONL). Es reanudable: omite lo ya hecho.
--workers N reparte las corridas entre N procesos (usa N núcleos). Con N > 1 los tiempos medidos pueden
inflarse un poco por la competencia entre procesos: para las tablas de tiempo del informe usa --workers 1.

Uso:
  python -m experiments.benchmark --instances data/instances/graph24.hcp ... \
      --algorithms ga sa aco_ls --seeds 10 --max-evals 100000 --time-limit 15 --out results/bench
"""
import argparse, concurrent.futures as cf, csv, json, os, platform, sys, time
from functools import lru_cache
from pathlib import Path
from src.core import read_hcp, validate, Config, write_tour
from src.algorithms import REGISTRY, PRINCIPALES

CAMPOS = ["algoritmo", "instancia", "n", "m", "sha256", "semilla", "fitness", "exito",
          "valido_independiente", "legalidad", "tiempo_s", "evaluaciones",
          "max_evals", "time_limit"]


def instancias_del_lote(catalogo, carpeta, lote):
    """Distribuye el catálogo por tamaño en tres lotes disjuntos."""
    with open(catalogo, encoding="utf-8", newline="") as archivo:
        filas = sorted(csv.DictReader(archivo),
                       key=lambda fila: (int(fila["n"]), int(fila["m"]), fila["archivo"]))
    return [os.fspath(Path(carpeta) / fila["archivo"]) for fila in filas[lote - 1::3]]


def hechos(ruta):
    if not os.path.exists(ruta):
        return set()
    with open(ruta, encoding="utf-8") as f:
        return {(r["algoritmo"], r["instancia"], int(r["semilla"])) for r in csv.DictReader(f)}


@lru_cache(maxsize=4)
def _cargar(ruta):
    return read_hcp(ruta)


def _tarea(args):
    """Una corrida (se ejecuta en el proceso principal o en un worker)."""
    ruta, alg, s, max_evals, time_limit = args
    g = _cargar(ruta)
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    r = REGISTRY[alg](g, Config(max_evals, time_limit), s)
    v = validate(g, r.best_route)                         # validación independiente
    fila = {"algoritmo": alg, "instancia": nombre, "n": g.n, "m": g.m, "sha256": g.sha256[:12],
            "semilla": s, "fitness": r.best_fitness, "exito": int(r.best_fitness == 0),
            "valido_independiente": int(v["es_hamiltoniano"]),
            "legalidad": round(1 - r.best_fitness / g.n, 6), "tiempo_s": round(r.time, 4),
            "evaluaciones": r.iterations, "max_evals": max_evals, "time_limit": time_limit}
    hist = {"algoritmo": alg, "instancia": nombre, "semilla": s, "hist": r.history}
    return fila, hist, (r.best_route if v["es_hamiltoniano"] else None)


def main():
    ap = argparse.ArgumentParser()
    origen = ap.add_mutually_exclusive_group(required=True)
    origen.add_argument("--instances", nargs="+")
    origen.add_argument("--lote", type=int, choices=(1, 2, 3), help="tercio del catálogo FHCP ordenado por tamaño")
    ap.add_argument("--catalogo", default="data/catalogo_fhcp.csv")
    ap.add_argument("--instancias-dir", default="data/instances")
    ap.add_argument("--algorithms", nargs="+", choices=sorted(REGISTRY), default=PRINCIPALES)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--max-evals", type=int, default=100_000)
    ap.add_argument("--time-limit", type=float, default=15.0)
    ap.add_argument("--workers", type=int, default=1, help="procesos en paralelo (1 = secuencial)")
    ap.add_argument("--out", required=True, help="prefijo de salida, p. ej. results/bench")
    ap.add_argument("--tours", default=None, help="carpeta donde guardar los tours válidos encontrados")
    a = ap.parse_args()

    instancias = a.instances if a.lote is None else instancias_del_lote(a.catalogo, a.instancias_dir, a.lote)
    faltantes = [ruta for ruta in instancias if not os.path.isfile(ruta)]
    if faltantes:
        ap.error(f"Faltan {len(faltantes)} instancias (primera: {faltantes[0]}). Extrae data/FHCPCS.7z.")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    if a.tours:
        os.makedirs(a.tours, exist_ok=True)
    csv_path, hist_path = a.out + "_runs.csv", a.out + "_hist.jsonl"
    ya = hechos(csv_path)
    nuevo = not os.path.exists(csv_path)
    with open(a.out + "_entorno.txt", "w", encoding="utf-8") as f:
        f.write(f"python {sys.version.split()[0]} | {platform.platform()} | {platform.processor() or platform.machine()} | "
                f"núcleos {os.cpu_count()} | workers {a.workers}\n"
                f"fecha {time.strftime('%Y-%m-%d %H:%M:%S')} | max_evals {a.max_evals} | time_limit {a.time_limit}s | seeds 0..{a.seeds - 1}\n")

    tareas = []
    for ruta in instancias:
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        for alg in a.algorithms:
            for s in range(a.seeds):
                if (alg, nombre, s) not in ya:
                    tareas.append((ruta, alg, s, a.max_evals, a.time_limit))
    total = len(tareas)
    cota = total * a.time_limit / max(1, a.workers)
    print(f"{total} corridas pendientes (ya hechas: {len(ya)}). Presupuesto aproximado: {cota / 60:.0f} min "
          f"con {a.workers} proceso(s), más sobrecarga.", flush=True)

    with open(csv_path, "a", newline="", encoding="utf-8") as fc, open(hist_path, "a", encoding="utf-8") as fh:
        w = csv.DictWriter(fc, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        hechas, t0 = 0, time.time()

        def guardar(res):
            nonlocal hechas
            fila, hist, ruta_ok = res
            if a.tours and ruta_ok is not None:
                write_tour(os.path.join(a.tours, f"{fila['algoritmo']}_{fila['instancia']}_s{fila['semilla']}.tour"),
                           ruta_ok, name=f"{fila['algoritmo']} {fila['instancia']}")
            fh.write(json.dumps(hist) + "\n")
            fh.flush()
            w.writerow(fila)
            fc.flush()
            hechas += 1
            print(f"[{hechas}/{total}] {fila['algoritmo']} {fila['instancia']} semilla {fila['semilla']}: "
                  f"fitness {fila['fitness']} ({fila['tiempo_s']} s) | {(time.time() - t0) / 60:.1f} min", flush=True)

        if a.workers <= 1:
            for t in tareas:
                guardar(_tarea(t))
        else:
            with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
                futuros = [ex.submit(_tarea, t) for t in tareas]
                try:
                    for fu in cf.as_completed(futuros):
                        guardar(fu.result())
                except KeyboardInterrupt:
                    for fu in futuros:
                        fu.cancel()
                    print("Interrumpido: lo ya guardado se conserva; vuelve a lanzar el comando para continuar.")


if __name__ == "__main__":
    main()
