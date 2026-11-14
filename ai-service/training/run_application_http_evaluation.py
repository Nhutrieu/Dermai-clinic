"""Run a fully registered application evaluation through the deployed Docker API.

No images are skipped, gates bypassed, or model/settings changed. Native Windows
attempts are archived before the Docker run; they never enter final metrics.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import importlib.util
import json
import mimetypes
import subprocess
import time

import httpx

SOURCE = Path(__file__).with_name('evaluate_application_model.py')
spec = importlib.util.spec_from_file_location('frozen_application_evaluation', SOURCE)
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def docker_snapshot():
    probe = r'''
from pathlib import Path
import hashlib,json,platform,torch,torchvision,numpy
from app.config import settings
root=Path('/models/research_pipeline');manifest=json.loads((root/'manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
out=dict(platform=platform.system(),python=platform.python_version(),torch=torch.__version__,torchvision=torchvision.__version__,numpy=numpy.__version__,device='cpu',cuda_available=torch.cuda.is_available(),manifest_sha256=sha(root/'manifest.json'),assets_sha256={k:sha(root/v['path']) for k,v in manifest['assets'].items()},app_sha256={p.name:sha(p) for p in Path('/app/app').glob('*.py')},api_settings={k:getattr(settings,k) for k in ['max_upload_bytes','confidence_threshold','confidence_margin_threshold','normalized_entropy_threshold','allowed_mime','inference_threads']})
print(json.dumps(out))
'''
    process=subprocess.run(['docker','compose','exec','-T','ai-service','python','-'],
        input=probe.encode(),capture_output=True,cwd=m.ROOT,check=True)
    snap=json.loads(process.stdout.decode())
    snap['image_id']=subprocess.run(['docker','inspect','--format','{{.Image}}','dermai-clinic-ai-service-1'],capture_output=True,text=True,check=True).stdout.strip()
    return snap


def register(out,url):
    p=m.read(out/'protocol.json');m.verify_frozen(p)
    if (out/'predictions_locked.json').exists() or (out/'results.json').exists():
        raise FileExistsError('Preserve completed/scored predictions')
    if p.get('execution_revision')==2:
        raise FileExistsError('Docker execution already registered; use run')
    snap=docker_snapshot();manifest=m.read(m.PACKAGE/'manifest.json')
    assert snap['platform']=='Linux' and not snap['cuda_available']
    assert snap['manifest_sha256']==m.sha(m.PACKAGE/'manifest.json')
    assert snap['api_settings']==p['api_settings']
    for name,entry in manifest['assets'].items():assert snap['assets_sha256'][name]==entry['sha256']
    for name,h in snap['app_sha256'].items():assert m.sha(m.AI/'app'/name)==h
    with httpx.Client(base_url=url,timeout=15) as client:
        health=client.get('/health').json()
    assert health['modelReady'] and health['ragReady'] and health['modelVersion']==p['version'] and health['modelMode']=='research_pipeline'
    native=out/'native_attempts';native.mkdir(exist_ok=True)
    m.write(native/'protocol_v1.json',p)
    for name in ['predictions.jsonl','environment.json']:
        f=out/name
        if f.exists():
            target=native/name
            assert target.resolve().is_relative_to(m.ROOT.resolve()) and not target.exists()
            f.rename(target)
    snap.update(health=health,base_url=url,checked_utc=m.utc())
    m.write(out/'docker_runtime.json',snap)
    amendment=dict(registered_utc=m.utc(),original_protocol_sha256=m.sha(native/'protocol_v1.json'),
        reason='Windows native process access violations occurred during Pillow PNG/Grad-CAM encoding; evaluate the entire original manifest on the deployed Linux Docker API instead.',
        change='Execution engine only; same original images, audit, thresholds, 26 package assets, app code, labels, metrics and all 723 inputs. Discard native partial outputs from final metrics; no outcome-based exclusion.',
        native_attempt_records=sum(1 for _ in (native/'predictions.jsonl').open(encoding='utf-8')) if (native/'predictions.jsonl').exists() else 0,
        runner_sha256=m.sha(Path(__file__)),docker_snapshot_sha256=m.sha(out/'docker_runtime.json'))
    m.write(out/'execution_amendment.json',amendment)
    p.update(execution_revision=2,engine='Live HTTP POST /predict on the deployed Linux Docker CPU API; original full workflow, no mocks',
        execution_amendment='execution_amendment.json',base_url=url)
    for f in [Path(__file__),out/'docker_runtime.json',out/'execution_amendment.json']:
        p['frozen_sha256'][m.rel(f)]=m.sha(f)
    m.write(out/'protocol.json',p);m.write(out/'status.json',dict(state='registered_Docker_HTTP',updated_utc=m.utc()))
    print('Registered complete Docker API evaluation; native attempts archived and excluded from metrics',flush=True)


def run(out):
    p=m.read(out/'protocol.json');m.verify_frozen(p);assert p['execution_revision']==2
    assert not(out/'predictions_locked.json').exists()
    snap=docker_snapshot();expected=m.read(out/'docker_runtime.json')
    for key in ['image_id','manifest_sha256','assets_sha256','app_sha256','api_settings']:
        assert snap[key]==expected[key],key
    rows=m.read(out/'evaluation_manifest.json');file=out/'predictions.jsonl';done=[]
    if file.exists():
        done=[json.loads(x) for x in file.read_text(encoding='utf-8').splitlines()]
        assert len(done)<=len(rows)
        for a,b in zip(rows,done):assert all(a[k]==b[k] for k in ['path','sha256','label','dataset','group'])
    with httpx.Client(base_url=p['base_url'],timeout=60) as client,file.open('a',encoding='utf-8') as log:
        health=client.get('/health').json();assert health['modelReady'] and health['modelVersion']==p['version']
        m.write(out/'environment.json',dict(engine='deployed_Docker_CPU_HTTP',**snap,health=health))
        for i,row in enumerate(rows[len(done):],len(done)):
            image=m.ROOT/row['path'];assert m.sha(image)==row['sha256']
            started=time.perf_counter()
            response=client.post('/predict',headers={'X-User-Role':'PATIENT'},
                files={'image':(image.name,image.read_bytes(),mimetypes.guess_type(image.name)[0] or 'image/jpeg')})
            if response.status_code not in [200,413,415,422]:
                m.write(out/'error.json',dict(index=i,status=response.status_code,detail=response.text[:500]))
                raise RuntimeError('Unexpected API failure; preserve prefix, do not skip sample')
            payload=response.json();record={k:row[k] for k in ['path','sha256','label','dataset','group']}
            record.update(http_status=response.status_code,seconds=time.perf_counter()-started)
            if response.status_code==200:
                assert payload['model_version']==p['version'] and payload['score_type']=='fold_vote_fraction'
                for key in ['disease','confidence','top3','uncertain','model_version','score_type','confidence_is_calibrated','decision_policy_applied','fold_decisions']:
                    record[key]=payload[key]
                record.update(gradcam_present=bool(payload['gradcam_image']),guidance_present=bool(payload.get('guidance')))
            else:record.update(disease=None,uncertain=None,detail=payload.get('detail',''))
            log.write(json.dumps(record,ensure_ascii=False)+'\n');log.flush();done.append(record)
            if (i+1)%25==0 or i+1==len(rows):
                m.write(out/'status.json',dict(state='predicting_Docker_HTTP',completed=i+1,total=len(rows),updated_utc=m.utc()))
                print(f'Docker API predictions {i+1}/{len(rows)}',flush=True)
    m.verify_frozen(p)
    m.write(out/'predictions_locked.json',dict(locked_utc=m.utc(),images=len(rows),
        predictions_sha256=m.sha(file),protocol_sha256=m.sha(out/'protocol.json'),engine='deployed_Docker_CPU_HTTP'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['register','run'])
    parser.add_argument('--output',type=Path,default=m.REPORT)
    parser.add_argument('--url',default='http://localhost:8000')
    args=parser.parse_args()
    if args.phase=='register':register(args.output.resolve(),args.url)
    else:run(args.output.resolve())
