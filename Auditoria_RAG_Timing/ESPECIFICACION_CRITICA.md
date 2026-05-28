# Plataforma de auditoria de canales laterales de latencia en sistemas RAG

## 1. Objetivo del documento

Este documento define y corrige la especificacion inicial de la aplicacion que se desarrollara dentro del TFG. La idea no es crear solo un lanzador de peticiones HTTP, sino una herramienta de auditoria que permita a un usuario autorizado evaluar si su sistema RAG filtra informacion indirecta mediante diferencias de tiempo.

La aplicacion debe permitir:

- Configurar sistemas RAG objetivo.
- Subir datasets de consultas etiquetadas.
- Ejecutar auditorias black-box mediante HTTP.
- Medir latencias de forma reproducible.
- Analizar si existen diferencias estadisticamente significativas entre grupos de consultas.
- Exportar resultados para memoria, defensa y analisis externo.

La herramienta no debe asumir que conoce la arquitectura interna del sistema auditado. En particular, no debe pedir al usuario que declare si el sistema tiene cache, si usa ChromaDB, si usa Redis o que algoritmo de retrieval utiliza. La herramienta observa desde fuera. Si hay cache, retrieval lento, LLM lento, streaming, red inestable o cualquier otro componente, eso debe reflejarse en las mediciones y en el analisis.

## 2. Correcciones criticas a la especificacion inicial

### 2.1. Confusion entre TTFB y respuesta completa

La especificacion original dice que se mide Time-to-First-Byte, pero el algoritmo propuesto usa `await response.aread()`. Eso no mide TTFB, sino tiempo hasta recibir toda la respuesta.

Son metricas distintas:

- `ttfb_ms`: tiempo desde antes de enviar la peticion hasta recibir el primer byte de respuesta.
- `full_response_ms`: tiempo desde antes de enviar la peticion hasta descargar toda la respuesta.
- `latency_ms`: metrica principal que se usara para graficas y analisis. Puede apuntar a TTFB, respuesta completa o ambas segun el modo elegido.

Recomendacion tecnica:

La herramienta debe medir ambas cuando sea posible. Esto evita perder informacion. En sistemas RAG con streaming, el TTFB puede reflejar tiempo hasta que el servidor empieza a generar, mientras que la respuesta completa incluye generacion del LLM. En sistemas sin streaming, ambas pueden ser muy parecidas.

Decision pendiente:

Elegir la metrica principal por defecto:

Decision tomada:

La herramienta medira `ttfb_ms` como metrica principal enfocada al canal lateral y guardara `full_response_ms` como metrica secundaria. Esto permite analizar el comportamiento observable desde fuera sin mezclar tanto la duracion completa de la generacion del LLM.

Criterio:

El uso de HTTP anade ruido de red, servidor, TLS, proxy, serializacion y colas internas. Aun asi, es el enfoque correcto para una auditoria black-box realista. Las pruebas internas del TFG demuestran que la senal existe en la capa de recuperacion; esta herramienta evaluara si la senal sigue siendo observable cuando se anade el ruido propio de un entorno real.

### 2.2. Falta modelo estadistico

Mostrar graficas no basta para afirmar que existe un canal lateral. La herramienta debe incluir un modulo estadistico minimo que transforme las latencias en evidencia interpretable.

Metricas por grupo:

- Numero de muestras.
- Media.
- Mediana.
- Desviacion estandar.
- Percentil 25.
- Percentil 75.
- Percentil 95.
- Minimo.
- Maximo.
- Tasa de error.

Comparativas entre grupos:

- Diferencia de medias.
- Diferencia de medianas.
- Welch t-test entre pares.
- Mann-Whitney U como alternativa no parametrica.
- Tamano del efecto, por ejemplo Cohen's d.
- Intervalos de confianza.
- Estimacion de numero de muestras necesarias para distinguir dos grupos con 95% o 99% de confianza.

La herramienta no debe decir simplemente "vulnerable" o "seguro" sin contexto. Debe mostrar una conclusion graduada:

- Sin evidencia suficiente.
- Evidencia debil.
- Evidencia moderada.
- Evidencia fuerte.

Decision pendiente:

Definir los umbrales exactos para clasificar la evidencia. Mi recomendacion es no fijarlos al principio. Primero implementaria las metricas y, tras probar con tus datasets, definimos umbrales defendibles para el TFG.

### 2.3. Falta paginacion y exportacion

Una auditoria puede generar miles o decenas de miles de resultados. Devolver todo en un unico endpoint no escala bien y puede romper el frontend.

Los resultados deben consultarse paginados:

```text
GET /api/v1/audits/{id}/results?page=1&page_size=100
```

Tambien debe haber exportacion:

```text
GET /api/v1/audits/{id}/export.csv
GET /api/v1/audits/{id}/export.json
```

Recomendacion tecnica:

El frontend debe usar paginacion real del backend, no cargar todo y paginar en navegador.

Decision pendiente:

Formato de exportacion adicional:

- CSV para analisis en Excel, Python o R.
- JSON para reproducibilidad.
- Markdown/PDF para informe automatico. Esto puede dejarse para una fase posterior.

Decision tomada:

La primera version incluira exportacion CSV y JSON. La generacion de informes Markdown/PDF queda como fase posterior.

### 2.4. Falta control de seguridad

La herramienta envia peticiones HTTP configurables por el usuario. Esto tiene riesgos si se ejecuta sin restricciones.

Controles minimos:

- Permitir solo URLs `http://` y `https://`.
- Validar URLs.
- Configurar timeouts obligatorios.
- Limitar tamano maximo de datasets.
- Limitar numero maximo de queries por auditoria.
- Limitar auditorias concurrentes.
- No mostrar tokens completos en el frontend.
- No guardar logs con cabeceras sensibles completas.
- Configurar CORS solo para origenes conocidos.
- Registrar errores de red sin exponer secretos.

Tambien es recomendable incluir una declaracion de uso autorizado. La herramienta debe presentarse como auditoria defensiva, no como herramienta ofensiva sin control.

Decision pendiente:

Autenticacion de la propia plataforma:

- MVP local sin login.
- Login simple con usuario/password.
- Integracion corporativa posterior.

Decision tomada:

La autenticacion se implementara desde el principio. Aunque el desarrollo se haga por fases, la aplicacion se quiere construir como una plataforma completa y profesional, y desde el inicio gestionara targets, cabeceras, posibles tokens y resultados sensibles.

Recomendacion de implementacion:

Primera version con autenticacion local simple:

