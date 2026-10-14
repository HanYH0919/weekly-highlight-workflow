"""User-selected journals and research scope; no built-in journal or subject defaults."""
import re
from urllib.parse import urlparse
from weekly_common import digest, within


def web_url(value):
    parsed = urlparse(str(value))
    return parsed.scheme in ('https', 'http') and bool(parsed.netloc)


def validate_selection(config):
    journals = config.get('journals', {})
    profiles = config.get('journal_profiles', {})
    if not isinstance(journals, dict) or not journals:
        raise ValueError('SELECTION_REQUIRED: select at least one journal; no journals are selected by default')
    if set(profiles) != set(journals):
        raise ValueError('SELECTION_REQUIRED: each selected journal needs its own name and verified official sources')
    paths = []
    for key, relative in journals.items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', key):
            raise ValueError('Journal IDs must use 1-64 letters, digits, hyphens or underscores; store full names in journal_profiles')
        path = within(config['workspace_root'], relative)
        if path.suffix.lower() != '.docx':
            raise ValueError('Each journal history must be a Word .docx file')
        paths.append(str(path).casefold())
        profile = profiles[key]
        if not str(profile.get('name', '')).strip() or profile.get('source_verified') is not True:
            raise ValueError('Verify journal identity and official source before setup')
        urls = profile.get('source_urls', [])
        if not isinstance(urls, list) or not urls or not all(web_url(url) for url in urls):
            raise ValueError('Each journal needs verified official homepage/feed/search URLs')
        if type(profile.get('include_preprints', False)) is not bool:
            raise ValueError('include_preprints must be a boolean')
        if profile.get('include_preprints') and not profile.get('preprint_source_urls'):
            raise ValueError('Preprints require explicit selected source URLs')
        if not all(web_url(url) for url in profile.get('preprint_source_urls', [])):
            raise ValueError('Invalid preprint source URL')
    if len(set(paths)) != len(paths):
        raise ValueError('Each journal must have a distinct history path')
    scope = config.get('research_scope', {})
    mode = scope.get('mode')
    if mode not in ('topics', 'journal-informed', 'all'):
        raise ValueError('SELECTION_REQUIRED: choose topics, journal-informed scope or explicitly all journal topics')
    for key in ('topics', 'exclude'):
        if not isinstance(scope.get(key, []), list) or not all(isinstance(s, str) and s.strip() for s in scope.get(key, [])):
            raise ValueError('Scope topics/exclude must be lists of nonempty strings')
    if not str(scope.get('criteria', '')).strip():
        raise ValueError('Write the user-selected screening criteria')
    if mode == 'topics' and not scope.get('topics'):
        raise ValueError('Topic mode requires the user research topics')
    if mode == 'journal-informed':
        evidence = scope.get('evidence_urls', [])
        if not isinstance(evidence, list) or not evidence or not all(web_url(url) for url in evidence):
            raise ValueError('Read official aims/scope or recent articles and record evidence before inferring scope')
    return config


def selection_hash(config):
    validate_selection(config)
    return digest({key:config[key] for key in ('journals','journal_profiles','research_scope')})


def assert_selection(data, config):
    if data.get('selection_sha256') != selection_hash(config):
        raise ValueError('SELECTION_CHANGED: regenerate the review and obtain approval for the current journal/topic selection')
    if set(data.get('history', {})) != set(config['journals']):
        raise ValueError('Review history does not match selected journals')
