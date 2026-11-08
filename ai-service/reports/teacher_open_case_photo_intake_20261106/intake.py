"""304: bounded licensed PMC clinical-figure candidate intake, no model training."""
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
from collections import Counter,defaultdict
from urllib.parse import urlparse,parse_qs,urlencode,quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from xml.etree import ElementTree as ET
import hashlib,io,json,re,time
import numpy as np
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=OUT.parent
STORE=ROOT/'SkinDisease/sources/pmc_case_photos_20261106'
BASE='https://pmc-oa-opendata.s3.amazonaws.com/'
XLINK='{http://www.w3.org/1999/xlink}href'
ALLOWED_LICENSES={'CC BY','CC BY-SA','CC BY-NC','CC BY-NC-SA','CC0'}
LABEL_PATTERNS={
 'Lupus':r'\b(?:discoid lupus|cutaneous lupus|lupus erythematosus tumidus)\b',
 'Psoriasis':r'\b(?:plaque psoriasis|psoriasis vulgaris|psoriasis)\b',
 'Tinea':r'\btinea (?:corporis|cruris|faciei|incognito)\b',
}
CAPTION_PATTERNS={**LABEL_PATTERNS,'Lupus':r'\b(?:discoid lupus|cutaneous lupus|lupus erythematosus|DLE|SCLE|CLE)\b'}
QUERIES={
 'Lupus':'("discoid lupus"[Title] OR "cutaneous lupus"[Title]) AND ("case report"[Title] OR "case reports"[Publication Type])',
 'Psoriasis':'("plaque psoriasis"[Title] OR "psoriasis vulgaris"[Title]) AND ("case report"[Title] OR "case reports"[Publication Type])',
 'Tinea':'("tinea corporis"[Title] OR "tinea cruris"[Title] OR "tinea faciei"[Title] OR "tinea incognito"[Title]) AND ("case report"[Title] OR "case reports"[Publication Type])',
}
POLICY_URLS={
 'DDI':'https://ddi-dataset.github.io/',
 'DDI2':'https://daneshjoulab.github.io/ddi2-dataset/',
 'eSkinHealth':'https://raw.githubusercontent.com/janet-sw/eSkinHealth/main/README.md',
 'PMC_developers':'https://pmc.ncbi.nlm.nih.gov/tools/developers/',
 'PMC_cloud':'https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/',
 'PMC_cloud_readme':BASE+'README.txt',
}
utc=lambda:datetime.now(timezone.utc).isoformat()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def lines(p,v):Path(p).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in v),encoding='utf-8')

def https_object(url):
    p=urlparse(url)
    if p.scheme=='s3' and p.netloc=='pmc-oa-opendata':url=BASE+p.path.lstrip('/')+('?' +p.query if p.query else '');p=urlparse(url)
    if p.scheme!='https' or p.netloc!='pmc-oa-opendata.s3.amazonaws.com' or '..' in p.path.split('/'):raise ValueError('Untrusted article object URL')
    return url

def request(url,limit=20_000_000):
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={'User-Agent':'DermAI-Clinic-research/1.0'}),timeout=25) as response:
                data=response.read(limit+1)
                if len(data)>limit:raise ValueError('Object exceeds bounded intake limit')
                return data,dict(response.headers)
        except (HTTPError,URLError,TimeoutError,OSError):
            if attempt:raise
            time.sleep(.7)

def fetch_object(url,dest,limit=20_000_000):
    url=https_object(url);data,headers=request(url,limit)
    md5=parse_qs(urlparse(url).query).get('md5',[None])[0]
    if md5 and hashlib.md5(data).hexdigest()!=md5:raise ValueError('Publisher-supplied object MD5 mismatch')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():assert dest.read_bytes()==data,'Preserve previous source snapshot'
    else:dest.write_bytes(data)
    return data,dict(url=url,sha256=hashlib.sha256(data).hexdigest(),md5_checked=bool(md5),bytes=len(data),etag=headers.get('ETag'))

