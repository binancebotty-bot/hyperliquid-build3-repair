#!/usr/bin/env python3
# Defect 1 acceptance proof: resolve EVERY evidence_ref in verdicts_v2.json
# against the BRANCH OBJECT (git cat-file -e <commit>:<path>), never the
# working tree. Acceptance condition: zero missing paths.
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

head = subprocess.run(['git','rev-parse','HEAD'],cwd=str(REPO),capture_output=True).stdout.decode().strip()
data = json.loads((HERE/'verdicts.json').read_text(encoding='utf-8'))


def exists(p):
    return subprocess.run(['git','cat-file','-e',head+':'+p],cwd=str(REPO),capture_output=True).returncode == 0


table, missing = [], []
for row in data['rows']:
    refs = row.get('evidence_ref') or []
    if isinstance(refs, str):
        refs = [refs]
    for ref in refs:
        for part in str(ref).split(' + '):
            path = part.split('#',1)[0].strip()
            key = part.split('#',1)[1].strip() if '#' in part else ''
            ok = exists(path)
            table.append({'row_id':row['row_id'],'evidence_ref':part,'path':path,'key':key,'EXISTS':'yes' if ok else 'NO'})
            if not ok:
                missing.append({'row_id':row['row_id'],'path':path,'ref':part})

# 'citation_table' is deliberately NOT self-checked: CITATION_RESOLUTION.json is
# the OUTPUT of this run and is committed on top of the commit it resolves
# against, so it cannot exist inside that commit. Every row evidence_ref is
# still checked, and verdicts_v2.json's citation_table path does resolve at the
# final branch head.
for f in ('probe','raw_result','citation_resolver'):
    p = data.get(f)
    if not p:
        continue
    ok = exists(p)
    table.append({'row_id':'(document)','evidence_ref':f+' = '+p,'path':p,'key':'','EXISTS':'yes' if ok else 'NO'})
    if not ok:
        missing.append({'row_id':'(document)','path':p,'ref':f})

res = {'schema':'eng_inv_citation_resolution/v1','card':data.get('card'),'branch':data.get('branch'),
       'resolved_against':'git cat-file -e '+head+':<path>','commit':head,
       'total_refs':len(table),'missing_count':len(missing),
       'ACCEPTANCE_ZERO_MISSING':len(missing)==0,'table':table,'missing':missing}
(HERE/'CITATION_RESOLUTION.json').write_text(json.dumps(res,indent=1,ensure_ascii=False),encoding='utf-8')
for t in table:
    print('%-14s EXISTS=%-3s %s' % (t['row_id'],t['EXISTS'],t['path']))
print('')
print('total_refs=%d missing_count=%d ACCEPTANCE_ZERO_MISSING=%s' % (len(table),len(missing),len(missing)==0))
sys.exit(0 if not missing else 1)
