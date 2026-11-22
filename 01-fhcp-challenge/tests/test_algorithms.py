import os
import random
import pytest
from src.core import read_hcp, fitness, validate, random_permutation, Config
from src.core.operators import edge_recombination, two_opt_delta, swap_delta, reverse_segment, order_crossover, inversion_mutation
from src.algorithms import REGISTRY
from tests.helpers import instancia_plantada

HCP = os.path.join(os.path.dirname(__file__), "fixtures", "ejemplo6.hcp")


def test_delta_2opt_coincide_con_recalculo_completo():
    g = instancia_plantada(25, 30, seed=1)
    rng = random.Random(7)
    for _ in range(500):
        ruta = random_permutation(g.n, rng)
        i, j = sorted(rng.sample(range(1, g.n), 2))
        d = two_opt_delta(g.adj, ruta, i, j)
        antes = fitness(g, ruta)
        reverse_segment(ruta, i, j)
        assert fitness(g, ruta) - antes == d


def test_delta_swap_coincide_con_recalculo_completo():
    g = instancia_plantada(25, 30, seed=1)
    rng = random.Random(11)
    for _ in range(1000):
        ruta = random_permutation(g.n, rng)
        i, j = sorted(rng.sample(range(1, g.n), 2))
        d = swap_delta(g.adj, ruta, i, j)
        antes = fitness(g, ruta)
        ruta[i], ruta[j] = ruta[j], ruta[i]
        assert fitness(g, ruta) - antes == d


def test_operadores_conservan_permutacion():
    rng = random.Random(3)
    for n in (3, 4, 10, 50):
        for _ in range(100):
            a, b = random_permutation(n, rng, False), random_permutation(n, rng, False)
            h = order_crossover(a, b, rng)
            assert sorted(h) == list(range(n))
            inversion_mutation(h, rng)
            assert sorted(h) == list(range(n))


TODOS = ["random_search", "ga", "sa", "sa_2opt", "aco", "bee", "de", "pso", "ga_er", "aco_ls", "aco_ls_pre"]


@pytest.mark.parametrize("alg", TODOS)
def test_resuelve_ejemplo6(alg):
    g = read_hcp(HCP)
    r = REGISTRY[alg](g, Config(max_iterations=5000), seed=0)
    assert r.best_fitness == 0 and validate(g, r.best_route)["es_hamiltoniano"]


@pytest.mark.parametrize("alg", TODOS)
def test_contrato_y_reproducibilidad(alg):
    g = instancia_plantada(30, 25, seed=2)
    cfg = Config(max_iterations=3000)
    r1, r2 = REGISTRY[alg](g, cfg, 5), REGISTRY[alg](g, cfg, 5)
    assert r1.best_route == r2.best_route and r1.best_fitness == r2.best_fitness
    v = validate(g, r1.best_route)
    assert v["es_permutacion"] and v["aristas_faltantes"] == r1.best_fitness   # fitness reportado = real
    assert r1.iterations <= cfg.max_iterations
    fs = [f for _, f in r1.history]
    assert fs == sorted(fs, reverse=True)                                     # historial no empeora


@pytest.mark.parametrize("alg", [a for a in TODOS if a != "random_search"])
def test_superan_busqueda_aleatoria(alg):
    g = instancia_plantada(30, 25, seed=2)
    cfg = Config(max_iterations=20000)
    media = lambda a: sum(REGISTRY[a](g, cfg, s).best_fitness for s in range(5)) / 5
    assert media(alg) < media("random_search")


def test_tope_de_tiempo_se_respeta():
    g = instancia_plantada(60, 60, seed=3)
    r = REGISTRY["aco"](g, Config(max_iterations=10**9, time_limit=0.5), 0)
    assert r.time < 1.5


def test_edge_recombination_conserva_permutacion():
    rng = random.Random(4)
    for n in (3, 5, 20, 80):
        for _ in range(100):
            a, b = random_permutation(n, rng, False), random_permutation(n, rng, False)
            assert sorted(edge_recombination(a, b, rng)) == list(range(n))


def test_busqueda_local_no_empeora_y_conserva_permutacion():
    from src.algorithms.aco import _busqueda_local
    g = instancia_plantada(40, 40, seed=5)
    rng = random.Random(1)
    for _ in range(50):
        r = random_permutation(g.n, rng)
        f0 = fitness(g, r)
        r2, f2 = _busqueda_local(g.adj, r[:], f0, random.Random(2), 30)
        assert sorted(r2) == list(range(g.n)) and r2[0] == r[0]
        assert f2 == fitness(g, r2) and f2 <= f0
