# Plan de producto: SaaS multitenant de nóminas para gestorías

Documento de planificación para iniciar un proyecto nuevo en Claude Code.  
Basado en el aprendizaje del desarrollo de **Enteza RRHH** (mayo 2026).

---

## 1. Visión del producto

Una plataforma SaaS B2B donde **gestorías** son el cliente pagador y sus **empresas-cliente** son los usuarios finales. La gestoría contrata el servicio, añade sus empresas, sube las nóminas de cada una y los empleados las reciben y firman desde el móvil.

```
Gestoría (tenant) ──► Empresa A ──► Empleados A
                  └──► Empresa B ──► Empleados B
                  └──► Empresa C ──► Empleados C
```

### Propuesta de valor por perfil

| Perfil | Problema actual | Lo que obtiene |
|--------|----------------|----------------|
| Gestoría | Envía PDFs por email, no sabe si los han recibido | Panel único, firmas auditables, menos llamadas |
| Empresa cliente | Empleados pierden nóminas, sin firma legal | Historial digital, firma válida, sin papel |
| Empleado | Recibe PDF por email o en papel | Enlace WhatsApp, firma en 30 segundos desde el móvil |

---

## 2. Modelo de negocio

### Estructura de tenants

```
SaaS Platform
├── Gestoría 1 (tenant)
│   ├── Empresa A (sub-tenant)
│   │   └── Empleados A
│   ├── Empresa B
│   └── Empresa C
├── Gestoría 2 (tenant)
│   └── ...
```

### Planes sugeridos

| Plan | Precio/mes | Empresas | Empleados | Firmas | WhatsApp |
|------|-----------|----------|-----------|--------|----------|
| Starter | 49 € | 3 | 50 | ✓ | Manual |
| Pro | 149 € | 15 | 300 | ✓ | Automático |
| Business | 399 € | ilimitadas | 1.500 | ✓ | Automático + API |
| Enterprise | custom | ilimitadas | ilimitados | ✓ | White-label |

### Integraciones opcionales de pago

- Conexión Odoo (subida de adjuntos + asiento contable): +29 €/mes por empresa
- API REST para integración con software propio: Plan Business en adelante

---

## 3. Stack tecnológico

### Decisión de stack: por qué no Streamlit para el SaaS

Streamlit es ideal para herramientas internas mono-empresa. Para un SaaS multitenant necesitamos:
- Autenticación robusta con múltiples roles
- Aislamiento de datos por tenant (Row Level Security)
- UI reactiva y móvil-first para empleados
- Escalabilidad horizontal
- Webhooks, colas de trabajo, jobs programados

### Stack seleccionado (2026)

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Framework | **Next.js 16** + React 19 + TypeScript | App Router, Server Actions, RSC |
| Estilos | **Tailwind CSS 4** | Utility-first, mobile-first |
| Base de datos | **Supabase** (PostgreSQL) | RLS nativo, Auth, Storage, Realtime |
| Auth | **Supabase Auth** | Email/password + OAuth, JWT, RLS integrado |
| Procesamiento PDF | **Python microservicio** (FastAPI + PyMuPDF) | Reutilizar lógica validada de Enteza RRHH |
| Procesamiento Excel | **Python microservicio** (FastAPI + openpyxl) | Idem |
| Colas de trabajo | **Supabase pg_cron + Edge Functions** | Jobs programados sin infra adicional |
| WhatsApp | **Evolution API** | Instancia self-hosted, ya probada |
| Email transaccional | **Resend** | API simple, alta entregabilidad |
| Pagos | **Stripe** | Subscripciones, webhooks, portal de cliente |
| Firma canvas | **react-signature-canvas** | Equivalente a streamlit-drawable-canvas |
| PDF viewer | **react-pdf** | Compatible iOS Safari y Android Chrome |
| Validación | **Zod** | Schema-first, integrado con Next.js |
| Estado cliente | **Zustand** | Ligero, sin boilerplate |
| Testing | **Playwright** + **Vitest** | E2E + unitarios |
| Deploy | **VPS propio** (Docker) o **Vercel** + Supabase Cloud | Flexible |
| Monitorización | **Sentry** + **UptimeRobot** | Errores + disponibilidad |

