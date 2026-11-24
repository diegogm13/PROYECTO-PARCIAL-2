# SA V2 — CI/CD con pruebas automatizadas y observabilidad

Sistema de usuarios (**Login, Register y CRUD**) con un pipeline de **GitHub Actions** que:

1. corre las pruebas de **backend con pytest** y las de **frontend con Playwright**;
2. envía el resultado de cada ejecución a **OpenObserve** por API HTTP/JSON (éxito o fallo, commit, rama y usuario);
3. **solo si todas las pruebas pasan**, se conecta por SSH a **AWS EC2**, actualiza los contenedores y registra el despliegue en OpenObserve.
   Si alguna prueba falla, el job de despliegue no corre (no hay conexión SSH) y se registra el evento `deploy_blocked`.

En la EC2, la aplicación está instrumentada con **OpenTelemetry (OTLP)** y envía logs, métricas y trazas a OpenObserve.
Los recursos del servidor (CPU, RAM, ancho de banda, temperatura y disco) se ven en dashboards de OpenObserve
y también en **Grafana + Prometheus**. **NGINX** funciona como proxy inverso en `0.0.0.0:80`.

## Arquitectura

```
                  git push
 Desarrollador ─────────────► GitHub ──► GitHub Actions (.github/workflows/ci-cd.yml)
                                          │
        ┌─────────────────────────────────┼──────────────────────────────────┐
        │ backend-tests                   │ e2e-tests                         │
        │ flake8 + pytest (cobertura ≥70%)│ docker compose up (nginx+api+db)  │
        │ 43 pruebas                      │ Playwright: 18 pruebas front + API│
        └───────────────┬─────────────────┴──────────────┬───────────────────┘
                        │                                │
            ┌───────────▼────────────┐       ┌───────────▼─────────────────────┐
            │ report-tests (always)  │       │ deploy (solo si TODO pasó)      │
            │ POST /api/default/     │       │ SSH → git reset → compose up    │
            │  cicd_pipeline/_json   │       │ health check → rollback si falla│
            │  cicd_tests/_json      │       │ POST evento "deploy"            │
            │ + deploy_blocked si    │       └───────────┬─────────────────────┘
            │   fallaron las pruebas │                   │
            └───────────┬────────────┘                   ▼
                        │          ┌──────────────────── AWS EC2 (Ubuntu + Docker) ──────────────────────┐
                        │          │                                                                      │
                        │          │  :80  NGINX (proxy inverso) ──► /        frontend (HTML/JS)          │
                        │          │                              ├► /api/    backend Flask ──► PostgreSQL│
                        │          │                              └► /grafana Grafana                     │
                        │          │                                            │ OTLP (logs/métricas/trazas)
                        │          │  node-exporter + temperatura ──┐           ▼                          │
                        │          │                                ├──► OTel Collector ──┬──► OpenObserve │
                        └──────────┼────────────────────────────────┼─────────────────────┼──► :5080       │
                                   │                                └──► Prometheus ◄─────┘   (dashboards, │
                                   │                                       │                    alertas)   │
                                   │                                    Grafana :3000                      │
                                   └──────────────────────────────────────────────────────────────────────┘
```

| Pizarrón | Implementación |
|---|---|
| Pytest → Back | `tests/backend` (pytest + cobertura) |
| Playwright → Front | `tests/e2e` (pytest-playwright: UI de Login/Register/CRUD + API vía NGINX) |
| GitHub Actions pipeline | `.github/workflows/ci-cd.yml` |
| Logs "Prueba Report" → OpenObserve | `scripts/report_openobserve.py` → streams `cicd_pipeline` y `cicd_tests` |
| T.R. / StatusCode / API (GET, POST…) / Timestamp | métricas `app_requests`, `app_request_duration`, `app_errors` + log `http_request` por petición |
| EC2: RAM, CPU, Ancho de banda, Temp °C | node-exporter + `monitoring/temperature/temperature.sh` → OTel Collector → OpenObserve |
| Grafana + Prometheus | `monitoring/prometheus.yml`, `monitoring/grafana/` (dashboard ya cargado) |
| 0.0.0.0 NGINX + proxy inverso | `nginx/default.conf` |

