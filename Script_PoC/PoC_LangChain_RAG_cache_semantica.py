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
from typing import Dict, List, Tuple, Optional
import os
import random
import torch
import redis
from datetime import datetime
import hashlib

# Importamos las librerías necesarias de LangChain para RAG y HuggingFace para el modelo
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import PromptTemplate
from langchain_core.globals import set_llm_cache
from langchain_community.cache import RedisSemanticCache
from langchain_community.cache import InMemoryCache

# Parámetros principales del experimento para evaluar el comportamiento del sistema
K_VALUES = [5, 20, 50, 100]
FRECUENCIAS = ['alta_frecuencia', 'media_frecuencia', 'baja_frecuencia']
LONGITUDES = ['corta', 'media', 'larga']
DATABASE_PATH = "./workspace/pg19"
COLLECTION_NAME = "gutenberg_completo"
QUERIES_FILE = "Querys.json"
DIRECTORIO_SALIDA = "./resultados-cache"
NUM_ITERACIONES = 2
N_FREQ = {'alta_frecuencia': 'High', 'media_frecuencia': 'Medium', 'baja_frecuencia': 'Low'}
N_LONG = {'corta': 'Short', 'media': 'Medium', 'larga': 'Long'}

# Conexión con el servidor Redis local para la caché semántica
REDIS_URL = "redis://localhost:6379"

# Configuramos primero las variantes con Redis para detectar errores de conexión temprano
# Esto evita perder tiempo si Redis no está disponible
CACHE_CONFIGS = {
    # Primero probar Redis para fallar rápido si hay problemas
    'cache_sem_095': {'tipo': 'redis', 'umbral': 0.95},
    'cache_sem_090': {'tipo': 'redis', 'umbral': 0.90},
    'cache_sem_085': {'tipo': 'redis', 'umbral': 0.85},
    'cache_sem_080': {'tipo': 'redis', 'umbral': 0.80},
    # Después las configuraciones que siempre funcionan
    'sin_cache': {'tipo': 'none', 'umbral': None},
    'cache_exacta': {'tipo': 'memory', 'umbral': None}
}


