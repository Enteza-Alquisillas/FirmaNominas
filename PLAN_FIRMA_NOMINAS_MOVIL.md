# Plan de desarrollo: Firma de nominas desde movil + insercion en PDF + subida a Odoo

## 1) Objetivo

Construir una solucion propia (software libre y controlada internamente) para que cada empleado pueda:

1. Abrir su nomina desde el movil mediante enlace personalizado.
2. Ver el PDF de su nomina.
3. Firmar en un canvas tactil.
4. Confirmar firma (aceptacion explicita).
5. Generar PDF firmado (insertando imagen de firma en el PDF original).
6. Subir automaticamente el PDF firmado a Odoo vinculado al empleado.
7. Guardar evidencia de auditoria (fecha/hora, IP, hash documento, etc.).

---

## 2) Alcance funcional (MVP)

### Incluye

- Portal web responsive para movil (sin app nativa).
- Enlace unico por empleado/nomina (token seguro con caducidad).
- Vista PDF en movil.
- Canvas para firma manuscrita.
- Insercion de firma en PDF (imagen PNG) con metadatos.
- Subida automatica a Odoo (`ir.attachment` sobre `hr.employee`).
- Registro de auditoria y estado de firma.
- Reenvio de enlace y recordatorios basicos.

### No incluye (fase posterior)

- Firma electronica avanzada con certificado cualificado.
- Firma biometrica pericial avanzada.
- Integracion SMS obligatoria (se puede agregar luego como 2FA).

---

## 3) Arquitectura recomendada

## 3.1 Componentes

1. **Generador de solicitudes de firma**
   - Recibe PDFs individuales ya generados por el sistema actual.
   - Crea una solicitud de firma por empleado y periodo.
   - Emite enlace unico con token.

2. **Portal movil de firma**
   - Pagina publica protegida por token.
   - Render del PDF + canvas de firma.
   - Boton confirmar firma.

3. **Servicio de sellado PDF**
   - Convierte canvas (base64 PNG) a imagen.
   - Inserta firma en coordenadas definidas del PDF.
   - Calcula hash SHA-256 del PDF firmado.

4. **Conector Odoo**
   - Sube PDF firmado como adjunto.
   - Vincula a `hr.employee`.
   - Opcional: vincular tambien a `hr.payslip` si existe.

5. **Auditoria y evidencias**
   - Guarda estados, eventos y metadatos de firma.
   - Exportable para RRHH.

## 3.2 Stack tecnico sugerido (libre)

- Backend API: **FastAPI** (Python 3.11+)
- Frontend movil: **Next.js** o React SPA (responsive)
- DB: **PostgreSQL**
- Almacenamiento: sistema de archivos local cifrado o MinIO
- PDF: **PyMuPDF** o **pypdf**
- Firmas imagen: Pillow
- Cola (opcional): RQ/Celery para procesos de lote
- Reverse proxy: Nginx con HTTPS

> Nota: Se puede integrar directamente en el repositorio actual o separar en microservicio.

---

## 4) Modelo de datos (minimo)

## 4.1 Tabla `signature_requests`

- `id` (uuid)
- `employee_id_odoo` (int)
- `worker_number` (text)
- `dni` (text)
- `employee_name` (text)
- `period_month` (int)
- `period_year` (int)
- `pdf_original_path` (text)
- `pdf_original_sha256` (text)
- `token_hash` (text)
- `token_expires_at` (timestamp)
- `status` (enum: pending, opened, signed, rejected, expired, uploaded_odoo, upload_error)
- `opened_at` (timestamp null)
- `signed_at` (timestamp null)
- `uploaded_at` (timestamp null)
- `odoo_attachment_id` (int null)
- `created_at` / `updated_at`

## 4.2 Tabla `signature_evidences`

- `id` (uuid)
- `request_id` (uuid fk)
- `event_type` (created, opened_link, signed, uploaded_odoo, error)
- `ip` (text)
- `user_agent` (text)
- `device_info` (text)
- `pdf_signed_sha256` (text null)
- `metadata_json` (jsonb)
- `created_at`

