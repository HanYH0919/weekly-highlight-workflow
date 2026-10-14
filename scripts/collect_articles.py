"""Parse official saved indexes or fetch explicit URLs. Does not judge relevance."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from lxml import etree, html
from http_cache import fetch
from weekly_common import DOI_RE, dump_json, normalize_doi, plain_text


def parse_feed(blob, source_url):
    root = etree.fromstring(blob, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    rows = []
    for item in root.xpath('//*[local-name()="item" or local-name()="entry"]'):
        field = lambda name: item.xpath(f'./*[local-name()="{name}"]')
        text = lambda name: ''.join(field(name)[0].itertext()).strip() if field(name) else ''
        link = text('link') or (field('link')[0].get('href', '') if field('link') else '')
        doi = normalize_doi(text('doi') or link or text('identifier'))
        rows.append({'doi': doi, 'title': plain_text(text('title')), 'landing_url': link,
                     'date_candidate': text('date') or text('published') or text('pubDate'),
                     'abstract_candidate': plain_text(text('description') or text('summary')),
                     'index_source_url': source_url, 'date_verified': False, 'abstract_verified': False})
    return rows


def parse_acp_index(blob, source_url):
    tree = html.fromstring(blob)
    rows, seen = [], set()
    # Bind DOI, title and href to one article-sized block, never scan adjacent records.
    for anchor in tree.xpath('//a[@href]'):
        href = urljoin(source_url, anchor.get('href'))
        title = plain_text(' '.join(anchor.itertext()))
        if not (re.search(r'/articles/\d+/\d+/\d{4}/?$', href) or re.search(r'/preprints/\d{4}/egusphere-[^/]+/?$', href)) or len(title) < 25:
            continue
        node = anchor
        chosen = None
        for _ in range(6):
            if node is None:
                break
            links = {urljoin(source_url, x) for x in node.xpath('.//a/@href') if '/articles/' in x or '/preprints/' in x}
            dois = {normalize_doi(m.group()) for m in DOI_RE.finditer(' '.join(node.itertext()))}
            if len(links) <= 2 and len(dois) == 1:
                chosen = (node, next(iter(dois)))
                break
            node = node.getparent()
        if chosen is None:
            # Retain unbound record for explicit verification rather than inventing a DOI.
            chosen = (anchor, '')
        node, doi = chosen
        key = doi or href
        if key in seen:
            continue
        seen.add(key)
        rows.append({'title': title, 'doi': doi, 'landing_url': href,
                     'index_source_url': source_url, 'index_context': plain_text(' '.join(node.itertext())),
                     'date_verified': False, 'abstract_verified': False})
    if not rows:
        raise ValueError('No ACP article blocks found; inspect source instead of assuming no articles')
    return rows


def parse_article(blob, source_url):
    tree = html.fromstring(blob)
    meta = {}
    for node in tree.xpath('//meta[@content]'):
        key = (node.get('name') or node.get('property') or '').lower()
        meta.setdefault(key, []).append(node.get('content'))
    first = lambda *keys: next((meta[k][0] for k in keys if meta.get(k)), '')
    nodes = tree.xpath('//*[@id="abstract"]')
    raw = first('citation_abstract')
    if not raw and nodes:
        node = nodes[0]
        # Some publishers use the id on a heading rather than the abstract section.
        if node.tag in ('h1', 'h2', 'h3'):
            node = node.getnext()
        if node is not None:
            raw = etree.tostring(node, encoding='unicode', method='html')
    result = {'doi': normalize_doi(first('citation_doi', 'dc.identifier') or source_url),
              'title': plain_text(first('citation_title', 'dc.title', 'og:title')),
              'authors': meta.get('citation_author', []),
              'publication_date_candidate': first('citation_online_date', 'citation_publication_date', 'citation_date'),
              'abstract_html': raw, 'abstract': plain_text(raw),
              'pdf_url': urljoin(source_url, first('citation_pdf_url')) if first('citation_pdf_url') else '',
              'landing_url': source_url, 'date_verified': False, 'abstract_verified': False}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['feed', 'acp-index', 'article'])
    p.add_argument('--url', action='append', default=[], help='Explicit verified URL; repeat for known pages of one source')
    p.add_argument('--file', type=Path)
    p.add_argument('--source-url')
    p.add_argument('--cache-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--refresh', action='store_true')
    args = p.parse_args()
    sources = []
    if args.file:
        if not args.source_url:
            p.error('--file requires --source-url')
        sources.append((args.file.read_bytes(), {'final_url': args.source_url, 'saved_file': str(args.file)}))
    for url in args.url:
        sources.append(fetch(url, args.cache_dir, refresh=args.refresh))
    if not sources:
        p.error('Provide --url or --file')
    parser = {'feed': parse_feed, 'acp-index': parse_acp_index, 'article': parse_article}[args.mode]
    rows, provenance = [], []
    for blob, info in sources:
        result = parser(blob, info['final_url'])
        rows.extend(result if isinstance(result, list) else [result])
        provenance.append(info)
    dump_json(args.output, {'mode': args.mode, 'sources': provenance, 'records': rows,
                            'coverage_complete': False, 'note': 'Agent must verify pagination, dates, full abstracts and source semantics'})
    print(json.dumps({'records': len(rows), 'output': str(args.output)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
