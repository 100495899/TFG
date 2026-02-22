import chromadb
from chromadb.utils import embedding_functions
import time
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
import nltk

NUM_DOCS = 301
NUM_RUIDO = NUM_DOCS - (NUM_DOCS//4)
NUM_PRUEBAS = 300
LONGITUD_EXACTA = 500
TAMANO_LOTE = 5000
NUM_DIGITOS = len(str(NUM_DOCS))


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
    
            
    plt.figure(figsize=(10, 8))
    plt.scatter(vectores_2d[:, 0], vectores_2d[:, 1], c='blue', label='Dataset', alpha=0.3, s=10)
    
 
    plt.title("Mapa del Espacio Vectorial de ChromaDB (Reducción PCA)")
    plt.xlabel("Componente Principal 1")
    plt.ylabel("Componente Principal 2")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.show()


print("[*] Iniciando el Laboratorio de Ataque de Canal Lateral (Timing Attack)...")

ruta_bd = "./bd_tfg_local"
client = chromadb.PersistentClient(path=ruta_bd)
emb_fn = embedding_functions.DefaultEmbeddingFunction()

collection = client.get_or_create_collection(name="coleccion_nltk", embedding_function=emb_fn)

if collection.count() == 0:
    print("\n[!] La base de datos esta vacia. Procediendo a descargar y vectorizar...")
    nltk.download('gutenberg', quiet=True)
    from nltk.corpus import gutenberg

    print("\n[*] Extrayendo y troceando los libros clasicos...")
    archivos_libros = gutenberg.fileids()
    textos_reales = []

    for archivo in archivos_libros:
        texto_completo = gutenberg.raw(archivo)
        for i in range(0, len(texto_completo), 1000):
            trozo = texto_completo[i : i + 1000]
            if len(trozo.strip()) > 50: 
                textos_reales.append(trozo)

    print(f"[*] Hemos extraido {len(textos_reales)} fragmentos.")

    ids = [f"doc_{i:07d}" for i in range(len(textos_reales))]

    print("\n[*] Vectorizando textos y guardando en ChromaDB.")
    inicio_insercion = time.perf_counter()

    for i in range(0, len(textos_reales), TAMANO_LOTE):

        fin_lote = min(i + TAMANO_LOTE, len(textos_reales))

        collection.add(
            documents=textos_reales[i:fin_lote],
            ids=ids[i:fin_lote]
        )
        print(f"   [*] Insertados {fin_lote}/{len(textos_reales)} documentos...")

    fin_insercion = time.perf_counter()
    print(f"[*] Base de datos lista en {fin_insercion - inicio_insercion:.2f} segundos.")
    print("[+] Base de datos poblada e indexada correctamente.\n")

else:
    print(f"\n[+] ¡La base de datos ya existe en el disco duro!")
    print(f"[+] Contiene {collection.count()} fragmentos. Saltando la fase de vectorización.")

#print("[*] Visualizando base de datos vectorial")

#visualizar_espacio_vectorial(collection)

print(f"[*] Iniciando bateria de ataques ({NUM_PRUEBAS} iteraciones por query)...")

tiempos_acierto = []
tiempos_fallo = []

query_acierto = "¿Quién es el capitán del barco ballenero Pequod y a quién persigue?"
query_fallo = "¿En qué casa de Hogwarts estudian Harry Potter y Ron Weasley?"

vector_acierto = emb_fn([query_acierto])
vector_fallo = emb_fn([query_fallo])

collection.query(query_embeddings=vector_acierto, n_results=1)


for i in range(NUM_PRUEBAS):

    inicio = time.perf_counter_ns()
    _ = collection.query(query_embeddings=vector_fallo, n_results=5)
    fin = time.perf_counter_ns()
    tiempos_fallo.append((fin - inicio) / 1000)
    
    inicio = time.perf_counter_ns()
    _ = collection.query(query_embeddings=vector_acierto, n_results=5)
    fin = time.perf_counter_ns()
    tiempos_acierto.append((fin - inicio) / 1000)

    print(f"Prueba {i}/{NUM_PRUEBAS}: Fallo: {tiempos_fallo[i]} Acierto: {tiempos_acierto[i]}")

print("[*] Ataque finalizado")

media_acierto = sum(tiempos_acierto) / len(tiempos_acierto)
media_fallo = sum(tiempos_fallo) / len(tiempos_fallo)

print("\n======== RESULTADOS =========")
print(f"Latencia Acierto: {media_acierto:.4f} ms")
print(f"Latncia Fallo: {media_fallo:.4f} ms")
print(f"Diferencia: {abs(media_acierto - media_fallo):.4f} ms")


plt.figure(figsize=(10, 6))
plt.hist(tiempos_acierto, bins=30, alpha=0.7, label='Acierto', color='red')
plt.hist(tiempos_fallo, bins=30, alpha=0.7, label='Fallo', color='blue')
plt.axvline(media_acierto, color='darkred', linestyle='dashed', linewidth=2)
plt.axvline(media_fallo, color='darkblue', linestyle='dashed', linewidth=2)
plt.title('Distribución de Latencias de Búsqueda Vectorial (ChromaDB HNSW)')
plt.xlabel('Tiempo de Búsqueda (Milisegundos)')
plt.ylabel('Frecuencia')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.6)
plt.show()