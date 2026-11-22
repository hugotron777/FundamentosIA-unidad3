"""Recocido Simulado (SA) sobre permutaciones.

- Vecino (param `move`): "swap" (por defecto; intercambio aleatorio de dos posiciones, como pide la práctica)
  o "2opt" (inversión de un tramo). route[0] queda fijo. El cambio de fitness se calcula en O(1).
- Aceptación: Metropolis, P = exp(-delta / T) si delta > 0.
- Enfriamiento geométrico de t0 a t_end según el progreso del presupuesto (evaluaciones o tiempo).
- 1 iteración = 1 movimiento evaluado (1 evaluación de fitness, aunque por delta).

params: move ("swap"), t0 y t_end (swap: 2.0 y 0.01; 2opt: 0.3 y 0.02, ajustados)
"""
import math
import random
from src.core import Config, Result, Budget, fitness, random_permutation
from src.core.operators import two_opt_delta, swap_delta, reverse_segment

CADA = 64   # cada cuántos movimientos se recalcula la temperatura (evita llamar al reloj siempre)


def run(instance, config: Config, seed: int) -> Result:
    n, adj = instance.n, instance.adj
    if n < 4:
        raise ValueError("SA requiere n >= 4")
    p = config.params
    move = p.get("move", "swap")
    if move not in ("swap", "2opt"):
        raise ValueError("move debe ser 'swap' o '2opt'")
    d0, d1 = (2.0, 0.01) if move == "swap" else (0.3, 0.02)      # ajustados (tuning.py; swap: results/tuning_sa.csv)
    t0, t_end = p.get("t0", d0), p.get("t_end", d1)

    rng, budget = random.Random(seed), Budget(config)
    ruta = random_permutation(n, rng)
    f = fitness(instance, ruta)
    best, best_f, history = ruta[:], f, [(0, f)]
    T, k = t0, 0

    while best_f > 0 and not budget.exhausted():
        i, j = rng.randint(1, n - 1), rng.randint(1, n - 1)
        if i == j:
            continue
        if i > j:
            i, j = j, i
        if move == "swap":
            delta = swap_delta(adj, ruta, i, j)
        else:
            delta = two_opt_delta(adj, ruta, i, j)
        budget.tick()
        if delta <= 0 or rng.random() < math.exp(-delta / T):
            if move == "swap":
                ruta[i], ruta[j] = ruta[j], ruta[i]
            else:
                reverse_segment(ruta, i, j)
            f += delta
            if f < best_f:
                best, best_f = ruta[:], f
                history.append((budget.iterations, f))
        k += 1
        if k % CADA == 0:
            T = t0 * (t_end / t0) ** budget.progress()
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
