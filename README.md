# LabelSure — Alcohol Label Verification Prototype

LabelSure is a standalone, human-in-the-loop Streamlit application that uses **local OCR** to help reviewers compare alcohol label images with submitted application information. It highlights matching fields, potential mismatches, and items requiring manual inspection. **It does not approve or reject labels or certify TTB compliance.**

No API key, Tesseract executable, or external OCR service is required. OCR uses RapidOCR with ONNX Runtime installed through `pip`.

## Requirements

- Python **3.14.2** is the intended development environment; compatible binary wheels must be available for your operating system.
- Windows, macOS, or Linux with supported Python, NumPy, and ONNX Runtime packages.
- Internet access for the initial `pip` installation; OCR inference runs locally afterward.

## Installation and local run

```bash
python -m venv .venv
# Windows Git Bash:
source .venv/Scripts/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

Streamlit displays a local URL (typically `http://localhost:8501`).

## Single-label verification

1. Select **Single label**.
2. Enter the application's **brand**, **class/type**, **ABV** (e.g. `45`), and **net contents** (e.g. `750 mL`).
3. Upload a PNG or JPEG image and click **Verify label**.
4. Review the color-coded results and expand **OCR text** to see what the engine actually read.
5. Download the field-level CSV results if needed.

## Batch processing — separate applications per image

1. Select **Batch processing**.
2. Upload up to **300 PNG/JPEG images**.
3. Upload a UTF-8 CSV with one application row per image. Required headers are:

   ```csv
   filename,brand,type,abv,volume
   01_correct.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45,750 mL
   02_wrong_abv.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45,750 mL
   ```

4. The `filename` in each CSV row must **exactly match** the uploaded image's filename. Duplicate names, missing rows, and extra rows are reported as errors.
5. Click **Verify batch**. Review per-image results and the batch summary, then download the results CSV.

The app includes a **Download example CSV template** button. A `sample_applications.csv` is also supplied for the original sample-label filenames. Each image is checked against **its own CSV application row**, not one shared application.

## Interpreting results

| Status | Color | Meaning |
| --- | --- | --- |
| **Match** | Green | The checked field was recognized as matching the application. |
| **Mismatch** | Red | The verifier identified a conflicting value. |
| **Needs Review** | Orange | OCR or the comparison rules cannot establish a reliable result. |
| **Error** | Red | The image could not be processed. |

These are **review-assistance statuses**, not legal compliance decisions. A green government-warning text result does **not** verify bold typography, placement, size, or legibility.

## Verification approach

- **Brand:** case/punctuation-insensitive comparison; can flag a different explicitly labeled brand or a recognizable unlabeled distillery/brewery/winery name. Other unrecognized brands may require review.
- **Class/type:** text comparison, with explicitly labeled conflicting values flagged. OCR omissions or unusual layouts may require review.
- **ABV:** compares numeric percentages, prioritizing values labeled ABV or alcohol by volume. Ambiguous unrelated percentages can still affect results.
- **Net contents:** recognizes volume values in mL and liters, converting liters to mL for comparison. Multiple printed volumes can be ambiguous.
- **Government health warning:** checks the required warning text, including capitalization and punctuation, against OCR output. Formatting always requires visual inspection.

Verification is intentionally conservative where the image text is unclear. The result depends on what OCR extracts, not on perfect knowledge of the source image.

## Processing-time measurement

The application uses Python's `time.perf_counter()` to measure elapsed processing time per image and reports whether it is above or below the stakeholder's **five-second target**. Batch mode also reports total elapsed time and the number of images over five seconds.

**Measurement caveat:** In the current `app.py`, the per-image timer stops after OCR extraction, **before** the `verify()` function executes, despite the UI caption saying “OCR + verification.” It also excludes network upload time and most UI rendering. For a true end-to-end OCR-and-verification benchmark, move the timer stop until after `verify()` and record that duration. Initial OCR model initialization can make the first image slower. No five-second performance guarantee is claimed.

## Project structure

```text
labelsure/
├── app.py                 # Streamlit UI, CSV parsing, batch workflow, timing
├── ocr.py                 # Local OCR adapter and image handling
├── verification.py        # Field comparison rules and warning text check
├── requirements.txt       # Python dependencies
├── test_labels/           # Synthetic sample label images, if included
└── tests/                 # Verification unit tests
```

The design keeps OCR, comparison logic, and UI separate without introducing a database, web API, or complex service architecture.

## Testing

```bash
python -m pytest -q
```

For manual testing, use the synthetic images under `test_labels/` or the separate stricter-verifier test pack. Useful scenarios include correct fields, wrong brand, wrong ABV, wrong net contents, incorrect warning capitalization, missing warning, inconsistent proof, and blurry/angled bottle photos. Inspect the **OCR text** when an expected mismatch shows **Needs Review**; this may indicate extraction failure rather than a comparison-rule failure.

Unit tests validate comparison behavior; they do not establish accuracy on real bottle photographs, full regulatory compliance, or the five-second performance target.

## Known limitations and assumptions

- Human review is required for unclear OCR, typography, warning layout, and regulatory judgment.
- Exact warning text may fail to match when OCR changes punctuation, capitalization, or line breaks.
- Brand and class/type extraction uses limited heuristics rather than a trained field-layout model; false negatives and false positives are possible.
- Some regulatory fields are **not** checked: producer/bottler name and address, country of origin, beverage-specific exceptions, and other TTB requirements.
- No COLA integration, user accounts, database, permanent image storage, or formal security authorization.
- Batch processing is sequential; 300 images can take significant time and may exceed hosting resource limits.
- Use **synthetic or otherwise non-sensitive** sample data for this prototype.