def title_label(title):
    found=[k for k,pat in LABEL_PATTERNS.items() if re.search(pat,title,re.I)]
    if len(found)!=1:return None
    if re.search(r'\b(?:mimic\w*|overlap\w*|coexisten\w*|concurrent|masquerad\w*|versus)\b',title,re.I):return None
    return found[0]

def figure_reasons(caption,xml_text,label):
    reasons=[]
    if not re.search(CAPTION_PATTERNS[label],caption,re.I):reasons.append('caption_does_not_explicitly_name_target')
    other=[k for k,pat in LABEL_PATTERNS.items() if k!=label and re.search(pat,caption,re.I)]
    if other:reasons.append('caption_names_multiple_target_diseases')
    if not re.search(r'\b(?:clinical|photograph\w*|lesions?|plaques?|erythematous|cutaneous|scalp|face|arm|leg|trunk|skin)\b',caption,re.I):reasons.append('not_explicitly_clinical_photo_caption')
    if re.search(r'\b(?:histopath\w*|histolog\w*|microscop\w*|dermoscop\w*|hematoxylin|haematoxylin|immunohistochem\w*|KOH|magnification|magnified|periodic acid|culture|DNA|PCR|graph|chart)\b|H\s*&\s*E|\d+\s*[xX×]',caption,re.I):reasons.append('microscopy_dermoscopy_lab_or_chart')
    if re.search(r'\b(?:after|post-treatment|posttreatment|follow-up|followup|resolution|resolved|improvement|response|healed)\b',caption,re.I):reasons.append('after_treatment_or_mixed_timepoints')
    if re.search(r'\b(?:reproduced|reprinted|adapted|courtesy|permission|VisualDx|DermNet)\b',xml_text,re.I):reasons.append('third_party_credit_requires_separate_rights_check')
    if re.search(r'<(?:\w+:)?permissions\b',xml_text,re.I):reasons.append('figure_specific_rights_require_manual_check')
    return reasons

def media_for_graphic(href,urls):
    name=PurePosixPath(href).name
    matches=[u for u in urls if PurePosixPath(urlparse(u).path).name==name or PurePosixPath(urlparse(u).path).stem==PurePosixPath(name).stem]
    matches=[u for u in matches if PurePosixPath(urlparse(u).path).suffix.lower() in {'.jpg','.jpeg','.png','.tif','.tiff'}]
    return sorted(matches,key=lambda u:(PurePosixPath(urlparse(u).path).suffix.lower() not in {'.jpg','.jpeg'},u))

def fingerprint(data):
    with Image.open(io.BytesIO(data)) as im:
        im.verify()
    with Image.open(io.BytesIO(data)) as im:
        a=np.asarray(im.convert('L').resize((9,8),Image.Resampling.LANCZOS),dtype=np.int16)
        bits=(a[:,1:]>a[:,:-1]).ravel();h=0
        for b in bits:h=(h<<1)|int(b)
        rgb=ImageOps.exif_transpose(im).convert('RGB');w,hh=rgb.size
        pixel=hashlib.sha256(f'{w},{hh}:'.encode()+rgb.tobytes()).hexdigest()
        return dict(sha256=hashlib.sha256(data).hexdigest(),pixel_sha256=pixel,dhash64=f'{h:016x}',width=w,height=hh,image_frames=getattr(im,'n_frames',1))

def article_versions(pmcid):
    url=BASE+'?'+urlencode({'list-type':'2','prefix':pmcid+'.','delimiter':'/'})
    data,_=request(url,1_000_000);(OUT/'source_snapshots'/(pmcid+'_versions.xml')).write_bytes(data)
    tree=ET.fromstring(data);prefixes=[n.text for n in tree.findall('.//{*}CommonPrefixes/{*}Prefix')]
    return sorted(prefixes,key=lambda s:int(s.rstrip('/').split('.')[-1]))

