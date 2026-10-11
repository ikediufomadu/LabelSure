from io import BytesIO
from PIL import Image, ImageOps

_engine = None

def extract_text(data: bytes) -> str:
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR
        _engine = RapidOCR()
    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image).convert('RGB')
    if image.width * image.height > 16_000_000:
        raise ValueError('Image is too large (maximum 16 megapixels).')
    import numpy as np
    result = _engine(np.asarray(image))
    # RapidOCR newer releases expose txts; older releases return a tuple.
    if hasattr(result, 'txts'):
        return '\n'.join(result.txts or [])
    items = result[0] if isinstance(result, tuple) else result
    return '\n'.join(item[1] for item in (items or []))
