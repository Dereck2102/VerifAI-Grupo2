"""Persistence layer for TikTok scraping snapshots and historical datasets."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tiktok.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scrapes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL,
    fecha         TEXT NOT NULL,
    modo          TEXT,
    total_posts   INTEGER,
    duracion_s    REAL,
    opciones      TEXT,
    resultado     TEXT
);
CREATE INDEX IF NOT EXISTS ix_scrapes_user ON scrapes(username, fecha);

CREATE TABLE IF NOT EXISTS profile_snapshots (
    scrape_id     INTEGER REFERENCES scrapes(id) ON DELETE CASCADE,
    username      TEXT NOT NULL,
    fecha         TEXT NOT NULL,
    nombre        TEXT,
    verificado    INTEGER,
    seguidores    INTEGER,
    siguiendo     INTEGER,
    likes_totales INTEGER,
    videos        INTEGER,
    bio           TEXT,
    avatar        TEXT
);
CREATE INDEX IF NOT EXISTS ix_prof_user ON profile_snapshots(username, fecha);

CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL,
    descripcion     TEXT,
    timestamp       INTEGER,
    fecha           TEXT,
    url             TEXT,
    tipo            TEXT,
    duracion        INTEGER,
    fijado          INTEGER,
    hashtags        TEXT,
    menciones       TEXT,
    musica          TEXT,
    musica_original INTEGER,
    vistas          INTEGER,
    likes           INTEGER,
    comentarios     INTEGER,
    compartidos     INTEGER,
    guardados       INTEGER,
    fuente          TEXT,
    primera_vez     TEXT,
    ultima_vez      TEXT
);
CREATE INDEX IF NOT EXISTS ix_posts_user ON posts(username);

CREATE TABLE IF NOT EXISTS post_snapshots (
    scrape_id     INTEGER REFERENCES scrapes(id) ON DELETE CASCADE,
    post_id       TEXT NOT NULL,
    fecha         TEXT NOT NULL,
    vistas        INTEGER,
    likes         INTEGER,
    comentarios   INTEGER,
    compartidos   INTEGER,
    guardados     INTEGER
);
CREATE INDEX IF NOT EXISTS ix_psnap_post ON post_snapshots(post_id, fecha);
"""


class ScraperRepository(ABC):
    """Abstract repository defining persistence operations for scraped TikTok data."""

    @abstractmethod
    def initialize(self) -> None:
        """Initializes the underlying storage schema."""

    @abstractmethod
    def save_scrape(self, result: dict[str, Any]) -> int:
        """Persists a scrape execution, its profile snapshot, and its post snapshots."""

    @abstractmethod
    def get_scrape_result(self, scrape_id: int) -> Optional[dict[str, Any]]:
        """Retrieves the raw scrape result payload by identifier."""

    @abstractmethod
    def get_latest_scrape_id(self, username: str) -> Optional[int]:
        """Returns the most recent scrape identifier for a given username."""

    @abstractmethod
    def list_scrapes(self, username: Optional[str] = None) -> list[dict[str, Any]]:
        """Lists historical scrape executions."""

    @abstractmethod
    def list_accounts(self) -> list[dict[str, Any]]:
        """Lists all tracked accounts with their latest snapshot and aggregate statistics."""

    @abstractmethod
    def get_profile_history(self, username: str) -> list[dict[str, Any]]:
        """Returns chronological profile metric snapshots for an account."""

    @abstractmethod
    def get_post_velocity(self, username: str) -> dict[str, dict[str, Any]]:
        """Computes view and like growth rates across snapshots for each post."""

    @abstractmethod
    def get_posts_dataset(self, username: Optional[str] = None) -> list[dict[str, Any]]:
        """Returns deduplicated post records across one or all accounts."""

    @abstractmethod
    def get_profiles_dataset(self) -> list[dict[str, Any]]:
        """Returns all historical profile snapshots across all accounts."""

    @abstractmethod
    def delete_account(self, username: str) -> None:
        """Removes all stored records associated with an account."""