def main():
    assert not(OUT/'protocol.json').exists(),'Preserve304 intake registration'
    protected=R/'teacher_weak_free_sources_20261103/protected_union.jsonl'
    frozen={str(f.relative_to(ROOT)).replace('\\','/'):sha(f) for f in [protected,Path(__file__),ROOT/'ai-service/tests/test_open_case_photo_intake.py',R/'teacher_scin_unique_top_pilot_20261106/completion.json',ROOT/'ai-service/models/best_model.pth',ROOT/'ai-service/app/config.py',R/'active_research_track.json']}
    protocol=dict(registered_utc=utc(),scope='Bounded new free-source screening and provisional clinical-photo intake only. No model scoring, diagnosis by AI, training, deployment, contact or account creation.',frozen_sha256=frozen,
      sources=POLICY_URLS,queries=QUERIES,query_suffix=' AND open_access[filter] NOT pmc embargo[filter] AND 2016/01/01:2026/11/06[Publication Date]',per_class_article_limit=8,sort='pub date, as returned by NCBI ESearch; fixed first8 per query',
      source_version='Use earliest numerically available non-manuscript/non-retracted OA article version with license in allowlist. Archive all metadata decisions, full JATS only after license passes.',allowed_licenses=sorted(ALLOWED_LICENSES),
      rule='Narrow exact source title and figure-caption disease names only; no broad alias mapping or mixing diagnoses. Exclude microscopy/dermoscopy/lab/chart, post-treatment or mixed before-after captions and third-party credits. No crops or generated images; keep original source bytes. Each article is a conservative proxy group, not verified patient identity. Each figure is one file, panels are not counted as separate patients.',
      retrieval='NCBI ESearch <=2req/s and anonymous official PMC S3 metadata/JATS/media per current2026 docs. No HTML scraping or obsolete FTP/OA endpoint. Verify MD5 supplied in object URL, then byte/pixel/dHash and dimensions. Max20MB/object, at most3 graphic candidates/article, max72 images/24articles. All selected files remain provisional until visual modality/rights checks and a separate training protocol.',
      protection='Historical cached union19635 rows, plus all new candidates. Connect samearticle, exact byte/pixel or dHashHamming<=3 transitively; any existing-source hit or cross-label component quarantines entire component. Do not redownload/restore deleted corpora. No model error/loss/accuracy used in search or candidate choice.',
      limitations=['Author-reported diagnoses and captions are not a new clinical review in this project.','Case reports can be atypical and source-shifted; new files need not improve model scores.','Article-level groups and hashes do not establish new or independent patients.','Search and copyright checks are bounded; figure-specific exceptions may require manual rejection.','Queries and three example source pages were inspected exploratorily before registration; no model output was used.'],new_CNN_fits=0,selected=None,images_admitted_to_training=0,images_admitted_to_evaluation=0,serving_changed=False,global_5937_score_changed=False)
    write(OUT/'protocol.json',protocol);(OUT/'source_snapshots').mkdir(exist_ok=True);STORE.mkdir(parents=True,exist_ok=True)
    source_checks={}
    for name,url in POLICY_URLS.items():
        try:
            raw,headers=request(url,3_000_000);file=OUT/'source_snapshots'/(name+'.txt');file.write_bytes(raw);source_checks[name]=dict(url=url,path=file.relative_to(ROOT).as_posix(),sha256=sha(file),bytes=len(raw),status='retrieved')
        except Exception as e:source_checks[name]=dict(url=url,status='retrieval_failed',error=str(e))
    write(OUT/'source_checks.json',source_checks)
    searches={};articles=[];figures=[];downloads=[];totalbytes=0
    for label,query in QUERIES.items():
        term=query+protocol['query_suffix'];url='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?'+urlencode({'db':'pmc','term':term,'retmode':'json','retmax':8,'sort':'pub date','tool':'DermAIResearch'})
        raw,_=request(url,2_000_000);snap=OUT/'source_snapshots'/(label+'_esearch.json');snap.write_bytes(raw);response=json.loads(raw)['esearchresult'];ids=response.get('idlist',[]);searches[label]=dict(query=term,url=url,count=int(response.get('count',0)),ids=ids,snapshot_sha256=sha(snap));write(OUT/'searches.json',searches);time.sleep(.55)
        for ident in ids:
            pmcid='PMC'+ident;record=dict(pmcid=pmcid,query_label=label,url=f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/',accepted_source=False,reasons=[])
            print(dict(stage='metadata',pmcid=pmcid,label=label),flush=True)
            try:
                prefixes=article_versions(pmcid);chosen=None
                for prefix in prefixes:
                    key=prefix.rstrip('/');metaurl=BASE+'metadata/'+key+'.json';raw,_=fetch_object(metaurl,OUT/'source_snapshots'/(key+'.json'),2_000_000);meta=json.loads(raw)
                    lic=meta.get('license_code','').upper().strip();record.setdefault('versions',[]).append(dict(prefix=key,license=lic,is_manuscript=meta.get('is_manuscript'),is_retracted=meta.get('is_retracted')))
                    if lic in ALLOWED_LICENSES and meta.get('is_pmc_openaccess') is True and meta.get('is_retracted') is False and meta.get('is_manuscript') is False:chosen=(key,meta);break
                if chosen is None:record['reasons'].append('no_eligible_OA_version_or_license');articles.append(record);continue
                key,meta=chosen;record.update(title=meta['title'],license=meta['license_code'],doi=meta.get('doi'),article_version=key,metadata_path=(OUT/'source_snapshots'/(key+'.json')).relative_to(ROOT).as_posix())
                if title_label(meta['title'])!=label:record['reasons'].append('title_not_single_narrow_target_or_complex_overlap');articles.append(record);continue
                raw,obj=fetch_object(meta['xml_url'],OUT/'source_snapshots'/(key+'.xml'),3_000_000);tree=ET.fromstring(raw)
                if tree.get('article-type') in {'retraction','correction','expression-of-concern'}:record['reasons'].append('excluded_article_type');articles.append(record);continue
                license_nodes=tree.findall('.//article-meta/permissions/license');license_text=' '.join(' '.join(n.itertext()) for n in license_nodes)
                urls=[n.get(XLINK) for node in license_nodes for n in node.iter() if n.get(XLINK)]
                if not urls or not any('creativecommons.org/' in u for u in urls):record['reasons'].append('license_XML_not_explicit_CC');articles.append(record);continue
                record.update(accepted_source=True,license_urls=urls,article_type=tree.get('article-type'),xml_sha256=obj['sha256']);accepted=0
                for fig in tree.findall('.//fig'):
                    caption=' '.join(' '.join(n.itertext()) for n in fig.findall('caption'));fid=fig.get('id') or ''.join(fig.findtext('label','Figure')).replace(' ','')
                    f=dict(pmcid=pmcid,article_version=key,figure_id=fid,caption=caption,label=label,license=meta['license_code'],license_urls=urls,article_title=meta['title'],doi=meta.get('doi'),source_article=record['url'],source_group='PMC_ARTICLE::'+pmcid,source_patient_id=None,diagnostic_confirmation='author_reported_case_figure_caption_not_reviewed_in_project',training_eligible=False,evaluation_eligible=False)
                    reasons=figure_reasons(caption,ET.tostring(fig,encoding='unicode'),label);f['screening_reasons']=reasons
                    if reasons:figures.append(f);continue
                    graphics=fig.findall('.//graphic');possible=[]
                    for graphic in graphics:possible+=media_for_graphic(graphic.get(XLINK,''),meta.get('media_urls',[]))
                    if not possible:f['screening_reasons'].append('no_original_media_binding');figures.append(f);continue
                    if accepted>=3:f['screening_reasons'].append('fixed_article_graphic_cap');figures.append(f);continue
                    url=possible[0];filename=PurePosixPath(urlparse(url).path).name
                    destination=STORE/pmcid/filename;data,proof=fetch_object(url,destination);totalbytes+=len(data)
                    fp=fingerprint(data);f.update(path=destination.relative_to(ROOT).as_posix(),media_object=proof,**fp)
                    if min(fp['width'],fp['height'])<224:f['screening_reasons'].append('minimum_side_below224')
                    if fp['image_frames']!=1:f['screening_reasons'].append('multi_frame_image')
                    accepted+=1;downloads.append(f);figures.append(f)
            except Exception as e:record['reasons'].append('retrieval_or_validation_error');record['error']=str(e)
            articles.append(record);write(OUT/'article_screening.json',articles);lines(OUT/'figure_screening.jsonl',figures)
    write(OUT/'article_screening.json',articles);lines(OUT/'figure_screening.jsonl',figures)
    protection=[json.loads(x) for x in protected.read_text(encoding='utf-8').splitlines()];byte=defaultdict(list);pixel=defaultdict(list)
    hashes=[int(x['dhash64'],16) for x in protection]
    for j,v in enumerate(protection):byte[v['sha256']].append(j);pixel[v['pixel_sha256']].append(j)
    parent=list(range(len(downloads)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(i,j):
        i,j=find(i),find(j)
        if i!=j:parent[max(i,j)]=min(i,j)
    links=[];hits={}
    for i,v in enumerate(downloads):
        h=int(v['dhash64'],16);ix=set(byte[v['sha256']]+pixel[v['pixel_sha256']]);ix.update(j for j,x in enumerate(hashes) if (x^h).bit_count()<=3)
        if ix:hits[str(i)]=[dict(path=protection[j]['path'],exact_sha=v['sha256']==protection[j]['sha256'],same_pixel=v['pixel_sha256']==protection[j]['pixel_sha256'],dhash_distance=(h^hashes[j]).bit_count()) for j in sorted(ix)]
        for j,b in enumerate(downloads[:i]):
            reasons=[]
            if v['pmcid']==b['pmcid']:reasons.append('same_article_proxy')
            if v['sha256']==b['sha256']:reasons.append('same_bytes')
            if v['pixel_sha256']==b['pixel_sha256']:reasons.append('same_pixels')
            if (h^int(b['dhash64'],16)).bit_count()<=3:reasons.append('dhash_le3')
            if reasons:union(i,j);links.append(dict(a=i,b=j,reasons=reasons))
    components=defaultdict(list)
    for i in range(len(downloads)):components[find(i)].append(i)
    provisional=[];groups=[]
    for indices in components.values():
        labels={downloads[i]['label'] for i in indices};hit=any(str(i) in hits for i in indices);blocked=hit or len(labels)>1
        key=hashlib.sha256('\n'.join(sorted(downloads[i]['path'] for i in indices)).encode()).hexdigest()[:20]
        groups.append(dict(group=key,indices=indices,labels=sorted(labels),protected_hit=hit,quarantined=blocked,proxy_not_verified_patient=True))
        for i in indices:
            f=dict(downloads[i],group=key,quarantined=blocked,protected_hits=hits.get(str(i),[]),technical_visual_review_pending=True,clinical_review_in_project=False,role='provisional_source_candidate_not_admitted')
            if not blocked and not f['screening_reasons']:provisional.append(f)
    write(OUT/'similarity_audit.json',dict(protected_cache_sha256=sha(protected),protected_reference_rows=len(protection),links=links,hits=hits,components=groups))
    lines(OUT/'provisional_candidates.jsonl',provisional)
    result=dict(completed_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),searched_articles=len(articles),accepted_source_articles=sum(v['accepted_source'] for v in articles),source_search_counts={k:v['count'] for k,v in searches.items()},figures_screened=len(figures),downloaded_original_figure_files=len(downloads),download_bytes=totalbytes,downloaded_by_class=dict(Counter(v['label'] for v in downloads)),provisional_candidates=len(provisional),provisional_by_class=dict(Counter(v['label'] for v in provisional)),provisional_article_groups=len({v['pmcid'] for v in provisional}),direct_protected_hits=len(hits),quarantined_components=sum(v['quarantined'] for v in groups),protected_reference_rows=len(protection),images_admitted_to_training=0,images_admitted_to_evaluation=0,known_new_patient_count=None,CNN_fits=0,new_model_metrics=False,serving_changed=False,global_5937_score_changed=False)
    write(OUT/'results.json',result)
    for rel,h in frozen.items():assert sha(ROOT/rel)==h,rel
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
