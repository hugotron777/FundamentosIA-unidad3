"""Interfaz común: run(instance, config, seed) -> best_route, best_fitness, history, time, iterations"""
from dataclasses import dataclass, field
from typing import NamedTuple
import time


@dataclass
class Config:
    max_iterations: int = 10_000          # límite común (fijar en Fase 2)
    time_limit: float | None = None       # segundos; None = sin límite
    params: dict = field(default_factory=dict)  # parámetros propios del algoritmo


class Result(NamedTuple):
    best_route: list      # permutación 0..n-1
    best_fitness: int     # aristas faltantes (0 = éxito)
    history: list         # [(iteración, mejor_fitness)] solo cuando mejora
    time: float           # segundos
    iterations: int


class Budget:
    """Cuenta iteraciones y tiempo; todos los algoritmos deben usarlo."""
    def __init__(self, cfg: Config):
        self.cfg, self.iterations, self._t0 = cfg, 0, time.perf_counter()

    def tick(self, k: int = 1):
        self.iterations += k

    def elapsed(self) -> float:
        return time.perf_counter() - self._t0

    def progress(self) -> float:
        """Fracción consumida del presupuesto (0..1): el máximo entre evaluaciones y tiempo."""
        f = self.iterations / max(1, self.cfg.max_iterations)
        if self.cfg.time_limit:
            f = max(f, self.elapsed() / self.cfg.time_limit)
        return min(1.0, f)

    def exhausted(self) -> bool:
        if self.iterations >= self.cfg.max_iterations:
            return True
        return self.cfg.time_limit is not None and self.elapsed() >= self.cfg.time_limit