## Estructura

```
SA_V2/
├── .github/workflows/ci-cd.yml      # Pipeline CI/CD
├── backend/                         # API Flask
│   ├── app/
│   │   ├── routes/ (auth, users, system)
│   │   ├── models.py  security.py (JWT)  validators.py
│   │   ├── telemetry.py             # OpenTelemetry: trazas, métricas y logs (OTLP)
│   │   └── logging_config.py        # Logs JSON con trace_id
│   ├── Dockerfile  requirements.txt  wsgi.py
├── frontend/                        # index.html (login), register.html, users.html (CRUD)
├── nginx/                           # Proxy inverso + archivos estáticos
├── monitoring/
│   ├── otel-collector.yaml          # OTLP + node-exporter → OpenObserve / Prometheus
│   ├── prometheus.yml
│   ├── temperature/temperature.sh   # Métrica de temperatura
│   └── grafana/                     # Datasource + dashboard
├── scripts/
│   ├── report_openobserve.py        # Pipeline → OpenObserve (HTTP/JSON)
│   ├── openobserve_setup.py         # Crea dashboards y alertas en OpenObserve
│   ├── deploy.sh                    # Lo ejecuta el pipeline en la EC2 (con rollback)
│   └── setup_ec2.sh                 # Instalación inicial de la EC2
├── tests/
│   ├── backend/                     # pytest (43 pruebas)
│   └── e2e/                         # Playwright (18 pruebas)
├── docker-compose.yml               # App + perfil "monitoring"
└── .env.example
```

## Endpoints

Todas las respuestas tienen la forma `{"statusCode": 200, "data": ...}` o `{"statusCode": 4xx, "error": "..."}`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/api/health` | — | Estado, base de datos, versión y commit desplegado |
| POST | `/api/auth/register` | — | Registro `{name, email, password}` → 201 |
| POST | `/api/auth/login` | — | Login `{email, password}` → `{token, user}` |
| GET | `/api/auth/me` | JWT | Usuario actual |
| GET | `/api/users` | JWT | Listar usuarios |
| GET | `/api/users/{id}` | JWT | Consultar usuario |
| POST | `/api/users` | JWT | Crear `{name, email, password, role?, active?}` |
| PUT | `/api/users/{id}` | JWT | Actualizar uno o varios campos |
| DELETE | `/api/users/{id}` | JWT | Eliminar (no puede eliminarse a sí mismo) |
| GET | `/api/demo/error` | — | Lanza una excepción a propósito (sirve para mostrar errores en OpenObserve) |

## Comandos locales

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m playwright install chromium

# Backend (pytest + cobertura)
pytest --cov=backend/app --cov-report=term-missing

# Levantar la app (NGINX + backend + PostgreSQL) en http://localhost
docker compose up -d --build --wait

# Frontend E2E (Playwright) contra la app levantada
pytest tests/e2e
pytest tests/e2e --headed --slowmo 300     # viendo el navegador

docker compose down
```

## Configuración de AWS EC2 (una sola vez)

1. **Launch instance**: Ubuntu Server 24.04, tipo **t3.small (2 GB) o mayor**. El script agrega 2 GB de swap,
   porque en la instancia corren la app, OpenObserve, Grafana y Prometheus. Disco: 20 GB.
2. Key pair `.pem` (nunca se sube al repo). Asignar una **Elastic IP**.
3. **Security Group**, reglas de entrada:

   | Puerto | Uso | Origen |
   |---|---|---|
   | 22 | SSH (GitHub Actions) | 0.0.0.0/0 |
   | 80 | NGINX: app + `/grafana` | 0.0.0.0/0 |
   | 5080 | OpenObserve (UI y API del pipeline) | 0.0.0.0/0 |
   | 3000 | Grafana directo (opcional) | 0.0.0.0/0 |

   **No** abrir 9100 (node-exporter) ni 9090 (Prometheus).

