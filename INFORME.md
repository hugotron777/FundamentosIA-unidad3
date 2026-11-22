# Informe técnico: Metaheurísticas para el Problema del Ciclo Hamiltoniano sobre el FHCP Challenge Set

**Universidad Politécnica de Victoria**

**Práctica:** Aula invertida – Algoritmos heurísticos

**Docente:** Dr. Said Polanco Martagón

**Integrantes:**

| Nombre | Matrícula |
|---|---|
| Jared de Jesús Olazarán López | 2430022 |
| Georgina Reta Limas | 2430043 |
| Dulce Yaretzi Martínez Pérez | 2430038 |
| Melissa Jazmín Torres Martínez | 2430017 |
| Hugo Guillermo De León Ruiz | 2330419 |

**Repositorio:** código en `src/`, experimentos en `experiments/`, resultados en `results/`

---

## Resumen

Se implementaron seis metaheurísticas (GA, SA, ACO, Colonia de Abejas, DE y PSO), más una búsqueda aleatoria
como línea base y tres variantes mejoradas (SA con 2-opt, GA con recombinación de aristas y ACO con búsqueda
local 2-opt con y sin preprocesamiento). Todas cargan grafos del FHCP Challenge Set en formato HCP y devuelven
un arreglo de vértices (el ciclo propuesto), que un validador independiente comprueba.

Se evaluaron sobre 4 instancias del FHCP (n = 66 a 1002) con 10 semillas por algoritmo, un presupuesto de
100 000 evaluaciones de fitness y un tope de 15 s por corrida. Se hizo además una ronda "pesada" de 60 s por
corrida sobre 6 instancias (hasta n = 3468).

**Resultado principal:** solo los algoritmos con búsqueda local dirigida resolvieron una instancia del set.
ACO + 2-opt encontró el ciclo hamiltoniano de `graph1` en las 10/10 corridas (≈0.5 s, ≈530 hormigas) y
SA con 2-opt lo encontró en 5/10 corridas con 60 s. En `graph24` y `graph41`, ACO + 2-opt y SA (2-opt) llegan
a fitness 1: encuentran un **camino** hamiltoniano, pero sus extremos no son adyacentes. DE y PSO con claves
aleatorias apenas mejoran a la búsqueda aleatoria. En una corrida masiva sobre los 338 grafos del set con
hasta 2000 vértices, ACO + 2-opt resolvió 16 (de 66 a 310 vértices, sección 5.8). En comparación, el equipo
ganador del reto oficial (Cohen y Coudert) resolvió 985 de los 1001 grafos.

---

## 1. Fundamentación teórica (Fase 1)

### 1.1 Grafos, caminos y ciclos hamiltonianos

Un **grafo no dirigido** es un par G = (V, E), donde V = {v₁, …, vₙ} es el conjunto de **vértices** y
E ⊆ {{u, v} : u, v ∈ V, u ≠ v} el de **aristas**. El **grado** de un vértice es su número de vecinos.

- Un **camino** es una sucesión de vértices distintos (v₁, v₂, …, vₖ) en la que cada par consecutivo
  {vᵢ, vᵢ₊₁} ∈ E.
- Un **ciclo** es un camino (v₁, …, vₖ) con k ≥ 3 que además cumple {vₖ, v₁} ∈ E.
- Un **camino hamiltoniano** es un camino que pasa por los n vértices exactamente una vez.
- Un **ciclo hamiltoniano** es un ciclo que pasa por los n vértices exactamente una vez y regresa al
  origen. Por tanto tiene **longitud exacta n**: usa n vértices distintos y n aristas, n − 1 entre
  consecutivos más la de cierre {vₙ, v₁}.

Formalmente, G es hamiltoniano si existe una permutación π de {1, …, n} tal que
{v_π(i), v_π(i+1)} ∈ E para i = 1, …, n − 1 y {v_π(n), v_π(1)} ∈ E.

**Complejidad.** Decidir si un grafo es hamiltoniano es **NP-completo**: es uno de los 21 problemas de Karp
(1972), y la versión de búsqueda es NP-difícil. El número de ciclos candidatos es (n − 1)!/2. Para el grafo
más pequeño del set (n = 66) eso da del orden de 10⁹⁰ candidatos, así que la fuerza bruta es impracticable.

**Relación con el TSP.** El ciclo hamiltoniano es un caso particular del Problema del Agente Viajero. Basta
asignar costo 0 a las aristas de G y costo 1 a los pares que no son aristas: G es hamiltoniano si y solo si
el tour óptimo cuesta 0. Esta reducción justifica la función de fitness de la sección 2.2 y explica por qué
los mejores resolvedores del FHCP (Concorde, LKH) vienen del TSP.

### 1.2 Representación del espacio de búsqueda

Elegir la representación es decisivo. Hay dos riesgos: generar estructuras **ilegales** (vértices
repetidos u omitidos) o representaciones con mucha redundancia. Se consideraron estas opciones:

| Representación | Ventaja | Problema |
|---|---|---|
| Lista de aristas / matriz binaria | Directa | La mayoría de los individuos no son ciclos; requiere reparación |
| **Permutación de vértices** (elegida) | Siempre visita cada vértice una vez | Puede usar "aristas" que no existen en G |
| Claves aleatorias (*random keys*) | Permite operadores continuos (DE, PSO) | Fuerte redundancia: muchos vectores dan la misma permutación |

La decisión fue representar **toda solución como una permutación de 0..n−1**. Con ella, la restricción
"cada vértice exactamente una vez" se cumple por construcción. La única restricción que puede violarse es
"cada par consecutivo es una arista", y eso es justo lo que mide el fitness. Para que nunca aparezcan
cromosomas ilegales, todos los operadores (swap, inversión 2-opt, cruza OX, recombinación de aristas,
decodificación SPV) son **cerrados sobre permutaciones**. Las pruebas de `tests/` lo verifican.

### 1.3 Función de evaluación y heurísticas

Con la reducción al TSP, el fitness natural es el **número de aristas faltantes** del ciclo cerrado:

  f(π) = |{ i ∈ {1..n} : {π(i), π(i mod n + 1)} ∉ E }|

- f(π) = 0 si y solo si π es un ciclo hamiltoniano (criterio de éxito).
- f(π) = 1 significa que π contiene un **camino hamiltoniano** cuyos extremos no son adyacentes.
- La **legalidad** se define como 1 − f/n: la fracción de aristas del ciclo propuesto que existen en G.

Se estudiaron estas heurísticas que guían la búsqueda hacia la meta:

- **Evaluación incremental (delta).** Un swap o una inversión 2-opt cambia como máximo 4 o 2 aristas, así que
  el cambio de fitness se calcula en O(1) en lugar de O(n) (`two_opt_delta`, `swap_delta`).
- **Regla de Warnsdorff** (1823). Se prefiere el vecino con menos vecinos libres, porque es el que corre más
  riesgo de quedar aislado. ACO la usa como información heurística η.
