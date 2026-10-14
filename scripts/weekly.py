"""Weekly Highlights 1.11: configured review gate, frozen handoff, guarded installation."""
import argparse
import importlib.util
import json
import os
import shutil
import sys
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from weekly_common import (date_window, digest, dump_json, expected_records, extract_history,
                           file_hash, load_config, load_json, normalize_doi, plain_text, title_key, execution_records)


def deduplicate(records, history):
    old = [r for h in history.values() for r in h['records']]
    old_dois = {r['doi'] for r in old}
    kept, exact, historical, versions, issues = [], [], [], [], []
    ranked = sorted(enumerate(records), key=lambda p: (p[1].get('type') != '正式发表', p[0]))
    for _, raw in ranked:
        record = dict(raw)
        record['doi'] = normalize_doi(record.get('doi', ''))
        doi = record['doi']
        if not doi:
            raise ValueError('Every candidate must have a verified DOI')
        if doi in old_dois:
            historical.append(record)
            continue
        if any(r['doi'] == doi for r in kept):
            exact.append(record)
            continue
        known_relation = set()
        if record.get('version_relation_verified') is True and record.get('version_evidence_url'):
            known_relation = {normalize_doi(x) for x in record.get('related_dois', [])}
        related = next((r for r in old + kept if r['doi'] in known_relation or
                        (r.get('version_relation_verified') is True and r.get('version_evidence_url') and
                         doi in {normalize_doi(x) for x in r.get('related_dois', [])})), None)
        if related:
            versions.append({'record': record, 'matches': related['doi'], 'reason': 'verified version relation'})
            continue
        key = title_key(record.get('title', ''))
        for other in old + kept:
            other_key = title_key(other.get('title', ''))
            distinct = record.get('distinct_evidence_url') and other['doi'] in {normalize_doi(x) for x in record.get('distinct_from', [])}
            reverse = other.get('distinct_evidence_url') and doi in {normalize_doi(x) for x in other.get('distinct_from', [])}
            if key and other_key and not distinct and not reverse:
                ratio = SequenceMatcher(None, key, other_key).ratio()
                if key == other_key or (min(len(key), len(other_key)) >= 55 and ratio >= .94):
                    issues.append({'doi': doi, 'other_doi': other['doi'], 'title': record.get('title'),
                                   'reason': 'similar title; verify versions or document distinct studies'})
        kept.append(record)
    # Preserve user/discovery order after preferring formal articles within version pairs.
    order = {normalize_doi(r.get('doi', '')): i for i, r in reversed(list(enumerate(records)))}
    kept.sort(key=lambda r: order[r['doi']])
    return {'unique': kept, 'within_duplicates': exact, 'history_duplicates': historical,
            'version_duplicates': versions, 'version_review_required': issues}


def checked_review(path, approved=False, config=None):
    data = load_json(path)
    if data.get('kind') != ('approved' if approved else 'review'):
        raise ValueError('Incorrect handoff kind')
    saved = data.get('integrity')
    unsigned = {k: v for k, v in data.items() if k != 'integrity'}
    if saved != digest(unsigned):
        raise ValueError('Review/approval changed; regenerate and obtain approval for the new revision')
    if config is not None:
        from selection import assert_selection
        assert_selection(data, config)
    return data


