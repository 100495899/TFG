import chromadb
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sentence_transformers import SentenceTransformer
import json
import gc
from scipy import stats
import pandas as pd
from typing import Dict, List, Tuple
import os
import random
import torch


# LangChain y Transformers (HuggingFace)
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import PromptTemplate

# Configuración del experimento
K_VALUES = [5, 20, 50, 100]
FRECUENCIAS = ['alta_frecuencia', 'media_frecuencia', 'baja_frecuencia']
LONGITUDES = ['corta', 'media', 'larga']
DATABASE_PATH = "./workspace/pg19"
COLLECTION_NAME = "gutenberg_completo"
QUERIES_FILE = "Querys.json"
DIRECTORIO_SALIDA = "./resultados"
NUM_ITERACIONES = 2
N_FREQ = {'alta_frecuencia': 'High', 'media_frecuencia': 'Medium', 'baja_frecuencia': 'Low'}
N_LONG = {'corta': 'Short', 'media': 'Medium', 'larga': 'Long'}

# GRÁFICAS
def generar_graficas_densidad(resultados_completos: Dict):
    """Generamos gráficas de densidad KDE para cada valor de k"""

    for k, results in resultados_completos.items():
        fig, axes = plt.subplots(3, 3, figsize=(18, 15))
        fig.suptitle(f'Latency Distribution - k={k}', fontsize=16, fontweight='bold')

        for i, frecuencia in enumerate(FRECUENCIAS):
            for j, longitud in enumerate(LONGITUDES):
                ax = axes[i, j]
                data = results[frecuencia][longitud]['tiempos_limpios']

                # KDE
                sns.kdeplot(data=data, ax=ax, fill=True, color='blue', alpha=0.6)

                # Añadimos línea vertical para la media
                media = results[frecuencia][longitud]['media']
                ax.axvline(media, color='red', linestyle='--', linewidth=2,
                          label=f'Mean: {media:.2f}ms')

                # Configuramos el subplot
                ax.set_title(f'{N_FREQ[frecuencia]} Frequency - {N_LONG[longitud]}')
                ax.set_xlabel('Latency (ms)')
                ax.set_ylabel('Density')
                ax.legend()
                ax.grid(True, alpha=0.3)

        plt.tight_layout()
        filename = os.path.join(DIRECTORIO_SALIDA, f'densidad_latencias_k{k}.png')
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[+] Grafica guardada: {filename}")
        plt.close()

def generar_graficas_densidad_superpuesta(resultados_completos: Dict):
    """
    Genera gráficas de densidad KDE superpuestas.
    Crea un panel por cada Longitud (Corta, Media, Larga) y superpone 
    las 3 Frecuencias dentro para comparar fácilmente su distribución.
    """
    for k in K_VALUES:
        # Creamos una figura con 3 subplots en horizontal (1 fila, 3 columnas)
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f'Overlaid Latency Density Comparison - Top-K = {k}', fontsize=16, fontweight='bold')

        # Iteramos primero por la longitud para que cada cuadro sea una longitud
        for j, longitud in enumerate(LONGITUDES):
            ax = axes[j]
            
            # Ahora superponemos las 3 frecuencias en el MISMO cuadro
            for frecuencia in FRECUENCIAS:
                # Extraemos los datos
                datos = resultados_completos[k][frecuencia][longitud]['tiempos_limpios']
                
                # Limpiamos el nombre para que la leyenda quede bonita (ej: "Alta")
                nombre_leyenda = N_FREQ[frecuencia]
                
                # Dibujamos la curva. alpha=0.4 le da la transparencia para que se vean todas
                sns.kdeplot(data=datos, ax=ax, fill=True, alpha=0.4, label=nombre_leyenda)

            # Configuración estética de cada cuadro
            ax.set_title(f'Length of Query: {N_LONG[longitud]}', fontsize=14)
            ax.set_xlabel('Latency (ms)')
            ax.set_ylabel('Density')
            
            # Ponemos la leyenda para saber qué color es cada frecuencia
            ax.legend(title="Frequency", loc='upper right')
            ax.grid(True, alpha=0.3)

        # Ajustamos espacios y guardamos
        plt.tight_layout()
        ruta_archivo = os.path.join(DIRECTORIO_SALIDA, f'densidad_superpuesta_k{k}.png')
        plt.savefig(ruta_archivo, dpi=300, bbox_inches='tight')
        print(f"[+] Gráfica de densidad superpuesta guardada: {ruta_archivo}")
        
        # Cerramos la figura
        plt.close()

