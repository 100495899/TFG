# Exploiting Retrieval Latency Side-Channels in RAG Systems

Este repositorio contiene el código desarrollado para estudiar canales laterales temporales en sistemas RAG y automatizar su evaluación mediante una herramienta web de auditoría.

## Herramienta de auditoría

La carpeta [`Auditoria_RAG_Timing`](Auditoria_RAG_Timing/) contiene la aplicación completa. Incluye el frontend, la API backend, el worker encargado de ejecutar las pruebas, PostgreSQL, Redis y la configuración de Docker Compose.

En su [`README`](Auditoria_RAG_Timing/README.md) se explican los requisitos, la configuración del entorno y los comandos necesarios para levantar y usar la herramienta.

## Scripts de experimentación

La carpeta [`Script_PoC`](Script_PoC/) contiene los scripts empleados durante la fase experimental del proyecto. Incluye las pruebas de recuperación vectorial, la evaluación del pipeline RAG, los experimentos con caché y los scripts auxiliares usados para preparar consultas y analizar resultados.

Estos archivos recogen la evolución experimental del trabajo y no son necesarios para ejecutar la herramienta web.

## RAG externo de prueba

La carpeta [`Mock_RAG_RunPod`](Mock_RAG_RunPod/) contiene un sistema RAG desplegable como servicio HTTP externo. Se usó como target controlado para validar la herramienta en un entorno remoto. Su configuración y ejecución se describen en el README incluido en esa carpeta.
