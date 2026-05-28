
# Plan De Implementación: Plataforma De Auditoría RAG Timing

## Resumen

Se implementará el proyecto por fases pequeñas y verticales, combinando backend y frontend cuando tenga sentido. No haremos primero “todo el backend” y luego “todo el frontend”, porque eso retrasaría mucho la validación visual y funcional. La estrategia será:

- Primero cimentar infraestructura, Docker Compose, base de datos, autenticación y worker.
- Después construir flujos completos: targets, datasets, ejecución, resultados.
- Finalmente añadir análisis estadístico, experimento de caché, hardening y documentación.

El plan se documentará como `Auditoria_RAG_Timing/PLAN_IMPLEMENTACION.md` cuando se pase a modo implementación.

## Fase 0: Preparación Del Proyecto

Objetivo: dejar preparada la carpeta de aplicación sin mezclarla con las PoC antiguas.

Tareas:

- Crear estructura base dentro de `Auditoria_RAG_Timing/`.
- Añadir `README.md`, `.env.example`, `docker-compose.yml`.
- Crear carpetas:
  - `backend/`
  - `frontend/`
  - `mock-rag/`
- Mantener `ESPECIFICACION_CRITICA.md` como documento de requisitos.
- Crear `PLAN_IMPLEMENTACION.md` con este plan.
- Actualizar `.gitignore` para caches, `.env`, volúmenes locales, `node_modules`, builds y ficheros temporales.

Criterio de aceptación:

- La carpeta de la aplicación queda separada del material experimental del TFG.
- El proyecto tiene una estructura clara y preparada para Compose.

## Fase 1: Docker Compose E Infraestructura Base

Objetivo: levantar todos los servicios necesarios desde el inicio.

Servicios:

- `postgres`
- `redis`
- `backend`
- `worker`
- `frontend`
- `mock-rag`

Tareas:

- Configurar Docker Compose con red interna.
- Añadir volúmenes:
  - `postgres_data`
  - `datasets_data`
- Añadir `.env.example` con:
  - `DATABASE_URL`
  - `REDIS_URL`
  - `JWT_SECRET_KEY`
  - `SECRET_ENCRYPTION_KEY`
  - `ADMIN_EMAIL`
  - `ADMIN_PASSWORD`
  - `MAX_QUERIES_PER_AUDIT=5000`
  - `MAX_CONCURRENT_AUDITS=2`
- Crear Dockerfile de backend.
- Crear Dockerfile de frontend.
- Crear Dockerfile de `mock-rag`.

Criterio de aceptación:

- `docker compose up` levanta todos los servicios.
- Backend responde a `/health`.
- Frontend carga una pantalla inicial.
- Postgres y Redis están accesibles desde backend y worker.
- `mock-rag` responde a un endpoint de prueba.

## Fase 2: Backend Base, Configuración Y Base De Datos

Objetivo: preparar FastAPI, SQLAlchemy async, Alembic y configuración central.

Tareas:

- Inicializar backend con Python 3.11+.
- Configurar FastAPI async.
- Configurar Pydantic v2.
- Configurar SQLAlchemy 2.0 async con `asyncpg`.
- Configurar Alembic.
- Crear módulo de configuración con variables de entorno.
- Crear sesión async de base de datos.
- Crear logging estructurado básico.
- Crear endpoint `/health`.
- Crear primera migración vacía o base.

Modelos iniciales:

- `User`
- `Target`
- `Dataset`
- `AuditSession`
- `AuditResult`

Criterio de aceptación:

- Backend arranca dentro de Docker.
- Alembic puede aplicar migraciones.
- La conexión a PostgreSQL funciona.
- Los modelos quedan listos para fases posteriores.

## Fase 3: Autenticación Admin Desde El Inicio

Objetivo: proteger la aplicación desde el primer momento.

Tareas backend:

- Crear tabla `users`.
- Crear hash de password con `argon2` o `bcrypt`.
- Crear admin inicial desde `ADMIN_EMAIL` y `ADMIN_PASSWORD` si no hay usuarios.
- Implementar JWT.
- Endpoints:
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
  - `POST /api/v1/auth/logout`
- Proteger todos los endpoints bajo `/api/v1` salvo auth y health.

Tareas frontend:

- Crear pantalla `/login`.
- Guardar token de sesión.
- Añadir guard de rutas privadas.
- Añadir layout base con sidebar y topbar.

Criterio de aceptación:

- Sin login no se accede a la aplicación.
- El admin se crea automáticamente desde variables de entorno.
- El frontend mantiene sesión y permite cerrar sesión.

## Fase 4: Target Manager

Objetivo: poder registrar sistemas RAG objetivo.

Backend:

