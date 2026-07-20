# invoices/

Faktury k transakcím. Podporované formáty: PDF, PNG, JPG, JPEG.

Při prvním spuštění `uv run kategorizace` Gemini přečte každou fakturu
a uloží metadata (dodavatel, částka, datum, VS, číslo účtu) do `.index.json`.
Faktury, které se nezměnily, se při dalším spuštění přeskočí.
