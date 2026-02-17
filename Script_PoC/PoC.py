import chromadb
from chromadb.utils import embedding_functions
import random
import time
import numpy as np
import matplotlib.pyplot as plt
import gc
from sklearn.decomposition import PCA

NUM_RUIDO = 300
NUM_PRUEBAS = 50
LONGITUD_EXACTA = 500
TAMANO_LOTE = 5000
NUM_DIGITOS = len(str(NUM_RUIDO))

def generador_textos_aleatorios(longitud_deseada):
    vocabulario = [
        "el", "la", "los", "las", "un", "una", "empresa", "informe", "proyecto", 
        "datos", "sistema", "usuario", "reunion", "cliente", "presupuesto", 
        "analisis", "desarrollo", "seguridad", "red", "servidor", "ventas", 
        "marketing", "objetivos", "trimestre", "resultados", "recursos", "humanos",
        "tecnologia", "innovacion", "estrategia", "plan", "equipo", "gestion"
    ]
    
    num_palabras = (longitud_deseada // 2) + 1

    palabras_elegidas = random.choices(vocabulario, k=num_palabras)

    texto_completo = " ".join(palabras_elegidas)
        
    return texto_completo[:longitud_deseada]


def visualizar_espacio_vectorial(collection, id_secreto):
    print("\n[*] Extrayendo vectores y calculando el mapa 2D (PCA)...")
    
    # 1. Le pedimos a ChromaDB que nos devuelva TODOS los vectores
    datos = collection.get(include=['embeddings'])
    embeddings = datos['embeddings']
    ids = datos['ids']
    
    if len(embeddings) == 0:
        print("[!] La colección está vacía.")
        return

    # 2. Aplastamos de 384 dimensiones a 2 dimensiones
    pca = PCA(n_components=2)
    vectores_2d = pca.fit_transform(embeddings)
    
    # 3. Separamos las coordenadas para pintarlas de distinto color
    x_ruido, y_ruido = [], []
    x_secreto, y_secreto = [], []
    
    for i, id_doc in enumerate(ids):
        if id_doc == id_secreto:
            x_secreto.append(vectores_2d[i][0])
            y_secreto.append(vectores_2d[i][1])
        else:
            x_ruido.append(vectores_2d[i][0])
            y_ruido.append(vectores_2d[i][1])
            
    # 4. Dibujamos el mapa
    plt.figure(figsize=(10, 8))
    plt.scatter(x_ruido, y_ruido, c='blue', label='Ruido Corporativo', alpha=0.3, s=10)
    
    # Pintamos el secreto como una estrella roja gigante
    if x_secreto:
        plt.scatter(x_secreto, y_secreto, c='red', label='Documento Secreto', marker='*', s=300, edgecolors='black')
        
    plt.title("Mapa del Espacio Vectorial de ChromaDB (Reducción PCA)")
    plt.xlabel("Componente Principal 1")
    plt.ylabel("Componente Principal 2")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.show()

print("[*] Iniciando el Laboratorio de Ataque de Canal Lateral (Timing Attack)...")

client = chromadb.EphemeralClient()

emb_fn = embedding_functions.DefaultEmbeddingFunction()

collection = client.create_collection(name="tfg_rag_db", embedding_function=emb_fn)

print(f"[*] Generando e insertando {NUM_RUIDO} documentos de ruido de {LONGITUD_EXACTA} chars...")

textos_ruido = []
ids_ruido = []

for i in range(NUM_RUIDO):
   
    texto = generador_textos_aleatorios(LONGITUD_EXACTA)
    textos_ruido.append(texto)

    ids_ruido.append(f"doc_{i:0{NUM_DIGITOS}d}")

texto_base = "CONFIDENCIAL: listado oficial de despidos de la empresa las siguientes personas perderan su empleo "

texto_secreto = texto_base + generador_textos_aleatorios(LONGITUD_EXACTA - len(texto_base))
id_secreto = f"doc_{NUM_RUIDO}"

textos_ruido.append(texto_secreto)
ids_ruido.append(id_secreto)

print(f"[*] Insertando {len(textos_ruido)} documentos en lotes de {TAMANO_LOTE}...")

for i in range(0, len(textos_ruido), TAMANO_LOTE):

    lote_docs = textos_ruido[i : i + TAMANO_LOTE]
    lote_ids = ids_ruido[i : i + TAMANO_LOTE]

    collection.add(
        documents=lote_docs,
        ids=lote_ids
    )
    print(f"    [+] Lote insertado: del {i} al {i + len(lote_docs) - 1}")

print("[+] Base de datos poblada e indexada correctamente.\n")

print("[*] Visualizando base de datos vectorial")

visualizar_espacio_vectorial(collection, id_secreto)

print(f"[*] Iniciando bateria de ataques ({NUM_PRUEBAS} iteraciones por query)...")

tiempos_acierto = []
tiempos_fallo = []

query_acierto = "¿Dónde está la lista de despidos?"
query_fallo = "¿Cuál es la receta secreta de la tarta de manzana?"

vector_acierto = emb_fn([query_acierto])
vector_fallo = emb_fn([query_fallo])

collection.query(query_embeddings=vector_acierto, n_results=1)

gc.disable()

for i in range(NUM_PRUEBAS):
    # --- PRUEBA 1: Buscar algo que NO está ---
    inicio = time.perf_counter_ns()
    _ = collection.query(query_embeddings=vector_fallo, n_results=100)
    fin = time.perf_counter_ns()
    tiempos_fallo.append(fin - inicio)
    
    # --- PRUEBA 2: Buscar algo que SÍ está ---
    inicio = time.perf_counter_ns()
    _ = collection.query(query_embeddings=vector_acierto, n_results=100)
    fin = time.perf_counter_ns()
    tiempos_acierto.append(fin - inicio)

gc.enable()

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