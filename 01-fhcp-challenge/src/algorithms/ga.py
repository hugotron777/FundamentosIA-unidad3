"""Algoritmo Genético (GA) sobre permutaciones.

- Selección por torneo, cruza OX, mutación por inversión, elitismo.
- 1 iteración = 1 evaluación de fitness (hijo evaluado), para comparar con SA y búsqueda aleatoria.

params: pop_size (50), pc (0.9), pm (0.3), elite (2), tournament (3)  [pop_size y pm ajustados],
cross ("ox" por defecto, o "er" = recombinación de aristas)
"""
import random
from src.core import Config, Result, Budget, fitness, random_permutation
from src.core.operators import order_crossover, edge_recombination, inversion_mutation


def run(instance, config: Config, seed: int) -> Result:
    n = instance.n
    if n < 3:
        raise ValueError("GA requiere n >= 3")
    p = config.params
    pop_size, pc, pm = p.get("pop_size", 50), p.get("pc", 0.9), p.get("pm", 0.3)
    elite, k = min(p.get("elite", 2), pop_size), p.get("tournament", 3)
    cruza = edge_recombination if p.get("cross", "ox") == "er" else order_crossover

    rng, budget = random.Random(seed), Budget(config)
    best, best_f, history = None, None, []

    def evaluar(ruta):
        nonlocal best, best_f
        f = fitness(instance, ruta)
        budget.tick()
        if best_f is None or f < best_f:
            best, best_f = ruta[:], f
            history.append((budget.iterations, f))
        return f

    def torneo(fits):
        return min(rng.sample(range(len(fits)), min(k, len(fits))), key=lambda i: fits[i])

    pop, fits = [], []
    while len(pop) < pop_size and not budget.exhausted():
        r = random_permutation(n, rng, fix_start=False)
        pop.append(r)
        fits.append(evaluar(r))

    while best_f != 0 and not budget.exhausted() and len(pop) == pop_size:
        orden = sorted(range(pop_size), key=lambda i: fits[i])
        nueva = [pop[i][:] for i in orden[:elite]]
        nfits = [fits[i] for i in orden[:elite]]
        while len(nueva) < pop_size and not budget.exhausted() and best_f != 0:
            a, b = torneo(fits), torneo(fits)
            hijo = cruza(pop[a], pop[b], rng) if rng.random() < pc else pop[a][:]
            if rng.random() < pm:
                inversion_mutation(hijo, rng)
            nueva.append(hijo)
            nfits.append(evaluar(hijo))
        if len(nueva) < pop_size:
            break
        pop, fits = nueva, nfits
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
