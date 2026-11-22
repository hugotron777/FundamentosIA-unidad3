"""Punto de entrada simple: carga UN grafo del FHCP, ejecuta UNA metaheurística y devuelve el arreglo de vértices.

Uso:
  python -m experiments.resolver --instance data/instances/graph1.hcp --algorithm aco_ls --time-limit 30
  python -m experiments.resolver --instance data/instances/graph24.hcp --algorithm sa --seed 3 --param t0=0.2

El arreglo se imprime con las etiquetas del archivo (1..n) y, si es un ciclo hamiltoniano válido, se guarda
como TOUR (formato oficial del FHCP). Código de salida: 0 si encontró un ciclo válido, 1 si no.
"""
import argparse, os, sys
from src.core import read_hcp, validate, write_tour, Config
from src.algorithms import REGISTRY


def _valor(texto):
    if texto.lower() in ("true", "false"):
        return texto.lower() == "true"
    for tipo in (int, float):
        try:
            return tipo(texto)
        except ValueError:
            pass
    return texto


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True, help="archivo .hcp")
    ap.add_argument("--algorithm", required=True, choices=sorted(REGISTRY))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-evals", type=int, default=100_000)
    ap.add_argument("--time-limit", type=float, default=30.0, help="segundos")
    ap.add_argument("--param", action="append", default=[], metavar="clave=valor",
                    help="parámetro del algoritmo (repetible), p. ej. --param plateau=200")
    ap.add_argument("--tour", default=None, help="ruta del archivo TOUR (por defecto results/tours/...)")
    ap.add_argument("--completo", action="store_true", help="imprimir el arreglo completo aunque sea largo")
    a = ap.parse_args()

    params = dict(p.split("=", 1) for p in a.param)
    params = {k: _valor(v) for k, v in params.items()}
    g = read_hcp(a.instance)
    nombre = os.path.splitext(os.path.basename(a.instance))[0]
    r = REGISTRY[a.algorithm](g, Config(a.max_evals, a.time_limit, params), a.seed)
    v = validate(g, r.best_route)
    ruta = [x + 1 for x in r.best_route]                      # etiquetas 1..n como en el archivo

    print(f"Instancia {nombre}: n={g.n}, m={g.m} | algoritmo {a.algorithm} | semilla {a.seed}")
    print(f"Aristas faltantes: {r.best_fitness} | ciclo hamiltoniano válido: {'SÍ' if v['es_hamiltoniano'] else 'NO'} "
          f"| {r.time:.2f} s | {r.iterations} evaluaciones")
    mostrar = ruta if (a.completo or len(ruta) <= 60) else ruta[:30] + ["..."] + ruta[-10:]
    print("Arreglo de vértices propuesto (regresa al primero):", mostrar)
    if v["es_hamiltoniano"]:
        destino = a.tour or os.path.join("results", "tours", f"{a.algorithm}_{nombre}_s{a.seed}.tour")
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        write_tour(destino, r.best_route, name=f"{a.algorithm} {nombre}")
        print("Tour guardado en", destino)
    sys.exit(0 if v["es_hamiltoniano"] else 1)


if __name__ == "__main__":
    main()
