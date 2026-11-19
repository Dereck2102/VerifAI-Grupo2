<div align="center">

# VerifIA

### Auditoria y analitica avanzada de perfiles publicos de TikTok

[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Web-React%2019-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Mobile](https://img.shields.io/badge/Movil-React%20Native%20%2B%20Expo-000020?logo=expo&logoColor=white)](https://expo.dev/)
[![Playwright](https://img.shields.io/badge/Scraping-Playwright%20Async-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Gemini](https://img.shields.io/badge/IA-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)

**De datos dispersos a inteligencia estrategica para creadores de contenido, marcas y analistas.**

</div>

---

## Descripcion del Proyecto

**VerifIA** es una plataforma integral de auditoria, metricas y diagnostico para cuentas publicas de TikTok. Combina un motor de extraccion asincrono de alto rendimiento sin requerir inicio de sesion, almacenamiento relacional historico en SQLite, un motor de 12 reglas analiticas cuantitativas, analisis psicometrico Big Five (OCEAN) y generacion de reportes ejecutivos con Google Gemini.

La plataforma permite operar tanto desde navegador web como desde dispositivos moviles en la red local mediante codigo QR interactivo.

---

## Caracteristicas Principales

* **Scraping sin Login:** Extraccion inmediata de perfiles publicos sin necesidad de cuentas ni sesiones manuales.
* **Alto Rendimiento y Ahorro de Recursos:** Filtrado de red que aborta descargas pesadas (imagenes, video, fuentes), reduciendo el consumo de memoria RAM y ancho de banda en mas de un 70%.
* **4 Modos de Extraccion:**
  * `Hibrido`: Intercepcion de API interna + lectura de DOM (maxima cobertura).
  * `Red / API`: Captura exclusiva de paquetes JSON de TikTok.
  * `Visual (DOM)`: Lectura de elementos visuales renderizados.
  * `Rapido`: Obtencion del lote inicial sin desplazamiento (ideal para previsualizaciones).
* **Motor Analitico (12 Reglas):** Diagnostico automatico sin consumo de cuota (engagement rate, mejor horario, mejor dia, duraciones optimas, hashtags de alto impacto, videos virales y comparacion de formatos).
* **Persistencia SQLite:** Almacenamiento automatico de capturas historicas, evolucion de seguidores y velocidad de crecimiento de videos (vistas/hora).
* **Exportacion Profesional Multi-formato:** Generacion de reportes en Excel multi-hoja (`.xlsx`) estilizado con colores tematicos y filtros, CSV, JSON y descarga directa de la base de datos `.db`.
* **Psicometria Big Five (OCEAN):** Estimacion semantica del tono del creador con carga *lazy-load* y afinidad comercial con 10 nichos de mercado.
* **Auditoria Ejecutiva con Gemini:** Diagnostico cualitativo, estrategia de monetizacion y recomendaciones de crecimiento mediante modelos generativos de Google.
* **Acceso Movil LAN & QR:** Deteccion de IP local para acceder instantaneamente desde telefonos moviles o tablets en la misma red Wi-Fi.
* **Preparado para Produccion con Docker:** Configuracion lista para despliegue con un solo comando.

---

## Inicio Rapido

### Opcion 1: Con Docker (Recomendada)

Levanta el backend (FastAPI + Playwright) y el frontend (React + Nginx) en contenedores aislados:

```bash
docker compose up --build
```

* **Frontend Web:** `http://localhost:5173`
* **Backend API & Swagger:** `http://localhost:8000/docs`

---

### Opcion 2: Ejecucion Local

#### 1. Backend (Python 3.10+)

```bash
cd backend
python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

# Iniciar servidor
python main.py
```

> **Nota:** Configura tu `GOOGLE_API_KEY` en `backend/.env` si deseas habilitar los reportes de Google Gemini.

#### 2. Frontend (Node.js 18+)

```bash
cd frontend
npm install
npm run dev
```

#### 3. Aplicacion Movil (React Native + Expo)

```bash
cd mobile
npm install
npx expo start
```

---

## Arquitectura del Sistema

```
VerifIA/
├── backend/
│   ├── contexts/
│   │   ├── scraping/         # Motor Playwright asincrono y normalizadores
│   │   ├── analytics/        # Motor de 12 reglas analiticas e indicadores
│   │   ├── storage/          # Persistencia SQLite, snapshots e historial
│   │   ├── exporters/        # Exportacion a Excel (.xlsx), CSV y JSON
│   │   ├── psychometrics/    # Modelo Big Five OCEAN (lazy loading)
│   │   └── advisory/         # Cliente del modelo Google Gemini
│   ├── shared/utils/         # Utilidades de red e IP local
│   ├── main.py               # API FastAPI y servidor WebSocket
│   ├── requirements.txt      # Dependencias del servidor
│   └── Dockerfile            # Imagen backend con Playwright
├── frontend/
│   ├── src/
│   │   ├── components/       # Componentes visuales y consola en vivo
│   │   ├── pages/            # Extractor, Metricas y Acceso Movil LAN
│   │   └── services/         # Conexion WebSocket y API
│   ├── nginx.conf            # Proxy inverso de produccion
│   └── Dockerfile            # Construccion multi-stage de frontend
├── mobile/                   # App movil multiplataforma (Expo)
└── docker-compose.yml        # Orquestacion de contenedores
```

---

## Equipo de Desarrollo y Creditos

Proyecto academico desarrollado en la **Facultad de Ingenieria y Ciencias Aplicadas (FICA)** de la **Universidad Central del Ecuador (UCE)**:

* **Dereck Amacoria**: Integracion y desarrollo del motor de scraping asincrono (*tiktokscrapper*), implementacion de las 12 reglas analiticas, persistencia SQLite y desarrollo de los exportadores multi-formato (Excel `.xlsx`, CSV, JSON y base de datos).
* **Xavier Monteros**: Arquitectura fundacional de VerifIA, diseno del flujo de auditoria, estructura de contextos y desarrollo de interfaces y servicios principales.
* **Ariel Guerron**: Documentacion tecnica integral, diseno y redaccion del README, manuales de usuario y especificaciones de componentes.
* **Cristian Araujo**: Optimizacion de recursos del sistema, bloqueo de multimedia/ancho de banda, control de concurrencia y pruebas de rendimiento.

### Asistencia Tecnica de Modelos de Inteligencia Artificial
* Agradecimiento a los modelos de lenguaje **Claude Sonnet 4.6**, **Gemini 3.8 Flash** y al entorno **Google DeepMind Antigravity**, utilizados como asistentes de copiloto de programacion, refactorizacion de codigo, analisis de rendimiento y diseno de la arquitectura asincrona.

---

## Uso Responsable y Etico

* Este proyecto recopila exclusivamente informacion accesible de forma publica en TikTok.
* Se recomienda utilizar limites de extraccion razonables para evitar sobrecargar servidores y respetar las condiciones de servicio de las plataformas auditadas.
* El analisis psicometrico OCEAN es una estimacion semantica exploratoria con fines analiticos y de orientacion comercial, no una evaluacion psicologica formal.
