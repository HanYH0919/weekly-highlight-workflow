"""Render immutable candidates, plan exact-pixel reuse, record actual visual review."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from weekly_common import digest, dump_json, file_hash, load_config, load_json


def pixels(path):
    with Image.open(path) as im:
        im = im.convert('RGB')
        return hashlib.sha256(str(im.size).encode() + im.tobytes()).hexdigest()


def seal(data):
    data['integrity'] = digest({k: v for k, v in data.items() if k != 'integrity'})
    return data


def validate_manifest(data):
    if data.get('integrity') != digest({k: v for k, v in data.items() if k != 'integrity'}):
        raise ValueError('Manifest changed')
    if file_hash(data['docx']) != data['docx_sha256'] or file_hash(data['pdf']) != data['pdf_sha256']:
        raise ValueError('Candidate or PDF changed since rendering')
    if not data['pages']:
        raise ValueError('No rendered pages')
    for page in data['pages']:
        if pixels(page['path']) != page['pixel_sha256']:
            raise ValueError('Page changed since rendering')
    return data


def verify_qa(path, candidate=None):
    qa = load_json(path)
    if qa.get('kind') != 'accepted-qa' or qa.get('integrity') != digest({k: v for k, v in qa.items() if k != 'integrity'}):
        raise ValueError('Missing or modified accepted visual review')
    manifest = validate_manifest(qa['render'])
    if candidate and (str(Path(candidate).resolve()) != manifest['docx'] or file_hash(candidate) != manifest['docx_sha256']):
        raise ValueError('QA belongs to a different candidate')
    if set(qa['inspected_pages']) | set(qa['reused_pages']) != set(range(1, len(manifest['pages']) + 1)):
        raise ValueError('QA has unreviewed pages')
    from vision_probe import validate_receipt
    capability = validate_receipt(qa['capability_receipt_path'])
    if file_hash(qa['capability_receipt_path']) != qa['capability_receipt_sha256'] or capability['identity'] != qa['visual_review_identity']:
        raise ValueError('QA visual capability evidence changed')
    return qa


def numbers(value):
    return {int(v) for v in value.split(',') if v.strip()}


def make_plan(current, baseline=None, force=None):
    current = validate_manifest(current)
    force = set(force or ()) | {1}
    hashes = set()
    if baseline:
        baseline = verify_qa(baseline)
        if baseline['render']['environment'] == current['environment']:
            hashes = {p['pixel_sha256'] for p in baseline['render']['pages']}
    total = set(range(1, len(current['pages']) + 1))
    if not force <= total:
        raise ValueError('Forced page is outside render')
    reused = {p['number'] for p in current['pages'] if p['pixel_sha256'] in hashes and p['number'] not in force}
    return seal({'kind': 'visual-plan', 'render': current, 'reused_pages': sorted(reused),
                 'required_pages': sorted(total - reused), 'baseline': str(Path(baseline['qa_path']).resolve()) if baseline else None})


def accept(plan, inspected, reviewer, output, capability=None):
    if not capability:
        raise ValueError('A tested visual-review capability is required')
    from vision_probe import validate_receipt
    receipt = validate_receipt(capability)
    if reviewer != receipt['identity']['model']:
        raise ValueError('Reviewer must be the actual tested model; do not label another model as this reviewer')
    if plan.get('integrity') != digest({k: v for k, v in plan.items() if k != 'integrity'}):
        raise ValueError('Visual plan changed')
    validate_manifest(plan['render'])
    if not reviewer.strip() or not set(plan['required_pages']) <= inspected:
        raise ValueError('Actual reviewer and all required page inspections must be recorded')
    total = set(range(1, len(plan['render']['pages']) + 1))
    if not inspected <= total:
        raise ValueError('Inspected page outside render')
    reused = set(plan['reused_pages']) - inspected
    if reused:
        baseline = verify_qa(plan['baseline'])
        allowed = {p['pixel_sha256'] for p in baseline['render']['pages']}
        if baseline['render']['environment'] != plan['render']['environment'] or any(plan['render']['pages'][i - 1]['pixel_sha256'] not in allowed for i in reused):
            raise ValueError('Reuse baseline no longer matches')
    qa = seal({'kind': 'accepted-qa', 'render': plan['render'], 'reviewer': reviewer,
               'accepted_at': datetime.now(timezone.utc).isoformat(), 'qa_path': str(Path(output).resolve()),
               'inspected_pages': sorted(inspected), 'reused_pages': sorted(reused),
               'visual_review_identity': receipt['identity'], 'capability_receipt_path': str(Path(capability).resolve()),
               'capability_receipt_sha256': file_hash(capability)})
    dump_json(output, qa)
    return qa


def render(docx, output, environment_id, config):
    output, docx = Path(output).resolve(), Path(docx).resolve()
    if output.exists():
        raise FileExistsError('Use a fresh render directory for each candidate')
    soffice = config['render'].get('soffice') or shutil.which('soffice.com') or shutil.which('soffice')
    pdftoppm = config['render'].get('pdftoppm') or shutil.which('pdftoppm')
    if not soffice or not pdftoppm:
        raise FileNotFoundError('LibreOffice/pdftoppm unavailable; configure existing tools, do not silently skip rendering')
    output.mkdir(parents=True)
    before = file_hash(docx)
    profile = (output / 'lo-profile').as_uri()
    kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    subprocess.run([soffice, '-env:UserInstallation=' + profile, '--headless', '--convert-to', 'pdf', '--outdir', str(output), str(docx)],
                   check=True, capture_output=True, timeout=180, **kwargs)
    pdf = output / (docx.stem + '.pdf')
    if not pdf.is_file():
        raise RuntimeError('Renderer returned without candidate PDF')
    subprocess.run([pdftoppm, '-r', '110', '-png', str(pdf), str(output / 'page')], check=True, capture_output=True, timeout=240, **kwargs)
    pages = sorted(output.glob('page-*.png'), key=lambda p: int(p.stem.rsplit('-', 1)[1]))
    if before != file_hash(docx):
        raise RuntimeError('Candidate changed while rendering')
    from pypdf import PdfReader
    if len(pages) != len(PdfReader(str(pdf)).pages):
        raise RuntimeError('Incomplete PNG render')
    manifest = seal({'kind': 'render', 'docx': str(docx), 'docx_sha256': before, 'pdf': str(pdf),
                     'pdf_sha256': file_hash(pdf), 'environment': digest({'id': environment_id, 'soffice': file_hash(soffice), 'pdftoppm': file_hash(pdftoppm), 'dpi': 110}),
                     'created_at': datetime.now(timezone.utc).isoformat(),
                     'pages': [{'number': i, 'path': str(p), 'pixel_sha256': pixels(p)} for i, p in enumerate(pages, 1)]})
    dump_json(output / 'render-manifest.json', manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('render')
    r.add_argument('--docx', type=Path, required=True)
    r.add_argument('--output-dir', type=Path, required=True)
    r.add_argument('--environment-id', required=True)
    r.add_argument('--config', type=Path)
    plan = sub.add_parser('plan')
    plan.add_argument('--current', type=Path, required=True)
    plan.add_argument('--baseline', type=Path)
    plan.add_argument('--force-pages', default='1')
    plan.add_argument('--output', type=Path, required=True)
    a = sub.add_parser('accept')
    a.add_argument('--plan', type=Path, required=True)
    a.add_argument('--inspected', required=True)
    a.add_argument('--reviewer', required=True)
    a.add_argument('--output', type=Path, required=True)
    a.add_argument('--config', type=Path)
    args = p.parse_args()
    if args.command == 'render':
        result = render(args.docx, args.output_dir, args.environment_id, load_config(args.config))
    elif args.command == 'plan':
        result = make_plan(load_json(args.current), args.baseline, numbers(args.force_pages))
        dump_json(args.output, result)
    else:
        config = load_config(args.config)
        result = accept(load_json(args.plan), numbers(args.inspected), args.reviewer, args.output, config['setup']['capability_receipt'])
    print(json.dumps({k: v for k, v in result.items() if k not in ('render', 'pages')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
