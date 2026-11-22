"""Operadores sobre permutaciones (compartidos por los algoritmos)."""


def two_opt_delta(adj, route, i, j) -> int:
    """Cambio de fitness (aristas faltantes) al invertir route[i..j], con 1 <= i < j <= n-1.

    Solo cambian 2 aristas, así que el delta se calcula en O(1) sin recorrer la ruta.
    El vértice route[0] nunca se mueve. Válido para grafos no dirigidos.
    """
    n = len(route)
    a, b, c, d = route[i - 1], route[i], route[j], route[(j + 1) % n]
    viejo = (b not in adj[a]) + (d not in adj[c])
    nuevo = (c not in adj[a]) + (d not in adj[b])
    return nuevo - viejo


def swap_delta(adj, route, i, j) -> int:
    """Cambio de fitness al intercambiar route[i] y route[j], con 1 <= i < j <= n-1 (O(1)).

    Cambian hasta 4 aristas (2 si los puestos son contiguos, porque la arista entre ambos no cambia).
    """
    n = len(route)
    a, x, y, d = route[i - 1], route[i], route[j], route[(j + 1) % n]
    if j == i + 1:
        viejo = (x not in adj[a]) + (d not in adj[y])
        nuevo = (y not in adj[a]) + (d not in adj[x])
        return nuevo - viejo
    b, c = route[i + 1], route[j - 1]
    viejo = (x not in adj[a]) + (b not in adj[x]) + (y not in adj[c]) + (d not in adj[y])
    nuevo = (y not in adj[a]) + (b not in adj[y]) + (x not in adj[c]) + (d not in adj[x])
    return nuevo - viejo


def reverse_segment(route, i, j):
    """Invierte route[i..j] en sitio."""
    route[i:j + 1] = route[i:j + 1][::-1]


def order_crossover(p1, p2, rng):
    """OX: copia un tramo de p1 y completa con el orden relativo de p2. Devuelve una permutación válida."""
    n = len(p1)
    a, b = sorted(rng.sample(range(n + 1), 2))
    hijo = [None] * n
    hijo[a:b] = p1[a:b]
    en_tramo = set(p1[a:b])
    pos = b % n
    for v in p2[b:] + p2[:b]:
        if v not in en_tramo:
            hijo[pos] = v
            pos = (pos + 1) % n
    return hijo


def inversion_mutation(route, rng):
    """Invierte un tramo aleatorio (en sitio)."""
    n = len(route)
    a, b = sorted(rng.sample(range(n), 2))
    reverse_segment(route, a, b)


def edge_recombination(p1, p2, rng):
    """ER: el hijo reutiliza aristas de los padres (en cada paso va al vecino con menos vecinos libres).

    Conserva mejor las aristas reales que OX, que solo conserva el orden. Devuelve una permutación válida.
    """
    n = len(p1)
    vec = {v: set() for v in p1}
    for p in (p1, p2):
        for i in range(n):
            a, b = p[i], p[(i + 1) % n]
            vec[a].add(b)
            vec[b].add(a)
    actual = p1[0] if rng.random() < 0.5 else p2[0]
    restantes = set(p1)
    hijo = []
    while True:
        hijo.append(actual)
        restantes.discard(actual)
        if not restantes:
            return hijo
        vecinos = vec[actual]
        for w in vecinos:
            vec[w].discard(actual)
        if vecinos:
            minimo = min(len(vec[w]) for w in vecinos)
            actual = rng.choice([w for w in vecinos if len(vec[w]) == minimo])
        else:
            actual = rng.choice(tuple(restantes))
