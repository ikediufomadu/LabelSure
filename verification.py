"""Conservative, explainable comparisons for label OCR text."""
import re
from dataclasses import dataclass

WARNING = ("GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
           "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
           "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
           "operate machinery, and may cause health problems.")

@dataclass
class Result:
    field: str
    status: str
    detail: str


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold().replace('’', "'"))


def lines(observed: str) -> list[str]:
    return [x.strip() for x in observed.splitlines() if x.strip()]


def brand_candidate(expected: str, observed: str) -> str | None:
    """Find an unlabeled brand only when a distinctive brand suffix is present.

    This is intentionally narrow: arbitrary headings are not proof of a wrong brand.
    """
    suffixes = ('DISTILLERY', 'BREWING COMPANY', 'BREWERY', 'VINEYARDS', 'WINERY')
    suffix = next((s for s in suffixes if normalize(expected).endswith(normalize(s))), None)
    if not suffix:
        return None
    # A brand is usually near the top of the OCR output, before product details.
    for line in lines(observed)[:8]:
        candidate = re.sub(r'(?i)^\s*(?:brand(?:\s+name)?)\s*[:\-]\s*', '', line).strip()
        if re.search(rf'(?i)\b{re.escape(suffix)}\b', candidate):
            # Avoid treating paragraphs or multiple merged OCR lines as a brand.
            if 2 <= len(candidate.split()) <= 7 and not re.search(r'(?i)government warning|according to', candidate):
                return candidate
    return None


def check_field(field: str, expected: str, observed: str) -> Result:
    if not expected.strip():
        return Result(field, 'Needs Review', 'No application value supplied')
    observed_lines = lines(observed)
    spans = observed_lines + [' '.join(observed_lines[i:i+2]) for i in range(len(observed_lines)-1)]
    if any(normalize(expected) == normalize(span) for span in spans):
        return Result(field, 'Match', 'Complete field text confirmed')
    if field == 'Class/type' and any(re.search(r'(?<![a-z0-9])' + r'[^a-z0-9]*'.join(map(re.escape, re.findall(r'[a-z0-9]+', expected.casefold()))) + r'(?![a-z0-9])', span.casefold()) for span in spans):
        return Result(field, 'Match', 'Class/type confirmed')
    labels = {'Brand': r'brand(?:\s+name)?', 'Class/type': r'(?:class\s*/\s*type|class|type)'}
    pattern = labels.get(field)
    if pattern:
        for line in lines(observed):
            match = re.match(rf'(?i)^\s*(?:{pattern})\s*[:\-]\s*(.+?)\s*$', line)
            if match:
                return Result(field, 'Mismatch', f'Expected {expected}; detected {match.group(1)}')
    if field == 'Brand':
        candidate = brand_candidate(expected, observed)
        if candidate and normalize(candidate) != normalize(expected):
            return Result(field, 'Mismatch', f'Expected {expected}; detected likely brand {candidate}')
    return Result(field, 'Needs Review', 'Expected text not confirmed by OCR; inspect image')


def check_abv(expected: str, observed: str) -> Result:
    try:
        target = float(expected.strip().replace('%', ''))
    except ValueError:
        return Result('ABV', 'Needs Review', 'Enter ABV as a number, e.g. 45')
    # Percentages not identified as ABV (e.g., marketing copy) are not proof of mismatch.
    tagged = re.findall(r'(?i)(?:abv|alc\.?\s*/?\s*vol\.?|alcohol\s+by\s+volume)\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)\s*%', observed)
    tagged += re.findall(r'(?i)(\d{1,3}(?:\.\d+)?)\s*%\s*(?:abv|alc\.?\s*/?\s*vol\.?)', observed)
    values = [float(v) for v in tagged]
    if not values:
        values = [float(v) for v in re.findall(r'(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%', observed)]
    if not values:
        return Result('ABV', 'Needs Review', 'No ABV percentage detected')
    if not (0 <= target <= 100) or any(not (0 <= v <= 100) for v in values):
        return Result('ABV', 'Needs Review', 'Invalid ABV detected')
    if len(set(values)) > 1:
        return Result('ABV', 'Needs Review', 'Conflicting ABV percentages detected')
    proofs = [float(v) for v in re.findall(r'(?i)\b(\d+(?:\.\d+)?)\s*proof\b', observed)]
    if proofs and any(abs(v / 2 - values[0]) > 0.01 for v in proofs):
        return Result('ABV', 'Mismatch', 'Printed proof and ABV are inconsistent')
    if abs(values[0]-target) < 0.001:
        return Result('ABV', 'Match', f'Expected {target:g}%; detected {values[0]:g}%')
    if not tagged and len(values) != 1:
        return Result('ABV', 'Needs Review', 'Multiple percentages detected without an ABV label')
    return Result('ABV', 'Mismatch', f'Expected {target:g}%; detected {", ".join(f"{v:g}%" for v in values)}')


def milliliters(value: str) -> float | None:
    match = re.search(r'(?i)(\d+(?:\.\d+)?)\s*(ml|m[l1]|lit(?:er|re)s?|l)\b', value)
    if not match:
        return None
    unit = match.group(2).lower()
    return float(match.group(1)) * (1000 if unit.startswith('l') and unit not in ('ml', 'm1') else 1)


def check_volume(expected: str, observed: str) -> Result:
    target = milliliters(expected)
    if target is None:
        return Result('Net contents', 'Needs Review', 'Enter volume as 750 mL or 1 L')
    candidates = []
    for line in lines(observed):
        # Volume with units is a distinctive signal; other numbers aren't used.
        for m in re.finditer(r'(?i)\b\d+(?:\.\d+)?\s*(?:ml|m1|liters?|litres?|l)\b', line):
            v = milliliters(m.group())
            if v is not None:
                candidates.append(v)
    if not candidates:
        return Result('Net contents', 'Needs Review', 'No readable volume detected')
    if len(set(candidates)) > 1:
        return Result('Net contents', 'Needs Review', 'Conflicting volumes detected; inspect image')
    if abs(candidates[0]-target) < .01:
        return Result('Net contents', 'Match', f'Expected {target:g} mL; detected matching volume')
    return Result('Net contents', 'Mismatch', f'Expected {target:g} mL; detected {candidates[0]:g} mL')


def check_warning(observed: str) -> Result:
    # Keep punctuation and case. OCR cannot establish bold typography.
    clean = re.sub(r'\s+', ' ', observed).strip()
    expected = re.sub(r'\s+', ' ', WARNING)
    if expected in clean:
        return Result('Government warning', 'Match', 'Exact warning text confirmed by OCR; bold heading/layout still require visual review')
    if re.search(r'(?i)government\s+warning\s*:', clean) and 'birth defects' in clean.casefold() and 'health problems' in clean.casefold():
        return Result('Government warning', 'Mismatch', 'Warning detected but required wording or capitalization differs; inspect image')
    return Result('Government warning', 'Needs Review', 'Exact warning text not confirmed; inspect wording, capitalization and formatting')


def verify(application: dict[str, str], observed: str) -> list[Result]:
    return [check_field('Brand', application.get('brand', ''), observed),
            check_field('Class/type', application.get('type', ''), observed),
            check_abv(application.get('abv', ''), observed),
            check_volume(application.get('volume', ''), observed),
            check_warning(observed)]
