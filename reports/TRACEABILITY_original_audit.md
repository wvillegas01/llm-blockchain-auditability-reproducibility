# Trazabilidad de auditoria de datos

## Proyecto

Blockchain aplicado a auditabilidad de decisiones generadas por LLM.

## Objetivo de esta fase

Auditar las fuentes conversacionales disponibles en el espacio de trabajo experimental local del proyecto.

para determinar que datasets pueden utilizarse como base experimental del framework de auditabilidad criptografica.

## Fecha

2026-06-03

## Raiz de destino

Espacio de trabajo experimental local del proyecto. En esta version publica, las rutas locales originales fueron omitidas deliberadamente.

## Artefactos generados

- `00_inventory/audit_comunicacion_inventory.csv`: inventario completo de archivos perfilados.
- `02_audit_outputs/audit_comunicacion_rollup.csv`: resumen agregado por dataset.
- `03_reports/auditoria_datos_comunicacion_para_auditabilidad.md`: informe metodologico inicial.
- `01_scripts/audit_comunicacion_datasets.py`: script usado para generar la auditoria.
- `04_logs/audit_execution_log.md`: registro breve de ejecucion y decisiones.

## Decision preliminar

- Dataset principal recomendado: `lmsys-chat-1m`.
- Dataset de validacion externa recomendado: `WildChat`.
- Dataset complementario para preferencias humanas: `Chatbot_arena`.
- Datasets secundarios/control: `UltraChat`, `DailyDialog`, `Empathetic`, `Reddit`, `MultiWOZ`, `ConversationChronicles`.

## Razonamiento

La seleccion prioriza fuentes con conversaciones LLM reales, identificadores de conversacion, campos de modelo, metadatos de moderacion y, cuando esta disponible, metadata temporal. Esto permite construir registros auditables con hashes reproducibles sin almacenar texto original en el ledger.

## Siguiente fase sugerida

Construir una auditoria de normalizacion para `lmsys-chat-1m`, `WildChat` y `Chatbot_arena`, con conteos reales de turnos, duplicados, distribucion de modelos, disponibilidad temporal y campos candidatos para `AuditRecord`.
