# Prompt maestro para mejorar la aplicación Streamlit de nóminas y Odoo 15 Community

## 1. Rol que debe asumir la IA desarrolladora

Actúa como **arquitecto senior Python / Streamlit / Odoo 15 Community**, con experiencia en:

- Automatización de procesos administrativos y contables.
- Procesamiento de PDF y Excel en Python.
- Integración con Odoo 15 Community mediante XML-RPC.
- Desarrollo de aplicaciones locales seguras para datos sensibles de nóminas.
- Generación de ficheros de importación contable para Odoo.
- Buenas prácticas de estado en Streamlit, especialmente para evitar pérdidas de resultados tras un `rerun`.

Tu tarea es **mejorar una aplicación Streamlit ya existente** que:

1. Recibe un PDF con todas las nóminas mensuales de una empresa.
2. Recibe un Excel con el detalle de nómina y los datos económicos por trabajador.
3. Divide el PDF en un PDF individual por trabajador.
4. Nombra cada PDF con el formato `DNI-MM-AAAA.pdf`.
5. Genera una plantilla de mapeo de cuentas.
6. Genera un Excel de importación de asiento contable para Odoo 15.
7. Debe añadir ahora una funcionalidad nueva: **subir cada PDF individual como adjunto a la ficha del empleado correspondiente en Odoo 15 Community**.

La aplicación debe funcionar de forma local, sin enviar datos de nóminas a servicios externos.

---

## 2. Contexto funcional del proyecto

La empresa genera mensualmente:

- Un **PDF único** que contiene una nómina por página.
- Un **Excel de detalle de nómina**, donde cada trabajador aparece asociado a un número de trabajador.
- Ese número de trabajador también aparece en la nómina del PDF.
- El PDF contiene datos como:
  - número de trabajador,
  - nombre del trabajador,
  - NIF/DNI/NIE,
  - periodo de liquidación,
  - total devengado,
  - deducciones,
  - líquido a percibir,
  - bases de cotización,
  - Seguridad Social empresa,
  - retenciones IRPF.

Regla de negocio principal:

```text
Cada página del PDF corresponde a un trabajador.
Cada PDF individual debe nombrarse como:
DNI-MM-AAAA.pdf

Ejemplo:
75427433Z-05-2026.pdf
```

Además, el Excel debe usarse para generar un asiento contable mensual de nóminas para Odoo 15 Community.

---

## 3. Situación actual de la aplicación

Existe una primera versión de la aplicación con esta estructura aproximada:

```text
nominas_odoo_streamlit/
├── app.py
├── requirements.txt
├── README.md
└── core/
    ├── __init__.py
    ├── payroll_pdf.py
    ├── payroll_excel.py
    ├── odoo_export.py
    └── utils.py
```

La aplicación actual ya hace, al menos, lo siguiente:

- Carga PDF completo de nóminas.
- Carga Excel de detalle de nómina.
- Extrae datos de cada página del PDF.
- Divide el PDF en PDFs individuales.
- Genera ZIP con los PDFs individuales.
- Genera plantilla Excel de mapeo de cuentas.
- Genera Excel de importación contable para Odoo.

Con los archivos de prueba de marzo de 2026, la aplicación debe ser capaz de obtener estos resultados esperados:

```text
Páginas PDF procesadas: 37
Trabajadores detectados: 37
PDFs individuales generados: 37
Líneas de asiento generadas: 153
Debe: 100.216,34 €
Haber: 100.216,34 €
Diferencia: 0,00 €
```

No debes romper estas funcionalidades existentes.

---

## 4. Problema detectado que debes corregir obligatoriamente

### 4.1. Error actual

Al probar la aplicación, una vez procesados los archivos de entrada, se generan botones de descarga:

- Descargar ZIP con nóminas individuales.
- Descargar plantilla de mapeo.
- Descargar Excel de importación para Odoo.

Pero cuando el usuario pulsa cualquiera de esos botones, **Streamlit vuelve a renderizar la aplicación**, desaparecen los botones y obliga a procesar de nuevo los archivos.

### 4.2. Causa probable

La causa es que los artefactos se generan dentro de un bloque similar a:

```python
if st.button("Procesar"):
    with tempfile.TemporaryDirectory() as tmpdir:
        # procesar
        st.download_button(...)
```

