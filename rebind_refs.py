import json, re, sys

SUM = 'certification/results/UI_LCC_8of53_t_41f3d95a.json'
PRB = 'certification/results/UI_LCC_8of53_t_41f3d95a_probes.json'
PREF = PRB + '#'

probes = json.load(open(PRB, encoding='utf-8'))
summary = json.load(open(SUM, encoding='utf-8'))

TOK = re.compile(r'([^.\[]+)|\[(\d+)\]')

def resolve(path):
    cur = probes
    for name, idx in TOK.findall(path):
        if name:
            cur = cur[name]
        else:
            cur = cur[int(idx)]
    return cur

R = {}

R['UI-LCC-CARD-02'] = dict(
  verdict='PASS',
  keys=['probe3.card_mutation.A[1]','probe3.card_mutation.B[1]',
        'card_probe.all_unavailable.cards[1]'],
  why='Real Account card cell "Open positions P&L (unrealised)" tracks the unrealised-PnL payload in the executed DOM: mutation A (123.45) renders "$123.45" (probe3.card_mutation.A[1]) and mutation B (-1.5) renders "$-1.5" (probe3.card_mutation.B[1]); flipping only that field moves only this cell. Unavailable source degrades to an em-dash, not a numeric 0 (card_probe.all_unavailable.cards[1]). Scope note: the literal fallback token observed is an em-dash, not the string "n/a"; a title/aria explanation of unavailability was NOT captured by this probe and is not claimed here.')

R['UI-LCC-CARD-03'] = dict(
  verdict='PASS',
  keys=['probe3.card_mutation.A[2]','probe3.card_mutation.B[2]',
        'card_probe.all_unavailable.cards[2]'],
  why='Card "Closed P&L (realised)" tracks the realised-PnL payload with a since-timestamp suffix: A (-42.0) renders "$-42.00 since 2023-11-14T22:13:20.000Z" (probe3.card_mutation.A[2]) and B (11.0) renders "$11.00 since ..." (probe3.card_mutation.B[2]). Unavailable source degrades to an em-dash (card_probe.all_unavailable.cards[2]). Row-bound: the mutation that moved this cell is the closed-P&L field, independent of the unrealised cell above.')

R['UI-LCC-CARD-04'] = dict(
  verdict='PASS',
  keys=['probe3.card_mutation.A[3]','probe3.card_mutation.B[3]',
        'card_probe.all_unavailable.cards[3]'],
  why='Card "Open Positions" tracks position-list cardinality: mutation A (2 positions) renders "2" (probe3.card_mutation.A[3]) and mutation B (empty list) renders "0" (probe3.card_mutation.B[3]). A genuine zero from an empty-but-available list is distinguishable from an unavailable source, which renders an em-dash (card_probe.all_unavailable.cards[3]). Row-bound by cardinality alone.')

R['UI-LCC-CARD-05'] = dict(
  verdict='FAIL',
  keys=['card_probe.all_unavailable.cards[4]','card_probe.all_unavailable.cards[0]',
        'card_probe.with_data.cards[4]','probe3.card_mutation.B[4]'],
  why='Executed DOM proves the false-zero defect the row forbids: with every source unavailable, all four sibling cards degrade to an em-dash (e.g. card_probe.all_unavailable.cards[0].value = em-dash) while "Live Exposure" still renders "$0" (card_probe.all_unavailable.cards[4]) - a fabricated numeric zero, not an honest unavailable state. The card value does move with the manual payload (with_data "$777", mutation B "$3"), and the rendered label is the bare string "Live Exposure" with no manual-estimate qualifier (card_probe.with_data.cards[4].label). Secondary, NOT probe-derived: a source read of the rendering path shows the value is manual_live_exposure_estimate defaulted with ||0; that provenance is recorded as source-read context only and is not counted as probe evidence here.')

R['UI-LCC-CARD-06'] = dict(
  verdict='FAIL',
  keys=['probe3.card_labels_contain_lastfill_lastreject.has_last_fill',
        'probe3.card_labels_contain_lastfill_lastreject.text',
        'probe5.status.with_data[5]','probe5.status.empty[5]'],
  why='The specified Last Fill card does not exist: the rendered Real Account card container has has_last_fill=false and its full text enumerates only five labels (Portfolio Value, Open positions P&L, Closed P&L, Open Positions, Live Exposure) - probe3.card_labels_contain_lastfill_lastreject. The value is not lost, it is relocated: the status strip renders "Last fill=BTC B 0.5" with data (probe5.status.with_data[5]) and degrades to an em-dash when absent (probe5.status.empty[5]). FAIL is on the specified card existing, not on data availability.')

