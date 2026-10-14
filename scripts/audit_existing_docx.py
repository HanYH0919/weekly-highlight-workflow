"""Read-only history audit; retains the preview CLI."""
import argparse
import csv
import json
from pathlib import Path
from weekly_common import dump_json, extract_history, load_json
from weekly import deduplicate

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docx', required=True, type=Path)
    p.add_argument('--candidates', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    history = extract_history(args.docx)
    result = {'docx': history['path'], 'sha256': history['sha256'], 'historical_doi_count': len(history['records']),
              'records': history['records'], 'historical_dois': [r['doi'] for r in history['records']]}
    if args.candidates:
        if args.candidates.suffix.lower() == '.json':
            records = load_json(args.candidates)
            if isinstance(records, dict):
                records = records['articles']
        else:
            with args.candidates.open(encoding='utf-8-sig', newline='') as f:
                records = list(csv.DictReader(f, delimiter='\t'))
        result['audit'] = deduplicate(records, {'history': history})
    if args.output:
        dump_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