- Modelo `targets` con:
  - `id`
  - `name`
  - `endpoint_url`
  - `http_method`
  - `headers_encrypted`
  - `payload_template`
  - `timeout_seconds`
  - `verify_tls`
  - timestamps
- Cifrar headers sensibles usando `SECRET_ENCRYPTION_KEY`.
- Validar:
  - URL válida.
  - Método `POST` o `GET`.
  - Para `POST`, `payload_template` contiene `{{QUERY}}`.
  - Para `GET`, `endpoint_url` contiene `{{QUERY}}`.
- Endpoints:
  - `GET /api/v1/targets`
  - `POST /api/v1/targets`
  - `GET /api/v1/targets/{id}`
  - `PUT /api/v1/targets/{id}`
  - `DELETE /api/v1/targets/{id}`
  - `POST /api/v1/targets/{id}/test`

Frontend:

- Vista `/targets`.
- Tabla de targets.
- Modal o página de creación/edición.
- Editor JSON simple para headers y payload.
- Mensaje claro recomendando `POST`.
- Enmascarar headers sensibles.
- Botón “Test Target”.

Criterio de aceptación:

- Se puede crear, editar, listar, probar y borrar un target.
- Los headers no se guardan en claro.
- El flujo principal favorece `POST`.

## Fase 5: Dataset Manager

Objetivo: subir y validar bancos de queries.

Backend:

- Modelo `datasets`.
- Guardar archivos en `/data/datasets`.
- Calcular `sha256`.
- Validar JSON:
  - raíz array;
  - cada elemento tiene `query`, `frequency`, `length`;
  - `frequency`: `high | medium | low | null`;
  - `length`: `short | medium | long`;
  - permitir campos extra e ignorarlos;
  - máximo 5000 queries ejecutables.
- Endpoints:
  - `GET /api/v1/datasets`
  - `POST /api/v1/datasets/upload`
  - `GET /api/v1/datasets/{id}`
  - `GET /api/v1/datasets/{id}/preview`
  - `DELETE /api/v1/datasets/{id}`
- Bloquear borrado normal si hay auditorías asociadas.

Frontend:

- Vista `/datasets`.
- Drag & drop de JSON.
- Tabla de datasets.
- Preview de primeras queries.
- Resumen por frecuencia y longitud.
- Mensajes de validación claros.

Criterio de aceptación:

- Se pueden subir datasets válidos.
- Se rechazan datasets inválidos.
- Se ve distribución por etiquetas.
- No se borran accidentalmente datasets usados.

## Fase 6: Mock RAG

Objetivo: tener un target simulado para desarrollo, demo y tests.

Tareas:

- Crear servicio `mock-rag`.
- Endpoint:
  - `POST /chat`
- Aceptar payload con `question`.
- Responder con JSON simple.
- Simular latencias según contenido:
  - `high`: baja latencia.
  - `medium`: latencia media.
  - `low`: latencia alta.
  - `null`: configurable o latencia alta.
- Añadir jitter aleatorio.
- Añadir endpoint health.

Criterio de aceptación:

- La aplicación puede auditar `mock-rag`.
- Las gráficas muestran diferencias artificiales esperadas.
- Queda documentado que no demuestra vulnerabilidad real, solo valida la herramienta.

## Fase 7: Worker Con Arq Y Motor De Auditoría

Objetivo: ejecutar auditorías largas mediante cola y workers.

Backend:

- Configurar Arq con Redis.
- `POST /api/v1/audits/start`:
  - valida target y dataset;
  - crea sesión `PENDING`;
  - genera `random_seed` si no se proporciona;
  - encola job `run_audit(session_id)`.
- Estados:
  - `PENDING`
  - `RUNNING`
  - `ABORT_REQUESTED`
  - `ABORTED`
  - `COMPLETED`
  - `FAILED`
- Endpoints:
  - `GET /api/v1/audits`
  - `GET /api/v1/audits/{id}`
  - `GET /api/v1/audits/{id}/status`
  - `POST /api/v1/audits/{id}/abort`

Worker:

- Cargar target y dataset.
- Barajar queries con `random_seed`.
- Ejecutar calibración.
- Ejecutar queries secuencialmente dentro de cada auditoría.
- Permitir varias auditorías simultáneas vía workers/concurrencia Arq.
- Respetar `MAX_CONCURRENT_AUDITS`.
- Revisar aborto antes de cada petición.
- Actualizar progreso cada 10 peticiones.
- Guardar errores individuales sin detener auditoría.
- Marcar `FAILED` si falla toda la calibración o hay 20 errores consecutivos.

Criterio de aceptación:

