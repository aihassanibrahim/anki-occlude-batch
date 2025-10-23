import os
import re
import glob
import shutil
import fitz  # PyMuPDF
import genanki

# ====== Konfig ======
DECK_NAME = "BV – Tentor (samlat)"
DECK_ID   = 2025102309  # valfritt stabilt tal
DPI       = 300         # Högre DPI för bättre läsbarhet
DEFAULT_SKIP_PAGES = 3  # hoppa över försättssidor

# Vill du ha olika skip per tenta? Ange här (namndel som matchar filnamnet -> antal sidor att hoppa)
SKIP_OVERRIDES = {
    # "Basvetenskap 2": 2,
    # "HT22": 4,
}

# ====== Hjälpfunktioner ======
def pdf_to_images(pdf_path, out_dir, prefix, dpi=DPI, skip_pages=0):
    """Konverterar PDF-sidor till PNG-bilder."""
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i, page in enumerate(doc):
        if i < skip_pages:
            continue
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = os.path.join(out_dir, f"{prefix}_{i+1:03d}.png")
        pix.save(img_path)
        paths.append(img_path)
    doc.close()
    return paths

def find_pairs():
    """Hitta alla filer utan 'facit' och matcha mot motsvarande filer med 'facit'."""
    # Hitta alla PDF-filer
    all_pdfs = glob.glob("*.pdf")
    
    # Separera filer med och utan "facit" i namnet
    utan_facit = []  # Filer utan "facit" i namnet
    med_facit = []   # Filer med "facit" i namnet
    
    for pdf in all_pdfs:
        if "facit" in pdf.lower():
            med_facit.append(pdf)
        else:
            utan_facit.append(pdf)
    
    print(f"📚 Hittade {len(utan_facit)} filer utan facit")
    print(f"📚 Hittade {len(med_facit)} filer med facit")
    
    pairs = []
    
    # Försök matcha filer baserat på liknande namn
    for utan in utan_facit:
        best_match = None
        best_score = 0
        
        # Ta bort "utan svar" och liknande från namnet för bättre matchning
        clean_utan = re.sub(r'\s*utan\s+svar\s*', '', utan, flags=re.IGNORECASE)
        clean_utan = re.sub(r'\s*utan\s+facit\s*', '', clean_utan, flags=re.IGNORECASE)
        clean_utan = re.sub(r'\s*utan_Facit\s*', '', clean_utan, flags=re.IGNORECASE)
        
        for med in med_facit:
            # Ta bort "facit" från namnet för jämförelse
            clean_med = re.sub(r'\s*facit\s*', '', med, flags=re.IGNORECASE)
            
            # Beräkna likhet mellan namnen
            score = calculate_similarity(clean_utan, clean_med)
            
            if score > best_score and score > 0.3:  # Minst 30% likhet (nu med exakt termin/typ/år-kontroll)
                best_score = score
                best_match = med
        
        if best_match:
            pairs.append((utan, best_match))
            print(f"✅ Matchade: {os.path.basename(utan)} ↔ {os.path.basename(best_match)} (likhet: {best_score:.2f})")
        else:
            print(f"⚠️ Ingen match hittad för: {os.path.basename(utan)}")
    
    return pairs

def calculate_similarity(name1, name2):
    """Beräkna exakt likhet mellan två filnamn baserat på termin och typ."""
    
    def extract_key_info(name):
        """Extrahera viktig information från filnamnet."""
        name_lower = name.lower()
        
        # Hitta termin (HT/VT + år)
        termin_match = re.search(r'(ht|vt)(\d{2,4})', name_lower)
        termin = termin_match.group(0) if termin_match else None
        
        # Hitta typ (ordinarie/rest)
        typ = None
        if 'ordinarie' in name_lower:
            typ = 'ordinarie'
        elif 'rest' in name_lower:
            typ = 'rest'
        
        # Hitta år separat också
        year_match = re.search(r'(20\d{2})', name_lower)
        year = year_match.group(1) if year_match else None
        
        return {
            'termin': termin,
            'typ': typ,
            'year': year,
            'original': name_lower
        }
    
    info1 = extract_key_info(name1)
    info2 = extract_key_info(name2)
    
    # Om båda har termin, måste de matcha exakt
    if info1['termin'] and info2['termin']:
        if info1['termin'] != info2['termin']:
            return 0  # Olika terminer = ingen match
    
    # Om båda har typ, måste de matcha exakt
    if info1['typ'] and info2['typ']:
        if info1['typ'] != info2['typ']:
            return 0  # Olika typer = ingen match
    
    # Om båda har år, måste de matcha exakt
    if info1['year'] and info2['year']:
        if info1['year'] != info2['year']:
            return 0  # Olika år = ingen match
    
    # Om vi kommer hit, är grundläggande info kompatibel
    # Beräkna likhet baserat på gemensamma ord (exklusive termin/typ/år)
    def clean_for_comparison(name):
        # Ta bort termin, typ och år för jämförelse
        cleaned = re.sub(r'(ht|vt)\d{2,4}', '', name.lower())
        cleaned = re.sub(r'(ordinarie|rest)', '', cleaned)
        cleaned = re.sub(r'20\d{2}', '', cleaned)
        cleaned = re.sub(r'[^a-z0-9\s]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    clean1 = clean_for_comparison(name1)
    clean2 = clean_for_comparison(name2)
    
    if not clean1 or not clean2:
        return 0.5  # Om vi inte kan jämföra ord, men termin/typ/år matchar
    
    words1 = set(clean1.split())
    words2 = set(clean2.split())
    
    if not words1 or not words2:
        return 0.5
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    base_similarity = len(intersection) / len(union) if union else 0
    
    # Höj likheten om termin/typ/år matchar perfekt
    bonus = 0
    if info1['termin'] and info2['termin'] and info1['termin'] == info2['termin']:
        bonus += 0.3
    if info1['typ'] and info2['typ'] and info1['typ'] == info2['typ']:
        bonus += 0.3
    if info1['year'] and info2['year'] and info1['year'] == info2['year']:
        bonus += 0.2
    
    return min(1.0, base_similarity + bonus)

def guess_skip(name):
    """Gissa hur många sidor som ska hoppas över baserat på filnamnet."""
    for key, val in SKIP_OVERRIDES.items():
        if key.lower() in name.lower():
            return val
    return DEFAULT_SKIP_PAGES

def clean_filename(name):
    """Rensa filnamn för användning som mappnamn."""
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name)

