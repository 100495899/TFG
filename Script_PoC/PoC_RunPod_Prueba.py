import chromadb
import time
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from sentence_transformers import SentenceTransformer
import random

NUM_PRUEBAS = 300

print("[*] Conectando a la base de datos en /workspace/pg19")
client = chromadb.PersistentClient(path="./workspace/pg19")

collection = client.get_collection(name="gutenberg_completo") 

print(f"[+] Coleccion cargada. Total de vectores en la BD: {collection.count()}")


print("[*] Cargando modelo de embeddings (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

'''total_vectores = collection.count()
indices_aleatorios = random.sample(range(total_vectores), 150)

ids_a_buscar = [f"doc_{i:07d}" for i in indices_aleatorios]

resultados_azar = collection.get(ids=ids_a_buscar)
querys_acierto = resultados_azar['documents']'''

querys_acierto = [
    "En un lugar de la Mancha, de cuyo nombre no quiero acordarme.",
    "Con diez cañones por banda, viento en popa, a toda vela.",
    "Pues el delito mayor del hombre es haber nacido.",
    "Volverán las oscuras golondrinas en tu balcón sus nidos a colgar.",
    "La heroica ciudad dormía la siesta. El viento sur, caliente y perezoso.",
    "Yo, señor, soy de Segovia. Mi padre se llamó Clemente Pablo.",
    "Caminante, no hay camino, se hace camino al andar.",
    "¿Qué es poesía? Dices mientras clavas en mi pupila tu pupila azul.",
    "Es hielo abrasador, es fuego helado, es herida que duele y no se siente.",
    "Señor, yo soy un hombre, un hombre de carne y hueso.",
    "Érase un hombre a una nariz pegado, érase una nariz superlativa.",
    "Coged de vuestra alegre primavera el dulce fruto antes que el tiempo airado.",
    "Cuentan de un sabio que un día tan pobre y mísero estaba.",
    "El ciego me dio una gran calabazada contra el toro de piedra.",
    "Las ilusiones perdidas son hojas desprendidas del árbol del corazón.",
    "Aquella noche el mar estaba embravecido y las olas golpeaban las rocas.",
    "El caballero andante sin amores es árbol sin hojas y sin fruto.",
    "¿Qué es la vida? Un frenesí. ¿Qué es la vida? Una ilusión.",
    "Salí de mi casa con la firme intención de no volver jamás.",
    "Los suspiros son aire y van al aire. Las lágrimas son agua y van al mar.",
    "Al que a buen árbol se arrima, buena sombra le cobija.",
    "La avaricia rompe el saco, como suele decirse habitualmente.",
    "Vuestra merced perdone mi atrevimiento, pero la necesidad me obliga.",
    "Todo pasa y todo queda, pero lo nuestro es pasar.",
    "El amor es un misterio que no puede ser explicado por la fría razón.",
    "La fortuna es un cristal que brilla, pero que también se quiebra fácilmente.",
    "Un hidalgo de los de lanza en astillero, adarga antigua, rocín flaco.",
    "En las noches de invierno, al calor de la lumbre, se contaban historias antiguas.",
    "La doncella lloraba amargamente su desdicha en el balcón del oscuro palacio.",
    "Los soldados marchaban al frente con el corazón encogido por el miedo.",
    "Por la calle mayor bajaba una procesión solemne y silenciosa.",
    "La vieja preparaba sus pócimas y hechizos en la oscuridad de su aposento.",
    "Sancho, amigo, la libertad es uno de los más preciados dones.",
    "El sol caía a plomo sobre las llanuras polvorientas de Castilla.",
    "Las campanas de la catedral repicaban anunciando la gran festividad.",
    "En el fondo de su alma, sabía que su destino estaba escrito en las estrellas.",
    "Levantó la espada con valentía dispuesto a defender el honor de su linaje.",
    "Las oscuras calles de Madrid albergaban conspiraciones y duelos a muerte.",
    "Una lágrima resbaló por su mejilla al leer la carta de su amado.",
    "La taberna estaba llena de truhanes, soldados y mendigos buscando refugio."
]

querys_fallo = [
    "El smartphone tiene conectividad 5G y pantalla OLED.",
    "Criptomonedas y tecnología blockchain en el metaverso.",
    "Programación en Python con inteligencia artificial y machine learning.",
    "El coche eléctrico de Tesla con piloto automático espacial.",
    "Un streamer de Twitch jugando a videojuegos de realidad virtual.",
    "Los astronautas llegaron a Marte usando cohetes reutilizables.",
    "Aplicación móvil para pedir comida a domicilio por internet.",
    "Algoritmos de cifrado cuántico para ciberseguridad avanzada.",
    "El uso de redes sociales como TikTok e Instagram por influencers.",
    "Impresión 3D de órganos humanos para trasplantes biónicos.",
    "Nanotecnología aplicada a procesadores de 3 nanómetros.",
    "Gafas de realidad aumentada para el teletrabajo en Zoom.",
    "Baterías de litio de estado sólido para patinetes eléctricos.",
    "El algoritmo de recomendación de Netflix y Spotify.",
    "Drones autónomos entregando paquetes de Amazon Prime.",
    "Edición genética con CRISPR para crear dinosaurios.",
    "El protocolo TCP/IP para redes WiFi de alta velocidad.",
    "Smartwatches que miden el oxígeno en sangre por Bluetooth.",
    "Un hacker vulnerando un servidor en la nube con ransomware.",
    "Inteligencia artificial generativa creando imágenes fotorrealistas.",
    "El router wifi de mi casa no tiene buena cobertura.",
    "Auriculares con cancelación de ruido activa.",
    "Un monitor ultra panorámico de 144hz para gaming.",
    "Conectando un disco duro externo por puerto USB-C.",
    "La tarjeta gráfica RTX 4090 tiene mucha memoria VRAM.",
    "Desarrollo de aplicaciones web usando React y Node.",
    "Un sistema operativo basado en el kernel de Linux.",
    "Comprando billetes de avión baratos en un portal web.",
    "El asistente virtual de Google responde a comandos de voz.",
    "Escuchando un podcast de tecnología en Spotify.",
    "El coche híbrido consume menos gasolina en ciudad.",
    "Una tablet con lápiz táctil para diseño gráfico.",
    "Subiendo archivos a la nube de Google Drive.",
    "Una videollamada de trabajo a través de Microsoft Teams.",
    "El reloj inteligente cuenta mis pasos diarios.",
    "Un teclado mecánico con luces RGB personalizables.",
    "La pantalla táctil del cajero automático está rota.",
    "Un cargador inalámbrico de carga rápida para el móvil.",
    "La base de datos en SQL está alojada en un servidor.",
    "Un panel solar portátil para cargar dispositivos electrónicos."
]


tiempos_acierto = []
tiempos_fallo = []


print(f"[*] Iniciando ataque midiendo latencias de busqueda (40 Aciertos vs 40 Fallos)...")

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