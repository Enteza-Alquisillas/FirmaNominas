# Roadmap — Enteza RRHH (Streamlit)

Planificación de mejoras ordenadas por impacto y esfuerzo.
Fecha de referencia: mayo 2026.

---

## Estado actual

La aplicación está en producción en `https://rrhh.enteza.es` con:

- Procesamiento de PDF y Excel de nóminas ✅
- Emparejamiento automático con empleados Odoo ✅
- Generación de asientos contables ✅
- Subida de adjuntos a Odoo ✅
- Firma digital móvil con token seguro ✅
- Entrega de enlace por WhatsApp Web ✅
- HTTPS con Let's Encrypt ✅

---

## Fase 1 — Estabilidad y operación 24/7
> Esfuerzo bajo · Impacto alto · Plazo recomendado: 2-4 semanas

### 1.1 Renovación automática de certificado SSL

El certificado de Let's Encrypt caduca cada 90 días. Sin automatización hay riesgo de caída del HTTPS y los enlaces WhatsApp dejarían de funcionar en móvil.

**Solución**: cron en el VPS que renueva el certificado y recarga nginx sin downtime.

```bash
# Cron propuesto (ejecutar como root o con sudo)
0 3 * * 1 certbot renew --quiet && \
  cp /etc/letsencrypt/live/rrhh.enteza.es/fullchain.pem /ruta/proyecto/deploy/certs/ && \
  cp /etc/letsencrypt/live/rrhh.enteza.es/privkey.pem /ruta/proyecto/deploy/certs/ && \
  docker compose -f /ruta/proyecto/docker-compose.yml restart nginx
```

---

### 1.2 Backup automático de datos

La carpeta `data/` contiene la BD SQLite de firmas, los PDFs originales y los PDFs firmados. Es el único dato que no está en Odoo y si se pierde no hay recuperación.

**Solución**: script diario que comprime y guarda fuera del VPS.

```bash
# Backup diario a las 2:00
0 2 * * * tar -czf /home/enteza/backups/rrhh_$(date +%F).tar.gz \
  /ruta/proyecto/data /ruta/proyecto/.env.local && \
  find /home/enteza/backups -name "rrhh_*.tar.gz" -mtime +30 -delete
```

Opcional: sincronizar con un bucket S3/Backblaze para backup offsite.

---

### 1.3 Alertas de salud del servicio

Si el contenedor cae nadie se entera hasta que alguien intenta usar la app.

**Solución**: script de health-check que envía un mensaje si el servicio no responde.

- Usar UptimeRobot (gratuito) apuntando a `https://rrhh.enteza.es/_stcore/health`
- Notificación por email o Telegram si cae

---

## Fase 2 — Mejora del flujo de firma
> Esfuerzo medio · Impacto alto · Plazo recomendado: 4-6 semanas

### 2.1 Envío WhatsApp por API oficial (Evolution API)

El sistema actual abre WhatsApp Web y el operador tiene que pulsar "Enviar" manualmente para cada empleado. Con la instancia de Evolution API que ya tienes en el VPS, el envío puede ser completamente automático.

**Flujo propuesto**:
1. Se generan las solicitudes de firma (igual que ahora)
2. La app llama a Evolution API con el teléfono y el mensaje
3. El mensaje llega al empleado sin intervención manual
4. El estado pasa a "enviado" automáticamente

**Impacto**: elimina el proceso manual para empresas con 50+ empleados.

---

### 2.2 Recordatorio automático a empleados que no han firmado

Actualmente no hay seguimiento de quién ha firmado y quién no, salvo consultar la tabla de estado.

**Propuesta**:
- Tras N días sin firma, reenviar el enlace automáticamente (o mostrar en UI los pendientes destacados)
- Panel de estado con semáforo: pendiente / enlace abierto / firmado / subido a Odoo
- El dato ya existe en SQLite (`signature_events`), solo falta exponerlo mejor en la UI

---

### 2.3 Página de firma mejorada para móvil

La página de firma actual es funcional pero básica. Mejoras de UX:

