"""Build clean standard/WorkBuddy archives from an explicit public-file allowlist."""
import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ['.gitignore', 'config.example.json', 'LICENSE', 'README.md', 'requirements.txt',
                'SKILL.md', 'START_HERE.md', 'VERSION.txt', 'agents/openai.yaml']
PUBLIC_GROUPS = [('scripts', '*.py'), ('references', '*.md'), ('tests', 'test_*.py')]


def checksums(root):
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    content = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(root).as_posix() + '\n' for p in files)
    (root/'SHA256SUMS.txt').write_text(content, encoding='utf-8')


def archive(root, output):
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(p for p in root.rglob('*') if p.is_file()):
            z.write(file, 'weekly-highlight-workflow/' + file.relative_to(root).as_posix())


def build(output):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError('Use a fresh output directory so old/private artifacts cannot enter a release')
    output.mkdir(parents=True)
    public = output/'standard'/'weekly-highlight-workflow'
    public.mkdir(parents=True)
    files = [ROOT/p for p in PUBLIC_FILES]
    for folder, pattern in PUBLIC_GROUPS:
        files.extend(sorted((ROOT/folder).glob(pattern)))
    for source in files:
        destination = public/source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    checksums(public)
    archive(public, output/'weekly-highlight-workflow-1.01.zip')
    workbuddy = output/'workbuddy'/'weekly-highlight-workflow'
    shutil.copytree(public, workbuddy)
    skill = workbuddy/'SKILL.md'
    text = skill.read_text(encoding='utf-8')
    # WorkBuddy's import metadata extends the standard skill; the maintained core is identical.
    extra = ('version: "1.01"\nauthor: "Weekly Highlights contributors"\n'
             'display_name: "Weekly Highlights"\n'
             'description_zh: "ACP、ACP相关预印本与PNAS文献筛选、去重和周报更新"\n'
             'description_en: "Screen ACP and PNAS papers, deduplicate and update weekly reports"\n')
    skill.write_text(text.replace('---\n', '---\n'+extra, 1), encoding='utf-8')
    checksums(workbuddy)
    archive(workbuddy, output/'weekly-highlight-workflow-1.01-workbuddy.zip')
    print('CLEAN_RELEASE_BUILT: ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    build(parser.parse_args().output_dir)