- Usuarios en base de datos.
- Password hash con `bcrypt` o `argon2`.
- Login con JWT.
- Proteccion de todos los endpoints bajo `/api/v1`.

Roles avanzados y OAuth pueden quedar para fases posteriores.

### 2.5. Falta reproducibilidad con `random_seed`

La especificacion exige `random.shuffle()` para romper efectos de cache interna y evitar sesgos por orden. Eso esta bien, pero si no se guarda la semilla no se puede reproducir una auditoria.

La sesion debe guardar:

- `random_seed`.
- Orden real de ejecucion mediante `request_index`.
- Timestamp de cada peticion.

Recomendacion tecnica:

Al iniciar una auditoria:

1. Si el usuario proporciona semilla, se usa.
2. Si no, el backend genera una.
3. La semilla se guarda en `audit_sessions`.
4. Cada resultado guarda su `request_index`.

Decision pendiente:

Permitir que el usuario introduzca una semilla desde la UI o mantenerlo oculto en modo avanzado. Recomiendo mostrarlo como opcion avanzada.

Decision tomada:

Se guardara siempre `random_seed`. La UI podra mostrarlo como opcion avanzada, pero si el usuario no introduce una semilla, el backend generara una automaticamente.

### 2.6. Falta soporte correcto para GET

La especificacion inicial permite `GET` y `POST`, pero solo habla de `payload_template`. En GET normalmente no hay body, o no deberia dependerse de el.

Opciones para GET:

- Insertar `{{QUERY}}` directamente en la URL.
- Usar un campo `query_param_name`.
- Permitir `query_params_template` como JSON.

Modelo recomendado:

Para `POST`:

- `payload_template` obligatorio.
- Debe contener `{{QUERY}}`.

Para `GET`:

- `url_template` o `query_params_template` debe contener `{{QUERY}}`.
- `payload_template` no debe ser obligatorio.

Decision pendiente:

Elegir la forma de configuracion para GET:

- Opcion simple: URL completa con `{{QUERY}}`.
- Opcion mas estructurada: `base_url` + `query_params_template`.

Recomiendo empezar con URL completa con `{{QUERY}}`, porque es mas flexible para endpoints black-box.

Decision pendiente:

Todavia se debe decidir el formato exacto de GET. Se mantiene como decision abierta porque afecta directamente al modelo `targets` y a la UI.

Decision tomada:

La herramienta recomendara `POST` con cuerpo JSON como metodo principal para auditorias. Es mas apropiado para consultas potencialmente sensibles porque evita poner la query en claro dentro de la URL, historiales, proxies o logs intermedios.

`GET` se mantendra solo como soporte secundario para APIs que obliguen a usarlo. En ese caso, la forma mas compatible sera permitir una URL completa con `{{QUERY}}`, avisando en la UI de que la query puede quedar expuesta en logs de red o servidor.

Criterio:

No se fuerza al usuario a usar GET. El flujo principal de la aplicacion debe estar optimizado para POST.

### 2.7. `BackgroundTasks` es debil para auditorias largas

FastAPI `BackgroundTasks` sirve para tareas cortas, pero no es robusto para auditorias largas. Si el proceso backend se reinicia, la tarea se pierde. Tampoco ofrece buen control de concurrencia, reintentos o workers separados.

Opciones:

- MVP: FastAPI `BackgroundTasks`.
- Intermedio: `asyncio.create_task` con gestor interno de tareas.
- Produccion: worker separado con Redis + Celery, RQ, Dramatiq o Arq.

Recomendacion tecnica:

Para el TFG, se puede empezar con `BackgroundTasks` si queremos avanzar rapido. Pero la arquitectura debe dejar claro que el motor de ejecucion es separable. Idealmente, el codigo del motor no debe depender directamente de FastAPI.

Estructura recomendada:

```text
backend/
  app/
    api/
    models/
    schemas/
    services/
      audit_runner.py
      http_measurement.py
      statistics.py
```

Asi, si luego se cambia de `BackgroundTasks` a worker real, no hay que reescribir la logica central.

Decision pendiente:

Primera version:

- Opcion recomendada para MVP: `BackgroundTasks`, pero con motor desacoplado.
- Opcion mas profesional desde el principio: worker con Redis/Arq.

Decision tomada:

Se usaran workers desde el inicio. La aplicacion debe soportar auditorias largas y, potencialmente, auditorias simultaneas contra varios sistemas. Por tanto, `BackgroundTasks` queda descartado como mecanismo principal.

Arquitectura recomendada:

- `backend`: API FastAPI.
- `worker`: proceso separado encargado de ejecutar auditorias.
- `redis`: broker/cola de trabajos.
- `postgres`: persistencia de configuracion, sesiones y resultados.

Tecnologias candidatas:

- Arq: muy natural para Python async y Redis.
- RQ: simple, pero menos orientado a async.
- Celery: muy maduro, pero mas pesado.

Decision tomada:

Usar Arq como sistema de workers y cola. Encaja bien con FastAPI async, httpx async y SQLAlchemy async. Si durante la implementacion aparece algun problema serio, Celery sera la alternativa de respaldo.

### 2.8. Faltan campos de error, tamano de respuesta y metricas separadas

El modelo `audit_results` original guarda `is_error`, pero no guarda suficiente detalle para diagnosticar problemas.

Campos recomendados:

- `request_index`.
- `query_text`.
- `frequency_tag`.
- `length_tag`.
- `latency_ms`.
- `ttfb_ms`.
- `full_response_ms`.
- `status_code`.
- `response_size_bytes`.
- `is_error`.
- `error_type`.
- `error_message`.
- `timestamp`.

Ejemplos de `error_type`:

- `timeout`.
- `connection_error`.
- `tls_error`.
- `invalid_response`.
- `http_error`.
- `aborted`.

Recomendacion:

Un error individual no debe parar toda la auditoria. Debe guardarse como resultado fallido y continuar. Solo se debe marcar la sesion como `FAILED` si hay un fallo global permanente, por ejemplo target inaccesible durante muchas peticiones seguidas.

Decision pendiente:

Definir politica de fallo global:

- Fallar tras N errores consecutivos.
- Fallar si la tasa de error supera un porcentaje.
- Nunca fallar automaticamente y completar con errores.

Recomiendo: fallar si hay 20 errores consecutivos o si durante la calibracion no responde ninguna peticion.

Decision propuesta:

Mantener como regla inicial:

- Si la calibracion falla completamente, la auditoria pasa a `FAILED`.
- Si hay 20 errores consecutivos durante la ejecucion, la auditoria pasa a `FAILED`.
- Los errores individuales se guardan en `audit_results` y no detienen la auditoria.

