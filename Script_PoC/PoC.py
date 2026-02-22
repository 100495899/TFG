import chromadb
from chromadb.utils import embedding_functions
import time
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
import nltk
from nltk.corpus import gutenberg
import random
from scipy import stats
import seaborn as sns

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

nltk.download('gutenberg', quiet=True)

client = chromadb.EphemeralClient()
emb_fn = embedding_functions.DefaultEmbeddingFunction()
collection = client.create_collection(name="tfg_rag_db", embedding_function=emb_fn)

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

ids = [f"doc_{i:05d}" for i in range(len(textos_reales))]

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

print("[*] Visualizando base de datos vectorial")

visualizar_espacio_vectorial(collection)

print(f"[*] Iniciando bateria de ataques ({NUM_PRUEBAS} iteraciones por query)...")

print(f"[*] Iniciando bateria de ataques ({NUM_PRUEBAS} iteraciones por query)...")

tiempos_acierto = []
tiempos_fallo = []

querys_acierto = [
    "¿Quién es el capitán del barco ballenero Pequod y a quién persigue?",
    "¿Por qué cae Alicia por el agujero del conejo blanco?",
    "¿Qué profecía le hacen las tres brujas a Macbeth en el páramo?",
    "¿Cómo muere el fantasma del rey y qué le pide a su hijo?",
    "¿Con quién se casa finalmente Emma Woodhouse?",
    "¿Quién apuñala a Julio César en el Senado de Roma?",
    "¿Cuál es el papel de Satanás al tentar a Eva en el jardín?",
    "¿Qué animal del bosque acompaña siempre a Buster Bear?",
    "¿Cómo resuelve el Padre Brown el misterio de la cruz azul?",
    "¿Por qué el capitán Ahab tiene una pierna de marfil?",
    "¿Qué locuras le dice el Sombrerero Loco a la niña durante la fiesta del té?",
    "¿Qué ocurre con el cráneo del bufón Yorick en el cementerio?",
    "¿Cómo convence Lady Macbeth a su marido para cometer el asesinato?",
    "¿Qué relación de parentesco tienen Elinor y Marianne Dashwood?",
    "¿Quién es el capitán Wentworth y por qué Anne lo rechazó años atrás?",
    "¿Qué significa el canto a las hojas de hierba del poeta?",
    "¿Por qué el sacerdote sospecha del famoso ladrón Flambeau?",
    "¿Cómo describe el ángel la expulsión de Adán y Eva del paraíso?",
    "¿Qué consejo le da la Oruga azul fumando en pipa a Alicia?",
    "¿Cómo reacciona Bruto ante el fantasma de César antes de la batalla?"
]

querys_fallo = [
    "¿En qué casa de Hogwarts estudian Harry Potter y Ron Weasley?",
    "¿Cómo funciona el motor warp de la nave espacial Enterprise?",
    "¿Quién destruye el Anillo Único en el Monte del Destino?",
    "¿Cuál es la fórmula química para sintetizar plástico metacrilato?",
    "¿Qué selección nacional ganó el mundial de fútbol en Sudáfrica 2010?",
    "¿Cómo se entrena un modelo de lenguaje basado en arquitectura Transformers?",
    "¿Quiénes son los caminantes blancos y cómo cruzan el muro de hielo?",
    "¿Cuál fue la tasa de inflación media de la Unión Europea en 2023?",
    "¿Cómo se instala la librería de React en un proyecto de Node.js?",
    "¿Por qué el titán Thanos decide reunir las gemas del infinito?",
    "¿Qué ingredientes exactos lleva la auténtica pizza margarita napolitana?",
    "¿Cómo funciona la tecnología blockchain en las criptomonedas como Bitcoin?",
    "¿Cuáles son los síntomas principales de la variante omicron del virus?",
    "¿Qué ocurre al final de la película Matrix cuando Neo detiene las balas?",
    "¿Cómo se configura un servidor virtual en la nube de Amazon AWS?",
    "¿Quién fue el cantante principal y compositor de la banda de rock Queen?",
    "¿Cuáles son los movimientos legales para hacer un enroque en ajedrez?",
    "¿Qué propone la teoría de cuerdas en la física cuántica moderna?",
    "¿Cómo realizan el proceso de fotosíntesis las plantas de interior sin luz directa?",
    "¿Cuál fue el motivo político principal de la caída del muro de Berlín en 1989?"
]