- **Rotaciones de Pósa** (1976). Dado un camino, una arista desde un extremo hacia un vértice interior permite
  invertir un tramo y cambiar el extremo sin perder aristas. La búsqueda local de ACO las usa como
  movimientos neutros (delta = 0) para salir de mesetas.
- **Aristas forzadas.** Un vértice de grado 2 obliga a usar sus dos aristas, lo que permite eliminar otras
  aristas incompatibles. Es un preprocesamiento clásico en resolvedores del HCP (`src/core/preprocess.py`).

### 1.4 Métricas de evaluación

**Métricas de desempeño algorítmico**

| Métrica | Definición en este proyecto |
|---|---|
| Tasa de éxito | Corridas con f = 0 (validadas) / corridas totales. IC 95 % de Wilson |
| Costo en iteraciones | 1 iteración = 1 evaluación de fitness, completa o por delta. Así se comparan algoritmos con poblaciones de distinto tamaño |
| Tiempo computacional | Segundos de reloj por corrida (`time.perf_counter`) |
| ERT | *Expected Running Time*: evaluaciones totales / número de éxitos (Auger y Hansen, 2005) |
| Calidad | Fitness final (mejor, mediana, media, desviación) y legalidad |

**Métricas estadísticas: precisión, recall y F1.** Para aplicarlas, la búsqueda del ciclo se plantea como
una tarea de clasificación en dos niveles:

- **Nivel corrida.** Las 1001 instancias del FHCP son hamiltonianas, así que toda corrida es un caso positivo.
  - TP: el algoritmo reporta un ciclo y el validador independiente lo confirma.
  - FP: reporta un ciclo que el validador rechaza.
  - FN: no encuentra ciclo.

  Entonces precisión = TP/(TP+FP), **recall = TP/(TP+FN) = tasa de éxito** y F1 = 2PR/(P+R).
- **Nivel arista.** De las n aristas que propone el ciclo, son aciertos las que existen en G. La
  **precisión de aristas** es igual a la legalidad. El recall de aristas no se puede definir sin un ciclo
  de referencia único (una instancia puede tener muchos ciclos), así que no se reporta.

`experiments/analisis.py` calcula estas métricas y las escribe en `metricas_clasificacion.csv`.

**Pruebas estadísticas.** Se usaron Kruskal-Wallis por instancia, Mann-Whitney unilateral del mejor
algoritmo contra cada uno de los demás con corrección de Holm, y Friedman con rangos medios entre
instancias. Son pruebas no paramétricas, porque el fitness es discreto y está acotado.

### 1.5 El FHCP Challenge

El **Flinders Hamiltonian Cycle Project** publicó el *FHCP Challenge Set*: **1001 grafos hamiltonianos** de
66 a 9528 vértices (media ≈ 3000), diseñados para ser difíciles para las heurísticas estándar. Los
candidatos se probaron con Concorde, LKH y SLH, y se incluyó cada grafo que resultó difícil para al menos
dos de ellos (Haythorpe, 2018). El reto estuvo abierto del 30/09/2015 al 30/09/2016, con un premio de
US$1001.

- **Formato HCP** (entrada): encabezado `NAME`, `COMMENT`, `TYPE : HCP`, `DIMENSION : n`,
  `EDGE_DATA_FORMAT : EDGE_LIST`, `EDGE_DATA_SECTION`; después una arista "u v" por línea con vértices
  1..n, y al final `-1` / `EOF`.
- **Formato TOUR** (solución): `TYPE : TOUR`, `DIMENSION`, `TOUR_SECTION`; los n vértices en orden, `-1`,
  `EOF`. El proyecto escribe así los ciclos encontrados (`results/tours/`).
- **Criterio de benchmarking del reto:** el **número de instancias para las que se entrega un ciclo
  hamiltoniano válido**. No se premiaban soluciones parciales ni el tiempo. Por eso, además de la tasa de
  éxito por corrida, el proyecto reporta "instancias resueltas" (al menos una corrida exitosa).

---

## 2. Definición del problema y del modelo (Fases 2 y 4.2)

### 2.1 Definición algorítmica del grafo y los vértices

- `src/core/hcp_io.py` lee los archivos `.hcp` y convierte las etiquetas 1..n del archivo a vértices
  internos 0..n−1. Ignora aristas duplicadas y lazos. También escribe archivos `.tour` en 1..n.
- `src/core/graph.py`: `Instance(name, n, adj, m, sha256)`, donde `adj[v]` es un `frozenset` de vecinos.
  Así, la consulta "¿{u, v} ∈ E?" es O(1) en promedio, que es la operación más usada por todos los
  algoritmos.
- `src/core/fitness.py`: `fitness()` cuenta las aristas faltantes y `validate()` es un **validador
  independiente** de los algoritmos. Verifica que el resultado sea una permutación (sin repetidos ni
  ausentes) y que tenga 0 aristas faltantes. Todo éxito reportado se re-valida con él.

### 2.2 Representación y función de fitness

| Algoritmo | Representación | Cómo se obtiene la permutación |
|---|---|---|
| GA, SA, Bee | Permutación (vértice 0 fijo en SA/Bee) | Directa |
| ACO | Ruta construida vértice a vértice | Directa: la hormiga recorre aristas reales y salta solo si no tiene salida |
| DE, PSO | Vector real de n claves | Decodificación **SPV** (*Smallest Position Value*): ordenar los vértices por clave |

En todos los casos, fitness = aristas faltantes del ciclo cerrado (sección 1.3), que se **minimiza**.

### 2.3 Interfaz común

Todos los algoritmos exponen

```
run(instance, config, seed) -> Result(best_route, best_fitness, history, time, iterations)
```

Un objeto `Budget` lleva la cuenta de evaluaciones y tiempo, y aplica el mismo límite a todos.
`experiments/resolver.py` es el punto de entrada mínimo que pide la Fase 4.1: carga un grafo, ejecuta una
metaheurística, imprime el arreglo de vértices y guarda el `.tour` si es válido.

---

## 3. Implementación algorítmica (Fase 3)

Los valores entre corchetes son los parámetros finales, elegidos con `experiments/tuning.py` (ver 4.3).

### 3.1 Algoritmo Genético (GA): base de control (`src/algorithms/ga.py`)
Población de permutaciones, selección por torneo (k = 3), **cruza OX** (*Order Crossover*: copia un tramo de
un padre y completa con el orden relativo del otro), **mutación por inversión** de un tramo y elitismo
(2 individuos). [pop_size = 50, pc = 0.9, pm = 0.3]

**Variante GA (ER):** cruza por **recombinación de aristas** (Whitley et al., 1989), que hereda aristas en
lugar de posiciones.