En Streamlit, cualquier interacción puede provocar un `rerun`. Si los botones de descarga solo existen dentro del bloque del botón `Procesar`, al producirse el `rerun`, el bloque ya no se ejecuta y los resultados desaparecen.

Además, si los ficheros están dentro de un `TemporaryDirectory`, ese directorio puede destruirse al terminar el bloque, dejando rutas inválidas.

### 4.3. Solución obligatoria

Debes refactorizar la aplicación para que los resultados se conserven en `st.session_state`.

La aplicación debe tener una estructura de estado parecida a esta:

```python
DEFAULT_STATE = {
    "processed": False,
    "pdf_hash": None,
    "excel_hash": None,
    "mapping_hash": None,
    "period_month": None,
    "period_year": None,
    "pdf_pages": None,
    "employee_rows": None,
    "accounting_summary": None,
    "mapping_xlsx_bytes": None,
    "odoo_import_xlsx_bytes": None,
    "zip_payslips_bytes": None,
    "split_pdfs": None,
    "odoo_matches": None,
    "odoo_upload_log": None,
}
```

La lógica correcta debe ser:

```python
if "processed" not in st.session_state:
    st.session_state.processed = False

if st.button("Procesar nóminas"):
    artifacts = process_files(...)
    st.session_state.processed = True
    st.session_state.mapping_xlsx_bytes = artifacts.mapping_xlsx_bytes
    st.session_state.odoo_import_xlsx_bytes = artifacts.odoo_import_xlsx_bytes
    st.session_state.zip_payslips_bytes = artifacts.zip_payslips_bytes
    st.session_state.split_pdfs = artifacts.split_pdfs
    st.session_state.employee_rows = artifacts.employee_rows
    st.session_state.accounting_summary = artifacts.accounting_summary

if st.session_state.processed:
    render_results_from_session_state()
```

Y los botones de descarga deben estar siempre fuera del bloque `if st.button("Procesar")`:

```python
if st.session_state.processed:
    st.download_button(
        "Descargar ZIP con nóminas individuales",
        data=st.session_state.zip_payslips_bytes,
        file_name=f"nominas_individuales_{year}_{month:02d}.zip",
        mime="application/zip",
        key="download_zip_nominas",
        on_click="ignore",  # usar si la versión instalada de Streamlit lo soporta
    )
```

Si la versión de Streamlit no soporta `on_click="ignore"`, el uso de `st.session_state` debe bastar para que, aunque se produzca el `rerun`, los botones y datos sigan apareciendo.

Añade también un botón explícito:

```text
Limpiar resultados / iniciar nuevo procesamiento
```

Ese botón debe borrar el estado y permitir empezar de nuevo.

---

## 5. Nuevas funcionalidades a desarrollar

## 5.1. Conexión con Odoo 15 Community

Añade un módulo nuevo:

```text
core/odoo_client.py
```

Debe implementar conexión por XML-RPC a Odoo 15 Community.

La conexión debe usar:

```text
/xmlrpc/2/common
/xmlrpc/2/object
```

Parámetros necesarios:

- URL de Odoo.
- Base de datos.
- Usuario.
- Contraseña o API key, si se usa.

La aplicación debe permitir introducir estos datos desde la interfaz, pero también debe soportar configuración mediante `.streamlit/secrets.toml`.

Ejemplo de `secrets.toml`:

```toml
[odoo]
url = "https://odoo.midominio.com"
db = "nombre_base_datos"
username = "usuario@empresa.com"
password = "contraseña_o_api_key"
```

No debe haber credenciales hardcodeadas en el código.

### Clase recomendada

Implementa una clase parecida a esta:

```python
class OdooClient:
    def __init__(self, url: str, db: str, username: str, password: str):
        ...

    def authenticate(self) -> int:
        ...

    def execute_kw(self, model: str, method: str, args=None, kwargs=None):
        ...

    def fields_get(self, model: str) -> dict:
        ...

    def search_read(self, model: str, domain: list, fields: list, limit: int = 100):
        ...

    def create(self, model: str, values: dict) -> int:
        ...

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        ...
```

Incluye manejo claro de errores:

- URL incorrecta.
- Base de datos incorrecta.
- Usuario o contraseña incorrectos.
- Módulo `hr` no instalado.
- Modelo `hr.employee` no disponible.
- Permisos insuficientes para leer empleados.
- Permisos insuficientes para crear adjuntos en `ir.attachment`.

