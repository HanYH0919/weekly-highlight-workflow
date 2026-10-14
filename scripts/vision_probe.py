"""Actual image delivery and layout smoke test; no provider API keys required."""
import argparse
import json
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from weekly_common import digest, dump_json, file_hash, load_config, load_json


def identity(config):
    e = config['execution']
    return {'host': e['host'], 'host_version': e.get('host_version', 'unknown'),
            'provider': e['provider'], 'model': e['review_model']}


def seal(record):
    record['integrity'] = digest({k: v for k, v in record.items() if k != 'integrity'})
    return record


def checked(record):
    if record.get('integrity') != digest({k: v for k, v in record.items() if k != 'integrity'}):
        raise ValueError('Capability record changed; run a fresh test')
    return record


def font(size):
    for name in ['DejaVuSans.ttf', 'Arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf', 'C:/Windows/Fonts/arial.ttf']:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    raise RuntimeError('A normal text font is required to generate a readable vision test')


def make(config, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a new challenge directory; never reuse answers for a changed model')
    output.mkdir(parents=True)
    nonce = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
    exponent = secrets.choice([3, 4, 6, 8])
    colors = random.SystemRandom().sample(['red', 'blue', 'green'], 3)
    image = Image.new('RGB', (1000, 700), 'white'); draw = ImageDraw.Draw(image)
    draw.text((45, 30), 'Image input check', fill='black', font=font(35))
    draw.text((45, 110), 'Verification code:', fill='black', font=font(30))
    draw.text((420, 100), nonce, fill='black', font=font(52))
    for i, color in enumerate(colors):
        x = 90 + 300 * i
        draw.ellipse((x, 240, x + 100, 340), fill=color)
    draw.text((45, 410), 'Read the exponent in this expression:', fill='black', font=font(28))
    draw.text((120, 485), 'N = 10', fill='black', font=font(46))
    draw.text((280, 468), str(exponent), fill='black', font=font(25))
    image.save(output / 'input-check.png')
    board = Image.new('RGB', (1120, 1100), 'white'); b = ImageDraw.Draw(board)
    b.text((35, 20), 'Inspect panels A-D for overlap or clipping', fill='black', font=font(30))
    conditions = random.SystemRandom().sample(['clean', 'clean', 'overlap', 'clipped'], 4)
    for index, (label, condition) in enumerate(zip('ABCD', conditions)):
        x, y = 30 + (index % 2) * 550, 90 + (index // 2) * 500
        b.rectangle((x, y, x + 520, y + 450), outline='black', width=2)
        b.text((x + 18, y + 15), label, fill='black', font=font(34))
        panel = Image.new('RGB', (480, 340), '#f8f8f8'); d = ImageDraw.Draw(panel)
        d.text((15, 20), 'Weekly Highlights', fill='black', font=font(27))
        if condition == 'clipped':
            d.text((15, 110), 'Particle concentration measurement', fill='black', font=font(38))
            d.text((15, 320), 'Abstract: aerosol formation', fill='black', font=font(31))
        elif condition == 'overlap':
            d.text((15, 110), 'Summary: particle growth', fill='black', font=font(30))
            d.text((15, 119), 'Abstract: aerosol chemistry', fill='black', font=font(30))
        else:
            d.text((15, 105), 'Summary: particle growth', fill='black', font=font(28))
            d.text((15, 165), 'Abstract: aerosol chemistry', fill='black', font=font(28))
        board.paste(panel, (x + 20, y + 90))
    board.save(output / 'layout-check.png')
    inputs = [{'path': str(output / name), 'sha256': file_hash(output / name)} for name in ['input-check.png', 'layout-check.png']]
    public = {'probe_id': secrets.token_hex(12), 'identity': identity(config), 'inputs': inputs,
              'task': 'Open BOTH PNG images as actual image inputs. Do not read other files, use OCR, inspect pixels with code or use the private answer record. Return JSON: verification_code, leftmost_color, exponent (integer), panels {A: clean|overlap|clipped, B:..., C:..., D:...}. Report actual_model and delivery.image_input_confirmed plus image tool-call IDs/evidence. If image input is unavailable, report unavailable rather than guess.'}
    dump_json(output / 'challenge.json', seal(public))
    dump_json(output / 'answer.private.json', {'probe_id': public['probe_id'], 'verification_code': nonce,
                                              'leftmost_color': colors[0], 'exponent': exponent, 'panels': dict(zip('ABCD', conditions))})
    (output / 'PROMPT.txt').write_text(public['task'] + '\nRequested model: ' + public['identity']['model'] + '\nImages:\n' + '\n'.join(i['path'] for i in inputs), encoding='utf-8')
    return public


def grade(challenge_path, response_path, output):
    challenge_path = Path(challenge_path).resolve()
    challenge = checked(load_json(challenge_path))
    answer = load_json(challenge_path.parent / 'answer.private.json')
    response = load_json(response_path)
    for image in challenge['inputs']:
        if file_hash(image['path']) != image['sha256']:
            raise ValueError('Challenge image changed')
    delivery = response.get('delivery', {})
    actual = response.get('actual_model')
    evidence = delivery.get('image_tool_evidence')
    transported = delivery.get('image_input_confirmed') is True and isinstance(evidence, list) and len(evidence) >= 2
    score = {k: response.get(k) == answer[k] for k in ('verification_code', 'leftmost_color', 'exponent', 'panels')}
    passed = transported and actual == challenge['identity']['model'] and all(score.values())
    receipt = seal({'kind': 'vision-capability', 'status': 'passed' if passed else 'failed_or_unverified',
                    'probe_id': challenge['probe_id'], 'identity': challenge['identity'], 'actual_model': actual,
                    'image_input_confirmed': transported, 'checks': score, 'image_tool_evidence': evidence,
                    'inputs': challenge['inputs'], 'tested_at': datetime.now(timezone.utc).isoformat(),
                    'scope': 'Basic image delivery, notation and obvious layout defects; not a guarantee for all scientific pages',
                    'attestation': 'Recorded host-tool evidence, not a cryptographic attestation of provider internals'})
    dump_json(output, receipt)
    return receipt


def validate_receipt(path):
    receipt = checked(load_json(path))
    if receipt.get('kind') != 'vision-capability' or receipt.get('status') != 'passed' or not receipt.get('image_input_confirmed'):
        raise ValueError('No passing actual image test; configure a tested visual reviewer')
    if receipt.get('actual_model') != receipt.get('identity', {}).get('model') or set(receipt.get('checks', {})) != {'verification_code', 'leftmost_color', 'exponent', 'panels'} or not all(value is True for value in receipt['checks'].values()):
        raise ValueError('Model identity or visual checks do not match')
    for item in receipt['inputs']:
        if file_hash(item['path']) != item['sha256']:
            raise ValueError('Capability evidence images unavailable or changed')
    return receipt


def verify_capability(config):
    receipt = validate_receipt(config['setup']['capability_receipt'])
    if receipt['identity'] != identity(config):
        raise ValueError('Review model/provider/client changed; repeat the visual test')
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    m = sub.add_parser('make'); m.add_argument('--config', type=Path, required=True); m.add_argument('--output-dir', type=Path, required=True)
    g = sub.add_parser('grade'); g.add_argument('--challenge', type=Path, required=True); g.add_argument('--response', type=Path, required=True); g.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = make(load_config(args.config, require_ready=False), args.output_dir) if args.command == 'make' else grade(args.challenge, args.response, args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in ['task','inputs']}, ensure_ascii=False))
    if args.command == 'grade' and result['status'] != 'passed':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
