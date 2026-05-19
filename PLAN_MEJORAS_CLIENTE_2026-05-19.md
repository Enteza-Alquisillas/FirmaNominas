# Plan de Mejoras — Solicitudes Cliente · 2026-05-19

> **Estado:** Borrador para validación. No se toca código hasta aprobación.

---

## Resumen ejecutivo

El cliente ha planteado **12 mejoras** agrupadas en tres módulos: Asiento Contable, Empleados y Nóminas.
Dos puntos requieren aclaraciones antes de poder diseñar la solución.
El resto está listo para implementar en cuanto se valide este documento.

---

## MÓDULO A — Asiento Contable

### A1 · Cuentas de remuneraciones por empleado: 46510xxx vs 46500000

**Situación actual**
La función `safe_account_465(worker_number)` en `core/utils.py` genera siempre una cuenta de la forma `46510{n_trabajador}` para todos los empleados.
El fallback en Odoo busca primero exacta, luego por prefijo `4650%`.

**Lo que pide el cliente**
- Si el empleado **ya tiene cuenta creada en Odoo** (la cuenta `46510xxx` existe en Odoo) → usar esa cuenta exacta.
- Si el empleado **es nuevo** (la cuenta `46510xxx` no existe en Odoo) → usar `46500000`.

**Propuesta de implementación**
Añadir en el paso de generación del mapeo de cuentas (paso 1 → función `build_employee_rows`) una llamada previa a Odoo que verifique qué cuentas `46510xxx` existen realmente. Esta verificación es opcional si no hay conexión Odoo en ese momento. El resultado se puede reflejar en la columna `cuenta_remuneraciones` de la plantilla de mapeo antes de que el usuario la descargue.

Adicionalmente, el fallback actual en `_resolve_account_ids()` ya cubre este caso (busca `4650%` cuando no encuentra `4651xxx`), pero no distingue `46500000` de otras cuentas `4650x`. Se añade una búsqueda exacta de `46500000` como último escalón del fallback.

**Archivos afectados**
- `core/odoo_export.py` → `build_employee_rows()`
- `core/odoo_accounting.py` → `_resolve_account_ids()`
- `app.py` → paso 1 de procesamiento (para pasar conexión Odoo si está disponible)

**Complejidad:** Media · ~3h

---

### A2 · Cuenta 640xxxxx según función/gasto por empleado

**Situación actual**
Hay UNA columna `cuenta_sueldos` por empleado en la plantilla de mapeo. El importe del Excel de nóminas (`total_bruto`) se asienta en esa única cuenta.

**Lo que pide el cliente**
Un empleado puede trabajar en distintos almacenes el mismo mes (ej. L-V en almacén sillas, D en almacén general), con distintas cuentas de gasto 640. El asiento debe tener **varias filas 640** para ese empleado, cada una con su cuenta y su importe parcial.

**Aclaración recibida**
El almacén (y por tanto la cuenta 640) se determina a partir del **departamento al que pertenece el empleado en Odoo** (`hr.employee.department_id`).

**Propuesta de implementación**

*Caso normal (empleado en un solo departamento):*
Al hacer el emparejamiento en el paso 3, se lee `department_id` de `hr.employee`. Se configura en la app una tabla "departamento → cuenta 640" (puede ser un widget editable en el sidebar o una hoja adicional en el Excel de mapeo). La cuenta 640 se pre-rellena automáticamente en la plantilla de mapeo.

*Caso especial (empleado en dos almacenes mismo mes):*
En Odoo un empleado solo tiene un `department_id` activo en un momento dado. Si la distribución de costes entre departamentos no está en Odoo, se resuelve con el **editor de asiento simulado (A6)**: el usuario añade manualmente la segunda línea 640 con el importe parcial y ajusta la primera. Es la solución más práctica dado que estos casos son puntuales.

**Configuración departamento → cuenta 640 en el sidebar**
Se añade una sección expandible "Cuentas por departamento" con hasta 8 filas editables (departamento / cuenta 640). Se carga al iniciar la app desde `.env.local` y se puede editar en sesión.

**Archivos afectados**
- `app.py` → sidebar (tabla departamento→cuenta), paso 3 (leer `department_id`), paso 1 (aplicar al mapeo)
- `core/odoo_employee_matcher.py` → leer `department_id` junto al resto de campos
- `core/models.py` → `OdooEmployeeMatch` (campo `department`)
- `core/odoo_export.py` → `build_employee_rows()` (usar cuenta del departamento si disponible)

