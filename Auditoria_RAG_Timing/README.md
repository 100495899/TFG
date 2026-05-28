# RAG Timing Audit Platform

Plataforma de auditoria black-box para medir canales laterales de latencia en sistemas RAG.

## Arranque rapido

```bash
cp .env.example .env
docker compose up --build
```

Servicios:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Mock RAG: http://localhost:8010/health

Credenciales iniciales por defecto:

- Email: `admin@example.com`
- Password: `admin1234`

## Dataset esperado

```json
[
  {
    "query": "high latency test",
    "frequency": "high",
    "length": "short"
  }
]
```

Valores validos:

- `frequency`: `high`, `medium`, `low`, `null`
- `length`: `short`, `medium`, `long`

## Target de prueba

Usa el servicio `mock-rag` para validar el flujo:

- URL desde backend/worker: `http://mock-rag:8010/chat`
- Metodo: `POST`
- Payload:

```json
{
  "question": "{{QUERY}}"
}
```

`mock-rag` simula latencias artificiales. Sirve para desarrollo y demo, no para demostrar una vulnerabilidad real.
