import os
import time
import torch
import chromadb
from datasets import load_dataset
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

BATCH_SIZE = 5000
ENCODE_BATCH_SIZE = 512

if torch.cuda.is_available():
    nombre_gpu = torch.cuda.get_device_name(0)
    print(f"[+] GPU Detectada, usando: {nombre_gpu}")
    dispositivo = "cuda"
else:
    print("[-] No se detecta GPU. Usando CPU.")
    dispositivo = "cpu"

ruta_bd = "./workspace/pg19"
archivo_checkpoint = "./workspace/checkpoint.txt"

os.makedirs("./workspace", exist_ok=True)

client = chromadb.PersistentClient(path=ruta_bd)


collection = client.get_or_create_collection(
    name="gutenberg_completo")

print(f"[+] Base de datos conectada en {ruta_bd}.")
print(f"[*] Documentos actuales en la BD: {collection.count()}")

print("[*] Cargando modelo de embeddings en memoria VRAM")
model = SentenceTransformer("all-MiniLM-L6-v2", device=dispositivo)

ultimo_libro_procesado = -1
if os.path.exists(archivo_checkpoint):
    with open(archivo_checkpoint, "r") as f:
        contenido = f.read().strip()
        if contenido.isdigit():
            ultimo_libro_procesado = int(contenido)
            print(f"[+] Checkpoint encontrado. Retomando a partir del libro: {ultimo_libro_procesado + 1}")
else:
    print("Path de checkpoint no encontrado")

print("\n[*] Conectando con HuggingFace (Dataset PG19)...")

dataset = load_dataset("emozilla/pg19", split="train", streaming=True)

chunks_acumulados = []
ids_acumulados = []

contador_global_ids = collection.count()

inicio_total = time.perf_counter()


try:
    for indice_libro, libro in enumerate(dataset):

        if indice_libro <= ultimo_libro_procesado:
            continue
            
        texto_completo = libro['text']
        
        for i in range(0, len(texto_completo), 1000):
            trozo = texto_completo[i : i + 1000]
            
            if len(trozo.strip()) > 50:
                chunks_acumulados.append(trozo)
                ids_acumulados.append(f"doc_{contador_global_ids:09d}")
                contador_global_ids += 1
                
                if len(chunks_acumulados) >= BATCH_SIZE:
                    inicio_batch = time.perf_counter()

                    vectores = model.encode(
                        chunks_acumulados, 
                        batch_size=ENCODE_BATCH_SIZE, 
                        show_progress_bar=False
                    ).tolist()
                    tiempo_gpu = time.perf_counter() - inicio_batch
                    
                    inicio_db = time.perf_counter()
                    collection.add(
                        documents=chunks_acumulados,
                        embeddings=vectores,
                        ids=ids_acumulados
                    )
                    tiempo_db = time.perf_counter() - inicio_db
                    
                    fin_batch = time.perf_counter()
                    print(f"    -> [Libro {indice_libro}] Insertados {BATCH_SIZE} vectores | GPU: {tiempo_gpu:.2f}s | BD: {tiempo_db:.2f}s | Tiempo batch: {fin_batch - inicio_batch:.2f}s | Total BD: {contador_global_ids}")
                    
                    chunks_acumulados = []
                    ids_acumulados = []

        with open(archivo_checkpoint, "w") as f:
            f.write(str(indice_libro))


    if chunks_acumulados:
        vectores_finales = model.encode(chunks_acumulados, batch_size=ENCODE_BATCH_SIZE, show_progress_bar=False).tolist()
        collection.add(documents=chunks_acumulados, embeddings=vectores_finales, ids=ids_acumulados)
        
    fin_total = time.perf_counter()
    print(f"\n[+] INGESTA COMPLETADA EXITOSAMENTE en {(fin_total - inicio_total)/60:.2f} minutos")
    print(f"[+] Total de vectores en disco: {collection.count()}")

except KeyboardInterrupt:
    print("\n[-] Proceso pausado manualmente por el usuario (Ctrl+C).")
    print(f"[*] El progreso está a salvo. Vuelve a ejecutar el script para continuar.")
except Exception as e:
    print(f"\n[!] ERROR CRÍTICO: {e}")
    print("[*] No te preocupes, el checkpoint salvaguarda el trabajo anterior.")