R['UI-LCC-CARD-07'] = dict(
  verdict='FAIL',
  keys=['probe3.card_labels_contain_lastfill_lastreject.has_last_reject',
        'probe3.card_labels_contain_lastfill_lastreject.text',
        'probe5.status.with_data[6]','probe5.status.empty[6]'],
  why='Same defect class as CARD-06: no Last Reject card in the Real Account card container (has_last_reject=false, and the enumerated label text contains no such card) - probe3.card_labels_contain_lastfill_lastreject. The value exists only in the status strip: "Last reject=DOGE IOC_NO_IMMEDIATE_MATCH" (probe5.status.with_data[6]), em-dash when absent (probe5.status.empty[6]).')

R['UI-LCC-GRAPH-01'] = dict(
  verdict='PASS',
  keys=['probe3.graph_behavior.account_subtitle','probe3.graph_behavior.wallet_subtitle',
        'probe3.graph_behavior.exposure_subtitle','dom_probe.btn_mode_account'],
  why='Account mode is proven by its own rendered subtitle "Exchange account graph. ALL range - 2 portfolio pts, 0 realized fills." (probe3.graph_behavior.account_subtitle), which is distinct from the wallet-PnL and exposure subtitles produced in the same run (probe3.graph_behavior.wallet_subtitle / .exposure_subtitle) - so the three modes are not aliases of one another. The control ships in the executed DOM as a button labelled "Account" (dom_probe.btn_mode_account). Scope note: extra series beyond the subtitle text (e.g. realised-PnL/drawdown traces) were NOT captured by this probe and are not claimed.')

R['UI-LCC-GRAPH-02'] = dict(
  verdict='PASS',
  keys=['probe3.graph_behavior.wallet_subtitle','probe3.graph_behavior.account_subtitle',
        'probe3.graph_behavior.exposure_subtitle','dom_probe.btn_mode_wallet_pnl'],
  why='Selected-wallet PnL mode renders its own subtitle "Selected wallet live PnL. ALL range, 2 live data points." (probe3.graph_behavior.wallet_subtitle), distinct from the account and exposure subtitles in the same executed run, so the mode is not an alias. Control present in DOM: button "Selected Wallet PnL" (dom_probe.btn_mode_wallet_pnl).')

R['UI-LCC-GRAPH-03'] = dict(
  verdict='PASS',
  keys=['probe3.graph_behavior.exposure_subtitle','probe3.graph_behavior.wallet_subtitle',
        'dom_probe.btn_mode_exposure'],
  why='Exposure mode renders its own subtitle "Selected wallet exposure. ALL range, 2 live data points." (probe3.graph_behavior.exposure_subtitle), distinct from the wallet-PnL subtitle in the same run, so the mode is genuinely separate. Control present in DOM: button "Exposure" (dom_probe.btn_mode_exposure). Scope note: a separate no-wallet-selected empty message was NOT captured by this probe (the only empty-state string recorded is probe3.graph_behavior.empty_subtitle for the generic no-points case) and is not claimed.')

R['UI-LCC-GRAPH-04'] = dict(
  verdict='PASS',
  keys=['probe3.scale_filter.all','probe3.scale_filter.d7','probe3.scale_filter.d1',
        'dom_probe.btn_scale_1d'],
  why='1D scale is load-bearing on one fixed dataset: ALL range reports 4 live data points, 7D reports 3, and 1D reports "Not enough points in selected range (1D)." (probe3.scale_filter.all / .d7 / .d1). Three different outcomes from one series proves the scale selection actually filters. Control present in DOM: button "1D" (dom_probe.btn_scale_1d).')

R['UI-LCC-GRAPH-05'] = dict(
  verdict='PASS',
  keys=['probe3.scale_filter.d7','probe3.scale_filter.all','dom_probe.btn_scale_7d'],
  why='7D window filters independently: same dataset gives 3 live data points under 7D versus 4 under ALL (probe3.scale_filter.d7 vs .all), so the 7D boundary removes a point rather than being decorative. Control present in DOM: button "7D" (dom_probe.btn_scale_7d).')

R['UI-LCC-GRAPH-06'] = dict(
  verdict='PASS',
  keys=['dom_probe.btn_scale_all','probe3.scale_filter.all','probe3.scale_filter.d7',
        'probe3.scale_filter.d1'],
  why='ALL disables range filtering: the same series reports 4 live data points under ALL while 7D gives 3 and 1D gives 0 (probe3.scale_filter.all / .d7 / .d1). Control present in DOM: button "ALL" (dom_probe.btn_scale_all).')

