"""
Kategorizace bankovních transakcí pomocí Gemini AI.

Vstup:  CSV výpisy z Fio banky  +  složka s fakturami (PDF/PNG/JPG)
Výstup: CSV s přidanými sloupci Kategorie, Jistota kategorie, Chyba v kategorii,
        Faktura, Jistota faktura, Check přiřazení faktury, Špatně zvolená faktura

Spuštění:
    uv run kategorizace   – kategorizace všech firem
    uv run report         – report chybějících faktur
    uv run konfigurace    – výpis definovaných kategorií
"""

from .cli import main

__all__ = ["main"]