### 3.2 Recocido Simulado (SA) (`src/algorithms/sa.py`)
Como pide la práctica, el vecino es un **intercambio aleatorio de dos índices (swap)** del arreglo. La
aceptación sigue el criterio de Metropolis: un movimiento que empeora en δ se acepta con probabilidad
P = exp(−δ/T). El enfriamiento es geométrico y **lento**: T va de t₀ a t_end a lo largo de todo el
presupuesto, T = t₀·(t_end/t₀)^progreso, y se recalcula cada 64 movimientos. El delta se calcula en O(1).
[swap: t₀ = 2.0, t_end = 0.01]

Con t₀ = 2.0, al inicio se acepta el 61 % de los movimientos que empeoran en una arista (e^(−1/2)) y el 14 %
de los que empeoran en cuatro. La temperatura baja 200 veces a lo largo de las 100 000 evaluaciones, así que
al final SA solo acepta mejoras o movimientos neutros (ver 4.3).

**Variante SA (2-opt):** el vecino invierte un tramo, lo que cambia solo 2 aristas en vez de 4.

[t₀ = 0.3, t_end = 0.02]

### 3.3 Colonia de Hormigas (ACO) (`src/algorithms/aco.py`)
Es un esquema **MAX-MIN Ant System** (Stützle y Hoos, 2000). Cada hormiga parte del vértice 0 y avanza
**solo por aristas reales** hacia vértices no visitados. Elige el siguiente vértice con probabilidad
∝ τ^α·η^β, con η = 1/(1 + vecinos libres del candidato), que es la regla de Warnsdorff. Si queda
acorralada, salta a un vértice no visitado al azar; esa arista falta y penaliza el fitness. La feromona se
evapora a razón ρ y se deposita en las aristas del mejor de la iteración y del mejor global, dentro de los
límites [τ_min, τ_max]. Así se **refuerzan las aristas que conectan nodos difíciles** en rutas
prometedoras. [ants = 5, α = 1, β = 2, ρ = 0.1]

**Variantes:**

- **ACO + 2-opt (`aco_ls`):** cada hormiga se refina con una búsqueda local 2-opt dirigida a sus aristas
  faltantes, más hasta 100 movimientos neutros por rotaciones de Pósa.
- **ACO + 2-opt + prepro. (`aco_ls_pre`):** además reduce el grafo con aristas forzadas (sección 1.3).

### 3.4 Colonia de Abejas (ABC discreta) (`src/algorithms/bee.py`)
Las fuentes de alimento son permutaciones.

- **Empleadas:** aplican una variación (swap o inversión) a su fuente y la aceptan si no empeora.
- **Observadoras:** eligen una fuente con probabilidad ∝ 1/(1 + f), es decir, siguen a las fuentes
  prometedoras.
- **Exploradoras:** abandonan una fuente sin mejora estricta en `limit` intentos y la reemplazan por una
  permutación aleatoria.

[sources = 5, limit = 2000]

### 3.5 Evolución Diferencial (DE) (`src/algorithms/de.py`)
La DE es continua por naturaleza. Para adaptarla a permutaciones se usan **claves aleatorias** (Bean, 1994):
cada individuo es un vector x ∈ [0,1]ⁿ y se decodifica con SPV. La mutación DE/rand/1
(v = x_r1 + F·(x_r2 − x_r3)) y la cruza binomial operan en el espacio continuo, y la selección es voraz.
Así nunca se generan permutaciones ilegales. [pop_size = 10, F = 0.7, CR = 0.9]

### 3.6 Enjambre de Partículas (PSO) (`src/algorithms/pso.py`)
Cada partícula es un vector de claves con velocidad, decodificado por SPV (Tasgetiren et al., 2007). La
velocidad se actualiza con la regla estándar v ← w·v + c₁r₁(pbest − x) + c₂r₂(gbest − x), con topología
global y velocidad acotada. No hay líder: cada partícula solo sigue reglas simples con su mejor posición y
la del enjambre. [swarm = 50, w = 0.7, c₁ = c₂ = 1.5, vmax = 0.5]

### 3.7 Línea base
`random_search` muestrea permutaciones aleatorias. Sirve de piso: un algoritmo que no la supera no aprende
nada de la estructura del grafo.

---

## 4. Dataset y diseño experimental

### 4.1 Instancias

| Instancia | n | m | Grado mín./máx. | Vértices de grado 2 | Aristas eliminadas por preprocesamiento |
|---|---|---|---|---|---|
| graph1 | 66 | 99 | 3 / 3 | 0 | 0 |
| graph24 | 198 | 297 | 3 / 3 | 0 | 0 |
| graph41 | 300 | 451 | 3 / 4 | 0 | 0 |
| graph172 | 1002 | 1575 | 2 / 9 | 340 | 10 (672 aristas forzadas) |
| graph300* | 1815 | 3177 | 2 / 154 | 606 | 10 (1211 aristas forzadas) |
| graph600* | 3468 | 5203 | 3 / 4 | 0 | 0 |

\* Solo en la ronda pesada.

**Procedencia y verificación.** Las instancias provienen del FHCP Challenge Set: `data/FHCPCS.7z` trae los
1001 grafos y `data/catalogo_fhcp.csv` los cataloga con n, m, grados y sha256. Se comprobó que los 1001
archivos del `.7z` son **idénticos byte a byte** a los del catálogo, salvo por los saltos de línea
(CRLF en el `.7z`, LF en el catálogo). Si `FHCPCS.7z` es la descarga oficial de Flinders, esto resuelve el
pendiente de verificación de `data/README.md`. Por esa misma diferencia de saltos de línea los sha256 de
`bench_runs.csv` y `pesada_runs.csv` no coinciden, aunque el grafo es el mismo.

### 4.2 Protocolo

| Ronda | Instancias | Algoritmos | Semillas | Presupuesto | Archivo |
|---|---|---|---|---|---|
| **Benchmark principal** | graph1, 24, 41, 172 | los 10 + aleatoria | 0..9 | 100 000 evaluaciones, tope 15 s | `results/bench_*` |
| Pesada | + graph300, 600 | ga, sa_2opt, aco, bee, aco_ls, aco_ls_pre | 0..9 | 60 s (evaluaciones sin límite práctico) | `results/pesada_*` |
| Media | graph1, 24, 41, 172 | ga, sa_2opt, aco_ls | 0..4 | 30 s | `results/media_*` |

- **Comparación justa:** 1 iteración = 1 evaluación de fitness en todos los algoritmos. El tope de tiempo
  impide que los algoritmos con evaluaciones caras (GA-ER, ACO, ACO+LS) excedan el presupuesto. En ACO + LS,
  una iteración incluye la búsqueda local, así que su límite efectivo es el tiempo.
- **Validación:** todo tour con f = 0 se re-valida con `validate()`. La columna `validado` de la tabla
  resumen vale 1 en todas las filas: **0 falsos positivos**.
- **Entornos:** el benchmark principal se corrió en Python 3.12.3 (Linux x86_64; las 40 corridas de
  SA (swap) se repitieron el 12/11/2026 con los parámetros de 4.3, ver nota en 5.2) y las rondas
  pesada/media en Python 3.14.6 (Linux x86_64, 8 núcleos, ejecución en paralelo). Los tiempos son
  comparables dentro de cada ronda, no entre rondas.

