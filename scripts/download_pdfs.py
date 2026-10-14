"""Download only frozen approved articles; resume verified files and write a manifest."""
import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from http_cache import fetch
from verify_pdfs import verify_pdf
from weekly import checked_review
from weekly_common import load_config, within, pdf_relative


def download_one(record, base, settings):
    relative = record.get('pdf_file') or pdf_relative(record)
    path = within(base, relative)
    row = {'type': record['type'], 'doi': record['doi'], 'title': record['title'],
           'source_url': record.get('pdf_url', ''), 'file': relative, 'status': '',
           'bytes': 0, 'pages': '', 'sha256': '', 'download_date': datetime.now(timezone.utc).isoformat(),
           'si_status': 'not_requested', 'note': ''}
    try:
        if path.exists():
            result = verify_pdf(path, record)
            return dict(row, status='verified_existing', **result)
        if not row['source_url']:
            return dict(row, status='missing_verified_pdf_url', file='', note='Find a legitimate article PDF and add verified evidence; do not guess')
        blob, info = fetch(row['source_url'], base / '_http_cache', timeout=settings['timeout_seconds'], retries=settings['retries'])
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix('.pdf.part')
        part.write_bytes(blob)
        result = verify_pdf(part, record)
        if path.exists():
            raise FileExistsError('PDF appeared concurrently; do not overwrite')
        part.replace(path)
        return dict(row, status='downloaded_verified', final_url=info['final_url'], **result)
    except HTTPError as exc:
        return dict(row, status='publisher_blocked_waiting_user' if exc.code in (401, 403) else 'http_error', file='', note=str(exc))
    except Exception as exc:
        return dict(row, status='verification_or_download_failed', file='', note=str(exc))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path)
    p.add_argument('--approved', type=Path, required=True)
    p.add_argument('--journal', required=True, help='Selected journal ID')
    p.add_argument('--base-dir', type=Path, required=True)
    p.add_argument('--evidence', type=Path, help='Optional verified metadata evidence containing PDF URLs; cannot change approved identity')
    args = p.parse_args()
    config = load_config(args.config)
    data = checked_review(args.approved, True, config)
    if args.journal not in config['journals']:
        raise ValueError('Journal was not selected in local configuration')
    from weekly_common import execution_records
    records = execution_records(data, args.journal, args.evidence)
    if not records:
        print('ZERO_NEW: no directory created')
        return
    expected = Path(config['paths'][args.journal]).parent / data['window'][1][2:].replace('-', '')
    if args.base_dir.resolve() != expected.resolve():
        raise ValueError(f'Download target must be configured journal/date directory: {expected}')
    args.base_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=min(int(config['execution']['max_workers']), 6)) as executor:
        rows = list(executor.map(lambda r: download_one(r, args.base_dir, config['execution']), records))
    fields = list(dict.fromkeys(key for row in rows for key in row))
    manifest = args.base_dir / 'download-manifest.tsv'
    if manifest.exists():
        suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        manifest.rename(args.base_dir / f'download-manifest.previous-{suffix}.tsv')
    with manifest.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)
    ok = sum(r['status'] in ('verified_existing', 'downloaded_verified') for r in rows)
    print(json.dumps({'verified': ok, 'total': len(rows), 'manifest': str(manifest)}, ensure_ascii=False))
    if ok != len(rows):
        raise SystemExit(2)

if __name__ == '__main__':
    main()
