# Divisor de nóminas PDF y generador de asiento para Odoo 15 Community

Aplicación Streamlit para procesar un PDF mensual con una nómina por página y un Excel de detalle de nómina. Genera:

1. Un ZIP con un PDF individual por trabajador nombrado como `DNI-MM-AAAA.pdf`.
2. Una plantilla de mapeo de cuentas por trabajador.
3. Un Excel preparado para importar un asiento contable mensual en Odoo 15.
4. **Nuevo**: Subida automática de las nóminas individuales como adjuntos a la ficha del empleado en Odoo 15 Community.
5. **Nuevo**: Creación directa del asiento contable de nómina en Odoo (con modo simulación).

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue con Docker (VPS Linux)

### Requisitos

- Docker + Docker Compose plugin
- Dominio apuntando al VPS (si usaras HTTPS)

### 1) Configurar variables

Completa `.env.local` con tus credenciales Odoo y agrega:

```env
SIGN_BASE_URL=https://tu-dominio.com
```

### 2) Levantar servicios

```bash
docker compose build
docker compose up -d
```

### 3) Verificar estado

```bash
docker compose ps
docker compose logs -f app
```

La app queda publicada por Nginx en puerto 80.

### HTTPS (recomendado)

- Opcion simple: usa un proxy externo (Cloudflare Tunnel / Nginx del host).
- Opcion local: monta certificados en `deploy/certs` y agrega bloque TLS en `deploy/nginx/conf.d/app.conf`.

### Persistencia

Se guardan datos en volumen local del proyecto:

- `./data` (tokens, solicitudes, firmas, PDFs)
- `./uploads` (si se usa almacenamiento auxiliar)

## Flujo de uso

1. Subir el PDF completo de nóminas.
2. Subir el Excel de detalle de nómina.
3. Pulsar **Procesar nóminas y generar ficheros**.
4. Descargar la plantilla de mapeo y revisar las cuentas contables.
5. Volver a subir el mapeo revisado si se han cambiado cuentas.
6. Descargar el ZIP de nóminas individuales y el Excel de importación para Odoo.
7. Conectar con Odoo 15 Community (paso 2).
8. Emparejar empleados de las nóminas con los registros de Odoo (paso 3).
9. Subir las nóminas individuales como adjuntos a la ficha del empleado en Odoo (paso 4).

## Funcionalidades

### Procesamiento de PDF y Excel

- Lee cada página del PDF y extrae: número de trabajador, DNI/NIF/NIE, nombre, periodo de liquidación.
- Lee el Excel de detalle y extrae los conceptos económicos por trabajador.
- Genera PDFs individuales nombrados como `DNI-MM-AAAA.pdf`.
- Genera un asiento contable mensual cuadrado para importar en Odoo.

### Conexión con Odoo 15 Community

- Conexión por XML-RPC (`/xmlrpc/2/common`, `/xmlrpc/2/object`).
- Credenciales configurables desde la interfaz o desde `.streamlit/secrets.toml`.
- No hay credenciales hardcodeadas.

### Emparejamiento de empleados

- Automático por DNI/NIF/NIE.
- Automático por número de trabajador (si el campo existe en Odoo).
- Automático por nombre normalizado.
- Mapeo manual mediante plantilla Excel descargable.
- Tabla de revisión con estados: `MATCH_OK`, `NO_ENCONTRADO`, `AMBIGUO`.

### Subida de adjuntos a Odoo

- Sube cada PDF individual a `ir.attachment` vinculado a `hr.employee`.
- Modo simulación activado por defecto (no crea adjuntos reales).
- Política de duplicados: omitir, reemplazar o crear duplicado con sufijo.
- Log descargable de la subida.

### Creación de asiento contable en Odoo

- Construye las líneas contables desde el mismo mapeo ya usado para el Excel.
- Valida balance (debe/haber) antes de crear.
- Resuelve diario (`code`, `name` o `id`) y cuentas contables en Odoo.
- Modo simulación por defecto para validar sin crear nada real.

## Lógica de nombrado de PDFs

La aplicación lee cada página del PDF, busca el campo `NIF:` y el periodo de liquidación. El fichero individual se nombra como:

```text
DNI-MM-AAAA.pdf
```

Ejemplo:

```text
75427433Z-05-2026.pdf
```

Si no se localiza el DNI, se usa un nombre de reserva con el número de trabajador.

## Lógica contable inicial

La plantilla genera un asiento mensual con estas líneas base:

- Debe 640: total bruto de la nómina del trabajador.
- Debe 642: Seguridad Social a cargo de la empresa.
- Haber 465: líquido a percibir por el trabajador.
- Haber 4751: retenciones IRPF.
- Haber 476: TC1, agregado por defecto en una sola línea.
- Haber cuenta de embargo, si el Excel contiene `Embargo Juzgado (Nómina)`.

La cuenta 465 se precarga con la convención observada en el asiento de ejemplo: `46510` + número de trabajador a 3 dígitos. Por ejemplo, trabajador 228 -> `46510228`.

## Configuración de Odoo

Crea el archivo `.streamlit/secrets.toml` (no versionado) con:

```toml
[odoo]
url = "https://odoo.midominio.com"
db = "nombre_base_datos"
username = "usuario@empresa.com"
password = "contraseña_o_api_key"
```

También puedes introducir las credenciales directamente en la interfaz.

## Columnas del Excel de importación Odoo

Se usa una hoja `odoo_import` con columnas técnicas orientadas al modelo `account.move` y sus líneas `account.move.line`:

- `id`
- `move_type`
- `date`
- `journal_id`
- `ref`
- `line_ids/account_id`
- `line_ids/partner_id`
- `line_ids/name`
- `line_ids/debit`
- `line_ids/credit`
- `line_ids/tax_tag_ids`
- `line_ids/tax_ids`
- `line_ids/analytic_account_id`

En Odoo, entrar en **Contabilidad > Asientos contables**, usar **Favoritos > Importar registros**, cargar el Excel y revisar el mapeo propuesto antes de validar.

## Estructura del proyecto

```text
nominas_odoo_streamlit/
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── secrets.toml.example
├── core/
│   ├── __init__.py
│   ├── models.py
│   ├── state.py
│   ├── validators.py
│   ├── payroll_pdf.py
│   ├── payroll_excel.py
│   ├── odoo_export.py
│   ├── odoo_client.py
│   ├── odoo_employee_matcher.py
│   ├── odoo_attachments.py
│   └── utils.py
└── tests/
    ├── test_pdf_parsing.py
    ├── test_excel_parsing.py
    ├── test_accounting_export.py
    ├── test_employee_matching.py
    └── test_state_persistence.py
```

## Importante

- Revisar la cuenta 640 por trabajador/categoría antes de importar.
- Revisar que las cuentas existen en Odoo y que sus nombres/códigos son localizables por el importador.
- Revisar las etiquetas fiscales `mod111[02]` y `mod111[03]` si se utilizan cuadrículas del modelo 111.
- El asiento debe quedar con diferencia 0. Si no cuadra, revisar deducciones adicionales no contempladas.
- Los datos de nóminas se procesan localmente. No se envían a servicios externos.