**Complejidad:** Media · ~4h ✅ Aclarado

---

### A3 · Cuentas 6420xxxx Seguros Sociales diferenciadas por Sevilla / Jerez

**Situación actual**
Hay UNA columna `cuenta_ss_empresa` (por defecto `64200100`) para todos los empleados independientemente de su centro de trabajo.

**Lo que pide el cliente**
Diferenciar la cuenta de Seguros Sociales empresa según el centro: Sevilla usa una cuenta y Jerez usa otra.

**Propuesta de implementación**
La información del centro de trabajo ya está disponible en el campo `emp.center` del Excel de nóminas.

1. En `build_employee_rows()` se pre-rellena `cuenta_ss_empresa` según el centro del empleado usando una tabla de configuración. Esta tabla puede ser un parámetro en el sidebar de la app (dos campos de texto: "Cuenta SS Sevilla" / "Cuenta SS Jerez") o puede configurarse en el Excel de mapeo.
2. Si el usuario descarga y modifica el mapeo, ya puede ajustarlo manualmente. La mejora es que se pre-rellene correctamente desde el principio.

**Configuración sugerida en la app (sidebar)**
- Campo "Cuenta SS empresa — Centro Sevilla": `64200XXX`
- Campo "Cuenta SS empresa — Centro Jerez": `64200YYY`
- El usuario introduce las cuentas una vez; la app las guarda en sesión y las aplica al generar el mapeo.

**Archivos afectados**
- `app.py` → sidebar, paso de procesamiento
- `core/odoo_export.py` → `build_employee_rows()`

**Complejidad:** Baja · ~2h

---

### A4 · Campo EMPRESA en asiento = contacto/empleado correspondiente

**Situación actual**
La columna `partner_odoo` de la plantilla de mapeo contiene el nombre del empleado (texto libre). La función `_resolve_partner_ids()` busca en `res.partner` por nombre exacto. Si el nombre en Odoo no coincide exactamente, el campo queda vacío.

**Lo que pide el cliente**
Cada línea del asiento debe tener el empleado correcto en el campo EMPRESA de Odoo (`partner_id`).

**Propuesta de implementación**
Los empleados de Odoo (`hr.employee`) tienen un campo `address_home_id` que es su `res.partner` privado. Una vez que el paso 3 de la app ha realizado el emparejamiento y tenemos el `employee_id_odoo`, podemos leer `address_home_id` directamente y usarlo como `partner_id` en las líneas del asiento.

Esto elimina la búsqueda por nombre y garantiza que el partner correcto se asocie incluso cuando el nombre difiere.

El flujo quedaría:
1. Paso 3: emparejamiento → `employee_id_odoo` disponible en `st.session_state.odoo_matches`.
2. Paso 5: al crear el asiento, se lee `address_home_id` para cada empleado emparejado y se usa como `partner_id` en las líneas.

**Archivos afectados**
- `core/odoo_accounting.py` → `build_payroll_move_lines()`, `create_payroll_move_in_odoo()`
- `app.py` → paso 5, se pasa el diccionario `worker_number → partner_id` al construir las líneas

**Complejidad:** Media · ~2h

---

### A5 · Fecha contable = último día del mes

**Situación actual**
El sidebar tiene un `date_input` con valor por defecto = fecha de hoy. El usuario puede cambiarlo manualmente.

**Lo que pide el cliente**
Que la fecha contable sea el último día del mes que se está contabilizando (no la fecha de hoy).

**Propuesta de implementación**
Añadir un checkbox en el sidebar: **"Usar último día del mes nómina"**. Cuando está activo, la fecha se calcula automáticamente como el último día del mes detectado en el Excel/PDF (campo `period_month` / `period_year`). Si no está detectado aún, se usa el mes actual.

La detección del periodo ocurre en el paso 1 (`parse_payroll_excel`); el sidebar se renderiza antes, así que se propone lo siguiente:
- Valor por defecto del `date_input` = último día del mes actual.
- Tras procesar los archivos, si el periodo detectado difiere del actual, se muestra un aviso con opción de actualizar la fecha.

**Archivos afectados**
- `app.py` → sidebar, lógica de fecha

**Complejidad:** Baja · ~1h

---

### A6 · Borrador de asiento descargable, editable y re-importable

**Situación actual**
En el paso 5, el modo simulación muestra un `st.dataframe` (solo lectura) con las líneas del asiento. No es posible modificarlo ni exportarlo para revisión externa.

El Excel que ya existe ("Descargar Excel de importación para Odoo") está en formato de importación nativa de Odoo y no está pensado para ser re-ingestado por la app.

