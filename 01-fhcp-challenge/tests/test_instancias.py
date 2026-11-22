from src.core import read_hcp, fitness, validate

import os
import pytest

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
D = "data/instances/"   # instancias reales del FHCP (si no están, esas pruebas se omiten)


def test_envelope_oficial_con_sus_3_ciclos():
    g = read_hcp(os.path.join(FIX, "envelope6.hcp"))
    assert (g.n, g.m) == (6, 9)
    # Los 3 ciclos hamiltonianos que declara la página oficial (etiquetas 1..n -> 0..n-1)
    for ciclo in ([1, 2, 3, 6, 5, 4], [1, 2, 6, 3, 4, 5], [1, 4, 5, 6, 3, 2]):
        assert fitness(g, [v - 1 for v in ciclo]) == 0
    assert fitness(g, [0, 1, 2, 3, 4, 5]) == 1   # 1-2-3-4-5-6: solo falta la arista de cierre 6-1


def test_instancias_fhcp_cargan():
    esperado = {"graph1": (66, 99), "graph2": (70, 106), "graph3": (78, 117),
                "graph24": (198, 297), "graph41": (300, 451), "graph172": (1002, 1575)}
    for nombre, (n, m) in esperado.items():
        if not os.path.exists(D + nombre + ".hcp"):
            pytest.skip(f"falta {D}{nombre}.hcp")
        g = read_hcp(D + nombre + ".hcp")
        assert (g.n, g.m) == (n, m)
        assert all(len(a) >= 2 for a in g.adj)       # sin vértices de grado < 2 (son hamiltonianos)