### Arquitectura de servicios

```
┌─────────────────────────────────────────────┐
│  Next.js App (Vercel / VPS)                 │
│  ├── /app/(tenant)/dashboard                │
│  ├── /app/(tenant)/empresas                 │
│  ├── /app/(tenant)/nominas                  │
│  ├── /app/sign/[token]  ← página pública    │
│  └── /api/webhooks/stripe                   │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼───┐          ┌──────▼──────┐
│Supabase│          │Python Worker│
│  DB    │          │  (FastAPI)  │
│  Auth  │          │  PDF split  │
│ Storage│          │  Excel parse│
│  RLS   │          │  PDF sign   │
└───────┘          └─────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
        ┌─────▼────┐         ┌──────▼──────┐
        │Evolution │         │  Odoo XMLRPC│
        │   API    │         │  (opcional) │
        │(WhatsApp)│         └─────────────┘
        └──────────┘
```

---

## 4. Modelo de datos (PostgreSQL + Supabase RLS)

### Tablas principales

```sql
-- Tenants (gestorías)
tenants (
  id uuid PRIMARY KEY,
  name text,
  slug text UNIQUE,          -- para URLs: app.saas.com/t/gestoría-perez
  plan text,                 -- starter | pro | business | enterprise
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz
)

-- Usuarios de la gestoría
tenant_users (
  id uuid PRIMARY KEY,
  tenant_id uuid REFERENCES tenants,
  user_id uuid REFERENCES auth.users,
  role text,                 -- owner | admin | operator | viewer
  created_at timestamptz
)

-- Empresas cliente de la gestoría
companies (
  id uuid PRIMARY KEY,
  tenant_id uuid REFERENCES tenants,
  name text,
  cif text,
  odoo_url text,             -- opcional
  odoo_db text,
  odoo_user text,
  odoo_password_enc text,    -- cifrado con clave del tenant
  whatsapp_instance text,    -- nombre instancia Evolution API
  created_at timestamptz
)

-- Periodos de nómina
payroll_periods (
  id uuid PRIMARY KEY,
  company_id uuid REFERENCES companies,
  tenant_id uuid REFERENCES tenants,
  month int,
  year int,
  status text,               -- processing | ready | sending | completed
  pdf_original_path text,    -- Supabase Storage
  excel_path text,
  created_at timestamptz,
  UNIQUE(company_id, month, year)
)

-- Nóminas individuales
payslips (
  id uuid PRIMARY KEY,
  period_id uuid REFERENCES payroll_periods,
  tenant_id uuid REFERENCES tenants,
  worker_number text,
  employee_name text,
  dni text,
  pdf_path text,             -- Supabase Storage
  pdf_signed_path text,
  employee_id_odoo int,
  odoo_attachment_id int,
  sign_token text UNIQUE,
  sign_token_expires_at timestamptz,
  sign_status text,          -- pending | link_sent | opened | signed | uploaded | error
  signed_at timestamptz,
  employee_phone text,
  whatsapp_sent_at timestamptz,
  created_at timestamptz
)

-- Eventos de auditoría
payslip_events (
  id bigserial PRIMARY KEY,
  payslip_id uuid REFERENCES payslips,
  tenant_id uuid REFERENCES tenants,
  event text,                -- created | link_sent | opened | signed | uploaded | error
  metadata jsonb,
  created_at timestamptz
)

-- Mapeo de cuentas contables por empresa
accounting_mappings (
  id uuid PRIMARY KEY,
  company_id uuid REFERENCES companies,
  tenant_id uuid REFERENCES tenants,
  worker_number text,
  cuenta_sueldos text,
  cuenta_ss_empresa text,
  cuenta_remuneraciones text,
  cuenta_irpf text,
  cuenta_ss_acreedora text,
  partner_odoo text,
  updated_at timestamptz
)
```

### RLS: aislamiento total entre tenants

```sql
-- Ejemplo: companies solo visible para el tenant propietario
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant isolation" ON companies
  USING (tenant_id = (
    SELECT tenant_id FROM tenant_users
    WHERE user_id = auth.uid()
    LIMIT 1
  ));
```

