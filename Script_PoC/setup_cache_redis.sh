#!/bin/bash

echo "================================================"
echo "ARRANCANDO ENTORNO PERSISTENTE"
echo "================================================"

# 1. Arrancar el Redis Stack avanzado que guardamos en tu disco
echo "[*] Iniciando Redis Stack Server en segundo plano..."
nohup /workspace/redis-stack-persistent/bin/redis-stack-server > /workspace/redis.log 2>&1 &

echo "[*] ¡Todo listo! Redis está escuchando en el puerto 6379."
echo ""
echo "IMPORTANTE: Para correr tu código de Python, primero activa tu entorno copiando y pegando este comando:"
echo "source /workspace/mi_entorno/bin/activate"
echo "================================================"