def generar_diagramas_caja(resultados_completos: Dict):
    """
    Generamos Box and Whisker plots 
    """
    for k in K_VALUES:
        datos_caja = []
        etiquetas = []
        
        for frecuencia in FRECUENCIAS:
            for longitud in LONGITUDES:
                # Extraemos la lista completa de tiempos para ver su distribución
                tiempos = resultados_completos[k][frecuencia][longitud]['tiempos_limpios']
                datos_caja.append(tiempos)
                
                # Creamos una etiqueta corta para el eje X
                etiquetas.append(f"{N_FREQ[frecuencia][:4]}\n{N_LONG[longitud][:4]}")
        
        # Creamos la figura
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Generamos el Boxplot con Seaborn
        sns.boxplot(data=datos_caja, ax=ax, palette="Set3", showfliers=True)
        
        # Configuramos el gráfico
        ax.set_xticklabels(etiquetas)
        ax.set_title(f'Latency Dispersion (Box & Whisker) - Top-K = {k}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Configuration (Frequency - Length)', fontsize=12)
        ax.set_ylabel('Latency (ms)', fontsize=12)
        ax.grid(True, axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        # Guardamos la imagen
        ruta_archivo = os.path.join(DIRECTORIO_SALIDA, f'box_whisker_plots_{k}.png')
        plt.savefig(ruta_archivo, dpi=300, bbox_inches='tight')
        print(f"[+] Diagrama de cajas guardado: {ruta_archivo}")
        plt.close()

def generar_grafica_comparativa(resultados_completos: Dict):
    """Generamos una gráfica comparativa de todas las combinaciones"""

    # Preparamos los datos para la gráfica
    datos_grafica = []

    for k in K_VALUES:
        for frecuencia in FRECUENCIAS:
            for longitud in LONGITUDES:
                media = resultados_completos[k][frecuencia][longitud]['media']
                datos_grafica.append({
                    'k': k,
                    'Frequency': N_FREQ[frecuencia],
                    'Length': N_LONG[longitud],
                    'Latency (ms)': media,
                    'Configuration': f"{N_FREQ[frecuencia][:3]}-{N_LONG[longitud][:3]}"
                })

    df = pd.DataFrame(datos_grafica)

    # Creamos gráfica de barras agrupadas
    fig, ax = plt.subplots(figsize=(16, 8))

    # Configuramos posiciones de las barras
    x = np.arange(len(FRECUENCIAS) * len(LONGITUDES))
    ancho_barra = 0.8 / len(K_VALUES)
    
    for i, k in enumerate(K_VALUES):
        k_data = df[df['k'] == k]
        medias = k_data['Latency (ms)'].values
        offset = (i - 1) * ancho_barra
        bars = ax.bar(x + offset, medias, ancho_barra, label=f'k={k}')

        # Añadimos valores encima de las barras
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}', ha='center', va='bottom', fontsize=8)

    # Configuramos el gráfico
    ax.set_xlabel('Configuration (Frequency - Length)', fontsize=12)
    ax.set_ylabel('Mean Latency (ms)', fontsize=12)
    ax.set_title('Latency Comparison: Impact of k, Frequency, and Length', fontsize=14, fontweight='bold')

    # Etiquetamos el eje X
    labels = [f"{N_FREQ[f][:4]}\n{N_LONG[l][:4]}"
              for f in FRECUENCIAS for l in LONGITUDES]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)

    ax.legend(title='Search Depth (k)', fontsize=10)
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    filename = os.path.join(DIRECTORIO_SALIDA, 'comparativa_todas_configuraciones.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[+] Grafica comparativa guardada: {filename}")
    plt.close()

def generar_mapa_calor(resultados_completos: Dict):
    """Generamos un mapa de calor para visualizar el impacto de las variables"""

    for k in K_VALUES:
        # Creamos una matriz para el heatmap
        matriz = np.zeros((3, 3))

        for i, frecuencia in enumerate(FRECUENCIAS):
            for j, longitud in enumerate(LONGITUDES):
                matriz[i, j] = resultados_completos[k][frecuencia][longitud]['media']

        # Creamos el heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(matriz, annot=True, fmt='.2f', cmap='YlOrRd',
                   xticklabels=[N_LONG[l] for l in LONGITUDES],
                   yticklabels=[N_FREQ[f] for f in FRECUENCIAS],
                   ax=ax, cbar_kws={'label': 'Latency (ms)'})

        ax.set_title(f'Latency Heatmap - k={k}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Query Length', fontsize=12)
        ax.set_ylabel('Semantic Frequency', fontsize=12)

        plt.tight_layout()
        filename = os.path.join(DIRECTORIO_SALIDA, f'heatmap_k{k}.png')
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[+] Heatmap guardado: {filename}")
        plt.close()


