#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import csv
import heapq
import itertools
import logging
import random
import re
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from html import unescape
from urllib import robotparser
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuración (si el sitio cambia su HTML, ajusta los selectores aquí)

ALLOWED_DOMAIN = None  # se fija en Crawler.__init__ a partir de la URL inicial
DEFAULT_USER_AGENT = (
    "AnimeFLVStudentCrawler/1.0 "
    "(proyecto academico; contacto: tu-correo@ejemplo.com)"
)

SEL_TITLE = "h1.Title"
SEL_DESCRIPTION = "div.Description p"
SEL_GENRES = "nav.Nvgnrs a"
# Enlaces a títulos relacionados dentro de la ficha (prioridad alta)
SEL_RELATED = ["ul.ListAnmRel a[href]", "ul.ListSdbr a[href]"]
# Tarjetas de anime en páginas de listado (/browse?genre[]=...)
SEL_LISTING = "ul.ListAnimes a[href]"

ANIME_PATH_RE = re.compile(r"^/anime/[A-Za-z0-9\-_.]+$")
GENRE_HREF_RE = re.compile(r"genre(?:\[\]|%5B%5D)=([^&#]+)", re.I)

CSV_FIELDS = ["titulo", "descripcion", "generos", "url"]
REFILL_THRESHOLD = 30      # si la frontera tiene menos URLs, se pide otra página de listado
MAX_LISTING_PAGES = 60     # tope de páginas de listado por género

log = logging.getLogger("animeflv_crawler")


class ParseError(Exception):
    """La página no tiene la estructura esperada."""


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def in_domain(host):
    host = (host or "").lower()
    if not ALLOWED_DOMAIN:
        return False
    return host == ALLOWED_DOMAIN or host.endswith("." + ALLOWED_DOMAIN)


def normalize_anime_url(href, base, netloc):
    """Devuelve la URL canónica de un título o None si no es un /anime/<slug>
    dentro del dominio permitido. Elimina query, fragmento y '/' final."""
    parts = urlsplit(urljoin(base, href))
    if parts.scheme not in ("http", "https") or not in_domain(parts.hostname):
        return None
    path = parts.path.rstrip("/")
    if not ANIME_PATH_RE.match(path):
        return None
    return f"https://{netloc}{path}"


