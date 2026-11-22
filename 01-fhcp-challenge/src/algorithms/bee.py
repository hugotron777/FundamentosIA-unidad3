"""Colonia de Abejas (ABC discreta) sobre permutaciones.

- Fuentes de alimento = permutaciones (vértice 0 fijo). Vecindad: intercambio o inversión de tramo.
- Abejas empleadas: una variación por fuente; selección voraz (acepta si no empeora).
- Abejas observadoras: eligen fuente con probabilidad ∝ 1/(1+fitness) y la varían.
- Exploradoras: una fuente sin mejora estricta en `limit` intentos se reemplaza por una permutación aleatoria.
- 1 iteración = 1 variación evaluada (delta O(1)), igual que SA.

params: sources (5), limit (2000)  [ajustados]
"""
import random
from src.core import Config, Result, Budget, fitness, random_permutation
from src.core.operators import two_opt_delta, swap_delta, reverse_segment


def run(instance, config: Config, seed: int) -> Result:
    n, adj = instance.n, instance.adj
    if n < 4:
        raise ValueError("Bee Colony requiere n >= 4")
    p = config.params
    S, limit = p.get("sources", 5), p.get("limit", 2000)

    rng, budget = random.Random(seed), Budget(config)
    fuentes = [random_permutation(n, rng) for _ in range(S)]
    fits = [fitness(instance, r) for r in fuentes]
    intentos = [0] * S
    budget.tick(S)
    k = min(range(S), key=lambda s: fits[s])
    best, best_f, history = fuentes[k][:], fits[k], [(budget.iterations, fits[k])]

    def variar(s):
        nonlocal best, best_f
        ruta = fuentes[s]
        i, j = rng.randint(1, n - 1), rng.randint(1, n - 1)
        if i == j:
            return
        if i > j:
            i, j = j, i
        usar_swap = rng.random() < 0.5
        d = swap_delta(adj, ruta, i, j) if usar_swap else two_opt_delta(adj, ruta, i, j)
        budget.tick()
        if d <= 0:
            if usar_swap:
                ruta[i], ruta[j] = ruta[j], ruta[i]
            else:
                reverse_segment(ruta, i, j)
            if d < 0:
                intentos[s] = 0
            else:
                intentos[s] += 1
            fits[s] += d
            if fits[s] < best_f:
                best, best_f = ruta[:], fits[s]
                history.append((budget.iterations, best_f))
        else:
            intentos[s] += 1

    while best_f > 0 and not budget.exhausted():
        for s in range(S):                                   # fase de empleadas
            if budget.exhausted() or best_f == 0:
                break
            variar(s)
        pesos = [1.0 / (1 + f) for f in fits]
        for s in rng.choices(range(S), weights=pesos, k=S):   # fase de observadoras
            if budget.exhausted() or best_f == 0:
                break
            variar(s)
        for s in range(S):                                   # fase de exploradoras
            if intentos[s] > limit and fits[s] > 0:
                fuentes[s] = random_permutation(n, rng)
                fits[s] = fitness(instance, fuentes[s])
                intentos[s] = 0
                budget.tick()
                if fits[s] < best_f:
                    best, best_f = fuentes[s][:], fits[s]
                    history.append((budget.iterations, best_f))
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
