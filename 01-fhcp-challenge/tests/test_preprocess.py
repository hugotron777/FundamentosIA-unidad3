from src.core import fitness, validate
from src.core.preprocess import reducir
from tests.helpers import instancia_plantada


def test_reduccion_conserva_ciclos_hamiltonianos():
    # instancia plantada: el ciclo plantado debe seguir completo en el grafo reducido
    for seed in range(20):
        g = instancia_plantada(30, 6, seed=seed)          # pocas aristas extra -> hay grado 2
        red, forz, elim = reducir(g)
        assert all(red.adj[v] <= g.adj[v] for v in range(g.n))     # solo se quitan aristas
        assert elim == g.m - red.m
        assert all(len(f) <= 2 for f in forz)
        assert all(len(f) == 2 for f in (forz[v] for v in range(g.n) if len(g.adj[v]) == 2))
        # alguna orden de la reducción debe permitir fitness 0: el ciclo plantado sobrevive
        from tests.helpers import ciclo_plantado
        c = ciclo_plantado(30, 6, seed=seed)
        assert fitness(red, c) == 0 and validate(g, c)["es_hamiltoniano"]


def test_sin_grado_2_no_cambia_nada():
    from src.core import read_hcp
    import os
    g = read_hcp(os.path.join(os.path.dirname(__file__), "fixtures", "graph1.hcp"))   # cúbico
    red, forz, elim = reducir(g)
    assert elim == 0 and red.adj == g.adj