**Lo que pide el cliente**
Flujo completo de revisión/corrección del asiento **fuera de la app**:
1. La app genera un **borrador del asiento en Excel** con todas las líneas calculadas.
2. El usuario lo descarga, lo revisa y lo edita en Excel (añade filas de embargo, corrige cuentas, ajusta importes, etc.).
3. El usuario **sube el Excel editado** a la app.
4. La app lee las líneas del archivo subido y las usa para **crear el asiento real en Odoo**, en lugar de recalcularlo desde cero.

Este flujo garantiza que lo que se sube a Odoo es exactamente lo que el usuario ha revisado y aprobado.

**Propuesta de implementación**

*Paso 5 — nueva estructura:*

**Sub-paso 5a — Generar y descargar borrador**
- Botón "Descargar borrador asiento (Excel)" que genera un Excel con columnas:
  `centro`, `account_code`, `partner_name`, `name`, `debit`, `credit`, `line_role`, `worker_number`
- Una hoja por centro de trabajo + hoja de instrucciones con las columnas obligatorias.
- El usuario puede añadir filas nuevas, modificar cualquier campo, eliminar líneas.

**Sub-paso 5b — (Opcional) Subir borrador revisado**
- `st.file_uploader` para el Excel editado (mismas columnas).
- Si el usuario sube un borrador, la app lo lee y usa esas líneas en lugar de las calculadas automáticamente.
- Si no sube nada, usa el cálculo automático (comportamiento actual).
- Se muestra una preview de las líneas que se van a subir (con totales debe/haber y alerta si no cuadra).

**Sub-paso 5c — Crear en Odoo**
- Botón "Crear asiento en Odoo" que usa las líneas del borrador subido (o las calculadas si no hay borrador).
- Checkbox "Modo simulación" para hacer una pasada en seco antes de la creación real.

**Formato del Excel borrador**
```
| centro | account_code | partner_name | name | debit | credit | line_role | worker_number |
```
- `account_code`: código de cuenta tal como está en Odoo (la app lo resuelve a ID internamente).
- `partner_name`: nombre del partner en Odoo (la app lo resuelve a ID internamente).
- `line_role`: `salary`, `ss_company`, `remuneration`, `irpf`, `embargo`, etc. (determina etiquetas fiscales Modelo 111).
- Filas añadidas manualmente por el usuario: `line_role` = `manual` (sin etiquetas fiscales automáticas).

**Archivos afectados**
- `app.py` → paso 5, flujo completo
- `core/odoo_accounting.py` → función nueva `read_move_draft_xlsx()` para leer el borrador
- `core/odoo_export.py` → función nueva `generate_move_draft_xlsx()` para generar el borrador

**Complejidad:** Media-Alta · ~4h

---

## MÓDULO B — Empleados

### B1 · Restringir empleados por jefe de almacén (Sevilla / Jerez)

**Situación actual**
En Odoo, los jefes de almacén pueden ver empleados de cualquier centro de trabajo, sin restricción por su ámbito de responsabilidad.

**Lo que pide el cliente**
Que en Odoo el jefe de almacén de Jerez no pueda ver los registros de empleados de Sevilla, y viceversa. La app Streamlit no necesita control de acceso (la usan únicamente los administradores de la empresa).

**Propuesta de implementación**
La restricción se configura directamente en Odoo mediante **reglas de registro (Record Rules)** sobre el modelo `hr.employee`:

1. Crear una regla de registro para el grupo "Jefe Almacén Sevilla" que filtre `work_location_id` o `department_id` al centro de Sevilla.
2. Crear la misma regla para el grupo "Jefe Almacén Jerez" con su centro correspondiente.
3. Los usuarios administradores de Odoo (y la app Streamlit, que usa credenciales de administrador) no se ven afectados.

Esta configuración se realiza desde el menú **Ajustes → Técnico → Reglas de registro** en Odoo (requiere modo desarrollador activo).

**Archivos afectados**
- Ninguno en la app Streamlit.
- Configuración 100% en Odoo (reglas de registro, grupos de usuarios).

**Complejidad:** Baja · ~1h (configuración Odoo, sin código)

---

### B2 · Mostrar número de empleado

**Situación actual**
El número de empleado (`n_trabajador`) aparece en la tabla de emparejamiento pero no de forma destacada en la vista de nóminas PDF.

**Lo que pide el cliente**
Que el número de empleado sea visible.