Aplicar la misma política a: `companies`, `payroll_periods`, `payslips`, `payslip_events`, `accounting_mappings`.

---

## 5. Lecciones aprendidas de Enteza RRHH (críticas para el nuevo desarrollo)

### 5.1. Procesamiento de PDF (PyMuPDF)

- El sistema de coordenadas usa **puntos** (1 cm = 28.35 pt), eje Y crece **hacia abajo**.
- `find_anchor_below_recibi()` busca el texto "Recibí/Recibi/RECIBI" como ancla de la firma — reutilizar.
- Al dividir el PDF en páginas individuales usar `pypdf.PdfWriter` página a página, no `fitz` para el split (evita problemas con PDFs protegidos).
- Nombre de archivo: `{DNI}-{MM}-{YYYY}.pdf`. Si no hay DNI, fallback a `trabajador_{n_trabajador:03d}-{MM}-{YYYY}.pdf`.
- Detectar duplicados de nombre con contador: `{stem}_2.pdf`, `{stem}_3.pdf`.

### 5.2. Procesamiento de Excel de nóminas

- El Excel tiene bloques separados por centros de trabajo: `Centro: NOMBRE_CENTRO`. El bloque `Centro: TOTAL EMPRESA` es un resumen — **excluirlo siempre**.
- Las cabeceras de empleado tienen formato `"002 - NOMBRE APELLIDOS"` → regex `^\s*(\d+)\s*-\s*(.+?)\s*$`.
- Las columnas que empiezan por "TOTAL" en la cabecera son agregados — **saltarlas**.
- Los importes españoles usan coma decimal y punto millar: `"1.234,56"` → `Decimal("1234.56")`. Usar `str.replace(".", "").replace(",", ".")` antes de `Decimal()`.
- Conceptos clave a extraer: `total_bruto`, `total_neto`, `descuento_irpf`, `ss_empresa`, `coste_tc1`, `embargo_juzgado`, `total_indemniz_inss`, `valores_especie_autonomo`.

### 5.3. Asiento contable para Odoo

- **Un asiento por centro de trabajo**, nunca uno global. Filtrar `"TOTAL" in center.upper()`.
- El TC1 (Seguridad Social acreedora) se agrega en una sola línea por centro cuando `aggregate_ss=True`.
- **Etiquetas fiscales Modelo 111**:
  - Líneas 640xxx (sueldos): `tax_tag_ids = [(6, 0, [tag_mod111_02_id])]`
  - Líneas 475xxxxx (IRPF): `tax_line_id = irpf_tax_id` + `tax_tag_ids = [(6, 0, [tag_mod111_03_id])]`
  - Buscar el impuesto: `account.tax` where `name ilike 'Retenciones IRPF'` and `type_tax_use = 'none'`
  - Buscar los tags: `account.account.tag` where `name = 'mod111[02]'` / `'mod111[03]'`
- **Resolución de cuentas contables** en Odoo (fallback progresivo):
  1. Búsqueda exacta por código
  2. Si código empieza por `4651`: buscar prefijo `4650%` (cuenta genérica de remuneraciones)
  3. Fallback: recortar dígito a dígito por la derecha hasta encontrar coincidencia
  4. Cachear resultados de búsqueda por prefijo para no repetir llamadas XML-RPC

### 5.4. Integración Odoo XML-RPC

- Endpoints: `/xmlrpc/2/common` (auth) y `/xmlrpc/2/object` (operaciones).
- Adjuntos al empleado: modelo `ir.attachment`, campos `res_model="hr.employee"`, `res_id=employee_id`, `datas=base64_bytes`.
- **NO usar** `datas_fname` — no existe en todas las versiones de Odoo 15.
- Control de duplicados: buscar por `(res_model, res_id, name)` antes de crear.
- Para eliminar adjunto sin firma tras subir el firmado: `execute_kw("ir.attachment", "unlink", [[id]])`.
- El campo DNI en `hr.employee` suele ser `identification_id` pero puede variar — ofrecer selector al usuario.
- Campos candidatos de número de trabajador: `barcode`, `employee_number`, `registration_number`, `x_num_trabajador`, `x_studio_num_trabajador`.

### 5.5. Flujo de firma digital

