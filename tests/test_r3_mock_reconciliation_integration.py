"""R3 simulated authenticated evidence and historical reconciliation, not production replay."""
import pytest

class MockReplay:
    def __init__(self, network, account, dex):
        self.network, self.account, self.dex = network, account, dex
    def reconcile(self, sends, confirmations, ledger):
        if self.network != "testnet":
            raise RuntimeError("TESTNET_ONLY")
        if len(sends) != 2199 or len({s['attempt'] for s in sends}) != len(sends):
            raise RuntimeError("HISTORY_INCOMPLETE_OR_DUPLICATE")
        confirmed = {(c['attempt'], c['leader_fill']): c for c in confirmations
                     if c['account'] == self.account and c['dex'] == self.dex and c['network'] == self.network}
        covered = {(x['attempt'], x['leader_fill']) for x in ledger}
        if any((s['attempt'], s['leader_fill']) not in confirmed or
               (s['attempt'], s['leader_fill']) not in covered for s in sends):
            raise RuntimeError("UNRESOLVED_OR_UNAUTHENTICATED")
        return len(sends)

def history():
    sends = [{'attempt': str(i), 'leader_fill': f'L{i}'} for i in range(2199)]
    confirmations = [dict(s, network='testnet', account='acct-A', dex='dex-A') for s in sends]
    ledger = [dict(s) for s in sends]
    return sends, confirmations, ledger

def test_exact_2199_rows_authenticated_and_complete():
    assert MockReplay('testnet','acct-A','dex-A').reconcile(*history()) == 2199

def test_mainnet_is_denied_before_reconciliation():
    with pytest.raises(RuntimeError, match='TESTNET_ONLY'):
        MockReplay('mainnet','acct-A','dex-A').reconcile(*history())

def test_foreign_account_or_dex_rejected_not_reconciled():
    for attr in ('account', 'dex'):
        sends, confirmations, ledger = history()
        confirmations[20][attr] = 'foreign'
        with pytest.raises(RuntimeError, match='UNRESOLVED_OR_UNAUTHENTICATED'):
            MockReplay('testnet','acct-A','dex-A').reconcile(sends, confirmations, ledger)

def test_one_missing_leader_fill_denies_whole_history():
    sends, confirmations, ledger = history()
    ledger.pop(72)
    with pytest.raises(RuntimeError, match='UNRESOLVED_OR_UNAUTHENTICATED'):
        MockReplay('testnet','acct-A','dex-A').reconcile(sends, confirmations, ledger)
