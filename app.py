from __future__ import annotations

import base64
import hashlib
import io
import os
import tempfile
from datetime import date as dt_date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from core.odoo_attachments import delete_unsigned_attachment, upload_all_payslips
from core.odoo_accounting import build_payroll_move_lines, build_payroll_moves_by_center, create_payroll_move_in_odoo
from core.odoo_client import OdooClient
from core.odoo_employee_matcher import (
    apply_manual_mapping,
    get_available_worker_fields,
    match_employees,
)
from core.odoo_export import (
    build_employee_rows,
    generate_odoo_import_xlsx,
    mapping_template_xlsx,
    read_mapping_xlsx,
)
from core.payroll_excel import parse_payroll_excel
from core.payroll_pdf import extract_pdf_pages, split_pdf_to_zip
from core.signature_delivery import (
    build_sign_link,
    build_whatsapp_url,
    normalize_base_url,
    render_message,
)
from core.signature_pdf import insert_signature_into_pdf
from core.signature_repository import (
    add_event,
    create_request,
    get_request_by_token_hash,
    init_db,
    list_requests,
    mark_error,
    mark_opened,
    mark_signed,
    mark_uploaded,
    save_artifact,
)
from core.signature_tokens import create_token, expires_at, is_expired, token_hash
from core.state import clear_processing_state, init_state
from core.utils import mask_dni

_LOGO_PATH = Path(__file__).parent / "logo-enteza.png"
_logo_img = Image.open(_LOGO_PATH) if _LOGO_PATH.exists() else None

st.set_page_config(
    page_title="Enteza - RRHH",
    page_icon=_logo_img,
    layout="wide",
)

if _logo_img:
    st.logo(str(_LOGO_PATH), size="large")

st.title("Enteza - RRHH")
st.caption("Aplicacion local: los PDF y Excel se procesan en el servidor donde ejecutes Streamlit.")

init_state()
init_db()


def load_odoo_config_from_env_file() -> dict[str, str]:
    config = {
        "url": "",
        "db": "",
        "username": "",
        "password": "",
    }
    env_path = Path(".env.local")
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "ODOO_URL":
                config["url"] = value
            elif key == "ODOO_DB":
                config["db"] = value
            elif key == "ODOO_USER":
                config["username"] = value
            elif key == "ODOO_PASSWORD":
                config["password"] = value

    if os.getenv("ODOO_URL"):
        config["url"] = os.getenv("ODOO_URL", "")
    if os.getenv("ODOO_DB"):
        config["db"] = os.getenv("ODOO_DB", "")
    if os.getenv("ODOO_USER"):
        config["username"] = os.getenv("ODOO_USER", "")
    if os.getenv("ODOO_PASSWORD"):
        config["password"] = os.getenv("ODOO_PASSWORD", "")

    return config


def load_sign_base_url_from_env_file() -> str:
    env_path = Path(__file__).parent / ".env.local"
    value = ""
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            if key.strip() == "SIGN_BASE_URL":
                value = raw_value.strip().strip('"').strip("'")
                break

    if os.getenv("SIGN_BASE_URL"):
        value = os.getenv("SIGN_BASE_URL", "")

    return value.strip()


def fetch_odoo_employee_phones(odoo: OdooClient, employee_ids: list[int]) -> dict[int, str]:
    result: dict[int, str] = {}
    if not employee_ids:
        return result

    fields_info = odoo.get_employee_fields()
    candidate_fields = ["mobile_phone", "mobile", "work_phone", "phone"]
    available_fields = [f for f in candidate_fields if f in fields_info]
    if not available_fields:
        return result

    rows = odoo.read("hr.employee", employee_ids, ["id"] + available_fields)
    for row in rows:
        emp_id = int(row.get("id"))
        phone_val = ""
        for field_name in available_fields:
            value = row.get(field_name)
            if value:
                phone_val = str(value).strip()
                break
        result[emp_id] = phone_val

    return result


def _save_signature_image(signature_image_data, out_path: Path) -> bytes:
    image = Image.fromarray(signature_image_data.astype("uint8"), mode="RGBA")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG")
    return out_path.read_bytes()


