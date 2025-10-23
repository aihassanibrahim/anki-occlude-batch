import os
import sys
import argparse
import cv2
import numpy as np
import fitz  # PyMuPDF
from PIL import Image

"""
Maskar PDF-sidor och exporterar PNG + ny PDF.
Lägen:
  - mode=column  -> ritar en smal vertikal svart stapel vid svarsalternativen
  - mode=green   -> (som innan) hittar grönt och täcker

Exempel:
  python3 maska_ratt_svar.py "Rest Tentamen - Basvetenskap 3 - VT2022.pdf" out/ \
    --skip-pages 4 --mode column --col-x-perc 82 --col-width 28 --col-top-perc 18 --col-bot-perc 68
"""

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path", help="Path to input PDF")
    ap.add_argument("out_dir", help="Output dir")
    ap.add_argument("--dpi", type=int, default=220, help="Rasterization DPI (default: 220)")
    ap.add_argument("--skip-pages", type=int, default=0, help="Hoppa över första N sidor")
    ap.add_argument("--mode", choices=["column","green","replicate"], default="replicate",
                    help="column = vertikal stapel, green = maska grönt, replicate = hitta bock och replikerar svarta boxar på alla alternativ")

    # Kolumnmaskning (procent av bildmått)
    ap.add_argument("--col-x-perc", type=float, default=82.0, help="X-position i procent av bredd (0–100)")
    ap.add_argument("--col-width", type=int, default=28, help="Stapelns bredd i pixlar")
    ap.add_argument("--col-top-perc", type=float, default=15.0, help="Överkant i % av höjd")
    ap.add_argument("--col-bot-perc", type=float, default=70.0, help="Underkant i % av höjd")

    # HSV-intervall för grönt (om mode=green)
    ap.add_argument("--h1", type=int, default=35, help="Hue min (0–179)")
    ap.add_argument("--h2", type=int, default=85, help="Hue max (0–179)")
    ap.add_argument("--s1", type=int, default=40, help="Saturation min (0–255)")
    ap.add_argument("--v1", type=int, default=40, help="Value min (0–255)")
    ap.add_argument("--min-area", type=int, default=100, help="Min contour area to mask (px)")
    ap.add_argument("--th-low", type=int, default=20, help="Canny low threshold")
    ap.add_argument("--th-high", type=int, default=80, help="Canny high threshold")
    ap.add_argument("--line-thickness", type=int, default=12, help="Mask thickness for Hough lines")
    
    # Replikationsparametrar
    ap.add_argument("--rep-box-expand", type=float, default=1.2, dest="rep_box_expand", help="Skala på bockens box (1.0 = samma)")
    ap.add_argument("--rep-x-shift", type=int, default=0, dest="rep_x_shift", help="Flytta boxarna lite i x-led (px) om behövs")
    ap.add_argument("--rep-y-shift", type=int, default=0, dest="rep_y_shift", help="Flytta boxarna lite i y-led (px) per ruta")
    ap.add_argument("--rep-min-circles", type=int, default=3, dest="rep_min_circles", help="Min antal radioknappar för att replikera")
    
    # HoughCircles finjustering
    ap.add_argument("--hc-dp", type=float, default=1.2, dest="hc_dp")
    ap.add_argument("--hc-min-dist", type=int, default=40, dest="hc_min_dist")
    ap.add_argument("--hc-param1", type=int, default=120, dest="hc_param1")
    ap.add_argument("--hc-param2", type=int, default=20, dest="hc_param2")
    ap.add_argument("--hc-min-radius", type=int, default=8, dest="hc_min_radius")
    ap.add_argument("--hc-max-radius", type=int, default=18, dest="hc_max_radius")
    
    ap.add_argument("--build-apkg", action="store_true", help="Bygg Anki .apkg efter maskning")
    return ap.parse_args()

def pdf_to_images(pdf_path, dpi, out_dir_img, skip_pages):
    os.makedirs(out_dir_img, exist_ok=True)
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
        if i < skip_pages:
            continue
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = os.path.join(out_dir_img, f"page_{i+1:03d}.png")
        pix.save(img_path)
        images.append(img_path)
    doc.close()
    return images

def mask_green(img_bgr, h1, h2, s1, v1, min_area, th_low, th_high, line_thickness):
    img = img_bgr.copy()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([h1, s1, v1], dtype=np.uint8)
    upper = np.array([h2, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w*h >= min_area:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), thickness=-1)
    edges = cv2.Canny(mask, th_low, th_high)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=3)
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = l[0]
            cv2.line(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=line_thickness)
    return img

