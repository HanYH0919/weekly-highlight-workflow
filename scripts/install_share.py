"""Install a downloaded skill locally; configuration and vision validation are separate gates."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(root):
    root = Path(root).resolve()
    manifest = root / 'SHA256SUMS.txt'
    if not manifest.is_file():
        raise FileNotFoundError('Release manifest is missing; use a versioned download from the repository')
    paths = []
    for line in manifest.read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        if len(expected) != 64 or relative in paths or relative == 'SHA256SUMS.txt':
            raise ValueError('Malformed release manifest')
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or sha(path) != expected:
            raise ValueError('Release checksum mismatch: ' + relative)
        if any(part in {'.git', '__pycache__', 'installation.local.json', 'config.json'} for part in Path(relative).parts):
            raise ValueError('Local/private file is not a release file: ' + relative)
        paths.append(relative)
    if not {'SKILL.md', 'START_HERE.md', 'scripts/install_share.py'} <= set(paths):
        raise ValueError('Release manifest omits required skill files')
    return paths


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform', choices=['codex', 'pi', 'trae', 'openclaw', 'workbuddy', 'other'], required=True)
    p.add_argument('--destination', type=Path, help='Exact skill folder; required for WorkBuddy/other clients whose import path varies')
    p.add_argument('--replace-existing', action='store_true')
    p.add_argument('--verify-only', action='store_true')
    args = p.parse_args()
    release_files = verify(ROOT)
    if args.verify_only:
        print('RELEASE_CHECKSUMS_PASS')
        return
    defaults = {'codex': Path.home()/'.agents/skills/weekly-highlight-workflow',
                'pi': Path.home()/'.agents/skills/weekly-highlight-workflow',
                'trae': Path.home()/'.trae-cn/skills/weekly-highlight-workflow',
                'openclaw': Path.home()/'.openclaw/skills/weekly-highlight-workflow'}
    destination = args.destination or defaults.get(args.platform)
    if destination is None:
        p.error('Use the client ZIP import or specify its verified --destination; the installer does not guess WorkBuddy directories')
    destination = destination.expanduser().resolve()
    if destination.name != 'weekly-highlight-workflow':
        raise ValueError('Destination must be the exact weekly-highlight-workflow skill folder, not a parent or unrelated project')
    if destination == ROOT.resolve() or destination.is_relative_to(ROOT.resolve()) or ROOT.resolve().is_relative_to(destination):
        raise ValueError('Destination cannot contain the package or be inside it')
    backup = None
    local_pointer = None
    if destination.exists():
        if not args.replace_existing:
            raise FileExistsError('Skill already exists; inspect it and explicitly request --replace-existing')
        if not (destination/'SKILL.md').is_file():
            raise ValueError('Existing destination is not a skill folder')
        if (destination/'installation.local.json').is_file():
            local_pointer = json.loads((destination/'installation.local.json').read_text(encoding='utf-8-sig'))
        backup_root = (destination.parent.parent / 'weekly-highlights-backups').resolve()
        backup = (backup_root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')).resolve()
        if not backup.is_relative_to(backup_root) or backup.is_relative_to(destination) or destination.is_relative_to(backup):
            raise ValueError('Invalid resolved backup directory')
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(backup))
    try:
        # Copy only checksummed release files, even when installing from a Git clone
        # or a working directory containing local configuration and probe answers.
        destination.mkdir(parents=True)
        for relative in release_files + ['SHA256SUMS.txt']:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        if local_pointer:
            (destination/'installation.local.json').write_text(json.dumps(local_pointer,ensure_ascii=False,indent=2),encoding='utf-8')
        verify(destination)
    except Exception:
        # Preserve any partial installation for diagnosis; never overwrite a concurrently created folder.
        if backup and not destination.exists():
            shutil.move(str(backup), str(destination))
        raise
    print(json.dumps({'installed_path': str(destination), 'version': '1.01', 'backup': str(backup) if backup else None,
                      'status': 'files_installed_configuration_or_vision_check_required',
                      'next': 'Read START_HERE.md and run setup_share.py configure; file import alone does not validate models'},ensure_ascii=False))


if __name__ == '__main__':
    main()
