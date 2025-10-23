# anki-occlude-batch

Batch-mask **green checkmarks/lines** in a PDF (e.g., exam questions) and export:
- a **masked PDF** (answers covered), and
- **masked page images** ready for Anki.

Works great with Cursor or plain Python.

## ✨ Features
- Converts each PDF page to an image (configurable DPI).
- Detects **green** ticks/lines using **HSV** color threshold.
- Masks them with solid black rectangles.
- Rebuilds a **new PDF** from masked images.
- CLI flags for fine-tuning (HSV, min area, edge/line params).

## ⚙️ Requirements
Python 3.9+
