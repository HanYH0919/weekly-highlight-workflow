"""Insert verified records, preserving template paragraphs and old XML."""
import argparse
import re
import uuid
import os
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from weekly_common import DATE_RE, expected_records, normalize_doi


def new_library_templates(doc):
    """Make transient prototypes, never fake a historical article in a saved document."""
    scratch = Document()
    day = scratch.add_paragraph('')
    title = scratch.add_paragraph(); title.add_run('').bold = True
    num_pr = OxmlElement('w:numPr')
    level = OxmlElement('w:ilvl'); level.set(qn('w:val'), '0')
    num_id = OxmlElement('w:numId'); num_id.set(qn('w:val'), '5')
    num_pr.append(level); num_pr.append(num_id); title._p.get_or_add_pPr().append(num_pr)
    authors = scratch.add_paragraph(); authors.add_run('')
    doi = scratch.add_paragraph(); doi.add_run('')
    summary = scratch.add_paragraph(); summary.add_run('Summary').bold = True; summary.add_run('：')
    abstract = scratch.add_paragraph(); abstract.add_run('Abstract').bold = True; abstract.add_run(': ')
    # These prototypes use the default python-docx list definition. Copy it if absent.
    dest = doc.part.numbering_part.element
    if not any(n.get(qn('w:numId')) == '5' for n in dest.findall(qn('w:num'))):
        raise ValueError('Blank library has unexpected numbering; use the setup-generated starter')
    return day, title, authors, doi, summary, abstract


def clone_before(template, anchor, parts):
    element = deepcopy(template._p)
    anchor._p.addprevious(element)
    paragraph = Paragraph(element, anchor._parent)
    prototypes = [deepcopy(r._r.rPr) for r in paragraph.runs]
    # Templates may contain split formula/font runs. Preserve paragraph and per-label style,
    # not the old run count or the old article's scientific fragments.
    for child in list(element):
        if child.tag != qn('w:pPr'):
            element.remove(child)
    for index, text in enumerate(parts):
        for piece in filter(None, re.split(r'([\u2070-\u209f∼]+)', text)):
            run = paragraph.add_run(piece)
            if prototypes:
                properties = prototypes[min(index, len(prototypes) - 1)]
                if properties is not None:
                    run._r.insert(0, deepcopy(properties))
            if re.fullmatch(r'[\u2070-\u209f∼]+', piece):
                fonts = run._r.get_or_add_rPr().find(qn('w:rFonts'))
                if fonts is None:
                    fonts = OxmlElement('w:rFonts')
                    run._r.rPr.append(fonts)
                symbol_font = 'Segoe UI Symbol' if os.name == 'nt' else 'DejaVu Sans'
                fonts.set(qn('w:ascii'), symbol_font)
                fonts.set(qn('w:hAnsi'), symbol_font)
    return paragraph


def independent_numbering(doc, title):
    ppr = title._p.pPr
    if ppr is None or ppr.numPr is None or ppr.numPr.numId is None:
        raise ValueError('Template has no explicit article numbering; inspect before changing layout')
    numbering = doc.part.numbering_part.element
    nums = numbering.findall(qn('w:num'))
    old = next(n for n in nums if int(n.get(qn('w:numId'))) == ppr.numPr.numId.val)
    new_id = max(int(n.get(qn('w:numId'))) for n in nums) + 1
    abstracts = numbering.findall(qn('w:abstractNum'))
    old_abstract_id = old.find(qn('w:abstractNumId')).get(qn('w:val'))
    old_abstract = next(n for n in abstracts if n.get(qn('w:abstractNumId')) == old_abstract_id)
    abstract_id = max(int(n.get(qn('w:abstractNumId'))) for n in abstracts) + 1
    new_abstract = deepcopy(old_abstract)
    new_abstract.set(qn('w:abstractNumId'), str(abstract_id))
    for name in ('nsid', 'tmpl'):
        node = new_abstract.find(qn('w:' + name))
        if node is not None:
            node.set(qn('w:val'), uuid.uuid4().hex[:8].upper())
    nums[0].addprevious(new_abstract)
    new = deepcopy(old)
    new.set(qn('w:numId'), str(new_id))
    new.find(qn('w:abstractNumId')).set(qn('w:val'), str(abstract_id))
    # A new concrete numbering instance with an explicit start override starts at 1.
    for override in new.findall(qn('w:lvlOverride')):
        new.remove(override)
    override = OxmlElement('w:lvlOverride')
    override.set(qn('w:ilvl'), str(ppr.numPr.ilvl.val if ppr.numPr.ilvl is not None else 0))
    start = OxmlElement('w:startOverride')
    start.set(qn('w:val'), '1')
    override.append(start)
    new.append(override)
    numbering.append(new)
    return new_id


def build(source, records, day, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists():
        raise FileExistsError('Source must remain unchanged; choose a new candidate path')
    if not DATE_RE.fullmatch(day):
        raise ValueError('Date must be YYYY.M.D')
    doc = Document(str(source))
    paragraphs = doc.paragraphs
    if any(p.text.strip() == day for p in paragraphs):
        raise ValueError('Date section already exists; do not silently duplicate it')
    i = next((i for i, p in enumerate(paragraphs) if DATE_RE.fullmatch(p.text.strip())), None)
    empty_library = i is None and len(paragraphs) == 1 and not doc.tables
    if empty_library:
        prototypes = new_library_templates(doc)
        anchor = doc.add_paragraph('')
        date_template, title, authors, doi, summary, abstract = prototypes
    elif i is None or i + 5 >= len(paragraphs):
        raise ValueError('No usable date and five-paragraph article template')
    else:
        anchor, title, authors, doi, summary, abstract = paragraphs[i:i + 6]
        date_template = anchor
    if not empty_library and (not normalize_doi(doi.text) or not summary.text.startswith('Summary') or not abstract.text.startswith('Abstract')):
        raise ValueError('Template is not the expected five-paragraph format')
    num = independent_numbering(doc, title)
    new_date = clone_before(date_template, anchor, [day])
    new_date.paragraph_format.keep_with_next = True
    for record in records:
        title_p = clone_before(title, anchor, [record['title']])
        title_p._p.pPr.numPr.numId.val = num
        title_p.paragraph_format.keep_together = True
        title_p.paragraph_format.keep_with_next = True
        clone_before(authors, anchor, [record['authors']])
        clone_before(doi, anchor, ['https://doi.org/' + record['doi']])
        clone_before(summary, anchor, ['Summary', '：' + record['summary']])
        clone_before(abstract, anchor, ['Abstract', ': ' + record['abstract']])
    if empty_library:
        anchor._p.getparent().remove(anchor._p)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'metadata', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--date', required=True)
    args = p.parse_args()
    rows = expected_records(args.metadata)
    build(args.source, rows, args.date, args.output)
    print(f'CANDIDATE_READY articles={len(rows)} path={args.output}')

if __name__ == '__main__':
    main()