Esta regla se puede ajustar tras las primeras pruebas.

### 2.9. Falta vista resumen para interpretar si hay canal lateral

La vista de resultados no debe limitarse a tabla, scatter plot y barras. Eso ayuda a visualizar, pero no contesta la pregunta principal: "hay evidencia de canal lateral temporal?".

Debe existir una vista resumen con:

- Latencia media por frecuencia.
- Latencia mediana por frecuencia.
- Dispersion por frecuencia.
- Diferencias entre grupos.
- Tests estadisticos.
- Tamano del efecto.
- Numero de muestras por grupo.
- Tasa de error por grupo.
- Conclusion interpretativa.

Ejemplo de salida:

```text
Comparacion High vs Low
- Media High: 54.2 ms
- Media Low: 67.8 ms
- Diferencia: 13.6 ms
- p-value Welch: 0.0003
- Cohen's d: 0.82
- Evidencia: fuerte
```

La herramienta debe evitar afirmaciones absolutas. Mejor decir:

"Existe evidencia estadistica de que las consultas etiquetadas como Low presentan mayor latencia que las High en esta auditoria."

No decir:

"El sistema es vulnerable" sin matices.

## 3. Criterio sobre cache

No tiene sentido pedir al usuario que configure "el sistema tiene cache" o "no tiene cache" como si fuese una variable de la auditoria black-box. En una auditoria externa, muchas veces el usuario no sabra si hay cache en el RAG, en el LLM gateway, en el proxy, en la base vectorial o en otra capa.

Ademas, para el objetivo del TFG lo importante no es etiquetar la cache, sino medir si el comportamiento temporal permite inferir informacion.

Por tanto:

- La herramienta no debe tener un switch "target con cache".
- La herramienta si debe controlar el orden aleatorio de queries.
- La herramienta si debe permitir jitter entre peticiones.
- La herramienta si debe mostrar patrones compatibles con cache, si se observan.

Patrones que podrian indicar cache:

- Caida fuerte de latencia tras repetir consultas similares.
- Diferencia clara entre primera ejecucion y ejecuciones posteriores.
- TTFB muy bajo en grupos de queries semanticamente parecidas.
- Varianza temporal no explicada por frecuencia o longitud.

Posible funcionalidad futura:

- Modo "deteccion de cache": repetir un subconjunto controlado de queries y comparar primera respuesta vs respuestas posteriores.

Decision pendiente:

Incluir o no en la primera version un modo especifico de deteccion de cache.

Decision tomada:

- La herramienta no preguntara al usuario si el target tiene cache.
- Se guardaran suficientes metricas para observar patrones compatibles con cache.
- Se implementara como tarea secundaria un experimento minimo de deteccion de cache, no como flujo principal.

Experimento minimo propuesto:

1. Seleccionar un subconjunto pequeno de queries del dataset.
2. Ejecutarlas una vez en orden aleatorio.
3. Repetirlas una segunda vez tras una pausa corta.
4. Comparar `ttfb_ms` y `full_response_ms` entre primera y segunda ejecucion.
5. Mostrar si hay reduccion sistematica de latencia compatible con cache.

Este experimento no debe afirmar que "hay cache" de forma absoluta. Debe decir que se observa o no se observa un patron compatible con cache.

## 4. Modelo de datos recomendado

### Tabla `targets`

Campos:

- `id`
- `name`
- `endpoint_url`
- `http_method`
- `headers`
- `payload_template`
- `timeout_seconds`
- `verify_tls`
- `created_by`
- `created_at`
- `updated_at`

Decision tomada:

- El metodo recomendado sera `POST`.
- `payload_template` sera obligatorio para `POST` y debe contener `{{QUERY}}`.
- `GET` sera secundario. Si se usa, `endpoint_url` podra contener `{{QUERY}}`, mostrando advertencia de privacidad en la UI.

Pendiente de decidir:

Decision tomada:

- Los headers sensibles se cifraran en base de datos desde la primera version.
- En frontend se ocultaran parcialmente, pero eso no sustituye al cifrado.
- La clave de cifrado se pasara por variable de entorno `SECRET_ENCRYPTION_KEY`.

### Tabla `datasets`

Campos:

- `id`
- `name`
- `file_path`
- `original_filename`
- `total_queries`
- `sha256`
- `schema_version`
- `created_at`

Formato inicial:

```json
[
  {
    "query": "texto de la consulta",
    "frequency": "high",
    "length": "short"
  }
]
```

Pendiente de decidir:

- Si se permitira una descripcion opcional del dataset.
- Si se guardara una muestra de preview en BD o se leera directamente del archivo.

Decision tomada:

- Etiquetas oficiales en ingles.
- Maximo inicial de 5.000 queries por auditoria.
- Formato estricto con campos `query`, `frequency`, `length`.

### Tabla `audit_sessions`

Campos:

- `id`
- `target_id`
- `dataset_id`
- `status`
- `measurement_mode`
- `delay_min_ms`
- `delay_max_ms`
- `calibration_requests`
- `progress_current`
- `progress_total`
- `random_seed`
- `error_message`
- `created_at`
- `started_at`
- `completed_at`

### Tabla `audit_results`

Campos:

- `id`
- `session_id`
- `request_index`
- `query_text`
- `frequency_tag`
- `length_tag`
- `latency_ms`
- `ttfb_ms`
- `full_response_ms`
- `status_code`
- `response_size_bytes`
- `is_error`
- `error_type`
- `error_message`
- `timestamp`

## 5. API recomendada

### Targets

```text
GET    /api/v1/targets
POST   /api/v1/targets
GET    /api/v1/targets/{id}
PUT    /api/v1/targets/{id}
DELETE /api/v1/targets/{id}
POST   /api/v1/targets/{id}/test
```

### Datasets

```text
GET    /api/v1/datasets
POST   /api/v1/datasets/upload
GET    /api/v1/datasets/{id}
GET    /api/v1/datasets/{id}/preview
DELETE /api/v1/datasets/{id}
```

### Auditorias

```text
GET    /api/v1/audits
POST   /api/v1/audits/start
GET    /api/v1/audits/{id}
GET    /api/v1/audits/{id}/status
POST   /api/v1/audits/{id}/abort
GET    /api/v1/audits/{id}/results
GET    /api/v1/audits/{id}/summary
GET    /api/v1/audits/{id}/export.csv
GET    /api/v1/audits/{id}/export.json
```

## 6. Vistas de frontend recomendadas

### Dashboard

Debe mostrar:

