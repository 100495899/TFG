import pandas as pd
import numpy as np
import time
import random
import chromadb
from sentence_transformers import SentenceTransformer
import json
import gc
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# =====================================================================
# CONFIGURACIÓN DEL EXPERIMENTO
# =====================================================================
#DATABASE_PATH = "./workspace/pg19"
DATABASE_PATH = "./bd_tfg_local"
#COLLECTION_NAME = "gutenberg_completo"
COLLECTION_NAME = "coleccion_nltk"
#QUERIES_FILE = "queries_ataque.json"
QUERIES_FILE = "./Script_PoC/queries_ataque.json"
CSV_FRONTERAS = './Script_PoC/resultados_prueba_latencias.csv'

# Parámetros del experimento
K_VALUES = [5, 50, 100, 200]

# Mapeo de nombres para visualización
NOMBRE_CLASES = {
    'high_frequency': 'High',
    'medium_frequency': 'Medium',
    'low_frequency': 'Low'
}

# =====================================================================
# 1. CARGA DE FRONTERAS ESTADÍSTICAS
# =====================================================================
def cargar_fronteras_desde_csv(csv_path: str) -> Dict:
    """
    Carga las fronteras de clasificación desde el CSV de resultados previos
    """
    print("\n[*] Cargando fronteras estadísticas desde CSV...")
    df = pd.read_csv(csv_path)

    # Agrupamos por k y frecuencia, promediando las longitudes
    df_grouped = df.groupby(['k', 'Frequency']).agg({
        'Mean_Latency (ms)': 'mean',
        'Std_Latency (ms)': 'mean'
    }).reset_index()

    fronteras = {}
    estadisticas = {}

    for k_val in df_grouped['k'].unique():
        df_k = df_grouped[df_grouped['k'] == k_val]

        try:
            # Extraemos medias para cada frecuencia
            mu_H = df_k[df_k['Frequency'] == 'High']['Mean_Latency (ms)'].values[0]
            mu_M = df_k[df_k['Frequency'] == 'Medium']['Mean_Latency (ms)'].values[0]
            mu_L = df_k[df_k['Frequency'] == 'Low']['Mean_Latency (ms)'].values[0]

            # Guardamos estadísticas completas
            std_H = df_k[df_k['Frequency'] == 'High']['Std_Latency (ms)'].values[0]
            std_M = df_k[df_k['Frequency'] == 'Medium']['Std_Latency (ms)'].values[0]
            std_L = df_k[df_k['Frequency'] == 'Low']['Std_Latency (ms)'].values[0]

            estadisticas[k_val] = {
                'High': {'mean': mu_H, 'std': std_H},
                'Medium': {'mean': mu_M, 'std': std_M},
                'Low': {'mean': mu_L, 'std': std_L}
            }

            # Calculamos fronteras (punto medio entre clases)
            fronteras[k_val] = {
                'HM': (mu_H + mu_M) / 2,  # Frontera High-Medium
                'ML': (mu_M + mu_L) / 2   # Frontera Medium-Low
            }

            print(f"    k={k_val}: H-M={fronteras[k_val]['HM']:.2f}ms, M-L={fronteras[k_val]['ML']:.2f}ms")

        except IndexError:
            print(f"    [!] Datos incompletos para k={k_val}")

    return fronteras, estadisticas

# =====================================================================
# 2. CLASIFICADOR BASADO EN LATENCIAS
# =====================================================================
def clasificar_por_latencia(latencia_media: float, k: int, fronteras: Dict) -> str:
    """
    Clasifica un término basándose en su latencia media
    """
    if k not in fronteras:
        return "Unknown"

    f_HM = fronteras[k]['HM']
    f_ML = fronteras[k]['ML']

    if latencia_media < f_HM:
        return "High"
    elif latencia_media < f_ML:
        return "Medium"
    else:
        return "Low"

