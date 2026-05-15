from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.utils import normalize_dni, normalize_worker_number, normalize_name, mask_dni


class TestNormalizeDni:
    def test_basic_dni(self):
        assert normalize_dni("75427433Z") == "75427433Z"

    def test_dni_with_spaces(self):
        assert normalize_dni("75 427 433 Z") == "75427433Z"

    def test_dni_with_hyphens(self):
        assert normalize_dni("75-427-433-Z") == "75427433Z"

    def test_dni_lowercase(self):
        assert normalize_dni("75427433z") == "75427433Z"

    def test_dni_with_dots(self):
        assert normalize_dni("7.542.743.3Z") == "75427433Z"

    def test_nie(self):
        assert normalize_dni("X1234567L") == "X1234567L"

    def test_empty(self):
        assert normalize_dni("") == ""

    def test_none_like(self):
        assert normalize_dni(None) == ""


class TestNormalizeWorkerNumber:
    def test_basic_number(self):
        assert normalize_worker_number("228") == "228"

    def test_with_leading_zeros(self):
        assert normalize_worker_number("00228") == "228"

    def test_with_spaces(self):
        assert normalize_worker_number(" 228 ") == "228"

    def test_with_hyphens(self):
        assert normalize_worker_number("2-28") == "228"

    def test_empty(self):
        assert normalize_worker_number("") == ""


class TestNormalizeName:
    def test_basic_name(self):
        assert normalize_name("Juan Pérez") == "JUAN PEREZ"

    def test_with_accents(self):
        assert normalize_name("María José García") == "MARIA JOSE GARCIA"

    def test_with_extra_spaces(self):
        assert normalize_name("  Juan   Pérez  ") == "JUAN PEREZ"

    def test_empty(self):
        assert normalize_name("") == ""


class TestMaskDni:
    def test_basic_mask(self):
        assert mask_dni("75427433Z") == "7542****Z"

    def test_short_dni(self):
        assert mask_dni("123") == "123"

    def test_empty(self):
        assert mask_dni("") == ""

    def test_nie_mask(self):
        result = mask_dni("X1234567L")
        assert result.startswith("X123")
        assert result.endswith("L")
