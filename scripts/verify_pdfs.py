"""Verify PDF readability AND article identity; paths cannot escape base-dir."""
import argparse
from pathlib import Path
from pypdf import PdfReader
from weekly_common import DOI_RE, file_hash, load_json, normalize_doi, title_key, within


def verify_pdf(path, record):
    path = Path(path)
    with path.open('rb') as f:
        if f.read(5) != b'%PDF-':
            raise ValueError('Not a PDF')
    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError('PDF has no pages')
    text = '\n'.join(page.extract_text() or '' for page in reader.pages[:3])
    if len(text.strip()) < 100:
        raise ValueError('Insufficient extractable text; manual identity verification required')
    actual_dois = {normalize_doi(m.group()) for m in DOI_RE.finditer(text)}
    title = title_key(record.get('title', ''))
    has_doi = normalize_doi(record['doi']) in actual_dois
    has_title = len(title) >= 25 and title in title_key(text)
    if not has_doi and not has_title:
        raise ValueError('PDF identity mismatch: neither expected DOI nor full title found')
    first = text[:800].casefold()
    if any(label in first for label in ('supporting information', 'supplementary information', 'supplementary material', 'supporting appendix')):
        raise ValueError('Likely supporting information, not the main article')
    return {'bytes': path.stat().st_size, 'pages': len(reader.pages), 'sha256': file_hash(path),
            'identity': 'doi' if has_doi else 'title'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata', type=Path, required=True)
    p.add_argument('--base-dir', type=Path, required=True)
    args = p.parse_args()
    failures = []
    for record in load_json(args.metadata):
        try:
            result = verify_pdf(within(args.base_dir, record['pdf_file']), record)
            print('OK', record['doi'], result)
        except Exception as exc:
            failures.append((record.get('doi'), str(exc)))
    if failures:
        for row in failures:
            print('FAIL', *row)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