### 4.3 Ajuste de parámetros

Se hizo un barrido por rejilla (`experiments/tuning.py`, resultados en `results/tuning.csv`) sobre graph1 y
graph24 con las semillas 100–102, **distintas de las del benchmark** para no sobreajustar. El presupuesto
fue de 30 000 evaluaciones y 8 s. Métrica: fitness final medio / n.

| Algoritmo | Mejores parámetros | Fitness normalizado |
|---|---|---|
| ACO | ants = 5, β = 2.0 (empate) | 0.011 |
| SA (2-opt) | t₀ = 0.3, t_end = 0.02 | 0.096 |
| GA | pop_size = 50, pm = 0.3 | 0.243 |
| SA (swap) | t₀ = 2.0, t_end = 0.01 (ver abajo) | 0.223 |
| Bee | sources = 5, limit = 2000 | 0.295 |
| DE | pop_size = 10, F = 0.7, CR = 0.9 | 0.624 |
| PSO | swarm = 50, w = 0.7, vmax = 0.5 | 0.767 |

- **ACO:** ants = 5, β = 2 empató con ants = 10, β = 5 (0.01094 los dos). Se eligió 5/2 porque con
  menos hormigas por iteración la feromona se actualiza más seguido con el mismo presupuesto, y β = 2 es el
  valor habitual en MMAS (Stützle y Hoos, 2000).
- **SA (swap):** el primer barrido (30 000 evaluaciones) eligió t₀ = 0.1, t_end = 0.05. Con esa
  temperatura un empeoramiento de 1 se acepta con probabilidad e⁻¹⁰ ≈ 0.00005, así que SA se comportaba
  como un descenso que solo acepta mejoras, y no como el recocido que pide la práctica. Se repitió el ajuste
  con el presupuesto real del benchmark (100 000 evaluaciones, `results/tuning_sa.csv`). Las temperaturas
  casi nulas siguen siendo ligeramente mejores (0.204 contra 0.223), pero se eligió la mejor
  configuración con t₀ ≥ 1, **t₀ = 2.0 y t_end = 0.01**, para que SA acepte de verdad soluciones peores al
  inicio y enfríe lentamente. La diferencia entre temperaturas es pequeña frente a la que produce el
  vecindario (sección 7).

---

## 5. Comparativa de resultados (núcleo de la práctica)

### 5.1 Tasa de éxito y calidad (benchmark principal)

Cada celda indica **éxitos/10 · fitness mediano · mejor fitness** (aristas faltantes; 0 = ciclo
hamiltoniano):

| Algoritmo | graph1 (n=66) | graph24 (n=198) | graph41 (n=300) | graph172 (n=1002) |
|---|---|---|---|---|
| **ACO + 2-opt + prepro.** | **10/10 · 0 · 0** | 0/10 · 1 · 1 | 0/10 · 1 · 1 | 0/10 · 12 · 9 |
| **ACO + 2-opt** | **10/10 · 0 · 0** | 0/10 · 1 · 1 | 0/10 · 1 · 1 | 0/10 · 13.5 · 9 |
| ACO | 0/10 · 1 · 1 | 0/10 · 1.5 · 1 | 0/10 · 1 · 1 | 0/10 · 16 · 13 |
| GA (ER) | 0/10 · 4.5 · 4 | 0/10 · 47.5 · 43 | 0/10 · 154 · 145 | 0/10 · 911.5 · 898 |
| GA | 0/10 · 5.5 · 3 | 0/10 · 31.5 · 29 | 0/10 · 81 · 77 | 0/10 · 604.5 · 594 |
| SA (2-opt) | 0/10 · 1 · 1 | 0/10 · 16 · 11 | 0/10 · 42.5 · 37 | 0/10 · 634 · 622 |
| SA (swap) | 0/10 · 10.5 · 7 | 0/10 · 60.5 · 57 | 0/10 · 114 · 110 | 0/10 · 680 · 671 |
| Bee Colony | 0/10 · 4 · 2 | 0/10 · 55.5 · 51 | 0/10 · 131 · 125 | 0/10 · 844 · 832 |
| DE | 0/10 · 29 · 26 | 0/10 · 129.5 · 124 | 0/10 · 219 · 210 | 0/10 · 900.5 · 888 |
| PSO | 0/10 · 44 · 38 | 0/10 · 173 · 164 | 0/10 · 274 · 270 | 0/10 · 971 · 964 |
| Aleatoria | 0/10 · 53.5 · 52 | 0/10 · 185.5 · 184 | 0/10 · 287 · 286 | 0/10 · 989 · 986 |

El IC 95 % de Wilson de la tasa de éxito es [0.72, 1.00] para 10/10 y [0.00, 0.28] para 0/10.

![Tasa de éxito](results/analisis/fig_tasa_exito.png)

![Distribución del fitness final](results/analisis/fig_fitness_boxplot.png)

### 5.2 Tiempo computacional

Cada celda indica **tiempo medio por corrida / evaluaciones medias**:

| Algoritmo | graph1 | graph24 | graph41 | graph172 |
|---|---|---|---|---|
| ACO + 2-opt + prepro. | 0.48 s / 532 | 15.00 s / 7 103 | 15.00 s / 3 392 | 15.01 s / 554 |
| ACO + 2-opt | 0.49 s / 532 | 15.00 s / 7 331 | 15.00 s / 3 339 | 15.01 s / 544 |
| ACO | 6.75 s / 100 000 | 15.00 s / 72 750 | 15.00 s / 44 590 | 15.00 s / 11 460 |
| GA (ER) | 7.78 s / 100 000 | 15.00 s / 68 368 | 15.00 s / 40 432 | 15.00 s / 9 987 |
| GA | 1.16 s / 100 000 | 2.20 s / 100 000 | 3.52 s / 100 000 | 13.77 s / 100 000 |
| SA (2-opt) | 0.12 s / 100 000 | 0.11 s / 100 000 | 0.17 s / 100 000 | 0.43 s / 100 000 |
| SA (swap)† | 0.22 s / 100 000 | 0.21 s / 100 000 | 0.24 s / 100 000 | 0.25 s / 100 000 |
| Bee Colony | 0.14 s / 100 000 | 0.14 s / 100 000 | 0.20 s / 100 000 | 0.46 s / 100 000 |
| DE | 1.03 s / 100 000 | 1.96 s / 100 000 | 2.87 s / 100 000 | 11.72 s / 100 000 |
| PSO | 1.19 s / 100 000 | 2.17 s / 100 000 | 3.21 s / 100 000 | 12.99 s / 100 000 |
| Aleatoria | 1.19 s / 100 000 | 3.45 s / 100 000 | 5.84 s / 100 000 | 15.00 s / 61 505 |