def _render_public_sign_page(token_value: str) -> None:
    if _logo_img:
        st.image(_logo_img, width=160)
    st.title("Firma de nomina")
    st.caption("Firma manuscrita desde movil")

    hashed = token_hash(token_value)
    request = get_request_by_token_hash(hashed)
    if not request:
        st.error("Enlace invalido o no existente.")
        return
    if is_expired(request["token_expires_at"]):
        st.error("Enlace expirado. Contacta con RRHH.")
        return

    if request["status"] == "uploaded_odoo":
        st.success("Esta nomina ya fue firmada y enviada correctamente.")
        return

    mark_opened(request["id"])
    add_event(request["id"], "opened_link", {})

    pdf_path = Path(request["pdf_original_path"])
    if not pdf_path.exists():
        st.error("No se encontro el PDF de nomina para esta solicitud.")
        return

    st.write(f"Empleado: {request['employee_name']}")
    st.write(f"Periodo: {int(request['period_month']):02d}/{int(request['period_year'])}")

    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    st.markdown("### Vista previa de nomina")
    components.html(
        f"""
        <div style=\"width:100%;\"> 
          <iframe
            id=\"nomina-preview\"
            src=\"data:application/pdf;base64,{pdf_b64}\"
            width=\"100%\"
            style=\"border:1px solid #ddd;border-radius:8px;\"
          ></iframe>
        </div>
        <script>
          (function() {{
            const iframe = document.getElementById('nomina-preview');
            if (!iframe) return;
            const w = window.innerWidth || 1200;
            let h = 620;
            if (w <= 480) h = 380;
            else if (w <= 768) h = 460;
            else if (w <= 1024) h = 540;
            iframe.style.height = h + 'px';
          }})();
        </script>
        """,
        height=640,
    )

    st.download_button(
        "Descargar / ver nomina",
        data=pdf_bytes,
        file_name=pdf_path.name,
        mime="application/pdf",
        key=f"download_pdf_{request['id']}",
    )

    st.markdown("### Firma manuscrita")
    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",
        stroke_width=2,
        stroke_color="#111111",
        background_color="#ffffff",
        height=220,
        width=520,
        drawing_mode="freedraw",
        key=f"canvas_{request['id']}",
    )

    consent = st.checkbox("He revisado la nomina y confirmo mi firma", value=False)
    if st.button("Confirmar firma", type="primary"):
        if canvas_result.image_data is None:
            st.error("Debes firmar antes de confirmar.")
            return
        if not consent:
            st.error("Debes aceptar la confirmacion para continuar.")
            return

        signature_dir = Path("data/signature_pdfs/signatures")
        signed_dir = Path("data/signature_pdfs/signed")
        signature_path = signature_dir / f"{request['id']}.png"
        signed_pdf_path = signed_dir / f"{pdf_path.stem}-firmada.pdf"

        try:
            signature_png_bytes = _save_signature_image(canvas_result.image_data, signature_path)
            signed_dir.mkdir(parents=True, exist_ok=True)
            insert_signature_into_pdf(
                pdf_input_path=pdf_path,
                signature_png_bytes=signature_png_bytes,
                pdf_output_path=signed_pdf_path,
                page_index=0,
                x=350,
                y=690,
                width=180,
                height=60,
            )

            odoo_cfg = load_odoo_config_from_env_file()
            client = OdooClient(
                odoo_cfg["url"],
                odoo_cfg["db"],
                odoo_cfg["username"],
                odoo_cfg["password"],
            )
            client.authenticate()
            from core.odoo_attachments import upload_employee_payslip_attachment

            upload_result = upload_employee_payslip_attachment(
                odoo=client,
                employee_id=int(request["employee_id_odoo"]),
                filename=signed_pdf_path.name,
                pdf_bytes=signed_pdf_path.read_bytes(),
                month=int(request["period_month"]),
                year=int(request["period_year"]),
                duplicate_policy="replace",
                dry_run=False,
            )

            mark_signed(request["id"])
            mark_uploaded(request["id"], int(upload_result.get("attachment_id") or 0))
            save_artifact(request["id"], str(signature_path), str(signed_pdf_path))

            deleted = delete_unsigned_attachment(
                odoo=client,
                employee_id=int(request["employee_id_odoo"]),
                signed_filename=signed_pdf_path.name,
            )
            add_event(
                request["id"],
                "signed_and_uploaded",
                {"filename": signed_pdf_path.name, "unsigned_deleted": deleted},
            )
            st.rerun()
        except Exception as exc:
            mark_error(request["id"])
            add_event(request["id"], "error", {"message": str(exc)})
            st.error(f"No se pudo completar la firma/subida: {exc}")


query_token = st.query_params.get("token")
if query_token:
    _render_public_sign_page(str(query_token))
    st.stop()

