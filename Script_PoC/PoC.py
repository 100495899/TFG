import chromadb
from chromadb.utils import embedding_functions
import random
import time
import numpy as np
import matplotlib.pyplot as plt
import gc
from sklearn.decomposition import PCA
import requests

NUM_DOCS = 301
NUM_RUIDO = NUM_DOCS - (NUM_DOCS//4)
NUM_PRUEBAS = 30
LONGITUD_EXACTA = 500
TAMANO_LOTE = 5000
NUM_DIGITOS = len(str(NUM_DOCS))
MODELO_OLLAMA = "llama3.2"

vocabulario_it = ["servidor", "red", "nube", "código", "python", "base de datos", "firewall", "router", "API", "microservicios", "docker", "bug", "parche", "backend", "frontend", "latencia", "ciberseguridad", "despliegue"]
vocabulario_finanzas = ["presupuesto", "inversión", "ROI", "fiscal", "facturación", "auditoría", "impuestos", "balance", "gastos", "ingresos", "EBITDA", "activos", "pasivos", "trimestre", "bolsa", "acciones", "tesorería"]
vocabulario_marketing = ["campaña", "SEO", "leads", "conversión", "redes sociales", "audiencia", "branding", "publicidad", "anuncios", "engagement", "funnel", "CTR", "target", "newsletter", "patrocinio", "eventos"]
vocabulario_rrhh = ["empleado", "despido", "contrato", "entrevista", "confidencial", "beneficios", "baja", "evaluación", "desempeño", "retención", "talento", "horario", "fichaje", "formación", "nómina", "sindicato"]
    

def generador_textos_aleatorios(vocabulario):
  
    num_palabras = (LONGITUD_EXACTA // 4) + 1

    palabras_elegidas = random.choices(vocabulario, k=num_palabras)

    texto_completo = " ".join(palabras_elegidas)
        
    return texto_completo[:LONGITUD_EXACTA]


def visualizar_espacio_vectorial(collection):
    print("\n[*] Extrayendo vectores y calculando el mapa 2D (PCA)...")
    
    datos = collection.get(include=['embeddings'])
    embeddings = datos['embeddings']
    ids = datos['ids']
    
    if len(embeddings) == 0:
        print("[!] La colección está vacía.")
        return

    pca = PCA(n_components=2)
    vectores_2d = pca.fit_transform(embeddings)
    
    x_ruido, y_ruido = [], []
    x_secreto, y_secreto = [], []
    
    for i, id_doc in enumerate(ids):
        if id_doc in ids_secretos:
            x_secreto.append(vectores_2d[i][0])
            y_secreto.append(vectores_2d[i][1])
        else:
            x_ruido.append(vectores_2d[i][0])
            y_ruido.append(vectores_2d[i][1])
            
    plt.figure(figsize=(10, 8))
    plt.scatter(x_ruido, y_ruido, c='blue', label='Ruido Corporativo', alpha=0.3, s=10)
    
    if x_secreto:
        plt.scatter(x_secreto, y_secreto, c='red', label='Documento Secreto', marker='*', s=300, edgecolors='black')
        
    plt.title("Mapa del Espacio Vectorial de ChromaDB (Reducción PCA)")
    plt.xlabel("Componente Principal 1")
    plt.ylabel("Componente Principal 2")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.show()


def gaficas_tiempos(tiempos_acierto, tiempos_fallo):
    tiempos_acierto_ms = np.array(tiempos_acierto) / 1_000_000
    tiempos_fallo_ms = np.array(tiempos_fallo) / 1_000_000

    media_acierto = np.mean(tiempos_acierto_ms)
    media_fallo = np.mean(tiempos_fallo_ms)

    print("\n=== RESULTADOS DEL EXPERIMENTO ===")
    print(f"Media de latencia (Documento EXISTE): {media_acierto:.4f} ms")
    print(f"Media de latencia (Documento NO EXISTE): {media_fallo:.4f} ms")
    print(f"Diferencia (Señal): {abs(media_acierto - media_fallo):.4f} ms")


    plt.figure(figsize=(10, 6))
    plt.hist(tiempos_acierto_ms, bins=30, alpha=0.7, label='Documento EXISTE (Acierto)', color='red')
    plt.hist(tiempos_fallo_ms, bins=30, alpha=0.7, label='Documento NO EXISTE (Fallo)', color='blue')
    plt.axvline(media_acierto, color='darkred', linestyle='dashed', linewidth=2)
    plt.axvline(media_fallo, color='darkblue', linestyle='dashed', linewidth=2)
    plt.title('Distribución de Latencias de Búsqueda Vectorial (ChromaDB HNSW)')
    plt.xlabel('Tiempo de Búsqueda (Milisegundos)')
    plt.ylabel('Frecuencia')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.show()



print("[*] Iniciando el Laboratorio de Ataque de Canal Lateral (Timing Attack)...")

client = chromadb.EphemeralClient()

emb_fn = embedding_functions.DefaultEmbeddingFunction()

collection = client.create_collection(name="tfg_rag_db", embedding_function=emb_fn)

print(f"[*] Generando {NUM_RUIDO} documentos de ruido de {LONGITUD_EXACTA} chars...")

textos_ruido = []
ids_ruido = []

for i in range(NUM_RUIDO):
    if i < NUM_RUIDO/3:
        texto = generador_textos_aleatorios(vocabulario_finanzas)

    elif NUM_RUIDO/3 < i < 2*NUM_RUIDO/3:
        texto = generador_textos_aleatorios(vocabulario_it)
    
    else:
        texto = generador_textos_aleatorios(vocabulario_marketing)


    textos_ruido.append(texto)

    ids_ruido.append(f"doc_{i:0{NUM_DIGITOS}d}")


print(f"[*] Generando {NUM_DOCS - NUM_RUIDO} documentos secretos de {LONGITUD_EXACTA} chars...")

texto_secretos = []
ids_secretos = []

for i in range(NUM_RUIDO, NUM_DOCS):

    texto = generador_textos_aleatorios(vocabulario_rrhh)

    texto_secretos.append(texto)
    ids_secretos.append(f"doc_{i:0{NUM_DIGITOS}d}")


textos_completos = textos_ruido + texto_secretos
ids_completos = ids_ruido + ids_secretos

print(f"[*] Insertando {len(textos_completos)} documentos en lotes de {TAMANO_LOTE}...")

for i in range(0, len(textos_completos), TAMANO_LOTE):

    lote_docs = textos_completos[i : i + TAMANO_LOTE]
    lote_ids = ids_completos[i : i + TAMANO_LOTE]

    collection.add(
        documents=lote_docs,
        ids=lote_ids
    )
    print(f"    [+] Lote insertado: del {i} al {i + len(lote_docs) - 1}")

print("[+] Base de datos poblada e indexada correctamente.\n")

print("[*] Visualizando base de datos vectorial")

#visualizar_espacio_vectorial(collection)

print(f"[*] Iniciando bateria de ataques ({NUM_PRUEBAS} iteraciones por query)...")

def consultar_ollama(pregunta, contexto):
    
    prompt_completo = f"""Usa el siguiente contexto corporativo para responder a la pregunta. Si la respuesta NO está en el contexto, di EXACTAMENTE y ÚNICAMENTE: 'No tengo información sobre eso.' No inventes nada. 
        Contexto: {contexto}
        Pregunta: {pregunta}
        Respuesta:"""

    payload = {
        "model": MODELO_OLLAMA,
        "prompt": prompt_completo,
        "stream": False
    }
    
    inicio = time.perf_counter()
    respuesta = requests.post("http://localhost:11434/api/generate", json=payload)
    fin = time.perf_counter()
    
    tiempo_total_segundos = fin - inicio
    texto_generado = respuesta.json().get("response", "")
    
    return tiempo_total_segundos, texto_generado

tiempos_acierto = []
tiempos_fallo = []

tiempos_acierto_llm = []
tiempos_fallo_llm = []

query_acierto = "dame informacion sobre despidos y entrevistas"
query_fallo = "cual es la receta de la tarta de manzana"

vector_acierto = emb_fn([query_acierto])
vector_fallo = emb_fn([query_fallo])

collection.query(query_embeddings=vector_acierto, n_results=1)


for i in range(NUM_PRUEBAS):

    inicio = time.perf_counter_ns()
    resultados_fallo = collection.query(query_embeddings=vector_fallo, n_results=5)
    fin = time.perf_counter_ns()
    tiempos_fallo.append(fin - inicio)

    contexto_fallo = " ".join(resultados_fallo['documents'][0])
    tiempo_fallo, respuesta_fallo = consultar_ollama(query_fallo, contexto_fallo)
    tiempos_fallo_llm.append(tiempo_fallo)
    
    inicio = time.perf_counter_ns()
    resultados_acierto = collection.query(query_embeddings=vector_acierto, n_results=5)
    fin = time.perf_counter_ns()
    tiempos_acierto.append(fin - inicio)

    contexto_acierto = " ".join(resultados_acierto['documents'][0])
    tiempo_acierto, respuesta_acierto = consultar_ollama(query_acierto, contexto_acierto)
    tiempos_acierto_llm.append(tiempo_acierto)

print("\n[*] ¡Ataque finalizado con éxito!")

gaficas_tiempos(tiempos_acierto, tiempos_fallo)

gaficas_tiempos(tiempos_acierto_llm, tiempos_fallo_llm)