# =====================================================================
# 3. CONEXIÓN Y QUERIES A CHROMADB
# =====================================================================
def realizar_ataque_temporal(collection, model, queries_dict: Dict, k: int, fronteras: Dict) -> Dict:
    """
    Ejecuta el ataque de canal lateral midiendo tiempos reales de ChromaDB
    Usa la nueva estructura: 3 términos por clase, 20 variaciones cada uno
    """
    print(f"\n[*] Ejecutando ataque con k={k}")

    # Preparar todas las queries con su información
    queries_preparadas = []
    total_queries_base = 0

    for frecuencia in ['high_frequency', 'medium_frequency', 'low_frequency']:
        clase_nombre = NOMBRE_CLASES[frecuencia]

        # Para cada término en esta frecuencia (time/day/man, world/friend/face, bitcoin/ethereum/playstation)
        for termino_clave, variaciones in queries_dict[frecuencia].items():
            # Tomamos todas las 20 variaciones de cada término
            print(f"    -> Procesando término '{termino_clave}' ({clase_nombre}): {len(variaciones)} variaciones")

            # Vectorizamos todas las variaciones de una vez
            vectores = model.encode(variaciones).tolist()

            # Guardamos cada variación con su información
            for variacion_texto, vector in zip(variaciones, vectores):
                queries_preparadas.append({
                    'termino_base': termino_clave,
                    'texto': variacion_texto,
                    'vector': vector,
                    'clase_real': clase_nombre,
                    'tiempos': []
                })
            total_queries_base += len(variaciones)

    print(f"    -> Total queries preparadas: {total_queries_base} (9 términos × 20 variaciones)")

    # Mezclar aleatoriamente todas las queries para evitar sesgo de caché
    random.shuffle(queries_preparadas)
    print(f"    -> Queries mezcladas aleatoriamente para k={k}")

    # Ejecutar queries y medir tiempos
    print(f"    -> Ejecutando {total_queries_base} queries...")
    gc.disable()  # Desactivar recolección de basura durante medición

    for i, query_info in enumerate(queries_preparadas):
        inicio = time.perf_counter()
        _ = collection.query(
            query_embeddings=query_info['vector'],
            n_results=k
        )
        fin = time.perf_counter()

        latencia_ms = (fin - inicio) * 1000
        query_info['latencia'] = latencia_ms

        if (i + 1) % 50 == 0:
            print(f"        Progreso: {i+1}/{total_queries_base} queries ({(i+1)*100/total_queries_base:.1f}%)")

    gc.enable()
    gc.collect()

    # Agrupar resultados por término base y calcular estadísticas
    resultados = []
    terminos_procesados = {}

    # Agrupar latencias por término base
    for query in queries_preparadas:
        termino_base = query['termino_base']
        if termino_base not in terminos_procesados:
            terminos_procesados[termino_base] = {
                'clase_real': query['clase_real'],
                'latencias': [],
                'variaciones': []
            }
        terminos_procesados[termino_base]['latencias'].append(query['latencia'])
        if query['texto'] not in terminos_procesados[termino_base]['variaciones']:
            terminos_procesados[termino_base]['variaciones'].append(query['texto'])

    # Calcular estadísticas y clasificar cada término
    for termino_base, datos in terminos_procesados.items():
        # Filtrar outliers (top 1%)
        latencias = datos['latencias']
        if latencias:
            limite = np.percentile(latencias, 99)
            latencias_limpias = [t for t in latencias if t <= limite]

            latencia_media = np.mean(latencias_limpias)
            clase_predicha = clasificar_por_latencia(latencia_media, k, fronteras)

            resultados.append({
                'termino': termino_base,
                'clase_real': datos['clase_real'],
                'clase_predicha': clase_predicha,
                'latencia_media': latencia_media,
                'std': np.std(latencias_limpias),
                'n_mediciones': len(latencias_limpias),
                'n_variaciones': len(datos['variaciones'])
            })

    return resultados

# =====================================================================
# 4. GENERACIÓN DE MATRIZ DE CONFUSIÓN
# =====================================================================
def generar_matriz_confusion(resultados: List[Dict], k: int) -> np.ndarray:
    """
    Genera y visualiza la matriz de confusión
    """
    clases = ['High', 'Medium', 'Low']
    y_real = [r['clase_real'] for r in resultados]
    y_pred = [r['clase_predicha'] for r in resultados]

    # Calcular matriz
    matriz = confusion_matrix(y_real, y_pred, labels=clases)

    # Calcular métricas
    precision_global = sum([r['clase_real'] == r['clase_predicha'] for r in resultados]) / len(resultados)

    # Visualizar
    plt.figure(figsize=(8, 6))
    sns.heatmap(matriz, annot=True, fmt='d', cmap='Blues',
                xticklabels=clases, yticklabels=clases,
                cbar_kws={'label': 'Número de casos'})
    plt.title(f'Matriz de Confusión - k={k}\nPrecisión Global: {precision_global:.1%}')
    plt.xlabel('Clase Predicha')
    plt.ylabel('Clase Real')
    plt.tight_layout()
    plt.savefig(f'./matriz/matriz_confusion_k{k}.png', dpi=150)
    plt.close()  # Cerrar sin mostrar
    print(f"    -> Matriz de confusión guardada: matriz_confusion_k{k}.png")

    # Imprimir análisis detallado
    print(f"\n    === Resultados k={k} ===")
    print(f"    Precisión Global: {precision_global:.1%}")

    # Análisis por clase
    for i, clase in enumerate(clases):
        total_real = sum(matriz[i])
        if total_real > 0:
            precision_clase = matriz[i][i] / total_real
            print(f"    {clase}: {matriz[i][i]}/{total_real} correctos ({precision_clase:.1%})")

            # Análisis de errores
            errores = []
            for j, pred_clase in enumerate(clases):
                if i != j and matriz[i][j] > 0:
                    errores.append(f"{matriz[i][j]} como {pred_clase}")
            if errores:
                print(f"        Errores: {', '.join(errores)}")

    # Calcular penalización por errores graves
    errores_graves = matriz[0][2] + matriz[2][0]  # High->Low o Low->High
    errores_leves = matriz[0][1] + matriz[1][0] + matriz[1][2] + matriz[2][1]  # Adyacentes

    print(f"    Errores graves (High<->Low): {errores_graves}")
    print(f"    Errores leves (adyacentes): {errores_leves}")

    return matriz, precision_global