---

## 5.2. Búsqueda y emparejamiento de empleados en Odoo

El objetivo es vincular cada PDF individual con la ficha correcta del empleado en Odoo.

La aplicación debe permitir emparejar nóminas con empleados de Odoo usando varios criterios.

### Criterios posibles

1. **DNI/NIF/NIE** extraído del PDF.
2. **Número de trabajador** extraído del PDF y/o Excel.
3. **Nombre normalizado** del trabajador.
4. **Mapeo manual** cargado desde Excel.

En Odoo 15 Community, la ficha del empleado suele estar en el modelo:

```text
hr.employee
```

El campo de DNI/NIF puede ser:

```text
identification_id
```

Pero no debes asumirlo de forma rígida, porque puede variar según localización, módulos instalados o personalizaciones.

Por eso, la aplicación debe:

1. Consultar los campos disponibles de `hr.employee` con `fields_get`.
2. Mostrar al usuario un selector para elegir qué campo de Odoo contiene el DNI/NIF/NIE.
3. Mostrar otro selector para elegir qué campo de Odoo contiene el número de trabajador, si existe.
4. Permitir dejar vacío el campo de número de trabajador si Odoo no lo tiene.

Campos candidatos habituales para número de trabajador:

```text
barcode
employee_number
registration_number
x_num_trabajador
x_studio_num_trabajador
```

No todos existirán. La aplicación debe comprobar qué campos existen antes de usarlos.

### Normalización obligatoria

Implementa funciones de normalización:

```python
def normalize_dni(value: str) -> str:
    # mayúsculas, sin espacios, sin guiones, sin puntos
    ...


def normalize_worker_number(value: str) -> str:
    # quitar espacios, convertir 002 a 2 si procede, mantener como texto
    ...


def normalize_name(value: str) -> str:
    # mayúsculas, sin tildes, espacios únicos
    ...
```

### Flujo de emparejamiento recomendado

1. Si hay DNI en el PDF y el usuario ha seleccionado un campo DNI en Odoo:
   - Buscar empleado por DNI normalizado.
2. Si no hay coincidencia, y hay número de trabajador:
   - Buscar por el campo de número de trabajador seleccionado.
3. Si no hay coincidencia:
   - Buscar por nombre normalizado.
4. Si sigue sin haber coincidencia:
   - Marcar como `NO ENCONTRADO`.
5. Si hay más de una coincidencia:
   - Marcar como `AMBIGUO`.
6. Solo se podrán subir adjuntos para registros con estado `MATCH_OK`.

### Tabla de revisión en Streamlit

Después del emparejamiento, muestra una tabla con:

```text
n_trabajador
DNI
nombre_pdf
nombre_excel
archivo_pdf
employee_id_odoo
employee_name_odoo
criterio_match
estado_match
observaciones
```

Debe poder descargarse como Excel.

---

## 5.3. Mapeo manual de empleados

Añade opción para descargar una plantilla de mapeo manual de empleados Odoo.

Columnas recomendadas:

```text
n_trabajador
dni
nombre_pdf
nombre_excel
archivo_pdf
employee_id_odoo
employee_name_odoo
usar_para_subida
observaciones
```

El usuario podrá rellenar `employee_id_odoo` manualmente y volver a subir la plantilla.

Si se sube una plantilla manual, debe tener prioridad sobre el emparejamiento automático.

Validaciones:

- `employee_id_odoo` debe existir en Odoo.
- El empleado debe estar activo o, si está archivado, avisar.
- No debe haber dos PDFs asociados al mismo empleado para el mismo mes/año salvo que el usuario lo confirme.
- No debe haber un PDF sin empleado asociado si el usuario intenta subirlo.

---

## 5.4. Subida de PDFs individuales a la ficha del empleado

Añade una sección en la aplicación:

```text
4) Subir nóminas individuales a Odoo
```

Esta sección solo debe activarse si:

- El PDF y el Excel han sido procesados correctamente.
- Existen PDFs individuales en memoria o en disco persistente.
- La conexión a Odoo es correcta.
- El emparejamiento de empleados ha sido revisado.

### Modelo Odoo para adjuntos

Los PDFs deben subirse al modelo:

```text
ir.attachment
```

Cada adjunto debe crearse vinculado al empleado:

```python
{
    "name": "75427433Z-05-2026.pdf",
    "type": "binary",
    "datas": base64.b64encode(pdf_bytes).decode("utf-8"),
    "res_model": "hr.employee",
    "res_id": employee_id,
    "mimetype": "application/pdf",
    "description": "Nómina 05/2026 importada automáticamente desde Streamlit"
}
```

No uses `datas_fname` salvo que confirmes mediante `fields_get('ir.attachment')` que el campo existe en esa base de datos.

### Control de duplicados

Antes de crear el adjunto, buscar si ya existe un adjunto con el mismo:

```text
res_model = hr.employee
res_id = employee_id
name = nombre_del_pdf
```

La aplicación debe ofrecer tres políticas:

```text
1. Omitir si ya existe.
2. Reemplazar el adjunto existente.
3. Crear duplicado con sufijo de fecha/hora.
```

Por defecto: **omitir si ya existe**.

### Modo simulación obligatorio

Antes de subir nada realmente, debe existir un checkbox:

```text
Modo simulación: no crear adjuntos, solo mostrar qué se haría
```

Debe estar activado por defecto.

En modo simulación, la aplicación debe generar un log indicando:

```text
OK_SIMULADO: se subiría 75427433Z-05-2026.pdf al empleado ID 123 - Nombre Apellidos
NO_ENCONTRADO: no se sube porque no hay empleado asociado
DUPLICADO: ya existe un adjunto con ese nombre
AMBIGUO: no se sube porque hay más de una coincidencia
ERROR: detalle del error
```

Cuando el usuario desactive el modo simulación y pulse:

```text
Subir nóminas a Odoo
```

entonces se crearán o actualizarán los adjuntos.

---

## 6. Generación del asiento contable para Odoo

Mantén la funcionalidad actual de generación del asiento contable, pero mejora las validaciones y el resultado.

### 6.1. Excel de importación para Odoo

La aplicación debe seguir generando un Excel con estructura compatible con la importación de asientos contables en Odoo 15.

Mantén una hoja técnica con columnas tipo:

```text
id
move_type
date
journal_id
ref
line_ids/account_id
line_ids/partner_id
line_ids/name
line_ids/debit
line_ids/credit
line_ids/tax_tag_ids
line_ids/tax_ids
line_ids/analytic_account_id
```

Añade, si es útil, una segunda hoja con nombres más comprensibles para el usuario:

```text
Fecha
Diario
Referencia
Cuenta
Empresa/Partner
Etiqueta
Debe
Haber
Cuadrícula impuestos
Impuestos
Cuenta analítica
```

### 6.2. Reglas contables orientativas

La aplicación debe seguir usando una plantilla de mapeo editable por el usuario.

Cuentas habituales iniciales:

```text
64000000 - Sueldos y salarios
64200100 - Seguridad Social a cargo de la empresa
465xxxxx - Remuneraciones pendientes de pago por trabajador
47510000 - Hacienda Pública, acreedora por retenciones practicadas
47600012 - Seguridad Social acreedora / TC1
47100000 - Organismos de la Seguridad Social deudores, si hay prestaciones INSS
46599999 - Embargos u otras deducciones, revisable por el usuario
```

No debes imponer estas cuentas como definitivas. Deben ser parametrizables mediante Excel de mapeo.

### 6.3. Validaciones del asiento

Antes de permitir descargar el Excel de importación, muestra:

```text
Total debe
Total haber
Diferencia
Número de líneas
Número de empleados incluidos
Número de empleados excluidos
Deducciones no mapeadas
Advertencias
```

Si el asiento no cuadra, debe aparecer claramente:

```text
ASIENTO NO CUADRADO: revisar deducciones no mapeadas o conceptos especiales.
```

La descarga puede permitirse, pero con aviso.

---

## 7. Arquitectura técnica recomendada

Refactoriza hacia una arquitectura limpia:

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
│   ├── payroll_pdf.py
│   ├── payroll_excel.py
│   ├── accounting_export.py
│   ├── odoo_client.py
│   ├── odoo_employee_matcher.py
│   ├── odoo_attachments.py
│   ├── validators.py
│   └── utils.py
└── tests/
    ├── test_pdf_parsing.py
    ├── test_excel_parsing.py
    ├── test_accounting_export.py
    ├── test_employee_matching.py
    └── test_state_persistence.py
