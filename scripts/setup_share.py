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


def selection_config(config, selection_path):
    from copy import deepcopy
    from selection import validate_selection
    selected = load_json(selection_path)
    result = deepcopy(config)
    for key in ('journals', 'journal_profiles', 'research_scope'):
        if key not in selected:
            raise ValueError('Selection needs journals, journal_profiles and research_scope')
        result[key] = selected[key]
    result['version'] = '1.11'
    validate_selection(result)
    return result


def prepare_histories(config, new_library, allow_existing=False):
    from docx import Document
    from weekly_common import extract_history
    paths = {j: within(config['workspace_root'], p) for j,p in config['journals'].items()}
    # Check every selected target before creating anything.
    for path in paths.values():
        if path.exists():
            if new_library and not allow_existing:
                raise FileExistsError('New-library mode must not replace any existing Word file')
            extract_history(path)
        elif not new_library:
            raise FileNotFoundError('Every selected journal needs history; explicitly choose --new-library for missing histories')
    for journal,path in paths.items():
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            doc=Document()
            doc.add_paragraph('weekly highlights-' + config['journal_profiles'][journal]['name'])
            with path.open('xb') as stream:
                doc.save(stream)


def configure(args):
    root = Path(args.workspace).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError('Select an existing workspace directory')
    output = root / '.weekly-highlights' / 'config.json'
    if output.exists():
        raise FileExistsError('Local configuration exists; use scope to deliberately update journals/topics')
    config = load_json(SKILL / 'config.example.json')
    config['workspace_root'] = str(root)
    config = selection_config(config,args.selection)
    config['setup'] = {'status': 'vision_pending', 'history_mode': 'new' if args.new_library else 'existing'}
    config['execution'].update(preferred_model=args.worker_model, review_model=args.review_model or args.worker_model,
                               provider=args.provider, host=args.platform, host_version=args.host_version)
    config['render'] = {'soffice': args.soffice or shutil.which('soffice.com') or shutil.which('soffice') or '',
                        'pdftoppm': args.pdftoppm or shutil.which('pdftoppm') or ''}
    config['screening_profile'] = '.weekly-highlights/screening-profile.md'
    prepare_histories(config,args.new_library)
    dump_json(output, config)
    profile = root / '.weekly-highlights' / 'screening-profile.md'
    if not profile.exists():
        shutil.copyfile(SKILL / 'references' / 'screening-profile.md', profile)
    pointer = SKILL / 'installation.local.json'
    if not pointer.exists():
        try:
            dump_json(pointer, {'config_path': str(output), 'generated_locally': True})
        except PermissionError:
            print('Skill directory is read-only: use --config or WEEKLY_HIGHLIGHTS_CONFIG')
    print(json.dumps({'config': str(output), 'journals':list(config['journals']), 'scope':config['research_scope'],
                      'status': 'vision_pending', 'next': 'Run the actual model image test and finish'},ensure_ascii=False))


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
    c.add_argument('--selection',type=Path,required=True,help='Local JSON with selected journals, official sources and scope')
    c.add_argument('--soffice')
    c.add_argument('--pdftoppm')
    sc = sub.add_parser('scope',help='Change journal/topic selection or migrate 1.01; preserve existing documents and visual model settings')
    sc.add_argument('--config',type=Path,required=True)
    sc.add_argument('--selection',type=Path,required=True)
    sc.add_argument('--new-library',action='store_true',help='Create missing selected histories only; preserve all existing files')
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
    if args.command == 'scope':
        from uuid import uuid4
        previous = load_json(args.config)
        raw = selection_config(previous,args.selection)
        prepare_histories(raw,args.new_library,allow_existing=True)
        backup=args.config.with_name('config.backup-'+uuid4().hex+'.json')
        shutil.copyfile(args.config,backup)
        profile_backup = None
        if previous.get('version') != '1.11':
            # Old share editions shipped a subject-specific profile. Preserve it
            # as an archive, then install the neutral template for the new scope.
            relative = previous.get('screening_profile', '.weekly-highlights/screening-profile.md')
            profile = within(raw['workspace_root'], relative)
            profile.parent.mkdir(parents=True, exist_ok=True)
            if profile.exists():
                profile_backup = profile.with_name(profile.stem+'.pre-1.11-'+uuid4().hex+'.md')
                shutil.copyfile(profile, profile_backup)
            shutil.copyfile(SKILL/'references/screening-profile.md', profile)
            raw['screening_profile'] = relative
        dump_json(args.config,raw,overwrite=True)
        print(json.dumps({'selection_updated':True,'backup':str(backup),'journals':list(raw['journals']),
                          'legacy_profile_backup':str(profile_backup) if profile_backup else None,
                          'note':'Regenerate pending reviews/approvals; removed histories were not deleted'},ensure_ascii=False))
        return
    if args.command == 'doctor':
        dependencies = {name: bool(importlib.util.find_spec(name)) for name in ['docx', 'pypdf', 'PIL', 'lxml']}
        print(json.dumps({'version': '1.11', 'python': sys.executable, 'dependencies': dependencies,
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
    from selection import validate_selection
    validate_selection(config)
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
