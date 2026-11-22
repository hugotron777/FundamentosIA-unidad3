"""Registro de algoritmos. Cada módulo expone run(instance, config, seed) -> Result."""
from src.core import Config
from . import random_search, sa, ga, aco, bee, de, pso


def _con(modulo, **extra):
    """Variante de un algoritmo con parámetros fijos (se combinan con los de la Config)."""
    def run(instance, config, seed):
        cfg = Config(config.max_iterations, config.time_limit, {**extra, **config.params})
        return modulo.run(instance, cfg, seed)
    return run


REGISTRY = {
    "random_search": random_search.run,   # línea base
    "ga": ga.run,
    "sa": sa.run,                         # vecino por intercambio (swap), como pide la práctica
    "sa_2opt": _con(sa, move="2opt"),     # variante con inversión de tramo (2-opt)
    "aco": aco.run,
    "bee": bee.run,
    "de": de.run,
    "pso": pso.run,
    # mejoras (segunda ronda de experimentos)
    "ga_er": _con(ga, cross="er"),                 # GA con recombinación de aristas
    "aco_ls": _con(aco, ls=True),                  # ACO + búsqueda local 2-opt
    "aco_ls_pre": _con(aco, ls=True, reduce=True), # ACO + 2-opt + preprocesamiento de aristas forzadas
}

# Algoritmos que se comparan en el informe (la búsqueda aleatoria es solo piso de referencia)
PRINCIPALES = ["ga", "sa", "sa_2opt", "aco", "bee", "de", "pso"]
MEJORAS = ["ga_er", "aco_ls", "aco_ls_pre"]
