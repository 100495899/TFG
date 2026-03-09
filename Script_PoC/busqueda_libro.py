import chromadb
import random

ruta_bd = "./workspace/pg19"
client = chromadb.PersistentClient(path=ruta_bd)
collection = client.get_collection(name="gutenberg_completo")

total_docs = collection.count()
print(f"[*] Total de documentos: {total_docs}")

# Damos un "salto" aleatorio hacia el medio de la base de datos
# (Puedes cambiar este número a mano si quieres explorar otras zonas)
salto = random.randint(10000, total_docs - 500)

print(f"\n[*] Explorando la zona del ID: doc_{salto:09d}")
ids_exploracion = [f"doc_{i:09d}" for i in range(salto, salto + 5)]

resultados = collection.get(ids=ids_exploracion)

for i, texto in enumerate(resultados['documents']):
    print(f"\n--- TROZO {i+1} (ID: {ids_exploracion[i]}) ---")
    # Imprimimos solo los primeros 300 caracteres para no saturar la pantalla
    print(texto[:300] + "...")