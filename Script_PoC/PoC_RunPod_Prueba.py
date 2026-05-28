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


def ejecutar_bateria_pruebas(querys, model, collection, num_pruebas, nombre_prueba):

    tiempos = []
    print(f"\n[*] Iniciando batería de pruebas: {nombre_prueba} ({num_pruebas} iteraciones)")
    
    for i in range(num_pruebas):
        # 1. Elegir query al azar y vectorizar FUERA del tiempo
        q = random.choice(querys)
        print(f"Querie {i + 1}: {q}")
        vector_query = model.encode([q]).tolist()
        
        # 2. Medición pura de latencia en ChromaDB
        inicio = time.perf_counter()
        _ = collection.query(query_embeddings=vector_query, n_results=5)
        fin = time.perf_counter()
        
        tiempos.append((fin - inicio) * 1000)
        
        # Mostrar progreso por consola cada 100 iteraciones
       
        print(f" -> Progreso: {i+1}/{num_pruebas} Tiempo: {(fin - inicio) * 1000}")
            
    # 3. Limpieza estadística (Percentil 99)
    limite = np.percentile(tiempos, 99)
    tiempos_limpios = [t for t in tiempos if t <= limite]
    
    picos_borrados = len(tiempos) - len(tiempos_limpios)
    media = np.mean(tiempos_limpios)
    print(f"  [+] Batería terminada. Media: {media:.4f} ms (Picos filtrados: {picos_borrados})")
    
    return tiempos_limpios

print("[*] Conectando a la base de datos en /workspace/pg19")
client = chromadb.PersistentClient(path="./workspace/pg19")

collection = client.get_collection(name="gutenberg_completo") 

print(f"[+] Coleccion cargada. Total de vectores en la BD: {collection.count()}")