**Propuesta de implementación**
El campo ya existe en todos los dataframes. Se añade como primera columna en:
- Tabla de páginas PDF detectadas (paso 1).
- Tabla de emparejamiento (paso 3).
- Log de subida a Odoo (paso 4).
- Solicitudes de firma (paso 6).

**Archivos afectados**
- `app.py` → columnas de los dataframes

**Complejidad:** Baja · ~1h

---

### B3 · Cuenta 465 según CCC (terminación 375 → 46500xxx / terminación 213 → 46510xxx)

**Situación actual**
La cuenta `cuenta_remuneraciones` se genera con `safe_account_465(worker_number)` → siempre `46510{worker_number}`.

**Lo que pide el cliente**
- Empleados en **CCC 1** (terminado en 375) → cuenta `46500{n_trabajador}`
- Empleados en **CCC 2** (terminado en 213) → cuenta `46510{n_trabajador}`

El CCC (Código de Cuenta de Cotización) identifica el centro/grupo de cotización.

**Aclaración recibida**
El CCC se introduce **manualmente** y está relacionado con el **centro de trabajo** (`centro` del Excel).

**Propuesta de implementación**
Se añade en el sidebar una tabla de configuración simple "centro de trabajo → CCC (últimos 3 dígitos)":

| Centro de trabajo | CCC termina en |
|---|---|
| Almacén Sevilla | 375 |
| Almacén Jerez | 213 |

Con esta tabla, la lógica en `build_employee_rows()` determina el prefijo 465 de cada empleado a partir de su `emp.center`:
- Termina en 375 → `46500{n_trabajador}`
- Termina en 213 → `46510{n_trabajador}`
- No configurado → comportamiento actual (`46510{n_trabajador}`)

Esta configuración se puede persistir en `.env.local` para no tener que reintroducirla cada mes.

**Archivos afectados**
- `app.py` → sidebar (tabla centro→CCC), paso 1 (pasar configuración a `build_employee_rows`)
- `core/odoo_export.py` → `build_employee_rows()` (lógica de selección prefijo 465)
- `core/utils.py` → adaptar `safe_account_465()` para aceptar prefijo como parámetro

**Complejidad:** Baja · ~2h ✅ Aclarado

---

### B4 · Emparejamiento con Odoo por DNI o n_trabajador aunque el nombre no coincida

**Situación actual**
El emparejador ya busca en este orden:
1. Por DNI (campo seleccionable, candidatos: `identification_id`, `vat`, `x_dni`).
2. Por número de trabajador (campo seleccionable: `barcode`, `employee_number`, etc.).
3. Por nombre (último recurso).

El cliente confirma que en Odoo el DNI/NIF está en el campo **`identification_id`** del modelo `hr.employee`.

**Acción concreta**
- En el selector "Campo DNI/NIF en Odoo" del paso 3, preseleccionar `identification_id` como primera opción por defecto.
- Verificar que el emparejador lee `identification_id` directamente de `hr.employee` (sin pasar por `res.partner`).
- Eliminar la búsqueda secundaria por `vat` en `res.partner` (no aplica en este caso).

**Nota**: El sistema de fallback DNI → n_trabajador → nombre ya funciona; el ajuste es asegurarse de que `identification_id` queda como campo por defecto y se resuelve correctamente.

**Archivos afectados**
- `core/odoo_employee_matcher.py` → `match_employees()`, `_find_match()`
- `app.py` → paso 3, orden de candidatos DNI

**Complejidad:** Baja · ~2h

---

### B5 · Trasladar etiquetas de contacto a campos nativos de empleado en Odoo

**Situación actual**
Los empleados estaban dados de alta en Odoo como contactos (`res.partner`). El cliente les asignaba etiquetas/categorías en el contacto para clasificarlos (tipo de contrato, puesto, estado, etc.). Al migrarlos a empleados (`hr.employee`), esas etiquetas se han perdido o quedado desvinculadas.

**Lo que pide el cliente**
Trasladar la información que tenía en las etiquetas de contacto a los campos nativos equivalentes que existen en `hr.employee`:
- Etiqueta "tipo de contrato" → campo `contract_type_id` (o contrato activo en `hr.contract`).
- Etiqueta "puesto" → campo `job_id` (`hr.job`).
- Etiqueta "estado" → campo `active` o `employee_type`.

**Propuesta de implementación**
Esta es una tarea de configuración/migración de datos en Odoo, no un cambio en la app Streamlit:

