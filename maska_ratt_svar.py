import os
import sys
import argparse
import cv2
import numpy as np
import fitz  # PyMuPDF
from PIL import Image

"""
Batch-mask green checkmarks/lines in a PDF, output masked images + rebuilt PDF.

Usage:
    python maska_ratt_svar.py "input.pdf" out/ --min-area 120 --th-low 30 --th-high 100
"""

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path", help="Path to input PDF")
    ap.add_argument("out_dir", help="Output dir")
    ap.add_argument("--dpi", type=int, default=220, help="Rasterization DPI (default: 220)")
    # HSV range for green
    ap.add_argument("--h1", type=int, default=35, help="Hue min (0–179)")
    ap.add_argument("--h2", type=int, default=85, help="Hue max (0–179)")
    ap.add_argument("--s1", type=int, default=40, help="Saturation min (0–255)")
    ap.add_argument("--v1", type=int, default=40, help="Value min (0–255)")
    ap.add_argument("--min-area", type=int, default=100, help="Min contour area to mask (px)")
    ap.add_argument("--th-low", type=int, default=20, help="Canny low threshold")
    ap.add_argument("--th-high", type=int, default=80, help="Canny high threshold")
    ap.add_argument("--line-thickness", type=int, default=12, help="Mask thickness for Hough lines")
    return ap.parse_args()

def pdf_to_images(pdf_path, dpi, out_dir_img):
    os.makedirs(out_dir_img, exist_ok=True)
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
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

    # Base mask for "green"
    lower = np.array([h1, s1, v1], dtype=np.uint8)
    upper = np.array([h2, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    # Clean up noise
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

    # Contours
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h >= min_area:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), thickness=-1)

    # Line detection for thin marks
    edges = cv2.Canny(mask, th_low, th_high)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=3)
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = l[0]
            cv2.line(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=line_thickness)

    return img

def images_to_pdf(image_paths, out_pdf):
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    if not imgs:
        return
    first, rest = imgs[0], imgs[1:]
    first.save(out_pdf, save_all=True, append_images=rest)

def main():
    args = parse_args()
    pdf_path = args.pdf_path
    out_dir = args.out_dir
    out_img = os.path.join(out_dir, "masked_images")
    os.makedirs(out_dir, exist_ok=True)

    print("1) Rasterizing PDF…")
    pages = pdf_to_images(pdf_path, args.dpi, out_img)

    print("2) Masking green marks…")
    masked_paths = []
    for p in pages:
        bgr = cv2.imread(p)
        masked = mask_green(
            bgr,
            args.h1, args.h2, args.s1, args.v1,
            args.min_area, args.th_low, args.th_high, args.line_thickness
        )
        outp = p.replace(".png", "_masked.png")
        cv2.imwrite(outp, masked)
        masked_paths.append(outp)

    print("3) Building new PDF…")
    out_pdf = os.path.join(out_dir, "tenta_maskad.pdf")
    images_to_pdf(masked_paths, out_pdf)
    print(f"Done ✅  New PDF: {out_pdf}")
    print(f"Masked images: {out_img}")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # quick-start: try to run on a sample file if present
        default_pdf = "Rest Tentamen - Basvetenskap 3 - VT2022.pdf"
        if os.path.exists(default_pdf):
            sys.argv.extend([default_pdf, "out/"])
    main()