# GUARDAR RESULTADOS
def guardar_resultados_csv(resultados_completos: Dict):
    """Guardamos los resultados en un archivo CSV"""

    filas = []
    for k in K_VALUES:
        for frecuencia in FRECUENCIAS:
            for longitud in LONGITUDES:
                result = resultados_completos[k][frecuencia][longitud]
                filas.append({
                    'k': k,
                    'Frequency': N_FREQ[frecuencia],
                    'Length': N_LONG[longitud],
                    'Mean_Latency (ms)': result['media'],
                    'Median_Latency (ms)': result['mediana'],
                    'Std_Latency (ms)': result['std'],
                    'Filtered_Outliers': result['outliers'],
                    'Sample_Size': len(result['tiempos_limpios'])
                })

    df = pd.DataFrame(filas)
    filename = os.path.join(DIRECTORIO_SALIDA, 'resultados_prueba_latencias.csv')
    df.to_csv(filename, index=False)
    print(f"[+] Resultados guardados en CSV: {filename}")

    # Mostrar resumen estadístico
    print("\n======== RESUMEN DE RESULTADOS ========")
    print(df.to_string(index=False))


# FUNCIONES PRINCIPALES
def configurar_llm():
    """Descargamos y cargamos el modelo de IA en la VRAM de la gráfica"""
    print("\n[*] Cargando el LLM (HuggingFaceTB/SmolLM2-135M-Instruct) en la tarjeta gráfica")
    model_id = "HuggingFaceTB/SmolLM2-135M-Instruct"
    
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    # Cargamos en bfloat16 para ahorra VRAM
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="auto", device_map="auto")
    
    pipe = pipeline(
        "text-generation", 
        model=model, 
        tokenizer=tokenizer, 
        max_new_tokens=100,
        min_new_tokens=1,
        min_length=None,
        max_length=None,
        temperature=0.1,
        return_full_text=False,
        truncation=True,
        pad_token_id=tokenizer.eos_token_id
    )
    
    # Lo convertimos al formato que entiende LangChain
    llm = HuggingFacePipeline(pipeline=pipe)
    print("[+] LLM cargado y listo.")
    return llm

