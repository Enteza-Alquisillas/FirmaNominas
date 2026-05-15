# PRP-001: Firma de nomina movil con subida automatica a Odoo

> **Estado**: PENDIENTE
> **Fecha**: 2026-05-15
> **Proyecto**: nominas_odoo_streamlit

---

## Objetivo

Construir un portal movil de firma para que cada empleado firme su nomina desde un enlace personalizado, incrustar esa firma en el PDF de nomina en coordenadas fijas predefinidas y subir automaticamente el PDF firmado a Odoo en la ficha correcta del empleado.

## Por Que

| Problema | Solucion |
|----------|----------|
| El proceso actual genera y sube nominas, pero no permite firma del empleado desde movil ni confirmacion directa en el documento. | Crear flujo de firma movil con token seguro, canvas tactil, insercion en PDF y subida automatica a Odoo. |

**Valor de negocio**: reducir gestion manual RRHH, acelerar confirmacion de recepcion de nominas, mejorar trazabilidad legal operativa y disponibilidad de nomina firmada en Odoo.

## Que

### Criterios de Exito
- [ ] RRHH puede crear solicitudes de firma por lote para las nominas del mes y obtener enlaces unicos por empleado.
- [ ] Cada empleado puede abrir su enlace en movil, ver su PDF y firmar en canvas tactil.
- [ ] La firma se incrusta en el PDF en las coordenadas definidas y el PDF firmado se sube a Odoo.
- [ ] El sistema muestra estado por solicitud (`pending`, `opened`, `signed`, `uploaded_odoo`, `error`) con filtro por mes/ano.
- [ ] En caso de error de subida a Odoo, la solicitud no se pierde y permite reintento controlado.

### Comportamiento Esperado
RRHH procesa PDF/Excel como hoy, empareja empleados con Odoo y genera PDFs individuales. Luego inicia "Crear solicitudes de firma movil" para el periodo. El sistema crea un token por empleado y enlace de firma. El empleado abre el enlace en su telefono, visualiza su nomina, firma en canvas, acepta consentimiento y confirma. Backend valida token, incrusta firma en el PDF original usando coordenadas fijas predefinidas, sube el PDF firmado a Odoo (`ir.attachment` en `hr.employee`) y actualiza estado. RRHH consulta progreso y reintenta errores puntuales.

---

## Contexto

### Referencias
- `app.py` - flujo actual de procesamiento, matching y subida a Odoo.
- `core/odoo_attachments.py` - patron de subida de adjuntos a `ir.attachment`.
- `core/odoo_client.py` - XML-RPC wrapper y manejo de errores Odoo.
- `core/state.py` - persistencia de artefactos Streamlit en sesion.
- `PLAN_FIRMA_NOMINAS_MOVIL.md` - blueprint funcional detallado de la solucion.

### Arquitectura Propuesta (adaptada al proyecto actual)
```
nominas_odoo_streamlit/
├── app.py
├── core/
│   ├── signature_tokens.py          # token seguro, expiracion, validacion
│   ├── signature_repository.py      # persistencia requests/artifacts
│   ├── signature_pdf.py             # insercion de PNG en PDF
│   ├── signature_service.py         # orquestacion end-to-end firma
│   ├── signature_public_api.py      # endpoints de portal movil
│   └── odoo_attachments.py          # reutilizado para subida final
├── data/
│   └── signatures.db                # SQLite local para MVP
└── web-sign/
    └── (frontend movil)             # pagina publica de firma canvas
```

### Modelo de Datos (MVP local)
```sql
CREATE TABLE signature_requests (
  id TEXT PRIMARY KEY,
  employee_id_odoo INTEGER NOT NULL,
  worker_number TEXT,
  dni TEXT,
  employee_name TEXT,
  period_month INTEGER NOT NULL,
  period_year INTEGER NOT NULL,
  pdf_original_path TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  token_expires_at TEXT NOT NULL,
  status TEXT NOT NULL,
  opened_at TEXT,
  signed_at TEXT,
  uploaded_at TEXT,
  odoo_attachment_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE signature_artifacts (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  signature_png_path TEXT NOT NULL,
  pdf_signed_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (request_id) REFERENCES signature_requests(id)
);
```

---

## Blueprint (Assembly Line)

> IMPORTANTE: Solo definir FASES. Las subtareas se generan al entrar a cada fase.

### Fase 1: Base tecnica de firma y persistencia
**Objetivo**: Crear los modulos base de token, repositorio local (SQLite), modelos y servicio de firma sin tocar funcionalidades existentes.
**Validacion**: Se puede crear y consultar solicitudes de firma con estado `pending` y token con expiracion.

### Fase 2: Portal movil publico con canvas
**Objetivo**: Implementar UI movil (pagina publica) para abrir enlace, ver PDF y firmar en canvas con consentimiento.
**Validacion**: Desde movil se puede completar firma y enviar payload con imagen PNG base64.

### Fase 3: Insercion de firma en PDF
**Objetivo**: Incrustar firma manuscrita en PDF en coordenadas fijas predefinidas y guardar documento firmado.
**Validacion**: Se genera PDF firmado y la firma aparece en la zona prevista de firma manual.

### Fase 4: Subida automatica a Odoo
**Objetivo**: Subir PDF firmado a `ir.attachment` de `hr.employee` y actualizar estado final.
**Validacion**: Solicitudes firmadas quedan en `uploaded_odoo` con `odoo_attachment_id` o `error` recuperable.

### Fase 5: Integracion en app de RRHH
**Objetivo**: Agregar pasos en Streamlit para crear solicitudes, ver estados y reintentar errores.
**Validacion**: RRHH puede operar todo el ciclo sin perder flujo actual de nomina/asiento/subida.

### Fase 6: Validacion Final
**Objetivo**: Flujo end-to-end estable y usable en produccion controlada.
**Validacion**:
- [ ] `python -m pytest tests/` pasa
- [ ] Flujo completo de firma movil funciona en iOS/Android
- [ ] PDF firmado se adjunta en empleado correcto de Odoo
- [ ] Criterios de exito cumplidos

---

## 🧠 Aprendizajes (Self-Annealing / Neural Network)

### [2026-05-15]: Control de nombres PDF reales para Odoo
- **Error**: Inferir filename en matching causaba desalineacion con nombre real del split.
- **Fix**: Persistir `worker_pdf_filenames` en estado y usar filename real en cargas.
- **Aplicar en**: Cualquier flujo posterior que relacione empleado ↔ archivo generado.

---

## Gotchas

- [ ] Tokens nunca deben guardarse en claro, solo hash.
- [ ] El canvas puede enviar imagen vacia; validar trazo minimo en frontend y backend.
- [ ] Coordenadas de firma pueden variar segun plantilla PDF; parametrizar por empresa.
- [ ] No bloquear el hilo principal en Streamlit con procesos largos de lote.
- [ ] Cualquier error Odoo debe ser reintentable sin perder el PDF firmado ya generado.

## Anti-Patrones

- NO romper el flujo actual de procesamiento y subida de nominas.
- NO exponer DNI completo ni credenciales en logs.
- NO depender de `st.secrets` exclusivamente (usar `.env.local` ya implementado).
- NO insertar firma sobrescribiendo el PDF original.
- NO marcar como firmado si la subida a Odoo falla sin dejar estado de error explícito.

---

*PRP pendiente aprobación. No se ha implementado esta feature todavía.*
