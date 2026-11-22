[↩ Volver a la Unidad 3](../README.md)

> Proyecto en equipo. El informe técnico completo está en [INFORME.pdf](INFORME.pdf) y el enunciado de la práctica en [practica.pdf](practica.pdf).

# Algoritmos Heurísticos: Ciclo Hamiltoniano sobre el FHCP Challenge Set

Código de la práctica "Aula invertida – Algoritmos heurísticos": carga grafos del FHCP, ejecuta
metaheurísticas (GA, SA, ACO, Bee Colony, DE, PSO) y devuelve un arreglo de vértices (el ciclo propuesto).

## Estructura
- `src/core/` loader HCP, lector/escritor TOUR, fitness, validador, representación, operadores, interfaz común
- `src/algorithms/` `ga.py`, `sa.py` (swap y 2-opt), `aco.py`, `bee.py`, `de.py`, `pso.py`, `random_search.py` + registro
- `src/core/preprocess.py` aristas forzadas de vértices de grado 2; `operators.py` también trae ER (recombinación de aristas)
- `experiments/` `runner.py` (una corrida), `benchmark.py` (todo el benchmark), `tuning.py` (ajuste de parámetros),
  `analisis.py` (tablas, pruebas estadísticas y figuras), `catalogo.py` (catálogo de instancias),
  `interfaz.py` (interfaz gráfica con tkinter), `masivo.py` (una metaheurística sobre muchos grafos del set en paralelo)
- `data/instances/` instancias (.hcp); `data/README.md` explica su origen; `data/catalogo_fhcp.csv` cataloga las 1001
- `INFORME.md` informe técnico completo (teoría, comparativa, benchmarking contra el FHCP y conclusiones)
- `results/` resultados del benchmark, del ajuste, tablas y figuras; `results/evidencia/` capturas de ejecución
  (terminal e interfaz) con sus salidas y tiempos; `results/masivo/` corrida masiva de ACO + 2-opt (16 grafos
  resueltos, ciclos en `tours_resueltos/`); `tests/` pruebas (`pytest`)
- [Seguimiento FHCP](results/seguimiento_fhcp/README.md) reúne los intentos, el estado de las 1001 instancias
  y los ciclos verificados en las corridas posteriores.

## Convenciones
- Vértices internos 0..n-1; los archivos usan 1..n (la conversión está en `hcp_io.py`).
- Fitness = aristas faltantes del ciclo cerrado; éxito si fitness == 0. El validador es independiente de los algoritmos.
- Todo algoritmo expone `run(instance, config, seed) -> Result(best_route, best_fitness, history, time, iterations)`.
- 1 iteración = 1 evaluación de fitness (completa en GA/ACO/DE/PSO; por delta O(1) en SA/Bee). Presupuesto = evaluaciones o tiempo.

## Uso (desde la carpeta raíz del proyecto)
    pip install -r requirements.txt
    python -m pytest

    # Interfaz gráfica (tkinter): elegir grafo y algoritmo, ver el ciclo y la convergencia
    python -m experiments.interfaz
    # En Linux, si falta tkinter: sudo apt install python3-tk

    # Una corrida con varias semillas -> CSV
    python -m experiments.runner --instance data/instances/graph1.hcp --algorithm sa_2opt --seeds 10 --max-iter 100000 --out results/sa_graph1.csv

    # Benchmark completo (reanudable) + análisis
    python -m experiments.benchmark --instances data/instances/graph1.hcp data/instances/graph24.hcp \
        --algorithms ga sa sa_2opt aco bee de pso random_search --seeds 10 --max-evals 100000 --time-limit 15 \
        --out results/bench --tours results/tours
    python -m experiments.analisis --prefix results/bench --out results/analisis

Algoritmos disponibles: `ga`, `sa` (swap), `sa_2opt`, `aco`, `bee`, `de`, `pso`, `random_search`
 y las mejoras de la segunda ronda: `aco_ls` (ACO + 2-opt, el único que resolvió una instancia),
 `aco_ls_pre` (+ preprocesamiento) y `ga_er` (GA con recombinación de aristas).
Los tours válidos encontrados se guardan en `results/tours/` (formato TOUR del FHCP).
Los parámetros por algoritmo están en el docstring de cada módulo y se pasan en `Config.params`.

## Benchmark nocturno en tres equipos

Instalen las dependencias y extraigan el archivo del catálogo desde la raíz del repositorio.
El archivo `FHCPCS.7z` se distribuye con el proyecto. Los grafos extraídos se generan en cada equipo.

```bash
python -m pip install -r requirements.txt
7z e data/FHCPCS.7z -odata/instances '*.hcp'
```

Asignen el lote 1, 2 o 3 a cada equipo y ajusten el número de procesos según la CPU disponible.
Cambien juntos el número de `--lote` y el de las rutas `lote1` del ejemplo. Los tres lotes cubren los
1001 grafos sin repetirlos y se distribuyen por tamaño. Cada grafo se prueba con los seis algoritmos,
las mismas tres semillas y un límite de 30 segundos por intento. La corrida empieza con su propio
registro y prueba también los grafos con ciclos guardados en el seguimiento exploratorio.

```bash
python -m experiments.benchmark --lote 1 --algorithms ga sa aco bee de pso \
    --seeds 3 --max-evals 100000000 --time-limit 30 --workers 7 \
    --out results/nocturna/lote1 --tours results/nocturna/lote1_tours
```

Con siete procesos, el presupuesto de búsqueda de cada lote equivale a unas 7 h 10 min si todos
los intentos consumen el límite. Los tiempos incluyen el efecto de la máquina y de la ejecución en
paralelo. Para reanudar, usen el mismo comando y prefijo. Guarden los archivos de entorno de cada equipo
junto con las corridas, los historiales y los ciclos.

Una vez reunidos los tres lotes en `results/nocturna/`, estos comandos generan las tablas y gráficas.

```bash
awk 'FNR != 1 || NR == 1' results/nocturna/lote{1,2,3}_runs.csv > results/nocturna/conjunto_runs.csv
cat results/nocturna/lote{1,2,3}_hist.jsonl > results/nocturna/conjunto_hist.jsonl
python -m experiments.analisis --prefix results/nocturna/conjunto --out results/nocturna/analisis
```

## Autores
Universidad Politécnica de Victoria · Docente: Dr. Said Polanco Martagón

| Nombre | Matrícula |
|---|---|
| Jared de Jesús Olazarán López | 2430022 |
| Georgina Reta Limas | 2430043 |
| Dulce Yaretzi Martínez Pérez | 2430038 |
| Melissa Jazmín Torres Martínez | 2430017 |
| Hugo Guillermo De León Ruiz | 2330419 |