R['UI-LCC-GRAPH-07'] = dict(
  verdict='PASS',
  keys=['probe4.range_wiring.after_start_apply','probe4.range_wiring.all',
        'dom_probe.el_lcGraphStart','dom_probe.el_lcGraphApplyRange'],
  why='Start datetime is a real, wired control. The executed DOM contains a datetime-local input (dom_probe.el_lcGraphStart) and an Apply button (dom_probe.el_lcGraphApplyRange). Setting the start value and clicking Apply changed the rendered range window from "ALL range" to "05/06/2026, 00:00:00 to now" (probe4.range_wiring.after_start_apply vs .all) - the window text is driven by THIS input. Honest scope: for that window the chart reported "Not enough points in selected range", so this probe proves the start control drives the range window; it does not by itself prove a populated refilter, which the mutation control in UI-LCC-GRAPH-09 does establish.')

R['UI-LCC-GRAPH-08'] = dict(
  verdict='PASS',
  keys=['probe4.range_wiring.after_end_apply','probe4.range_wiring.after_start_apply',
        'dom_probe.el_lcGraphEnd'],
  why='End datetime is wired: with the start already applied, setting the end value and applying produced the bounded window "05/06/2026, 00:00:00 to 07/06/2026, 00:00:00" (probe4.range_wiring.after_end_apply) instead of the open-ended "... to now" (probe4.range_wiring.after_start_apply). The end boundary is exactly what changed the window text. Control present in DOM: datetime-local input (dom_probe.el_lcGraphEnd). Honest scope: that bounded window returned "Not enough points", so a populated bounded series is not claimed.')

R['UI-LCC-GRAPH-09'] = dict(
  verdict='PASS',
  keys=['probe3.apply_click.clicked','probe3.apply_click.subtitle',
        'probe4.range_mutation_control.real','probe4.range_mutation_control.mutant',
        'probe4.range_mutation_control.differs'],
  why='Apply is a live handler, not an inert button: an executed click registered (probe3.apply_click.clicked=true) and the graph re-rendered to the new range state, changing the subtitle to a start-to-now window (probe3.apply_click.subtitle). The range filter it drives is load-bearing, proven by a mutation control on a fixed custom window: real filter yields 3 live data points, identity-replacement mutant yields 10, differs=true (probe4.range_mutation_control.real / .mutant / .differs).')

rows = summary['rows']
seen = set()
errors = []
for row in rows:
    rid = row['row_id']
    if rid not in R:
        errors.append('no rebind for ' + rid)
        continue
    seen.add(rid)
    spec = R[rid]
    if spec['verdict'] != row['verdict']:
        errors.append('verdict drift ' + rid)
    for k in spec['keys']:
        try:
            v = resolve(k)
        except Exception as e:
            errors.append('%s unresolved %s (%s)' % (rid, k, e))
            continue
        if v is None:
            errors.append('%s null at %s' % (rid, k))
    row['verdict'] = spec['verdict']
    row['evidence_ref'] = PREF + spec['keys'][0]
    row['evidence_keys'] = spec['keys']
    row['evidence_artifact'] = PRB
    row['why'] = spec['why']

summary['evidence_ref_convention'] = 'evidence_ref = certification/results/UI_LCC_8of53_t_41f3d95a_probes.json#<json path>; evidence_keys lists every probe location the row relies on. Every path is resolvable in the committed probes artifact (verified by rebind_refs.py resolve()).'
summary['evidence_refs_rebound_at_utc'] = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
summary['evidence_refs_rebound_by_task'] = 't_c4fc4465'
summary['probe_caveats'] = [
  'dom_probe.renderCards_executed.err = ReferenceError: renderCards is not defined - one in-page invocation attempt failed, so no row claims "executed renderCards()"; card claims cite the rendered card DOM (card_probe.with_data / .all_unavailable) instead.',
  'CARD-02 fallback token is an em-dash, not the literal string "n/a"; no aria/title explanation is captured.',
  'GRAPH-03 no-wallet empty message not captured by the probe; only the generic no-points string exists.',
  'GRAPH-07/08 prove the range inputs drive the window text; the windows probed returned "Not enough points", so populated series are not claimed (GRAPH-09 mutation control covers filter load-bearing).',
  'CARD-05 manual-estimate provenance comes from a source read, not the probe; the probe proves the false "$0" and the unqualified label.'
]

if errors:
    print('ERRORS')
    for e in errors:
        print(' -', e)
    sys.exit(1)

assert seen == {r['row_id'] for r in rows}
json.dump(summary, open(SUM, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
open(SUM, 'a', encoding='utf-8').write('\n')
print('OK rows=', len(rows), 'refs_resolved=', sum(len(r['evidence_keys']) for r in rows))
print('verdicts=', {v: sum(1 for r in rows if r['verdict']==v) for v in ('PASS','FAIL')})