with st.sidebar:
    st.header("Parametros contables")
    default_today = dt_date.today()
    accounting_date = st.date_input("Fecha del asiento", value=default_today)
    journal = st.text_input("Diario Odoo", value="NOMINAS")
    reference = st.text_input(
        "Referencia del asiento",
        value=f"NOMINA {default_today.month:02d}/{default_today.year}",
    )
    aggregate_ss = st.checkbox("Agrupar credito del TC1 en una sola linea 476", value=True)
    st.divider()
    st.markdown(
        "**Flujo recomendado**\n\n"
        "1. Carga PDF y Excel.\n"
        "2. Descarga y revisa el mapeo de cuentas.\n"
        "3. Si modificas el mapeo, vuelve a subirlo.\n"
        "4. Descarga el ZIP de nominas y el Excel de importacion Odoo.\n"
        "5. Conecta con Odoo y sube las nominas individuales."
    )


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_split_pdfs_dict(
    pdf_path: Path, pdf_pages, default_month: int, default_year: int
) -> tuple[dict[str, bytes], dict[str, str]]:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    result: dict[str, bytes] = {}
    worker_to_filename: dict[str, str] = {}
    used_names: set[str] = set()

    for page_info in pdf_pages:
        writer = PdfWriter()
        writer.add_page(reader.pages[page_info.page_index])
        page_buf = io.BytesIO()
        writer.write(page_buf)
        month = page_info.month or default_month
        year = page_info.year or default_year
        base = page_info.dni or f"trabajador_{page_info.worker_number or page_info.page_index + 1:>03}"
        from core.utils import slugify_filename

        filename = f"{slugify_filename(base)}-{month:02d}-{year:04d}.pdf"
        if filename in used_names:
            stem = filename[:-4]
            counter = 2
            while f"{stem}_{counter}.pdf" in used_names:
                counter += 1
            filename = f"{stem}_{counter}.pdf"
        used_names.add(filename)
        result[filename] = page_buf.getvalue()
        if page_info.worker_number:
            worker_to_filename[str(page_info.worker_number)] = filename

    return result, worker_to_filename


with st.expander("1) Cargar archivos de entrada", expanded=not st.session_state.processed):
    pdf_file = st.file_uploader("PDF completo con todas las nominas", type=["pdf"], disabled=st.session_state.processed)
    excel_file = st.file_uploader("Excel de detalle de nomina", type=["xlsx"], disabled=st.session_state.processed)
    mapping_file = st.file_uploader("Mapeo de cuentas revisado (opcional)", type=["xlsx"], disabled=st.session_state.processed)

    if not st.session_state.processed and (not pdf_file or not excel_file):
        st.info("Sube el PDF de nominas y el Excel de detalle para iniciar el procesamiento.")
        st.stop()

    if st.button("Procesar nominas y generar ficheros", type="primary", disabled=st.session_state.processed):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pdf_path = tmpdir_path / "nominas.pdf"
            xlsx_path = tmpdir_path / "detalle_nomina.xlsx"
            pdf_path.write_bytes(pdf_file.getvalue())
            xlsx_path.write_bytes(excel_file.getvalue())

            mapping_path: Path | None = None
            if mapping_file:
                mapping_path = tmpdir_path / "mapeo.xlsx"
                mapping_path.write_bytes(mapping_file.getvalue())

            with st.spinner("Leyendo PDF y Excel..."):
                pdf_pages = extract_pdf_pages(pdf_path)
                employees, metadata = parse_payroll_excel(xlsx_path)

            detected_month = metadata.get("period_month") or next(
                (p.month for p in pdf_pages if p.month), accounting_date.month
            )
            detected_year = metadata.get("period_year") or next(
                (p.year for p in pdf_pages if p.year), accounting_date.year
            )

            employee_rows = build_employee_rows(employees, pdf_pages)
            if mapping_path:
                custom_mapping = read_mapping_xlsx(mapping_path)
                for row in employee_rows:
                    custom = custom_mapping.get(str(row["n_trabajador"]))
                    if custom:
                        row.update({k: v for k, v in custom.items() if v is not None})

            pdf_workers = {p.worker_number for p in pdf_pages if p.worker_number}
            excel_workers = {e.worker_number for e in employees}
            missing_pdf = sorted(excel_workers - pdf_workers, key=lambda x: int(x) if x.isdigit() else 0)
            missing_excel = sorted(pdf_workers - excel_workers, key=lambda x: int(x) if x.isdigit() else 0)

            mapping_bytes = mapping_template_xlsx(employee_rows)

            zip_bytes = split_pdf_to_zip(pdf_path, pdf_pages, detected_month, detected_year)

            split_pdfs, worker_pdf_filenames = build_split_pdfs_dict(
                pdf_path, pdf_pages, detected_month, detected_year
            )

            odoo_bytes, summary = generate_odoo_import_xlsx(
                employees=employees,
                employee_rows=employee_rows,
                month=detected_month,
                year=detected_year,
                journal=journal,
                date=accounting_date.isoformat(),
                reference=reference,
                aggregate_ss=aggregate_ss,
            )

            st.session_state.processed = True
            st.session_state.period_month = detected_month
            st.session_state.period_year = detected_year
            st.session_state.pdf_pages = pdf_pages
            st.session_state.excel_employees = employees
            st.session_state.employee_rows = employee_rows
            st.session_state.accounting_summary = summary
            st.session_state.mapping_xlsx_bytes = mapping_bytes
            st.session_state.odoo_import_xlsx_bytes = odoo_bytes
            st.session_state.zip_payslips_bytes = zip_bytes
            st.session_state.split_pdfs = split_pdfs
            st.session_state.worker_pdf_filenames = worker_pdf_filenames
            st.session_state.pdf_hash = file_hash(pdf_file.getvalue())
            st.session_state.excel_hash = file_hash(excel_file.getvalue())
            st.session_state.odoo_matches = None
            st.session_state.odoo_upload_log = None

            st.session_state._warnings = {
                "missing_pdf": missing_pdf,
                "missing_excel": missing_excel,
            }

        st.rerun()