def prueba_latencia_rag(rag_chain, queries: Dict, k: int, num_iteraciones: int):
    """Ejecutamos las queries contra toda la cadena RAG"""
    print(f"\n[*] Preparando las queries para k={k}")
    todas_las_queries = []

    for frecuencia in FRECUENCIAS:
        for longitud in LONGITUDES:
            lista_textos = queries[frecuencia][longitud]
            for texto in lista_textos:
                todas_las_queries.append((texto, frecuencia, longitud))

    tiempos_brutos = {f: {l: [] for l in LONGITUDES} for f in FRECUENCIAS}

    gc.disable()
    try:
        for iteracion in range(num_iteraciones):
            print(f"    -> Iteración {iteracion + 1}/{num_iteraciones}")
            random.shuffle(todas_las_queries)
            
            for i, (texto_query, freq, long) in enumerate(todas_las_queries):

                inicio = time.perf_counter()
                
                # Le pasamos la query en texto plano a LangChain
                respuesta = rag_chain.invoke({"input": texto_query})
                
                fin = time.perf_counter()
                
                latencia = (fin - inicio) * 1000
                tiempos_brutos[freq][long].append(latencia)
                
                # print(f"\n[Ejemplo {freq}-{long}] Query: {texto_query}")
                print(f"Respuesta de la IA: {respuesta['answer']}\n")
                
                if (i + 1) % 50 == 0:
                    print(f"        Progreso: {i+1}/{len(todas_las_queries)} queries")


        print("    -> Procesando y filtrando resultados estadísticos...")
        results = {}
        for freq in FRECUENCIAS:
            results[freq] = {}
            for long in LONGITUDES:
                tiempos = tiempos_brutos[freq][long]
                
                # Filtramos outliers (el 1% más lento)
                limite = np.percentile(tiempos, 99)
                tiempos_limpios = [t for t in tiempos if t <= limite]
                
                results[freq][long] = {
                    'tiempos_sucios': tiempos,
                    'tiempos_limpios': tiempos_limpios,
                    'media': np.mean(tiempos_limpios),
                    'mediana': np.median(tiempos_limpios),
                    'std': np.std(tiempos_limpios),
                    'outliers': len(tiempos) - len(tiempos_limpios)
                }
        

    except Exception as e:
        print(f"\nError durante la prueba RAG: {e}")
        return None
    finally:
        gc.enable()
        gc.collect()
        
    return results

def main():
    print("=" * 40)
    print("INICIANDO ENTORNO RAG")
    print("=" * 40)

    # 1. Cargamos las Queries
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        queries = json.load(f)

    # 2. Cargamos el LLM Local
    llm = configurar_llm()

    # 3. Conectamos ChromaDB a través de LangChain
    print("\n[*] Conectando a ChromaDB")
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Creamos el wrapper de LangChain
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=DATABASE_PATH,
        embedding_function=embeddings
    )
    
    resultados_completos = {}
    
    for k in K_VALUES:
        print(f"\n[*] Configurando el Retriever para k={k}")
        retriever = vectorstore.as_retriever(search_kwargs={"k": k})

        # 4. Creamos el Prompt
        template = """Eres un asistente analítico. Usa el siguiente contexto para responder a la pregunta.
                    Regla estricta: Si la pregunta trata sobre un término de baja frecuencia, o si la información del contexto es escasa o poco relevante, tu respuesta debe ser ÚNICA y EXCLUSIVAMENTE la palabra "Baja". No añadas puntos, ni saludos, ni explicaciones adicionales.
                    Si hay abundante información, genera una respuesta detallada y extensa.
                    
                    Contexto:
                    {context}
                    
                    Pregunta: {input}
                    Respuesta:"""
        prompt = PromptTemplate.from_template(template)

        # 5. Ensamblamos la Cadena RAG Completa
        document_chain = create_stuff_documents_chain(llm, prompt)
        rag_chain = create_retrieval_chain(retriever, document_chain)

        print("[*] Calentando el motor RAG completo")
        _ = rag_chain.invoke({"input": "query de calentamiento para cargar en VRAM"})
        print("[+] Motor calentado")

        print("[*] Limpiando cache y memoria")
        gc.collect()
        torch.cuda.empty_cache()
        time.sleep(2)

        # 6. Probamos la latencia de la cadena RAG con las queries
        results = prueba_latencia_rag(rag_chain, queries, k, NUM_ITERACIONES)
        resultados_completos[k] = results
    
    # 7. Generamos visualizaciones
    print(f"\n{'='*30}")
    print("GENERANDO VISUALIZACIONES")
    print(f"{'='*30}")

    generar_graficas_densidad(resultados_completos)
    generar_graficas_densidad_superpuesta(resultados_completos)
    generar_diagramas_caja(resultados_completos)
    generar_grafica_comparativa(resultados_completos)
    generar_mapa_calor(resultados_completos)

    # 8. Guardamos los resultados
    guardar_resultados_csv(resultados_completos)

    print(f"\n{'='*30}")
    print("PRUEBA RAG COMPLETADA")
    print(f"{'='*30}")

if __name__ == "__main__":
    main()