† Las corridas de SA (swap) se repitieron con los parámetros nuevos en otra máquina (Python 3.12.3, Linux
x86_64, 12 núcleos, ejecución secuencial; ver `results/bench_entorno.txt`). Su tiempo no es directamente
comparable con el resto de la tabla; el número de evaluaciones sí.

- **ERT** de ACO + 2-opt en graph1: **532.5 evaluaciones** (≈0.5 s). Es el único caso con éxito en el
  benchmark principal.
- **Costo por evaluación.** SA y Bee usan delta en O(1) y hacen 100 000 movimientos en 0.1–0.5 s. GA, DE y PSO
  evalúan permutaciones completas en O(n), unas 10–100 veces más caro. ACO construye cada ruta en O(n·grado)
  y con búsqueda local cada hormiga cuesta mucho más (~1 ms en graph1), pero cada evaluación vale mucho más.

![Tiempo](results/analisis/fig_tiempo.png)

### 5.3 Convergencia

La figura muestra la mediana del mejor fitness frente a las evaluaciones (escala log). ACO y ACO + 2-opt
llegan casi a 0 con pocas evaluaciones, porque construyen rutas sobre aristas reales. SA (2-opt) y Bee bajan rápido y
se estancan. SA (swap) se queda cerca de la búsqueda aleatoria durante las primeras ~10 000 evaluaciones,
porque a temperatura alta acepta muchos empeoramientos, y desciende cuando la temperatura baja. DE y PSO apenas se separan de la búsqueda aleatoria.

![Convergencia](results/analisis/fig_convergencia.png)

### 5.4 Precisión, recall y F1

Datos de `results/analisis/metricas_clasificacion.csv`:

| Algoritmo | Precisión (corrida) | Recall = tasa de éxito | F1 | Precisión de aristas: g1 / g24 / g41 / g172 |
|---|---|---|---|---|
| ACO + 2-opt + prepro. | 1.00 | g1: 1.00; resto: 0 | g1: 1.00; resto: 0 | 1.000 / 0.995 / 0.997 / 0.988 |
| ACO + 2-opt | 1.00 | g1: 1.00; resto: 0 | g1: 1.00; resto: 0 | 1.000 / 0.995 / 0.997 / 0.987 |
| ACO | n/d | 0 | 0 | 0.985 / 0.991 / 0.995 / 0.984 |
| SA (2-opt) | n/d | 0 | 0 | 0.983 / 0.921 / 0.859 / 0.366 |
| GA | n/d | 0 | 0 | 0.920 / 0.839 / 0.728 / 0.397 |
| Bee Colony | n/d | 0 | 0 | 0.938 / 0.722 / 0.565 / 0.159 |
| GA (ER) | n/d | 0 | 0 | 0.924 / 0.758 / 0.488 / 0.093 |
| SA (swap) | n/d | 0 | 0 | 0.852 / 0.694 / 0.618 / 0.320 |
| DE | n/d | 0 | 0 | 0.562 / 0.335 / 0.260 / 0.099 |
| PSO | n/d | 0 | 0 | 0.348 / 0.133 / 0.087 / 0.031 |
| Aleatoria | n/d | 0 | 0 | 0.191 / 0.064 / 0.043 / 0.013 |

La precisión por corrida es 1.00 siempre que hay positivos reportados: **no hubo ningún falso positivo**,
porque todo ciclo reportado pasó el validador independiente. Es "n/d" cuando el algoritmo nunca reportó un
ciclo. El recall, que coincide con la tasa de éxito, es la métrica que separa a los algoritmos. La precisión
de aristas mide qué tan cerca se quedó cada algoritmo de un ciclo cuando falló.

### 5.5 Significancia estadística

- **Kruskal-Wallis** por instancia: p < 10⁻¹⁶ en las 4 instancias (entre 4.7·10⁻¹⁷ y 9.0·10⁻¹⁷). Los algoritmos difieren.
- **Mann-Whitney + Holm**, comparando el mejor (ACO + 2-opt + prepro.) con cada uno de los demás: la
  diferencia es significativa al 5 % frente a **todos** los algoritmos en las 4 instancias, excepto frente a
  ACO + 2-opt sin preprocesamiento (p_Holm = 1.0, 1.0, 1.0, 0.30). Ver
  `results/analisis/pruebas_estadisticas.csv`.
- **Friedman** entre instancias: χ² = 33.8, **p = 0.0001**. Rangos medios (1 = mejor):

| ACO+2opt+pre | ACO+2opt | ACO | SA (2-opt) | GA | Bee | SA (swap) | GA (ER) | DE | PSO |
|---|---|---|---|---|---|---|---|---|---|
| 1.38 | 1.62 | 3.00 | 4.25 | 5.25 | 6.50 | 7.00 | 7.25 | 8.75 | 10.00 |

### 5.6 Ronda pesada (60 s por corrida)

Cada celda indica **éxitos/10 · fitness mediano · mejor fitness**:

| Algoritmo | graph1 (66) | graph24 (198) | graph41 (300) | graph172 (1002) | graph300 (1815) | graph600 (3468) |
|---|---|---|---|---|---|---|
| ACO + 2-opt + prepro. | **10/10 · 0 · 0** | 0/10 · 1 · 1 | 0/10 · 1 · 1 | 0/10 · 7.5 · **4** | 0/10 · 70.5 · 65 | 0/10 · 170 · 166 |
| ACO + 2-opt | **10/10 · 0 · 0** | 0/10 · 1 · 1 | 0/10 · 1 · 1 | 0/10 · 6.5 · 5 | 0/10 · 69 · 58 | 0/10 · 170 · 166 |
| ACO | 0/10 · 1 · 1 | 0/10 · 1.5 · 1 | 0/10 · 1 · 1 | 0/10 · 16 · 13 | 0/10 · **33 · 18** | 0/10 · **145 · 134** |
| SA (2-opt) | **5/10 · 0.5 · 0** | 0/10 · 1 · 1 | 0/10 · 1 · 1 | 0/10 · 25.5 · 20 | 0/10 · 133.5 · 119 | 0/10 · 969 · 901 |
| GA | 0/10 · 4 · 3 | 0/10 · 18 · 15 | 0/10 · 28.5 · 24 | 0/10 · 563 · 551 | 0/10 · 1470.5 · 1421 | 0/10 · 3296.5 · 3286 |
| Bee Colony | 0/10 · 2 · 1 | 0/10 · 30 · 28 | 0/10 · 71.5 · 70 | 0/10 · 549 · 526 | 0/10 · 1302 · 1262 | 0/10 · 3124 · 3028 |

- Con 60 s, **SA (2-opt) también resuelve graph1** (5/10). Las 5 corridas exitosas tardaron en promedio 39.7 s y 1.2·10⁷ movimientos; las otras 5 agotaron
  los 60 s. Es la
  segunda metaheurística del proyecto que encuentra un ciclo hamiltoniano del set.
- En los grafos más grandes (graph300, graph600), **ACO sin búsqueda local supera a ACO + 2-opt**. Con
  n ≥ 1815, la búsqueda local deja solo ~70–200 hormigas en 60 s y la feromona no alcanza a aprender.
  Friedman en esta ronda: χ² = 23.6, p = 0.0003. Análisis completo en `results/analisis_pesada/`.

