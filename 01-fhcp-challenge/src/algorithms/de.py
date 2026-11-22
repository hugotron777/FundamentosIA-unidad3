"""Evolución Diferencial (DE/rand/1/bin) con claves aleatorias.

Adaptación a permutaciones: cada individuo es un vector real de n claves; se decodifica ordenando los
vértices por su clave (SPV, ver representation.decode_spv). La mutación y la cruza operan en el espacio
continuo; la selección es voraz (acepta si el hijo no es peor).
1 iteración = 1 hijo decodificado y evaluado (1 evaluación de fitness).

params: pop_size (10), F (0.7), CR (0.9)  [pop_size y F ajustados]
"""
import random
import numpy as np
from src.core import Config, Result, Budget, fitness


def _decodificar(claves):
    return np.argsort(claves, kind="stable").tolist()


def run(instance, config: Config, seed: int) -> Result:
    n = instance.n
    p = config.params
    NP, F, CR = p.get("pop_size", 10), p.get("F", 0.7), p.get("CR", 0.9)
    rng, budget = np.random.default_rng(seed), Budget(config)
    py = random.Random(seed)
    best, best_f, history = None, None, []

    def evaluar(claves):
        nonlocal best, best_f
        ruta = _decodificar(claves)
        f = fitness(instance, ruta)
        budget.tick()
        if best_f is None or f < best_f:
            best, best_f = ruta, f
            history.append((budget.iterations, f))
        return f

    pop, fits = [], []
    while len(pop) < NP and not budget.exhausted():
        x = rng.random(n)
        pop.append(x)
        fits.append(evaluar(x))

    while best_f != 0 and not budget.exhausted() and len(pop) == NP:
        for i in range(NP):
            if budget.exhausted() or best_f == 0:
                break
            r1, r2, r3 = py.sample([k for k in range(NP) if k != i], 3)
            mutante = pop[r1] + F * (pop[r2] - pop[r3])
            cruza = rng.random(n) < CR
            cruza[py.randrange(n)] = True
            hijo = np.where(cruza, mutante, pop[i])
            fh = evaluar(hijo)
            if fh <= fits[i]:
                pop[i], fits[i] = hijo, fh
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
