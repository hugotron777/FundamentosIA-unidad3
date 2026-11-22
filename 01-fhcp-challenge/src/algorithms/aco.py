"""Ant Colony Optimization (estilo MAX-MIN Ant System) para el ciclo hamiltoniano.

- Cada hormiga construye una ruta desde el vértice 0 moviéndose solo por aristas reales a vértices no
  visitados. Probabilidad ∝ tau^alpha * eta^beta, con eta = 1/(1 + vecinos no visitados del candidato)
  (heurística de Warnsdorff: priorizar los vértices más "acorralados").
- Callejón sin salida: se salta a un vértice no visitado al azar (esa arista falta y cuenta en el fitness).
- Feromona solo en aristas del grafo. Evaporación rho y depósito del mejor de la iteración y del mejor
  global (depósito 1/(1+fitness)), con límites tau_min/tau_max.
- 1 iteración = 1 hormiga construida y evaluada (1 evaluación de fitness).

params: ants (5), alpha (1.0), beta (2.0), rho (0.1), q_best (0.5: peso del mejor global)  [ants y beta ajustados]
        ls (False): búsqueda local 2-opt sobre las aristas faltantes de cada hormiga (variante aco_ls),
            con hasta `plateau` (100) movimientos neutros por hormiga (rotaciones de Pósa)
        reduce (False): preprocesa el grafo con aristas forzadas de vértices de grado 2 (variante aco_ls_pre)
Con ls, 1 iteración = 1 hormiga con su búsqueda local; el tope de tiempo es el límite común efectivo.
"""
import random
from src.core import Config, Result, Budget, fitness
from src.core.preprocess import reducir
from src.core.operators import two_opt_delta


def _construir(adj, n, tau, alpha, beta, rng):
    visitado = [False] * n
    restantes = [len(a) for a in adj]          # vecinos no visitados de cada vértice
    sin_visitar = list(range(n))               # lista con borrado O(1) (swap-pop)
    pos = list(range(n))
    ruta = []

    def visitar(v):
        visitado[v] = True
        ruta.append(v)
        for w in adj[v]:
            restantes[w] -= 1
        k = pos[v]
        ultimo = sin_visitar[-1]
        sin_visitar[k] = ultimo
        pos[ultimo] = k
        sin_visitar.pop()

    visitar(0)
    actual = 0
    while len(ruta) < n:
        cand = [w for w in adj[actual] if not visitado[w]]
        if not cand:
            actual = sin_visitar[rng.randrange(len(sin_visitar))]   # salto forzado
        else:
            if len(cand) == 1:
                actual = cand[0]
            else:
                t = tau[actual]
                pesos = [(t[w] ** alpha) * (1.0 / (1 + restantes[w])) ** beta for w in cand]
                actual = rng.choices(cand, weights=pesos)[0]
        visitar(actual)
    return ruta


def _busqueda_local(adj, ruta, f, rng=None, plateau=0):
    """2-opt dirigido a las aristas faltantes, con caminata por mesetas (rotaciones de Pósa).

    Para cada arista faltante (a, b) busca un vecino real c de a (o de b) y reconecta con una inversión de
    tramo; acepta si el fitness baja (delta < 0). Si no hay mejora, hace hasta `plateau` movimientos con
    delta = 0 elegidos al azar (cambian el extremo del camino sin empeorar) y vuelve a buscar mejoras.
    El vértice de la posición 0 no se mueve. Devuelve (ruta, fitness).
    """
    n = len(ruta)
    pos = [0] * n
    for i, v in enumerate(ruta):
        pos[v] = i

    def aplicar(lo, hi):
        ruta[lo + 1:hi + 1] = ruta[lo + 1:hi + 1][::-1]
        for k in range(lo + 1, hi + 1):
            pos[ruta[k]] = k

    pasos = 0
    while f > 0:
        mejorado, neutros = False, []
        for i in [i for i in range(n) if ruta[(i + 1) % n] not in adj[ruta[i]]]:
            a, b = ruta[i], ruta[(i + 1) % n]
            candidatos = [(i, pos[c]) for c in adj[a]] + [(i, (pos[c] - 1) % n) for c in adj[b]]
            for x, y in candidatos:
                lo, hi = (x, y) if x < y else (y, x)
                if hi - lo < 2:
                    continue
                d = two_opt_delta(adj, ruta, lo + 1, hi)
                if d < 0:
                    aplicar(lo, hi)
                    f += d
                    mejorado = True
                    break
                if d == 0:
                    neutros.append((lo, hi))
            if mejorado:
                break
        if mejorado:
            continue
        if rng is None or pasos >= plateau or not neutros:
            break
        aplicar(*rng.choice(neutros))
        pasos += 1
    return ruta, f


def run(instance, config: Config, seed: int) -> Result:
    if config.params.get("reduce", False):
        red, _, _ = reducir(instance)
        r = _run(red, config, seed)
        f = fitness(instance, r.best_route)          # el reportado es sobre el grafo original
        hist = r.history if f == r.best_fitness else r.history + [(r.iterations, f)]
        return Result(r.best_route, f, hist, r.time, r.iterations)
    return _run(instance, config, seed)


def _run(instance, config: Config, seed: int) -> Result:
    n, adj = instance.n, instance.adj
    p = config.params
    m_hormigas, alpha, beta = p.get("ants", 5), p.get("alpha", 1.0), p.get("beta", 2.0)
    rho, q_best = p.get("rho", 0.1), p.get("q_best", 0.5)
    usar_ls, plateau = p.get("ls", False), p.get("plateau", 100)

    rng, budget = random.Random(seed), Budget(config)
    tau = [{w: 1.0 for w in adj[v]} for v in range(n)]
    best, best_f, history = None, None, []

    while not budget.exhausted() and best_f != 0:
        mejor_it, mejor_it_f = None, None
        for _ in range(m_hormigas):
            if budget.exhausted():
                break
            ruta = _construir(adj, n, tau, alpha, beta, rng)
            f = fitness(instance, ruta)
            if usar_ls:
                ruta, f = _busqueda_local(adj, ruta, f, rng, plateau)
            budget.tick()
            if mejor_it_f is None or f < mejor_it_f:
                mejor_it, mejor_it_f = ruta, f
            if best_f is None or f < best_f:
                best, best_f = ruta[:], f
                history.append((budget.iterations, f))
        if mejor_it is None or best_f == 0:
            break
        tau_max = 1.0 / (rho * (1 + best_f))
        tau_min = tau_max / (2.0 * n)
        for v in range(n):                                        # evaporación
            tv = tau[v]
            for w in tv:
                x = tv[w] * (1.0 - rho)
                tv[w] = x if x > tau_min else tau_min
        for ruta, f, peso in ((mejor_it, mejor_it_f, 1.0 - q_best), (best, best_f, q_best)):
            dep = peso / (1.0 + f)
            for i in range(n):                                    # depósito en aristas reales
                u, v = ruta[i], ruta[(i + 1) % n]
                if v in tau[u]:
                    tau[u][v] = min(tau_max, tau[u][v] + dep)
                    tau[v][u] = min(tau_max, tau[v][u] + dep)
    return Result(best, best_f, history, budget.elapsed(), budget.iterations)