```

### 7.1. Modelos de datos

Crea dataclasses o modelos Pydantic ligeros.

Ejemplo:

```python
@dataclass
class PayslipPage:
    page_index: int
    worker_number: str
    dni: str
    employee_name: str
    month: int | None
    year: int | None
    filename: str | None = None
    pdf_bytes: bytes | None = None
```

```python
@dataclass
class PayrollEmployee:
    worker_number: str
    name: str
    center: str | None
    concepts: dict[str, Decimal]
```

```python
@dataclass
class SplitPdfArtifact:
    worker_number: str
    dni: str
    employee_name: str
    month: int
    year: int
    filename: str
    pdf_bytes: bytes
```

```python
@dataclass
class OdooEmployeeMatch:
    worker_number: str
    dni: str
    employee_name_pdf: str
    employee_name_excel: str
    filename: str
    employee_id_odoo: int | None
    employee_name_odoo: str | None
    match_method: str
    match_status: str
    observations: str
```

```python
@dataclass
class UploadResult:
    filename: str
    worker_number: str
    dni: str
    employee_id_odoo: int | None
    employee_name_odoo: str | None
    status: str
    message: str
    attachment_id: int | None = None
```

---

## 8. Interfaz Streamlit esperada

La interfaz debe estar organizada por pasos.

### Paso 1: Cargar archivos

Componentes:

```text
- file_uploader PDF completo de nóminas
- file_uploader Excel detalle de nómina
- file_uploader mapeo de cuentas opcional
- botón Procesar nóminas
```

### Paso 2: Revisar resultados

Mostrar:

```text
- periodo detectado
- nº de páginas procesadas
- nº de trabajadores detectados
- tabla de páginas PDF detectadas
- tabla de empleados del Excel
- advertencias PDF vs Excel
- resumen contable
```

Botones persistentes:

```text
- Descargar ZIP con nóminas individuales
- Descargar plantilla de mapeo de cuentas
- Descargar Excel de importación Odoo
```

Estos botones no deben desaparecer después de pulsarlos.

### Paso 3: Conexión Odoo

Componentes:

```text
- URL
- Base de datos
- Usuario
- Contraseña/API key
- botón Probar conexión
```

Resultado:

```text
Conexión correcta. Usuario autenticado UID: X
```

O error claro.

### Paso 4: Emparejar empleados

Componentes:

```text
- selector de campo DNI en Odoo
- selector de campo número trabajador en Odoo
- selector de campo nombre en Odoo, normalmente name
- botón Buscar empleados en Odoo
- file_uploader mapeo manual Odoo opcional
```

Mostrar tabla de emparejamiento y permitir descargarla.

### Paso 5: Subir adjuntos

Componentes:

```text
- checkbox Modo simulación, activado por defecto
- selector política de duplicados
- botón Subir nóminas a Odoo
```

Mostrar log de subida:

```text
archivo_pdf
empleado_odoo
estado
mensaje
attachment_id
```

Permitir descargar el log en Excel.

### Paso 6: Limpiar estado

Botón:

```text
Limpiar resultados / iniciar nuevo procesamiento
```

Debe borrar `st.session_state` relacionado con el procesamiento.

---

## 9. Requisitos de seguridad y privacidad

Los datos tratados son nóminas y datos personales. Por tanto:

1. No enviar PDF ni Excel a APIs externas.
2. No usar OCR en la nube.
3. No registrar en logs contraseñas ni datos completos innecesarios.
4. No guardar credenciales en el repositorio.
5. No mostrar contraseñas en pantalla.
6. Usar `type="password"` en Streamlit para el campo contraseña.
7. Recomendar HTTPS para la URL de Odoo.
8. Si se guardan ficheros temporales, deben eliminarse al limpiar el estado.
9. Para depuración, permitir ocultar DNI parcialmente:

```text
75427433Z -> 7542****Z
```

---

## 10. Dependencias recomendadas

Actualiza `requirements.txt` con versiones razonables:

```text
streamlit>=1.32
pandas>=2.0
openpyxl>=3.1
PyMuPDF>=1.23
python-dateutil>=2.8
Unidecode>=1.3
```

`xmlrpc.client`, `base64`, `hashlib`, `tempfile`, `zipfile`, `io`, `pathlib` y `decimal` son librerías estándar.

Si usas `on_click="ignore"` en `st.download_button`, comprueba que la versión instalada de Streamlit lo soporta. Si no, el diseño con `st.session_state` debe seguir funcionando.

---

## 11. Código orientativo para corregir el problema de los botones

Implementa algo equivalente a esto en `app.py` o `core/state.py`:

```python
import streamlit as st