## 4.3 Tabla `signature_artifacts`

- `id` (uuid)
- `request_id` (uuid fk)
- `signature_png_path` (text)
- `pdf_signed_path` (text)
- `pdf_signed_sha256` (text)
- `created_at`

---

## 5) Flujo funcional extremo a extremo

1. Sistema actual divide nominas en PDF individual (`DNI-MM-AAAA.pdf`).
2. Operador RRHH pulsa "Crear solicitudes de firma".
3. Backend crea 1 registro por empleado y genera token seguro.
4. Se envia enlace por email/WhatsApp corporativo:
   - `https://tu-dominio/firma/<token>`
5. Empleado abre desde movil.
6. Ve su nomina PDF y canvas para firma.
7. Firma + checkbox de consentimiento + confirmar.
8. Backend:
   - valida token y estado,
   - guarda PNG de firma,
   - inserta firma en PDF,
   - calcula hash,
   - sube PDF firmado a Odoo,
   - registra evidencias,
   - cambia estado a `uploaded_odoo` (o `upload_error`).
9. RRHH consulta panel de estado y descarga reporte.

---

## 6) Diseño del enlace personalizado y seguridad

## 6.1 Token

- Token aleatorio criptografico (min 32 bytes).
- Solo guardar **hash del token** en BD (no token en claro).
- Caducidad recomendada: 7-15 dias.
- Uso unico para firma final (idempotencia controlada).

## 6.2 Controles

- HTTPS obligatorio.
- Rate limiting por IP/token.
- Bloqueo tras N intentos invalidos.
- CSRF y headers de seguridad.
- Sanitizacion de inputs.

## 6.3 Privacidad

- No exponer DNI completo en URL.
- No guardar password de Odoo en logs.
- Enmascarar DNI en vistas internas.

---

## 7) UI movil de firma

## 7.1 Pantalla unica (mobile-first)

Secciones:

1. Encabezado (empresa, empleado, periodo).
2. Visor PDF (iframe/canvas con zoom minimo).
3. Canvas de firma (alto aprox 180-240px).
4. Botones:
   - Limpiar firma
   - Confirmar firma
5. Checkbox legal:
   - "Declaro que he revisado esta nomina y firmo su recepcion."

## 7.2 Requisitos UX

- Funcionar en iOS Safari y Android Chrome.
- Tolerar rotacion vertical/horizontal.
- Soporte tactil y stylus.
- Bloquear confirmacion si el canvas esta vacio.

## 7.3 Implementacion canvas

- Libreria sugerida: `signature_pad`.
- Exportar PNG base64 (`toDataURL("image/png")`).
- Validacion de trazo minimo (n puntos/area minima).

---

## 8) Insercion de firma dentro del PDF

## 8.1 Estrategia

- Cargar PDF original.
- Definir coordenadas de firma por plantilla:
  - ejemplo: pagina 1, x=350, y=690, ancho=180, alto=60.
- Insertar PNG con transparencia.
- Agregar texto tecnico opcional:
  - "Firmado el DD/MM/AAAA HH:MM"
  - "IP: X.X.X.X"
- Guardar como nuevo PDF firmado.

## 8.2 Consideraciones

- Si hay distintas plantillas de nomina, crear perfil de coordenadas por empresa/centro.
- Mantener PDF original sin modificar.
- Calcular hash antes y despues.

---

## 9) Subida a Odoo tras firma

## 9.1 Modelo objetivo

`ir.attachment` con:

- `name`: `DNI-MM-AAAA-firmada.pdf`
- `type`: `binary`
- `datas`: base64(pdf_firmado)
- `res_model`: `hr.employee`
- `res_id`: `employee_id_odoo`
- `mimetype`: `application/pdf`
- `description`: `Nomina firmada MM/AAAA desde portal movil`

## 9.2 Politica de duplicados recomendada

