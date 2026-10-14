"""Offline synthetic journal/topic regression tests; no real model capability claims."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from weekly_common import load_json,dump_json,load_config
from selection import validate_selection,selection_hash
from setup_share import selection_config,prepare_histories
from vision_probe import make,grade
from collect_articles import parse_index,parse_feed


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('WEEKLY_HIGHLIGHTS_TEST_TMP'))
        self.base=Path(self.temp.name)
        self.config=load_json(ROOT/'config.example.json')
        self.config['workspace_root']=str(self.base)
        self.config['execution'].update(host='synthetic-test',host_version='test',provider='test',preferred_model='synthetic-model',review_model='synthetic-model')
        self.config['journals']={j:f'{j}/{j}.docx' for j in ['J1','J2','J3']}
        self.config['journal_profiles']={j:{'name':'Synthetic Journal '+j,'source_urls':['https://example.org/'+j],'source_verified':True,'include_preprints':False} for j in self.config['journals']}
        self.config['research_scope']={'mode':'topics','topics':['synthetic research question'],'exclude':['synthetic exclusion'],'criteria':'Synthetic selection only; not real research','evidence_urls':[]}
        prepare_histories(self.config,True)
        # Deliberately generated synthetic answers test gates, NOT a real visual model.
        make(self.config,self.base/'probe')
        answer=load_json(self.base/'probe/answer.private.json')
        answer.update(actual_model='synthetic-model',delivery={'image_input_confirmed':True,'image_tool_evidence':['SYNTHETIC-one','SYNTHETIC-two']})
        dump_json(self.base/'response.json',answer)
        grade(self.base/'probe/challenge.json',self.base/'response.json',self.base/'receipt.json')
        self.config['setup'].update(status='ready',capability_receipt=str(self.base/'receipt.json'))
        self.path=self.base/'config.json'
        self.save()

    def tearDown(self):self.temp.cleanup()
    def save(self):dump_json(self.path,self.config,overwrite=True)

    def cli(self,script,*args,ok=True):
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),*map(str,args)],capture_output=True,text=True,encoding='utf-8',cwd=self.base)
        if ok:self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        else:self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        return result

    def records(self):
        rows=[]
        for i,j in enumerate(self.config['journals']):
            rows.append({'journal':j,'type':'正式发表','doi':f'10.9999/synthetic-{i}', 'title':['Alpha synthetic study','Beta evaluation report','Gamma methods investigation'][i],
                         'publication_date':'2026-10-14','date_verified':True,'date_source_url':'https://example.org/date',
                         'abstract':'SYNTHETIC TEST ONLY. This abstract is generated solely to exercise software paths and contains no scientific findings or claims.',
                         'abstract_verified':True,'abstract_source_url':'https://example.org/abstract','landing_url':'https://example.org/article',
                         'screening':{'decision':'include','question':'synthetic question','contribution':'synthetic contribution','relevance':'synthetic selected topic'},
                         'summary':'纯软件合成测试，并非真实研究。','authors':['Example, Test'],'authors_verified':True,'authors_source_url':'https://example.org/authors'})
        return {'window':['2026-10-05','2026-10-14'],'discovery':{j:{'source':'https://example.org/'+j,'checked':1,'coverage_complete':True,'stop_reason':'synthetic window covered'} for j in self.config['journals']},'articles':rows}

    def review(self,source=None,name='review'):
        source=source or self.records(); input_path=self.base/(name+'-input.json');dump_json(input_path,source)
        out=self.base/name
        self.cli('weekly.py','--config',self.path,'prepare-review','--today','2026-10-14','--records',input_path,'--out-dir',out)
        return out

    def test_no_default_journals_or_topics(self):
        empty=load_json(ROOT/'config.example.json');empty['workspace_root']=str(self.base)
        self.assertEqual(empty['journals'],{});self.assertEqual(empty['research_scope']['topics'],[])
        with self.assertRaises(ValueError):validate_selection(empty)

    def test_three_arbitrary_journals_preflight_and_numbering(self):
        result=self.cli('weekly.py','--config',self.path,'preflight','--today','2026-10-14')
        self.assertEqual(set(json.loads(result.stdout)['history']),{'J1','J2','J3'})
        out=self.review();text=(out/'review-list.txt').read_text(encoding='utf-8')
        self.assertEqual(text.count('```text'),3);self.assertEqual(text.count('1. Title'),3)
        self.assertIn(self.config['research_scope']['criteria'],text)

    def test_single_journal_is_supported(self):
        for key in ['journals','journal_profiles']:self.config[key]={'J2':self.config[key]['J2']}
        self.save();out=self.review()
        self.assertEqual((out/'review-list.txt').read_text(encoding='utf-8').count('```text'),1)

    def test_cross_journal_doi_duplicate_removed_before_copy_list(self):
        data=self.records();data['articles'][1]=dict(data['articles'][0],journal='J2')
        out=self.review(data);review=load_json(out/'review.json')
        self.assertEqual(review['counts']['within_duplicates'],1)
        self.assertEqual((out/'review-list.txt').read_text(encoding='utf-8').count('https://doi.org/10.9999/synthetic-0'),1)

    def test_unknown_or_missing_journal_blocks_formal_list(self):
        for mode in ['unknown','missing']:
            data=self.records()
            if mode=='unknown':data['articles'][0]['journal']='NOT_SELECTED'
            else:data['discovery'].pop('J3')
            p=self.base/(mode+'.json');dump_json(p,data);out=self.base/mode
            self.cli('weekly.py','--config',self.path,'prepare-review','--today','2026-10-14','--records',p,'--out-dir',out,ok=False)
            self.assertFalse((out/'review-list.txt').exists())

    def test_preprints_not_implicitly_added(self):
        data=self.records();data['articles'][0]['type']='预印本'
        p=self.base/'preprint.json';dump_json(p,data)
        self.cli('weekly.py','--config',self.path,'prepare-review','--today','2026-10-14','--records',p,'--out-dir',self.base/'blocked',ok=False)
        self.assertFalse((self.base/'blocked/review-list.txt').exists())

    def test_scope_change_blocks_approval_and_execution(self):
        out=self.review();approved=self.base/'approved.json'
        self.cli('weekly.py','--config',self.path,'approve','--review',out/'review.json','--confirmation','SYNTHETIC TEST AUTHORIZATION','--output',approved)
        self.config['research_scope']['criteria']='Changed synthetic question';self.save()
        r=self.cli('weekly.py','--config',self.path,'approve','--review',out/'review.json','--confirmation','SYNTHETIC','--output',self.base/'invalid.json',ok=False)
        self.assertIn('SELECTION_CHANGED',r.stderr)
        self.cli('weekly.py','--config',self.path,'metadata','--approved',approved,'--journal','J1','--output',self.base/'metadata.json',ok=False)
        self.cli('download_pdfs.py','--config',self.path,'--approved',approved,'--journal','J1','--base-dir',self.base/'J1/261014',ok=False)
        self.assertFalse((self.base/'J1/261014').exists())

    def test_journal_informed_scope_needs_reading_evidence(self):
        self.config['research_scope'].update(mode='journal-informed',topics=[])
        with self.assertRaises(ValueError):validate_selection(self.config)
        self.config['research_scope']['evidence_urls']=['https://example.org/aims-scope']
        validate_selection(self.config)
        self.config['research_scope']['mode']='all';self.config['research_scope']['evidence_urls']=[]
        validate_selection(self.config)

    def test_duplicate_history_path_rejected(self):
        self.config['journals']['J2']=self.config['journals']['J1']
        with self.assertRaises(ValueError):validate_selection(self.config)

    def test_new_library_does_not_replace_existing(self):
        path=self.base/self.config['journals']['J1'];before=path.read_bytes()
        with self.assertRaises(FileExistsError):prepare_histories(self.config,True)
        self.assertEqual(path.read_bytes(),before)

    def test_legacy_config_requires_explicit_selection_and_scope_preserves_history(self):
        before={p:p.read_bytes() for p in (self.base/j for j in self.config['journals'].values())}
        selected={k:self.config[k] for k in ['journals','journal_profiles','research_scope']};p=self.base/'selection.json';dump_json(p,selected)
        self.config.pop('journal_profiles');self.config.pop('research_scope');self.config['version']='1.01';self.save()
        legacy_profile=self.base/'.weekly-highlights/screening-profile.md'
        legacy_profile.parent.mkdir(parents=True,exist_ok=True)
        legacy_profile.write_text('SYNTHETIC legacy narrow topic. Must not be inherited.',encoding='utf-8')
        self.cli('weekly.py','--config',self.path,'preflight',ok=False)
        self.cli('setup_share.py','scope','--config',self.path,'--selection',p)
        after=load_json(self.path)
        self.assertEqual(after['version'],'1.11');self.assertEqual(after['execution'],self.config['execution'])
        self.assertEqual(after['setup'],self.config['setup']);self.assertTrue(list(self.base.glob('config.backup-*.json')))
        backups=list(legacy_profile.parent.glob('screening-profile.pre-1.11-*.md'))
        self.assertEqual(len(backups),1)
        self.assertIn('SYNTHETIC legacy narrow topic',backups[0].read_text(encoding='utf-8'))
        self.assertEqual(legacy_profile.read_bytes(),(ROOT/'references/screening-profile.md').read_bytes())
        for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
        self.cli('weekly.py','--config',self.path,'preflight')

    def test_generic_index_binds_each_journal_article_block(self):
        blob=b'<main><article><a href="/one">First study</a><p>10.9999/one</p></article><article><a href="/two">Second study</a><p>10.9999/two</p></article></main>'
        rows=parse_index(blob,'https://example.org/journal','//article')
        self.assertEqual([r['doi'] for r in rows],['10.9999/one','10.9999/two'])
        self.assertFalse(any(r['abstract_verified'] for r in rows))
        with self.assertRaises(ValueError):parse_index(blob,'https://example.org/journal',None)

    def test_atom_feed_stays_unverified(self):
        rows=parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Example</title><link href="https://doi.org/10.9999/atom"/><published>2026-10-14</published></entry></feed>','https://example.org/feed')
        self.assertEqual(rows[0]['doi'],'10.9999/atom');self.assertFalse(rows[0]['date_verified'])


if __name__=='__main__':unittest.main()
