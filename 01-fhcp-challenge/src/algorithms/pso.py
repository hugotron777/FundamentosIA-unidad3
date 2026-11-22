"""Optimización por Enjambre de Partículas (PSO) con claves aleatorias.

Cada partícula es un vector real de n claves (posición) con su velocidad; se decodifica ordenando los
vértices por clave (SPV). Actualización estándar con inercia w, coeficientes c1 (cognitivo) y c2 (social),
topología global y velocidad acotada.
1 iteración = 1 partícula decodificada y evaluada (1 evaluación de fitness).

params: swarm (50), w (0.7), c1 (1.5), c2 (1.5), vmax (0.5)
"""
import numpy as np
from src.core import Config, Result, Budget, fitness


def run(instance, config: Config, seed: int) -> Result:
    n = instance.n
    p = config.params
    S, w, c1, c2, vmax = p.get("swarm", 50), p.get("w", 0.7), p.get("c1", 1.5), p.get("c2", 1.5), p.get("vmax", 0.5)
    rng, budget = np.random.default_rng(seed), Budget(config)
    best, best_f, history = None, None, []

    def evaluar(x):
        nonlocal best, best_f
        ruta = np.argsort(x, kind="stable").tolist()
        f = fitness(instance, ruta)
        budget.tick()
        if best_f is None or f < best_f:
            best, best_f = ruta, f
            history.append((budget.iterations, f))
        return f

    pos, vel, pbest, pbest_f = [], [], [], []
    while len(pos) < S and not budget.exhausted():
        x = rng.random(n)
        pos.append(x)
        vel.append(rng.uniform(-vmax, vmax, n))
        pbest.append(x.copy())
        pbest_f.append(evaluar(x))
    if not pos:
        return Result(None, None, [], budget.elapsed(), budget.iterations)
    g = int(np.argmin(pbest_f))
    gbest, gbest_f = pbest[g].copy(), pbest_f[g]

    while best_f != 0 and not budget.exhausted() and len(pos) == S:
        for i in range(S):
            if budget.exhausted() or best_f == 0:
                break
            r1, r2 = rng.random(n), rng.random(n)
            vel[i] = np.clip(w * vel[i] + c1 * r1 * (pbest[i] - pos[i]) + c2 * r2 * (gbest - pos[i]), -vmax, vmax)
            pos[i] = pos[i] + vel[i]
            f = evaluar(pos[i])
            if f <= pbest_f[i]:
                pbest[i], pbest_f[i] = pos[i].copy(), f
                if f < gbest_f:
                    gbest, gbest_f = pos[i].copy(), f
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
