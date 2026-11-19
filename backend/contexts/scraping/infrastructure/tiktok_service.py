"""Unified Playwright-based TikTok scraping service with async execution and no-login support."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Response, async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PERFIL_NAVEGADOR_DIR = BASE_DIR / "tiktok_browser_profile"

USER_AGENTS: dict[str, str] = {
    "chrome_windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "chrome_mac": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "edge_windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
    ),
}

MODOS: tuple[str, ...] = ("hibrido", "red", "dom", "rapido")

SELECTOR_POST = '[data-e2e="user-post-item"]'
SELECTOR_HIDRATACION = "script#__UNIVERSAL_DATA_FOR_REHYDRATION__"
SELECTORES_CAPTCHA: tuple[str, ...] = (
    "#captcha-verify-container-main-page",
    "#captcha_container",
    "div[class*='captcha_verify']",
    "div[class*='CaptchaVerify']",
)

JS_LEER_DOM = """
(sel) => Array.from(document.querySelectorAll(sel)).map(el => {
    const a = el.querySelector('a');
    const v = el.querySelector('[data-e2e="video-views"]') || el.querySelector('strong');
    const img = el.querySelector('img');
    const descEl = el.querySelector('[title], a');
    return {
        href: a ? a.href : null,
        vistas: v ? v.innerText.trim() : null,
        alt: img ? img.getAttribute('alt') : null,
        portada: img ? img.getAttribute('src') : null,
        desc: descEl ? (descEl.getAttribute('title') || descEl.innerText || '') : '',
        fijado: !!el.querySelector('[data-e2e="video-card-badge"]'),
    };
})
"""


@dataclass(frozen=True)
class ScrapeOptions:
    """Configuración para la ejecución del scraping de perfiles."""
    modo: str = "hibrido"
    max_scrolls: int = 5
    max_posts: int = 19
    scroll_delay_ms: int = 1800
    headless: bool = True
    bloquear_multimedia: bool = True
    sesion_persistente: bool = False
    humanizar: bool = True
    detener_sin_nuevos: int = 3
    fecha_desde: Optional[str] = None
    user_agent: str = "chrome_windows"
    timeout_carga_s: int = 25
    reintentos: int = 2
    max_comment_videos: int = 2
    max_following: int = 20
    max_followers: int = 20

    @classmethod
    def desde_dict(cls, data: Optional[dict[str, Any]]) -> ScrapeOptions:
        raw = data or {}

        def _parse_int(key: str, default: int, minimum: int, maximum: int) -> int:
            try:
                return max(minimum, min(int(raw.get(key, default)), maximum))
            except (TypeError, ValueError):
                return default

        def _parse_bool(key: str, default: bool) -> bool:
            val = raw.get(key, default)
            if isinstance(val, str):
                return val.lower() in ("1", "true", "on", "si", "sí", "yes")
            return bool(val)

        modo = raw.get("modo", "hibrido")
        return cls(
            modo=modo if modo in MODOS else "hibrido",
            max_scrolls=_parse_int("max_scrolls", 5, 0, 100),
            max_posts=_parse_int("max_posts", _parse_int("max_videos", 19, 1, 500), 1, 5000),
            scroll_delay_ms=_parse_int("scroll_delay_ms", 1800, 400, 15000),
            headless=_parse_bool("headless", True),
            bloquear_multimedia=_parse_bool("bloquear_multimedia", True),
            sesion_persistente=_parse_bool("sesion_persistente", False),
            humanizar=_parse_bool("humanizar", True),
            detener_sin_nuevos=_parse_int("detener_sin_nuevos", 3, 1, 30),
            fecha_desde=(raw.get("fecha_desde") or "").strip() or None,
            user_agent=raw.get("user_agent", "chrome_windows"),
            timeout_carga_s=_parse_int("timeout_carga_s", 25, 5, 120),
            reintentos=_parse_int("reintentos", 1, 0, 4),
            max_comment_videos=_parse_int("max_comment_videos", 2, 0, 10),
            max_following=_parse_int("max_following", 20, 0, 100),
            max_followers=_parse_int("max_followers", 20, 0, 100)
        )


class TikTokDataParser:
    """Normaliza y estructura datos extraídos tanto de la API de TikTok como del DOM."""

    @staticmethod
    def format_number(val: Any) -> str:
        try:
            num = int(val)
            if num < 0:
                num = num + 4294967296
            if num >= 1_000_000_000:
                return f"{round(num / 1_000_000_000, 1)}B"
            if num >= 1_000_000:
                return f"{round(num / 1_000_000, 1)}M"
            if num >= 1_000:
                return f"{round(num / 1_000, 1)}K"
            return str(num)
        except Exception:
            return str(val or "0")

    @staticmethod
    def parse_count(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip().upper().replace(" ", "")
        if not text:
            return None
        mult = 1
        if text.endswith("K"):
            mult, text = 1_000, text[:-1]
        elif text.endswith("M"):
            mult, text = 1_000_000, text[:-1]
        elif text.endswith("B"):
            mult, text = 1_000_000_000, text[:-1]
        text = text.replace(",", ".")
        if text.count(".") > 1:
            text = text.replace(".", "")
        try:
            return int(float(text) * mult)
        except ValueError:
            return None

    @classmethod
    def to_int(cls, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return cls.parse_count(value)

    @staticmethod
    def extract_hashtags(item: dict[str, Any], description: str) -> list[str]:
        tags: list[str] = []
        for extra in item.get("textExtra") or []:
            name = extra.get("hashtagName")
            if name:
                tags.append(name.lower())
        if not tags:
            for challenge in item.get("challenges") or []:
                if challenge.get("title"):
                    tags.append(challenge["title"].lower())
        if not tags and description:
            tags = [h.lower() for h in re.findall(r"#([\w\ñ\Ñ]+)", description)]
        return list(dict.fromkeys(tags))

    @staticmethod
    def extract_mentions(item: dict[str, Any], description: str) -> list[str]:
        mentions = [
            extra.get("userUniqueId")
            for extra in item.get("textExtra") or []
            if extra.get("userUniqueId")
        ]
        if not mentions and description:
            mentions = re.findall(r"@([\w.]+)", description)
        return list(dict.fromkeys(mentions))

    @classmethod
    def parse_api_item(cls, item: dict[str, Any], username: str) -> dict[str, Any]:
        video_id = str(item.get("id", ""))
        ts = cls.to_int(item.get("createTime")) or 0
        desc = item.get("desc", "") or ""
        stats = item.get("stats") or {}
        stats_v2 = item.get("statsV2") or {}
        video = item.get("video") or {}
        music = item.get("music") or {}
        is_photo = bool(item.get("imagePost"))

        def _stat(key: str) -> int:
            val = cls.to_int(stats_v2.get(key))
            if val is not None:
                return val
            return cls.to_int(stats.get(key)) or 0

        plays = _stat("playCount")
        likes = _stat("diggCount")
        comments = _stat("commentCount")
        shares = _stat("shareCount")
        collects = _stat("collectCount")

        cover = (
            video.get("cover")
            or video.get("originCover")
            or video.get("dynamicCover")
            or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"
        )

        duration_sec = cls.to_int(video.get("duration")) or 15

        return {
            "id": video_id,
            "vid_id": video_id,
            "descripcion": desc,
            "desc": desc,
            "timestamp": ts,
            "create_time": ts,
            "fecha": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else None,
            "url": f"https://www.tiktok.com/@{username}/{'photo' if is_photo else 'video'}/{video_id}",
            "tipo": "foto" if is_photo else "video",
            "duracion": duration_sec,
            "duration": f"{duration_sec}s",
            "fijado": bool(item.get("isPinnedItem") or item.get("isPinned")),
            "hashtags": cls.extract_hashtags(item, desc),
            "menciones": cls.extract_mentions(item, desc),
            "musica": {
                "titulo": music.get("title"),
                "autor": music.get("authorName"),
                "original": bool(music.get("original")),
            },
            "portada": cover,
            "thumbnail": cover,
            "views": cls.format_number(plays),
            "likes": cls.format_number(likes),
            "shares": cls.format_number(shares),
            "comments_count": cls.format_number(comments),
            "raw_plays": plays,
            "raw_interactions": likes + comments + shares + collects,
            "estadisticas": {
                "vistas": plays,
                "likes": likes,
                "comentarios": comments,
                "compartidos": shares,
                "guardados": collects,
            },
            "fuente": "api",
        }

    @classmethod
    def parse_dom_item(cls, raw: dict[str, Any], username: str) -> Optional[dict[str, Any]]:
        href = raw.get("href") or ""
        match = re.search(r"/(video|photo)/(\d+)", href)
        if not match:
            return None
        video_id = match.group(2)
        desc = raw.get("desc") or raw.get("alt") or ""
        plays = cls.parse_count(raw.get("vistas")) or 0
        cover = raw.get("portada") or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"

        return {
            "id": video_id,
            "vid_id": video_id,
            "descripcion": desc,
            "desc": desc,
            "timestamp": 0,
            "create_time": 0,
            "fecha": None,
            "url": href.split("?")[0] if href else f"https://www.tiktok.com/@{username}/video/{video_id}",
            "tipo": "foto" if match.group(1) == "photo" else "video",
            "duracion": 15,
            "duration": "15s",
            "fijado": bool(raw.get("fijado")),
            "hashtags": list(dict.fromkeys(h.lower() for h in re.findall(r"#([\w\ñ\Ñ]+)", desc))),
            "menciones": [],
            "musica": {"titulo": None, "autor": None, "original": None},
            "portada": cover,
            "thumbnail": cover,
            "views": cls.format_number(plays),
            "likes": "0",
            "shares": "0",
            "comments_count": "0",
            "raw_plays": plays,
            "raw_interactions": 0,
            "estadisticas": {
                "vistas": plays,
                "likes": 0,
                "comentarios": 0,
                "compartidos": 0,
                "guardados": 0,
            },
            "fuente": "dom",
        }

    @classmethod
    def parse_profile(cls, user_detail: dict[str, Any], fallback_user: str) -> dict[str, Any]:
        info = user_detail.get("userInfo") or {}
        user = info.get("user") or {}
        stats = info.get("statsV2") or info.get("stats") or {}
        stats_v1 = info.get("stats") or {}

        def _stat(key: str, fallback: Optional[str] = None) -> Optional[int]:
            val = cls.to_int(stats.get(key))
            if val is None and fallback:
                val = cls.to_int(stats.get(fallback))
            if val is None:
                val = cls.to_int(stats_v1.get(key)) or (
                    cls.to_int(stats_v1.get(fallback)) if fallback else None
                )
            return val

        raw_followers = _stat("followerCount") or 0
        raw_likes = _stat("heartCount", "heart") or 0
        raw_following = _stat("followingCount") or 0
        raw_videos = _stat("videoCount") or 0

        uname = user.get("uniqueId") or fallback_user
        name = user.get("nickname") or uname
        bio = user.get("signature") or ""
        avatar = user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb") or ""

        return {
            "id": user.get("id"),
            "usuario": uname,
            "username": f"@{uname.lstrip('@')}",
            "nombre": name,
            "name": name,
            "bio": bio,
            "avatar": avatar,
            "verificado": bool(user.get("verified")),
            "privada": bool(user.get("privateAccount")),
            "enlace_bio": (user.get("bioLink") or {}).get("link"),
            "region": user.get("region"),
            "seguidores": raw_followers,
            "followers": cls.format_number(raw_followers),
            "siguiendo": raw_following,
            "likes_totales": raw_likes,
            "likes": cls.format_number(raw_likes),
            "videos": raw_videos,
            "videosCount": str(raw_videos),
            "amigos": _stat("friendCount") or 0,
            "engagement": "N/A",
            "avgViews": "N/A"
        }


class TikTokScraperService:
    """Servicio completo de extracción con Playwright async, soporte sin login y streaming."""

    def __init__(self, log_callback: Optional[Callable[[str], Any]] = None):
        self.log_callback = log_callback
        self.parser = TikTokDataParser()

    async def _log(self, message: str) -> None:
        if self.log_callback:
            try:
                res = self.log_callback(message)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    async def scrape(
        self,
        username: str,
        target: str = "all",
        max_videos: int = 19,
        max_comment_videos: int = 2,
        max_following: int = 20,
        max_followers: int = 20,
        options_dict: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Punto de entrada compatible con VerifAI que invoca el motor optimizado."""
        clean_user = username.replace("@", "").strip()
        opts = options_dict or {}
        opts.setdefault("max_videos", max_videos)
        opts.setdefault("max_comment_videos", max_comment_videos)
        opts.setdefault("max_following", max_following)
        opts.setdefault("max_followers", max_followers)
        scrape_opts = ScrapeOptions.desde_dict(opts)

        return await self._execute_scrape(clean_user, target, scrape_opts)

    async def _execute_scrape(
        self, username: str, target: str, options: ScrapeOptions
    ) -> Dict[str, Any]:
        start_time = time.time()
        await self._log(f"[INIT] Configurando motor de extracción para @{username} (Modo: {options.modo})...")

        posts_map: Dict[str, Dict[str, Any]] = {}
        captured_comments: List[Dict[str, Any]] = []
        captured_followers: List[Dict[str, Any]] = []
        captured_following: List[Dict[str, Any]] = []

        profile_data = {
            "name": username,
            "username": f"@{username}",
            "bio": "",
            "followers": "0",
            "likes": "0",
            "videosCount": "0",
            "engagement": "N/A",
            "avgViews": "N/A",
            "avatar": ""
        }

        async with async_playwright() as playwright:
            browser = None
            context = None
            try:
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--mute-audio"
                ]

                # Sesión sin login por defecto (contexto limpio)
                # Si sesion_persistente está activada y existe directorio, la usa
                if options.sesion_persistente:
                    PERFIL_NAVEGADOR_DIR.mkdir(parents=True, exist_ok=True)
                    context = await playwright.chromium.launch_persistent_context(
                        str(PERFIL_NAVEGADOR_DIR),
                        headless=options.headless,
                        args=launch_args,
                        user_agent=USER_AGENTS.get(options.user_agent, USER_AGENTS["chrome_windows"]),
                        viewport={"width": 1280, "height": 850}
                    )
                else:
                    browser = await playwright.chromium.launch(
                        headless=options.headless,
                        args=launch_args
                    )
                    context = await browser.new_context(
                        user_agent=USER_AGENTS.get(options.user_agent, USER_AGENTS["chrome_windows"]),
                        viewport={"width": 1280, "height": 850}
                    )

                # Optimización masiva de rendimiento: Bloqueo de multimedia
                if options.bloquear_multimedia:
                    async def filter_route(route):
                        if route.request.resource_type in ("media", "image", "font"):
                            await route.abort()
                        else:
                            await route.continue_()
                    await context.route("**/*", filter_route)

                page = context.pages[0] if context.pages else await context.new_page()

                # 1. Listener de red para atrapar respuestas de la API interna de TikTok
                async def on_response(response: Response):
                    req_url = response.url
                    # A. Catálogo de publicaciones
                    if "/api/post/item_list" in req_url and response.status == 200:
                        try:
                            data = await response.json()
                            for item in data.get("itemList") or []:
                                parsed = self.parser.parse_api_item(item, username)
                                if parsed["id"] not in posts_map:
                                    posts_map[parsed["id"]] = parsed
                        except Exception:
                            pass

                    # B. Comentarios
                    if ("/api/comment/list" in req_url or "comment/list" in req_url) and response.status == 200:
                        try:
                            data = await response.json()
                            for comm in data.get("comments") or []:
                                c_id = str(comm.get("cid", ""))
                                if c_id and not any(c["id"] == c_id for c in captured_comments):
                                    u = comm.get("user") or {}
                                    raw_uid = u.get("unique_id") or u.get("uniqueId") or "anónimo"
                                    captured_comments.append({
                                        "id": c_id,
                                        "video_id": "api_intercepted",
                                        "video_url": f"https://www.tiktok.com/@{username}",
                                        "author": f"@{raw_uid.lstrip('@')}",
                                        "author_name": u.get("nickname") or raw_uid,
                                        "avatar": (u.get("avatar_thumb") or {}).get("url_list", [""])[0] if isinstance(u.get("avatar_thumb"), dict) else "",
                                        "text": comm.get("text") or "",
                                        "likes": self.parser.format_number(comm.get("digg_count", 0)),
                                        "date": time.strftime("%Y-%m-%d", time.localtime(comm.get("create_time", time.time())))
                                    })
                        except Exception:
                            pass

                if options.modo in ("hibrido", "red", "rapido"):
                    page.on("response", on_response)

                url = f"https://www.tiktok.com/@{username}"
                await self._log(f"[NETWORK] Navegando a {url}...")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=options.timeout_carga_s * 1000)
                except Exception as e:
                    await self._log(f"[WARN] Error inicial cargando {url}: {e}. Reintentando...")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass

                # 2. Extracción de datos del perfil desde SSR Hydration
                await self._log("[PARSER] Inspeccionando datos hidratados de TikTok...")
                try:
                    await page.wait_for_selector(SELECTOR_HIDRATACION, state="attached", timeout=8000)
                    hydration_el = await page.query_selector(SELECTOR_HIDRATACION)
                    if hydration_el:
                        raw_json = await hydration_el.inner_text()
                        hydration_data = json.loads(raw_json)
                        user_detail = hydration_data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
                        if user_detail:
                            profile_data = self.parser.parse_profile(user_detail, username)
                            # Posts iniciales embebidos en la carga SSR
                            for item in user_detail.get("itemList") or []:
                                parsed = self.parser.parse_api_item(item, username)
                                if parsed["id"] not in posts_map:
                                    posts_map[parsed["id"]] = parsed
                            await self._log(f"[SUCCESS] Perfil detectado: {profile_data['name']} (@{profile_data['usuario']}) con {profile_data['followers']} seguidores.")
                except Exception as e:
                    await self._log(f"[WARN] No se pudo leer hidratación SSR completa: {e}")

                # 3. Detección de Captcha
                for c_sel in SELECTORES_CAPTCHA:
                    if await page.query_selector(c_sel):
                        await self._log("[CAPTCHA] TikTok ha solicitado verificación.")
                        if not options.headless:
                            await self._log("[CAPTCHA] Esperando resolución en ventana (40s)...")
                            for _ in range(40):
                                await page.wait_for_timeout(1000)
                                if not await page.query_selector(c_sel):
                                    await self._log("[CAPTCHA] Resuelto con éxito.")
                                    break
                        break

                # 4. Lectura visual del DOM (Fallback o Modo DOM)
                if options.modo in ("hibrido", "dom"):
                    try:
                        raw_dom_cards = await page.evaluate(JS_LEER_DOM, SELECTOR_POST)
                        for raw_card in raw_dom_cards:
                            parsed = self.parser.parse_dom_item(raw_card, username)
                            if parsed and parsed["id"] not in posts_map:
                                posts_map[parsed["id"]] = parsed
                    except Exception:
                        pass

                # 5. Scrolls adaptativos y humanizados si se requieren más publicaciones
                if options.modo != "rapido" and options.max_scrolls > 0 and len(posts_map) < options.max_posts:
                    await self._log(f"[SCROLL] Recolectando publicaciones adicionales (Objetivo: {options.max_posts})...")
                    sin_nuevos = 0
                    for s_idx in range(options.max_scrolls):
                        if len(posts_map) >= options.max_posts:
                            break

                        cant_anterior = len(posts_map)

                        # Humanización: pequeños movimientos y scroll progresivo
                        if options.humanizar:
                            await page.mouse.move(random.randint(400, 800), random.randint(300, 600))
                            await page.mouse.wheel(0, random.randint(700, 1200))
                            await page.wait_for_timeout(random.randint(150, 400))
                        else:
                            await page.evaluate("window.scrollBy(0, 1000)")

                        await page.wait_for_timeout(options.scroll_delay_ms)

                        # Leer DOM tras el scroll
                        if options.modo in ("hibrido", "dom"):
                            try:
                                raw_dom_cards = await page.evaluate(JS_LEER_DOM, SELECTOR_POST)
                                for raw_card in raw_dom_cards:
                                    parsed = self.parser.parse_dom_item(raw_card, username)
                                    if parsed and parsed["id"] not in posts_map:
                                        posts_map[parsed["id"]] = parsed
                            except Exception:
                                pass

                        nuevos = len(posts_map) - cant_anterior
                        await self._log(f"[PROGRESS] Scroll {s_idx + 1}/{options.max_scrolls}: {len(posts_map)} posts (+{nuevos})")

                        if nuevos == 0:
                            sin_nuevos += 1
                            if sin_nuevos >= options.detener_sin_nuevos:
                                await self._log("[INFO] No hay más contenido nuevo cargando. Finalizando scrolls.")
                                break
                        else:
                            sin_nuevos = 0

            except Exception as exc:
                await self._log(f"[ERROR] Error durante el ciclo de scraping: {exc}")
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        # 6. Consolidar métricas finales
        all_posts = list(posts_map.values())[:options.max_posts]
        total_plays = sum(p.get("raw_plays", 0) for p in all_posts)
        total_interactions = sum(p.get("raw_interactions", 0) for p in all_posts)
        v_count = len(all_posts)

        profile_data["videosCount"] = str(profile_data.get("videos") or v_count)

        if v_count > 0:
            if total_plays > 0:
                profile_data["avgViews"] = self.parser.format_number(int(total_plays / v_count))
                profile_data["engagement"] = f"{round((total_interactions / total_plays) * 100, 2)}%"
            else:
                profile_data["avgViews"] = all_posts[0].get("views", "0")
                profile_data["engagement"] = "0%"

        # Formatear lista de videos para la UI de React / Mobile
        formatted_videos = []
        for idx, vid in enumerate(all_posts):
            formatted_videos.append({
                "id": vid["id"],
                "url": vid["url"],
                "thumbnail": vid.get("thumbnail") or vid.get("portada", ""),
                "views": vid.get("views", "0"),
                "likes": vid.get("likes", "0"),
                "shares": vid.get("shares", "0"),
                "comments_count": vid.get("comments_count", "0"),
                "duration": vid.get("duration", "15s"),
                "duracion": vid.get("duracion", 15),
                "desc": vid.get("desc") or vid.get("descripcion", ""),
                "descripcion": vid.get("descripcion") or vid.get("desc", ""),
                "create_time": vid.get("create_time", 0),
                "fecha": vid.get("fecha"),
                "hashtags": vid.get("hashtags", []),
                "menciones": vid.get("menciones", []),
                "musica": vid.get("musica", {}),
                "tipo": vid.get("tipo", "video"),
                "fijado": vid.get("fijado", False),
                "estadisticas": vid.get("estadisticas", {})
            })

        duration_s = round(time.time() - start_time, 2)
        await self._log(f"[SUCCESS] Extracción finalizada en {duration_s}s: {len(formatted_videos)} publicaciones recolectadas.")

        raw_scrape_result = {
            "estado": "ok",
            "usuario": username,
            "username": username,
            "perfil": profile_data,
            "profile": profile_data,
            "publica": True,
            "total_posts_extraidos": len(formatted_videos),
            "posts": formatted_videos,
            "videos": formatted_videos,
            "comments": captured_comments,
            "followers_list": captured_followers,
            "following_list": captured_following,
            "meta": {
                "fecha_scrape": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duracion_s": duration_s,
                "opciones": asdict(options)
            }
        }

        # Ejecución del motor analítico de reglas e insights
        try:
            from contexts.analytics.analytics_service import default_dashboard_builder
            dashboard = default_dashboard_builder.build(raw_scrape_result)
            raw_scrape_result["analytics"] = dashboard
            raw_scrape_result["kpis"] = dashboard.get("kpis", {})
            raw_scrape_result["insights"] = dashboard.get("insights", [])
        except Exception as e:
            await self._log(f"[WARN] No se pudo computar el dashboard analítico: {e}")
            raw_scrape_result["analytics"] = {}

        return raw_scrape_result