# =====================================================================
# 5. ANÁLISIS DE DISTRIBUCIONES
# =====================================================================
def analizar_distribuciones(resultados: List[Dict], k: int):
    """
    Visualiza las distribuciones de latencias por clase
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for i, clase in enumerate(['High', 'Medium', 'Low']):
        ax = axes[i]

        # Filtrar resultados de esta clase real
        datos_clase = [r['latencia_media'] for r in resultados if r['clase_real'] == clase]

        if datos_clase:
            # Histograma con KDE
            ax.hist(datos_clase, bins=15, alpha=0.6, color='blue', edgecolor='black')
            ax.axvline(np.mean(datos_clase), color='red', linestyle='--',
                      label=f'Media: {np.mean(datos_clase):.2f}ms')

            # Colorear según clasificación
            for r in resultados:
                if r['clase_real'] == clase:
                    color = 'green' if r['clase_predicha'] == clase else 'red'
                    ax.scatter(r['latencia_media'], 0, color=color, alpha=0.5, s=30)

            ax.set_title(f'Clase: {clase}')
            ax.set_xlabel('Latencia (ms)')
            ax.set_ylabel('Frecuencia')
            ax.legend()
            ax.grid(True, alpha=0.3)

    plt.suptitle(f'Distribución de Latencias - k={k}')
    plt.tight_layout()
    plt.savefig(f'./matriz/distribucion_latencias_k{k}.png', dpi=150)
    plt.close()  # Cerrar sin mostrar
    print(f"    -> Distribución de latencias guardada: distribucion_latencias_k{k}.png")

# =====================================================================
# 6. FUNCIÓN PRINCIPAL
# =====================================================================
def main():
    print("=" * 60)
    print("SIMULADOR DE ATAQUE POR CANAL LATERAL - CHROMADB")
    print("=" * 60)

    # Cargar fronteras desde CSV
    fronteras, estadisticas = cargar_fronteras_desde_csv(CSV_FRONTERAS)

    # Cargar queries desde JSON
    print("\n[*] Cargando queries desde JSON...")
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        queries_dict = json.load(f)

    # Conectar a ChromaDB
    print(f"\n[*] Conectando a ChromaDB en {DATABASE_PATH}...")
    client = chromadb.PersistentClient(path=DATABASE_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    print(f"[+] Colección cargada. Total vectores: {collection.count()}")

    # Cargar modelo de embeddings
    print("\n[*] Cargando modelo de embeddings...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("[+] Modelo cargado")

    # Calentamiento
    print("\n[*] Calentando motor HNSW...")
    vector_calentamiento = model.encode(["query de calentamiento"]).tolist()
    _ = collection.query(query_embeddings=vector_calentamiento, n_results=5)
    print("[+] Motor calentado")

    # Almacenar todos los resultados
    todos_resultados = {}

    # Ejecutar experimentos
    for k in K_VALUES:
        if k not in fronteras:
            print(f"\n[!] Saltando k={k} - No hay fronteras disponibles")
            continue

        print(f"\n{'='*60}")
        print(f"EXPERIMENTO CON k={k}")
        print(f"{'='*60}")

        # Limpiar memoria antes de cada prueba
        gc.collect()
        time.sleep(1)

        # Ejecutar ataque
        resultados = realizar_ataque_temporal(
            collection, model, queries_dict, k, fronteras
        )

        # Generar matriz de confusión
        matriz, precision = generar_matriz_confusion(resultados, k)

        # Analizar distribuciones
        analizar_distribuciones(resultados, k)

        # Guardar resultados
        todos_resultados[k] = {
            'resultados': resultados,
            'matriz': matriz,
            'precision_global': precision
        }

    # Resumen final
    print(f"\n{'='*60}")
    print("RESUMEN FINAL DEL ATAQUE")
    print(f"{'='*60}")

    for k in todos_resultados:
        precision = todos_resultados[k]['precision_global']
        print(f"\n[k={k}]: Precisión Global = {precision:.1%}")

        # Mostrar clasificación por término
        print("  Clasificación por término:")
        for resultado in todos_resultados[k]['resultados']:
            correcto = "OK" if resultado['clase_real'] == resultado['clase_predicha'] else "X"
            print(f"    {correcto} {resultado['termino']:12} - Real: {resultado['clase_real']:6} | Predicho: {resultado['clase_predicha']:6} | Latencia: {resultado['latencia_media']:.2f}ms")

    # Guardar resultados detallados en CSV
    print("\n[*] Guardando resultados detallados...")
    for k in todos_resultados:
        df = pd.DataFrame(todos_resultados[k]['resultados'])
        df.to_csv(f'resultados_ataque_k{k}.csv', index=False)
        print(f"    -> Resultados guardados: resultados_ataque_k{k}.csv")

    print("\n[+] Ataque completado exitosamente")

if __name__ == "__main__":
    main()