1. Revisar las etiquetas (`res.partner.category_id`) que el cliente usaba e identificar a qué campo de `hr.employee` corresponde cada una.
2. Para cada empleado, rellenar el campo nativo correspondiente (`job_id`, `contract_type_id`, `active`) con el valor equivalente a la etiqueta que tenía como contacto.
3. Esta operación puede hacerse manualmente desde la ficha de cada empleado en Odoo, o masivamente mediante una importación CSV desde `Empleados → Importar`.

**Archivos afectados**
- Ninguno en la app Streamlit.
- Operación de migración de datos en Odoo (manual o importación CSV).

**Complejidad:** Baja · ~2h (según volumen de empleados y número de etiquetas a mapear)

---

## MÓDULO C — Nóminas

### C1 · Nombre del empleado en el nombre del archivo PDF

**Situación actual**
Los PDFs individuales se nombran como: `{DNI}-{mm}-{yyyy}.pdf`
Ejemplo: `12345678A-04-2026.pdf`

**Lo que pide el cliente**
Incluir también el nombre de la persona.
Ejemplo: `12345678A-JUAN-GARCIA-LOPEZ-04-2026.pdf`

**Propuesta de implementación**
En `payroll_pdf.py` → `split_pdf_to_zip()` y en `app.py` → `build_split_pdfs_dict()`, cambiar la construcción del nombre de fichero:

```python
# Actual
filename = f"{slugify_filename(base)}-{month:02d}-{year:04d}.pdf"

# Nuevo
nombre_slug = slugify_filename(page_info.employee_name or "")
filename = f"{slugify_filename(base)}-{nombre_slug}-{month:02d}-{year:04d}.pdf"
```

La función `slugify_filename` ya elimina caracteres especiales, tildes y espacios; convierte a mayúsculas o minúsculas según convención.

**Archivos afectados**
- `core/payroll_pdf.py` → `split_pdf_to_zip()`
- `app.py` → `build_split_pdfs_dict()`

**Complejidad:** Muy baja · ~30min

---

## Resumen de tareas y estado

| ID | Módulo | Tarea | Complejidad | Estado |
|----|--------|-------|-------------|--------|
| A1 | Asiento | Cuentas 46510xxx vs 46500000 según si existe en Odoo | Media | ✅ Listo |
| A2 | Asiento | Cuenta 640 según departamento Odoo (multi-almacén → editor simulación) | Media | ✅ Aclarado |
| A3 | Asiento | Cuenta SS diferenciada Sevilla/Jerez | Baja | ✅ Listo |
| A4 | Asiento | EMPRESA en asiento = partner del empleado Odoo | Media | ✅ Listo |
| A5 | Asiento | Fecha = último día del mes nómina | Baja | ✅ Listo |
| A6 | Asiento | Borrador asiento descargable → edita en Excel → re-sube → crea en Odoo | Media-Alta | ✅ Listo |
| B1 | Empleados | Restringir vistas por jefe almacén — Record Rules en Odoo (sin cambios en app) | Baja | ✅ Aclarado |
| B2 | Empleados | Mostrar número de empleado | Baja | ✅ Listo |
| B3 | Empleados | Cuenta 465 según CCC configurado por centro de trabajo | Baja | ✅ Aclarado |
| B4 | Empleados | Emparejamiento por `vat` (DNI en campo IVA Odoo) | Baja | ✅ Listo |
| B5 | Empleados | Mostrar tipo contrato, puesto, estado en tabla | Baja-Media | ✅ Listo |
| C1 | Nóminas | Nombre en nombre de archivo PDF | Muy baja | ✅ Listo |

---

## Orden de implementación sugerido

1. **C1** — Nombre en PDF (30 min, impacto inmediato y sin riesgo).
2. **A5** — Fecha último día del mes (1h).
3. **B2** — Mostrar n_trabajador (1h).
4. **B3** — Cuenta 465 por CCC/centro (2h).
5. **B4** — Emparejamiento por `vat` (2h).
6. **A3** — Cuenta SS por centro Sevilla/Jerez (2h).
7. **A2** — Cuenta 640 por departamento Odoo (4h).
8. **A4** — Partner en asiento desde hr.employee (2h).
9. **A1** — Cuentas 46510 vs 46500 según existencia en Odoo (3h).
10. **A6** — Borrador asiento: generar Excel → usuario edita → re-sube → crea en Odoo (4h).
11. **B5** — Campos contrato/puesto/estado en tabla (2h).
12. **B1** — Record Rules en Odoo para restringir empleados por centro (1h configuración Odoo).

**Estimación total:** ~24h de desarrollo + ~1h de configuración Odoo.
