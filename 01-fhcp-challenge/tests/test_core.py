import os
import random
from src.core import (read_hcp, write_tour, read_tour, fitness, validate,
                      random_permutation, decode_spv, Config)
from src.algorithms import REGISTRY
from experiments.runner import correr

HCP = os.path.join(os.path.dirname(__file__), "fixtures", "ejemplo6.hcp")


def test_loader():
    g = read_hcp(HCP)
    assert (g.n, g.m) == (6, 7)
    assert g.has_edge(0, 1) and g.has_edge(1, 0)      # simétrico
    assert not g.has_edge(5, 0)                        # 6-1 no existe
    assert len(g.sha256) == 64


def test_ciclo_valido_tiene_fitness_0():
    g = read_hcp(HCP)
    ruta = [0, 1, 2, 5, 4, 3]                          # 1-2-3-6-5-4
    assert fitness(g, ruta) == 0
    assert validate(g, ruta)["es_hamiltoniano"]


def test_cierre_faltante_cuenta_1():
    g = read_hcp(HCP)
    ruta = [0, 1, 2, 3, 4, 5]                          # 1-2-3-4-5-6, falta 6-1
    assert fitness(g, ruta) == 1
    assert not validate(g, ruta)["es_hamiltoniano"]


def test_permutaciones_invalidas():
    g = read_hcp(HCP)
    dup = validate(g, [0, 1, 2, 2, 4, 3])
    assert not dup["es_permutacion"] and dup["repetidos"] == 1 and dup["vertices_ausentes"] == 1
    corta = validate(g, [0, 1, 2])
    assert not corta["es_permutacion"] and corta["aristas_faltantes"] is None


def test_tour_roundtrip(tmp_path):
    ruta = [0, 1, 2, 5, 4, 3]
    p = tmp_path / "t.tour"
    write_tour(str(p), ruta)
    assert "1\n2\n3\n6\n5\n4\n-1\nEOF" in p.read_text()
    assert read_tour(str(p)) == ruta


def test_representacion():
    rng = random.Random(0)
    p = random_permutation(10, rng)
    assert p[0] == 0 and sorted(p) == list(range(10))
    assert decode_spv([0.62, 0.05, 0.31, 0.88, 0.47, 0.20]) == [1, 5, 2, 4, 0, 3]


def test_runner_y_reproducibilidad():
    cfg = Config(max_iterations=2000)
    a = correr(HCP, "random_search", 3, cfg)
    b = correr(HCP, "random_search", 3, cfg)
    assert [r["fitness"] for r in a] == [r["fitness"] for r in b]
    assert all(r["valido_independiente"] == r["exito"] for r in a)
    assert "random_search" in REGISTRY
