"""Interfaz gráfica (tkinter) para resolver un grafo del FHCP con cualquiera de las metaheurísticas.

Uso (desde la carpeta raíz del proyecto):
  python -m experiments.interfaz

Permite elegir la instancia (.hcp), el algoritmo, la semilla, el presupuesto y parámetros extra; ejecuta la
búsqueda en segundo plano y muestra:
  - el resultado (aristas faltantes, si es ciclo hamiltoniano válido, tiempo y evaluaciones),
  - la curva de convergencia (mejor fitness contra evaluaciones),
  - el ciclo propuesto dibujado en círculo (verde = arista del grafo, rojo = arista que falta),
  - el arreglo de vértices (etiquetas 1..n del archivo), que se puede guardar como TOUR del FHCP.
"""
import glob
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from src.core import Config, read_hcp, validate, write_tour
from src.algorithms import REGISTRY

NOMBRES = {
    "aco_ls": "ACO + 2-opt",
    "aco_ls_pre": "ACO + 2-opt + preprocesamiento",
    "aco": "Colonia de Hormigas (ACO)",
    "sa": "Recocido Simulado (SA, swap)",
    "sa_2opt": "Recocido Simulado (SA, 2-opt)",
    "ga": "Algoritmo Genético (GA)",
    "ga_er": "GA con recombinación de aristas",
    "bee": "Colonia de Abejas (ABC)",
    "de": "Evolución Diferencial (DE)",
    "pso": "Enjambre de Partículas (PSO)",
    "random_search": "Búsqueda aleatoria (línea base)",
}
CARPETAS = ["data/test_instances", "data/instances"]
MAX_ARISTAS_DIBUJO = 20_000      # por encima de esto no se dibujan las aristas del grafo (solo el ciclo)


def _valor(texto):
    texto = texto.strip()
    if texto.lower() in ("true", "false"):
        return texto.lower() == "true"
    for tipo in (int, float):
        try:
            return tipo(texto)
        except ValueError:
            pass
    return texto


def _leer_params(texto):
    """'t0=2, t_end=0.01' -> {'t0': 2, 't_end': 0.01}"""
    params = {}
    for parte in texto.replace(";", ",").split(","):
        if parte.strip():
            if "=" not in parte:
                raise ValueError(f"parámetro sin '=': {parte.strip()}")
            k, v = parte.split("=", 1)
            params[k.strip()] = _valor(v)
    return params


