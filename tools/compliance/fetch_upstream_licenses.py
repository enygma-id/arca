#!/usr/bin/env python3
"""Retrieve exact upstream license documents used by ARCA, without modifying code.
Only trusted hard-coded HTTPS URLs. Requires network access on the executing machine.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCES = [
    {
        'id':'CESIUM-1.145', 'component':'CesiumJS', 'version':'1.145',
        'url':'https://raw.githubusercontent.com/CesiumGS/cesium/1.145/LICENSE.md',
        'path':'third-party/cesium/LICENSE.md', 'min_bytes':25000,
        'must_contain':['Apache License','Third-Party Code', 'CesiumJS'], 'required':True,
        'purpose':'Full tagged Cesium license including upstream third-party sections; remote CDN dependency',
    },
    {
        'id':'MAPLIBRE-v6.9.0', 'component':'MapLibre GL JS', 'version':'v6.9.0',
        'url':'https://raw.githubusercontent.com/maplibre/maplibre-gl-js/v6.9.0/LICENSE.txt',
        'path':'third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt', 'min_bytes':3000,
        'must_contain':['MapLibre contributors','mapbox-gl-js','glfx.js'], 'required':True,
        'purpose':'Full original tagged BSD and inherited-origin third party text; DOES NOT overwrite existing LICENSE',
    },
    {
        'id':'DECK-v9.3.7', 'component':'Deck.gl', 'version':'v9.3.7',
        'url':'https://raw.githubusercontent.com/visgl/deck.gl/v9.3.7/LICENSE',
        'path':'third-party/deck.gl/LICENSE.upstream-v9.3.7', 'min_bytes':700,
        'must_contain':['MIT', 'Permission is hereby granted'], 'required':True,
        'purpose':'Original tagged root license; bundled transitive/Apache modules still require assessment',
    },
    {
        'id':'THREE-r185', 'component':'Three.js', 'version':'r185 = 0.185.0',
        'url':'https://raw.githubusercontent.com/mrdoob/three.js/r185/LICENSE',
        'path':'third-party/three/LICENSE.upstream-r185', 'min_bytes':700,
        'must_contain':['MIT License','three.js authors'], 'required':True,
        'purpose':'Compare with existing bundled license; preserves original existing file',
    },
    {
        'id':'CESIUM-1.145-THIRDPARTY', 'component':'CesiumJS third-party bundle inventory', 'version':'1.145',
        'url':'https://cdn.jsdelivr.net/npm/cesium@1.145.0/Build/Cesium/ThirdParty.json',
        'path':'third-party/cesium/ThirdParty.json', 'min_bytes':15,
        'must_contain':[], 'required':False,
        'purpose':'Optional release-bundle-generated ThirdParty.json, only when endpoint exists',
    },
]


def verify(data:bytes, src:dict):
    if len(data) < src['min_bytes']: raise ValueError('File too small or empty; possibly a 404/HTML response')
    head=data[:600].lstrip().lower()
    if head.startswith(b'<!doctype') or head.startswith(b'<html') or b'<html' in head[:100]: raise ValueError('HTML response is not a legal text')
    if src['path'].endswith('.json'):
        obj=json.loads(data)
        if not isinstance(obj,(list,dict)) or not obj: raise ValueError('Empty/invalid JSON')
    else:
        body=data.decode('utf-8-sig')
        for s in src['must_contain']:
            if s.lower() not in body.lower(): raise ValueError('Missing mandatory signature: '+s)
    return hashlib.sha256(data).hexdigest()


def get(url:str)->bytes:
    # curl is included with macOS, handles system trust stores better than some standalone Python builds.
    with tempfile.TemporaryDirectory(prefix='arca_upstream_') as temp:
        tmp=Path(temp)/'download.tmp'
        cmd=['curl','--fail','--silent','--show-error','--location','--retry','1',
             '--connect-timeout','15','--max-time','30','--proto','=https',
             '--proto-redir','=https','--tlsv1.2','--user-agent','ARCA-Community-License-Provenance/1.0',
             '--output',str(tmp),url]
        p=subprocess.run(cmd, capture_output=True,text=True)
        if p.returncode: raise RuntimeError('curl failed: '+(p.stderr.strip()[:300] or str(p.returncode)))
        return tmp.read_bytes()


def main():
    cli=argparse.ArgumentParser(description='ARCA version-specific upstream legal evidence fetcher')
    cli.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2])
    args=cli.parse_args()
    root=args.repo_root.resolve()
    if not (root/'pyproject.toml').is_file() or not (root/'LICENSE').is_file():
        print('ERROR: Expected ARCA repository root with pyproject.toml and LICENSE:',root,file=sys.stderr)
        return 2
    date=datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows=[]
    for spec in SOURCES:
        dst=root/spec['path']
        rec={'id':spec['id'],'component':spec['component'],'version':spec['version'],
             'source_url':spec['url'],'repo_path':spec['path'],'required':spec['required'],
             'status':'NOT_FETCHED','sha256':None,'size':None,'timestamp_utc':date}
        try:
            data=get(spec['url'])
            digest=verify(data,spec)
            dst.parent.mkdir(parents=True,exist_ok=True)
            if dst.exists() and dst.read_bytes()==data: action='unchanged'
            else:
                # atomic replacement only after complete verification; never delete a previously good document on failure
                temp=dst.with_name('.'+dst.name+'.tmp')
                try:
                    temp.write_bytes(data);os.replace(temp,dst)
                finally:
                    temp.unlink(missing_ok=True)
                action='written'
            rec.update({'status':'FETCHED_TAGGED_SOURCE','sha256':digest,'size':len(data),'action':action})
            print('OK  ',spec['id'],'=>',spec['path'],len(data),'bytes, sha256',digest)
        except Exception as exc:
            rec.update({'status':'NEEDS_VERIFICATION','error':str(exc)})
            print('WARN',spec['id'],'NOT downloaded:',exc,file=sys.stderr)
        rows.append(rec)
    out_dir=root/'docs/compliance'
    out_dir.mkdir(parents=True,exist_ok=True)
    out_file=out_dir/'UPSTREAM_FETCH_EVIDENCE.json'
    out_file.write_text(json.dumps({'tool':'ARCA upstream license evidence fetcher',
         'generated_utc':date,'baseline_note':'ZIP overlay only. Runtime code, main LICENSE and third-party originals unchanged.',
         'review_status':'DOCUMENTARY_EVIDENCE_ONLY; HUMAN_LEGAL_APPROVAL_REQUIRED',
         'results':rows},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# ARCA upstream license document retrieval', '',f'Date (UTC): {date}',
      '', '**This is evidence of source retrieval, not proof of complete legal compliance.**',
      '', '| Component | Version | Status | Destination | SHA-256 |', '|---|---|---|---|---|']
    for r in rows:
        lines.append('| '+ ' | '.join((r['component'],r['version'],r['status'],
                        '`'+r['repo_path']+'`', ('`'+r['sha256']+'`') if r['sha256'] else '—'))+' |')
    lines += ['', '## Remaining human/administrative checks',
      '- Verify Cesium 1.145 license and notices correspond to the remote Cesium distribution.',
      '- Confirm MapLibre full tagged LICENSE text governs the exact vendored JS/CSS/worker files.',
      '- Reconcile Deck.gl bundled source/modules; root MIT license is not proof for all transitive modules.',
      '- Inspect Python-native wheels on actual target platforms separately.',
      '- Do NOT change the root AGPL-3.0-only LICENSE or treat these texts as Enygma-owned.',
      '- Do NOT publish a declaration of complete compliance without human approval.',
      '', '## Version-specific official sources', '']
    for r in rows: lines += ['- '+r['id']+': '+r['source_url']]
    (out_dir/'UPSTREAM_FETCH_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    fails=[r for r in rows if r['required'] and r['status']!='FETCHED_TAGGED_SOURCE']
    print('\nEvidence saved:',out_file)
    if fails:
        print('Required documents pending:',', '.join(r['id'] for r in fails))
        return 1
    print('All required root license texts downloaded; legal/bundle verification is still separate.')
    return 0

if __name__=='__main__': sys.exit(main())