- Ultimas auditorias.
- Estado de auditorias activas.
- Boton de nueva auditoria.
- Resumen rapido: completadas, fallidas, abortadas.

### Target Manager

Debe permitir:

- Crear target.
- Editar target.
- Probar target con una query manual.
- Validar JSON de headers y payload.
- Ocultar tokens sensibles.

### Dataset Manager

Debe permitir:

- Subir JSON.
- Previsualizar queries.
- Ver distribucion por frecuencia y longitud.
- Eliminar dataset.

### Audit Runner

Debe permitir:

- Elegir target.
- Elegir dataset.
- Configurar jitter.
- Configurar calibracion.
- Configurar modo de medicion.
- Opcional avanzado: `random_seed`.

No debe pedir:

- Si el sistema tiene cache.
- Que base vectorial usa.
- Que LLM usa.

Eso puede anotarse como metadato manual en el futuro, pero no debe condicionar el motor black-box.

### Execution Monitor

Debe mostrar:

- Progreso.
- Estado.
- Latencia media parcial.
- Numero de errores.
- Boton de abortar con confirmacion.

### Analytics & Results

Debe mostrar:

- Tabla paginada.
- Scatter plot de latencia por orden de peticion.
- Grafico de medias por `frequency_tag`.
- Histograma o densidad por grupo.
- Resumen estadistico.
- Comparativas entre grupos.
- Exportacion.

## 7. Orden recomendado de implementacion

### Fase 1: MVP funcional

- Backend FastAPI.
- PostgreSQL.
- Modelos basicos.
- CRUD de targets.
- Upload de datasets.
- Worker con Arq y Redis.
- Medicion de `ttfb_ms` y `full_response_ms`.
- Resultados paginados.
- Autenticacion admin.
- Frontend basico.

### Fase 2: Medicion robusta

- Separar `ttfb_ms` y `full_response_ms`.
- `random_seed`.
- Mejor manejo de errores.
- Export CSV/JSON.
- Endpoint de summary.

### Fase 3: Analisis estadistico

- Welch t-test.
- Mann-Whitney U.
- Cohen's d.
- Estimacion de muestras necesarias.
- Vista de interpretacion del canal lateral.

### Fase 4: Robustez profesional

- Limites de concurrencia.
- Cifrado o gestion segura de secretos.
- Informes automaticos.

## 8. Preguntas pendientes para decidir contigo

Estas decisiones no deberian cerrarse sin validarlas:

1. La metrica principal por defecto sera TTFB, respuesta completa o ambas?
2. Para GET, prefieres URL completa con `{{QUERY}}` o parametros separados?
3. Cual sera el tamano maximo permitido de dataset?
4. Cual sera el numero maximo de queries por auditoria?
5. La primera version usara `BackgroundTasks` o metemos worker desde el inicio?
6. Habra autenticacion en la herramienta o sera local sin login para el TFG?
7. Que etiquetas oficiales tendran los datasets: `high/medium/low`, `alta/media/baja/nula`, o libres?
8. Se incluira en la primera version un modo especifico de deteccion de cache, o solo se observara indirectamente?

## 9. Despliegue con Docker Compose

Decision recomendada: la aplicacion debe desarrollarse y ejecutarse mediante Docker Compose desde el inicio.

Motivos:

- Facilita reproducibilidad para el TFG.
- Permite levantar backend, frontend y PostgreSQL con un solo comando.
- Evita depender de configuraciones locales distintas.
- Hace mas profesional la entrega.
- Permite anadir facilmente Redis o un worker si mas adelante se decide.

Stack inicial recomendado:

```text
docker-compose.yml
  backend
  frontend
  postgres
```

Stack ampliado si se usa worker:

```text
docker-compose.yml
  backend
  frontend
  postgres
  redis
  worker
```

Volumenes recomendados:

```text
postgres_data
datasets_data
exports_data
```

Variables de entorno recomendadas:

```text
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/auditoria_rag
DATASETS_DIR=/data/datasets
EXPORTS_DIR=/data/exports
BACKEND_CORS_ORIGINS=http://localhost:5173
MAX_DATASET_SIZE_MB=20
MAX_QUERIES_PER_AUDIT=10000
```

Criterio:

No veo una alternativa mejor para este caso. Ejecutarlo sin Docker seria mas rapido al principio, pero peor para documentar, reproducir y defender. Kubernetes seria excesivo. Por tanto, Docker Compose debe considerarse requisito del proyecto.

## 10. Explicacion de decisiones pendientes

### 10.1. Metrica principal: TTFB, respuesta completa o ambas

Esta es una decision importante porque define que tipo de canal lateral estamos midiendo.

`TTFB` mide el tiempo hasta que llega el primer byte. Es util si queremos reducir el ruido de respuestas largas del LLM. En muchos sistemas RAG, el primer byte aparece cuando el servidor ya ha hecho retrieval, ha construido el prompt y empieza a responder. Por tanto, puede capturar mejor diferencias en la fase de recuperacion o preparacion.

`full_response_ms` mide el tiempo hasta descargar toda la respuesta. Es mas facil de implementar y refleja lo que percibe el usuario final, pero mezcla muchas cosas: retrieval, generacion del LLM, longitud de la respuesta, streaming, red y serializacion.

Medir ambas es mas robusto. Permite analizar si la diferencia aparece antes de generar texto o si solo aparece al completar la respuesta.

Recomendacion:

Medir ambas desde el principio si no complica demasiado. Usar `ttfb_ms` como metrica principal por defecto y guardar `full_response_ms` para comparar.

Decision a tomar:

- Simple: solo respuesta completa.
- Mejor para investigacion: ambas.
- Enfocada al canal lateral: TTFB como principal y respuesta completa como secundaria.

### 10.2. Soporte GET: URL con `{{QUERY}}` o parametros separados

Para `POST`, la query se puede insertar en un JSON:

```json
{
  "question": "{{QUERY}}"
}
```

Para `GET`, lo normal es que vaya en la URL:

```text
https://example.com/rag/search?q={{QUERY}}
```

La forma mas flexible es permitir que la URL completa contenga `{{QUERY}}`. Asi se puede auditar casi cualquier endpoint sin tener que modelar parametros por separado.

La forma mas estructurada seria guardar:

```text
base_url = https://example.com/rag/search
query_params_template = {"q": "{{QUERY}}", "top_k": "5"}
```

Recomendacion:

Empezar con URL completa con `{{QUERY}}` para GET. Es mas simple y sirve para mas casos black-box.

Decision a tomar:

- Flexible y simple: URL completa con `{{QUERY}}`.
- Mas ordenada: parametros separados.
- Mas completa: soportar ambas, pero aumenta trabajo de UI y validacion.

