# Instancias

## Origen y verificación
- `envelope6.hcp`: ejemplo oficial de 6 vértices de la página del FHCP (3 ciclos hamiltonianos conocidos).
- `graph1, graph2, graph3` (depuración, n=66/70/78) y `graph24, graph41, graph172` (n=198/300/1002):
  tomados de una **copia pública** del FHCP Challenge Set en GitHub (repositorio cgungor/ham-path,
  carpeta FHCPCS), no del sitio oficial de Flinders.
- Comprobaciones hechas: la copia tiene 1001 grafos, n entre 66 y 9528 y media de ~3098 vértices, que
  coincide con lo que publica Flinders; los 1001 cargan sin errores; encabezado
  "FHCP Challenge Set. http://fhcp.edu.au/fhcpcs".
- **Pendiente:** compararlos con los archivos oficiales (FHCPCS.7z) si logras descargarlos
  (comparar `sha256` del catálogo contra el de los archivos oficiales). Mientras tanto, declarar en el
  informe que la fuente fue una copia pública.
- `ejemplo6.hcp` es un grafo propio de prueba, no es del FHCP.

## Catálogo
`data/catalogo_fhcp.csv` lista las 1001 instancias (archivo, n, m, grado mín/máx, sha256).
Se regenera con: `python -m experiments.catalogo CARPETA_CON_HCP salida.csv`
