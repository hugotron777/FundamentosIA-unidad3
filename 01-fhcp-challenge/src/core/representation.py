"""Representación común: permutación de vértices (+ decodificador de claves reales)."""
import random


def random_permutation(n: int, rng: random.Random, fix_start: bool = True):
    """Permutación aleatoria; con fix_start el vértice 0 queda al inicio."""
    if fix_start:
        resto = list(range(1, n))
        rng.shuffle(resto)
        return [0] + resto
    ruta = list(range(n))
    rng.shuffle(ruta)
    return ruta


def decode_spv(keys):
    """Smallest Position Value: ordena los índices por clave creciente (DE, PSO)."""
    return sorted(range(len(keys)), key=lambda i: keys[i])