### 10.3. Tamano maximo de dataset

Hay que limitar el tamano para evitar que un usuario suba archivos enormes y rompa el backend o el disco.

Factores:

- Cada query genera una peticion HTTP.
- Cada resultado se guarda en PostgreSQL.
- El frontend debe poder paginar y exportar despues.
- En auditorias reales puede haber miles de queries.

Decision tomada:

- Tamano maximo de archivo: 20 MB.
- Numero maximo de queries por dataset: configurable.
- Para MVP: 5.000 queries por auditoria como limite intermedio.

Decision a tomar:

- Conservador: 5 MB y 2.000 queries.
- Equilibrado: 20 MB y 10.000 queries.
- Agresivo: 100 MB y 50.000 queries, pero requiere mas cuidado con workers, paginacion y exportacion.

Para el TFG recomiendo equilibrio: suficiente para pruebas serias, sin complicar demasiado.

Decision tomada:

Se usara un limite intermedio de 5.000 queries por auditoria. La idea futura sera necesitar cada vez menos queries gracias a mejores estrategias estadisticas y generacion interna equilibrada, pero 5.000 deja margen para auditorias robustas sin abrir la puerta a ejecuciones excesivamente grandes.

El tamano maximo de archivo puede quedar en 20 MB, pero el backend rechazara o pedira recorte si el numero de queries supera el limite configurado.

Futuro:

Se implementara mas adelante un generador interno de queries con formato equilibrado. Esto permitira crear datasets mejor distribuidos sin depender siempre de archivos externos.

### 10.4. Numero maximo de queries por auditoria

Este limite es distinto al tamano del archivo. Un dataset podria tener 20.000 queries, pero una auditoria podria ejecutar solo una parte.

Motivos para limitar:

- Evitar ejecuciones de horas por error.
- Evitar sobrecargar el target.
- Evitar crecimiento descontrolado de la BD.

Decision tomada:

Para la primera version, 5.000 queries por auditoria. Ademas, mostrar una estimacion de duracion antes de lanzar:

```text
duracion estimada = queries * (delay medio + latencia esperada)
```

Decision a tomar:

- 1.000: rapido y seguro, pero podria quedarse corto en algunos escenarios.
- 5.000: limite intermedio elegido para la primera version.
- 10.000: posible limite avanzado futuro.
- Sin limite: no recomendable.

Decision tomada:

El limite inicial sera 5.000 queries por auditoria. El valor debe ser configurable mediante variable de entorno.

### 10.5. `BackgroundTasks` o worker desde el inicio

`BackgroundTasks` de FastAPI es sencillo y suficiente para una primera version. El problema es que no es robusto: si el proceso se reinicia, la tarea se pierde.

Un worker separado con Redis o una cola es mas profesional:

- Backend recibe la peticion.
- Guarda sesion en BD.
- Encola trabajo.
- Worker ejecuta auditoria.
- Frontend consulta estado.

Opciones:

- `BackgroundTasks`: mas rapido de implementar.
- Worker con Redis + Arq/RQ/Celery: mas robusto.

Recomendacion:

Si el objetivo es avanzar rapido, empezar con `BackgroundTasks` pero escribir el motor desacoplado. Si queremos que la arquitectura nazca profesional desde el principio, usar worker.

Mi criterio:

Para una herramienta que puede lanzar auditorias largas, el worker tiene mas sentido. Como ya quieres Docker Compose, anadir `redis` y `worker` no es tan raro. Aun asi, para no bloquear el desarrollo, se puede hacer por fases.

Decision tomada:

Se usara worker con cola desde el inicio. La herramienta debe poder ejecutar auditorias largas y permitir auditar mas de un sistema al mismo tiempo. `BackgroundTasks` no encaja con ese objetivo profesional.

Decision tecnica pendiente:

Elegir tecnologia de cola:

- Arq: elegido por encajar bien con async.
- Celery: mas conocido y robusto, pero mas pesado.
- RQ: simple, pero menos ideal para async.

Decision tomada:

Se usara Arq. Celery queda como alternativa si Arq presenta problemas.

### 10.6. Autenticacion

Si la herramienta se usa localmente para el TFG, se puede prescindir de login al principio.

Si se presenta como plataforma profesional, deberia tener autenticacion, porque guarda endpoints, headers, tokens y resultados de auditoria.

Opciones:

- Sin login: mas rapido, suficiente para demo local.
- Login simple: usuario y contrasena local.
- Autenticacion avanzada: JWT, roles, OAuth, etc.

Decision tomada:

La autenticacion se implementara desde el principio. La aplicacion manejara informacion sensible y se quiere construir como herramienta completa, aunque el desarrollo sea incremental.

Primera version recomendada:

- Tabla `users`.
- Login con email/username y password.
- Hash seguro de password.
- JWT access token.
- Proteccion de rutas API.
- Frontend con pantalla de login y sesion persistente.

Pendiente:

Definir si habra roles avanzados en el futuro.

Decision tomada:

En la primera version solo existira rol administrador. No se implementara gestion avanzada de permisos al inicio.

### 10.7. Etiquetas oficiales de datasets

Tus pruebas actuales usan conceptos como alta, media, baja frecuencia y longitud corta, media, larga. La herramienta puede permitir etiquetas libres, pero eso complica el analisis automatico.

Opciones:

- Etiquetas fijas en ingles: `high`, `medium`, `low`, `null`.
- Etiquetas fijas en espanol: `alta`, `media`, `baja`, `nula`.
- Etiquetas libres: cualquier string.
- Modelo mixto: aceptar libres, pero normalizar algunas conocidas.

Recomendacion:

Modelo mixto. Internamente guardar strings libres, pero la UI y los ejemplos recomiendan:

```text
frequency: high | medium | low | null
length: short | medium | long
```

Motivo:

Ingles encaja mejor con codigo, graficas y exportaciones. Pero si el usuario sube `alta`, podemos normalizarlo a `high`.

Decision tomada:

Habra un formato JSON obligatorio con nombres especificos de campos. De momento se mantiene el formato actual:

```json
[
  {
    "query": "texto de la consulta",
    "frequency": "high",
    "length": "short"
  }
]
```

Pendiente:

Los valores oficiales seran en ingles:

```text
frequency: high | medium | low | null
length: short | medium | long
```

La herramienta validara estrictamente estos valores. Si en el futuro se quiere admitir espanol, se podra anadir una capa de normalizacion, pero no sera parte de la primera version.

### 10.8. Modo especifico de deteccion de cache