def validate_candidate(record, window, config):
    for key in ('title', 'summary', 'abstract', 'landing_url', 'date_source_url', 'abstract_source_url'):
        if not str(record.get(key, '')).strip():
            raise ValueError(f"{record['doi']}: missing {key}")
    if record.get('journal') not in config['journals'] or record.get('type') not in ('正式发表', '预印本'):
        raise ValueError('Invalid journal/type')
    if record['type'] == '预印本' and not config['journal_profiles'][record['journal']].get('include_preprints', False):
        raise ValueError('Preprints were not selected for this journal')
    when = date.fromisoformat(record.get('publication_date', ''))
    if not date.fromisoformat(window[0]) <= when <= date.fromisoformat(window[1]):
        raise ValueError(f"Outside date window: {record['doi']}")
    if record.get('date_verified') is not True or record.get('abstract_verified') is not True:
        raise ValueError('Date and full abstract must be verified before review')
    screen = record.get('screening', {})
    if screen.get('decision') != 'include' or any(not screen.get(k) for k in ('question', 'contribution', 'relevance')):
        raise ValueError('Missing evidence-based screening decision')
    # Check scientific conversion now, not after an expensive rendering cycle.
    if record.get('abstract_html') and plain_text(record['abstract_html']) != plain_text(record['abstract']):
        raise ValueError('Preserved abstract markup and plain text do not agree')


