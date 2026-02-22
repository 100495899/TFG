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

for i in range(20):

    vector_acierto = emb_fn([querys_acierto[i]])
    vector_fallo = emb_fn([querys_fallo[i]])

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