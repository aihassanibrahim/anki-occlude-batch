# Anki Deck Generator för Tentor

Skapar Anki-deck från tentor med och utan facit. Perfekt för att studera genom att jämföra frågor med svar.

## ✨ Funktioner
- Hittar automatiskt par av tentor (utan facit ↔ med facit)
- Konverterar PDF-sidor till bilder med hög kvalitet
- Skapar Anki-kort med side-by-side visning (fråga ↔ svar)
- Hoppar över försättssidor automatiskt
- Genererar `.apkg` filer som kan importeras direkt i Anki

## 🚀 Snabbstart

1. **Installera beroenden:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Placera dina PDF-filer i samma mapp:**
   - Tentor utan facit: `*utan facit*.pdf` eller `*utan_Facit*.pdf`
   - Tentor med facit: `*facit*.pdf` eller `*Facit*.pdf`

3. **Kör scriptet:**
   ```bash
   python skap_anki_deck.py
   ```

4. **Importera i Anki:**
   - Öppna Anki
   - File → Import
   - Välj `tentor_samlat.apkg`

## 📁 Filnamnskonventioner

Scriptet hittar automatiskt par baserat på filnamn:

**Exempel på fungerande par:**
- `Tenta utan facit.pdf` ↔ `Tenta facit.pdf`
- `Exam utan_Facit.pdf` ↔ `Exam_Facit.pdf`
- `Test utan facit.pdf` ↔ `Test med facit.pdf`

## ⚙️ Konfiguration

Du kan justera inställningar i början av `skap_anki_deck.py`:

```python
DECK_NAME = "BV – Tentor (samlat)"  # Namn på Anki-decket
DPI = 200                           # Bildkvalitet (200-220 rekommenderas)
DEFAULT_SKIP_PAGES = 3              # Sidor att hoppa över i början

# Olika skip per tenta
SKIP_OVERRIDES = {
    "Basvetenskap 2": 2,
    "HT22": 4,
}
```

## 📋 Krav
Python 3.9+