# --------------------------------------------------------------------------- #
# Crawler
# --------------------------------------------------------------------------- #
class Crawler:
    def __init__(self, args):
        global ALLOWED_DOMAIN
        self.args = args
        parts = urlsplit(args.url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or "." not in host:
            raise SystemExit("La URL inicial no es válida (debe empezar con https://).")
        # El rastreo queda limitado al dominio base de la URL inicial
        # (p. ej. www3.animeflv.net -> animeflv.net, animeflv.lu -> animeflv.lu)
        ALLOWED_DOMAIN = ".".join(host.split(".")[-2:])
        self.netloc = parts.netloc.lower()
        self.start_url = normalize_anime_url(args.url, args.url, self.netloc)
        if not self.start_url:
            raise SystemExit(
                "La URL inicial debe tener la forma https://<dominio>/anime/<nombre-del-anime>"
            )

        self._local = threading.local()      # una Session por hilo
        self._lock = threading.Lock()        # protege failed / blocked
        self._rate_lock = threading.Lock()   # limitador de ritmo global
        self._next_slot = 0.0

        self.robots = robotparser.RobotFileParser()
        self.delay = args.delay

        self.frontier = []                 # heap: (prioridad, contador, url)
        self._counter = itertools.count()
        self.queued = set()                # URLs que ya entraron a la frontera
        self.saved = set()                 # URLs guardadas en el CSV
        self.failed = {}                   # url -> motivo
        self.blocked = set()               # URLs omitidas por robots.txt
        self.consecutive_failures = 0

        self.current_genres = []           # géneros del último título guardado
        self.genre_pages = {}              # genero -> siguiente página de listado
        self.exhausted = set()             # géneros sin más páginas
        self.genre_failures = {}
        self.sitemap_done = False
        self.t0 = time.monotonic()

    # ------------------------------- sesiones ------------------------------- #
    def _session(self):
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": self.args.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
            })
            retry = Retry(
                total=3, connect=3, read=3, backoff_factor=2,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["GET"]),
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            self._local.session = s
        return s

    # ------------------------------ robots.txt ------------------------------ #
    def setup_robots(self):
        robots_url = f"https://{self.netloc}/robots.txt"
        try:
            resp = self._session().get(robots_url, timeout=self.args.timeout)
        except requests.RequestException as exc:
            raise SystemExit(
                f"No se pudo descargar robots.txt ({exc}). Por precaución no se rastrea."
            )
        if resp.status_code == 200:
            self.robots.parse(resp.text.splitlines())
            log.info("robots.txt cargado desde %s", robots_url)
        elif resp.status_code in (404, 410):
            self.robots.parse([])
            self.robots.allow_all = True
            log.info("El sitio no publica robots.txt (HTTP %s): sin restricciones.",
                     resp.status_code)
        else:
            raise SystemExit(
                f"robots.txt respondió HTTP {resp.status_code}; no se rastrea por precaución."
            )

        crawl_delay = self.robots.crawl_delay(self.args.user_agent)
        if crawl_delay:
            self.delay = max(self.delay, float(crawl_delay))
            log.info("Se respeta Crawl-delay=%s de robots.txt", crawl_delay)

    def allowed(self, url):
        return self.robots.can_fetch(self.args.user_agent, url)

    # ----------------------- ritmo global de peticiones --------------------- #
    def _wait(self):
        """Reserva un turno: dos peticiones nunca comienzan con menos de
        `delay` segundos de diferencia, sin importar cuántos hilos haya."""
        with self._rate_lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.delay + random.uniform(0, self.args.jitter)
        pause = slot - now
        if pause > 0:
            time.sleep(pause)

    def _penalize(self, seconds):
        """Pausa global (todos los hilos) si el sitio responde 429/503."""
        with self._rate_lock:
            self._next_slot = max(self._next_slot, time.monotonic() + seconds)
        log.warning("El sitio pidió reducir el ritmo: pausa global de %ss", seconds)

    def _record_failure(self, url, reason):
        with self._lock:
            self.failed[url] = reason

    # -------------------------------- red ---------------------------------- #
    def fetch(self, url, expect_html=True):
        """Descarga una URL. Devuelve el HTML o None (registrando el motivo)."""
        if not self.allowed(url):
            with self._lock:
                self.blocked.add(url)
            log.warning("Omitida por robots.txt: %s", url)
            return None
        self._wait()
        try:
            resp = self._session().get(url, timeout=self.args.timeout)
            resp.raise_for_status()
            if not in_domain(urlsplit(resp.url).hostname):
                raise requests.RequestException(
                    f"redirección fuera del dominio: {resp.url}")
            if expect_html and "html" not in resp.headers.get("Content-Type", "").lower():
                raise requests.RequestException("la respuesta no es HTML")
            resp.encoding = "utf-8"
            return resp.text
        except requests.RequestException as exc:
            self._record_failure(url, str(exc))
            log.error("Fallo de red en %s: %s", url, exc)
            if "429" in str(exc) or "503" in str(exc):
                self._penalize(10)
            return None

    # ------------------------------- parseo -------------------------------- #
    def parse_anime(self, html, url):
        """Devuelve (registro, enlaces[(url, prioridad)], slugs_de_generos)."""
        soup = BeautifulSoup(html, "html.parser")

        # Título
        tag = soup.select_one(SEL_TITLE)
        titulo = clean(tag.get_text()) if tag else ""
        if not titulo:
            og = soup.find("meta", property="og:title")
            titulo = clean(og.get("content")) if og else ""
        if not titulo:
            raise ParseError("no se encontró el título")

        # Descripción
        tag = soup.select_one(SEL_DESCRIPTION)
        descripcion = clean(tag.get_text()) if tag else ""
        if not descripcion:
            meta = (soup.find("meta", property="og:description")
                    or soup.find("meta", attrs={"name": "description"}))
            descripcion = clean(meta.get("content")) if meta else ""

        # Géneros (nombre visible + slug para poder pedir el listado por género)
        names, slugs = [], []
        anchors = soup.select(SEL_GENRES)
        if not anchors:
            anchors = [a for a in soup.select("a[href]")
                       if GENRE_HREF_RE.search(a["href"])]
        for a in anchors:
            name = clean(a.get_text())
            if name and name not in names:
                names.append(name)
            m = GENRE_HREF_RE.search(a.get("href", ""))
            if m:
                slug = unquote(m.group(1)).lower()
                if slug not in slugs:
                    slugs.append(slug)

        if not descripcion:
            log.warning("Sin descripción: %s", url)
        if not names:
            log.warning("Sin géneros: %s", url)

        # Enlaces a otros títulos: relacionados primero, el resto con menor prioridad
        links, seen = [], {url}
        groups = [(sel, 0) for sel in SEL_RELATED] + [("a[href]", 2)]
        for selector, priority in groups:
            for a in soup.select(selector):
                link = normalize_anime_url(a["href"], url, self.netloc)
                if link and link not in seen:
                    seen.add(link)
                    links.append((link, priority))

        record = {
            "titulo": titulo,
            "descripcion": descripcion,
            "generos": ";".join(names),
            "url": url,
        }
        return record, links, slugs

    def parse_listing(self, html, base):
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.select(SEL_LISTING) or soup.select("a[href]")
        out, seen = [], set()
        for a in anchors:
            link = normalize_anime_url(a["href"], base, self.netloc)
            if link and link not in seen:
                seen.add(link)
                out.append(link)
        return out

    # ---------------- tareas que se ejecutan en los hilos ------------------- #
    def task_anime(self, url):
        html = self.fetch(url)
        if html is None:
            return ("fail", None)
        try:
            return ("ok", self.parse_anime(html, url))
        except Exception as exc:  # estructura distinta, HTML roto, etc.
            return ("parse_error", str(exc))

    def task_listing(self, url):
        html = self.fetch(url)
        return None if html is None else self.parse_listing(html, url)

    # ------------------------------ frontera ------------------------------- #
    def push(self, url, priority):
        if url in self.queued:
            return False
        self.queued.add(url)
        heapq.heappush(self.frontier, (priority, next(self._counter), url))
        return True

    def next_listing_job(self):
        """Elige una página de listado de un género del título actual (o de
        cualquiera si ya se agotaron). Devuelve (genero, pagina, url) o None."""
        candidates = [g for g in self.current_genres if g not in self.exhausted]
        if not candidates:
            candidates = [g for g in self.genre_pages if g not in self.exhausted]
        if not candidates:
            return None

        genre = min(candidates, key=lambda g: self.genre_pages[g])
        page = self.genre_pages[genre]
        self.genre_pages[genre] = page + 1
        if genre == "*":   # listado general, sin filtrar por género
            url = f"https://{self.netloc}/browse?order=default&page={page}"
        else:
            url = f"https://{self.netloc}/browse?genre[]={genre}&order=default&page={page}"

        if not self.allowed(url):
            log.warning("robots.txt no permite los listados (/browse); "
                        "solo se seguirán enlaces relacionados.")
            self.exhausted.update(self.genre_pages)
            return None
        return genre, page, url

    def discover_from_sitemaps(self):
        """Último recurso: lee los sitemaps declarados en robots.txt (o
        /sitemap.xml) y encola todos los /anime/<slug> que encuentre."""
        self.sitemap_done = True
        pending_maps = deque(self.robots.site_maps() or [f"https://{self.netloc}/sitemap.xml"])
        visited, fetched, added = set(), 0, 0
        while pending_maps and fetched < 15:
            sitemap = pending_maps.popleft()
            if sitemap in visited or not in_domain(urlsplit(sitemap).hostname):
                continue
            visited.add(sitemap)
            if sitemap.endswith(".gz"):
                log.warning("Sitemap comprimido omitido: %s", sitemap)
                continue
            text = self.fetch(sitemap, expect_html=False)
            fetched += 1
            if not text:
                continue
            for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.S):
                loc = unescape(loc)
                link = normalize_anime_url(loc, sitemap, self.netloc)
                if link:
                    added += self.push(link, 3)
                elif loc.lower().split("?")[0].endswith(".xml"):
                    pending_maps.append(loc)
        log.info("Sitemap: %d títulos nuevos encontrados", added)

    # ----------------------- procesamiento de resultados -------------------- #
    def handle_anime(self, url, result, writer, fh):
        status, payload = result
        if status != "ok":
            if status == "parse_error":
                self._record_failure(url, f"parseo: {payload}")
                log.error("No se pudo interpretar %s: %s", url, payload)
            self.consecutive_failures += 1
            return

        record, links, slugs = payload
        self.consecutive_failures = 0
        if url in self.saved:
            return
        writer.writerow(record)
        fh.flush()
        self.saved.add(url)

        self.current_genres = slugs
        for slug in slugs:
            self.genre_pages.setdefault(slug, 1)
        for link, priority in links:
            self.push(link, priority)

        log.info("[%d/%d] %s  (%s)", len(self.saved), self.args.records,
                 record["titulo"], record["generos"] or "sin géneros")

    def handle_listing(self, job, links):
        genre, page, _ = job
        if links is None:
            self.genre_failures[genre] = self.genre_failures.get(genre, 0) + 1
            if self.genre_failures[genre] >= 3:
                self.exhausted.add(genre)
            return
        added = sum(self.push(link, 1) for link in links)
        log.info("Listado '%s' pág. %d: %d enlaces (%d nuevos)",
                 genre, page, len(links), added)
        if not links or page >= MAX_LISTING_PAGES:
            self.exhausted.add(genre)

    # ------------------------------ ejecución ------------------------------ #
    def run(self):
        self.setup_robots()
        if not self.allowed(self.start_url):
            raise SystemExit("robots.txt no permite rastrear la URL inicial.")

        workers = self.args.workers
        goal = self.args.records
        self.push(self.start_url, -1)
        self.genre_pages.setdefault("*", 1)   # listado general como fuente de respaldo
        pending = {}  # future -> ("anime", url) | ("listing", job)

        with open(self.args.output, "w", newline="", encoding="utf-8-sig") as fh, \
                ThreadPoolExecutor(max_workers=workers + 1) as pool:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            try:
                while True:
                    anime_inflight = sum(1 for k, _ in pending.values() if k == "anime")
                    listing_inflight = any(k == "listing" for k, _ in pending.values())
                    room = goal - len(self.saved) - anime_inflight

                    # 1) Si la frontera se está vaciando, pedir un listado por género
                    job_submitted = False
                    if room > 0 and not listing_inflight and len(self.frontier) < REFILL_THRESHOLD:
                        job = self.next_listing_job()
                        if job:
                            pending[pool.submit(self.task_listing, job[2])] = ("listing", job)
                            job_submitted = True

                    # 1b) Sin listados ni frontera: probar el sitemap del sitio
                    if (room > 0 and not self.frontier and not self.sitemap_done
                            and not listing_inflight and not (job_submitted)):
                        self.discover_from_sitemaps()

                    # 2) Lanzar títulos en paralelo sin pasarse del objetivo
                    while self.frontier and anime_inflight < workers and room > 0:
                        _, _, url = heapq.heappop(self.frontier)
                        pending[pool.submit(self.task_anime, url)] = ("anime", url)
                        anime_inflight += 1
                        room -= 1

                    if not pending:
                        log.warning("No quedan más títulos por visitar "
                                    "(descubiertos: %d, guardados: %d).",
                                    len(self.queued), len(self.saved))
                        break

                    done, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for fut in done:
                        kind, info = pending.pop(fut)
                        try:
                            result = fut.result()
                        except Exception as exc:  # error inesperado en un hilo
                            log.exception("Error inesperado en %s", info)
                            if kind == "anime":
                                self._record_failure(info, f"excepción: {exc}")
                                self.consecutive_failures += 1
                            continue
                        if kind == "anime":
                            self.handle_anime(info, result, writer, fh)
                        else:
                            self.handle_listing(info, result)

                    if len(self.saved) >= goal:
                        break
                    if self.consecutive_failures >= self.args.max_consecutive_failures:
                        log.error("%d fallos consecutivos: se detiene para no "
                                  "saturar al sitio (¿bloqueo o cambio de HTML?).",
                                  self.consecutive_failures)
                        break
            except KeyboardInterrupt:
                log.warning("Interrumpido por el usuario; se conserva lo guardado.")
        self.summary()

    def summary(self):
        elapsed = int(time.monotonic() - self.t0)
        print("\n" + "=" * 50)
        print(f"Registros guardados : {len(self.saved)}  ->  {self.args.output}")
        print(f"Títulos descubiertos: {len(self.queued)}")
        print(f"Páginas fallidas    : {len(self.failed)}  (detalle en {self.args.log_file})")
        if self.blocked:
            print(f"Omitidas (robots.txt): {len(self.blocked)}")
        print(f"Tiempo total        : {elapsed // 60} min {elapsed % 60} s")
        if len(self.saved) < 500:
            print("Aviso: no se alcanzó el mínimo de 500 registros.")
        print("=" * 50)


# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(description="Crawler concurrente de metadatos de AnimeFLV")
    p.add_argument("url", help="URL de partida, p. ej. https://animeflv.lu/anime/one-piece")
    p.add_argument("-o", "--output", default="animeflv.csv", help="CSV de salida")
    p.add_argument("-n", "--records", type=int, default=600,
                   help="registros únicos a reunir (500-1000, por defecto 600)")
    p.add_argument("-w", "--workers", type=int, default=4,
                   help="títulos descargados en paralelo (1-10, por defecto 4)")
    p.add_argument("--delay", type=float, default=0.5,
                   help="segundos mínimos entre el inicio de dos peticiones, en total "
                        "(por defecto 0.5; robots.txt Crawl-delay tiene prioridad)")
    p.add_argument("--jitter", type=float, default=0.2,
                   help="variación aleatoria extra en segundos (por defecto 0.2)")
    p.add_argument("--timeout", type=float, default=20, help="timeout por petición (s)")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                   help="User-Agent identificable (cambia el correo de contacto)")
    p.add_argument("--max-consecutive-failures", type=int, default=10)
    p.add_argument("--log-file", default="crawler.log")
    args = p.parse_args()

    if not 500 <= args.records <= 1000:
        p.error("--records debe estar entre 500 y 1000")
    if not 1 <= args.workers <= 10:
        p.error("--workers debe estar entre 1 y 10")
    if args.delay < 0 or args.jitter < 0:
        p.error("--delay y --jitter no pueden ser negativos")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.log_file, encoding="utf-8"),
                  logging.StreamHandler()],
    )
    Crawler(args).run()


if __name__ == "__main__":
    main()