- Generar token seguro con `secrets.token_urlsafe(32)`, guardar solo el hash (`hashlib.sha256`).
- URL pública: `https://dominio.com/sign?token=TOKEN_ORIGINAL` (no el hash).
- TTL configurable (default 10 días). Comprobar expiración en cada acceso.
- Canvas de firma: **520×220 px** es buen balance para móvil y desktop.
- Insertar firma en PDF con `fitz` (PyMuPDF): buscar ancla "Recibí", offset `-2cm` horizontal y `-0.8cm` vertical respecto al ancla.
- Tras subir el PDF firmado: **eliminar el PDF sin firmar** del mismo empleado en Odoo.
- El nombre del firmado: `{stem_original}-firmada.pdf`. Para encontrar el sin firmar: quitar `-firmada` del stem.

### 5.6. WhatsApp (Evolution API)

- La instancia debe tener un número de WhatsApp Business conectado.
- Endpoint: `POST /message/sendText/{instance}` con body `{ "number": "+34XXXXXXXXX", "text": "..." }`.
- Normalizar teléfonos: quitar espacios, guiones, paréntesis. Añadir `+34` si no tiene prefijo internacional.
- El mensaje debe incluir el enlace de firma completo con `https://` — WhatsApp solo hace preview de HTTPS.
- WhatsApp Web manual (fallback): construir URL `https://wa.me/{phone}?text={encoded_message}`.

### 5.7. Infraestructura y deploy

- **HTTPS obligatorio** para que los enlaces WhatsApp sean clicables en móvil.
- Let's Encrypt con nginx en Docker: parar el contenedor nginx antes de `certbot renew --standalone`, copiar `.pem` a `deploy/certs/`, arrancar nginx. Automatizar con cron (lunes y jueves 3:00).
- **`restart: unless-stopped`** en Docker Compose garantiza reinicio automático si el proceso falla.
- Health check: `GET /_stcore/health` para Streamlit, `/health` o `/api/health` para Next.js.
- Volumen persistente en Docker: montar `./data` en `/app/data` para SQLite y PDFs.
- Para Supabase Storage: usar buckets privados con URLs firmadas (`createSignedUrl`) para descargas.

---

## 6. Estructura del proyecto Next.js

```
saas-nominas/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   ├── register/page.tsx
│   │   │   └── layout.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx           ← sidebar + navbar con tenant
│   │   │   ├── dashboard/page.tsx   ← resumen del periodo actual
│   │   │   ├── empresas/
│   │   │   │   ├── page.tsx         ← listado de empresas
│   │   │   │   └── [id]/page.tsx    ← detalle empresa
│   │   │   ├── nominas/
│   │   │   │   ├── page.tsx         ← periodos
│   │   │   │   └── [periodId]/
│   │   │   │       ├── page.tsx     ← estado por empleado (semáforo)
│   │   │   │       ├── upload/page.tsx
│   │   │   │       ├── match/page.tsx
│   │   │   │       └── accounting/page.tsx
│   │   │   └── configuracion/page.tsx
│   │   ├── sign/
│   │   │   └── [token]/page.tsx     ← página pública de firma (móvil)
│   │   └── api/
│   │       ├── webhooks/stripe/route.ts
│   │       └── webhooks/evolution/route.ts
│   │
│   ├── features/
│   │   ├── payroll/
│   │   │   ├── components/
│   │   │   │   ├── PeriodUploader.tsx
│   │   │   │   ├── EmployeeStatusTable.tsx   ← semáforo
│   │   │   │   ├── AccountingPanel.tsx
│   │   │   │   └── MatchingPanel.tsx
│   │   │   ├── actions/
│   │   │   │   ├── upload-payroll.ts         ← Server Action
│   │   │   │   ├── process-payroll.ts        ← llama al worker Python
│   │   │   │   └── send-signatures.ts
│   │   │   └── types.ts
│   │   ├── signing/
│   │   │   ├── components/
│   │   │   │   ├── SignatureCanvas.tsx
│   │   │   │   └── PdfViewer.tsx
│   │   │   └── actions/
│   │   │       └── submit-signature.ts
│   │   ├── companies/
│   │   ├── auth/
│   │   └── billing/
│   │
│   ├── shared/
│   │   ├── components/
│   │   │   ├── ui/                  ← shadcn/ui components
│   │   │   └── layout/
│   │   ├── lib/
│   │   │   ├── supabase/
│   │   │   │   ├── client.ts
│   │   │   │   ├── server.ts
│   │   │   │   └── middleware.ts
│   │   │   ├── odoo/
│   │   │   │   ├── client.ts        ← XML-RPC wrapper (portar de Python)
│   │   │   │   └── accounting.ts    ← lógica de asientos
│   │   │   └── evolution/
│   │   │       └── client.ts        ← WhatsApp API
│   │   └── types/
│   │       └── database.ts          ← tipos generados por Supabase
│   │
├── python-worker/                   ← microservicio Python
│   ├── main.py                      ← FastAPI
│   ├── core/
│   │   ├── payroll_pdf.py           ← REUTILIZAR de Enteza RRHH
│   │   ├── payroll_excel.py         ← REUTILIZAR de Enteza RRHH
│   │   ├── signature_pdf.py         ← REUTILIZAR de Enteza RRHH
│   │   └── utils.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── supabase/
│   ├── migrations/
│   │   ├── 001_tenants.sql
│   │   ├── 002_companies.sql
│   │   ├── 003_payslips.sql
│   │   ├── 004_rls_policies.sql
│   │   └── 005_functions.sql
│   └── seed.sql
│
├── docker-compose.yml
├── .env.local.example
└── CLAUDE.md                        ← instrucciones para el agente
```

