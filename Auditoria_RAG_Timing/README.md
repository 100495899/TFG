# Auditoría RAG Timing

Herramienta web para auditar sistemas RAG externos mediante diferencias de latencia observables desde una API HTTP. La aplicación permite configurar targets, cargar datasets, ejecutar auditorías en segundo plano, consultar resultados e iniciar inferencias de términos usando una calibración previa.

## Requisitos

- Docker
- Docker Compose
- Git
- Navegador web moderno

No es necesario instalar Python ni Node en la máquina host para ejecutar la herramienta con Docker Compose.

## Obtener El Código

Si se parte desde un repositorio remoto:

```bash
git clone <URL_DEL_REPOSITORIO>
cd <CARPETA_DEL_REPOSITORIO>/Auditoria_RAG_Timing
```

Si ya se dispone de la carpeta del proyecto:

```bash
cd Auditoria_RAG_Timing
```

Todos los comandos siguientes deben ejecutarse desde la carpeta `Auditoria_RAG_Timing`, donde se encuentra `docker-compose.yml`.

## Configuración

Copia la plantilla de entorno:

```bash
cp .env.example .env
```

Antes de arrancar la herramienta, revisa el archivo `.env` y cambia los valores necesarios. Las variables principales son:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: configuración de PostgreSQL.
- `DATABASE_URL`: conexión usada por el backend y el worker.
- `REDIS_URL`: conexión a Redis para la cola de trabajos.
- `JWT_SECRET_KEY`: clave usada para firmar las sesiones.
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`: credenciales del usuario administrador inicial.
- `DATASETS_DIR`: ruta interna donde se guardan los datasets subidos.
- `BACKEND_CORS_ORIGIN`: origen permitido para el frontend.
- `VITE_API_BASE_URL`: URL del backend usada durante la construcción del frontend.

El archivo `.env` contiene configuración local y no debe subirse al repositorio.

## Arranque

Levanta todos los servicios con:

```bash
docker compose up --build
```

Servicios incluidos:

- `postgres`: base de datos principal.
- `redis`: cola de trabajos.
- `backend`: API FastAPI y migraciones Alembic.
- `worker`: ejecución en segundo plano de auditorías e inferencias.
- `frontend`: interfaz React servida por Nginx.

El backend ejecuta las migraciones automáticamente al arrancar mediante `alembic upgrade head`.

## Acceso

Una vez levantados los contenedores:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Documentación de la API: `http://localhost:8000/docs`

El inicio de sesión se realiza con `ADMIN_EMAIL` y `ADMIN_PASSWORD`, definidos en `.env`.

## Comandos Útiles

Parar los servicios sin borrar datos:

```bash
docker compose down
```

Reconstruir las imágenes y levantar de nuevo:

```bash
docker compose up --build
```

Ver el estado de los servicios:

```bash
docker compose ps
```

Eliminar servicios y volúmenes persistentes:

```bash
docker compose down -v
```

Este último comando borra los datos almacenados en PostgreSQL y los datasets guardados en el volumen de Docker. No debe usarse si se quieren conservar auditorías, inferencias o resultados.
