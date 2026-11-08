"""256 audit a new public Psoriasis archive without inflating frame/augmentation counts."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
import json,hashlib,io,re,zipfile
import numpy as np
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;R=OUT.parent;STORE=ROOT/'SkinDisease/sources/skindis_india_v2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();utc=lambda:datetime.now(timezone.utc).isoformat()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def entries(p):return [json.loads(v) for v in Path(p).read_text(encoding='utf-8').splitlines()]
def lines(p,rows):Path(p).write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in rows),encoding='utf-8')
PROTECTED=[R/'original_eight_psoriasis_supplement_20261021'/n for n in ['extended_protected_fingerprints.jsonl','candidate_fingerprints.jsonl','combined_auxiliary_train_final.jsonl']]


def family(member):
    stem=Path(member).stem
    if re.fullmatch(r'frame_\d+',stem):return 'unidentified_frame_sequence'
    stem=re.sub(r'_frame_\d+$','',stem);stem=re.sub(r' \(\d+\)$','',stem);return re.sub(r'_\d{1,2}$','',stem)


def fingerprint(data):
    with Image.open(io.BytesIO(data)) as im:
        raw=im.convert('L').resize((9,8),Image.Resampling.LANCZOS);v=np.asarray(raw,dtype=np.int16);value=0
        for bit in (v[:,1:]>v[:,:-1]).ravel():value=(value<<1)|int(bit)
        rgb=ImageOps.exif_transpose(im).convert('RGB');w,h=rgb.size;pixel=hashlib.sha256(f'{w},{h}:'.encode()+rgb.tobytes()).hexdigest()
    return dict(sha256=hashlib.sha256(data).hexdigest(),pixel_sha256=pixel,dhash64=f'{value:016x}',width=w,height=h)


def main():
    assert not (OUT/'protocol.json').exists(),'Preserve256 audit'
    source=read(OUT/'r7kdbj2wym_files.json')[0];archive=STORE/source['filename'];assert sha(archive)==source['content_details']['sha256_hash'];files=[archive,Path(__file__),ROOT/'tmp/review_weak_free_sources_20261103.py',ROOT/'tmp/finish_weak_free_sources_20261103.py',OUT/'acquisition_protocol.json',OUT/'archive_inventory.json',OUT/'r7kdbj2wym_snapshot.json',OUT/'r7kdbj2wym_files.json',OUT/'pgd42j3h5c_snapshot.json',OUT/'pgd42j3h5c_files.json',OUT/'source_screening.json',*PROTECTED,R/'teacher_weak_data_readiness_20261103/completion.json']
    p=dict(registered_utc=utc(),scope='Free public clinical-photo source screening and SkinDis-India v2 Psoriasis auxiliary-candidate preparation. Exploratory archive names already inspected before this protocol; no model predictions/metrics used.',sources_sha256={f.relative_to(ROOT).as_posix():sha(f) for f in files},
        rule='ReadallJPEGmembers, folderlabels onlyPsoriasis/Vitiligo. CanonicalpixelSHA exiftransposeRGB width,height prefix; historicaldHash rawL9x8Lanczos/right>left. WithinPsoriasis connectsamefilenamefamily,byteSHA,pixelSHA,ordHashHamming<=3 transitively. Filenamerecipe removes_frame_digits, copy suffix(space(n)), trailing_one_or_two_digit_numericvariant (notlongcameraID/timestamp); bareframe_digits alloneunknownfamily. Theseareconservativeproxygroups, notverifiedpatients.',
        protection='CompareALLPsoriasisframes exhaustively againstunionexisting19261historicalprotectedfingerprints,374Fitzcandidates,1128auxiliaryrows, andcurrentarchiveVitiligo. ExactSHA/pixel orrawdHash<=3 hit quarantinesWHOLEPsoriasiscomponent. Missinghistoricalphysicalfiles remainprotectedbycachedfingerprint andnotrestored. No near-hit usedasdiagnosisjudgment.',
        candidate_choice='One deterministic representative per unquarantinedcomponent:lexicographicallysmallestSHA thenmember. CopyoriginalJPEGbytes toreview_candidates/<SHA>.jpg. Sourcefolder labelPsoriasis only; noVitiligomapping to8diseases. Allcandidates provisionalauxiliaryTRAIN-ONLY, notadmitted/currenttrain/test. training_eligible=False untilseparatefrozenexperimentadmitsrole; evaluation_eligible=False. No diagnosisconfirmation orverifiedpatientID claim.',
        boundary='No newCNNfit, prediction, modelselection, thresholdsearch, scoreupdate, sourcecontact, accountcreation oraccess-requestsubmission. SourceCCBY4claimedbypublicrecord, no commercial permission inferred for otherdatasets. No synthetic/augmentedframe countednewpatient.',
        limitations=['Filenamefamilies anddHash do notcapturealltransforms orsamepatientacrossviews; noindependencetestclaim.','Source title saysaugmented, nooriginal-to-frame map/patientIDs inarchive; sourcefolder labels notnewclinicalconfirmation.','Historicalfingerprints maycoverdeletedfiles:useconservatively,neverrestoreinactivecorpora.','Source search is bounded screening, notproofnootherfreeLupus/Tineasourceexists.'],labels_changed=0,new_CNN_fits=0,new_metrics_computed=False,selected=None,serving_changed=False,global_5937_score_changed=False)
    write(OUT/'protocol.json',p);protected={}
    for f in PROTECTED:
        for row in entries(f):protected[(row['path'],row['sha256'])]=row
    protection=list(protected.values());lines(OUT/'protected_union.jsonl',protection);rows=[]
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            path=Path(item.filename)
            assert not path.is_absolute() and '..' not in path.parts and not (item.flag_bits&1)
            if item.is_dir():continue
            assert path.suffix.lower() in ['.jpg','.jpeg'] and path.parent.name in ['Psoriasis','Vitiligo']
            data=z.read(item);rows.append(dict(member=item.filename,source_label=path.parent.name,filename_family=path.parent.name+'::'+family(item.filename),**fingerprint(data)))
    lines(OUT/'archive_fingerprints.jsonl',rows);cand=[v for v in rows if v['source_label']=='Psoriasis'];other=[dict(path='archive::'+v['member'],**{k:v[k] for k in ['sha256','pixel_sha256','dhash64']}) for v in rows if v['source_label']=='Vitiligo'];ref=protection+other;hvalues=[int(v['dhash64'],16) for v in ref];exact=defaultdict(set);pix=defaultdict(set)
    for i,v in enumerate(ref):exact[v['sha256']].add(i);pix[v['pixel_sha256']].add(i)
    parent=list(range(len(cand)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    hashes=[int(v['dhash64'],16) for v in cand];links=[];hits={}
    for i,v in enumerate(cand):
        matching=set(exact[v['sha256']])|pix[v['pixel_sha256']]
        matching.update(j for j,value in enumerate(hvalues) if (hashes[i]^value).bit_count()<=3)
        if matching:hits[i]=[dict(path=ref[j]['path'],distance=(hashes[i]^hvalues[j]).bit_count(),exact_sha=v['sha256']==ref[j]['sha256'],same_pixel=v['pixel_sha256']==ref[j]['pixel_sha256']) for j in sorted(matching)]
        for j in range(i):
            reasons=[]
            if v['filename_family']==cand[j]['filename_family']:reasons.append('filename_family')
            if v['sha256']==cand[j]['sha256']:reasons.append('sha256')
            if v['pixel_sha256']==cand[j]['pixel_sha256']:reasons.append('pixel_sha256')
            if (hashes[i]^hashes[j]).bit_count()<=3:reasons.append('dhash_le3')
            if reasons:union(i,j);links.append(dict(a=i,b=j,reasons=reasons))
    components=defaultdict(list)
    for i in range(len(cand)):components[find(i)].append(i)
    groups=[];candidates=[];STORE.joinpath('review_candidates').mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for key,indices in sorted(components.items()):
            members=[cand[i] for i in indices];bad=[i for i in indices if i in hits];group=hashlib.sha256('\n'.join(sorted(v['member'] for v in members)).encode()).hexdigest()[:20];representative=min(members,key=lambda v:(v['sha256'],v['member']));groups.append(dict(group=group,indices=indices,filename_families=sorted({v['filename_family'] for v in members}),members=len(members),quarantined=bool(bad),protected_hit_indices=bad,representative_member=None if bad else representative['member']))
            if not bad:
                destination=STORE/'review_candidates'/(representative['sha256']+'.jpg');data=z.read(representative['member']);assert hashlib.sha256(data).hexdigest()==representative['sha256']
                if destination.exists():assert sha(destination)==representative['sha256']
                else:destination.write_bytes(data)
                candidates.append(dict(source='SkinDis-India-v2',dataset_url='https://data.mendeley.com/datasets/r7kdbj2wym/2',source_label='Psoriasis',label='Psoriasis',source_member=representative['member'],path=destination.relative_to(ROOT).as_posix(),group=group,source_patient_id=None,clinical_confirmation_available=False,filename_families=sorted({v['filename_family'] for v in members}),related_archive_frames=len(members),license='CC BY4.0 statedbydatasetrecord',role='provisional_auxiliary_candidate_not_admitted',training_eligible=False,evaluation_eligible=False,**{k:representative[k] for k in ['sha256','pixel_sha256','dhash64','width','height']}))
    write(OUT/'similarity_audit.json',dict(links=links,hits=hits,components=groups));lines(OUT/'provisional_candidates.jsonl',candidates)
    exists=sum((ROOT/v['path']).is_file() for v in protection);r=dict(completed_utc=utc(),protocol_sha256=sha(OUT/'protocol.json'),archive_images=len(rows),archive_class_counts=dict(Counter(v['source_label'] for v in rows)),psoriasis_frames=len(cand),psoriasis_distinct_bytes=len({v['sha256'] for v in cand}),psoriasis_distinct_pixels=len({v['pixel_sha256'] for v in cand}),filename_families=len({v['filename_family'] for v in cand}),conservative_components=len(groups),protected_reference_rows=len(protection),protected_reference_physical_paths_present=exists,protected_reference_missing_or_archive_paths=len(protection)-exists,crossclass_reference_images=len(other),direct_hit_images=len(hits),quarantined_components=sum(v['quarantined'] for v in groups),provisional_representatives=len(candidates),images_admitted_to_training=0,images_admitted_to_evaluation=0,known_new_patient_count=None,new_CNN_fits=0,new_model_metrics=False,selected=None,serving_changed=False,global_5937_score_changed=False);write(OUT/'results.json',r)
    for f,h in p['sources_sha256'].items():assert sha(ROOT/f)==h,f
    print(r,flush=True)


if __name__=='__main__':main()