- Se puede lanzar una auditoría.
- El worker la ejecuta fuera del proceso API.
- El estado cambia correctamente.
- Se puede abortar.
- Pueden existir varias auditorías en cola y varias ejecutándose según límite.

## Fase 8: Medición HTTP TTFB Y Respuesta Completa

Objetivo: medir correctamente canal lateral black-box.

Tareas:

- Implementar `http_measurement.py`.
- Usar `httpx.AsyncClient`.
- Medir con streaming:
  - `ttfb_ms`
  - `full_response_ms`
  - `latency_ms = ttfb_ms`
- Guardar:
  - `status_code`
  - `response_size_bytes`
  - `is_error`
  - `error_type`
  - `error_message`
  - `timestamp`
- No guardar cuerpo de respuesta.
- Reemplazar `{{QUERY}}` de forma recursiva en JSON.
- Para `GET`, reemplazar en URL solo como modo secundario.

Criterio de aceptación:

- TTFB no se confunde con respuesta completa.
- El sistema mide targets con streaming y sin streaming.
- Queries con caracteres especiales no rompen el JSON.
- Los errores se registran sin exponer secretos.

## Fase 9: Audit Runner Y Monitor En Frontend

Objetivo: lanzar y seguir auditorías desde UI.

Frontend:

- Vista `/audits/new`.
- Wizard:
  - elegir target;
  - elegir dataset;
  - configurar delay min/max;
  - configurar calibración;
  - opción avanzada de `random_seed`;
  - estimación de duración.
- Vista `/audits/running/:id`.
- Polling cada 2 segundos con TanStack Query.
- Progress bar.
- Estado textual.
- Contador de errores.
- Latencia media parcial si está disponible.
- Botón abortar con confirmación.
- Redirección automática a resultados al completar.

Criterio de aceptación:

- Un usuario puede lanzar auditoría sin tocar consola.
- El progreso se actualiza.
- El abort funciona visual y técnicamente.
- Al terminar se navega a resultados.

## Fase 10: Resultados, Paginación Y Exportación

Objetivo: consultar resultados de forma escalable.

Backend:

- `GET /api/v1/audits/{id}/results?page=&page_size=`
- Paginación real en SQL.
- Filtros mínimos:
  - `frequency`
  - `length`
  - `is_error`
  - `status_code`
- Export:
  - `GET /api/v1/audits/{id}/export.csv`
  - `GET /api/v1/audits/{id}/export.json`
- Generar exports al vuelo.

Frontend:

- Vista `/audits/results/:id`.
- Tabla paginada.
- Filtros.
- Botones CSV/JSON.
- Estado para auditoría fallida o abortada.

Criterio de aceptación:

- No se cargan miles de filas de golpe.
- Se pueden exportar resultados completos.
- La tabla es usable con 5000 resultados.

## Fase 11: Summary Estadístico Y Analytics

Objetivo: responder si hay evidencia de canal lateral.

Backend:

- `GET /api/v1/audits/{id}/summary`.
- Métricas por grupo:
  - count;
  - mean;
  - median;
  - std;
  - p25;
  - p75;
  - p95;
  - min;
  - max;
  - error_rate.
- Comparativas:
  - diferencia de medias;
  - diferencia de medianas;
  - Welch t-test;
  - Mann-Whitney U;
  - Cohen’s d.
- Clasificación experimental:
  - `insufficient`
  - `weak`
  - `moderate`
  - `strong`

Frontend:

- Cards resumen.
- Bar chart de latencia media por `frequency`.
- Scatter plot por orden de petición.
- Histograma o densidad por grupo si la librería elegida lo permite.
- Tabla de comparativas.
- Texto interpretativo prudente.

Criterio de aceptación:

- La vista no dice solo “vulnerable/no vulnerable”.
- Muestra evidencia estadística y limitaciones.
- Permite comparar `high`, `medium`, `low`, `null`.

## Fase 12: Experimento Secundario De Caché

Objetivo: observar patrones compatibles con caché sin preguntar al usuario si existe caché.

Backend:

- Añadir modo avanzado opcional de auditoría cache-probe.
- Seleccionar subconjunto de queries.
- Ejecutar primera ronda aleatoria.
- Pausar.
- Ejecutar segunda ronda.
- Comparar reducción de:
  - `ttfb_ms`
  - `full_response_ms`
- Guardar resultados vinculados a la sesión o a una tabla secundaria si hace falta.

Frontend:

- Mostrar experimento como sección avanzada.
- Mostrar reducción media primera vs segunda ejecución.
- Texto: “patrón compatible con caché”, nunca certeza absoluta.

Criterio de aceptación:

- No interfiere con auditoría principal.
- No requiere que el usuario declare arquitectura interna.
- Aporta valor como análisis complementario.