print("[*] Cargando modelo de embeddings (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')


querys_alta = [
    "A man spending his day thinking about things.",
    "The man worked all day to build that thing.",
    "Every day the man found a new thing to do.",
    "That thing took the man a whole day to finish.",
    "A young man looking at a strange thing during the day.",
    "The old man looked at the house with his eyes.",
    "A time will come when the man sees the light of day.",
    "The eyes of the man showed he had no time.",
    "Nothing is a better thing for a man than a good day.",
    "He spent a long time looking at the thing in the house.",
    "The man opened his eyes and saw the day.",
    "Time passes fast when a man is busy with a thing.",
    "Every man needs a house to live in one day.",
    "The thing in the house caught the eye of the man.",
    "Day after day, the man gave his time to the house."
]

querys_synonyms = [
    "A person spending his morning thinking about many things.",
    "The individual worked all hours to build that object.",
    "Every morning the guy found a new task to do.",
    "That object took the fellow a whole afternoon to finish.",
    "A young person looking at a strange item during the daytime.",
    "The old fellow looked at the house with his eyes.",
    "A moment will come when the person sees the morning light.",
    "The eyes of the individual showed he had no moment to spare.",
    "Nothing is a better object for a person than a calm morning.",
    "He spent a long period looking at the item in the house.",
    "The guy opened his eyes and saw the daylight.",
    "Hours pass fast when a person is busy with an object.",
    "Every individual needs a house to live in one morning.",
    "The item in the house caught the eye of the fellow.",
    "Morning after morning, the person gave his hours to the house.",
    "The human watched the daylight fade after a long period."
]

querys_media = [
    "He went to visit his old friend in the country.",
    "A true friend will always be by your side.",
    "She wrote a long letter to her best friend.",
    "Meeting a loyal friend after many years apart.",
    "They remained good friends for their entire lives.",
    "My dear friend sent a short letter yesterday.",
    "Finding a new friend can change your life.",
    "The two friends walked together through the forest.",
    "A kind friend is a treasure to keep.",
    "She smiled when she saw her childhood friend.",
    "Trusting a friend is easy when they are honest.",
    "His friend helped him carry the heavy boxes.",
    "We invited a close friend over for dinner.",
    "Every person needs a friend to talk to.",
    "The letter from my friend brought good news."
]

querys_nula = [
    "Sauron rules the dark land of Mordor with his ring.",
    "Oil rigs and modern tankers located in the Persian Gulf.",
    "People dancing the lambada at a modern discotheque.",
    "Cooking delicious spicy creole sausages on a barbecue grill.",
    "Playing multiplayer video games on a wifi router connection.",
    "A software developer debugging python code on a laptop.",
    "Astronauts repairing solar panels on the international space station.",
    "Calling an Uber to go to the international airport terminal.",
    "Installing a high-end graphics card in the motherboard.",
    "Streaming a Netflix documentary on a smartphone display.",
    "A cybersecurity hacker bypassing the firewall of the database server.",
    "Eating avocado toast while listening to a Spotify podcast.",
    "A blockchain cryptocurrency transaction using Bitcoin wallets.",
    "Sending a quick WhatsApp message with a funny emoji.",
    "A Jedi using a lightsaber to defeat Darth Vader in the Death Star."
]

#visualizar_espacio_vectorial_optimizado(collection)

print("\n[*] Calentando el motor HNSW...")
_ = collection.query(query_embeddings=model.encode(["hello world"]).tolist(), n_results=1)

print(f"[*] Iniciando ataque midiendo latencias de busqueda")

tiempos_alta = ejecutar_bateria_pruebas(querys_alta, model, collection, NUM_PRUEBAS, "Alta Frecuencia")
tiempos_sinonimo = ejecutar_bateria_pruebas(querys_synonyms, model, collection, NUM_PRUEBAS, "Sinonimos")
tiempos_media = ejecutar_bateria_pruebas(querys_media, model, collection, NUM_PRUEBAS, "Media Frecuencia")
tiempos_nula = ejecutar_bateria_pruebas(querys_nula, model, collection, NUM_PRUEBAS, "Nula Frecuencia")


print("\n[+] Ataque finalizado. Generando analisis estadistico...")

# 4. Cálculo de medias para la gráfica
m_alta = np.mean(tiempos_alta)
m_sinonimo = np.mean(tiempos_sinonimo)
m_media = np.mean(tiempos_media)
m_nula = np.mean(tiempos_nula)

t_stat, p_value = stats.ttest_ind(tiempos_alta, tiempos_nula)

print("\n======== RESULTADOS =========")
print(f"1. Alta Freq: {m_alta:.4f} ms")
print(f"2. Freq Media: {m_media:.4f} ms")
print(f"3. Freq Nula: {m_nula:.4f} ms")
print(f"4. Freq Sinonimo: {m_sinonimo:.4f} ms")

print(f"Diferencia Alta-Nula: {abs(m_alta - m_nula):.4f} ms")

print("--- ANALISIS DE SIGNIFICANCIA (P-VALUE) ---")
print(f"P-Value: {p_value:.10f}")

# 5. Generación de la Gráfica con Seaborn
plt.figure(figsize=(12, 7))

sns.kdeplot(tiempos_alta, fill=True, color="red", label=f"Alta Frecuencia (Media: {m_alta:.2f} ms)", alpha=0.4)
sns.kdeplot(tiempos_media, fill=True, color="orange", label=f"Media Frecuencia (Media: {m_media:.2f} ms)", alpha=0.4)
sns.kdeplot(tiempos_nula, fill=True, color="green", label=f"Fuera de Dominio (Media: {m_nula:.2f} ms)", alpha=0.4)
sns.kdeplot(tiempos_sinonimo, fill=True, color="blue", label=f"Sinonimos (Media: {m_sinonimo:.2f} ms)", alpha=0.4)

plt.axvline(m_alta, color='darkred', linestyle='dashed', linewidth=2)
plt.axvline(m_media, color='darkorange', linestyle='dashed', linewidth=2)
plt.axvline(m_nula, color='darkgreen', linestyle='dashed', linewidth=2)
plt.axvline(m_sinonimo, color='darkblue', linestyle='dashed', linewidth=2)

plt.title('Prueba basada en Densidad Semántica', fontsize=14)
plt.xlabel('Tiempo de Búsqueda (Milisegundos)', fontsize=12)
plt.ylabel('Densidad de Probabilidad', fontsize=12)
plt.legend(loc="upper right")
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()

ruta_grafica = 'grafica_latencia_semantica_local.png'
plt.savefig(ruta_grafica, dpi=300)
print(f"\n[+] Gráfica guardada exitosamente como '{ruta_grafica}'")