if not st.session_state.processed:
    st.stop()

month = st.session_state.period_month
year = st.session_state.period_year
warnings = getattr(st.session_state, "_warnings", {})

st.success(
    f"Periodo detectado: {month:02d}/{year}. "
    f"{len(st.session_state.pdf_pages)} paginas PDF, "
    f"{len(st.session_state.excel_employees)} trabajadores Excel."
)

if warnings.get("missing_pdf"):
    st.warning(
        f"Trabajadores presentes en Excel y no localizados en PDF: {', '.join(warnings['missing_pdf'])}"
    )
if warnings.get("missing_excel"):
    st.warning(
        f"Trabajadores presentes en PDF y no localizados en Excel: {', '.join(warnings['missing_excel'])}"
    )

col1, col2 = st.columns(2)
with col1:
    st.subheader("Paginas PDF detectadas")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "pagina": p.page_index + 1,
                    "n_trabajador": p.worker_number,
                    "dni": p.dni,
                    "nombre": p.employee_name,
                    "mes": p.month,
                    "ano": p.year,
                }
                for p in st.session_state.pdf_pages
            ]
        ),
        use_container_width=True,
        height=360,
    )

with col2:
    st.subheader("Resumen Excel / mapeo")
    st.dataframe(
        pd.DataFrame(st.session_state.employee_rows),
        use_container_width=True,
        height=360,
    )

summary = st.session_state.accounting_summary
if summary["is_balanced"]:
    st.success(
        f"Asiento cuadrado. Debe: {summary['total_debit']:.2f} / "
        f"Haber: {summary['total_credit']:.2f} / "
        f"Diferencia: {summary['balance']:.2f}. "
        f"Lineas: {summary['line_count']}"
    )
else:
    st.error(
        f"ASIENTO NO CUADRADO: revisar deducciones no mapeadas o conceptos especiales. "
        f"Debe: {summary['total_debit']:.2f} / Haber: {summary['total_credit']:.2f} / "
        f"Diferencia: {summary['balance']:.2f}"
    )

st.subheader("Descargas")
col_a, col_b, col_c = st.columns(3)

with col_a:
    st.download_button(
        "Descargar ZIP con nominas individuales",
        data=st.session_state.zip_payslips_bytes,
        file_name=f"nominas_individuales_{year}_{month:02d}.zip",
        mime="application/zip",
        key="download_zip_nominas",
    )

with col_b:
    st.download_button(
        "Descargar plantilla de mapeo de cuentas",
        data=st.session_state.mapping_xlsx_bytes,
        file_name=f"mapeo_nominas_{year}_{month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_mapeo_cuentas",
    )

with col_c:
    st.download_button(
        "Descargar Excel de importacion para Odoo",
        data=st.session_state.odoo_import_xlsx_bytes,
        file_name=f"asiento_odoo_nomina_{year}_{month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_asiento_odoo",
    )

st.divider()

odoo_env = load_odoo_config_from_env_file()

with st.expander("2) Conexion con Odoo 15 Community", expanded=False):
    st.markdown(
        "Introduce las credenciales de Odoo o configurales en `.streamlit/secrets.toml`."
    )
    col_odoo1, col_odoo2 = st.columns(2)
    with col_odoo1:
        odoo_url = st.text_input(
            "URL de Odoo",
            value=odoo_env.get("url", ""),
            placeholder="https://odoo.midominio.com",
        )
        odoo_db = st.text_input(
            "Base de datos",
            value=odoo_env.get("db", ""),
        )
    with col_odoo2:
        odoo_user = st.text_input(
            "Usuario",
            value=odoo_env.get("username", ""),
        )
        odoo_pass = st.text_input(
            "Contrasena / API key",
            value=odoo_env.get("password", ""),
            type="password",
        )

    if st.button("Probar conexion", type="primary"):
        if not all([odoo_url, odoo_db, odoo_user, odoo_pass]):
            st.error("Completa todos los campos de conexion.")
        else:
            try:
                client = OdooClient(odoo_url, odoo_db, odoo_user, odoo_pass)
                uid = client.authenticate()
                has_hr = client.check_hr_module()
                st.success(f"Conexion correcta. Usuario autenticado UID: {uid}")
                if has_hr:
                    st.info("Modulo RRHH (hr.employee) disponible.")
                else:
                    st.warning("No se detecto el modulo hr.employee. La subida de adjuntos podria fallar.")
                st.session_state._odoo_client = client
                st.session_state._odoo_connected = True
            except ConnectionError as e:
                st.error(str(e))
            except PermissionError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Error inesperado: {e}")

