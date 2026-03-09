import random
import chromadb
import matplotlib.pyplot as plt
from collections import Counter
from transformers import AutoTokenizer

def generar_histograma_frecuencias():
    print("[*] Cargando el tokenizador all-MiniLM-L6-v2...")
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

    ruta_bd = "./workspace/pg19"
    client = chromadb.PersistentClient(path=ruta_bd)
    collection = client.get_collection(name="gutenberg_completo")
    
    total_docs = collection.count()
    print(f"Total docs: {total_docs}")
    if total_docs == 0:
        print("[!] La colección está vacía.")
        return

    tamano_muestra = min(100000, total_docs)
    print(f"[*] Extrayendo muestra de {tamano_muestra} documentos para el análisis...")
    indices_unicos = random.sample(range(total_docs), tamano_muestra)
    ids_aleatorios = [f"doc_{i:09d}" for i in indices_unicos]
    
    print("[*] Descargando textos de ChromaDB en lotes (para evitar el límite de SQLite)...")
    todos_los_textos = []
    tamano_lote = 5000
    
    for i in range(0, tamano_muestra, tamano_lote):
        lote_ids = ids_aleatorios[i : i + tamano_lote]
        datos = collection.get(ids=lote_ids, include=['documents'])
        todos_los_textos.extend(datos['documents'])
        print(f"    -> Lote descargado: {min(i + tamano_lote, tamano_muestra)} / {tamano_muestra} textos...")
    # -----------------------------------

    # 4. Contar los tokens
    print("[*] Tokenizando textos y contando frecuencias")
    contador_tokens = Counter()
    
    for texto in todos_los_textos:
        # Extraemos los tokens (ignorando los tokens especiales como [CLS] o [SEP])
        tokens = tokenizer.tokenize(texto)
        contador_tokens.update(tokens)

    # 5. Preparar los datos para la gráfica (Los 50 más comunes)
    top_n = 50
    tokens_mas_comunes = contador_tokens.most_common(top_n)
    
    palabras = [par[0] for par in tokens_mas_comunes]
    frecuencias = [par[1] for par in tokens_mas_comunes]

    # 6. Dibujar el Histograma
    print(f"[*] Generando histograma de los {top_n} tokens más frecuentes...")
    plt.figure(figsize=(15, 6))
    plt.bar(palabras, frecuencias, color='teal', alpha=0.7)
    
    plt.title(f"Distribución de Frecuencia de Tokens (Muestra de {tamano_muestra} docs)")
    plt.xlabel("Tokens")
    plt.ylabel("Frecuencia Absoluta")
    plt.xticks(rotation=45, ha='right') # Inclinamos las palabras para que se lean bien
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Guardar la imagen
    ruta_imagen = "prueba_histograma_frecuencia_runpod.png"
    plt.savefig(ruta_imagen, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"[+] ¡Éxito! El histograma se ha guardado en: {ruta_imagen}")
    
    # Imprimir un pequeño resumen por consola para que lo veas rápido
    print("\n--- Top 10 tokens más frecuentes ---")
    for i in range(10):
        print(f"{i+1}. '{palabras[i]}': {frecuencias[i]} veces")

# Ejecutar la función
generar_histograma_frecuencias()