### 5.7 Evidencia de ejecución (capturas y tiempos)

Las capturas se tomaron el 17/11/2026 en la misma máquina del benchmark (Linux, Python 3.12.3, 12 núcleos,
un solo proceso). Las de terminal muestran la salida real de cada comando, tal como se guardó en
`results/evidencia/*.txt`. Al pie de cada una va el tiempo total del comando (reloj de pared), que incluye
arrancar Python y cargar el grafo. El tiempo que reporta cada algoritmo cuenta solo la búsqueda.

**Resolver una instancia (`experiments/resolver.py`).** ACO + 2-opt encuentra un ciclo hamiltoniano de graph1
en 0.12 s y 95 evaluaciones, y lo guarda en formato TOUR:

![Terminal: resolver graph1 con ACO + 2-opt](results/evidencia/t1_resolver_graph1_aco_ls.png)

Con los grafos de prueba pequeños (envelope6 y ejemplo6) SA 2-opt y GA dan con el ciclo de inmediato. En
graph24 (n = 198), SA 2-opt agota las 100 000 evaluaciones en 0.21 s y se queda a 19 aristas:

![Terminal: varias instancias y algoritmos](results/evidencia/t2_resolver_pequenos.png)

**Varias semillas (`experiments/runner.py`).** ACO + 2-opt resuelve graph1 con las 10 semillas. El tiempo por
corrida va de 0.10 s a 2.91 s (media 0.69 s, mediana 0.40 s); la variación viene de cuántas iteraciones
necesita cada semilla (80 a 2 320):

![Terminal: 10 semillas de ACO + 2-opt en graph1](results/evidencia/t3_runner_graph1.png)

**Mini-benchmark (`experiments/benchmark.py`).** 5 algoritmos × 2 instancias × 5 semillas, límite de 5 s y
100 000 evaluaciones por corrida (50 corridas, 65 s en total):

![Terminal: mini-benchmark de 50 corridas](results/evidencia/t4_benchmark.png)

| Instancia | Algoritmo | Éxitos | Fitness mín. / medio | Tiempo medio (s) | Tiempo mín.–máx. (s) | Evaluaciones medias |
|---|---|---|---|---|---|---|
| graph1 (n = 66) | ACO + 2-opt | **5/5** | **0 / 0** | 0.84 | 0.13–2.90 | 670 |
| graph1 | SA (2-opt) | 0/5 | 1 / 1.2 | 0.21 | 0.20–0.22 | 100 000 |
| graph1 | Bee Colony | 0/5 | 3 / 4.0 | 0.25 | 0.25–0.26 | 100 000 |
| graph1 | GA | 0/5 | 3 / 5.0 | 2.03 | 2.00–2.11 | 100 000 |
| graph1 | SA (swap) | 0/5 | 8 / 10.6 | 0.23 | 0.22–0.23 | 100 000 |
| graph24 (n = 198) | ACO + 2-opt | 0/5 | **1 / 1.0** | 5.00 | 5.00–5.00 | 1 653 |
| graph24 | SA (2-opt) | 0/5 | 16 / 17.6 | 0.20 | 0.20–0.20 | 100 000 |
| graph24 | GA | 0/5 | 30 / 32.0 | 3.80 | 3.78–3.85 | 100 000 |
| graph24 | Bee Colony | 0/5 | 51 / 54.0 | 0.26 | 0.26–0.26 | 100 000 |
| graph24 | SA (swap) | 0/5 | 58 / 62.0 | 0.21 | 0.21–0.21 | 100 000 |

Los resultados coinciden con el benchmark principal (§5.1–5.2). ACO + 2-opt es el único que cierra el ciclo
en graph1 y el que más se acerca en graph24, aunque ahí consume todo el límite de tiempo. SA y Bee Colony son
los más rápidos (≈0.2 s para 100 000 evaluaciones, porque evalúan por delta), pero se quedan lejos. Las
corridas completas están en `results/evidencia/bench_runs.csv`.

**Pruebas automáticas.** `pytest` pasa 48 pruebas (1 omitida) en 21.4 s:

![Terminal: pytest](results/evidencia/t5_pytest.png)

**Interfaz gráfica (`experiments/interfaz.py`).** Muestra el ciclo propuesto en círculo (verde: arista del
grafo; rojo: arista que no existe), la curva de convergencia, el tiempo y el arreglo de vértices. ACO + 2-opt
resuelve graph1 en 0.14 s:

![Interfaz: graph1 resuelto con ACO + 2-opt](results/evidencia/g1_interfaz_graph1_aco_ls.png)

En el mismo grafo, el GA termina con 6 aristas faltantes tras 100 000 evaluaciones (2.22 s):

![Interfaz: graph1 con GA](results/evidencia/g2_interfaz_graph1_ga.png)

En graph24, SA 2-opt baja de ~190 a 19 aristas faltantes en 0.22 s; las 19 aristas inexistentes se ven
marcadas en rojo:

![Interfaz: graph24 con SA 2-opt](results/evidencia/g3_interfaz_graph24_sa_2opt.png)

Y en un grafo pequeño (envelope6), la colonia de abejas encuentra el ciclo en 5 evaluaciones:

![Interfaz: envelope6 con Bee Colony](results/evidencia/g4_interfaz_envelope6_bee.png)

### 5.8 Corrida masiva sobre el set (ACO + 2-opt)

Las secciones anteriores usan 6 instancias para comparar algoritmos. Para medir cuántos grafos del set
resuelve el mejor de ellos, se corrió ACO + 2-opt (`aco_ls`, semilla 0) sobre los 338 grafos de hasta 2000
vértices, del más chico al más grande, con 11 procesos en paralelo (`experiments/masivo.py`). Se hizo en
tres pasadas:

1. 30 s por grafo sobre los 33 grafos más chicos: resolvió 12. Se detuvo porque cada grafo no resuelto
   gastaba los 30 s completos.
2. 4 s por grafo sobre los 338 grafos de hasta 2000 vértices: resolvió 10, todos ya incluidos en la pasada
   anterior. Tardó 2 min de reloj.
3. 10 reintentos con semillas 1 a 10 y 6 s por grafo sobre los grafos de hasta 400 vértices que seguían sin
   resolver: resolvió 4 más (graph31, graph35, graph39 y graph43). En las últimas cinco semillas no salió
   ninguno nuevo.

En total se resolvieron 16 grafos. Los 16 ciclos se validaron de nuevo contra su grafo y están en
`results/masivo/tours_resueltos/`.

| Vértices | Grafos | Resueltos | Con f = 1 | f mediano | Mejor f |
|---|---|---|---|---|---|
| 66–200 | 24 | 11 | 13 | 1 | 0 |
| 201–400 | 35 | 5 | 26 | 1 | 0 |
| 401–700 | 72 | 0 | 0 | 15 | 2 |
| 701–1000 | 40 | 0 | 0 | 31 | 13 |
| 1001–2000 | 167 | 0 | 0 | 82 | 31 |
| **Total** | **338** | **16** | **39** | | |