class Interfaz(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ciclo Hamiltoniano – Metaheurísticas sobre el FHCP Challenge Set")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self.instancia = None          # grafo cargado
        self.ruta_instancia = None
        self.resultado = None          # (Result, validación, algoritmo, semilla)
        self.hilo = None
        self._t_inicio = 0.0
        self._construir()
        self._buscar_instancias()

    # ------------------------------------------------------------------ construcción de la ventana
    def _construir(self):
        estilo = ttk.Style(self)
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("Titulo.TLabel", font=("TkDefaultFont", 11, "bold"))
        estilo.configure("Exito.TLabel", foreground="#1b7f3b", font=("TkDefaultFont", 12, "bold"))
        estilo.configure("Fallo.TLabel", foreground="#b3261e", font=("TkDefaultFont", 12, "bold"))

        izq = ttk.Frame(self, padding=10)
        izq.pack(side="left", fill="y")
        der = ttk.Frame(self, padding=(0, 10, 10, 10))
        der.pack(side="left", fill="both", expand=True)

        # --- instancia
        ttk.Label(izq, text="1. Instancia", style="Titulo.TLabel").pack(anchor="w")
        fila = ttk.Frame(izq)
        fila.pack(fill="x", pady=(2, 0))
        self.cb_inst = ttk.Combobox(fila, state="readonly", width=30)
        self.cb_inst.pack(side="left", fill="x", expand=True)
        self.cb_inst.bind("<<ComboboxSelected>>", lambda e: self._cargar(self._rutas[self.cb_inst.current()]))
        ttk.Button(fila, text="Abrir…", command=self._abrir).pack(side="left", padx=(4, 0))
        self.lbl_inst = ttk.Label(izq, text="Ningún grafo cargado", foreground="#555", wraplength=300)
        self.lbl_inst.pack(anchor="w", pady=(2, 10))

        # --- algoritmo
        ttk.Label(izq, text="2. Algoritmo", style="Titulo.TLabel").pack(anchor="w")
        self._claves = [k for k in NOMBRES if k in REGISTRY] + sorted(set(REGISTRY) - set(NOMBRES))
        self.cb_alg = ttk.Combobox(izq, state="readonly", width=38,
                                   values=[NOMBRES.get(k, k) for k in self._claves])
        self.cb_alg.current(0)
        self.cb_alg.pack(fill="x", pady=(2, 10))

        # --- presupuesto
        ttk.Label(izq, text="3. Presupuesto y semilla", style="Titulo.TLabel").pack(anchor="w")
        rej = ttk.Frame(izq)
        rej.pack(fill="x", pady=(2, 0))
        self.v_semilla = tk.StringVar(value="0")
        self.v_evals = tk.StringVar(value="100000")
        self.v_tiempo = tk.StringVar(value="15")
        self.v_params = tk.StringVar(value="")
        for i, (txt, var) in enumerate([("Semilla", self.v_semilla), ("Máx. evaluaciones", self.v_evals),
                                        ("Tiempo límite (s)", self.v_tiempo)]):
            ttk.Label(rej, text=txt).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(rej, textvariable=var, width=12).grid(row=i, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(izq, text="Parámetros extra (opcional), p. ej. t0=2, t_end=0.01",
                  foreground="#555", wraplength=300).pack(anchor="w", pady=(6, 0))
        ttk.Entry(izq, textvariable=self.v_params).pack(fill="x", pady=(2, 10))

        # --- ejecutar
        self.btn_ejecutar = ttk.Button(izq, text="▶  Ejecutar", command=self._ejecutar)
        self.btn_ejecutar.pack(fill="x", ipady=4)
        self.barra = ttk.Progressbar(izq, mode="indeterminate")
        self.barra.pack(fill="x", pady=(6, 0))
        self.lbl_estado = ttk.Label(izq, text="Listo", foreground="#555")
        self.lbl_estado.pack(anchor="w", pady=(2, 10))

        # --- resultado
        ttk.Label(izq, text="Resultado", style="Titulo.TLabel").pack(anchor="w")
        self.lbl_veredicto = ttk.Label(izq, text="—")
        self.lbl_veredicto.pack(anchor="w", pady=(2, 0))
        self.lbl_detalle = ttk.Label(izq, text="", justify="left")
        self.lbl_detalle.pack(anchor="w", pady=(2, 6))
        self.btn_tour = ttk.Button(izq, text="Guardar ciclo como .tour", command=self._guardar_tour,
                                   state="disabled")
        self.btn_tour.pack(fill="x")

        ttk.Label(izq, text="Arreglo de vértices (1..n)", style="Titulo.TLabel").pack(anchor="w", pady=(10, 0))
        self.txt_ruta = ScrolledText(izq, width=40, height=8, wrap="word", font=("TkFixedFont", 9))
        self.txt_ruta.pack(fill="both", expand=True, pady=(2, 0))
        self.txt_ruta.configure(state="disabled")

        # --- gráficas
        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.ax_ciclo = self.fig.add_subplot(1, 2, 1)
        self.ax_conv = self.fig.add_subplot(1, 2, 2)
        self.fig.subplots_adjust(left=0.03, right=0.97, wspace=0.25)
        self.canvas = FigureCanvasTkAgg(self.fig, master=der)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._limpiar_graficas()

    # ------------------------------------------------------------------ instancias
    def _buscar_instancias(self):
        rutas = []
        for c in CARPETAS:
            rutas += glob.glob(os.path.join(c, "*.hcp"))
        rutas = sorted(set(rutas), key=lambda p: (os.path.basename(p) != "graph1.hcp", os.path.basename(p)))
        self._rutas = rutas
        self.cb_inst["values"] = [f"{os.path.basename(p)}  ({os.path.dirname(p)})" for p in rutas]
        if rutas:
            self.cb_inst.current(0)
            self._cargar(rutas[0])

    def _abrir(self):
        ruta = filedialog.askopenfilename(title="Abrir grafo del FHCP",
                                          filetypes=[("Grafos HCP", "*.hcp"), ("Todos", "*.*")])
        if ruta:
            if ruta not in self._rutas:
                self._rutas.append(ruta)
                self.cb_inst["values"] = list(self.cb_inst["values"]) + [os.path.basename(ruta)]
            self.cb_inst.current(self._rutas.index(ruta))
            self._cargar(ruta)

    def _cargar(self, ruta):
        try:
            g = read_hcp(ruta)
        except Exception as e:                       # archivo con formato incorrecto
            messagebox.showerror("No se pudo leer el grafo", str(e))
            return
        self.instancia, self.ruta_instancia, self.resultado = g, ruta, None
        grados = [len(a) for a in g.adj]
        self.lbl_inst.configure(text=f"{g.name}: n = {g.n} vértices, m = {g.m} aristas, "
                                     f"grado {min(grados)}–{max(grados)}")
        self.lbl_veredicto.configure(text="—", style="TLabel")
        self.lbl_detalle.configure(text="")
        self.btn_tour.configure(state="disabled")
        self._poner_ruta("")
        self._limpiar_graficas()

    # ------------------------------------------------------------------ ejecución
    def _ejecutar(self):
        if self.instancia is None:
            messagebox.showwarning("Falta el grafo", "Primero elige o abre un archivo .hcp")
            return
        try:
            campo = "Semilla"
            semilla = int(self.v_semilla.get())
            campo = "Máx. evaluaciones"
            evals = int(float(self.v_evals.get()))
            if evals <= 0:
                raise ValueError("debe ser un número positivo")
            campo = "Tiempo límite"
            tiempo = float(self.v_tiempo.get())
            if tiempo <= 0:
                raise ValueError("debe ser un número positivo")
            campo = "Parámetros extra"
            params = _leer_params(self.v_params.get())
        except ValueError as e:
            detalle = str(e) if campo == "Parámetros extra" or "positivo" in str(e) else "no es un número válido"
            messagebox.showerror("Datos inválidos", f"{campo}: {detalle}")
            return
        alg = self._claves[self.cb_alg.current()]
        self.btn_ejecutar.configure(state="disabled")
        self.btn_tour.configure(state="disabled")
        self.barra.start(12)
        self._t_inicio = time.perf_counter()
        self._tic(alg)
        g = self.instancia

        def trabajo():
            try:
                r = REGISTRY[alg](g, Config(evals, tiempo, params), semilla)
                v = validate(g, r.best_route)
                self.after(0, self._terminado, g, (r, v, alg, semilla), None)
            except Exception as e:                 # p. ej. parámetro desconocido o n demasiado pequeño
                self.after(0, self._terminado, g, None, e)

        self.hilo = threading.Thread(target=trabajo, daemon=True)
        self.hilo.start()

    def _tic(self, alg):
        if self.hilo is not None and not self.hilo.is_alive():
            return
        t = time.perf_counter() - self._t_inicio
        self.lbl_estado.configure(text=f"Ejecutando {NOMBRES.get(alg, alg)}… {t:.1f} s")
        self.after(200, self._tic, alg)

    def _terminado(self, g, resultado, error):
        self.barra.stop()
        self.btn_ejecutar.configure(state="normal")
        if error is not None:
            self.lbl_estado.configure(text="Error")
            messagebox.showerror("Error al ejecutar", f"{type(error).__name__}: {error}")
            return
        if g is not self.instancia:                 # el usuario cambió de grafo mientras corría
            self.lbl_estado.configure(text="Listo (resultado descartado: se cambió de grafo)")
            return
        self.resultado = resultado
        r, v, alg, semilla = resultado
        ok = v["es_hamiltoniano"]
        self.lbl_estado.configure(text="Listo")
        if ok:
            self.lbl_veredicto.configure(text="✔ Ciclo hamiltoniano válido", style="Exito.TLabel")
        else:
            self.lbl_veredicto.configure(text=f"✘ No es ciclo: faltan {r.best_fitness} aristas",
                                         style="Fallo.TLabel")
        legal = 1 - r.best_fitness / g.n
        self.lbl_detalle.configure(text=f"Algoritmo: {NOMBRES.get(alg, alg)} (semilla {semilla})\n"
                                        f"Aristas faltantes: {r.best_fitness} de {g.n}  "
                                        f"(legalidad {legal:.3f})\n"
                                        f"Tiempo: {r.time:.2f} s   Evaluaciones: {r.iterations:,}")
        self.btn_tour.configure(state="normal" if ok else "disabled")
        self._poner_ruta(", ".join(str(x + 1) for x in r.best_route) + f"  → {r.best_route[0] + 1}")
        self._dibujar(g, r)

    # ------------------------------------------------------------------ salida
    def _poner_ruta(self, texto):
        self.txt_ruta.configure(state="normal")
        self.txt_ruta.delete("1.0", "end")
        self.txt_ruta.insert("1.0", texto)
        self.txt_ruta.configure(state="disabled")

    def _guardar_tour(self):
        if not self.resultado:
            return
        r, v, alg, semilla = self.resultado
        nombre = os.path.splitext(os.path.basename(self.ruta_instancia))[0]
        ruta = filedialog.asksaveasfilename(title="Guardar ciclo (formato TOUR del FHCP)",
                                            initialdir=os.path.join("results", "tours"),
                                            initialfile=f"{alg}_{nombre}_s{semilla}.tour",
                                            defaultextension=".tour", filetypes=[("TOUR", "*.tour")])
        if ruta:
            os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
            write_tour(ruta, r.best_route, name=f"{alg} {nombre}")
            self.lbl_estado.configure(text=f"Tour guardado en {ruta}")

    # ------------------------------------------------------------------ gráficas
    def _limpiar_graficas(self):
        for ax in (self.ax_ciclo, self.ax_conv):
            ax.clear()
        self.ax_ciclo.set_title("Ciclo propuesto")
        self.ax_ciclo.set_axis_off()
        self.ax_ciclo.text(0.5, 0.5, "Ejecuta un algoritmo\npara ver el ciclo", ha="center", va="center",
                           color="#888", transform=self.ax_ciclo.transAxes)
        self.ax_conv.set_title("Convergencia")
        self.ax_conv.set_xlabel("Evaluaciones")
        self.ax_conv.set_ylabel("Aristas faltantes (mejor)")
        self.ax_conv.grid(alpha=0.3)
        self.canvas.draw_idle()

    def _dibujar(self, g, r):
        ruta, n = r.best_route, g.n
        ang = 2 * np.pi * np.arange(n) / n                 # vértices en círculo, en el orden del ciclo
        xy = np.zeros((n, 2))
        xy[ruta, 0], xy[ruta, 1] = np.cos(ang), np.sin(ang)

        ax = self.ax_ciclo
        ax.clear()
        ax.set_aspect("equal")
        ax.set_axis_off()
        if g.m <= MAX_ARISTAS_DIBUJO:                       # resto de aristas del grafo, en gris
            otras = [(xy[u], xy[w]) for u in range(n) for w in g.adj[u] if u < w]
            ax.add_collection(LineCollection(otras, colors="#c8c8c8", linewidths=0.4,
                                             alpha=1.0 if n <= 300 else 0.5, zorder=1))
        buenas, malas, marcas = [], [], []
        for i in range(n):
            u, w = ruta[i], ruta[(i + 1) % n]
            if w in g.adj[u]:
                buenas.append((xy[u], xy[w]))
            else:
                malas.append((xy[u], xy[w]))
                m = (xy[u] + xy[w]) / np.linalg.norm(xy[u] + xy[w])   # punto medio, sobre el círculo
                marcas.append((m * 1.04, m * 1.16))                    # rayita roja por fuera
        ax.scatter(xy[:, 0], xy[:, 1], s=14 if n <= 100 else (5 if n <= 300 else 1), c="#333", zorder=2)
        ax.add_collection(LineCollection(buenas, colors="#1b7f3b", linewidths=2.5 if n <= 300 else 1.5, zorder=3))
        if malas:
            ax.add_collection(LineCollection(malas, colors="#d62728", linewidths=4.0, zorder=4))
            ax.add_collection(LineCollection(marcas, colors="#d62728", linewidths=1.2, zorder=4))
        if n <= 80:
            for v in range(n):
                ax.annotate(str(v + 1), xy[v] * 1.08, ha="center", va="center", fontsize=6, color="#444")
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.2, 1.2)
        ax.set_title(f"Ciclo propuesto: {len(buenas)} aristas del grafo (verde)\n"
                     f"{len(malas)} aristas que no existen (rojo, marcadas por fuera)", fontsize=9)

        ax = self.ax_conv
        ax.clear()
        if r.history:
            it = [max(1, h[0]) for h in r.history] + [max(1, r.iterations)]
            fit = [h[1] for h in r.history] + [r.history[-1][1]]
            ax.step(it, fit, where="post", color="#1f5fa8", linewidth=1.8)
            ax.set_xscale("log")
        ax.set_title("Convergencia", fontsize=10)
        ax.set_xlabel("Evaluaciones (escala log)")
        ax.set_ylabel("Aristas faltantes (mejor)")
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)
        self.canvas.draw_idle()


def main():
    Interfaz().mainloop()


if __name__ == "__main__":
    main()