---

## 7. Flujo completo del producto

### Flujo operario de gestoría

```
1. Login → selecciona empresa cliente
2. Sube PDF de nóminas + Excel de detalle → procesa el worker Python
3. Revisa tabla de empleados detectados
4. (Opcional) Conecta con Odoo → empareja empleados automáticamente
5. (Opcional) Ajusta mapeo de cuentas contables
6. Envía solicitudes de firma → WhatsApp automático por Evolution API
7. Panel semáforo en tiempo real: pendiente / enlace abierto / firmado / subido a Odoo
8. (Opcional) Crea asiento contable en Odoo con un clic
9. Descarga ZIP con nóminas + Excel de importación + log
```

### Flujo empleado

```
1. Recibe WhatsApp con enlace
2. Abre enlace en móvil → página de firma (sin login)
3. Ve la nómina en PDF
4. Dibuja firma en canvas
5. Confirma → PDF firmado se genera y sube a Odoo
6. Pantalla de confirmación
```

### Flujo automático de recordatorios

```
pg_cron cada día a las 9:00 →
  SELECT empleados sin firma con token no expirado desde hace >2 días
  → Evolution API: reenvío del enlace
  → Log del evento en payslip_events
```

---

## 8. CLAUDE.md para el nuevo proyecto

Este es el contenido del `CLAUDE.md` que debe ir en la raíz del nuevo proyecto para orientar al agente:

