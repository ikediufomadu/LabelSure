"""LabelSure: single-image review and CSV-mapped batch review."""
import csv
import time
from io import StringIO, BytesIO
from pathlib import Path

import streamlit as st
from ocr import extract_text
from verification import verify

st.set_page_config(page_title='LabelSure', page_icon='🔎', layout='centered')
st.title('LabelSure')
st.caption('Alcohol label verification assistant · Human review required')

COLUMNS = ['filename', 'brand', 'type', 'abv', 'volume']
RESULT_COLUMNS = ['file', 'field', 'status', 'detail', 'seconds']


def application_fields(key):
    st.write('**Application details**')
    return {
        'brand': st.text_input('Brand name', 'OLD TOM DISTILLERY', key=f'{key}_brand'),
        'type': st.text_input('Class / type', 'Kentucky Straight Bourbon Whiskey', key=f'{key}_type'),
        'abv': st.text_input('Alcohol by volume (%)', '45', key=f'{key}_abv'),
        'volume': st.text_input('Net contents', '750 mL', key=f'{key}_volume'),
    }


def show_result(result):
    marker = {'Match': 'green', 'Mismatch': 'red', 'Needs Review': 'orange', 'Error': 'red'}.get(result.status, 'orange')
    st.markdown(f'**:{marker}[{result.field}: {result.status}]** — {result.detail}')


def parse_manifest(data: bytes) -> dict[str, dict[str, str]]:
    """Match each uploaded image to its own application row by exact filename."""
    try:
        content = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('CSV must be UTF-8 encoded') from exc
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames or any(c not in reader.fieldnames for c in COLUMNS):
        raise ValueError('CSV requires columns: ' + ', '.join(COLUMNS))
    applications = {}
    for row_number, row in enumerate(reader, start=2):
        name = (row.get('filename') or '').strip()
        if not name or Path(name).name != name:
            raise ValueError(f'Row {row_number}: filename must be a plain image filename')
        if name in applications:
            raise ValueError(f'Duplicate filename in CSV: {name}')
        applications[name] = {field: (row.get(field) or '').strip() for field in COLUMNS[1:]}
    if not applications:
        raise ValueError('CSV has no application rows')
    return applications


def process(files, applications, batch=False):
    if not files:
        st.warning('Upload at least one image.')
        return
    if len(files) > 300:
        st.error('Maximum 300 images per batch.')
        return
    names = [file.name for file in files]
    if len(names) != len(set(names)):
        st.error('Image filenames must be unique.')
        return
    if set(names) != set(applications):
        missing = sorted(set(names) - set(applications))
        extra = sorted(set(applications) - set(names))
        st.error(f'CSV/image mismatch. Images without rows: {missing or "none"}. Rows without images: {extra or "none"}.')
        return

    records = []
    progress = st.progress(0)
    total_start = time.perf_counter()
    for i, file in enumerate(files):
        with st.expander(file.name, expanded=not batch):
            start = time.perf_counter()
            try:
                data = file.getvalue()
                if len(data) > 10 * 1024 * 1024:
                    raise ValueError('Image exceeds 10 MB')
                if not batch:
                    st.image(data, width=350)
                with st.spinner('Reading label...'):
                    observed = extract_text(data)
                seconds = time.perf_counter() - start
                if not observed.strip():
                    st.warning('No readable text detected; manual review required.')
                for result in verify(applications[file.name], observed):
                    show_result(result)
                    records.append({'file': file.name, 'field': result.field,
                                    'status': result.status, 'detail': result.detail,
                                    'seconds': f'{seconds:.2f}'})
                st.caption(f'OCR + verification: {seconds:.2f}s ' + ('(over 5s target)' if seconds > 5 else '(within 5s target)'))
                with st.expander('OCR text'):
                    st.text(observed or '(none)')
            except Exception as exc:
                seconds = time.perf_counter() - start
                st.error(f'Unable to process image: {exc}')
                records.append({'file': file.name, 'field': 'Image', 'status': 'Error',
                                'detail': str(exc), 'seconds': f'{seconds:.2f}'})
        progress.progress((i + 1) / len(files))

    if batch:
        st.subheader('Batch summary')
        elapsed = time.perf_counter() - total_start
        durations = {r['file']: float(r['seconds']) for r in records}
        cols = st.columns(3)
        cols[0].metric('Images', len(files))
        cols[1].metric('Total time', f'{elapsed:.2f}s')
        cols[2].metric('Images over 5s', sum(t > 5 for t in durations.values()))
        st.caption('Times include OCR and verification (not upload time). First image may include model initialization. Counts are per field.')
        counts = {s: sum(r['status'] == s for r in records) for s in ('Match', 'Mismatch', 'Needs Review', 'Error')}
        cols = st.columns(4)
        for col, (status, count) in zip(cols, counts.items()):
            col.metric(status, count)
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=RESULT_COLUMNS)
    writer.writeheader()
    writer.writerows(records)
    st.download_button('Download CSV results', output.getvalue(), 'label_results.csv',
                       mime='text/csv', key='batch_download' if batch else 'single_download')


single, batch = st.tabs(['Single label', 'Batch processing'])
with single:
    st.write('Verify one label against its application.')
    with st.form('single_form'):
        application = application_fields('single')
        file = st.file_uploader('Upload label (PNG or JPG)', type=['png', 'jpg', 'jpeg'], key='single_file')
        submitted = st.form_submit_button('Verify label', type='primary')
    if submitted:
        process([file] if file else [], {file.name: application} if file else {})

with batch:
    st.write('Upload label images and a CSV containing **one application per image**. Filenames must match exactly.')
    sample = ('filename,brand,type,abv,volume\n'
              '01_correct.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45,750 mL\n'
              '02_wrong_abv.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45,750 mL\n')
    st.download_button('Download example CSV template', sample, 'applications_template.csv', mime='text/csv')
    with st.form('batch_form'):
        files = st.file_uploader('Upload multiple label images', type=['png', 'jpg', 'jpeg'],
                                 accept_multiple_files=True, key='batch_files')
        manifest = st.file_uploader('Upload application CSV', type=['csv'], key='manifest')
        submitted = st.form_submit_button('Verify batch', type='primary')
    if submitted:
        if not manifest:
            st.error('Upload an application CSV to run a batch.')
        else:
            try:
                applications = parse_manifest(manifest.getvalue())
                process(files, applications, batch=True)
            except ValueError as exc:
                st.error(str(exc))

st.caption('Prototype only. Warning typography must be visually checked. Images are not intentionally saved.')