def review_text(data):
    blocks = [f"筛选日期范围：{data['window'][0]} 至 {data['window'][1]}（{data['timezone']}，含首尾）\n" +
              '\n'.join(f"{j}：来源 {data['discovery'][j]['source']}；检查 {data['discovery'][j]['checked']} 条；" +
                        ('覆盖完整' if data['discovery'][j]['coverage_complete'] else '覆盖不完整，结果仅代表已核验范围') +
                        f"；入选 {sum(r['journal'] == j for r in data['articles'])} 篇" for j in data['journal_order']) +
              f"\n首版前去重：本轮重复 {data['counts']['within_duplicates']}；历史DOI重复 {data['counts']['history_duplicates']}；确认版本重复 {data['counts']['version_duplicates']}。"]
    blocks.insert(0, '本轮筛选范围：' + data['research_scope']['criteria'])
    for journal in data['journal_order']:
        rows = [r for r in data['articles'] if r['journal'] == journal]
        lines = [f"weekly highlights-{data['journal_names'][journal]} ({journal})", '']
        for index, record in enumerate(rows, 1):
            lines += [f"{index}. Title：{plain_text(record['title'])}",
                      f"https://doi.org/{record['doi']}", f"Summary：{record['summary']}", '']
        if not rows:
            complete = data['discovery'][journal]['coverage_complete']
            lines += ['本次日期窗口内未发现符合筛选条件的新增文章' if complete else '本轮已核验范围内暂无符合条件的新增文章；来源覆盖不完整', '']
        blocks.append('```text\n' + '\n'.join(lines).rstrip() + '\n```')
    return '\n\n'.join(blocks) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    pre = sub.add_parser('preflight')
    pre.add_argument('--today')
    pre.add_argument('--out', type=Path)
    prep = sub.add_parser('prepare-review')
    prep.add_argument('--records', type=Path, required=True)
    prep.add_argument('--today')
    prep.add_argument('--out-dir', type=Path, required=True)
    approve = sub.add_parser('approve')
    approve.add_argument('--review', type=Path, required=True)
    approve.add_argument('--confirmation', required=True, help='Record actual user authorization; never synthesize it')
    approve.add_argument('--output', type=Path, required=True)
    meta = sub.add_parser('metadata')
    meta.add_argument('--approved', type=Path, required=True)
    meta.add_argument('--journal', required=True, help='Selected journal ID')
    meta.add_argument('--output', type=Path, required=True)
    meta.add_argument('--evidence', type=Path, help='Verified author/PDF evidence; cannot change confirmed title, Summary or abstract')
    install = sub.add_parser('install')
    install.add_argument('--approved', type=Path, required=True)
    install.add_argument('--journal', required=True, help='Selected journal ID')
    install.add_argument('--candidate', type=Path, required=True)
    install.add_argument('--qa', type=Path, required=True)
    install.add_argument('--metadata', type=Path, required=True, help='Exact verified metadata used to build candidate')
    install.add_argument('--archive-receipt', type=Path,
                         help='Optional project archive receipt; otherwise retain a verified backup under workspace/_archive')
    args = parser.parse_args()
    config = load_config(args.config)
    if hasattr(args, 'journal') and args.journal not in config['journals']:
        raise ValueError('Journal was not selected in local configuration')
    if args.command in ('preflight', 'prepare-review'):
        histories = {j: extract_history(p) for j, p in config['paths'].items()}
        window = date_window(config, args.today)
    if args.command == 'preflight':
        result = {'version': '1.11', 'window': window, 'workspace_root': config['workspace_root'],
                  'python': sys.executable, 'dependencies': {p: bool(importlib.util.find_spec(p)) for p in ('docx', 'pypdf', 'PIL', 'lxml')},
                  'history': {j: {'path': h['path'], 'sha256': h['sha256'], 'count': len(h['records'])} for j, h in histories.items()},
                  'preferred_execution_model': config['execution']['preferred_model']}
        if args.out:
            dump_json(args.out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not all(result['dependencies'].values()):
            raise SystemExit('Missing dependencies; do not install without authorization')
    elif args.command == 'prepare-review':
        if args.out_dir.exists():
            raise FileExistsError('Choose a new review revision directory')
        source = load_json(args.records)
        if source.get('window') != window:
            raise ValueError('Input window differs from execution window; use --today for explicit replay')
        for j in config['journals']:
            discovery = source.get('discovery', {}).get(j, {})
            if not all(k in discovery for k in ('source', 'checked', 'coverage_complete', 'stop_reason')) or not isinstance(discovery['coverage_complete'], bool):
                raise ValueError('Discovery must describe source and coverage for each journal')
            if type(discovery['checked']) is not int or discovery['checked'] < 0 or not discovery['source'] or not discovery['stop_reason']:
                raise ValueError('Discovery counts/source/stop reason must be explicit')
        if set(source.get('discovery', {})) != set(config['journals']):
            raise ValueError('Discovery must cover exactly selected journals')
        if any(r.get('journal') not in config['journals'] for r in source['articles']):
            raise ValueError('Input includes an unselected journal')
        audit = deduplicate(source['articles'], histories)
        if audit['version_review_required']:
            dump_json(args.out_dir / 'blocked-dedup-audit.json', audit)
            raise SystemExit('VERSION_REVIEW_REQUIRED: no formal copy-ready list generated')
        for r in audit['unique']:
            validate_candidate(r, window, config)
        for j in config['journals']:
            for n, r in enumerate([r for r in audit['unique'] if r['journal'] == j], 1):
                r['order'] = n
        data = {'kind': 'review', 'version': '1.11', 'window': window, 'discovery': source['discovery'],
                'history': {j: {'path': h['path'], 'sha256': h['sha256']} for j, h in histories.items()},
                'articles': audit['unique'], 'counts': {k: len(v) for k, v in audit.items()}}
        from selection import selection_hash
        data.update(selection_sha256=selection_hash(config), journal_order=list(config['journals']), timezone=config['timezone'],
                    journal_names={j:p['name'] for j,p in config['journal_profiles'].items()}, research_scope=config['research_scope'])
        data['revision'] = digest(data)[:16]
        data['integrity'] = digest(data)
        dump_json(args.out_dir / 'review.json', data)
        dump_json(args.out_dir / 'dedup-audit.json', audit)
        (args.out_dir / 'review-list.txt').write_text(review_text(data), encoding='utf-8')
        print(json.dumps({'revision': data['revision'], 'counts': data['counts'], 'list': str(args.out_dir / 'review-list.txt')}, ensure_ascii=False))
    elif args.command == 'approve':
        data = checked_review(args.review, config=config)
        if not args.confirmation.strip():
            raise ValueError('Actual authorization text required')
        for journal, h in data['history'].items():
            if config['paths'][journal] != h['path'] or file_hash(h['path']) != h['sha256']:
                raise RuntimeError('History changed since review; re-deduplicate before approval')
        data.pop('integrity')
        data.update(kind='approved', authorization=args.confirmation.strip(), approved_at=datetime.now(timezone.utc).isoformat())
        data['integrity'] = digest(data)
        dump_json(args.output, data)
        print(f'APPROVAL_RECORDED revision={data["revision"]}')
    elif args.command == 'metadata':
        data = checked_review(args.approved, True, config)
        records = execution_records(data, args.journal, args.evidence)
        if not records:
            print('ZERO_NEW: leave rolling document unchanged')
            return
        if args.output.exists():
            raise FileExistsError(args.output)
        # Validate in temporary storage so a failed enrichment never leaves a ready-looking output.
        import tempfile
        try:
            with tempfile.TemporaryDirectory() as temp:
                candidate = Path(temp) / 'metadata.json'
                dump_json(candidate, records)
                expected_records(candidate)
        except Exception:
            raise ValueError('Missing verified authors or scientific-text conflict; supply checked --evidence, escalate content conflicts')
        dump_json(args.output, records)
        print(f'METADATA_READY {len(records)}')
    elif args.command == 'install':
        from render_review import verify_qa
        from validate_weekly_docx import validate_document
        data = checked_review(args.approved, True, config)
        records = [r for r in data['articles'] if r['journal'] == args.journal]
        if not records:
            raise ValueError('ZERO_NEW: do not install')
        metadata = load_json(args.metadata)
        if [normalize_doi(r['doi']) for r in metadata] != [r['doi'] for r in records]:
            raise ValueError('Installation metadata order differs from approval')
        for approved_record, actual in zip(records, metadata):
            for key in ('title', 'summary', 'abstract', 'publication_date', 'type', 'journal'):
                if plain_text(actual.get(key, '')) != plain_text(approved_record.get(key, '')):
                    raise ValueError(f'Installation metadata changes approved {key}')
        history = data['history'][args.journal]
        target = Path(config['paths'][args.journal])
        if str(target) != history['path'] or args.candidate.resolve() == target:
            raise ValueError('Candidate/destination mismatch')
        if args.archive_receipt:
            receipt = load_json(args.archive_receipt)
        else:
            import uuid
            if not target.is_file() or file_hash(target) != history['sha256']:
                raise RuntimeError('Source changed before archive; re-deduplicate')
            folder = Path(config['workspace_root']) / '_archive' / ('weekly-highlights-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:6])
            folder.mkdir(parents=True, exist_ok=False)
            archive_path = folder / target.name
            shutil.copyfile(target, archive_path)
            receipt = {'original_path': str(target), 'archived_path': str(archive_path), 'sha256': file_hash(archive_path)}
            dump_json(folder / 'archive-receipt.json', receipt)
        archived = Path(receipt['archived_path']).resolve()
        root = Path(config['workspace_root'])
        if not archived.is_relative_to(root / '_archive') or str(Path(receipt['original_path']).resolve()) != str(target):
            raise ValueError('Archive receipt is outside the project archive or wrong target')
        if file_hash(archived) != history['sha256'] or receipt['sha256'].lower() != history['sha256']:
            raise RuntimeError('Archive differs from reviewed source')
        if target.exists() and file_hash(target) != history['sha256']:
            raise RuntimeError('Source changed concurrently; do not overwrite')
        verify_qa(args.qa, args.candidate)
        validate_document(args.candidate, args.metadata, '.'.join(str(int(x)) for x in data['window'][1].split('-')), archived)
        pending = target.with_name(target.name + '.weekly-pending-' + data['revision'])
        if pending.exists():
            raise FileExistsError(pending)
        shutil.copyfile(args.candidate, pending)
        candidate_hash = file_hash(args.candidate)
        if file_hash(pending) != candidate_hash:
            raise RuntimeError('Staged installation hash mismatch')
        if target.exists() and file_hash(target) != history['sha256']:
            raise RuntimeError('Source changed during staging')
        os.replace(pending, target)
        if file_hash(target) != candidate_hash:
            raise RuntimeError('Installed hash mismatch')
        print(f'INSTALLED {target} sha256={candidate_hash}')


if __name__ == '__main__':
    main()