## Fase 13: Hardening, Retención Y Seguridad

Objetivo: cerrar riesgos antes de considerar la app presentable.

Tareas:

- Validar CORS desde entorno.
- Revisar que no se loguean tokens ni queries sensibles en producción.
- Revisar cifrado de headers.
- Añadir límites:
  - tamaño máximo archivo;
  - máximo queries;
  - timeout mínimo/máximo;
  - concurrencia;
  - page size máximo.
- Añadir borrado seguro:
  - bloquear datasets usados;
  - borrar auditorías con cascade de resultados.
- Mejorar mensajes de error.
- Añadir pantalla de “uso autorizado”.

Criterio de aceptación:

- La app no expone secretos en UI/logs.
- Los límites están aplicados en backend, no solo en frontend.
- La app se puede defender como herramienta de auditoría autorizada.

## Fase 14: Tests Y Validación

Backend:

- Tests de auth.
- Tests de validación de target.
- Tests de validación de dataset.
- Tests de cifrado/descifrado de headers.
- Tests de reemplazo recursivo `{{QUERY}}`.
- Tests de medición HTTP con `mock-rag`.
- Tests de worker y estados.
- Tests de abort.
- Tests de summary estadístico.
- Tests de export CSV/JSON.

Frontend:

- Test manual documentado mínimo.
- Si da tiempo:
  - tests de formularios;
  - tests de login;
  - tests de tabla/resultados.

End-to-end:

- Levantar Compose.
- Crear admin.
- Login.
- Crear target contra `mock-rag`.
- Subir dataset.
- Lanzar auditoría.
- Ver progreso.
- Completar.
- Ver analytics.
- Exportar resultados.

Criterio de aceptación:

- El flujo principal funciona de extremo a extremo.
- Los errores críticos están cubiertos.
- La demo se puede repetir.

## Fase 15: Documentación Final

Objetivo: dejar el proyecto entendible y defendible.

Documentos:

- `README.md`:
  - qué es la herramienta;
  - cómo levantar con Docker Compose;
  - usuario admin inicial;
  - cómo crear target;
  - cómo subir dataset;
  - cómo ejecutar auditoría.
- `PLAN_IMPLEMENTACION.md`:
  - este plan.
- `ESPECIFICACION_CRITICA.md`:
  - requisitos y decisiones.
- Guía de dataset:
  - formato JSON;
  - etiquetas permitidas;
  - ejemplos.
- Guía de interpretación:
  - TTFB vs respuesta completa;
  - ruido HTTP;
  - límites de la inferencia;
  - significado de evidencia débil/moderada/fuerte.

Criterio de aceptación:

- Otra persona puede levantar y probar el sistema.
- El tribunal puede entender arquitectura, uso y limitaciones.
- La herramienta queda conectada claramente con el TFG.

## APIs E Interfaces Públicas Principales

Backend:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET/POST/PUT/DELETE /api/v1/targets`
- `POST /api/v1/targets/{id}/test`
- `GET/POST/DELETE /api/v1/datasets`
- `GET /api/v1/datasets/{id}/preview`
- `POST /api/v1/audits/start`
- `GET /api/v1/audits/{id}/status`
- `POST /api/v1/audits/{id}/abort`
- `GET /api/v1/audits/{id}/results`
- `GET /api/v1/audits/{id}/summary`
- `GET /api/v1/audits/{id}/export.csv`
- `GET /api/v1/audits/{id}/export.json`

Dataset JSON:

```json
[
  {
    "query": "example question",
    "frequency": "high",
    "length": "short"
  }
]
```

Valores válidos:

- `frequency`: `high`, `medium`, `low`, `null`
- `length`: `short`, `medium`, `long`

## Supuestos Y Defaults Cerrados

- Docker Compose obligatorio.
- Backend FastAPI async.
- Frontend React + TypeScript + Vite.
- PostgreSQL con SQLAlchemy async y Alembic.
- Redis + Arq para workers.
- Celery solo como fallback si Arq bloquea.
- Autenticación desde el inicio.
- Rol único inicial: `admin`.
- Admin inicial por variables de entorno.
- Headers sensibles cifrados en BD.
- Método recomendado: `POST`.
- `GET` solo secundario.
- TTFB es métrica principal.
- Respuesta completa se guarda como secundaria.
- No se guarda cuerpo de respuesta.
- Máximo inicial: 5000 queries por auditoría.
- Concurrencia configurable; default recomendado `MAX_CONCURRENT_AUDITS=2`.
- Se permiten campos extra en datasets, ignorados en v1.
- `mock-rag` incluido desde el inicio.
- Borrado normal de datasets usados queda bloqueado.