- Si existe `DNI-MM-AAAA-firmada.pdf` para ese empleado:
  - por defecto: **replace** (actualizar)
  - alternativa: versionar con timestamp.

## 9.3 Estado final

- `uploaded_odoo` si correcto.
- `upload_error` con detalle si falla.

---

## 10) Endpoints API propuestos

## 10.1 Backoffice

- `POST /api/signature-requests/bulk-create`
  - input: lista de empleados/PDFs/periodo
  - output: solicitudes + links

- `GET /api/signature-requests`
  - filtros por estado/periodo

- `POST /api/signature-requests/{id}/resend`
  - reenvio enlace

## 10.2 Portal empleado

- `GET /api/public/sign/{token}`
  - valida token y devuelve metadata + URL temporal PDF

- `POST /api/public/sign/{token}/confirm`
  - body: `signature_png_base64`, `consent=true`
  - accion: insertar firma + subir Odoo + registrar evidencia

---

## 11) Requisitos legales y de evidencia (practicos)

- Registrar consentimiento expreso (checkbox + accion de firma).
- Registrar timestamp UTC + zona local.
- Guardar hash SHA-256 del PDF firmado.
- Guardar evidencia tecnica: IP, user-agent, evento.
- Mantener trazabilidad de version del documento firmado.

> Recomendacion: validar con asesoria laboral si en vuestro caso se requiere firma avanzada.

---

## 12) Plan de implementacion por fases

## Fase 1 - MVP funcional (2-4 semanas)

1. Tablas y modelos.
2. Generacion de solicitudes y token.
3. Pantalla movil con visor PDF + canvas.
4. Confirmacion firma + insercion en PDF.
5. Subida a Odoo + log de estado.
6. Panel RRHH basico (pendientes/firmadas/error).

## Fase 2 - Operacion

1. Reenvio y recordatorios.
2. Caducidad y renovacion de token.
3. Exportacion de evidencias (Excel/PDF).
4. Observabilidad (metricas y alertas).

## Fase 3 - Hardening

1. OTP email/SMS opcional.
2. Sellado de tiempo externo (si aplica).
3. Politicas de retencion y cifrado en reposo.

---

## 13) Pruebas obligatorias

## 13.1 Funcionales

- Link valido abre nomina correcta.
- Link expirado no permite firmar.
- Canvas vacio bloquea confirmacion.
- Firma genera PDF firmado.
- PDF firmado se sube a Odoo en empleado correcto.

## 13.2 Seguridad

- Token invalido denegado.
- Reintentos excesivos limitados.
- Sin fuga de datos sensibles en logs.

## 13.3 Compatibilidad movil

- iOS Safari (ultimas 2 versiones).
- Android Chrome (ultimas 2 versiones).

---

## 14) Integracion con el proyecto actual

## 14.1 Nuevos modulos sugeridos

- `core/signature_requests.py`
- `core/signature_pdf.py`
- `core/signature_delivery.py`
- `core/signature_audit.py`

## 14.2 Nuevos pasos en UI Streamlit

1. Paso 7: "Crear solicitudes de firma movil"
2. Paso 8: "Monitor de firma y subida Odoo"

## 14.3 Variables de entorno

- `SIGN_BASE_URL`
- `SIGN_TOKEN_TTL_HOURS`
- `SIGN_STORAGE_DIR`
- `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`

---

## 15) Criterios de aceptacion

Se considera listo cuando:

1. Cada empleado puede firmar desde movil con enlace unico.
2. La firma se incrusta en su PDF de nomina correctamente.
3. El PDF firmado se sube automaticamente a Odoo en su ficha.
4. Queda evidencia auditable de todo el proceso.
5. RRHH puede ver estados y detectar excepciones.

---

## 16) Decision recomendada

Implementar Fase 1 de inmediato con firma simple + evidencia robusta + subida automatica a Odoo.

Con esto tendreis una solucion utilizable en produccion rapidamente, con coste bajo, control total de datos y una base escalable para elevar nivel legal en fases siguientes.
