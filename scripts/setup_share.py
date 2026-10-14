"""Recipient setup: explicit workspace, existing/new history and tested review model."""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from weekly_common import dump_json, load_json, load_config, within

SKILL = Path(__file__).resolve().parents[1]
PLATFORMS = ['codex', 'pi', 'workbuddy', 'trae', 'openclaw', 'other']


def configure(args):
    root = Path(args.workspace).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError('Select an existing workspace directory; create it explicitly first if needed')
    output = root / '.weekly-highlights' / 'config.json'
    if output.exists():
        raise FileExistsError('Local configuration exists; use a new workspace or deliberately revise and re-test it')
    config = load_json(SKILL / 'config.example.json')
    config['workspace_root'] = str(root)
    config['setup'] = {'status': 'vision_pending', 'history_mode': 'new' if args.new_library else 'existing'}
    config['execution'].update(preferred_model=args.worker_model, review_model=args.review_model or args.worker_model,
                               provider=args.provider, host=args.platform, host_version=args.host_version)
    config['render'] = {'soffice': args.soffice or shutil.which('soffice.com') or shutil.which('soffice') or '',
                        'pdftoppm': args.pdftoppm or shutil.which('pdftoppm') or ''}
    config['screening_profile'] = '.weekly-highlights/screening-profile.md'
    if args.acp_docx:
        config['journals']['ACP'] = str(Path(args.acp_docx).expanduser().resolve().relative_to(root))
    if args.pnas_docx:
        config['journals']['PNAS'] = str(Path(args.pnas_docx).expanduser().resolve().relative_to(root))
    paths = {j: within(root, p) for j, p in config['journals'].items()}
    if args.new_library:
        if any(p.exists() for p in paths.values()):
            raise FileExistsError('New-library mode must not replace any existing Word file')
        from docx import Document
        for journal, path in paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = Document()
            doc.add_paragraph('weekly highlights-' + journal)
            doc.save(path)
    elif not all(p.is_file() for p in paths.values()):
        raise FileNotFoundError('Existing-library mode requires both historical Word files; choose paths or explicitly use --new-library')
    dump_json(output, config)
    profile = root / '.weekly-highlights' / 'screening-profile.md'
    if not profile.exists():
        shutil.copyfile(SKILL / 'references' / 'screening-profile.md', profile)
    pointer = SKILL / 'installation.local.json'
    # Only a local pointer is generated. Never include it in source or releases.
    if not pointer.exists():
        try:
            dump_json(pointer, {'config_path': str(output), 'generated_locally': True})
        except PermissionError:
            print('Skill directory is read-only: use --config or WEEKLY_HIGHLIGHTS_CONFIG for future calls')
    print(json.dumps({'config': str(output), 'status': 'vision_pending', 'next': 'make a vision challenge, invoke the selected model with image input, grade and finish'}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('configure')
    c.add_argument('--workspace', required=True)
    c.add_argument('--platform', choices=PLATFORMS, required=True)
    c.add_argument('--worker-model', required=True)
    c.add_argument('--review-model')
    c.add_argument('--provider', default='HOST_MANAGED')
    c.add_argument('--host-version', default='unknown')
    c.add_argument('--new-library', action='store_true')
    c.add_argument('--acp-docx')
    c.add_argument('--pnas-docx')
    c.add_argument('--soffice')
    c.add_argument('--pdftoppm')
    d = sub.add_parser('doctor')
    d.add_argument('--config', type=Path, required=True)
    models = sub.add_parser('models')
    models.add_argument('--config', type=Path, required=True)
    models.add_argument('--worker-model')
    models.add_argument('--review-model')
    models.add_argument('--provider')
    models.add_argument('--host-version')
    f = sub.add_parser('finish')
    f.add_argument('--config', type=Path, required=True)
    f.add_argument('--capability', type=Path, required=True)
    f.add_argument('--fallback-confirmed', action='store_true', help='User agreed to use the tested main/other model for vision')
    f.add_argument('--worker-capability', type=Path, help='Record the actual small-model test when selecting a fallback reviewer')
    args = p.parse_args()
    if args.command == 'configure':
        return configure(args)
    config = load_config(args.config, require_ready=False)
    if args.command == 'doctor':
        dependencies = {name: bool(importlib.util.find_spec(name)) for name in ['docx', 'pypdf', 'PIL', 'lxml']}
        print(json.dumps({'version': '1.01', 'python': sys.executable, 'dependencies': dependencies,
                          'render_tools': config['render'], 'setup': config['setup'],
                          'history': {j: Path(v).is_file() for j, v in config['paths'].items()}}, ensure_ascii=False, indent=2))
        return
    if args.command == 'models':
        raw = load_json(args.config)
        for arg, key in [('worker_model', 'preferred_model'), ('review_model', 'review_model'), ('provider', 'provider'), ('host_version', 'host_version')]:
            value = getattr(args, arg)
            if value:
                raw['execution'][key] = value
        raw['setup']['status'] = 'vision_pending'
        raw['setup'].pop('capability_receipt', None)
        dump_json(args.config, raw, overwrite=True)
        print('MODELS_CHANGED: repeat actual visual test before setup is ready')
        return
    from vision_probe import validate_receipt, identity
    receipt = validate_receipt(args.capability)
    if receipt['identity'] != identity(config):
        raise ValueError('Receipt does not match selected platform/provider/review model/client version')
    if receipt['identity']['model'] != config['execution']['preferred_model'] and not args.fallback_confirmed:
        raise ValueError('Explicitly confirm the main/other model fallback; do not misrepresent small-model vision as passing')
    if receipt['identity']['model'] != config['execution']['preferred_model']:
        from vision_probe import checked
        if not args.worker_capability:
            raise ValueError('Record the small-model test as well as the tested fallback reviewer')
        worker = checked(load_json(args.worker_capability))
        if worker.get('kind') != 'vision-capability' or worker['identity']['model'] != config['execution']['preferred_model']:
            raise ValueError('Worker test does not match the selected small model')
    if not all(importlib.util.find_spec(name) for name in ['docx', 'pypdf', 'PIL', 'lxml']):
        raise RuntimeError('Dependencies missing; setup is not ready')
    from weekly_common import extract_history
    for path in config['paths'].values():
        extract_history(path)
    for key in ['soffice', 'pdftoppm']:
        value = config['render'].get(key)
        if not value or not (Path(value).is_file() or shutil.which(value)):
            raise RuntimeError('Configure working LibreOffice and pdftoppm before completing setup')
    raw = load_json(args.config)
    raw['setup'].update(status='ready', capability_receipt=str(args.capability.resolve()),
                        vision_mode='small_model' if receipt['identity']['model'] == raw['execution']['preferred_model'] else 'tested_fallback_model')
    if args.worker_capability:
        raw['setup']['worker_capability_receipt'] = str(args.worker_capability.resolve())
    dump_json(args.config, raw, overwrite=True)
    print('SETUP_READY: configured paths and actual tested visual reviewer')


if __name__ == '__main__':
    main()