Aunque no tenga sentido preguntar al usuario si el target tiene cache, si puede tener sentido disenar un experimento para detectar patrones compatibles con cache.

Modo normal:

- Se barajan queries.
- Se mide latencia.
- Se analiza por grupos.

Modo deteccion de cache:

- Se selecciona un subconjunto de queries.
- Se ejecutan una primera vez.
- Se repiten despues con orden controlado.
- Se compara primera ejecucion vs repetidas.

Esto podria revelar:

- Cache exacta.
- Cache semantica.
- Cache de embeddings.
- Cache de retrieval.
- Cache HTTP o proxy.

Riesgo:

Anadirlo desde el principio complica el MVP. Ademas, el objetivo principal no es clasificar la cache, sino detectar diferencias temporales.

Decision tomada:

No sera parte central del flujo de auditoria, pero se considera util como experimento secundario. Se incluira como tarea posterior o modo avanzado minimo.

La aplicacion no preguntara al usuario si hay cache. Solo observara si existen patrones compatibles con cache.

Implementacion minima sugerida:

- Ejecutar un subconjunto repetido de queries.
- Comparar primera ejecucion contra repeticion.
- Mostrar reduccion media de TTFB y respuesta completa.
- Presentar el resultado como indicio, no como certeza.

## 11. Criterio tecnico general

La herramienta debe estar disenada como auditor black-box. No debe intentar modelar internamente el RAG objetivo. Su valor esta en enviar consultas controladas, medir de forma fiable, ordenar y aleatorizar correctamente, guardar resultados reproducibles y aplicar estadistica para evaluar si las diferencias de latencia son significativas.

La aplicacion sera mas defendible si evita conclusiones exageradas y separa claramente:

- Lo medido.
- Lo inferido.
- La evidencia estadistica.
- Las limitaciones.

Ese enfoque encaja bien con el TFG y permite evolucionar desde una prueba de concepto academica hacia una herramienta profesional de auditoria.

## 12. Elementos que faltaban para una especificacion implementable

Esta seccion recoge las piezas que conviene cerrar antes de empezar a escribir codigo. Sin ellas, el desarrollo acabaria tomando decisiones improvisadas.

### 12.1. Estructura de carpetas del proyecto

Estructura recomendada:

```text
Auditoria_RAG_Timing/
  docker-compose.yml
  .env.example
  README.md
  ESPECIFICACION_CRITICA.md

  backend/
    Dockerfile
    pyproject.toml
    alembic.ini
    app/
      main.py
      core/
        config.py
        security.py
        logging.py
      db/
        base.py
        session.py
        migrations/
      models/
        user.py
        target.py
        dataset.py
        audit.py
      schemas/
        auth.py
        target.py
        dataset.py
        audit.py
        common.py
      api/
        deps.py
        v1/
          auth.py
          targets.py
          datasets.py
          audits.py
      services/
        dataset_service.py
        target_service.py
        audit_service.py
        audit_runner.py
        http_measurement.py
        statistics_service.py
        export_service.py
      workers/
        arq_worker.py
        jobs.py
      tests/

  frontend/
    Dockerfile
    package.json
    src/
      main.tsx
      app/
      routes/
      components/
      features/
        auth/
        targets/
        datasets/
        audits/
        analytics/
      lib/
      api/
```

Criterio:

Separar `services/audit_runner.py` del worker es importante. El runner debe poder ejecutarse desde Arq, desde tests o desde una futura CLI sin depender de FastAPI.

### 12.2. Contrato exacto del dataset

La primera version aceptara un JSON de array plano:

```json
[
  {
    "query": "What does the system know about internal mergers?",
    "frequency": "high",
    "length": "short"
  }
]
```

Reglas:

- El archivo debe ser JSON valido.
- La raiz debe ser un array.
- Cada elemento debe contener exactamente, como minimo, `query`, `frequency`, `length`.
- `query` debe ser string no vacio.
- `frequency` debe ser `high`, `medium`, `low` o `null`.
- `length` debe ser `short`, `medium` o `long`.
- El backend debe rechazar datasets con mas de 5.000 queries ejecutables por auditoria.

Decision pendiente:

Decision tomada:

El formato no sera estricto respecto a campos extra. El backend exigira `query`, `frequency` y `length`, pero permitira otros campos adicionales y los ignorara en la primera version. Esto facilita evolucionar el formato sin romper datasets futuros.

### 12.3. Contrato exacto de target

Para `POST`, ejemplo recomendado:

```json
{
  "name": "RAG local test",
  "endpoint_url": "https://example.com/api/chat",
  "http_method": "POST",
  "headers": {
    "Authorization": "Bearer TOKEN",
    "Content-Type": "application/json"
  },
  "payload_template": {
    "question": "{{QUERY}}"
  },
  "timeout_seconds": 30,
  "verify_tls": true
}
```

Reglas:

- `endpoint_url` debe ser URL valida.
- `http_method` debe ser `POST` o `GET`.
- Para `POST`, `payload_template` debe contener `{{QUERY}}` en algun punto del JSON.
- Para `GET`, `endpoint_url` debe contener `{{QUERY}}`.
- `headers` debe ser un objeto JSON.
- `timeout_seconds` debe tener limite inferior y superior, por ejemplo 1 a 300 segundos.

Decision pendiente:

Definir si se cifran headers sensibles en BD. Mi recomendacion profesional es si: cifrado simetrico con una clave `SECRET_ENCRYPTION_KEY` en entorno. Si lo dejamos solo oculto en frontend, la aplicacion es mas simple pero menos seria.

### 12.4. Autenticacion inicial

La primera version tendra un unico rol `admin`.

Endpoints minimos:

```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

Implementacion:

- Password hasheada con `argon2` o `bcrypt`.
- JWT access token.
- Token guardado en frontend de forma controlada.
- Todos los endpoints de targets, datasets y audits requieren autenticacion.

Decision pendiente:

Metodo de creacion del primer admin:

- Variables de entorno `ADMIN_EMAIL` y `ADMIN_PASSWORD` al arrancar.
- Comando CLI `create-admin`.
- Pantalla inicial de bootstrap si no hay usuarios.

Recomendacion: variables de entorno para Docker Compose, mas simple y reproducible.

Decision tomada:

El primer admin se creara mediante variables de entorno:

```text
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin
```

En el arranque, si no existe ningun usuario, el backend creara ese administrador inicial.

### 12.5. Worker y concurrencia

Se usara Arq con Redis.

Flujo:

1. El backend valida la peticion `POST /api/v1/audits/start`.
2. Crea `audit_session` en estado `PENDING`.
3. Encola job `run_audit(session_id)`.
4. El worker toma el job.
5. Marca sesion como `RUNNING`.
6. Ejecuta auditoria.
7. Marca `COMPLETED`, `FAILED` o `ABORTED`.

Concurrencia:

- La aplicacion debe permitir mas de una auditoria simultanea.
- Debe existir limite configurable, por ejemplo `MAX_CONCURRENT_AUDITS=2`.
- El limite se aplicara en el worker o en la cola, no solo en frontend.

Decision pendiente:

Valor inicial de concurrencia. Recomendacion: 2 auditorias simultaneas. Es suficiente para demostrar profesionalidad sin arriesgar sobrecarga.

Decision tomada:

La herramienta debe soportar desde el inicio varias auditorias simultaneas mediante workers y cola. El numero maximo de auditorias concurrentes sera configurable con `MAX_CONCURRENT_AUDITS`.

Valor inicial recomendado:

```text
MAX_CONCURRENT_AUDITS=2
```

Esto no significa que el sistema solo pueda tener dos auditorias en cola. Puede haber muchas auditorias pendientes, pero solo un numero limitado se ejecutara al mismo tiempo para no saturar la maquina ni los targets.

### 12.6. Semantica de aborto

`POST /api/v1/audits/{id}/abort` no mata violentamente el proceso. Cambia la sesion a `ABORTED_REQUESTED` o marca una bandera equivalente.

Recomendacion de estados:

```text
PENDING
RUNNING
ABORT_REQUESTED
ABORTED
COMPLETED
FAILED
```

El worker revisa el estado antes de cada peticion. Si detecta `ABORT_REQUESTED`, deja de enviar nuevas consultas y marca `ABORTED`.

Criterio:

Esto evita cortar una peticion a medias y deja la BD consistente.

### 12.7. Medicion HTTP precisa

Para medir TTFB correctamente con httpx, se debe usar streaming.

Pseudocodigo:

```python
t0 = time.perf_counter()
async with client.stream(method, url, headers=headers, json=payload) as response:
    status_code = response.status_code
    first_byte_at = None
    response_size = 0

    async for chunk in response.aiter_bytes():
        if first_byte_at is None:
            first_byte_at = time.perf_counter()
        response_size += len(chunk)