# ====== Huvudflöde ======
def main():
    print("🔍 Söker efter tentapar...")
    pairs = find_pairs()
    
    if not pairs:
        print("❌ Hittade inga par av tentor utan/m med facit i denna mapp.")
        print("📝 Kontrollera att filnamnen innehåller 'utan facit' och motsvarande 'facit' filer.")
        return

    print(f"📚 Hittade {len(pairs)} tentapar")
    
    # Skapa Anki-deck
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    media = []
    work_root = "anki_build"
    
    # Rensa och skapa arbetsmapp
    if os.path.exists(work_root):
        shutil.rmtree(work_root)
    os.makedirs(work_root, exist_ok=True)

    # Skapa Anki-modell för side-by-side visning
    model = genanki.Model(
        21022026, "Tenta Side-by-Side",
        fields=[{'name': 'Front'}, {'name': 'Back'}, {'name': 'Meta'}],
        templates=[{
            'name': 'Card',
            'qfmt': '{{Front}}<div class="meta">{{Meta}}</div>',
            'afmt': '{{Front}}<hr id="answer" style="margin: 15px 0; border: 1px solid #ccc;">{{Back}}<div class="meta">{{Meta}}</div>',
        }],
        css="""
        .card {
            font-family: -apple-system, Segoe UI, Arial;
            font-size: 16px;
            text-align: center;
        }
        img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 5px 0;
        }
        .front-img {
            margin-bottom: 10px;
        }
        .back-img {
            margin-top: 10px;
        }
        .meta {
            font-size: 12px;
            color: #666;
            margin-top: 8px;
            font-style: italic;
        }
        """
    )

    total_notes = 0
    
    for utan, med in pairs:
        base = re.sub(r"\.pdf$", "", os.path.basename(utan))
        # Ta bort "utan svar" och liknande från namnet
        tenta_name = re.sub(r'\s*utan\s+svar\s*', '', base, flags=re.IGNORECASE)
        tenta_name = re.sub(r'\s*utan\s+facit\s*', '', tenta_name, flags=re.IGNORECASE)
        tenta_name = re.sub(r'\s*utan_Facit\s*', '', tenta_name, flags=re.IGNORECASE)
        tenta_name = tenta_name.strip(" -_")
        skip = guess_skip(tenta_name)

        print(f"\n📖 Bearbetar: {tenta_name}")
        print(f"   Skip sidor: {skip}")

        # Skapa undermapp för denna tenta
        out_dir = os.path.join(work_root, clean_filename(tenta_name))
        
        # Konvertera PDF:er till bilder
        front_imgs = pdf_to_images(utan, out_dir, "front", dpi=DPI, skip_pages=skip)
        back_imgs  = pdf_to_images(med,  out_dir, "back",  dpi=DPI, skip_pages=skip)

        # Säkerställ lika många sidor
        n = min(len(front_imgs), len(back_imgs))
        
        if n == 0:
            print(f"   ⚠️ Inga sidor att bearbeta efter skip={skip}")
            continue
            
        print(f"   📄 Bearbetar {n} sidor")

        for idx in range(n):
            f, b = front_imgs[idx], back_imgs[idx]
            meta = f"{tenta_name} – sida {idx+1+skip}"
            
            note = genanki.Note(
                model=model,
                fields=[
                    f'<div class="front-img"><img src="{os.path.basename(f)}"></div>',  # utan facit = fråga
                    f'<div class="back-img"><img src="{os.path.basename(b)}"></div>',   # med facit = svar
                    meta
                ]
            )
            deck.add_note(note)
            media.extend([f, b])
            total_notes += 1

        print(f"   ✅ Lade till {n} kort")

    if total_notes == 0:
        print("❌ Inga kort skapades. Kontrollera PDF-filerna och skip-inställningar.")
        return

    # Skapa Anki-paket
    print(f"\n📦 Skapar Anki-paket med {total_notes} kort...")
    pkg = genanki.Package(deck)
    pkg.media_files = media
    out_apkg = "tentor_samlat.apkg"
    pkg.write_to_file(out_apkg)
    
    print(f"\n✅ KLART: {out_apkg} med {total_notes} kort.")
    print(f"📁 Arbetsfiler finns i: {work_root}")
    print(f"💡 Importera {out_apkg} i Anki för att använda decket.")

if __name__ == "__main__":
    main()
