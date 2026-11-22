[↩ Volver a la Unidad 3](../README.md)


# Dataset con web crawler

Crawler en Python que construye un dataset de animes a partir de AnimeFLV. Parte de la ficha de un anime, sigue los títulos relacionados y las páginas de listado por género, y guarda de cada anime el título, la descripción, los géneros y la URL.

- Respeta `robots.txt`, se limita al dominio de la URL inicial y usa un `User-Agent` identificado.
- Trabaja con varios hilos, con retraso aleatorio entre peticiones y reintentos.
- Registra el avance en un archivo de log.

| Archivo | Contenido |
| --- | --- |
| [crawler.py](crawler.py) | Crawler. Los selectores CSS están al inicio del archivo por si el sitio cambia su HTML. |
| [HUGO_GUILLERMO_DE_LEON_RUIZ.csv](HUGO_GUILLERMO_DE_LEON_RUIZ.csv) | Dataset final: 600 animes con `titulo, descripcion, generos, url`. |
| [crawler.log](crawler.log) | Log de la ejecución que generó el dataset. |

## Ejecutar

```bash
pip install requests beautifulsoup4
python crawler.py https://animeflv.lu/anime/one-piece -o animes.csv -n 600
```

Opciones útiles: `-w` (hilos), `--delay` y `--jitter` (espera entre peticiones), `--log-file`.
