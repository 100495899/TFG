# Target RAG Para RunPod

Esta carpeta contiene un RAG externo usado para probar `Auditoria_RAG_Timing` contra un servicio HTTP realista.

No forma parte del despliegue principal con Docker Compose. La herramienta de auditoria lo trata como un target externo y lo llama a traves del endpoint `/chat`.

## Configuracion

Copia la plantilla de entorno:

```bash
cp .env.example .env
```

Solo `RAG_API_KEY` se configura mediante variable de entorno, porque es un secreto. El resto de valores quedan fijados en `app/main.py` para reproducir el entorno de pruebas en RunPod:

- ruta de Chroma: `/workspace/workspace/pg19`
- coleccion: `gutenberg_completo`
- embeddings: `all-MiniLM-L6-v2`
- LLM: `HuggingFaceTB/SmolLM2-135M-Instruct`
- retriever `k`: `20`

## Ejecucion

Instala las dependencias en el entorno de RunPod y arranca la API:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

En la herramienta de auditoria, el target debe configurarse con la URL publica de RunPod seguida de `/chat`. La clave debe enviarse en el header `X-API-Key`.
