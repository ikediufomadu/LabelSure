# LabelSure test scenarios

Use the app defaults: OLD TOM DISTILLERY / Kentucky Straight Bourbon Whiskey / 45 / 750 mL.

| Image | Intended test |
|---|---|
| 01_correct.png | All four application fields should match; warning still needs visual formatting review |
| 02_wrong_abv.png | ABV mismatch (40% vs 45%) |
| 03_wrong_brand.png | Brand not found (Needs Review); manual confirmation of mismatch |
| 04_warning_case.png | Warning heading is title case, not uppercase; must be flagged for manual review |
| 05_missing_warning.png | Warning absent; Needs Review |
| 06_wrong_volume.png | Net contents differs (700 vs 750 mL); currently Needs Review because the simple verifier uses text presence, not structured volume extraction |

These are synthetic test labels, not compliant artwork. The warning text may be read with OCR line breaks; the app intentionally does not auto-approve warning formatting.
