#!/usr/bin/env python3
"""Reconcile ARCA's version-exact fetched upstream license evidence.

Offline, stdlib-only. Preflight validates exact tagged bytes, consistency with
UPSTREAM_FETCH_EVIDENCE.json, and original vendored bundle hashes.
No claims of bundle-level compliance, no source/runtime modification.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

RECORDS = [
    dict(key='cesiumjs',name='CesiumJS',version='1.145',id='CESIUM-1.145',
         path='third-party/cesium/LICENSE.md',sha='721844bc0cdaa9b1a9a145dbca1f981e2de15a7e200a5d1fd9f5f1eed8e5d030',
         source='https://raw.githubusercontent.com/CesiumGS/cesium/1.145/LICENSE.md'),
    dict(key='maplibre-gl',name='MapLibre GL JS',version='6.9.0',id='MAPLIBRE-v6.9.0',
         path='third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt',sha='ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2',
         source='https://raw.githubusercontent.com/maplibre/maplibre-gl-js/v6.9.0/LICENSE.txt'),
    dict(key='deck.gl',name='Deck.gl',version='9.3.7',id='DECK-v9.3.7',
         path='third-party/deck.gl/LICENSE.upstream-v9.3.7',sha='e499a2c2ba3b9faabe91fdfddf43e329439263264b7148e5548d0ec605cce9f2',
         source='https://raw.githubusercontent.com/visgl/deck.gl/v9.3.7/LICENSE'),
    dict(key='three',name='Three.js',version='0.185.0',id='THREE-r185',
         path='third-party/three/LICENSE.upstream-r185',sha='8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc',
         source='https://raw.githubusercontent.com/mrdoob/three.js/r185/LICENSE'),
    dict(key='cesiumjs-thirdparty',name='CesiumJS ThirdParty.json',version='1.145',id='CESIUM-1.145-THIRDPARTY',
         path='third-party/cesium/ThirdParty.json',sha=None,
         source='https://raw.githubusercontent.com/CesiumGS/cesium/1.145/ThirdParty.json'),
]

FOLDERS = {
 'cesiumjs': ('third-party/cesium/LICENSE.md', 'third-party/cesium/ThirdParty.json'),
 'deck.gl': ('third-party/deck.gl/LICENSE.upstream-v9.3.7',),
 'maplibre-gl': ('third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt',),
 'three': ('third-party/three/LICENSE.upstream-r185',),
}


def digest(data): return hashlib.sha256(data).hexdigest()


def replace_table_row(text, prefix, new_row):
    lines=text.splitlines(keepends=True)
    hits=[i for i,l in enumerate(lines) if l.startswith(prefix)]
    if len(hits)!=1: raise ValueError('Expected exactly one markdown table row '+prefix+', found '+str(len(hits)))
    lines[hits[0]]=new_row+'\n'
    return ''.join(lines)


def must_read(root, relative):
    p=root/relative
    if not p.is_file(): raise FileNotFoundError(f'Required file absent: {relative}')
    return p.read_bytes()


def reconcile(root):
    errors=[]; evidence={}; checked=[]
    for rec in RECORDS:
        try:
            raw=must_read(root,rec['path'])
            if len(raw)<100: raise ValueError('Unexpectedly short')
            sha=digest(raw)
            if rec['sha'] and sha!=rec['sha']: raise ValueError(f'SHA256 differs: expected {rec["sha"]} got {sha}')
            if rec['path'].endswith('.json'):
                obj=json.loads(raw)
                if not isinstance(obj,(dict,list)) or not obj: raise ValueError('JSON empty or invalid')
            elif raw.lstrip().lower().startswith(b'<html'): raise ValueError('HTML not license text')
            evidence[rec['id']]={'id':rec['id'],'key':rec['key'],'name':rec['name'],'version':rec['version'],
                'path':rec['path'],'sha256':sha,'size_bytes':len(raw),'source_url':rec['source'],
                'status':'FETCHED_TAGGED_SOURCE','legal_compliance':'NOT_DETERMINED'}
            checked.append(rec['path'])
        except Exception as exc: errors.append(f'{rec["id"]}: {exc}')
    fetch_file=root/'docs/compliance/UPSTREAM_FETCH_EVIDENCE.json'
    if not fetch_file.is_file(): errors.append('Missing docs/compliance/UPSTREAM_FETCH_EVIDENCE.json')
    else:
        try:
            fetched=json.loads(fetch_file.read_text(encoding='utf-8-sig'))
            fetched_rows={r['id']:r for r in fetched.get('results',[])}
            for rec in RECORDS:
                row=fetched_rows.get(rec['id'])
                if not row: errors.append(f'No fetch-evidence entry for {rec["id"]}'); continue
                if row.get('status')!='FETCHED_TAGGED_SOURCE':
                    errors.append(f'Fetch evidence not success for {rec["id"]}: {row.get("status")}')
                if row.get('sha256')!=evidence.get(rec['id'],{}).get('sha256'):
                    errors.append(f'Fetch evidence SHA differs for {rec["id"]}')
        except Exception as exc: errors.append(f'Fetch evidence unreadable: {exc}')
    try:
        manifest=json.loads(must_read(root,'third-party/MANIFEST.json'))
        vendors=manifest['vendor_file_inventory']
        for r in vendors:
            path=r['path']; sha=digest(must_read(root,path))
            if sha!=r['sha256']: errors.append(f'Vendored bundle SHA mismatch {path}')
    except Exception as exc: errors.append(f'Manifest/vendor inventory cannot be validated: {exc}')
    if errors: raise ValueError('Preflight FAILED; no files changed:\n - '+'\n - '.join(errors))

    timestamp=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    values={r['key']:evidence[r['id']] for r in RECORDS}
    manifest['upstream_legal_documents']=list(evidence.values())
    manifest['upstream_document_reconciliation']={
      'reconciled_at_utc':timestamp,
      'status':'LICENSE_TEXTS_ARCHIVED__BUNDLE_AND_LEGAL_REVIEW_PENDING',
      'local_legal_text_sha_verified':True,
      'vendored_files_sha_verified':len(vendors),
      'notices_bundled_completeness_verified':False,
      'native_wheels_verified':False,
      'human_approval_required':True,
    }
    front=manifest['frontend_vendor_dependencies']
    for k in ('cesiumjs','deck.gl','maplibre-gl','three'):
        r=values[k]; ent=front[k]
        ent['upstream_license_text_path']=r['path'];ent['upstream_license_text_sha256']=r['sha256']
        ent['upstream_license_document_status']='FETCHED_TAGGED_SOURCE'
        ent['reference_status']='TAGGED_LICENSE_ARCHIVED__BUNDLE_OR_DISTRIBUTION_REVIEW_PENDING'
    ces=front['cesiumjs']
    ces['license_text_path']=values['cesiumjs']['path'];ces['sha256']=values['cesiumjs']['sha256']
    ces['third_party_notice_path']=values['cesiumjs-thirdparty']['path']
    ces['third_party_notice_sha256']=values['cesiumjs-thirdparty']['sha256']
    ces['status']='NEEDS_VERIFICATION'
    ces['note']='Both upstream documents archived; verify correspondence with actual remote CDN build and complete attribution obligations.'
    front['maplibre-gl']['complete_upstream_license_status']='TAGGED_LICENSE_CAPTURED; VENDORED_BUNDLE_PROVENANCE_PENDING'
    front['deck.gl']['bundle_license_notice_status']='UPSTREAM_ROOT_LICENSE_CAPTURED; DIST_BUNDLE_TRANSITIVE_NOTICES_PENDING'
    front['deck.gl']['license']='MIT (tagged root); exact distributed bundle component notices require verification'
    # Existing files list remains valid; add new evidence files without duplicates.
    for r in RECORDS:
        rel=r['path'].removeprefix('third-party/')
        if rel not in manifest['files']: manifest['files'].append(rel)
    changes={'third-party/MANIFEST.json':(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')}

    notices=must_read(root,'THIRD_PARTY_NOTICES.md').decode('utf-8')
    row_map={
     '| **CesiumJS** |': '| **CesiumJS** | **1.145** | CDN script, CSS and Cesium assets invoked by Studio and viewer | Apache-2.0; release-specific third-party notices | Fetched upstream [`LICENSE.md`](./third-party/cesium/LICENSE.md) and [`ThirdParty.json`](./third-party/cesium/ThirdParty.json); exact CDN build and notice completeness still `NEEDS_VERIFICATION`. |',
     '| **Deck.gl** |': '| **Deck.gl** | **9.3.7** | Local minified bundle plus remote unpkg fallback | MIT root; bundled transitive components to verify | Fetched [`v9.3.7 LICENSE`](./third-party/deck.gl/LICENSE.upstream-v9.3.7); attribution and license composition of the shipped bundle still `NEEDS_VERIFICATION`. |',
     '| **MapLibre GL JS** |': '| **MapLibre GL JS** | **6.9.0** | Local MJS, worker, shared module and CSS | BSD-3-Clause with inherited component notices | Fetched full [`v6.9.0 LICENSE.txt`](./third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt), including upstream-origin attribution; vendored build provenance remains `NEEDS_VERIFICATION`. |',
     '| **Three.js** |': '| **Three.js** | **0.185.0 (r185)** | Local Three core, module and addons | MIT | Fetched tagged [`r185 LICENSE`](./third-party/three/LICENSE.upstream-r185); exact vendored-file origin still requires comparison. |',
    }
    for prefix,row in row_map.items(): notices=replace_table_row(notices,prefix,row)
    old='**Do not present this inventory as completed evidence for the corresponding upstream license files.** Obtain the exact released license/NOTICE and embedded bundle notices in the approval step described in [`docs/compliance/UPSTREAM_LICENSE_FETCH.md`](./docs/compliance/UPSTREAM_LICENSE_FETCH.md).'
    new='**Tagged upstream legal texts and Cesium ThirdParty.json are now archived in `third-party/`**, with SHA-256 in `third-party/MANIFEST.json` and retrieval evidence in `docs/compliance/UPSTREAM_FETCH_EVIDENCE.json`. This is documentary evidence, not completion of bundled-module attribution, Python-native wheel licensing, service terms, or legal review. See [`docs/compliance/RECONCILIATION_REPORT.md`](./docs/compliance/RECONCILIATION_REPORT.md).'
    if old not in notices: raise ValueError('Notice explanatory statement changed; refuse unsafe replace')
    notices=notices.replace(old,new,1)
    changes['THIRD_PARTY_NOTICES.md']=notices.encode('utf-8')

    readme=must_read(root,'third-party/README.md').decode('utf-8')
    readme_rows={
     '| CesiumJS 1.145 |': '| CesiumJS 1.145 | Remote browser CDN, two entrypoints | [`cesium/LICENSE.md`](./cesium/LICENSE.md), [`cesium/ThirdParty.json`](./cesium/ThirdParty.json) | Tagged texts archived; CDN release/bundle notice review pending |',
     '| Deck.gl 9.3.7 |': '| Deck.gl 9.3.7 | Local bundle + remote fallback | [`deck.gl/LICENSE.upstream-v9.3.7`](./deck.gl/LICENSE.upstream-v9.3.7), [`deck.gl/UPSTREAM_NOTICES_STATUS.md`](./deck.gl/UPSTREAM_NOTICES_STATUS.md) | Root license archived; exact bundle notice mapping pending |',
     '| MapLibre 6.9.0 |': '| MapLibre 6.9.0 | Local modules / worker / CSS | [`maplibre-gl/LICENSE.upstream-v6.9.0.txt`](./maplibre-gl/LICENSE.upstream-v6.9.0.txt) | Complete tagged text archived; bundle provenance pending |',
     '| Three.js r185 |': '| Three.js r185 | Local module/core/addons | [`three/LICENSE.upstream-r185`](./three/LICENSE.upstream-r185) | Tagged text archived; vendored artifact mapping pending |',
    }
    for prefix,row in readme_rows.items(): readme=replace_table_row(readme,prefix,row)
    readme=readme.replace('2. Obtain authoritative version-exact source license texts and `NOTICE`/third-party attribution files; archive SHA-256 and tagged upstream source URLs.',
      '2. Check archived version-specific upstream texts in `third-party/` and their SHA-256 in `MANIFEST.json`; obtain any remaining bundle-specific notices after inspecting the actual distributed artifact.')
    changes['third-party/README.md']=readme.encode('utf-8')

    changes['third-party/cesium/README.md']=('''# CesiumJS 1.145 — license evidence (CDN runtime)

- ARCA loads CesiumJS through `https://cesium.com/downloads/cesiumjs/releases/1.145/Build/Cesium/` in two HTML entrypoints.
- [Exact tagged `LICENSE.md`](./LICENSE.md) and [exact tagged `ThirdParty.json`](./ThirdParty.json) were captured by ARCA's upstream fetch tool.
- Exact SHA-256 and original source URLs are recorded in [`third-party/MANIFEST.json`](../MANIFEST.json) and `docs/compliance/UPSTREAM_FETCH_EVIDENCE.json`.
- **Status: `NEEDS_VERIFICATION` for legal attribution coverage of the actual remote Cesium CDN build**. The tagged source-file list is not automatically proof of the compiled distributable's complete obligations.
- Cesium binary is not vendored by ARCA in this snapshot. Do not add full Cesium assets or change runtime paths as part of licensing reconciliation.
- Final human/legal review remains required. Root ARCA `AGPL-3.0-only` is unchanged.
''').encode('utf-8')

    changes['third-party/maplibre-gl/UPSTREAM_NOTICES_STATUS.md']=('''# MapLibre GL JS 6.9.0 — upstream text archived

`third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt` is the full tagged upstream license text retrieved by ARCA's fetch tool and verified against the recorded SHA-256. Keep this complete text, including any inherited attribution; the existing shortened `LICENSE` has deliberately **not** been removed.

Source: https://raw.githubusercontent.com/maplibre/maplibre-gl-js/v6.9.0/LICENSE.txt

**Remaining:** Verify original provenance and license/NOTICE coverage of the exact local JS/MJS/CSS/worker artifacts. Status `NEEDS_VERIFICATION` for binary/bundle attribution until that is done; do not claim complete compliance solely from this text.
''').encode('utf-8')
    changes['third-party/deck.gl/UPSTREAM_NOTICES_STATUS.md']=('''# Deck.gl 9.3.7 — root license archived, bundle audit pending

`third-party/deck.gl/LICENSE.upstream-v9.3.7` is the original tagged project root MIT license captured by ARCA's fetch tool. The existing synopsis `third-party/deck.gl/LICENSE` is retained for comparison, not certified as a full list of bundle attributions.

Source: https://raw.githubusercontent.com/visgl/deck.gl/v9.3.7/LICENSE

**Remaining:** Identify the licensed components inside `src/arca/server/static/vendor/deck.gl-9.3.7.min.js` and the unpkg fallback, including third-party attribution and any Apache-2.0 components where actually present. Status `NEEDS_VERIFICATION` until bundle composition and notices are checked.
''').encode('utf-8')

    csv_text=must_read(root,'docs/compliance/ARCA_LICENSE_REGISTER.csv').decode('utf-8-sig')
    csv_reader=csv.DictReader(io.StringIO(csv_text))
    fields=csv_reader.fieldnames
    if not fields or 'component_name' not in fields: raise ValueError('Unexpected register columns')
    rows=list(csv_reader); revised=0
    for row in rows:
        comp=(row.get('component_name') or '').strip().lower()
        key=comp if comp in ('deck.gl','maplibre-gl','three') else ('cesiumjs' if comp=='cesiumjs' else None)
        if not key: continue
        ev=values[key]
        row['license_file']=ev['path']
        if key=='cesiumjs': row['notice_file']=values['cesiumjs-thirdparty']['path']
        elif not row.get('notice_file'): row['notice_file']='THIRD_PARTY_NOTICES.md'
        # Preserve status NEEDS_VERIFICATION: proven retrieval is not enough for binary audit.
        row['status']='NEEDS_VERIFICATION'
        extra=f"tagged license captured: {ev['path']} SHA256={ev['sha256']}"
        if key=='cesiumjs': extra+=f"; tagged ThirdParty.json SHA256={values['cesiumjs-thirdparty']['sha256']}"
        original=row.get('evidence_reference','')
        if 'tagged license captured:' in original:
            original=original.split('; tagged license captured:')[0]
        row['evidence_reference']=(original+'; '+extra).lstrip('; ')
        row['action_for_programmer']='Validate exact shipped/frontend CDN bundle composition, copyright notices and license completeness; keep original tagged text; human approval before final status'
        revised+=1
    sio=io.StringIO(newline='')
    writer=csv.DictWriter(sio,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    changes['docs/compliance/ARCA_LICENSE_REGISTER.csv']=('\ufeff'+sio.getvalue()).encode('utf-8')
    report=['# ARCA — Upstream License Reconciliation Report','','Generated (UTC): '+timestamp,'','## Verified inputs',
      '- All five upstream files exist and were checked against `UPSTREAM_FETCH_EVIDENCE.json`.','- Four tagged license text SHA-256 values match the originally captured reference digests.','- CesiumJS `ThirdParty.json` is parseable JSON and matches the local fetch evidence hash.',
      f'- {len(vendors)} vendored frontend hashes match `third-party/MANIFEST.json`.','',
      '## Scope of changes','- Only notices, manifest, third-party reference README/status files, license register and this report/evidence are updated.','- No ARCA-owned `LICENSE`, Python/JS runtime, conversion engine, `uv.lock`, or upload/server endpoints modified.',
      f'- {revised} existing register rows updated with tagged evidence; statuses remain `NEEDS_VERIFICATION`.','',
      '## Outstanding (not closed by this reconciliation)',
      '- Confirm exact bundled JS/CSS/worker provenance and transitive notices for MapLibre, Deck.gl, Three.js.',
      '- Verify Cesium notices correspond to the actual Cesium CDN distribution including assets/workers.',
      '- Check exact native Python wheels on supported OS/platforms, and terms for map services and branding.',
      '- Conduct human/legal final review; do not declare full compliance from document retrieval.',
      '', '## Evidence inventory', '', '| ID | File | SHA-256 |', '|---|---|---|']
    for ev in evidence.values(): report.append(f'| {ev["id"]} | `{ev["path"]}` | `{ev["sha256"]}` |')
    changes['docs/compliance/RECONCILIATION_REPORT.md']=('\n'.join(report)+'\n').encode('utf-8')
    changes['docs/compliance/RECONCILIATION_EVIDENCE.json']=(json.dumps({'generated_utc':timestamp,'status':'TAGGED_LICENSE_TEXT_CAPTURED__HUMAN_REVIEW_PENDING','documents':list(evidence.values()),'vendor_hashes_rechecked':len(vendors),'register_rows_revised':revised},indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    return changes,evidence


def main():
    parser=argparse.ArgumentParser(description='Reconcile existing ARCA upstream license evidence (offline and safe)')
    parser.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--apply',action='store_true',help='Make verified changes in ARCA repo; backup originals outside git first')
    args=parser.parse_args(); root=args.repo_root.resolve()
    if not (root/'LICENSE').is_file() or not (root/'pyproject.toml').is_file():
        print('ERROR: not an ARCA repository root:',root,file=sys.stderr);return 2
    try: changes,evidence=reconcile(root)
    except Exception as exc: print('ERROR:',exc,file=sys.stderr);return 1
    modified=[p for p,data in changes.items() if not (root/p).exists() or (root/p).read_bytes()!=data]
    print('PREFLIGHT OK: 5 upstream documents, 10 vendor hashes, fetch evidence coherent.')
    print('Files to write:',len(modified))
    for p in modified:print('  ',p)
    if not args.apply:
        print('DRY RUN only; to apply run: python3 tools/compliance/reconcile_upstream_licenses.py --apply')
        return 0
    backup=Path(tempfile.mkdtemp(prefix='ARCA_LICENSE_BACKUP_'))
    try:
        for rel in modified:
            src=root/rel
            if src.is_file():
                dst=backup/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        for rel in modified:
            dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(changes[rel])
        json.loads((root/'third-party/MANIFEST.json').read_text())
        json.loads((root/'docs/compliance/RECONCILIATION_EVIDENCE.json').read_text())
        print('SUCCESS. Backup of previous files:',backup)
        print('Review with GitHub Desktop before committing. Legal approval remains required.')
    except Exception as exc:
        print('Write failed, restoring original files:',exc,file=sys.stderr)
        for rel in modified:
            original=backup/rel
            if original.is_file(): shutil.copy2(original,root/rel)
            else: (root/rel).unlink(missing_ok=True)
        return 1
    return 0

if __name__=='__main__':sys.exit(main())
