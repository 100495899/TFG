import pandas as pd
import numpy as np
import math

# 1. Cargar los datos
csv_file = './Script_PoC/resultados_prueba_latencias.csv'
df = pd.read_csv(csv_file)

# Vamos a agrupar por 'k' y 'Frequency', promediando las diferentes longitudes (Short, Medium, Long)
# para obtener una única Media y Desviación Estándar por cada Frecuencia en un 'k' dado.
df_grouped = df.groupby(['k', 'Frequency']).agg({
    'Mean_Latency (ms)': 'mean',
    'Std_Latency (ms)': 'mean'
}).reset_index()

def calcular_intentos_necesarios(mu_i, mu_j, sigma_i, sigma_j, confianza="95"):
    """
    Aplica la fórmula matemática para calcular el número de intentos (n).
    """
    # Valores Z estándar en estadística
    z_dict = {"95": 1.96, "99": 2.58}
    z = z_dict[confianza]
    
    numerador = (z**2) * ((sigma_i**2) + (sigma_j**2))
    denominador = (mu_i - mu_j)**2
    
    # Si las medias son idénticas, el denominador es 0 (evitamos división por cero)
    if denominador == 0:
        return float('inf')
    
    n = numerador / denominador
    return math.ceil(n) # Redondeamos hacia arriba porque no puedes hacer "3.1" intentos

# 2. Analizar y comparar las clases para cada valor de 'k'
K_VALUES = df_grouped['k'].unique()
PARES = [('High', 'Low'), ('High', 'Medium'), ('Medium', 'Low')]

print("=== HERRAMIENTA ESTADÍSTICA: ANÁLISIS DE CANAL LATERAL EN CHROMADB ===\n")

for k in K_VALUES:
    print(f"--- Análisis para k = {k} ---")
    df_k = df_grouped[df_grouped['k'] == k]
    
    # Extraemos los datos de cada clase
    datos_clases = {}
    for freq in ['High', 'Medium', 'Low']:
        row = df_k[df_k['Frequency'] == freq]
        if not row.empty:
            datos_clases[freq] = {
                'mu': row['Mean_Latency (ms)'].values[0],
                'sigma': row['Std_Latency (ms)'].values[0]
            }
            
    # Calculamos la fórmula para cada par
    for clase1, clase2 in PARES:
        if clase1 in datos_clases and clase2 in datos_clases:
            mu1, sigma1 = datos_clases[clase1]['mu'], datos_clases[clase1]['sigma']
            mu2, sigma2 = datos_clases[clase2]['mu'], datos_clases[clase2]['sigma']
            
            n_95 = calcular_intentos_necesarios(mu1, mu2, sigma1, sigma2, "95")
            n_99 = calcular_intentos_necesarios(mu1, mu2, sigma1, sigma2, "99")
            
            diferencia_medias = abs(mu1 - mu2)
            
            print(f"Comparando [{clase1}] vs [{clase2}]:")
            print(f"  -> Diferencia de tiempos: {diferencia_medias:.2f} ms")
            print(f"  -> Intentos necesarios (95% confianza): {n_95}")
            print(f"  -> Intentos necesarios (99% confianza): {n_99}\n")