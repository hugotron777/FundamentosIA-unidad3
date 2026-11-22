"""Línea base: búsqueda aleatoria. Sirve para probar el runner y como piso de comparación."""
import random
from src.core import Config, Result, Budget, fitness, random_permutation


def run(instance, config: Config, seed: int) -> Result:
    rng, budget = random.Random(seed), Budget(config)
    best, best_f, history = None, None, []
    while not budget.exhausted():
        ruta = random_permutation(instance.n, rng)
        f = fitness(instance, ruta)
        budget.tick()
        if best_f is None or f < best_f:
            best, best_f = ruta, f
            history.append((budget.iterations, f))
        if best_f == 0:
            break
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