f es el número de aristas faltantes en la mejor ruta encontrada para cada grafo, tomando todas las pasadas.

Resueltos: graph1, 2, 3, 4, 6, 8, 10, 12, 14, 18, 23, 27, 31, 35, 39 y 43 (de 66 a 310 vértices). El tiempo
mediano hasta encontrar el ciclo fue 0.8 s y el máximo 23 s.

El método tiene un límite claro alrededor de 300–400 vértices. Por debajo, casi todos los grafos no resueltos
quedan en f = 1: el algoritmo encuentra un camino hamiltoniano y no logra cerrarlo, y más semillas ya no lo
cambian. Por encima de 400 vértices no se acerca: el f mediano crece de 15 a 82. Los 663 grafos de más de
2000 vértices no se intentaron. Resolver más grafos requiere un método distinto (búsqueda exacta con
retroceso y reglas de aristas forzadas, o reducir al TSP y usar LKH/Concorde, como los participantes del
reto), no más tiempo de la misma metaheurística.

---

## 6. Benchmarking contra el FHCP Challenge

### 6.1 Resultados oficiales del reto

| Equipo | Grafos resueltos (de 1001) |
|---|---|
| N. Cohen y D. Coudert (INRIA, Francia), ganadores | **985** |
| Johnson (IBM, Reino Unido) | 614 |
| Gharbi y Syarif (King Saud University) | 488 |
| Noisternig (TU Darmstadt) | 464 |
| Nurhafiz (independiente) | 385 |

Fuente: Haythorpe (2018) y la página oficial del FHCP. Ningún equipo resolvió los 1001. Los 16 grafos que
quedaron sin resolver son instancias derivadas de grafos de Stedman (Sted4, Sted5, Sted6 y 13 combinaciones
que los contienen). Los ganadores descompusieron las instancias, buscaron estructuras repetidas entre
ellas y reutilizaron soluciones de subgrafos. En la construcción del set se usaron como referencia
resolvedores especializados del TSP/HCP: Concorde (exacto, *branch-and-cut*) y LKH (heurística de
Lin-Kernighan-Helsgaun).

### 6.2 Contraste con este proyecto

| Aspecto | Mejores del FHCP | Este proyecto |
|---|---|---|
| Instancias resueltas | 985/1001 (ganadores); 385–614 (resto de los equipos) | 1 de 6 en la comparativa (graph1); **16** de 338 en la corrida masiva (§5.8) |
| Tamaño máximo atacado | hasta 9528 vértices | 3468 vértices |
| Mejor resultado parcial | n/a (solo cuentan ciclos completos) | Camino hamiltoniano (f = 1) en graph24 y graph41; f = 4 en graph172 |
| Técnicas | Descomposición estructural, reducción al TSP, Concorde/LKH, búsqueda local profunda, días de cómputo | Metaheurísticas genéricas, 15–60 s por corrida, Python puro |

**Análisis.**

1. **Brecha de calidad.** Con la métrica oficial (instancias con ciclo válido), las metaheurísticas genéricas
   quedan muy lejos de los resolvedores especializados. Incluso graph1, el grafo más fácil del set, solo se
   resolvió con búsqueda local dirigida (2-opt + rotaciones de Pósa). Es justo el tipo de componente que
   tienen LKH y los resolvedores ganadores.
2. **"Casi" no cuenta.** En graph24 y graph41 los mejores algoritmos encuentran caminos hamiltonianos
   (99.5–99.7 % de aristas correctas) pero no logran cerrar el ciclo. Las instancias del FHCP están
   **diseñadas para ese engaño**: tienen muchos caminos hamiltonianos casi correctos y muy pocos ciclos. Una
   heurística que solo mide aristas faltantes ve una meseta enorme en f = 1.
3. **Estructura.** Los grafos pequeños del set son cúbicos (grado 3) y sin vértices de grado 2, así que el
   preprocesamiento de aristas forzadas no cambia nada en ellos. Por eso aco_ls y aco_ls_pre dan resultados
   idénticos en graph1/24/41. En graph172 y graph300 fija 672 y 1211 aristas, pero el efecto no es
   significativo (p_Holm = 0.30 en graph172; en la ronda pesada el mejor f baja de 5 a 4, aunque la mediana
   sube de 6.5 a 7.5). Los ganadores explotaron esta clase de estructura a gran escala.
4. **Escala.** El costo de la búsqueda local en Python limita a ACO + 2-opt en n ≥ 1000. Una implementación
   en C/C++ (como LKH) haría 100–1000 veces más trabajo en el mismo tiempo.

---

## 7. Conclusiones

1. **ACO fue la metaheurística que mejor se adaptó a los cuellos de botella de los grafos difíciles.**
   Construye las rutas **sobre aristas reales** con la regla de Warnsdorff, así que nunca propone
   aristas inexistentes salvo en callejones sin salida, y la feromona aprende qué aristas conectan los
   nodos difíciles. Sola, llega a f = 1 en graph1/24/41. Con búsqueda local 2-opt + Pósa, **resuelve graph1
   en 10/10 corridas en medio segundo** y queda primera en el ranking de Friedman (p = 0.0001).
2. **SA es la segunda mejor opción si se usa el vecindario adecuado.** SA con swap, como lo pide el
   enunciado, cambia 4 aristas por movimiento y se estanca. SA con 2-opt cambia solo 2: reduce el fitness
   mediano entre 2.7 y 10.5 veces en n ≤ 300 (7 % en graph172) y con 60 s resolvió graph1 en 5/10 corridas.
   La representación y el vecindario pesan más que el esquema de enfriamiento: cambiar la temperatura de SA
   (swap) movió el fitness ≈10 % (sección 4.3), mientras que cambiar el vecindario lo movió hasta 10 veces.
3. **GA y Bee Colony** mejoran claramente a la búsqueda aleatoria, pero se degradan rápido con n. La cruza
   OX conserva el orden pero rompe aristas. La recombinación de aristas (GA-ER) es mejor por evaluación,
   pero cuesta 7 veces más y con tope de tiempo quedó peor.
4. **DE y PSO con claves aleatorias no son adecuados para este problema.** El mapeo continuo → permutación
   (SPV) destruye la localidad: un cambio pequeño en las claves reordena muchos vértices. Por eso su
   fitness queda cerca de la búsqueda aleatoria, sobre todo en n = 1002.
5. **Lección central.** Ante grafos "engañosos", lo que funcionó fue **explotar la estructura del grafo**:
   construir solo sobre aristas reales, búsqueda local dirigida a las aristas faltantes, movimientos neutros
   para cruzar mesetas y aristas forzadas. Ajustar más los parámetros de un algoritmo ciego a la estructura
   no habría dado ese resultado. Es la misma conclusión que se desprende de los resultados del reto oficial.

