# XLSX Drive Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload all validated XLSX files from `data/upload/` as native Google Sheets with the agreed naming convention.

**Architecture:** Extend the existing Drive uploader with an XLSX input mode. Read workbook headers and rows with `openpyxl`, validate the required named columns, derive the majority month/year from `Datum`, and use Drive API upload conversion to Google Sheets. Keep the existing CSV workflow unchanged.

**Tech Stack:** Python 3.12, `openpyxl`, Google Drive API, existing service-account configuration, pytest.

## Global Constraints

- Required headers are exactly `Datum`, `Objem`, `Měna`, `Kategorie`, `Jistota kategorie`, `Firma`, and `Radek`.
- Existing same-name Drive files are updated; otherwise files are created.
- Source XLSX files remain unchanged.
- Generated names are lowercase, ASCII, hyphen-separated, and omit the extension.
- Upload targets native Google Sheets MIME type.

---

### Task 1: Add workbook validation and naming helpers

**Files:**
- Modify: `src/kategorizace/drive.py`
- Test: `tests/test_drive.py` (create if the repository has no existing drive tests)

**Interfaces:**
- Produce `XLSX_REQUIRED_COLUMNS`.
- Produce `_xlsx_headers_and_rows(path) -> tuple[list[str], list[list[object]]]`.
- Produce `_xlsx_drive_nazev(path) -> str`.

- [ ] **Step 1: Write failing tests**

```python
def test_xlsx_name_uses_majority_month_and_existing_stem(tmp_path):
    path = tmp_path / "RD Výdajový 1.xlsx"
    write_workbook(path, ["Datum", "Objem", "Měna", "Kategorie", "Jistota kategorie", "Firma", "Radek"], [
        ["01.08.2026", 10, "CZK", "A", 1, "RD", "R01"],
        ["15.08.2026", 20, "CZK", "B", 1, "RD", "R02"],
    ])
    assert _xlsx_drive_nazev(path) == "08-2026-rd-vydajovy-1"


def test_xlsx_validation_rejects_missing_required_header(tmp_path):
    path = tmp_path / "bad.xlsx"
    write_workbook(path, ["Datum", "Objem"], [["01.08.2026", 10]])
    with pytest.raises(ValueError, match="Jistota kategorie"):
        _xlsx_headers_and_rows(path)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `uv run pytest tests/test_drive.py -q`
Expected: FAIL because the XLSX helpers do not yet exist.

- [ ] **Step 3: Implement minimal helpers**

Use `openpyxl.load_workbook(path, read_only=True, data_only=True)`, take the first worksheet, strip header text, reject missing required names, drop only fully empty trailing rows, and reuse `_slug` plus `_parsuj_datum` to calculate the majority `MM-YYYY` prefix.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_drive.py -q`
Expected: PASS.

---

### Task 2: Add Drive API XLSX conversion upload

**Files:**
- Modify: `src/kategorizace/drive.py`
- Test: `tests/test_drive.py`

**Interfaces:**
- Produce `_nahraj_xlsx_soubor(service, cesta, nazev, folder_id, existujici) -> str`.

- [ ] **Step 1: Write failing API-mock tests**

Assert that both create and update calls use `MediaFileUpload(..., mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")`, include `supportsAllDrives=True`, and set `mimeType` to `application/vnd.google-apps.spreadsheet` on create.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest tests/test_drive.py -q`
Expected: FAIL because the conversion uploader does not exist.

- [ ] **Step 3: Implement the conversion uploader**

Mirror `_nahraj_soubor`: call `files().update` for an existing name; call `files().create` with `body={"name": nazev, "parents": [folder_id], "mimeType": SHEET_MIMETYPE}` for a new name. Return `"aktualizováno"` or `"nahráno"`.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_drive.py -q`
Expected: PASS.

---

### Task 3: Wire XLSX files into the CLI and report row counts

**Files:**
- Modify: `src/kategorizace/drive.py`
- Test: `tests/test_drive.py`

- [ ] **Step 1: Write a failing orchestration test**

Mock Drive service and configuration, place two valid workbooks in a temporary upload directory, invoke the XLSX upload path, and assert two files are processed, generated names are used, and the reported row count excludes headers.

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `uv run pytest tests/test_drive.py -q`
Expected: FAIL because the CLI currently only scans `firmy/*/results/*.csv`.

- [ ] **Step 3: Implement the XLSX scan path**

Add an explicit `data/upload/*.xlsx` scan to `main()` or a small testable helper. Validate each workbook before calling Drive; print one error per invalid file and continue. Preserve the current CSV scan and summary behavior. Use the actual XLSX row count in the success message.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_drive.py -q`
Expected: PASS.

---

### Task 4: Perform the real upload and verify results

**Files:**
- Modify: none

- [ ] **Step 1: Run the full relevant test set**

Run: `uv run pytest tests/test_drive.py -q`
Expected: all tests PASS.

- [ ] **Step 2: Run the uploader against the configured Drive**

Run: `uv run nahraj-na-drive`
Expected: all 13 files from `data/upload/` are reported as uploaded or updated; invalid files are zero.

- [ ] **Step 3: Verify the resulting Drive listing**

Confirm each generated name exists as a native Google Sheet and the summary reports the expected data-row counts. Do not delete or modify the local XLSX sources.