- Mostrar nombre del empleado y periodo de forma clara antes del canvas
- Previsualización del PDF en móvil (el iframe actual no funciona bien en todos los navegadores móviles)
- Confirmación visual clara tras firmar ("Tu firma ha sido registrada correctamente")
- Soporte para orientación horizontal en el canvas de firma

---

## Fase 3 — Funcionalidades nuevas
> Esfuerzo medio-alto · Impacto medio · Plazo recomendado: 6-10 semanas

### 3.1 Multi-empresa

Ahora la app conecta con un único Odoo. Si Enteza gestiona varias empresas (o en el futuro se usa para otros clientes), se necesita seleccionar la empresa al inicio de cada sesión.

**Propuesta**:
- Selector de empresa en sidebar con configuraciones pre-cargadas
- Cada empresa con sus propias credenciales Odoo y su propia carpeta de datos
- `.env.local` extiende con secciones por empresa o se usa un fichero YAML de configuración

---

### 3.2 Dashboard de histórico de periodos

Actualmente cada vez que se procesa un periodo se parte de cero. No hay visión histórica.

**Propuesta**:
- Tabla de periodos procesados con estado (procesado, contabilizado, todos firmados)
- Acceso a los PDFs firmados de periodos anteriores
- Estadísticas: % de empleados que firman, tiempo medio de firma

---

### 3.3 Importación directa desde Odoo (sin subir PDF manualmente)

Ahora el operador descarga el PDF de nóminas desde el sistema de nóminas externo y lo sube manualmente. Si las nóminas se generan en Odoo o hay un sistema con API, se podría automatizar la carga.

**Propuesta**: botón "Importar desde Odoo" que recupera los adjuntos del periodo seleccionado directamente.

---

## Fase 4 — Calidad técnica
> Esfuerzo bajo-medio · Sin impacto visible para el usuario · Plazo: paralelo a otras fases

### 4.1 Suite de tests ampliada

Los tests actuales cubren casos básicos. Añadir:
- Tests de integración contra un Odoo de pruebas
- Tests end-to-end del flujo de firma (con Playwright)
- Test del proceso de renovación SSL

### 4.2 Variables de entorno documentadas

Crear `.env.local.example` con todas las variables necesarias comentadas, para facilitar nuevos despliegues.

### 4.3 Logs estructurados

Añadir logging a fichero (rotativo) para poder diagnosticar errores en producción sin tener que conectarse al contenedor.

---

## Priorización recomendada

| # | Tarea | Fase | Esfuerzo | Impacto |
|---|-------|------|----------|---------|
| 1 | Renovación automática SSL | 1.1 | Bajo | Crítico |
| 2 | Backup automático `data/` | 1.2 | Bajo | Crítico |
| 3 | UptimeRobot health-check | 1.3 | Mínimo | Alto |
| 4 | Envío WhatsApp automático (Evolution API) | 2.1 | Medio | Alto |
| 5 | Panel de pendientes de firma mejorado | 2.2 | Medio | Alto |
| 6 | UX página de firma móvil | 2.3 | Medio | Medio |
| 7 | Multi-empresa | 3.1 | Alto | Medio |
| 8 | Dashboard histórico | 3.2 | Medio | Medio |
| 9 | Logs estructurados | 4.3 | Bajo | Medio |

---

## Notas sobre la Evolution API

El VPS ya tiene una instancia de Evolution API corriendo (`evolution_evolution`). Antes de implementar el envío automático de WhatsApp (fase 2.1) hay que:

1. Conectar un número de WhatsApp Business a Evolution API
2. Revisar los límites de la API (mensajes por día, formato de teléfonos)
3. Decidir si se usa un número corporativo dedicado o el número actual del operador

El código de la app ya tiene toda la lógica de construcción del mensaje y normalización de teléfonos — solo habría que añadir la llamada HTTP a Evolution API en lugar de abrir WhatsApp Web.

---

*Documento generado en mayo 2026. Revisar prioridades trimestralmente según uso real de la aplicación.*