**Trabajo futuro:** usar un fitness que distinga caminos según qué tan cerca estén sus extremos de cerrarse;
añadir movimientos 3-opt / Or-opt; reiniciar la búsqueda desde varios extremos con rotaciones de Pósa;
reimplementar el núcleo en C/Numba; y, para pasar de los 16 grafos resueltos en la corrida masiva (§5.8),
combinar la metaheurística con búsqueda exacta con retroceso o con una reducción al TSP.

---

## 8. Reproducibilidad

```bash
pip install -r requirements.txt
python -m pytest                          # 48 pruebas pasan, 1 omitida
# Extraer data/FHCPCS.7z en data/instances/

# Resolver una instancia (devuelve el arreglo de vértices y guarda el .tour si es válido)
python -m experiments.resolver --instance data/instances/graph1.hcp --algorithm aco_ls --time-limit 30

# Benchmark principal y análisis (tablas, pruebas, métricas F1 y figuras)
python -m experiments.benchmark --instances data/instances/graph1.hcp data/instances/graph24.hcp \
    data/instances/graph41.hcp data/instances/graph172.hcp \
    --algorithms ga ga_er sa sa_2opt aco aco_ls aco_ls_pre bee de pso random_search \
    --seeds 10 --max-evals 100000 --time-limit 15 --out results/bench --tours results/tours
python -m experiments.tuning --out results/tuning.csv
python -m experiments.tuning --out results/tuning_sa.csv --algs sa --evals 100000 \
    --grid '{"t0": [0.1, 0.5, 1.0, 2.0, 3.0], "t_end": [0.01, 0.02, 0.05, 0.1]}'
python -m experiments.analisis --prefix results/bench  --out results/analisis
python -m experiments.analisis --prefix results/pesada --out results/analisis_pesada

# Corrida masiva (§5.8): ACO + 2-opt sobre los grafos de hasta 2000 vértices
python -m experiments.masivo --algorithm aco_ls --time-limit 4 --max-n 2000 --workers 11 --salida results/masivo/s0
```

Los ciclos hamiltonianos encontrados para graph1 (20 en `results/tours/` y 25 en `results/tours_pesada/`) están
en formato TOUR del FHCP. Los 16 de la corrida masiva están en `results/masivo/tours_resueltos/`, y el mejor
resultado de cada grafo en `results/masivo/resumen_por_grafo.csv`.

---

## 9. Verificación de requisitos de la práctica

| Requisito de `practica.pdf` | Dónde se cumple |
|---|---|
| F1: Teoría de grafos y ciclos hamiltonianos (longitud n) | §1.1 |
| F1: Representación del espacio de búsqueda sin estructuras ilegales | §1.2, §2.2 |
| F1: Decodificación, fitness y heurísticas | §1.3, §2.2 |
| F1: Métricas (costo, iteraciones, precisión, recall, F1) | §1.4, §5.2, §5.4 |
| F1: Estándares, formatos y criterios del FHCP | §1.5 |
| F2: Problema del ciclo hamiltoniano, NP-difícil, relación con TSP | §1.1 |
| F2: Dataset FHCP Challenge Set | §4.1 |
| F3: GA (base de control) | §3.1 |
| F3: SA con swaps y enfriamiento lento | §3.2 |
| F3: ACO y Bee Colony con feromonas | §3.3, §3.4 |
| F3: DE adaptada a permutaciones | §3.5 |
| F3: PSO | §3.6 |
| F4.1: Código que carga grafos FHCP y devuelve un arreglo de vértices | `src/`, `experiments/resolver.py`, §2.3 |
| F4.2: Definición algorítmica del grafo y fundamentación teórica | §1.1, §2.1 |
| F4.2: Mapeo de representación y función de fitness | §2.2 |
| F4.2: Comparativa (tasa de éxito y tiempo) en tablas y gráficos | §5 |
| F4.2: Benchmarking contra el FHCP Challenge | §6 |
| F4.2: Conclusiones sobre la metaheurística que mejor se adaptó | §7 |
| Evidencia de ejecución (capturas, tiempos y resultados) | §5.7 |
| Corrida masiva sobre el set: grafos resueltos | §5.8 |

---

## Referencias

- Auger, A. y Hansen, N. (2005). Performance evaluation of an advanced local search evolutionary algorithm. *IEEE CEC 2005*.
- Bean, J. C. (1994). Genetic algorithms and random keys for sequencing and optimization. *ORSA Journal on Computing*, 6(2).
- Croes, G. A. (1958). A method for solving traveling-salesman problems. *Operations Research*, 6(6).
- Dorigo, M. y Stützle, T. (2004). *Ant Colony Optimization*. MIT Press.
- Garey, M. R. y Johnson, D. S. (1979). *Computers and Intractability*. W. H. Freeman.
- Goldberg, D. E. (1989). *Genetic Algorithms in Search, Optimization and Machine Learning*. Addison-Wesley.
- Haythorpe, M. (2018). FHCP Challenge Set: The first set of structurally difficult instances of the Hamiltonian cycle problem. *Bulletin of the ICA*, 83. arXiv:1902.10352.
- Helsgaun, K. (2000). An effective implementation of the Lin-Kernighan traveling salesman heuristic. *European Journal of Operational Research*, 126(1).
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2).
- Karaboga, D. y Basturk, B. (2007). A powerful and efficient algorithm for numerical function optimization: artificial bee colony (ABC) algorithm. *Journal of Global Optimization*, 39(3).
- Karp, R. M. (1972). Reducibility among combinatorial problems. En *Complexity of Computer Computations*. Plenum.
- Kennedy, J. y Eberhart, R. (1995). Particle swarm optimization. *Proc. IEEE ICNN*.
- Kirkpatrick, S., Gelatt, C. D. y Vecchi, M. P. (1983). Optimization by simulated annealing. *Science*, 220(4598).
- Pósa, L. (1976). Hamiltonian circuits in random graphs. *Discrete Mathematics*, 14(4).
- Storn, R. y Price, K. (1997). Differential evolution – a simple and efficient heuristic for global optimization over continuous spaces. *Journal of Global Optimization*, 11(4).
- Stützle, T. y Hoos, H. H. (2000). MAX-MIN Ant System. *Future Generation Computer Systems*, 16(8).
- Tasgetiren, M. F., Liang, Y.-C., Sevkli, M. y Gencyilmaz, G. (2007). A particle swarm optimization algorithm for makespan and total flowtime minimization in the permutation flowshop sequencing problem. *European Journal of Operational Research*, 177(3).
- Whitley, D., Starkweather, T. y Fuquay, D. (1989). Scheduling problems and traveling salesmen: the genetic edge recombination operator. *Proc. 3rd ICGA*.
- Flinders Hamiltonian Cycle Project – FHCP Challenge Set: https://sites.flinders.edu.au/flinders-hamiltonian-cycle-project/fhcp-challenge-set/