with st.expander("3) Emparejar empleados con Odoo", expanded=False):
    if not st.session_state.get("_odoo_connected"):
        st.info("Primero prueba la conexion con Odoo en el paso anterior.")
    else:
        odoo: OdooClient = st.session_state._odoo_client
        worker_fields = get_available_worker_fields(odoo)

        try:
            employee_fields_info = odoo.get_employee_fields()
        except Exception as exc:
            st.error(f"No se pudieron leer los campos de hr.employee: {exc}")
            st.stop()
        dni_candidates = [f for f in ["identification_id", "vat", "x_dni", "x_studio_dni"] if f in employee_fields_info]
        name_candidates = [f for f in ["name"] if f in employee_fields_info]

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            dni_field = st.selectbox(
                "Campo DNI/NIF en Odoo",
                options=dni_candidates if dni_candidates else [""],
                index=0,
                disabled=not dni_candidates,
            )
        with col_f2:
            worker_field_options = [None] + worker_fields
            worker_field = st.selectbox(
                "Campo numero trabajador en Odoo",
                options=worker_field_options,
            )
        with col_f3:
            name_field = st.selectbox(
                "Campo nombre en Odoo",
                options=name_candidates if name_candidates else [""],
                index=0,
                disabled=not name_candidates,
            )

        manual_mapping_file = st.file_uploader("Mapeo manual de empleados (opcional)", type=["xlsx"])

        if st.button("Buscar empleados en Odoo", type="primary"):
            if not dni_field:
                st.error("Selecciona un campo DNI valido.")
            else:
                with st.spinner("Buscando empleados en Odoo..."):
                    matches = match_employees(
                        odoo=odoo,
                        pdf_pages=st.session_state.pdf_pages,
                        excel_employees=st.session_state.excel_employees,
                        dni_field=dni_field,
                        worker_field=worker_field,
                        name_field=name_field or "name",
                    )

                    worker_pdf_filenames = st.session_state.get("worker_pdf_filenames", {})
                    if worker_pdf_filenames:
                        for item in matches:
                            mapped_filename = worker_pdf_filenames.get(str(item.worker_number))
                            if mapped_filename:
                                item.filename = mapped_filename

                    if manual_mapping_file:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            tmp_path = Path(tmpdir) / "manual_mapping.xlsx"
                            tmp_path.write_bytes(manual_mapping_file.getvalue())
                            wb = pd.read_excel(tmp_path)
                            manual_rows = wb.to_dict(orient="records")
                            matches = apply_manual_mapping(matches, manual_rows, odoo)

                    st.session_state.odoo_matches = matches
                    st.session_state._odoo_dni_field = dni_field
                    st.session_state._odoo_worker_field = worker_field
                    st.session_state._odoo_name_field = name_field or "name"
                st.rerun()

        if st.session_state.odoo_matches:
            matches = st.session_state.odoo_matches
            match_df = pd.DataFrame(
                [
                    {
                        "n_trabajador": m.worker_number,
                        "DNI": mask_dni(m.dni) if m.dni else "",
                        "nombre_pdf": m.employee_name_pdf,
                        "nombre_excel": m.employee_name_excel,
                        "archivo_pdf": m.filename,
                        "employee_id_odoo": m.employee_id_odoo,
                        "employee_name_odoo": m.employee_name_odoo,
                        "criterio_match": m.match_method,
                        "estado_match": m.match_status,
                        "observaciones": m.observations,
                    }
                    for m in matches
                ]
            )

            st.subheader("Tabla de emparejamiento")
            st.dataframe(match_df, use_container_width=True, height=400)

            match_counts = pd.Series([m.match_status for m in matches]).value_counts()
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("MATCH_OK", int(match_counts.get("MATCH_OK", 0)))
            col_m2.metric("NO_ENCONTRADO", int(match_counts.get("NO_ENCONTRADO", 0)))
            col_m3.metric("AMBIGUO", int(match_counts.get("AMBIGUO", 0)))
            col_m4.metric("Total", len(matches))

            match_xlsx_buf = io.BytesIO()
            with pd.ExcelWriter(match_xlsx_buf, engine="openpyxl") as writer:
                match_df.to_excel(writer, sheet_name="emparejamiento", index=False)
            match_xlsx_buf.seek(0)

            st.download_button(
                "Descargar tabla de emparejamiento",
                data=match_xlsx_buf.getvalue(),
                file_name=f"emparejamiento_odoo_{year}_{month:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_matches",
            )

            manual_template_buf = io.BytesIO()
            with pd.ExcelWriter(manual_template_buf, engine="openpyxl") as writer:
                match_df.to_excel(writer, sheet_name="mapeo_manual", index=False)
            manual_template_buf.seek(0)

            st.download_button(
                "Descargar plantilla mapeo manual",
                data=manual_template_buf.getvalue(),
                file_name=f"mapeo_manual_odoo_{year}_{month:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_manual_template",
            )

