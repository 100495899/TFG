import chromadb
import time
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from sentence_transformers import SentenceTransformer
import random
import itertools
from sklearn.decomposition import PCA
import umap

NUM_PRUEBAS = 600

def visualizar_espacio_vectorial_optimizado(collection, num_muestras=50000):
    print(f"\n[*] Preparando visualización. Calculando tamaño total...")
    total_docs = collection.count()
    
    if total_docs == 0:
        print("[!] La colección está vacía.")
        return
        
    limite = min(num_muestras, total_docs)
    print(f"[*] Total en BD: {total_docs}. Extrayendo una muestra aleatoria ÚNICA de {limite} vectores...")

    indices_unicos = random.sample(range(total_docs), limite)
    ids_aleatorios = [f"doc_{i:09d}" for i in indices_unicos]
    
    print("[*] Descargando vectores de ChromaDB en lotes (para sortear el límite de SQLite)...")
    todos_los_embeddings = []
    tamano_lote = 5000 # Un número seguro que a SQLite le encanta
    
    # Bucle para descargar por viajes
    for i in range(0, limite, tamano_lote):
        lote_ids = ids_aleatorios[i : i + tamano_lote]
        datos = collection.get(ids=lote_ids, include=['embeddings'])
        todos_los_embeddings.extend(datos['embeddings'])
        print(f"    -> Viaje completado: {min(i + tamano_lote, limite)} / {limite} vectores...")
    
    print("\n[*] Calculando el mapa topológico (UMAP)...")
    reductor_umap = umap.UMAP(
            n_neighbors=15, 
            min_dist=0.1, 
            n_components=2, 
            metric='cosine', 
            random_state=100495899
        )
    
    vectores_2d = reductor_umap.fit_transform(todos_los_embeddings)
    
    print("[*] Dibujando los clústeres semánticos...")
    plt.figure(figsize=(14, 10))
    
    plt.scatter(vectores_2d[:, 0], vectores_2d[:, 1], c='purple', alpha=0.15, s=2, edgecolors='none')
    
    plt.title(f"Mapa Semántico del Espacio Vectorial (UMAP - Muestra: {limite})")
    plt.xlabel("Dimensión Topológica 1")
    plt.ylabel("Dimensión Topológica 2")
    
    plt.xticks([]) 
    plt.yticks([])
    
    ruta_imagen = "/workspace/mapa_semantico_umap.png"
    plt.savefig(ruta_imagen, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close() 
    
    print(f"[+] ¡Éxito! El mapa semántico se ha guardado en: {ruta_imagen}")

print("[*] Conectando a la base de datos en /workspace/pg19")
client = chromadb.PersistentClient(path="./workspace/pg19")

collection = client.get_collection(name="gutenberg_completo") 

print(f"[+] Coleccion cargada. Total de vectores en la BD: {collection.count()}")


print("[*] Cargando modelo de embeddings (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')


palabras_acierto = [
    "the", "of", "and", "to", "a", "in", "i", "that", "was", "his",
    "is", "as", "with", "for", "you", "had", "he", "not", "but", "at",
    "be", "by", "which", "this", "have", "from", "him", "or", "were",
    "we", "one", "are", "an", "their", "there", "when", "been", "who", "will",
    "would", "what", "out", "more", "if", "man", "no", "so", "#amp", "said",
    "could", "very", "some", "your", "time", "up", "upon",
    "can", "only", "about"
]

palabras_fallo = [
    "ashjfhwiuhrt", "plorvex", "drimtal", "zunthera", "krevon", "lintora",
    "shavix", "brontel", "virexon", "talnori", "zempra", "florvyn",
    "kradim", "yenthor", "plavion", "drastel", "monvira", "xentari",
    "zolmira", "trivon", "blanter", "shorvex", "prantel", "vornika",
    "xelvorn", "drimora", "quintal", "zervion", "plenthor", "arvinta",
    "krovent", "limvora", "traxion", "blenvar", "sorvinta", "prelthor",
    "zanviro", "crontel", "velnira", "droxen", "shalvorn", "prastel",
    "zonther", "vrelmira", "klentor", "drivon", "morxina", "veltrix",
    "zanthir", "plorxen", "trivora", "xeltrum", "bravion", "sornika",
    "klavira", "prontel", "dravion", "selthora", "vrontex", "plimora",
    "krenthor", "zalmira", "trovina", "blenxar"
]

querys_acierto = []

querys_fallo = []

NUM_QUERYS = 50
LONGITUD_PALABRAS_FALLO = 10
LONGITUD_PALABRAS_ACIERTO = 15

print("[*] Generando queries aleatorias de prueba...")

for _ in range(NUM_QUERYS):
    query_acierto = " ".join(random.choices(palabras_acierto, k=LONGITUD_PALABRAS_ACIERTO))
    querys_acierto.append(query_acierto)

    query_fallo = " ".join(random.choices(palabras_fallo, k=LONGITUD_PALABRAS_FALLO))
    querys_fallo.append(query_fallo)

tiempos_acierto = []
tiempos_fallo = []

#visualizar_espacio_vectorial_optimizado(collection)

print(f"[*] Iniciando ataque midiendo latencias de busqueda")

for i in range(NUM_PRUEBAS):
    q_acierto = random.choice(querys_acierto)
    q_fallo = random.choice(querys_fallo)

    vector_acierto = model.encode([q_acierto]).tolist()
    vector_fallo = model.encode([q_fallo]).tolist()

    inicio = time.perf_counter()
    _ = collection.query(query_embeddings=vector_fallo, n_results=5)
    fin = time.perf_counter()
    tiempos_fallo.append((fin - inicio) * 1000)
    
    inicio = time.perf_counter()
    _ = collection.query(query_embeddings=vector_acierto, n_results=5)
    fin = time.perf_counter()
    tiempos_acierto.append((fin - inicio) * 1000)

    # Imprimir progreso por terminal
    print(f"Prueba {i+1}/{NUM_PRUEBAS}: Fallo: {tiempos_fallo[i]:.4f} ms | Acierto: {tiempos_acierto[i]:.4f} ms")

print("\n[+] Ataque finalizado. Generando analisis estadistico...")


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

plt.savefig('grafica_resultados_runpod.png', dpi=300)
print("\n[+] Grafica guardada como 'grafica_resultados_runpod.png'")
plt.show()