def find_green_tick_bbox(img_bgr, h1, h2, s1, v1, min_area):
    """Returnera (x,y,w,h) för största gröna blobben (bocken/markeringen)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([h1, s1, v1], dtype=np.uint8)
    upper = np.array([h2, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None; best_area = 0
    for c in cnts:
        x,y,w,h = cv2.boundingRect(c)
        area = w*h
        if area >= min_area and area > best_area:
            best = (x,y,w,h); best_area = area
    return best  # eller None

def detect_option_circles(img_bgr, dp, min_dist, p1, p2, rmin, rmax):
    """Hitta radioknappar (små cirklar) som markerar svarsalternativens rader."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=dp,
                               minDist=min_dist, param1=p1, param2=p2,
                               minRadius=rmin, maxRadius=rmax)
    if circles is None:
        return []
    circles = np.uint16(np.around(circles[0]))  # (x,y,r)
    
    if len(circles) == 0:
        return []
    
    # Sortera top-down på y (en rad per alternativ)
    circles = sorted(circles, key=lambda c: c[1])
    
    # Filtrera för att få exakt 5 cirklar (vanligast antal svarsalternativ)
    # Ta de första 5 cirklarna som är tillräckligt långt ifrån varandra
    filtered_circles = []
    for circle in circles:
        x, y, r = circle
        # Kolla om denna cirkel är för nära en redan vald cirkel i Y-led
        too_close = False
        for existing in filtered_circles:
            if abs(y - existing[1]) < min_dist:  # Använd hela min_dist för Y-gruppering
                too_close = True
                break
        if not too_close:
            filtered_circles.append(circle)
            # Stoppa vid 5 cirklar (vanligast antal svarsalternativ)
            if len(filtered_circles) >= 5:
                break
    
    return filtered_circles