st.divider()

with st.expander("4) Subir nominas individuales a Odoo", expanded=False):
    if not st.session_state.get("_odoo_connected"):
        st.info("Primero conecta con Odoo.")
    elif not st.session_state.odoo_matches:
        st.info("Primero empareja los empleados en el paso 3.")
    else:
        odoo: OdooClient = st.session_state._odoo_client
        dry_run = st.checkbox(
            "Modo simulacion: no crear adjuntos, solo mostrar que se haria",
            value=True,
        )
        duplicate_policy = st.selectbox(
            "Politica de duplicados",
            options=["skip", "replace", "duplicate"],
            format_func=lambda x: {
                "skip": "Omitir si ya existe",
                "replace": "Reemplazar el adjunto existente",
                "duplicate": "Crear duplicado con sufijo fecha/hora",
            }[x],
            index=0,
        )

        if st.button("Subir nominas a Odoo", type="primary", disabled=not st.session_state.split_pdfs):
            matches = st.session_state.odoo_matches
            split_pdfs = st.session_state.split_pdfs

            with st.spinner("Subiendo nominas a Odoo..." if not dry_run else "Simulando subida..."):
                results = upload_all_payslips(
                    odoo=odoo,
                    matches=matches,
                    split_pdfs=split_pdfs,
                    month=month,
                    year=year,
                    duplicate_policy=duplicate_policy,
                    dry_run=dry_run,
                )

                st.session_state.odoo_upload_log = results

            st.rerun()

        if st.session_state.odoo_upload_log:
            results = st.session_state.odoo_upload_log
            log_df = pd.DataFrame(
                [
                    {
                        "archivo_pdf": r.filename,
                        "n_trabajador": r.worker_number,
                        "dni": mask_dni(r.dni) if r.dni else "",
                        "employee_id_odoo": r.employee_id_odoo,
                        "employee_name_odoo": r.employee_name_odoo,
                        "estado": r.status,
                        "mensaje": r.message,
                        "attachment_id": r.attachment_id,
                    }
                    for r in results
                ]
            )

            st.subheader("Log de subida")
            st.dataframe(log_df, use_container_width=True, height=400)

            status_counts = pd.Series([r.status for r in results]).value_counts()
            col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
            col_s1.metric("OK_SIMULADO", int(status_counts.get("OK_SIMULADO", 0)))
            col_s2.metric("CREADO", int(status_counts.get("CREADO", 0)))
            col_s3.metric("DUPLICADO_OMITIDO", int(status_counts.get("DUPLICADO_OMITIDO", 0)))
            col_s4.metric("REEMPLAZADO", int(status_counts.get("REEMPLAZADO", 0)))
            col_s5.metric("ERROR", int(status_counts.get("ERROR", 0)))

            log_xlsx_buf = io.BytesIO()
            with pd.ExcelWriter(log_xlsx_buf, engine="openpyxl") as writer:
                log_df.to_excel(writer, sheet_name="log_subida", index=False)
            log_xlsx_buf.seek(0)

            st.download_button(
                "Descargar log de subida",
                data=log_xlsx_buf.getvalue(),
                file_name=f"log_subida_odoo_{year}_{month:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_upload_log",
            )

st.divider()

