"""Análisis del benchmark: tablas, pruebas estadísticas y figuras para el informe.

Uso: python -m experiments.analisis --prefix results/bench --out results/analisis
"""
import argparse, json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

ORDEN = ["aco_ls_pre", "aco_ls", "aco", "ga_er", "ga", "sa_2opt", "sa", "bee", "de", "pso", "random_search"]
NOMBRES = {"ga": "GA", "sa": "SA (swap)", "sa_2opt": "SA (2-opt)", "aco": "ACO", "bee": "Bee Colony",
           "de": "DE", "pso": "PSO", "random_search": "Aleatoria",
           "ga_er": "GA (ER)", "aco_ls": "ACO + 2-opt", "aco_ls_pre": "ACO + 2-opt + prepro."}
COLORES = {"ga": "#1f77b4", "sa": "#d62728", "sa_2opt": "#ff9896", "aco": "#2ca02c", "bee": "#ff7f0e",
           "de": "#9467bd", "pso": "#8c564b", "random_search": "#7f7f7f",
            "ga_er": "#aec7e8", "aco_ls": "#98df8a", "aco_ls_pre": "#006400"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def holm(pvals):
    idx = np.argsort(pvals)
    m = len(pvals)
    aj = np.empty(m)
    previo = 0.0
    for r, i in enumerate(idx):
        previo = max(previo, min(1.0, (m - r) * pvals[i]))
        aj[i] = previo
    return aj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    df = pd.read_csv(a.prefix + "_runs.csv")
    algs = [x for x in ORDEN if x in set(df.algoritmo)]
    insts = sorted(df.instancia.unique(), key=lambda s: int(df[df.instancia == s].n.iloc[0]))
    n_de = {i: int(df[df.instancia == i].n.iloc[0]) for i in insts}
    m_de = {i: int(df[df.instancia == i].m.iloc[0]) for i in insts}

    # ---- Tabla 1: resumen por instancia y algoritmo
    filas = []
    for i in insts:
        for al in algs:
            d = df[(df.instancia == i) & (df.algoritmo == al)]
            if d.empty:
                continue
            k, N = int(d.exito.sum()), len(d)
            lo, hi = wilson(k, N)
            ert = d.evaluaciones.sum() / k if k else np.nan      # tiempo esperado hasta solución (en evaluaciones)
            filas.append({"instancia": i, "n": n_de[i], "m": m_de[i], "algoritmo": NOMBRES[al], "corridas": N,
                          "exitos": k, "tasa_exito": k / N, "IC95_inf": lo, "IC95_sup": hi,
                          "fitness_mejor": int(d.fitness.min()), "fitness_mediana": float(d.fitness.median()),
                          "fitness_media": float(d.fitness.mean()), "fitness_desv": float(d.fitness.std(ddof=1)) if N > 1 else 0.0,
                          "legalidad_media": float(d.legalidad.mean()),
                          "tiempo_medio_s": float(d.tiempo_s.mean()), "evals_medias": float(d.evaluaciones.mean()),
                          "ERT_evals": ert, "validado": int(d.valido_independiente.sum() == d.exito.sum())})
    t1 = pd.DataFrame(filas)
    t1.to_csv(os.path.join(a.out, "tabla_resumen.csv"), index=False)

    # ---- Pruebas: Kruskal-Wallis por instancia y Mann-Whitney vs el mejor (Holm)
    pruebas = []
    for i in insts:
        d = df[df.instancia == i]
        grupos = [d[d.algoritmo == al].fitness.values for al in algs if al != "random_search"]
        try:
            kw = stats.kruskal(*grupos)
            kwp = kw.pvalue
        except ValueError:
            kwp = np.nan
        med = {al: d[d.algoritmo == al].fitness.median() for al in algs if al != "random_search"}
        mejor = min(med, key=med.get)
        ps, otros = [], []
        for al in med:
            if al == mejor:
                continue
            u = stats.mannwhitneyu(d[d.algoritmo == mejor].fitness, d[d.algoritmo == al].fitness, alternative="less")
            ps.append(u.pvalue)
            otros.append(al)
        aj = holm(np.array(ps)) if ps else []
        for al, p, pa in zip(otros, ps, aj):
            pruebas.append({"instancia": i, "kruskal_p": kwp, "mejor": NOMBRES[mejor], "comparado_con": NOMBRES[al],
                            "p_MW": p, "p_Holm": pa, "significativo_5%": bool(pa < 0.05)})
    t2 = pd.DataFrame(pruebas)
    t2.to_csv(os.path.join(a.out, "pruebas_estadisticas.csv"), index=False)

    # ---- Rangos medios entre instancias + Friedman
    pr = df[df.algoritmo != "random_search"].groupby(["instancia", "algoritmo"]).fitness.mean().unstack()
    pr = pr[[x for x in algs if x in pr.columns]]
    rangos = pr.rank(axis=1)
    rm = rangos.mean().rename(index=NOMBRES)
    fr = stats.friedmanchisquare(*[pr[c].values for c in pr.columns]) if len(pr) >= 3 and pr.shape[1] >= 3 else None
    with open(os.path.join(a.out, "rangos_friedman.txt"), "w", encoding="utf-8") as f:
        f.write("Rango medio por algoritmo (1 = mejor fitness medio; sobre las instancias):\n")
        f.write(rm.sort_values().round(2).to_string() + "\n")
        if fr:
            f.write(f"\nFriedman: chi2={fr.statistic:.3f}, p={fr.pvalue:.4f} (bloques = {len(pr)} instancias)\n")

    # ---- Instancias resueltas (métrica oficial del reto): al menos una corrida exitosa
    res = df.groupby(["algoritmo", "instancia"]).exito.max().unstack().reindex(algs)
    res.index = [NOMBRES[x] for x in res.index]
    res["instancias_resueltas"] = res.sum(axis=1)
    res.to_csv(os.path.join(a.out, "instancias_resueltas.csv"))

    # ---- Métricas de clasificación (precisión, recall, F1)
    # Por corrida: todas las instancias FHCP son hamiltonianas, así que cada corrida es un caso positivo.
    #   TP = la corrida reporta un ciclo y el validador independiente lo confirma; FP = reporta un ciclo que el
    #   validador rechaza; FN = no encontró ciclo. Recall = tasa de éxito.
    # Por arista: de las n aristas del ciclo propuesto, las que existen en el grafo son aciertos
    #   (precisión de aristas = legalidad = 1 - fitness/n).
    met = []
    for i in insts:
        for al in algs:
            d = df[(df.instancia == i) & (df.algoritmo == al)]
            if d.empty:
                continue
            tp = int(((d.exito == 1) & (d.valido_independiente == 1)).sum())
            fp = int(((d.exito == 1) & (d.valido_independiente == 0)).sum())
            fn = len(d) - tp - fp
            prec = tp / (tp + fp) if tp + fp else np.nan
            rec = tp / len(d)
            f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
            pa = float(d.legalidad.mean())
            met.append({"instancia": i, "algoritmo": NOMBRES[al], "TP": tp, "FP": fp, "FN": fn,
                        "precision": prec, "recall": rec, "F1": f1, "precision_aristas": pa})
    pd.DataFrame(met).to_csv(os.path.join(a.out, "metricas_clasificacion.csv"), index=False)

    # ---- Figuras
    x = np.arange(len(insts))
    prin = [al for al in algs if al != "random_search"]
    w = 0.8 / len(prin)
    fig, ax = plt.subplots(figsize=(9, 4))
    for j, al in enumerate(prin):
        tasas = [t1[(t1.instancia == i) & (t1.algoritmo == NOMBRES[al])].tasa_exito.iloc[0] for i in insts]
        ax.bar(x + j * w - 0.4 + w / 2, tasas, w, label=NOMBRES[al], color=COLORES[al])
    ax.set_xticks(x); ax.set_xticklabels([f"{i}\n(n={n_de[i]})" for i in insts])
    ax.set_ylabel("Tasa de éxito"); ax.set_ylim(0, 1.05); ax.legend(ncol=4, fontsize=8)
    ax.set_title("Tasa de éxito (ciclo hamiltoniano completo) por instancia")
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "fig_tasa_exito.png"), dpi=150); plt.close(fig)

    filas = (len(insts) + 1) // 2                     # rejilla de 2 columnas para que se lea en el informe
    fig, axs = plt.subplots(filas, 2, figsize=(11, 4.6 * filas), squeeze=False)
    for ax in axs.flat[len(insts):]:
        ax.set_visible(False)
    for ax, i in zip(axs.flat, insts):
        d = df[df.instancia == i]
        datos = [d[d.algoritmo == al].fitness.values for al in algs]
        bp = ax.boxplot(datos, patch_artist=True, tick_labels=[NOMBRES[al] for al in algs])
        for patch, al in zip(bp["boxes"], algs):
            patch.set_facecolor(COLORES[al])
        ax.set_title(f"{i} (n={n_de[i]})"); ax.set_ylabel("Aristas faltantes (menor es mejor)")
        ax.tick_params(axis="x", rotation=60, labelsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "fig_fitness_boxplot.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    for j, al in enumerate(prin):
        tm = [t1[(t1.instancia == i) & (t1.algoritmo == NOMBRES[al])].tiempo_medio_s.iloc[0] for i in insts]
        ax.bar(x + j * w - 0.4 + w / 2, tm, w, label=NOMBRES[al], color=COLORES[al])
    ax.set_yscale("log"); ax.set_xticks(x); ax.set_xticklabels([f"{i}\n(n={n_de[i]})" for i in insts])
    ax.set_ylabel("Tiempo medio por corrida (s, escala log)"); ax.legend(ncol=4, fontsize=8)
    ax.set_title("Tiempo computacional (mismo presupuesto de evaluaciones, con tope de tiempo)")
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "fig_tiempo.png"), dpi=150); plt.close(fig)

    # convergencia: mediana del mejor fitness vs evaluaciones
    hist = {}
    with open(a.prefix + "_hist.jsonl", encoding="utf-8") as f:
        for linea in f:
            r = json.loads(linea)
            hist[(r["algoritmo"], r["instancia"], r["semilla"])] = r["hist"]
    tope = int(df.max_evals.iloc[0])
    grilla = np.unique(np.geomspace(1, tope, 80).astype(int))
    fig, axs = plt.subplots(filas, 2, figsize=(11, 4.0 * filas + 0.8), squeeze=False)
    for ax in axs.flat[len(insts):]:
        ax.set_visible(False)
    for ax, i in zip(axs.flat, insts):
        for al in algs:
            curvas = []
            for s in sorted(df[(df.instancia == i) & (df.algoritmo == al)].semilla):
                h = hist.get((al, i, int(s)))
                if not h:
                    continue
                it = np.array([p[0] for p in h]); fv = np.array([p[1] for p in h])
                idx = np.searchsorted(it, grilla, side="right") - 1
                curvas.append(np.where(idx >= 0, fv[np.clip(idx, 0, None)], fv[0]))
            if curvas:
                ax.plot(grilla, np.median(np.array(curvas), axis=0), label=NOMBRES[al], color=COLORES[al],
                        ls="--" if al == "random_search" else "-")
        ax.set_xscale("log"); ax.set_title(f"{i} (n={n_de[i]})"); ax.set_xlabel("Evaluaciones de fitness")
        ax.set_ylabel("Mediana del mejor fitness")
    manejadores, etiquetas = axs[0][0].get_legend_handles_labels()
    fig.legend(manejadores, etiquetas, loc="lower center", ncol=6, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.8 / (4.0 * filas + 0.8), 1, 1))
    fig.savefig(os.path.join(a.out, "fig_convergencia.png"), dpi=150); plt.close(fig)
    print("Tablas y figuras en", a.out)
    print(t1[["instancia", "algoritmo", "exitos", "fitness_mejor", "fitness_mediana", "tiempo_medio_s"]].to_string(index=False))


if __name__ == "__main__":
    main()