```markdown
# SaaS Nóminas — Instrucciones para el agente

## Stack
- Next.js 16 + React 19 + TypeScript + Tailwind CSS 4
- Supabase (PostgreSQL + RLS + Auth + Storage)
- Python Worker: FastAPI + PyMuPDF + openpyxl (puerto 8000)
- WhatsApp: Evolution API
- Pagos: Stripe

## Reglas críticas

### Multi-tenant
- SIEMPRE filtrar por `tenant_id` en todas las queries.
- NUNCA hacer queries sin RLS activo.
- Usar `createServerClient` de Supabase en Server Components/Actions.
- Usar `createBrowserClient` solo en Client Components.

### Procesamiento de PDF/Excel
- La lógica de extracción está en `python-worker/core/`.
- NO reescribir: reutilizar `payroll_pdf.py`, `payroll_excel.py`, `signature_pdf.py` de Enteza RRHH.
- Los nombres de archivo de nómina: `{DNI}-{MM}-{YYYY}.pdf`.
- Excluir siempre centros con "TOTAL" en el nombre.

### Asiento contable Odoo
- Un asiento por centro de trabajo (nunca uno global).
- Líneas 640xxx: tax_tag_ids = mod111[02].
- Líneas 475xxx: tax_line_id = impuesto IRPF + tax_tag_ids = mod111[03].
- Fallback de cuentas: exacto → prefijo 4650% → progresivo por la derecha.

### Firma digital
- Tokens: `secrets.token_urlsafe(32)`, guardar solo SHA-256.
- Tras subir PDF firmado: eliminar el PDF sin firma del mismo empleado en Odoo.
- Nombre firmado: `{stem_original}-firmada.pdf`.

### WhatsApp
- Normalizar teléfonos: quitar espacios/guiones, añadir +34 si falta prefijo.
- El enlace DEBE ser HTTPS para ser clicable en WhatsApp móvil.

### Seguridad
- Contraseñas Odoo de tenants: cifrar con `@supabase/vault` o AES-256.
- Nunca exponer credenciales Odoo en respuestas de API.
- PDFs en Supabase Storage: bucket privado + URLs firmadas con TTL corto.
- Tokens de firma: solo válidos una vez (marcar como usados tras la firma).

## Comandos
\`\`\`bash
npm run dev        # Next.js en puerto 3000
npm run typecheck  # Verificar tipos
npm run lint       # ESLint
cd python-worker && uvicorn main:app --reload --port 8000
\`\`\`

## Variables de entorno necesarias
\`\`\`env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
EVOLUTION_API_URL=
EVOLUTION_API_KEY=
PYTHON_WORKER_URL=http://localhost:8000
ENCRYPTION_KEY=   # 32 bytes base64 para cifrar credenciales Odoo
\`\`\`
```

---

## 9. Fases de desarrollo recomendadas

### Fase 0 — Setup (1 semana)
- [ ] Crear proyecto Next.js 16 con Supabase
- [ ] Migraciones SQL con RLS desde el primer día
- [ ] Auth: registro de gestoría + login + middleware de tenant
- [ ] Stripe: integración básica de subscripciones
- [ ] Python worker: FastAPI con endpoints `/process-pdf` y `/process-excel`

### Fase 1 — Core (3 semanas)
- [ ] CRUD de empresas por tenant
- [ ] Upload de PDF + Excel → llamada al worker Python
- [ ] División en nóminas individuales → Supabase Storage
- [ ] Panel de empleados con estado (semáforo)
- [ ] Generación de tokens de firma

### Fase 2 — Firma (2 semanas)
- [ ] Página pública `/sign/[token]` — visor PDF + canvas firma
- [ ] Submit firma → PDF firmado → Storage
- [ ] Eliminación del PDF sin firma
- [ ] Recordatorios automáticos (pg_cron)

### Fase 3 — WhatsApp (1 semana)
- [ ] Integración Evolution API
- [ ] Envío automático al crear solicitudes de firma
- [ ] Webhook de estado de entrega (si Evolution API lo soporta)

### Fase 4 — Odoo (2 semanas)
- [ ] Conexión XML-RPC por empresa
- [ ] Emparejamiento automático de empleados
- [ ] Subida de adjuntos a ir.attachment
- [ ] Asiento contable por centro (con mod111)

### Fase 5 — Polish y lanzamiento (2 semanas)
- [ ] Dashboard con métricas (% firmas, tiempo medio)
- [ ] Historial de periodos
- [ ] Exportaciones (ZIP, Excel de log)
- [ ] Tests E2E con Playwright
- [ ] Documentación de onboarding para gestorías

---

## 10. Preguntas a responder antes de empezar

1. **¿Self-hosted o Supabase Cloud?** — Supabase Cloud es más rápido de arrancar; self-hosted da más control de costes a escala.
2. **¿Un worker Python compartido o uno por tenant?** — Compartido con autenticación por `tenant_id` en la cabecera es suficiente para empezar.
3. **¿White-label desde el día 1?** — Si sí, el dominio de la página de firma debe ser configurable por tenant (`firmas.tugestoría.com`).
4. **¿Soporte a ERP distintos de Odoo?** — La integración Odoo es opcional; el core (split PDF + firma) funciona sin ERP.
5. **¿Número WhatsApp compartido o uno por gestoría?** — Un número compartido es viable al inicio; a escala, una instancia Evolution por gestoría.

---

*Documento generado en mayo 2026 · Basado en el desarrollo de Enteza RRHH*