with st.expander("5) Crear asiento contable de nomina en Odoo", expanded=False):
    if not st.session_state.get("_odoo_connected"):
        st.info("Primero conecta con Odoo.")
    else:
        dry_run_move = st.checkbox(
            "Modo simulacion asiento: no crear asiento real",
            value=True,
            key="dry_run_payroll_move",
        )
        create_move = st.button("Crear asientos contables en Odoo (uno por centro)", type="primary")

        if create_move:
            odoo: OdooClient = st.session_state._odoo_client
            with st.spinner("Preparando asientos contables..." if dry_run_move else "Creando asientos en Odoo..."):
                moves_by_center = build_payroll_moves_by_center(
                    employees=st.session_state.excel_employees,
                    employee_rows=st.session_state.employee_rows,
                    month=month,
                    year=year,
                    aggregate_ss=aggregate_ss,
                )

                if not moves_by_center:
                    st.warning("No se encontraron centros de trabajo con empleados para generar asientos.")
                else:
                    results_by_center: dict[str, dict] = {}
                    for center_name, center_lines in moves_by_center.items():
                        center_label = center_name if center_name else "Sin centro"
                        center_reference = f"{reference} - {center_label}" if center_label != "Sin centro" else reference
                        res = create_payroll_move_in_odoo(
                            odoo=odoo,
                            lines=center_lines,
                            move_date=accounting_date.isoformat(),
                            journal=journal,
                            reference=center_reference,
                            dry_run=dry_run_move,
                        )
                        results_by_center[center_label] = {
                            "result": res,
                            "lines": center_lines,
                        }

                    st.session_state.odoo_move_results = results_by_center

            st.rerun()

        if st.session_state.get("odoo_move_results"):
            for center_label, data in st.session_state.odoo_move_results.items():
                move_result = data["result"]
                preview_lines = data["lines"]
                status = move_result.get("status", "")

                st.markdown(f"### Centro: {center_label}")
                if status == "OK_SIMULADO":
                    st.success(move_result.get("message", "Simulacion completada."))
                    tax_ok = move_result.get("irpf_tax_id")
                    t02_ok = move_result.get("tag_mod111_02")
                    t03_ok = move_result.get("tag_mod111_03")
                    if tax_ok and t02_ok and t03_ok:
                        st.info(f"Impuesto IRPF encontrado (ID {tax_ok}). Tags mod111[02] (ID {t02_ok}) y mod111[03] (ID {t03_ok}) listos.")
                    else:
                        st.warning(
                            "No se encontraron todos los elementos fiscales: "
                            f"impuesto IRPF={'OK' if tax_ok else 'NO'}, "
                            f"mod111[02]={'OK' if t02_ok else 'NO'}, "
                            f"mod111[03]={'OK' if t03_ok else 'NO'}. "
                            "Las lineas se crearán sin etiquetas fiscales para Modelo 111."
                        )
                elif status == "CREADO":
                    st.success(move_result.get("message", "Asiento creado correctamente."))
                else:
                    st.error(move_result.get("message", "No se pudo crear el asiento."))

                summary_move = move_result.get("summary", {})
                col_mv1, col_mv2, col_mv3, col_mv4 = st.columns(4)
                col_mv1.metric("Lineas", int(summary_move.get("line_count", 0)))
                col_mv2.metric("Debe", f"{float(summary_move.get('total_debit', 0)):.2f}")
                col_mv3.metric("Haber", f"{float(summary_move.get('total_credit', 0)):.2f}")
                col_mv4.metric("Diferencia", f"{float(summary_move.get('balance', 0)):.2f}")

                if preview_lines:
                    st.dataframe(pd.DataFrame(preview_lines), use_container_width=True, height=260)

                st.divider()

st.divider()