class CacheMonitor:
    """Clase que monitoriza y registra las estadísticas del sistema de caché
    Permite analizar el rendimiento distinguiendo entre hits y misses"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Limpia los contadores para comenzar una nueva medición"""
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'hit_latencies': [],
            'miss_latencies': [],
            'hits_por_frecuencia': {f: 0 for f in FRECUENCIAS},
            'misses_por_frecuencia': {f: 0 for f in FRECUENCIAS},
            'hits_por_longitud': {l: 0 for l in LONGITUDES},
            'misses_por_longitud': {l: 0 for l in LONGITUDES}
        }

    def registrar_consulta(self, latencia: float, es_hit: bool, frecuencia: str, longitud: str):
        """Guarda los datos de cada consulta realizada para análisis posterior"""
        self.stats['total_queries'] += 1

        if es_hit:
            self.stats['cache_hits'] += 1
            self.stats['hit_latencies'].append(latencia)
            self.stats['hits_por_frecuencia'][frecuencia] += 1
            self.stats['hits_por_longitud'][longitud] += 1
        else:
            self.stats['cache_misses'] += 1
            self.stats['miss_latencies'].append(latencia)
            self.stats['misses_por_frecuencia'][frecuencia] += 1
            self.stats['misses_por_longitud'][longitud] += 1

    def obtener_resumen(self) -> Dict:
        """Calcula y devuelve las métricas agregadas del experimento"""
        if self.stats['total_queries'] == 0:
            return {'error': 'No hay consultas registradas'}

        hit_rate = self.stats['cache_hits'] / self.stats['total_queries']

        resumen = {
            'total_queries': self.stats['total_queries'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'hit_rate': hit_rate,
            'miss_rate': 1 - hit_rate,
            'hit_latencies': self.stats['hit_latencies'],
            'miss_latencies': self.stats['miss_latencies'],
            'latencia_media_hits': np.mean(self.stats['hit_latencies']) if self.stats['hit_latencies'] else 0,
            'latencia_media_misses': np.mean(self.stats['miss_latencies']) if self.stats['miss_latencies'] else 0,
            'hit_rates_por_frecuencia': {},
            'hit_rates_por_longitud': {}
        }

        # Calculamos el porcentaje de aciertos agrupado por frecuencia y longitud
        for freq in FRECUENCIAS:
            total = self.stats['hits_por_frecuencia'][freq] + self.stats['misses_por_frecuencia'][freq]
            if total > 0:
                resumen['hit_rates_por_frecuencia'][freq] = self.stats['hits_por_frecuencia'][freq] / total

        for long in LONGITUDES:
            total = self.stats['hits_por_longitud'][long] + self.stats['misses_por_longitud'][long]
            if total > 0:
                resumen['hit_rates_por_longitud'][long] = self.stats['hits_por_longitud'][long] / total

        return resumen

def verificar_redis_stack() -> bool:
    """Comprueba que tengamos Redis Stack instalado con el módulo RediSearch
    necesario para implementar búsquedas semánticas eficientes"""
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()

        # Comprobamos qué módulos tiene cargados Redis
        try:
            modules = redis_client.execute_command('MODULE', 'LIST')
            # Buscamos específicamente el módulo de búsqueda
            for module in modules:
                if len(module) > 1 and 'search' in str(module[1]).lower():
                    # Intentamos usar comandos de RediSearch para confirmar que funciona
                    try:
                        info = redis_client.execute_command('FT.INFO', 'test_idx')
                    except:
                        # Creamos un índice temporal para verificar que RediSearch funciona correctamente
                        try:
                            redis_client.execute_command('FT.CREATE', 'test_idx',
                                                       'SCHEMA', 'field', 'TEXT')
                            redis_client.execute_command('FT.DROPINDEX', 'test_idx')
                            return True
                        except redis.ResponseError as e:
                            if "Index already exists" in str(e):
                                return True
                    return True
            print("[!] RediSearch no encontrado en los módulos de Redis")
            return False
        except redis.ResponseError as e:
            print(f"[!] Error verificando módulos: {e}")
            return False
    except redis.ConnectionError as e:
        print(f"[!] Redis no disponible: {e}")
        return False
    except Exception as e:
        print(f"[!] Error verificando Redis Stack: {e}")
        return False

def configurar_cache(config_name: str, embeddings) -> Optional[CacheMonitor]:
    """Establece el sistema de caché apropiado según el experimento actual
    Puede ser sin caché, caché exacta en memoria o caché semántica con Redis"""
    config = CACHE_CONFIGS[config_name]
    monitor = CacheMonitor()

    if config['tipo'] == 'none':
        set_llm_cache(None)
        print(f"[*] Caché desactivada")
    elif config['tipo'] == 'memory':
        set_llm_cache(InMemoryCache())
        print(f"[*] Caché en memoria activada")
    elif config['tipo'] == 'redis':
        try:
            # Primero comprobamos que podemos conectarnos a Redis
            redis_client = redis.from_url(REDIS_URL)
            redis_client.ping()

            # Vaciamos la base de datos para empezar con caché limpia
            redis_client.flushdb()

            # Creamos la caché semántica con el umbral de similitud especificado
            cache = RedisSemanticCache(
                redis_url=REDIS_URL,
                embedding=embeddings,
                score_threshold=config['umbral']
            )
            set_llm_cache(cache)
            print(f"[*] Caché semántica Redis activada (umbral={config['umbral']})")
        except redis.ConnectionError as e:
            print(f"[!] Error de conexión Redis: {e}")
            print("[!] Saltando esta configuración de caché")
            return None
        except ValueError as e:
            if "RediSearch" in str(e):
                print(f"[!] ERROR: Redis Stack con RediSearch no está instalado")
                return None
            else:
                print(f"[!] Error de configuración: {e}")
                return None
        except Exception as e:
            print(f"[!] Error configurando RedisSemanticCache: {e}")
            print(f"[!] Detalle del error: {type(e).__name__}")
            return None

    return monitor

def detectar_cache_hit(latencia_ms: float, cache_type: str = 'none', percentil_threshold: float = 100.0) -> bool:
    """
    Determina si una consulta fue un hit de caché basándose en su latencia.

    Cada tipo de caché tiene diferentes latencias esperadas:
    - Sin caché: siempre es miss por definición
    - Caché en memoria: muy rápida, menos de 100ms indica hit
    - Caché Redis: búsqueda semántica más costosa, threshold de 100ms

    Los umbrales están calibrados para el entorno de ejecución específico
    donde los hits de caché semántica rondan los 80-180ms.
    """
    if cache_type == 'none':
        return False
    
    if cache_type == 'memory':
        return latencia_ms < 100.0
    
    if cache_type == 'redis':
        return latencia_ms < 100.0
    
    return latencia_ms < percentil_threshold

# Funciones para visualizar el impacto del sistema de caché en el rendimiento
def generar_graficas_cache(resultados_cache: Dict):
    """Crea visualizaciones detalladas del comportamiento del sistema de caché
    Incluye comparativas de hit rates y análisis de latencias"""

    # Primera gráfica: comparamos el porcentaje de aciertos entre configuraciones
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # Mostramos el rendimiento general de cada configuración de caché
    ax = axes[0, 0]
    configs = list(resultados_cache.keys())
    hit_rates = [resultados_cache[c]['resumen']['hit_rate'] for c in configs]
    bars = ax.bar(configs, hit_rates, color='skyblue', edgecolor='black')
    ax.set_title('Cache Hit Rate por Configuración', fontweight='bold')
    ax.set_ylabel('Hit Rate')
    ax.set_ylim([0, 1])
    ax.grid(True, axis='y', alpha=0.3)

    # Agregamos los porcentajes exactos encima de cada barra para mayor claridad
    for bar, rate in zip(bars, hit_rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.1%}', ha='center', va='bottom')

    # Segunda gráfica: desglose por frecuencia semántica de las consultas
    ax = axes[0, 1]
    x = np.arange(len(FRECUENCIAS))
    width = 0.15

    for i, config in enumerate(configs):
        if 'hit_rates_por_frecuencia' in resultados_cache[config]['resumen']:
            rates = [resultados_cache[config]['resumen']['hit_rates_por_frecuencia'].get(f, 0)
                    for f in FRECUENCIAS]
            ax.bar(x + i*width, rates, width, label=config)

    ax.set_xlabel('Frecuencia')
    ax.set_ylabel('Hit Rate')
    ax.set_title('Hit Rate por Frecuencia Semántica', fontweight='bold')
    ax.set_xticks(x + width * (len(configs)-1) / 2)
    ax.set_xticklabels([N_FREQ[f] for f in FRECUENCIAS])
    ax.legend(fontsize=8)
    ax.grid(True, axis='y', alpha=0.3)

    # Tercera gráfica: comparamos tiempos de respuesta entre aciertos y fallos
    ax = axes[1, 0]
    data_comparacion = []
    labels_comparacion = []

    for config in configs:
        resumen = resultados_cache[config]['resumen']
        if resumen.get('latencia_media_hits', 0) > 0:
            data_comparacion.append([
                resumen['latencia_media_hits'],
                resumen['latencia_media_misses']
            ])
            labels_comparacion.append(config)

    if data_comparacion:
        positions = np.arange(len(labels_comparacion))
        width = 0.35

        hits_data = [d[0] for d in data_comparacion]
        misses_data = [d[1] for d in data_comparacion]

        ax.bar(positions - width/2, hits_data, width, label='Cache Hits', color='green', alpha=0.7)
        ax.bar(positions + width/2, misses_data, width, label='Cache Misses', color='red', alpha=0.7)

        ax.set_xlabel('Configuración')
        ax.set_ylabel('Latencia Media (ms)')
        ax.set_title('Latencias: Cache Hits vs Misses', fontweight='bold')
        ax.set_xticks(positions)
        ax.set_xticklabels(labels_comparacion, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, axis='y', alpha=0.3)

    # Cuarta gráfica: histogramas de densidad para ver la distribución completa
    ax = axes[1, 1]
    for i, config in enumerate(configs):
        if config != 'sin_cache' and 'latencias' in resultados_cache[config]:
            latencias = resultados_cache[config]['latencias']
            if latencias:
                ax.hist(latencias, bins=30, alpha=0.5, label=config, density=True)

    ax.set_xlabel('Latencia (ms)')
    ax.set_ylabel('Densidad')
    ax.set_title('Distribución de Latencias por Configuración', fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    filename = os.path.join(DIRECTORIO_SALIDA, 'analisis_cache_completo.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[+] Análisis de caché guardado: {filename}")
    plt.close()

def generar_reporte_cache(resultados_cache: Dict, k: int):
    """Crea un informe textual completo con todas las estadísticas del experimento
    Incluye métricas generales, desglose por categorías e impacto en el canal lateral"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DIRECTORIO_SALIDA, f'reporte_cache_k{k}_{timestamp}.txt')

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"REPORTE DE ANÁLISIS DE CACHÉ SEMÁNTICA\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"K = {k}\n")
        f.write("=" * 70 + "\n\n")

        for config_name, data in resultados_cache.items():
            f.write(f"\n{'='*50}\n")
            f.write(f"CONFIGURACIÓN: {config_name}\n")
            f.write(f"{'='*50}\n")

            resumen = data['resumen']

            # Escribimos las estadísticas principales del experimento
            f.write(f"\nMÉTRICAS GENERALES:\n")
            f.write(f"  Total consultas: {resumen['total_queries']}\n")
            f.write(f"  Cache hits: {resumen['cache_hits']}\n")
            f.write(f"  Cache misses: {resumen['cache_misses']}\n")
            f.write(f"  Hit rate global: {resumen['hit_rate']:.2%}\n")
            f.write(f"  Miss rate global: {resumen['miss_rate']:.2%}\n")

            # Analizamos los tiempos de respuesta
            f.write(f"\nLATENCIAS:\n")
            f.write(f"  Media hits: {resumen['latencia_media_hits']:.2f} ms\n")
            f.write(f"  Media misses: {resumen['latencia_media_misses']:.2f} ms\n")
            f.write(f"  Reducción: {(1 - resumen['latencia_media_hits']/resumen['latencia_media_misses'])*100:.1f}%\n")

            # Desglosamos el rendimiento según la frecuencia semántica
            f.write(f"\nHIT RATES POR FRECUENCIA:\n")
            for freq in FRECUENCIAS:
                if freq in resumen['hit_rates_por_frecuencia']:
                    rate = resumen['hit_rates_por_frecuencia'][freq]
                    f.write(f"  {N_FREQ[freq]:8}: {rate:.2%}\n")

            # Desglosamos el rendimiento según el tamaño de las consultas
            f.write(f"\nHIT RATES POR LONGITUD:\n")
            for long in LONGITUDES:
                if long in resumen['hit_rates_por_longitud']:
                    rate = resumen['hit_rates_por_longitud'][long]
                    f.write(f"  {N_LONG[long]:8}: {rate:.2%}\n")

            # Evaluamos cómo la caché afecta a la información filtrada por timing
            if 'impacto_canal_lateral' in data:
                f.write(f"\nIMPACTO EN CANAL LATERAL:\n")
                impacto = data['impacto_canal_lateral']
                f.write(f"  Varianza pre-caché: {impacto.get('var_sin_cache', 0):.2f}\n")
                f.write(f"  Varianza con-caché: {impacto.get('var_con_cache', 0):.2f}\n")
                f.write(f"  Reducción de señal: {impacto.get('reduccion_senal', 0):.1f}%\n")

    print(f"[+] Reporte detallado guardado: {filename}")

def generar_graficas_densidad_superpuesta(resultados_completos: Dict, directorio_salida: str):
    """
    Crea gráficas de densidad que superponen las distribuciones de diferentes frecuencias.
    Permite comparar visualmente cómo varía la latencia según la frecuencia semántica
    manteniendo fija la longitud de la consulta.
    """
    for k in sorted(resultados_completos.keys()):
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f'Overlaid Latency Density Comparison - Top-K = {k}', fontsize=16, fontweight='bold')

        for j, longitud in enumerate(LONGITUDES):
            ax = axes[j]
            hay_datos = False

            for frecuencia in FRECUENCIAS:
                datos = resultados_completos[k][frecuencia][longitud]['tiempos_limpios']
                if datos:
                    hay_datos = True
                    sns.kdeplot(data=datos, ax=ax, fill=True, alpha=0.4, label=N_FREQ[frecuencia])

            ax.set_title(f'Length of Query: {N_LONG[longitud]}', fontsize=14)
            ax.set_xlabel('Latency (ms)')
            ax.set_ylabel('Density')
            if hay_datos:
                ax.legend(title="Frequency", loc='upper right')
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        ruta_archivo = os.path.join(directorio_salida, f'densidad_superpuesta_k{k}.png')
        plt.savefig(ruta_archivo, dpi=300, bbox_inches='tight')
        print(f"[+] Gráfica de densidad superpuesta guardada: {ruta_archivo}")
        plt.close()

def generar_diagramas_caja(resultados_completos: Dict, directorio_salida: str):
    """
    Crea diagramas de caja y bigotes para visualizar la dispersión de las latencias.
    Muestra la mediana, cuartiles y valores atípicos para cada combinación de parámetros,
    facilitando la identificación de patrones y anomalías.
    """
    for k in sorted(resultados_completos.keys()):
        datos_caja = []
        etiquetas = []

        for frecuencia in FRECUENCIAS:
            for longitud in LONGITUDES:
                tiempos = resultados_completos[k][frecuencia][longitud]['tiempos_limpios']
                datos_caja.append(tiempos)
                etiquetas.append(f"{N_FREQ[frecuencia][:4]}\n{N_LONG[longitud][:4]}")

        fig, ax = plt.subplots(figsize=(14, 7))
        sns.boxplot(data=datos_caja, ax=ax, palette="Set3", showfliers=True)
        ax.set_xticklabels(etiquetas)
        ax.set_title(f'Latency Dispersion (Box & Whisker) - Top-K = {k}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Configuration (Frequency - Length)', fontsize=12)
        ax.set_ylabel('Latency (ms)', fontsize=12)
        ax.grid(True, axis='y', alpha=0.3)

        plt.tight_layout()
        ruta_archivo = os.path.join(directorio_salida, f'box_whisker_plots_{k}.png')
        plt.savefig(ruta_archivo, dpi=300, bbox_inches='tight')
        print(f"[+] Diagrama de cajas guardado: {ruta_archivo}")
        plt.close()

def generar_grafica_comparativa(resultados_completos: Dict, directorio_salida: str):
    """
    Construye una gráfica de barras agrupadas que compara todas las configuraciones.
    Visualiza el impacto conjunto de los tres parámetros principales (k, frecuencia y longitud)
    en la latencia media del sistema.
    """
    k_values = sorted(resultados_completos.keys())
    datos_grafica = []

    for k in k_values:
        for frecuencia in FRECUENCIAS:
            for longitud in LONGITUDES:
                media = resultados_completos[k][frecuencia][longitud]['media']
                datos_grafica.append({
                    'k': k,
                    'Frequency': N_FREQ[frecuencia],
                    'Length': N_LONG[longitud],
                    'Latency (ms)': media
                })

    if not datos_grafica:
        return

    df = pd.DataFrame(datos_grafica)
    fig, ax = plt.subplots(figsize=(16, 8))

    x = np.arange(len(FRECUENCIAS) * len(LONGITUDES))
    ancho_barra = 0.8 / max(len(k_values), 1)

    for i, k in enumerate(k_values):
        k_data = df[df['k'] == k]
        medias = k_data['Latency (ms)'].values
        offset = (i - (len(k_values) - 1) / 2) * ancho_barra
        bars = ax.bar(x + offset, medias, ancho_barra, label=f'k={k}')

        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=8)

    ax.set_xlabel('Configuration (Frequency - Length)', fontsize=12)
    ax.set_ylabel('Mean Latency (ms)', fontsize=12)
    ax.set_title('Latency Comparison: Impact of k, Frequency, and Length', fontsize=14, fontweight='bold')

    labels = [f"{N_FREQ[f][:4]}\n{N_LONG[l][:4]}" for f in FRECUENCIAS for l in LONGITUDES]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(title='Search Depth (k)', fontsize=10)
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    filename = os.path.join(directorio_salida, 'comparativa_todas_configuraciones.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[+] Grafica comparativa guardada: {filename}")
    plt.close()

def generar_mapa_calor(resultados_completos: Dict, directorio_salida: str):
    """
    Crea un mapa de calor que muestra la latencia como intensidad de color.
    Facilita la identificación rápida de las combinaciones de parámetros
    que producen mayores o menores latencias.
    """
    for k in sorted(resultados_completos.keys()):
        matriz = np.zeros((3, 3))

        for i, frecuencia in enumerate(FRECUENCIAS):
            for j, longitud in enumerate(LONGITUDES):
                matriz[i, j] = resultados_completos[k][frecuencia][longitud]['media']

        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(
            matriz,
            annot=True,
            fmt='.2f',
            cmap='YlOrRd',
            xticklabels=[N_LONG[l] for l in LONGITUDES],
            yticklabels=[N_FREQ[f] for f in FRECUENCIAS],
            ax=ax,
            cbar_kws={'label': 'Latency (ms)'}
        )

        ax.set_title(f'Latency Heatmap - k={k}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Query Length', fontsize=12)
        ax.set_ylabel('Semantic Frequency', fontsize=12)

        plt.tight_layout()
        filename = os.path.join(directorio_salida, f'heatmap_k{k}.png')
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[+] Heatmap guardado: {filename}")
        plt.close()

def prueba_latencia_rag_con_cache(rag_chain, queries: Dict, k: int, num_iteraciones: int,
                                  config_name: str, embeddings, monitor: CacheMonitor):
    """Ejecuta el conjunto de consultas midiendo el rendimiento y detectando hits de caché.
    Recopila estadísticas detalladas para posterior análisis del comportamiento del sistema."""
    print(f"\n[*] Ejecutando pruebas con configuración: {config_name}, k={k}")
    cache_type = CACHE_CONFIGS.get(config_name, {}).get('tipo', 'none')

    todas_las_queries = []
    for frecuencia in FRECUENCIAS:
        for longitud in LONGITUDES:
            lista_textos = queries[frecuencia][longitud]
            for texto in lista_textos:
                todas_las_queries.append((texto, frecuencia, longitud))

    tiempos_brutos = {f: {l: [] for l in LONGITUDES} for f in FRECUENCIAS}
    todas_latencias = []

    gc.disable()
    try:
        for iteracion in range(num_iteraciones):
            print(f"    -> Iteración {iteracion + 1}/{num_iteraciones}")
            random.shuffle(todas_las_queries)

            for i, (texto_query, freq, long) in enumerate(todas_las_queries):
                # Medimos el tiempo que tarda en procesarse la consulta
                inicio = time.perf_counter()
                respuesta = rag_chain.invoke({"input": texto_query})
                fin = time.perf_counter()

                latencia = (fin - inicio) * 1000

                # Determinamos si fue un acierto de caché basándonos en la latencia observada
                es_cache_hit = detectar_cache_hit(
                    latencia,
                    cache_type=cache_type,
                    percentil_threshold=100.0
                )

                # Guardamos las métricas para análisis posterior
                monitor.registrar_consulta(latencia, es_cache_hit, freq, long)

                # Almacenamos toda la información de esta consulta
                tiempos_brutos[freq][long].append({
                    'latencia': latencia,
                    'cache_hit': es_cache_hit,
                    'respuesta': respuesta['answer'][:100]  # Primeros 100 chars
                })
                todas_latencias.append(latencia)

                if (i + 1) % 50 == 0:
                    print(f"        Progreso: {i+1}/{len(todas_las_queries)} queries")

        print("    -> Procesando resultados...")
        results = {}
        for freq in FRECUENCIAS:
            results[freq] = {}
            for long in LONGITUDES:
                datos = tiempos_brutos[freq][long]
                latencias = [d['latencia'] for d in datos]

                # Eliminamos valores atípicos que distorsionarían las estadísticas
                if latencias:
                    limite = np.percentile(latencias, 99)
                    latencias_limpias = [t for t in latencias if t <= limite]
                else:
                    latencias_limpias = []

                results[freq][long] = {
                    'datos_completos': datos,
                    'tiempos_limpios': latencias_limpias,
                    'media': np.mean(latencias_limpias) if latencias_limpias else 0,
                    'mediana': np.median(latencias_limpias) if latencias_limpias else 0,
                    'std': np.std(latencias_limpias) if latencias_limpias else 0,
                    'outliers': len(latencias) - len(latencias_limpias),
                    'cache_hits': sum(1 for d in datos if d['cache_hit']),
                    'cache_misses': sum(1 for d in datos if not d['cache_hit'])
                }

    except Exception as e:
        print(f"\n[!] Error durante la prueba: {e}")
        return None, None
    finally:
        gc.enable()
        gc.collect()

    return results, todas_latencias

def generar_graficas_densidad(resultados_completos: Dict, directorio_salida: str):
    """Crea visualizaciones de densidad de kernel para analizar la distribución
    de latencias en cada configuración del experimento"""

    for k in sorted(resultados_completos.keys()):
        results = resultados_completos[k]
        fig, axes = plt.subplots(3, 3, figsize=(18, 15))
        fig.suptitle(f'Latency Distribution - k={k}', fontsize=16, fontweight='bold')

        for i, frecuencia in enumerate(FRECUENCIAS):
            for j, longitud in enumerate(LONGITUDES):
                ax = axes[i, j]
                data = results[frecuencia][longitud]['tiempos_limpios']

                # Generamos la estimación de densidad de kernel
                if data:  # Verificar que hay datos
                    sns.kdeplot(data=data, ax=ax, fill=True, color='blue', alpha=0.6)

                # Marcamos la media para facilitar la interpretación
                media = results[frecuencia][longitud]['media']
                ax.axvline(media, color='red', linestyle='--', linewidth=2,
                          label=f'Mean: {media:.2f}ms')

                # Ajustamos las etiquetas y formato del gráfico
                ax.set_title(f'{N_FREQ[frecuencia]} Frequency - {N_LONG[longitud]}')
                ax.set_xlabel('Latency (ms)')
                ax.set_ylabel('Density')
                ax.legend()
                ax.grid(True, alpha=0.3)

        plt.tight_layout()
        filename = os.path.join(directorio_salida, f'densidad_latencias_k{k}.png')
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[+] Grafica guardada: {filename}")
        plt.close()

def generar_graficas_rag_por_configuracion(resultados_globales: Dict):
    """
    Produce el conjunto completo de visualizaciones para cada configuración de caché.
    Esto permite comparar el comportamiento del sistema RAG bajo diferentes estrategias
    de almacenamiento en caché.
    """
    for config_name, data in resultados_globales.items():
        resultados_por_k = data.get('resultados_por_k', {})
        if not resultados_por_k:
            print(f"[!] Sin resultados de latencia para {config_name}. No se generan gráficas RAG.")
            continue

        directorio_config = os.path.join(DIRECTORIO_SALIDA, config_name)
        os.makedirs(directorio_config, exist_ok=True)

        print(f"[*] Generando gráficas RAG para configuración: {config_name}")
        generar_graficas_densidad(resultados_por_k, directorio_config)
        generar_graficas_densidad_superpuesta(resultados_por_k, directorio_config)
        generar_diagramas_caja(resultados_por_k, directorio_config)
        generar_grafica_comparativa(resultados_por_k, directorio_config)
        generar_mapa_calor(resultados_por_k, directorio_config)

def configurar_llm():
    """Inicializa el modelo de lenguaje que usaremos para generar las respuestas.
    El modelo se carga en la GPU para acelerar la inferencia."""
    print("\n[*] Cargando el LLM (HuggingFaceTB/SmolLM2-135M-Instruct) en la tarjeta gráfica")
    model_id = "HuggingFaceTB/SmolLM2-135M-Instruct"

    tokenizer = AutoTokenizer.from_pretrained(model_id)
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

    llm = HuggingFacePipeline(pipeline=pipe)
    print("[+] LLM cargado y listo.")
    return llm

def main():
    print("=" * 60)
    print("INICIANDO PRUEBA RAG CON CACHÉ SEMÁNTICA")
    print("=" * 60)

    # Preparamos el directorio donde guardaremos los resultados
    os.makedirs(DIRECTORIO_SALIDA, exist_ok=True)

    # Paso 1: Comprobamos que tenemos acceso a Redis y sus módulos necesarios
    print("\n[*] Verificando conexión con Redis...")
    redis_disponible = False
    redisearch_disponible = False

    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
        print("[+] Redis conectado correctamente")
        redis_disponible = True

        # Verificamos que el módulo de búsqueda semántica esté instalado
        print("[*] Verificando módulo RediSearch...")
        if verificar_redis_stack():
            print("[+] RediSearch disponible - Caché semántica habilitada")
            redisearch_disponible = True
        else:
            print("[!] RediSearch NO disponible")

    except redis.ConnectionError:
        print("[!] Redis no está disponible")


    # Adaptamos las pruebas según los componentes disponibles en el sistema
    if not redis_disponible:
        print("\n[!] Ejecutando solo con caché en memoria y sin caché")
        global CACHE_CONFIGS
        CACHE_CONFIGS = {
            'sin_cache': {'tipo': 'none', 'umbral': None},
            'cache_exacta': {'tipo': 'memory', 'umbral': None}
        }
    elif not redisearch_disponible:
        print("\n[!] Redis disponible pero sin RediSearch")
        print("[!] Deshabilitando configuraciones de caché semántica")
        CACHE_CONFIGS = {
            'sin_cache': {'tipo': 'none', 'umbral': None},
            'cache_exacta': {'tipo': 'memory', 'umbral': None}
        }

    # Paso 2: Cargamos las consultas de prueba desde el archivo JSON
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        queries = json.load(f)

    # Paso 3: Inicializamos el modelo de embeddings y el modelo de lenguaje
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    llm = configurar_llm()

    # Paso 4: Establecemos conexión con la base de datos vectorial
    print("\n[*] Conectando a ChromaDB")
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=DATABASE_PATH,
        embedding_function=embeddings
    )

    # Estructura para guardar todos los datos del experimento
    resultados_globales = {}

    # Paso 5: Realizamos las pruebas con cada estrategia de caché configurada
    for config_name in CACHE_CONFIGS.keys():
        print(f"\n{'='*60}")
        print(f"CONFIGURACIÓN: {config_name}")
        print(f"{'='*60}")

        resultados_config = {
            'resultados_por_k': {},
            'metricas_cache': {},
            'latencias': []
        }

        for k in K_VALUES:
            print(f"\n[*] Configurando retriever con k={k}")
            retriever = vectorstore.as_retriever(search_kwargs={"k": k})

            # Construimos el pipeline de recuperación y generación
            template = """Eres un asistente analítico. Usa el siguiente contexto para responder a la pregunta.
                        Regla estricta: Si la pregunta trata sobre un término de baja frecuencia, o si la información del contexto es escasa o poco relevante, tu respuesta debe ser ÚNICA y EXCLUSIVAMENTE la palabra "Baja". No añadas puntos, ni saludos, ni explicaciones adicionales.
                        Si hay abundante información, genera una respuesta detallada y extensa.

                        Contexto:
                        {context}

                        Pregunta: {input}
                        Respuesta:"""
            prompt = PromptTemplate.from_template(template)
            document_chain = create_stuff_documents_chain(llm, prompt)
            rag_chain = create_retrieval_chain(retriever, document_chain)

            # Activamos el sistema de caché correspondiente y su monitor
            monitor = configurar_cache(config_name, embeddings)

            # Si hubo algún error de configuración, pasamos a la siguiente
            if monitor is None:
                print(f"[!] Saltando configuración {config_name} debido a errores")
                continue

            # Hacemos una consulta inicial para preparar el sistema
            print("[*] Calentando motor RAG...")
            try:
                print("    -> Intentando invoke de calentamiento...")
                _ = rag_chain.invoke({"input": "query de calentamiento"})
                print("    -> Calentamiento exitoso")
            except ValueError as e:
                if "RediSearch" in str(e):
                    print(f"\n[!] ERROR: RedisSemanticCache requiere RediSearch >=2.4")
                    print(f"[!] Detalles: {str(e)[:200]}...")
                    print(f"[!] Esta configuración ({config_name}) no puede ejecutarse")
                    print(f"[!] Saltando a la siguiente configuración...\n")
                    continue
                else:
                    print(f"[!] Error de valor inesperado: {e}")
                    continue
            except Exception as e:
                print(f"\n[!] ERROR durante calentamiento: {type(e).__name__}")
                print(f"[!] Mensaje: {str(e)[:200]}...")
                print(f"[!] Saltando configuración {config_name}")
                continue

            # Liberamos memoria antes de comenzar las pruebas reales
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            time.sleep(2)

            # Lanzamos el conjunto completo de consultas de prueba
            results, todas_latencias = prueba_latencia_rag_con_cache(
                rag_chain, queries, k, NUM_ITERACIONES,
                config_name, embeddings, monitor
            )

            if results:
                resultados_config['resultados_por_k'][k] = results
                resultados_config['latencias'].extend(todas_latencias)

                # Recopilamos las estadísticas finales del monitor
                resumen_cache = monitor.obtener_resumen()
                resultados_config['metricas_cache'][k] = resumen_cache

                # Mostramos un resumen rápido en consola
                print(f"\n[+] Resumen k={k}, config={config_name}:")
                print(f"    Hit Rate: {resumen_cache['hit_rate']:.1%}")
                print(f"    Latencia media hits: {resumen_cache['latencia_media_hits']:.2f}ms")
                print(f"    Latencia media misses: {resumen_cache['latencia_media_misses']:.2f}ms")

        # Analizamos cómo la caché reduce la información filtrada por timing
        if 'sin_cache' in resultados_globales and config_name != 'sin_cache':
            var_sin_cache = np.var(resultados_globales['sin_cache']['latencias'])
            var_con_cache = np.var(resultados_config['latencias'])
            reduccion = (1 - var_con_cache/var_sin_cache) * 100

            resultados_config['impacto_canal_lateral'] = {
                'var_sin_cache': var_sin_cache,
                'var_con_cache': var_con_cache,
                'reduccion_senal': reduccion
            }

            print(f"\n[!] Impacto en canal lateral:")
            print(f"    Reducción de varianza: {reduccion:.1f}%")

        resultados_globales[config_name] = resultados_config

    # Paso 6: Creamos todas las gráficas y documentos de análisis
    print(f"\n{'='*60}")
    print("GENERANDO VISUALIZACIONES Y REPORTES")
    print(f"{'='*60}")

    # Producimos las visualizaciones específicas del análisis de caché
    resultados_cache_resumen = {}
    for config_name, data in resultados_globales.items():
        # Agregamos las estadísticas de todos los valores de k probados
        resumen_combinado = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'hit_latencies': [],
            'miss_latencies': []
        }

        for k, metricas in data['metricas_cache'].items():
            if isinstance(metricas, dict) and 'total_queries' in metricas:
                resumen_combinado['total_queries'] += metricas['total_queries']
                resumen_combinado['cache_hits'] += metricas['cache_hits']
                resumen_combinado['cache_misses'] += metricas['cache_misses']
                resumen_combinado['hit_latencies'].extend(metricas.get('hit_latencies', []))
                resumen_combinado['miss_latencies'].extend(metricas.get('miss_latencies', []))

        if resumen_combinado['total_queries'] > 0:
            resumen_combinado['hit_rate'] = resumen_combinado['cache_hits'] / resumen_combinado['total_queries']
            resumen_combinado['miss_rate'] = 1 - resumen_combinado['hit_rate']
            resumen_combinado['latencia_media_hits'] = np.mean(resumen_combinado['hit_latencies']) if resumen_combinado['hit_latencies'] else 0
            resumen_combinado['latencia_media_misses'] = np.mean(resumen_combinado['miss_latencies']) if resumen_combinado['miss_latencies'] else 0

            # Consolidamos las métricas agrupadas por categoría
            resumen_combinado['hit_rates_por_frecuencia'] = {}
            resumen_combinado['hit_rates_por_longitud'] = {}

            for k_val in data['metricas_cache'].keys():
                if isinstance(data['metricas_cache'][k_val], dict):
                    for key in ['hit_rates_por_frecuencia', 'hit_rates_por_longitud']:
                        if key in data['metricas_cache'][k_val]:
                            if key not in resumen_combinado:
                                resumen_combinado[key] = {}
                            resumen_combinado[key].update(data['metricas_cache'][k_val][key])

        resultados_cache_resumen[config_name] = {
            'resumen': resumen_combinado,
            'latencias': data['latencias'],
            'impacto_canal_lateral': data.get('impacto_canal_lateral', {})
        }

    generar_graficas_cache(resultados_cache_resumen)
    generar_graficas_rag_por_configuracion(resultados_globales)

    # Creamos informes detallados para cada valor de k
    for k in K_VALUES:
        reporte_data = {}
        for config_name in resultados_globales.keys():
            if k in resultados_globales[config_name]['metricas_cache']:
                reporte_data[config_name] = {
                    'resumen': resultados_globales[config_name]['metricas_cache'][k],
                    'impacto_canal_lateral': resultados_globales[config_name].get('impacto_canal_lateral', {})
                }
        generar_reporte_cache(reporte_data, k)

    # Exportamos todos los datos a formato CSV para análisis externo
    filas = []
    for config_name, data in resultados_globales.items():
        for k, results in data['resultados_por_k'].items():
            for freq in FRECUENCIAS:
                for long in LONGITUDES:
                    result = results[freq][long]
                    filas.append({
                        'config_cache': config_name,
                        'k': k,
                        'frecuencia': N_FREQ[freq],
                        'longitud': N_LONG[long],
                        'latencia_media_ms': result['media'],
                        'mediana_ms': result['mediana'],
                        'std_ms': result['std'],
                        'cache_hits': result['cache_hits'],
                        'cache_misses': result['cache_misses'],
                        'hit_rate': result['cache_hits'] / (result['cache_hits'] + result['cache_misses']) if (result['cache_hits'] + result['cache_misses']) > 0 else 0
                    })

    df = pd.DataFrame(filas)
    filename = os.path.join(DIRECTORIO_SALIDA, 'resultados_cache_semantica.csv')
    df.to_csv(filename, index=False)
    print(f"\n[+] Resultados guardados en: {filename}")

    # Presentamos un resumen ejecutivo de los resultados principales
    print(f"\n{'='*60}")
    print("RESUMEN FINAL")
    print(f"{'='*60}")

    for config_name, data in resultados_cache_resumen.items():
        print(f"\n{config_name}:")
        print(f"  Hit Rate Global: {data['resumen']['hit_rate']:.1%}")
        print(f"  Reducción latencia: {(1 - data['resumen']['latencia_media_hits']/data['resumen']['latencia_media_misses'])*100:.1f}%" if data['resumen']['latencia_media_misses'] > 0 else "  N/A")
        if 'reduccion_senal' in data.get('impacto_canal_lateral', {}):
            print(f"  Reducción señal canal lateral: {data['impacto_canal_lateral']['reduccion_senal']:.1f}%")

    print(f"\n[+] PRUEBA COMPLETADA")

if __name__ == "__main__":
    main()
