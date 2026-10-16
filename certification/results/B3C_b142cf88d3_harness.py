import json,pathlib,sys
d=json.loads(pathlib.Path(__file__).with_name('B3C_'+sys.argv[1]+'.json').read_text())
assert d['overall_result']=='NOT_TESTED' and len(d['checks'])==6
assert all(r['result']=='NOT_TESTED' and len(r['negative_tests'])==4 for r in d['checks'])
print('STRUCTURE PASS: six explicit NOT_TESTED rows')
