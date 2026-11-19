import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Cargar el .env ubicado en la misma carpeta que main.py (backend/.env)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from shared.utils.network import get_local_ip
from contexts.scraping.infrastructure.tiktok_service import TikTokScraperService, ScrapeOptions
from contexts.psychometrics.infrastructure.psychometric_service import BigFiveEmbeddingService
from contexts.advisory.infrastructure.gemini_service import GeminiAuditService
from contexts.storage.repository import default_repository
from contexts.analytics.analytics_service import default_dashboard_builder, AccountBenchmarker
from contexts.exporters.exporter_service import default_exporter_registry, XLSX_DISPONIBLE

app = FastAPI(title="VerifIA", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar base de datos SQLite
default_repository.initialize()

# Inicialización diferida / lazy del servicio de Embeddings
psychometric_service = BigFiveEmbeddingService()

# Semáforo para controlar la concurrencia y proteger recursos
scrape_semaphore = asyncio.Semaphore(2)


class ScrapeRequest(BaseModel):
    username: str
    target: str = "all"
    modo: str = "hibrido"
    max_videos: int = 19
    max_comment_videos: int = 2
    max_following: int = 20
    max_followers: int = 20
    headless: bool = True
    bloquear_multimedia: bool = True
    sesion_persistente: bool = False
    humanizar: bool = True


class BigFiveRequest(BaseModel):
    profile: dict
    videos: list = []
    comments: list = []


@app.get("/api/info")
def get_system_info():
    """Devuelve la configuración de red y disponibilidad del sistema para acceso LAN/QR."""
    return {
        "local_ip": get_local_ip(),
        "port": 8000,
        "xlsx_disponible": XLSX_DISPONIBLE
    }


@app.post("/api/analyze/big-five")
def analyze_big_five_endpoint(payload: BigFiveRequest):
    """Calcula o recalcula el análisis psicométrico Big Five (OCEAN)."""
    return psychometric_service.analyze(
        profile=payload.profile,
        videos=payload.videos,
        comments=payload.comments
    )


@app.post("/api/scrape")
async def run_scrape_endpoint(payload: ScrapeRequest):
    """Ejecución HTTP síncrona de extracción y guardado."""
    async with scrape_semaphore:
        service = TikTokScraperService()
        opts = {
            "modo": payload.modo,
            "max_videos": payload.max_videos,
            "max_posts": payload.max_videos,
            "max_comment_videos": payload.max_comment_videos,
            "max_following": payload.max_following,
            "max_followers": payload.max_followers,
            "headless": payload.headless,
            "bloquear_multimedia": payload.bloquear_multimedia,
            "sesion_persistente": payload.sesion_persistente,
            "humanizar": payload.humanizar,
        }
        results = await service.scrape(
            username=payload.username,
            target=payload.target,
            options_dict=opts
        )

        # Añadir psicometría
        results["psychometrics"] = psychometric_service.analyze(
            profile=results.get("profile", {}),
            videos=results.get("videos", []),
            comments=results.get("comments", [])
        )

        # Persistir en SQLite para historial y analítica
        try:
            scrape_id = default_repository.save_scrape(results)
            results["scrape_id"] = scrape_id
        except Exception as e:
            print(f"[WARN] No se pudo guardar scrape en base de datos: {e}")

        return results


@app.websocket("/ws/scrape")
async def websocket_scrape_endpoint(websocket: WebSocket):
    """Streaming de logs en vivo y resultados finales vía WebSocket."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        username = data.get("username", "")
        target = data.get("target", "all")
        
        modo = data.get("modo", "hibrido")
        max_videos = int(data.get("max_videos", 19))
        max_comment_videos = int(data.get("max_comment_videos", 2))
        max_following = int(data.get("max_following", 20))
        max_followers = int(data.get("max_followers", 20))
        headless = bool(data.get("headless", True))
        bloquear_multimedia = bool(data.get("bloquear_multimedia", True))

        async def send_log_to_client(message: str):
            await websocket.send_json({"type": "log", "message": message})

        if scrape_semaphore.locked():
            await send_log_to_client("[QUEUE] Servidor ocupado. Tu solicitud está en espera...")

        async with scrape_semaphore:
            service = TikTokScraperService(log_callback=send_log_to_client)
            opts = {
                "modo": modo,
                "max_videos": max_videos,
                "max_posts": max_videos,
                "max_comment_videos": max_comment_videos,
                "max_following": max_following,
                "max_followers": max_followers,
                "headless": headless,
                "bloquear_multimedia": bloquear_multimedia,
                "humanizar": True
            }

            final_data = await service.scrape(
                username=username,
                target=target,
                options_dict=opts
            )

            # Fase de Embeddings / Psicometría
            await send_log_to_client("[AI] Analizando semántica y distribución de rasgos Big Five (OCEAN)...")
            final_data["psychometrics"] = psychometric_service.analyze(
                profile=final_data.get("profile", {}),
                videos=final_data.get("videos", []),
                comments=final_data.get("comments", [])
            )

            # Persistencia en base de datos local
            try:
                scrape_id = default_repository.save_scrape(final_data)
                final_data["scrape_id"] = scrape_id
                await send_log_to_client(f"[DB] Snapshot guardado en base de datos local (ID #{scrape_id}).")
            except Exception as e:
                await send_log_to_client(f"[DB WARN] Error guardando snapshot: {e}")

            await send_log_to_client(f"[AI] Arquetipo detectado: {final_data['psychometrics']['arquetipo']}")
            await websocket.send_json({"type": "result", "data": final_data})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        err_msg = str(e).strip() or f"{type(e).__name__}: {repr(e)}"
        await websocket.send_json({"type": "error", "message": err_msg})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


gemini_service = None
try:
    gemini_service = GeminiAuditService()
except Exception as e:
    print(f"[WARN] Gemini no inicializado: {e}")


class GeminiReportRequest(BaseModel):
    profile: dict
    psychometrics: dict
    frequency: str = "Moderada"


@app.post("/api/ai/gemini-report")
def get_gemini_report_endpoint(payload: GeminiReportRequest):
    if not gemini_service:
        return {"error": "Servicio de Gemini no configurado en el servidor"}
    
    return gemini_service.generate_creator_report(
        profile=payload.profile,
        psychometrics=payload.psychometrics,
        frequency=payload.frequency
    )


# --- NUEVOS ENDPOINTS: HISTORIAL, CUENTAS Y EXPORTACIÓN ---

@app.get("/api/scrapes")
def list_scrapes_endpoint(username: Optional[str] = None):
    """Lista los scrapes guardados en el repositorio."""
    return default_repository.list_scrapes(username)


@app.get("/api/scrapes/{scrape_id}")
def get_scrape_endpoint(scrape_id: int):
    """Obtiene el resultado completo de un scrape guardado."""
    result = default_repository.get_scrape_result(scrape_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scrape no encontrado")
    return result


@app.get("/api/accounts")
def list_accounts_endpoint():
    """Lista las cuentas registradas con métricas de benchmarking."""
    accounts = default_repository.list_accounts()
    return AccountBenchmarker.compare(accounts)


@app.post("/api/accounts/{username}/delete")
def delete_account_endpoint(username: str):
    """Elimina una cuenta y su historial de la base de datos."""
    default_repository.delete_account(username)
    return {"ok": True}


@app.get("/api/export/{scrape_id}.{fmt}")
def export_scrape_endpoint(scrape_id: int, fmt: str):
    """Exporta un scrape específico a formato JSON, CSV o Excel (XLSX)."""
    result = default_repository.get_scrape_result(scrape_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scrape no encontrado")

    fmt_clean = fmt.lower().strip()
    exporter = default_exporter_registry.get_scrape_exporter(fmt_clean)
    if not exporter:
        raise HTTPException(status_code=400, detail=f"Formato '{fmt}' no soportado")

    if fmt_clean == "xlsx" and not XLSX_DISPONIBLE:
        raise HTTPException(status_code=501, detail="openpyxl no está instalado")

    username = result.get("usuario") or result.get("username") or "tiktok"
    filename = f"tiktok_{username}_scrape_{scrape_id}.{fmt_clean}"

    dashboard = result.get("analytics")
    if not dashboard:
        history = default_repository.get_profile_history(username)
        velocities = default_repository.get_post_velocity(username)
        dashboard = default_dashboard_builder.build(result, history, velocities)

    content = exporter.export_scrape(result, dashboard)
    return Response(
        content=content,
        media_type=exporter.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/export/dataset.{fmt}")
def export_dataset_endpoint(fmt: str, username: Optional[str] = None):
    """Exporta el dataset global o de una cuenta en formato CSV, XLSX, JSON o SQLite (db)."""
    fmt_clean = fmt.lower().strip()

    if fmt_clean == "db":
        if not default_repository.db_path.exists():
            raise HTTPException(status_code=404, detail="Base de datos no encontrada")
        return FileResponse(
            path=str(default_repository.db_path),
            filename="tiktok_dataset.db",
            media_type="application/x-sqlite3"
        )

    exporter = default_exporter_registry.get_dataset_exporter(fmt_clean)
    if not exporter:
        raise HTTPException(status_code=400, detail=f"Formato '{fmt}' no soportado")

    if fmt_clean == "xlsx" and not XLSX_DISPONIBLE:
        raise HTTPException(status_code=501, detail="openpyxl no está instalado")

    posts = default_repository.get_posts_dataset(username)
    profiles = default_repository.get_profiles_dataset() if fmt_clean != "csv" else []

    target_name = username or "global"
    filename = f"dataset_{target_name}.{fmt_clean}"
    content = exporter.export_dataset(posts, profiles)

    return Response(
        content=content,
        media_type=exporter.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)