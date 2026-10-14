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


def parse_index(blob, source_url, article_xpath, title_xpath='.//a[@href]', link_xpath='.//a[@href]/@href'):
    if not article_xpath:
        raise ValueError('Inspect the publisher index and supply --article-xpath; no journal-specific parser is assumed')
    tree=html.fromstring(blob)
    rows=[]
    for block in tree.xpath(article_xpath):
        if not isinstance(block,etree._Element):
            raise ValueError('article-xpath must select article container elements')
        titles=block.xpath(title_xpath);links=block.xpath(link_xpath)
        if not titles or not links:
            raise ValueError('Selected article block has no title/link; correct the selectors or use browser verification')
        title=titles[0]
        title=plain_text(' '.join(title.itertext()) if isinstance(title,etree._Element) else str(title))
        link=links[0]
        link=link.get('href','') if isinstance(link,etree._Element) else str(link)
        context=plain_text(' '.join(block.itertext()))
        dois={normalize_doi(m.group()) for m in DOI_RE.finditer(context)}
        rows.append({'title':title,'doi':next(iter(dois)) if len(dois)==1 else '',
                     'landing_url':urljoin(source_url,link),'index_source_url':source_url,
                     'index_context':context,'date_verified':False,'abstract_verified':False})
    if not rows:
        raise ValueError('No selected article blocks; do not treat a failed parser as zero articles')
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
    p.add_argument('mode', choices=['feed', 'index', 'article'])
    p.add_argument('--url', action='append', default=[], help='Explicit verified URL; repeat for known pages of one source')
    p.add_argument('--file', type=Path)
    p.add_argument('--source-url')
    p.add_argument('--cache-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--journal',help='Journal ID from selected local configuration')
    p.add_argument('--article-xpath')
    p.add_argument('--title-xpath',default='.//a[@href]')
    p.add_argument('--link-xpath',default='.//a[@href]/@href')
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
    parser = {'feed': parse_feed, 'index': lambda blob,url: parse_index(blob,url,args.article_xpath,args.title_xpath,args.link_xpath), 'article': parse_article}[args.mode]
    rows, provenance = [], []
    for blob, info in sources:
        result = parser(blob, info['final_url'])
        rows.extend(result if isinstance(result, list) else [result])
        provenance.append(info)
    if args.journal:
        for record in rows:
            record['journal']=args.journal
    dump_json(args.output, {'mode': args.mode, 'sources': provenance, 'records': rows,
                            'coverage_complete': False, 'note': 'Agent must verify pagination, dates, full abstracts and source semantics'})
    print(json.dumps({'records': len(rows), 'output': str(args.output)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