t1 = time.perf_counter()
ttfb_ms = (first_byte_at - t0) * 1000 if first_byte_at else (t1 - t0) * 1000
full_response_ms = (t1 - t0) * 1000
```

Notas:

- Si la respuesta no tiene cuerpo, `ttfb_ms` puede aproximarse al tiempo hasta headers.
- `full_response_ms` siempre debe guardarse si la peticion no falla antes.
- `latency_ms` sera igual a `ttfb_ms` en la primera version.

### 12.8. Construccion segura de payload

No se debe convertir el JSON a string y hacer reemplazos ingenuos si se puede evitar.

Opcion aceptable:

- Serializar `payload_template` a string.
- Reemplazar `{{QUERY}}`.
- Parsear de nuevo a JSON.
- Si falla, devolver error de validacion.

Opcion mejor:

- Recorrer recursivamente el JSON.
- Reemplazar `{{QUERY}}` solo en strings.

Recomendacion:

Implementar reemplazo recursivo. Es mas limpio y evita problemas con caracteres especiales dentro de la query.

### 12.9. Endpoint de resumen estadistico

`GET /api/v1/audits/{id}/summary` debe devolver una estructura estable para el frontend.

Ejemplo conceptual:

```json
{
  "session_id": "uuid",
  "metric": "ttfb_ms",
  "groups": [
    {
      "frequency": "high",
      "count": 1200,
      "mean_ms": 52.4,
      "median_ms": 50.1,
      "std_ms": 8.2,
      "p25_ms": 47.0,
      "p75_ms": 57.2,
      "p95_ms": 70.9,
      "error_rate": 0.01
    }
  ],
  "comparisons": [
    {
      "group_a": "high",
      "group_b": "low",
      "mean_difference_ms": 13.6,
      "welch_p_value": 0.0003,
      "cohens_d": 0.82,
      "evidence": "strong"
    }
  ]
}
```

Decision pendiente:

Umbrales de evidencia. Propuesta inicial, sujeta a validacion con datos reales:

- `insufficient`: menos de 30 muestras por grupo o demasiados errores.
- `weak`: p-value < 0.05 y Cohen's d >= 0.2.
- `moderate`: p-value < 0.01 y Cohen's d >= 0.5.
- `strong`: p-value < 0.001 y Cohen's d >= 0.8.

No debe bloquear la implementacion. Puede empezar devolviendo metricas y dejar `evidence` como experimental.

### 12.10. Exportacion

CSV:

- Una fila por resultado.
- Columnas iguales a `audit_results`.
- Incluir metadatos basicos de sesion en comentarios no es ideal para CSV. Mejor exportar tambien JSON.

JSON:

- Metadata de sesion.
- Target sin secretos completos.
- Dataset metadata.
- Summary estadistico.
- Resultados.

Decision pendiente:

Si los exports se generan en memoria al vuelo o se guardan en `/data/exports`. Recomendacion: para 5.000 queries se pueden generar al vuelo; guardar exports puede quedar para fase posterior.

Decision tomada:

En la primera version, los exports CSV/JSON se generaran al vuelo. Guardarlos fisicamente en `/data/exports` queda para una fase posterior si hace falta.

### 12.11. Logging y auditoria interna

Se necesitan logs estructurados.

Registrar:

- Inicio y fin de auditoria.
- Errores de target.
- Aborts.
- Fallos de dataset.
- Fallos de autenticacion.

No registrar:

- Authorization completo.
- Queries sensibles en logs de servidor, salvo que sea modo debug local.
- Respuestas completas del target.

Decision pendiente:

Guardar o no fragmentos de respuesta. Recomendacion: no guardar cuerpo de respuesta en la primera version, solo `status_code`, `response_size_bytes` y metricas temporales.

Decision tomada:

No se guardara el cuerpo de respuesta del target en la primera version. No es necesario para el objetivo principal y podria almacenar informacion sensible. Solo se guardaran metadatos: codigo HTTP, tamano de respuesta, errores y metricas temporales.

### 12.12. Politica de retencion y limpieza

Falta definir cuanto tiempo se conservan resultados y datasets.

Para primera version:

- No borrar automaticamente.
- Permitir borrar auditorias manualmente.
- Al borrar una auditoria, borrar resultados por cascade.
- Al borrar dataset, impedir borrado si hay auditorias asociadas o permitir borrado solo del archivo manteniendo metadata.

Decision pendiente:

Comportamiento al borrar datasets usados por auditorias. Recomendacion: no permitir borrar datasets con auditorias asociadas, salvo borrado forzado.

Decision tomada:

Se bloqueara el borrado normal de datasets que tengan auditorias asociadas. Si mas adelante se necesita, se podra anadir un borrado forzado con confirmacion explicita.

### 12.13. Frontend: estados y experiencia minima

Rutas:

```text
/login
/dashboard
/targets
/datasets
/audits/new
/audits/running/:id
/audits/results/:id
```

Estados que deben estar disenados:

- Loading.
- Empty state.
- Error state.
- Unauthorized.
- Audit running.
- Audit aborted.
- Audit failed.
- Audit completed.

Componentes clave:

- Sidebar.
- Topbar con usuario.
- Target form.
- Dataset upload.
- Audit wizard.
- Progress monitor.
- Results table.
- Summary cards.
- Scatter plot.
- Bar chart.
- Export buttons.

Recomendacion:

Usar TanStack Query para datos y polling. Evita hacer polling manual desordenado y simplifica cache en frontend.

### 12.14. Pruebas automatizadas

Backend:

- Tests unitarios de validacion de dataset.
- Tests de reemplazo `{{QUERY}}`.
- Tests de medicion HTTP usando un servidor fake.
- Tests de estadistica.
- Tests de endpoints protegidos por auth.
- Tests de abort.

Frontend:

- Tests de componentes criticos si da tiempo.
- Como minimo, validacion manual documentada para demo.

End-to-end:

- Docker Compose levanta backend, frontend, postgres, redis y worker.
- Target fake incluido para pruebas locales.

### 12.15. Target fake para desarrollo

Conviene crear un servicio o endpoint fake para probar la herramienta sin depender de un RAG real.

Opciones:

- Endpoint dentro del backend solo en modo desarrollo.
- Servicio `mock-rag` separado en Docker Compose.

Recomendacion:

Crear `mock-rag` como servicio separado. Puede responder con latencias artificiales diferentes segun palabras clave o etiquetas. Esto permite demostrar la herramienta en defensa aunque no haya un RAG real funcionando.

Ejemplo:

- Queries con "high" responden en 50 ms.
- Queries con "low" responden en 90 ms.
- Algunas respuestas tienen jitter aleatorio.

Importante:

Debe quedar documentado como target de prueba, no como resultado real.

Explicacion:

`mock-rag` no es un RAG real. Es un servicio falso de pruebas que simula una API tipo RAG. Sirve para desarrollar y demostrar la plataforma sin depender de un sistema externo.

Por ejemplo, el `mock-rag` puede exponer:

```text
POST /chat
```

Y responder con retardos artificiales:

- Queries con `frequency = high`: respuesta en torno a 50 ms.
- Queries con `frequency = medium`: respuesta en torno a 70 ms.
- Queries con `frequency = low`: respuesta en torno a 100 ms.
- Jitter aleatorio para parecer mas realista.

Utilidad:

- Permite probar que la herramienta mide bien.
- Permite probar workers, colas, abort, progreso y resultados.
- Permite hacer demos aunque no haya un RAG real arrancado.
- Permite validar graficas y resumen estadistico.

Limitacion:

No prueba la vulnerabilidad real. Solo prueba que la herramienta funciona correctamente. Los resultados importantes deben venir de targets reales o de tus PoC/RAG de investigacion.

Decision tomada:

Se incluira `mock-rag` desde el inicio como servicio de desarrollo y demostracion dentro de Docker Compose.

### 12.16. Variables de entorno definitivas

Propuesta:

```text
POSTGRES_DB=auditoria_rag
POSTGRES_USER=auditoria
POSTGRES_PASSWORD=auditoria
DATABASE_URL=postgresql+asyncpg://auditoria:auditoria@postgres:5432/auditoria_rag
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY=change-me
JWT_EXPIRE_MINUTES=1440
SECRET_ENCRYPTION_KEY=change-me
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin
DATASETS_DIR=/data/datasets
EXPORTS_DIR=/data/exports
MAX_DATASET_SIZE_MB=20
MAX_QUERIES_PER_AUDIT=5000
MAX_CONCURRENT_AUDITS=2
BACKEND_CORS_ORIGINS=http://localhost:5173
```

### 12.17. Migraciones

Usar Alembic desde el principio.

Regla:

No crear tablas directamente desde SQLAlchemy en produccion. Para desarrollo se puede facilitar, pero la version seria debe usar migraciones.

### 12.18. Preguntas que quedan abiertas

Estas son las decisiones que todavia conviene cerrar contigo:

1. Cifrado de headers sensibles en base de datos: si o no desde la primera version.
2. Creacion del primer admin: variables de entorno, CLI o pantalla bootstrap.
3. Concurrencia inicial: recomiendo 2 auditorias simultaneas.
4. Permitir campos extra en datasets: recomiendo si, ignorandolos.
5. Borrado de datasets usados: bloquear borrado o permitir borrado forzado.
6. Guardar cuerpo de respuesta del target: recomiendo no.
7. Incluir `mock-rag` en Docker Compose desde el inicio: recomiendo si, ayuda muchisimo a desarrollar y demostrar.

Estado actual de estas decisiones:

1. Cifrado de headers sensibles: decidido que si.
2. Primer admin: decidido por variables de entorno.
3. Concurrencia: decidido que habra auditorias simultaneas con limite configurable.
4. Campos extra en datasets: decidido que se permiten e ignoran.
5. Borrado de datasets usados: decidido bloquear borrado normal.
6. Guardar cuerpo de respuesta: decidido que no.
7. `mock-rag`: decidido incluirlo desde el inicio.

## 13. Especificacion consolidada para empezar codigo

Decision base actual:

- Docker Compose obligatorio.
- Backend FastAPI async.
- PostgreSQL con SQLAlchemy async y Alembic.
- Redis + Arq para workers.
- Frontend React + TypeScript.
- Autenticacion admin desde el inicio.
- POST recomendado para targets.
- TTFB metrica principal.
- Respuesta completa metrica secundaria.
- Maximo 5.000 queries por auditoria.
- Dataset con etiquetas en ingles.
- Resultados paginados.
- Export CSV/JSON.
- Summary estadistico.
- Cache no se configura manualmente; se observa indirectamente.
- `mock-rag` incluido como target simulado de desarrollo y demo.

Con esto ya se puede empezar la implementacion con bastante seguridad. Lo que queda abierto son decisiones de acabado profesional, no dudas estructurales.
