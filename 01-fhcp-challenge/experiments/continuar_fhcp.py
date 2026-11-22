"""Ejecuta una pasada FHCP reanudable y registra los ciclos verificados.

El registro inicial importa las corridas masivas y el lote de 40 grafos.
Para los métodos en C++, compilar el archivo correspondiente de fhcp_native
con g++ -std=c++17 -O3 y pasar el ejecutable mediante --ejecutable.
"""
import argparse
import csv
import fcntl
import hashlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import subprocess
import time

from src.algorithms import REGISTRY
from src.core import Config, read_hcp, read_tour, validate, write_tour
from src.core.preprocess import reducir


CAMPOS = [
    "corrida", "archivo", "metodo", "semilla", "limite_s", "segundos",
    "faltantes", "resuelto", "estado", "ciclo",
]
METODOS_NATIVOS = (
    "ramificacion", "frontera", "frontera_dominantes",
    "descomposicion", "descomposicion_amplia", "cortes",
)


def leer_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def escribir_csv(path, fields, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def importar():
    mass = Path("results/masivo")
    lot = Path("results/lote_40")
    best = {r["archivo"]: r for r in leer_csv(mass / "resumen_por_grafo.csv")}
    history = []
    for path in sorted(mass.glob("*/resultados.csv")):
        stage = path.parent.name
        for row in leer_csv(path):
            name = row["archivo"]
            success = row["resuelto"] == "1"
            tour = mass / "tours_resueltos" / Path(name).with_suffix(".tour")
            has_tour = success and tour.is_file()
            history.append(dict(corrida=f"masivo/{stage}", archivo=name, metodo=row["algoritmo"],
                                semilla=row["semilla"], limite_s=30 if stage == "30s" else (4 if stage == "s0" else 6),
                                segundos=row["segundos"], faltantes=row["faltantes"], resuelto=int(has_tour),
                                estado="resuelto" if has_tour else "sin ciclo encontrado",
                                ciclo=str(tour) if has_tour else ""))
    for row in leer_csv(lot / "intentos.csv"):
        tour = lot / "tours" / Path(row["archivo"]).with_suffix(".tour")
        if row["resuelto"] == "1":
            assert tour.is_file(), tour
            row["ciclo"] = str(tour)
        history.append(dict(corrida="lote_40", **row))
    assert all(any(row["archivo"] == name and row["resuelto"] in (1, "1") for row in history)
               for name, data in best.items() if data["resuelto"] == "1")
    return history


def resumen(catalog, history):
    attempts = defaultdict(list)
    for row in history:
        attempts[row["archivo"]].append(row)
    records = []
    for graph in catalog:
        rows = attempts[graph["archivo"]]
        success = next((row for row in rows if int(row["resuelto"]) == 1), None)
        missing = [int(row["faltantes"]) for row in rows if row["faltantes"] != ""]
        records.append(dict(archivo=graph["archivo"], n=graph["n"], m=graph["m"], intentos=len(rows),
                            mejor_faltantes=0 if success else min(missing, default=""),
                            resuelto=int(success is not None), metodo_solucion=success["metodo"] if success else "",
                            ciclo=success["ciclo"] if success else ""))
    return records


def intentar(path, method, executable, limit, seed):
    start = time.monotonic()
    inst = read_hcp(path)
    route = None
    missing = ""
    if method == "cortes":
        from experiments.fhcp_cortes import buscar
        route, status = buscar(inst, executable, limit, seed)
    elif method == "milp":
        from experiments.fhcp_milp import buscar
        reduced, _, _ = reducir(inst)
        route, status = buscar(reduced, limit, seed)
    elif method in REGISTRY:
        result = REGISTRY[method](inst, Config(100_000, limit, {}), seed)
        route, missing = result.best_route, result.best_fitness
        status = "sin ciclo encontrado"
    else:
        search_graph = reducir(inst)[0] if method != "ramificacion" else inst
        edges = [f"{u} {v}" for u in range(search_graph.n) for v in sorted(search_graph.adj[u]) if u < v]
        data = f"{search_graph.n} {search_graph.m}\n" + "\n".join(edges)
        try:
            proc = subprocess.run([executable, str(round(limit * 1000)), str(seed)],
                                  input=data, text=True, capture_output=True, check=True, timeout=limit + 4)
            output = proc.stdout.splitlines()
            status = output[0].split()[0]
            if status == "resuelto":
                route = list(map(int, output[1].split()))
        except subprocess.TimeoutExpired:
            status = "tiempo agotado"
    if route is not None and validate(inst, route)["es_hamiltoniano"]:
        return route, 0, "resuelto", round(time.monotonic() - start, 3)
    if status == "resuelto":
        raise ValueError(f"El ciclo de {path.name} no pasó la validación")
    return None, missing, status, round(time.monotonic() - start, 3)


def registrar(args):
    output = args.salida
    log = output / "intentos.csv"
    state = output / "estado.csv"
    catalog = leer_csv(args.catalogo)
    if not log.exists():
        escribir_csv(log, CAMPOS, importar())
    history = leer_csv(log)
    records = resumen(catalog, history)
    escribir_csv(state, list(records[0]), records)
    if args.auditar:
        audited = 0
        for record, original in zip(records, catalog):
            if not record["resuelto"]:
                continue
            path = args.instancias / record["archivo"]
            instance = read_hcp(path)
            if instance.sha256 != original["sha256"]:
                normalized = path.read_bytes().replace(b"\r\n", b"\n")
                if hashlib.sha256(normalized).hexdigest() != original["sha256"]:
                    raise ValueError(f'La instancia {record["archivo"]} difiere del catálogo')
            if not validate(instance, read_tour(record["ciclo"]))["es_hamiltoniano"]:
                raise ValueError(f'Ciclo inválido para {record["archivo"]}')
            audited += 1
        print(f"Verificados {audited}/{len(records)} ciclos contra el catálogo.", flush=True)
        return
    if args.solo_registro:
        print(f"Resueltos: {sum(row['resuelto'] for row in records)}/{len(records)}", flush=True)
        return
    previous = [row for row in history if row["corrida"] == args.corrida]
    expected = (args.metodo, args.semilla, args.limite)
    if any((row["metodo"], int(row["semilla"]), float(row["limite_s"])) != expected for row in previous):
        raise ValueError("Para cambiar el método, la semilla o el límite, usa otro nombre de corrida.")
    done = {row["archivo"] for row in previous if not row["estado"].startswith("error")}
    pending = sorted((row for row in records if row["resuelto"] == 0
                      and args.min_n <= int(row["n"]) <= args.max_n
                      and int(row["m"]) <= args.max_m and row["archivo"] not in done),
                     key=lambda row: int(row["n"]))
    tours = output / "tours"
    tours.mkdir(exist_ok=True)
    found = 0
    total = sum(row["resuelto"] for row in records)
    print(f"{args.corrida}: {len(pending)} por probar, {total} resueltos previos", flush=True)
    try:
        with log.open("a", encoding="utf-8", newline="") as file, ProcessPoolExecutor(args.workers) as pool:
            writer = csv.DictWriter(file, fieldnames=CAMPOS)
            futures = {pool.submit(intentar, args.instancias / row["archivo"], args.metodo,
                                   args.ejecutable, args.limite, args.semilla): row["archivo"] for row in pending}
            for index, future in enumerate(as_completed(futures), 1):
                name = futures[future]
                cycle = ""
                try:
                    route, missing, status, seconds = future.result()
                    if route:
                        path = tours / Path(name).with_suffix(".tour")
                        tmp = path.with_suffix(".tmp")
                        write_tour(tmp, route, name=f"{args.metodo} {Path(name).stem}",
                                   comment=f"Corrida {args.corrida}, semilla {args.semilla}")
                        inst = read_hcp(args.instancias / name)
                        if not validate(inst, read_tour(tmp))["es_hamiltoniano"]:
                            tmp.unlink()
                            raise ValueError("El TOUR guardado no pasó la validación")
                        tmp.replace(path)
                        cycle = str(path)
                        found += 1
                except Exception as exc:
                    status, missing, seconds = f"error: {exc}", "", ""
                row = dict(corrida=args.corrida, archivo=name, metodo=args.metodo, semilla=args.semilla,
                           limite_s=args.limite, segundos=seconds, faltantes=missing, resuelto=int(bool(cycle)),
                           estado=status, ciclo=cycle)
                writer.writerow(row)
                file.flush()
                history.append(row)
                if cycle or index % 50 == 0 or status.startswith("error"):
                    print(f"{index}/{len(pending)} | {name} | {status} | {total+found} resueltos", flush=True)
                if cycle or index % 25 == 0:
                    escribir_csv(state, list(records[0]), resumen(catalog, history))
    finally:
        escribir_csv(state, list(records[0]), resumen(catalog, history))
    print(f"{args.corrida}: {found} nuevos, {total+found}/{len(records)} acumulados", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogo", type=Path, default=Path("data/catalogo_fhcp.csv"))
    parser.add_argument("--instancias", type=Path, default=Path("data/instances"))
    parser.add_argument("--salida", type=Path, default=Path("results/seguimiento_fhcp"))
    parser.add_argument("--corrida")
    parser.add_argument("--metodo", choices=[*REGISTRY, *METODOS_NATIVOS, "milp"])
    parser.add_argument("--ejecutable", type=Path)
    parser.add_argument("--limite", type=float, default=1.0)
    parser.add_argument("--semilla", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--min-n", type=int, default=0)
    parser.add_argument("--max-n", type=int, default=10_000)
    parser.add_argument("--max-m", type=int, default=10**7)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--solo-registro", action="store_true")
    mode.add_argument("--auditar", action="store_true")
    args = parser.parse_args()
    if not (args.solo_registro or args.auditar) and (not args.corrida or not args.metodo):
        parser.error("Indica --corrida y --metodo para ejecutar una pasada.")
    if args.metodo in METODOS_NATIVOS:
        if args.ejecutable is None or not args.ejecutable.is_file():
            parser.error("Indica el ejecutable compilado mediante --ejecutable.")
        args.ejecutable = args.ejecutable.resolve()
    if args.metodo == "cortes":
        for solver in ("frontera", "descomposicion", "ramificacion"):
            if not args.ejecutable.with_name(solver).is_file():
                parser.error(f"Compila {solver} junto al detector de separadores.")
    if args.limite <= 0 or args.workers <= 0:
        parser.error("El límite y la cantidad de procesos deben ser positivos.")
    if not args.solo_registro and not args.instancias.is_dir():
        parser.error("La carpeta de instancias indicada no existe.")
    args.salida.mkdir(parents=True, exist_ok=True)
    with (args.salida / ".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Ya hay una corrida escribiendo en este registro.")
        registrar(args)


if __name__ == "__main__":
    main()
