from __future__ import annotations

import logging
import xmlrpc.client
from typing import Any

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.uid: int | None = None
        self._common_url = f"{self.url}/xmlrpc/2/common"
        self._object_url = f"{self.url}/xmlrpc/2/object"

    def authenticate(self) -> int:
        common = xmlrpc.client.ServerProxy(self._common_url)
        try:
            uid = common.authenticate(self.db, self.username, self.password, {})
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar a Odoo ({self.url}): {e}") from e

        if not uid:
            raise PermissionError(
                f"Autenticacion fallida. Verifica usuario, contrasena y base de datos '{self.db}'."
            )

        self.uid = uid
        return uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        if self.uid is None:
            raise RuntimeError("Debes autenticarte antes de ejecutar operaciones.")

        models = xmlrpc.client.ServerProxy(self._object_url)
        args = args or []
        kwargs = kwargs or {}
        try:
            return models.execute_kw(
                self.db, self.uid, self.password, model, method, args, kwargs
            )
        except xmlrpc.client.Fault as exc:
            raise RuntimeError(
                f"Error Odoo en {model}.{method}: {exc.faultString}"
            ) from exc
        except OSError as exc:
            raise ConnectionError(
                f"No se pudo completar la llamada XML-RPC a Odoo ({model}.{method})."
            ) from exc

    def fields_get(self, model: str) -> dict:
        return self.execute_kw(model, "fields_get")

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list,
        limit: int = 100,
    ) -> list[dict]:
        return self.execute_kw(
            model,
            "search_read",
            args=[domain],
            kwargs={"fields": fields, "limit": limit},
        )

    def search(self, model: str, domain: list, limit: int = 100) -> list[int]:
        return self.execute_kw(
            model,
            "search",
            args=[domain],
            kwargs={"limit": limit},
        )

    def create(self, model: str, values: dict) -> int:
        return self.execute_kw(model, "create", args=[values])

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        result = self.execute_kw(model, "write", args=[ids, values])
        return bool(result)

    def read(self, model: str, ids: list[int], fields: list | None = None) -> list[dict]:
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        return self.execute_kw(model, "read", args=[ids], kwargs=kwargs)

    def get_employee_fields(self) -> dict:
        return self.fields_get("hr.employee")

    def get_attachment_fields(self) -> dict:
        return self.fields_get("ir.attachment")

    def search_employees(
        self,
        domain: list,
        fields: list | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if fields is None:
            fields = ["id", "name", "identification_id", "barcode", "active"]
        return self.search_read("hr.employee", domain, fields, limit)

    def check_hr_module(self) -> bool:
        try:
            self.fields_get("hr.employee")
            return True
        except Exception:
            return False