class SqliteScraperRepository(ScraperRepository):
    """SQLite implementation of ScraperRepository."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        """Returns the filesystem path of the SQLite database."""
        return self._db_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript(SCHEMA_SQL)

    def save_scrape(self, result: dict[str, Any]) -> int:
        meta = result.get("meta", {})
        fecha = meta.get("fecha_scrape") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = (result.get("usuario") or result.get("username") or "").lower().lstrip("@")
        perfil = result.get("perfil") or result.get("profile") or {}

        def _to_int(val):
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO scrapes (username, fecha, modo, total_posts, duracion_s, opciones, resultado) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    username,
                    fecha,
                    meta.get("opciones", {}).get("modo", "hibrido"),
                    result.get("total_posts_extraidos", len(result.get("posts", []))),
                    meta.get("duracion_s", 0.0),
                    json.dumps(meta.get("opciones", {}), ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            scrape_id = int(cursor.lastrowid)

            conn.execute(
                "INSERT INTO profile_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    scrape_id,
                    username,
                    fecha,
                    perfil.get("nombre") or perfil.get("name"),
                    int(bool(perfil.get("verificado"))),
                    _to_int(perfil.get("seguidores") or perfil.get("followers")),
                    _to_int(perfil.get("siguiendo")),
                    _to_int(perfil.get("likes_totales") or perfil.get("likes")),
                    _to_int(perfil.get("videos") or perfil.get("videosCount")),
                    perfil.get("bio"),
                    perfil.get("avatar"),
                ),
            )

            for post in result.get("posts", []):
                stats = post.get("estadisticas") or {
                    "vistas": _to_int(post.get("views")),
                    "likes": _to_int(post.get("likes")),
                    "comentarios": _to_int(post.get("comments_count")),
                    "compartidos": _to_int(post.get("shares")),
                    "guardados": 0
                }
                music = post.get("musica") or {}
                conn.execute(
                    """
                    INSERT INTO posts (id, username, descripcion, timestamp, fecha, url, tipo, duracion, fijado,
                                       hashtags, menciones, musica, musica_original, vistas, likes, comentarios,
                                       compartidos, guardados, fuente, primera_vez, ultima_vez)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        descripcion     = COALESCE(NULLIF(excluded.descripcion, ''), posts.descripcion),
                        timestamp       = COALESCE(excluded.timestamp, posts.timestamp),
                        fecha           = COALESCE(excluded.fecha, posts.fecha),
                        duracion        = COALESCE(excluded.duracion, posts.duracion),
                        fijado          = excluded.fijado,
                        hashtags        = CASE WHEN excluded.hashtags != '[]' THEN excluded.hashtags ELSE posts.hashtags END,
                        musica          = COALESCE(excluded.musica, posts.musica),
                        musica_original = COALESCE(excluded.musica_original, posts.musica_original),
                        vistas          = COALESCE(excluded.vistas, posts.vistas),
                        likes           = COALESCE(excluded.likes, posts.likes),
                        comentarios     = COALESCE(excluded.comentarios, posts.comentarios),
                        compartidos     = COALESCE(excluded.compartidos, posts.compartidos),
                        guardados       = COALESCE(excluded.guardados, posts.guardados),
                        fuente          = CASE WHEN excluded.fuente = 'api' THEN 'api' ELSE posts.fuente END,
                        ultima_vez      = excluded.ultima_vez
                    """,
                    (
                        str(post["id"]),
                        username,
                        post.get("descripcion") or post.get("desc"),
                        post.get("timestamp") or post.get("create_time"),
                        post.get("fecha"),
                        post.get("url"),
                        post.get("tipo", "video"),
                        _to_int(post.get("duracion")),
                        int(bool(post.get("fijado"))),
                        json.dumps(post.get("hashtags") or [], ensure_ascii=False),
                        json.dumps(post.get("menciones") or [], ensure_ascii=False),
                        music.get("titulo"),
                        None
                        if music.get("original") is None
                        else int(bool(music.get("original"))),
                        stats.get("vistas"),
                        stats.get("likes"),
                        stats.get("comentarios"),
                        stats.get("compartidos"),
                        stats.get("guardados"),
                        post.get("fuente", "api"),
                        fecha,
                        fecha,
                    ),
                )
                conn.execute(
                    "INSERT INTO post_snapshots VALUES (?,?,?,?,?,?,?,?)",
                    (
                        scrape_id,
                        str(post["id"]),
                        fecha,
                        stats.get("vistas"),
                        stats.get("likes"),
                        stats.get("comentarios"),
                        stats.get("compartidos"),
                        stats.get("guardados"),
                    ),
                )
        return scrape_id

    def get_scrape_result(self, scrape_id: int) -> Optional[dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT resultado FROM scrapes WHERE id = ?", (scrape_id,)
            ).fetchone()
        return json.loads(row["resultado"]) if row else None

    def get_latest_scrape_id(self, username: str) -> Optional[int]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT id FROM scrapes WHERE username = ? ORDER BY id DESC LIMIT 1",
                (username.lower().lstrip("@"),),
            ).fetchone()
        return int(row["id"]) if row else None

    def list_scrapes(self, username: Optional[str] = None) -> list[dict[str, Any]]:
        with self._connection() as conn:
            if username:
                rows = conn.execute(
                    "SELECT id, username, fecha, modo, total_posts, duracion_s FROM scrapes "
                    "WHERE username = ? ORDER BY id DESC",
                    (username.lower().lstrip("@"),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, username, fecha, modo, total_posts, duracion_s FROM scrapes "
                    "ORDER BY id DESC LIMIT 50"
                ).fetchall()
        return [dict(r) for r in rows]

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT ps.username, ps.nombre, ps.verificado, ps.seguidores, ps.likes_totales, ps.videos,
                       ps.avatar, ps.fecha AS ultimo_scrape,
                       (SELECT COUNT(*) FROM scrapes s WHERE s.username = ps.username) AS num_scrapes,
                       (SELECT COUNT(*) FROM posts p WHERE p.username = ps.username) AS posts_guardados,
                       (SELECT AVG(vistas) FROM posts p WHERE p.username = ps.username AND vistas IS NOT NULL)
                            AS vistas_promedio
                FROM profile_snapshots ps
                WHERE ps.scrape_id = (SELECT MAX(scrape_id) FROM profile_snapshots WHERE username = ps.username)
                ORDER BY ps.fecha DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def get_profile_history(self, username: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT fecha, seguidores, siguiendo, likes_totales, videos FROM profile_snapshots "
                "WHERE username = ? ORDER BY fecha",
                (username.lower().lstrip("@"),),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_post_velocity(self, username: str) -> dict[str, dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT s.post_id, s.fecha, s.vistas, s.likes
                FROM post_snapshots s JOIN posts p ON p.id = s.post_id
                WHERE p.username = ? AND s.vistas IS NOT NULL
                ORDER BY s.post_id, s.fecha
                """,
                (username.lower().lstrip("@"),),
            ).fetchall()

        by_post: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_post.setdefault(row["post_id"], []).append(dict(row))

        velocities: dict[str, dict[str, Any]] = {}
        for post_id, snaps in by_post.items():
            if len(snaps) < 2:
                continue
            first, last = snaps[0], snaps[-1]
            try:
                hours = (
                    datetime.strptime(last["fecha"], "%Y-%m-%d %H:%M:%S")
                    - datetime.strptime(first["fecha"], "%Y-%m-%d %H:%M:%S")
                ).total_seconds() / 3600
            except ValueError:
                continue
            if hours <= 0:
                continue
            gained_views = (last["vistas"] or 0) - (first["vistas"] or 0)
            gained_likes = (last["likes"] or 0) - (first["likes"] or 0)
            velocities[post_id] = {
                "vistas_ganadas": gained_views,
                "likes_ganados": gained_likes,
                "horas": round(hours, 1),
                "vistas_por_hora": round(gained_views / hours, 1),
            }
        return velocities

    def get_posts_dataset(self, username: Optional[str] = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM posts"
        params: tuple[Any, ...] = ()
        if username:
            sql += " WHERE username = ?"
            params = (username.lower().lstrip("@"),)
        sql += " ORDER BY username, timestamp DESC"
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        dataset: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            try:
                record["hashtags"] = ", ".join(json.loads(record.get("hashtags") or "[]"))
            except Exception:
                pass
            try:
                record["menciones"] = ", ".join(json.loads(record.get("menciones") or "[]"))
            except Exception:
                pass
            dataset.append(record)
        return dataset

    def get_profiles_dataset(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT username, fecha, nombre, verificado, seguidores, siguiendo, likes_totales, videos "
                "FROM profile_snapshots ORDER BY username, fecha"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_account(self, username: str) -> None:
        normalized = username.lower().lstrip("@")
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM post_snapshots WHERE post_id IN (SELECT id FROM posts WHERE username = ?)",
                (normalized,),
            )
            conn.execute("DELETE FROM posts WHERE username = ?", (normalized,))
            conn.execute("DELETE FROM profile_snapshots WHERE username = ?", (normalized,))
            conn.execute("DELETE FROM scrapes WHERE username = ?", (normalized,))


default_repository = SqliteScraperRepository()

