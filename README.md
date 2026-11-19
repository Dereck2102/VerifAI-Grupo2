<div align="center">

# VerifAI Scraper Pro

### Auditoría y analítica avanzada de perfiles públicos de TikTok

[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Web-React%2019-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Mobile](https://img.shields.io/badge/Móvil-React%20Native%20%2B%20Expo-000020?logo=expo&logoColor=white)](https://expo.dev/)
[![Playwright](https://img.shields.io/badge/Scraping-Playwright%20Async-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Gemini](https://img.shields.io/badge/IA-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)

**De datos dispersos a inteligencia estratégica para creadores de contenido, marcas y analistas.**

</div>

---

## 📌 Descripción del Proyecto

**VerifAI Scraper Pro** es una plataforma integral de auditoría, métricas y diagnóstico para cuentas públicas de TikTok. Combina un motor de extracción asíncrono de alto rendimiento sin requerir inicio de sesión, almacenamiento relacional histórico en SQLite, un motor de 12 reglas analíticas cuantitativas, análisis psicométrico Big Five (OCEAN) y generación de reportes ejecutivos con Google Gemini.

La plataforma permite operar tanto desde navegador web como desde dispositivos móviles en la red local mediante código QR interactivo.

---

## ✨ Características Principales

* ⚡ **Scraping sin Login:** Extracción inmediata de perfiles públicos sin necesidad de cuentas ni sesiones manuales.
* 🛡️ **Alto Rendimiento y Ahorro de Recursos:** Filtrado de red que aborta descargas pesadas (imágenes, video, fuentes), reduciendo el consumo de memoria RAM y ancho de banda en más de un 70%.
* 🎯 **4 Modos de Extracción:**
  * `Híbrido`: Intercepción de API interna + lectura de DOM (máxima cobertura).
  * `Red / API`: Captura exclusiva de paquetes JSON de TikTok.
  * `Visual (DOM)`: Lectura de elementos visuales renderizados.
  * `Rápido`: Obtención del lote inicial sin desplazamiento (ideal para previsualizaciones).
* 📊 **Motor Analítico (12 Reglas):** Diagnóstico automático sin consumo de cuota (engagement rate, mejor horario, mejor día, duraciones óptimas, hashtags de alto impacto, videos virales y comparación de formatos).
* 💾 **Persistencia SQLite:** Almacenamiento automático de capturas históricas, evolución de seguidores y velocidad de crecimiento de videos (vistas/hora).
* 📑 **Exportación Profesional Multi-formato:** Generación de reportes en Excel multi-hoja (`.xlsx`) estilizado con colores temáticos y filtros, CSV, JSON y descarga directa de la base de datos `.db`.
* 🧠 **Psicometría Big Five (OCEAN):** Estimación semántica del tono del creador con carga *lazy-load* y afinidad comercial con 10 nichos de mercado.
* 🤖 **Auditoría Ejecutiva con Gemini:** Diagnóstico cualitativo, estrategia de monetización y recomendaciones de crecimiento mediante modelos generativos de Google.
* 📱 **Acceso Móvil LAN & QR:** Detección de IP local para acceder instantáneamente desde teléfonos móviles o tablets en la misma red Wi-Fi.
* 🐳 **Preparado para Producción con Docker:** Configuración lista para despliegue con un solo comando.

---

## 🚀 Inicio Rápido

### Opción 1: Con Docker (Recomendada)

Levanta el backend (FastAPI + Playwright) y el frontend (React + Nginx) en contenedores aislados:

```bash
docker compose up --build
```

* **Frontend Web:** `http://localhost:5173`
* **Backend API & Swagger:** `http://localhost:8000/docs`

---

### Opción 2: Ejecución Local

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

#### 3. Aplicación Móvil (React Native + Expo)

```bash
cd mobile
npm install
npx expo start
```

---

## 🏗️ Arquitectura del Sistema

```
VerifAI-Grupo2/
├── backend/
│   ├── contexts/
│   │   ├── scraping/         # Motor Playwright asíncrono y normalizadores
│   │   ├── analytics/        # Motor de 12 reglas analíticas e indicadores
│   │   ├── storage/          # Persistencia SQLite, snapshots e historial
│   │   ├── exporters/        # Exportación a Excel (.xlsx), CSV y JSON
│   │   ├── psychometrics/    # Modelo Big Five OCEAN (lazy loading)
│   │   └── advisory/         # Cliente del modelo Google Gemini
│   ├── shared/utils/         # Utilidades de red e IP local
│   ├── main.py               # API FastAPI y servidor WebSocket
│   ├── requirements.txt      # Dependencias del servidor
│   └── Dockerfile            # Imagen backend con Playwright
├── frontend/
│   ├── src/
│   │   ├── components/       # Componentes visuales y consola en vivo
│   │   ├── pages/            # Extractor, Métricas y Acceso Móvil LAN
│   │   └── services/         # Conexión WebSocket y API
│   ├── nginx.conf            # Proxy inverso de producción
│   └── Dockerfile            # Construcción multi-stage de frontend
├── mobile/                   # App móvil multiplataforma (Expo)
└── docker-compose.yml        # Orquestación de contenedores
```

---

## 👥 Equipo de Desarrollo y Créditos

Proyecto académico desarrollado en la **Facultad de Ingeniería y Ciencias Aplicadas (FICA)** de la **Universidad Central del Ecuador (UCE)**:

* **Dereck Amacoria**: Integración y desarrollo del motor de scraping asíncrono (*tiktokscrapper*), implementación de las 12 reglas analíticas, persistencia SQLite y desarrollo de los exportadores multi-formato (Excel `.xlsx`, CSV, JSON y base de datos).
* **Xavier Monteros**: Arquitectura fundacional de VerifAI, diseño del flujo de auditoría, estructura de contextos y desarrollo de interfaces y servicios principales.
* **Ariel Guerrón**: Documentación técnica integral, diseño y redacción del README, manuales de usuario y especificaciones de componentes.
* **Cristian Araujo**: Optimización de recursos del sistema, bloqueo de multimedia/ancho de banda, control de concurrencia y pruebas de rendimiento.

### 🤖 Asistencia Técnica de Modelos de Inteligencia Artificial
* Agradecimiento a los modelos de lenguaje **Claude Sonnet 4.6**, **Gemini 3.8 Flash** y al entorno **Google DeepMind Antigravity**, utilizados como asistentes de copiloto de programación, refactorización de código, análisis de rendimiento y diseño de la arquitectura asíncrona.

---

## ⚖️ Uso Responsable y Ético

* Este proyecto recopila exclusivamente información accesible de forma pública en TikTok.
* Se recomienda utilizar límites de extracción razonables para evitar sobrecargar servidores y respetar las condiciones de servicio de las plataformas auditadas.
* El análisis psicométrico OCEAN es una estimación semántica exploratoria con fines analíticos y de orientación comercial, no una evaluación psicológica formal.