with st.expander("6) Solicitudes de firma movil", expanded=False):
    sign_base_url_env = normalize_base_url(load_sign_base_url_from_env_file())
    st.text_input(
        "URL publica detectada (SIGN_BASE_URL)",
        value=sign_base_url_env,
        disabled=True,
        help="Se usa directamente para construir enlaces de firma. Configurar en .env.local",
    )
    token_ttl_hours = st.number_input("Caducidad del enlace (horas)", min_value=1, max_value=24 * 30, value=24 * 10)
    wa_template = st.text_area(
        "Plantilla WhatsApp",
        value=(
            "Hola {nombre}, ya puedes firmar tu nomina del periodo {periodo}.\n\n"
            "Enlace de firma:\n\n{link}"
        ),
        help="Variables disponibles: {nombre}, {periodo}, {link}",
    )

    can_create_requests = bool(st.session_state.get("odoo_matches") and st.session_state.get("split_pdfs"))
    if not sign_base_url_env.strip():
        st.error("Falta SIGN_BASE_URL. Define una URL publica completa en .env.local (ej: https://rrhh.tudominio.com).")
        can_create_requests = False
    elif "localhost" in sign_base_url_env or "127.0.0.1" in sign_base_url_env:
        st.warning("SIGN_BASE_URL apunta a localhost. Para enlaces WhatsApp debe ser una URL publica real.")
    if not can_create_requests:
        st.info("Primero procesa archivos y realiza emparejamiento con Odoo.")
    else:
        if st.button("Crear solicitudes de firma para MATCH_OK", type="primary"):
            created_rows: list[dict[str, str]] = []
            originals_dir = Path("data/signature_pdfs/original")
            originals_dir.mkdir(parents=True, exist_ok=True)
            mapping_by_worker = {
                str(row.get("n_trabajador", "")): row for row in (st.session_state.employee_rows or [])
            }
            odoo_phone_by_employee_id: dict[int, str] = {}
            if st.session_state.get("_odoo_connected"):
                try:
                    odoo: OdooClient = st.session_state._odoo_client
                    employee_ids = [
                        int(m.employee_id_odoo)
                        for m in st.session_state.odoo_matches
                        if m.match_status == "MATCH_OK" and m.employee_id_odoo
                    ]
                    odoo_phone_by_employee_id = fetch_odoo_employee_phones(odoo, employee_ids)
                except Exception:
                    odoo_phone_by_employee_id = {}

            for match in st.session_state.odoo_matches:
                if match.match_status != "MATCH_OK" or not match.employee_id_odoo:
                    continue
                pdf_bytes = st.session_state.split_pdfs.get(match.filename)
                if not pdf_bytes:
                    continue
                row_map = mapping_by_worker.get(str(match.worker_number), {})
                telefono = str(row_map.get("telefono") or row_map.get("movil") or "").strip()
                origen_telefono = "excel"
                if not telefono:
                    telefono = str(
                        odoo_phone_by_employee_id.get(int(match.employee_id_odoo), "")
                    ).strip()
                    origen_telefono = "odoo" if telefono else "sin_dato"
                original_path = originals_dir / match.filename
                original_path.write_bytes(pdf_bytes)
                token_value = create_token()
                req_id = create_request(
                    {
                        "employee_id_odoo": int(match.employee_id_odoo),
                        "worker_number": str(match.worker_number),
                        "dni": str(match.dni or ""),
                        "employee_name": str(match.employee_name_excel or match.employee_name_pdf or ""),
                        "period_month": int(month),
                        "period_year": int(year),
                        "pdf_original_path": str(original_path),
                        "token_hash": token_hash(token_value),
                        "token_expires_at": expires_at(int(token_ttl_hours)),
                    }
                )
                add_event(req_id, "created", {"filename": match.filename})
                sign_link = build_sign_link(sign_base_url_env, token_value)
                period_label = f"{int(month):02d}/{int(year)}"
                employee_name = str(match.employee_name_odoo or match.employee_name_excel or "")
                wa_message = render_message(wa_template, employee_name, period_label, sign_link)
                wa_link = build_whatsapp_url(telefono, wa_message) if telefono else ""
                created_rows.append(
                    {
                        "request_id": req_id,
                        "empleado": str(match.employee_name_odoo or ""),
                        "n_trabajador": str(match.worker_number),
                        "telefono": telefono,
                        "origen_telefono": origen_telefono,
                        "link_firma": sign_link,
                        "whatsapp_link": wa_link,
                        "mensaje_whatsapp": wa_message,
                        "estado_envio": "pendiente",
                    }
                )

            st.session_state.signature_links = created_rows
            st.session_state.whatsapp_delivery_log = created_rows.copy()
            st.success(f"Solicitudes creadas: {len(created_rows)}")

        if st.session_state.get("signature_links"):
            st.subheader("Enlaces generados")
            st.dataframe(pd.DataFrame(st.session_state.signature_links), use_container_width=True, height=280)

            st.markdown("### Envio por WhatsApp Web")
            links = st.session_state.signature_links
            for i, row in enumerate(links):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                with c1:
                    st.write(f"**{row.get('empleado', '')}**")
                with c2:
                    st.write(row.get("telefono", ""))
                with c3:
                    if row.get("whatsapp_link"):
                        st.link_button("Abrir WhatsApp", row["whatsapp_link"], use_container_width=True)
                    else:
                        st.caption("Sin telefono")
                with c4:
                    mark_sent = st.checkbox("Enviado", key=f"wa_sent_{i}")
                    row["estado_envio"] = "enviado_manual" if mark_sent else "pendiente"

            pending = [r for r in links if r.get("estado_envio") != "enviado_manual"]
            if pending:
                st.info(f"Pendientes de envio WhatsApp: {len(pending)}")
            else:
                st.success("Todos los enlaces marcados como enviados.")

            wa_export = pd.DataFrame(links)
            wa_buf = io.BytesIO()
            with pd.ExcelWriter(wa_buf, engine="openpyxl") as writer:
                wa_export.to_excel(writer, sheet_name="whatsapp_envios", index=False)
            wa_buf.seek(0)
            st.download_button(
                "Descargar listado WhatsApp",
                data=wa_buf.getvalue(),
                file_name=f"whatsapp_firma_nominas_{year}_{month:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_whatsapp_delivery",
            )

    st.subheader("Estado de solicitudes")
    reqs = list_requests(period_month=int(month), period_year=int(year))
    if reqs:
        req_df = pd.DataFrame(reqs)
        st.dataframe(req_df, use_container_width=True, height=280)
    else:
        st.info("No hay solicitudes de firma para este periodo.")

st.divider()

if st.button("Limpiar resultados / iniciar nuevo procesamiento"):
    clear_processing_state()
    if "_odoo_client" in st.session_state:
        del st.session_state["_odoo_client"]
    if "_odoo_connected" in st.session_state:
        del st.session_state["_odoo_connected"]
    if "_warnings" in st.session_state:
        del st.session_state["_warnings"]
    if "odoo_move_results" in st.session_state:
        del st.session_state["odoo_move_results"]
    st.rerun()