ARTIFACT_KEYS = [
    "processed",
    "period_month",
    "period_year",
    "pdf_pages_df",
    "employee_rows_df",
    "accounting_summary",
    "mapping_xlsx_bytes",
    "odoo_import_xlsx_bytes",
    "zip_payslips_bytes",
    "split_pdfs",
    "odoo_matches_df",
    "odoo_upload_log_df",
]


def init_state():
    defaults = {
        "processed": False,
        "period_month": None,
        "period_year": None,
        "pdf_pages_df": None,
        "employee_rows_df": None,
        "accounting_summary": None,
        "mapping_xlsx_bytes": None,
        "odoo_import_xlsx_bytes": None,
        "zip_payslips_bytes": None,
        "split_pdfs": None,
        "odoo_matches_df": None,
        "odoo_upload_log_df": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_processing_state():
    for key in ARTIFACT_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    init_state()
```

Y en `app.py`:

```python
init_state()

if st.button("Procesar nóminas", type="primary"):
    artifacts = process_uploaded_files(...)
    st.session_state.processed = True
    st.session_state.period_month = artifacts.period_month
    st.session_state.period_year = artifacts.period_year
    st.session_state.mapping_xlsx_bytes = artifacts.mapping_xlsx_bytes
    st.session_state.odoo_import_xlsx_bytes = artifacts.odoo_import_xlsx_bytes
    st.session_state.zip_payslips_bytes = artifacts.zip_payslips_bytes
    st.session_state.split_pdfs = artifacts.split_pdfs
    st.session_state.accounting_summary = artifacts.accounting_summary

if st.session_state.processed:
    month = st.session_state.period_month
    year = st.session_state.period_year

    st.download_button(
        "Descargar ZIP con nóminas individuales",
        data=st.session_state.zip_payslips_bytes,
        file_name=f"nominas_individuales_{year}_{month:02d}.zip",
        mime="application/zip",
        key="download_zip_nominas",
    )

    st.download_button(
        "Descargar plantilla de mapeo de cuentas",
        data=st.session_state.mapping_xlsx_bytes,
        file_name=f"mapeo_nominas_{year}_{month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_mapeo_cuentas",
    )

    st.download_button(
        "Descargar Excel de importación Odoo",
        data=st.session_state.odoo_import_xlsx_bytes,
        file_name=f"asiento_odoo_nomina_{year}_{month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_asiento_odoo",
    )

if st.button("Limpiar resultados / iniciar nuevo procesamiento"):
    clear_processing_state()
    st.rerun()
```

---

## 12. Código orientativo para subir adjuntos a Odoo

Implementa en `core/odoo_attachments.py` algo similar:

```python
import base64
from datetime import datetime


def find_existing_attachment(odoo, employee_id: int, filename: str):
    domain = [
        ("res_model", "=", "hr.employee"),
        ("res_id", "=", employee_id),
        ("name", "=", filename),
    ]
    records = odoo.search_read(
        "ir.attachment",
        domain=domain,
        fields=["id", "name", "res_model", "res_id"],
        limit=1,
    )
    return records[0] if records else None


def upload_employee_payslip_attachment(
    odoo,
    employee_id: int,
    filename: str,
    pdf_bytes: bytes,
    month: int,
    year: int,
    duplicate_policy: str = "skip",
    dry_run: bool = True,
):
    existing = find_existing_attachment(odoo, employee_id, filename)

    if existing and duplicate_policy == "skip":
        return {
            "status": "DUPLICADO_OMITIDO",
            "message": f"Ya existe el adjunto {filename}",
            "attachment_id": existing["id"],
        }

    final_filename = filename
    if existing and duplicate_policy == "duplicate":
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = filename.replace(".pdf", f"_{suffix}.pdf")

    values = {
        "name": final_filename,
        "type": "binary",
        "datas": base64.b64encode(pdf_bytes).decode("utf-8"),
        "res_model": "hr.employee",
        "res_id": employee_id,
        "mimetype": "application/pdf",
        "description": f"Nómina {month:02d}/{year} importada automáticamente desde Streamlit",
    }

    if dry_run:
        return {
            "status": "OK_SIMULADO",
            "message": f"Se subiría {final_filename} al empleado {employee_id}",
            "attachment_id": existing["id"] if existing else None,
        }

    if existing and duplicate_policy == "replace":
        odoo.write("ir.attachment", [existing["id"]], values)
        return {
            "status": "REEMPLAZADO",
            "message": f"Adjunto reemplazado: {final_filename}",
            "attachment_id": existing["id"],
        }

    attachment_id = odoo.create("ir.attachment", values)
    return {
        "status": "CREADO",
        "message": f"Adjunto creado: {final_filename}",
        "attachment_id": attachment_id,
    }
```

---

## 13. Pruebas mínimas obligatorias

Añade pruebas automáticas o, al menos, funciones de validación reproducibles.

### 13.1. PDF

Validar que:

- Detecta una página por nómina.
- Extrae número de trabajador.
- Extrae DNI/NIF/NIE.
- Extrae nombre.
- Extrae mes y año.
- Genera nombre de archivo `DNI-MM-AAAA.pdf`.

### 13.2. Excel

Validar que:

- Detecta trabajadores por columnas.
- Extrae número de trabajador desde la cabecera.
- Extrae nombre del trabajador.
- Extrae conceptos económicos relevantes.
- Convierte importes españoles correctamente:

```text
1.234,56 -> Decimal("1234.56")
```

### 13.3. Asiento Odoo

Validar que:

- El asiento queda cuadrado.
- Las líneas con importe 0 no se generan.
- Las cuentas vacías generan advertencia.
- La plantilla de mapeo puede reimportarse.

### 13.4. Estado Streamlit

Validar manualmente que:

1. Se cargan PDF y Excel.
2. Se pulsa `Procesar nóminas`.
3. Aparecen los botones de descarga.
4. Se pulsa un botón de descarga.
5. Los botones siguen apareciendo.
6. No es necesario volver a procesar.

### 13.5. Odoo

Validar en modo simulación:

- Conexión correcta.
- Lectura de campos de `hr.employee`.
- Emparejamiento por DNI.
- Emparejamiento por número de trabajador.
- Detección de no encontrados.
- Detección de duplicados.

Validar en modo real, con un empleado de prueba:

- Se crea un adjunto en `ir.attachment`.
- El adjunto queda vinculado a `hr.employee`.
- El PDF se puede abrir desde Odoo.
- Si se repite la subida, aplica la política de duplicados.

---

## 14. Criterios de aceptación final

La mejora se considerará correcta si cumple todo esto:

1. La aplicación carga PDF y Excel sin errores.
2. Detecta correctamente el periodo de liquidación.
3. Divide el PDF en un PDF individual por nómina.
4. Nombra cada PDF como `DNI-MM-AAAA.pdf`.
5. Genera ZIP descargable.
6. Genera plantilla de mapeo de cuentas descargable.
7. Genera Excel de importación contable para Odoo.
8. Los botones de descarga no desaparecen al pulsarlos.
9. El usuario puede limpiar el estado y comenzar de nuevo.
10. La aplicación se conecta a Odoo 15 Community por XML-RPC.
11. La aplicación permite elegir campos de Odoo para DNI y número de trabajador.
12. La aplicación empareja nóminas con empleados.
13. La aplicación muestra una tabla de revisión antes de subir adjuntos.
14. La aplicación permite modo simulación.
15. La aplicación sube los PDFs a `ir.attachment` vinculados a `hr.employee`.
16. La aplicación controla duplicados.
17. La aplicación genera log descargable de la subida.
18. No hay credenciales hardcodeadas.
19. No se envían datos a servicios externos.
20. El código queda organizado, documentado y mantenible.

---

## 15. Instrucciones finales para la IA desarrolladora

No empieces reescribiendo todo el proyecto desde cero.

Primero:

1. Lee el código existente.
2. Identifica las funciones ya válidas.
3. Refactoriza el estado de Streamlit para corregir el problema de los botones.
4. Conserva la lógica de extracción PDF/Excel si funciona.
5. Añade los nuevos módulos de Odoo de forma separada.
6. Añade pruebas y validaciones.
7. Actualiza el README.
8. Entrega el proyecto completo listo para ejecutar.

El resultado final debe poder ejecutarse con:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

En Linux/Mac:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