4. Instalar y levantar todo:

   ```bash
   ssh -i llave.pem ubuntu@<IP_EC2>
   curl -fsSL https://raw.githubusercontent.com/<usuario>/<repo>/main/scripts/setup_ec2.sh | sh -s https://github.com/<usuario>/<repo>.git
   nano ~/sa-v2/.env          # cambiar contraseñas
   exit                       # volver a entrar para usar docker sin sudo
   ssh -i llave.pem ubuntu@<IP_EC2>
   cd ~/sa-v2 && GIT_SHA=$(git rev-parse HEAD) docker compose up -d --build
   ```

5. Crear los dashboards y las alertas de OpenObserve (desde la EC2 o desde tu PC):

   ```bash
   OPENOBSERVE_URL=http://<IP_EC2>:5080 OPENOBSERVE_USER=<user> OPENOBSERVE_PASSWORD=<pass> \
     python3 scripts/openobserve_setup.py
   ```

## GitHub Secrets

*Settings → Secrets and variables → Actions*:

| Secreto | Valor |
|---|---|
| `EC2_HOST` | IP pública (Elastic IP) de la EC2 |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Contenido completo del `.pem` |
| `OPENOBSERVE_URL` | `http://<IP_EC2>:5080` |
| `OPENOBSERVE_USER` | El mismo `OPENOBSERVE_USER` del `.env` |
| `OPENOBSERVE_PASSWORD` | El mismo `OPENOBSERVE_PASSWORD` del `.env` |

## Observabilidad

**OpenObserve** (`http://<IP_EC2>:5080`):

| Señal | Dónde verla |
|---|---|
| Ejecuciones del pipeline | Logs → stream `cicd_pipeline` (event = tests / deploy / deploy_blocked) |
| Resultado de cada prueba | Logs → stream `cicd_tests` |
| Logs de la app y excepciones | Logs → stream `default` (`event = http_request`, `severity = ERROR`) |
| Trazas por petición (HTTP → SQL) | Traces |
| Métricas por endpoint | Metrics → `app_requests`, `app_request_duration_bucket`, `app_errors` |
| Recursos de la EC2 | Metrics → `node_cpu_seconds_total`, `node_memory_*`, `node_network_*`, `node_temperature_celsius` |

Dashboards que crea `openobserve_setup.py`:

- **SA - Vista general**: pipeline, trazas, CPU, RAM, ancho de banda y temperatura en una sola pantalla (criterio 3).
- **SA - Infraestructura EC2**
- **SA - Aplicación**
- **SA - Pipeline CI/CD**

Alertas: pipeline fallido, 5xx/excepciones, CPU > 80 %, RAM > 85 %, temperatura > 70 °C y latencia p95 > 1 s.

**Grafana** (`http://<IP_EC2>/grafana/`): dashboard *SA - EC2 y Aplicación* con los mismos indicadores, leídos desde Prometheus.

> **Temperatura:** las instancias EC2 virtualizadas normalmente no exponen sensores térmicos al sistema operativo.
> `temperature.sh` usa el sensor real si existe (`source="sensor"`). Si no existe, publica una estimación
> calculada a partir del uso de CPU (`source="estimado"`).

## Demostración en clase

**Push con fallos** (criterio 1). Romper un componente visual, por ejemplo en `frontend/index.html`:

```html
<button class="block" type="submit" data-testid="login-submit">Ingresar</button>   <!-- antes: Entrar -->
```

```bash
git commit -am "Demo: cambia texto del botón de login (falla)" && git push
```

→ Playwright falla (`test_pagina_login_carga`) → `report-tests` registra `tests: failure` y `deploy_blocked` en OpenObserve
→ el job `deploy` aparece como *skipped* (no hay conexión SSH) → la alerta `sa_pipeline_fallido` se activa.

**Push exitoso** (criterio 2). Revertir el cambio (`git revert HEAD` o regresar el texto a "Entrar") y hacer push
→ todas las pruebas pasan → `deploy` actualiza los contenedores en EC2 → evento `deploy: success` en OpenObserve
→ `http://<IP_EC2>/api/health` muestra el nuevo `commit`.