def mask_replicate(img_bgr, args):
    """Hitta grön bock → rita svarta boxar på alla alternativs y-positions."""
    img = img_bgr.copy()

    # 1) hitta bockens bbox
    bbox = find_green_tick_bbox(img_bgr, args.h1, args.h2, args.s1, args.v1, args.min_area)
    if bbox is None:
        print("  ⚠️ Ingen grön bock hittad - hoppar över denna sida")
        return img  # Returnera originalbilden om ingen bock hittas

    x,y,w,h = bbox
    print(f"  ✅ Grön bock hittad vid ({x},{y}) storlek {w}x{h}")
    
    # expandera/justera storlek lite så boxen garanterat täcker markören
    cx = x + w//2
    cy = y + h//2
    w2 = int(w * args.rep_box_expand)
    h2 = int(h * args.rep_box_expand)
    w2 = max(w2, 16); h2 = max(h2, 16)  # minstorlek

    # 2) hitta alternativens cirklar (y-positions)
    circles = detect_option_circles(img_bgr, args.hc_dp, args.hc_min_dist,
                                    args.hc_param1, args.hc_param2,
                                    args.hc_min_radius, args.hc_max_radius)

    print(f"  🔍 Hittade {len(circles)} radioknappar")
    
    if len(circles) < args.rep_min_circles:
        print(f"  ⚠️ För få radioknappar ({len(circles)} < {args.rep_min_circles}) - hoppar över")
        return img  # Returnera originalbilden om för få cirklar

    # 3) rita svarta boxar på alla y, samma x som bocken
    x1 = cx - w2//2 + args.rep_x_shift
    x2 = cx + (w2 - w2//2) + args.rep_x_shift
    
    print(f"  📦 Ritar {len(circles)} boxar vid x={x1}-{x2}")
    
    for i, (cx_c, cy_c, r) in enumerate(circles):
        yy1 = max(0, int(cy_c - h2//2 + args.rep_y_shift))
        yy2 = min(img.shape[0], int(cy_c + (h2 - h2//2) + args.rep_y_shift))
        cv2.rectangle(img, (x1, yy1), (x2, yy2), (0,0,0), thickness=-1)
        print(f"    Box {i+1}: y={yy1}-{yy2}")

    return img

def mask_column(img_bgr, x_perc, width_px, top_perc, bot_perc):
    img = img_bgr.copy()
    H, W = img.shape[:2]
    
    # Först hitta den gröna bocken för att bestämma X-position
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # HSV-intervall för grönt (samma som i mask_green)
    lower_green = np.array([35, 40, 40], dtype=np.uint8)
    upper_green = np.array([85, 255, 255], dtype=np.uint8)
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # Hitta konturer av gröna områden
    cnts, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    x_center = int(W * (x_perc / 100.0))  # Fallback position
    
    # Om vi hittar gröna områden, använd deras X-position
    if cnts:
        # Hitta det största gröna området (förmodligen bocken)
        largest_contour = max(cnts, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        x_center = x + w // 2  # Centrum av den gröna bocken
    
    # Skapa vertikal stapel som börjar vid den gröna bocken
    x1 = max(0, x_center - width_px // 2)
    x2 = min(W, x_center + (width_px - width_px // 2))
    y1 = int(H * (top_perc / 100.0))
    y2 = int(H * (bot_perc / 100.0))
    cv2.rectangle(img, (x1, y1), (x2, y2), (0,0,0), thickness=-1)
    return img

def images_to_pdf(image_paths, out_pdf):
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    if not imgs:
        return
    first, rest = imgs[0], imgs[1:]
    first.save(out_pdf, save_all=True, append_images=rest)

def build_apkg_from_images(img_dir, output="bv3_maskad.apkg"):
    import re, glob, genanki
    DECK_NAME = "BV3 – Maskad tenta (auto)"
    DECK_ID   = 2025102301
    masked = sorted(glob.glob(os.path.join(img_dir, "page_*_masked.png")))
    if not masked:
        print("Inga _masked.png hittades – hoppar över .apkg")
        return
    model = genanki.Model(
        1607392319,
        'Basic (Image Front/Back)',
        fields=[{'name':'Front'},{'name':'Back'}],
        templates=[{'name':'Card 1','qfmt':'{{Front}}','afmt':'{{Front}}<hr id=answer>{{Back}}'}],
        css=".card{font-family:-apple-system,Segoe UI,Arial; font-size:18px} img{max-width:100%}"
    )
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    media = []
    for m in masked:
        base = os.path.basename(m)
        num = base.split("_")[1]  # 001
        orig = os.path.join(img_dir, f"page_{num}.png")
        if not os.path.exists(orig):
            continue
        front = f'<img src="{base}">'
        back  = f'<img src="page_{num}.png">'
        note = genanki.Note(model=model, fields=[front, back])
        deck.add_note(note)
        media += [m, orig]
    pkg = genanki.Package(deck)
    pkg.media_files = media
    pkg.write_to_file(output)
    print(f"Klar ✅ skapade {output}")

def main():
    args = parse_args()
    out_dir = args.out_dir
    out_img = os.path.join(out_dir, "masked_images")
    os.makedirs(out_dir, exist_ok=True)

    print("1) Rasteriserar PDF…")
    pages = pdf_to_images(args.pdf_path, args.dpi, out_img, skip_pages=args.skip_pages)

    print(f"2) Maskar sidor (mode={args.mode})…")
    masked_paths = []
    for p in pages:
        bgr = cv2.imread(p)
        if args.mode == "green":
            masked = mask_green(
                bgr, args.h1, args.h2, args.s1, args.v1,
                args.min_area, args.th_low, args.th_high, args.line_thickness
            )
        elif args.mode == "column":
            masked = mask_column(
                bgr, args.col_x_perc, args.col_width, args.col_top_perc, args.col_bot_perc
            )
        else:  # replicate
            masked = mask_replicate(bgr, args)

        outp = p.replace(".png", "_masked.png")
        cv2.imwrite(outp, masked)
        masked_paths.append(outp)

    print("3) Bygger ny PDF…")
    out_pdf = os.path.join(out_dir, "tenta_maskad.pdf")
    images_to_pdf(masked_paths, out_pdf)
    print(f"✅ Ny PDF klar: {out_pdf}")
    print(f"📁 Bilder: {out_img}")

    if args.build_apkg:
        print("4) Bygger .apkg…")
        build_apkg_from_images(out_img)

if __name__ == "__main__":
    # Snabbstart: om inga argument → försök köra på defaultfil med rimliga parametrar
    if len(sys.argv) == 1 and os.path.exists("Rest Tentamen - Basvetenskap 3 - VT2022.pdf"):
        sys.argv.extend([
            "Rest Tentamen - Basvetenskap 3 - VT2022.pdf", "out/",
            "--skip-pages","4","--mode","column","--col-x-perc","82",
            "--col-width","28","--col-top-perc","18","--col-bot-perc","68","--build-apkg"
        ])
    main()