collection.query(query_embeddings=emb_fn([querys_fallo[3]]), n_results=5)

for i in range(NUM_PRUEBAS):

    q_acierto = random.choice(querys_acierto)
    q_fallo = random.choice(querys_fallo)

    vector_acierto = emb_fn([q_acierto])
    vector_fallo = emb_fn([q_fallo])

    inicio = time.perf_counter()
    _ = collection.query(query_embeddings=vector_fallo, n_results=5)
    fin = time.perf_counter()
    tiempos_fallo.append((fin - inicio) * 1000)
    
    inicio = time.perf_counter()
    _ = collection.query(query_embeddings=vector_acierto, n_results=5)
    fin = time.perf_counter()
    tiempos_acierto.append((fin - inicio) * 1000)

    print(f"Prueba {i}/{NUM_PRUEBAS}: Fallo: {tiempos_fallo[i]} Acierto: {tiempos_acierto[i]}")

print("[*] Ataque finalizado")

media_acierto = np.mean(tiempos_acierto)
media_fallo = np.mean(tiempos_fallo)
mediana_acierto = np.median(tiempos_acierto)
mediana_fallo = np.median(tiempos_fallo)

todos_los_tiempos = tiempos_acierto + tiempos_fallo
limite_superior = np.percentile(todos_los_tiempos, 99)

aciertos_limpios = [t for t in tiempos_acierto if t <= limite_superior]
fallos_limpios = [t for t in tiempos_fallo if t <= limite_superior]

media_a = np.mean(aciertos_limpios)
media_f = np.mean(fallos_limpios)
mediana_a = np.median(aciertos_limpios)
mediana_f = np.median(fallos_limpios)

print(f"    -> Se han filtrado {len(tiempos_acierto) - len(aciertos_limpios)} picos en aciertos.")
print(f"    -> Se han filtrado {len(tiempos_fallo) - len(fallos_limpios)} picos en fallos.")

t_stat, p_value = stats.ttest_ind(aciertos_limpios, fallos_limpios)

print("\n======== RESULTADOS =========")
print("------------Sin Limpiar---------------")
print(f"Media Acierto: {media_acierto:.4f} ms")
print(f"Media Fallo: {media_fallo:.4f} ms")
print(f"Diferencia Media: {abs(media_acierto - media_fallo):.4f} ms")
print(f"Mediana Acierto: {mediana_acierto:.4f} ms")
print(f"Mediana Fallo: {mediana_fallo:.4f} ms")
print(f"Diferencia Mediana: {abs(mediana_acierto - mediana_fallo):.4f} ms")

print("------------Limpio---------------")
print(f"Media Acierto: {media_a:.4f} ms")
print(f"Media Fallo: {media_f:.4f} ms")
print(f"Diferencia Media: {abs(media_a - media_f):.4f} ms")
print(f"Mediana Acierto: {mediana_a:.4f} ms")
print(f"Mediana Fallo: {mediana_f:.4f} ms")
print(f"Diferencia Mediana: {abs(mediana_a - mediana_f):.4f} ms")

print("--- ANALISIS DE SIGNIFICANCIA (P-VALUE) ---")
print(f"P-Value: {p_value:.10f}")


plt.figure(figsize=(10, 6))
sns.kdeplot(aciertos_limpios, fill=True, color="red", label=f"Acierto (Media: {media_a:.2f} ms)", alpha=0.5)
sns.kdeplot(fallos_limpios, fill=True, color="blue", label=f"Fallo (Media: {media_f:.2f} ms)", alpha=0.5)
plt.axvline(media_a, color='darkred', linestyle='dashed', linewidth=2)
plt.axvline(media_f, color='darkblue', linestyle='dashed', linewidth=2)
plt.title('Distribución de Latencias de Búsqueda Vectorial (ChromaDB HNSW)')
plt.xlabel('Tiempo de Búsqueda (Milisegundos)', fontsize=12)
plt.ylabel('Densidad de Probabilidad', fontsize=12)
plt.legend(loc="upper right")
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()