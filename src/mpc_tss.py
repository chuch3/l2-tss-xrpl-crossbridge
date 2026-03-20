import hashlib
from dataclasses import dataclass
from typing import Dict, List

from cryptography.hazmat.primitives import hashes
from ecdsa import SECP256k1, SigningKey

QUORUM_THRESHOLD = 0.6  # 60% total quorum votes
BANK_WEIGHT = 0.4  # 40% banks
HOLDER_WEIGHT = 0.6  # 60% stablecoin holders


@dataclass
class QuorumResult:
    bank_votes_pct: float
    holder_votes_pct: float
    total_quorum_pct: float
    approved: bool


class TSSKeyShare:
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.private_share = SigningKey.generate(curve=SECP256k1)

    def sign_partial(self, message_hash: bytes) -> bytes:
        return self.private_share.sign(message_hash)


class MPC_TSS_Protocol:
    def __init__(self):
        self.key_shares: List[TSSKeyShare] = []
        self.malaysian_banks: Dict[str, TSSKeyShare] = {}
        self.chinese_banks: Dict[str, TSSKeyShare] = {}
        self.myr_holders: Dict[str, TSSKeyShare] = {}
        self.cny_holders: Dict[str, TSSKeyShare] = {}

    def key_ceremony(self):
        """MPC Key Ceremony with FAUCET wallets"""
        print("> MPC-TSS Key Ceremony")

        # Malaysian banks (fixed 1820 total simulated) (adjustable)
        malaysian_banks = ["Maybank", "CIMB", "Public", "RHB"] * 455
        for i, bank in enumerate(malaysian_banks):
            share = TSSKeyShare(f"MYR_BNK_{bank}_{i}")
            self.malaysian_banks[bank + str(i)] = share
            self.key_shares.append(share)

        # Chinese banks (3800 total simulated) (adjustable)
        chinese_banks = ["ICBC", "ABC", "BOC", "CCB"] * 950
        for i, bank in enumerate(chinese_banks):
            share = TSSKeyShare(f"CNY_BNK_{bank}_{i}")
            self.chinese_banks[bank + str(i)] = share
            self.key_shares.append(share)

        print(f">> {len(self.key_shares)} key shares distributed | 60% threshold")

    def calculate_quorum(
        self, bank_votes: int, holder_votes: int, is_myr: bool
    ) -> QuorumResult:
        """t-of-n: 40% banks + 60% holders = 60% total"""
        total_holders = 1000  # Mock holder count
        if is_myr:
            total_banks = len(self.malaysian_banks)
        else:
            total_banks = len(self.chinese_banks)

        bank_pct = (bank_votes / total_banks) * 100
        holder_pct = (holder_votes / total_holders) * 100
        total_quorum = bank_pct * BANK_WEIGHT + holder_pct * HOLDER_WEIGHT

        return QuorumResult(bank_pct, holder_pct, total_quorum, total_quorum >= 60)

    def generate_tss_signature(self, tx_hash: str, quorum: QuorumResult) -> str:
        if not quorum.approved:
            raise ValueError(f"Quorum failed: {quorum.total_quorum_pct:.1f}%")

        message_hash = hashes.Hash(hashes.SHA256())
        message_hash.update(tx_hash.encode())
        msg_digest = message_hash.finalize()

        partial_sigs = []
        if quorum.bank_votes_pct >= 40:
            for share in list(self.malaysian_banks.values())[:5]:
                partial_sigs.append(share.sign_partial(msg_digest))
        if quorum.holder_votes_pct >= 60:
            for share in (
                list(self.myr_holders.values())[:10]
                if hasattr(self, "myr_holders")
                else []
            ):
                partial_sigs.append(share.sign_partial(msg_digest))

        sig_hash = hashlib.sha256(b"".join(p for p in partial_sigs)).hexdigest()
        print(
            f"TSS signature: {len(partial_sigs)} partials for 1 private key signature"
        )
        return sig_hash
