"""
MPC-TSS Protocol Implementation
Threshold Signature Scheme for MYR<->CNY cross-border stablecoin bridge.
t-of-n: 40% banks + 60% holders >= 60% total quorum to authorize.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cryptography.hazmat.primitives import hashes
from ecdsa import SECP256k1, SigningKey

logger = logging.getLogger(__name__)

# Governance weights
QUORUM_THRESHOLD = 60.0  # 60% total quorum required
BANK_WEIGHT = 0.40       # Banks contribute 40% of vote
HOLDER_WEIGHT = 0.60     # Holders contribute 60% of vote


@dataclass
class QuorumResult:
    bank_votes: int
    holder_votes: int
    total_banks: int
    total_holders: int
    bank_votes_pct: float        # raw % of banks that voted
    holder_votes_pct: float      # raw % of holders that voted
    weighted_bank_pct: float     # bank_votes_pct * BANK_WEIGHT
    weighted_holder_pct: float   # holder_votes_pct * HOLDER_WEIGHT
    total_quorum_pct: float      # sum of weighted contributions
    approved: bool
    side: str                    # "MYR" or "CNY"

    def summary(self) -> str:
        status = "✅ APPROVED" if self.approved else "❌ REJECTED"
        return (
            f"[{self.side} Quorum] {status} | "
            f"Banks: {self.bank_votes}/{self.total_banks} "
            f"({self.bank_votes_pct:.1f}% × {BANK_WEIGHT:.0%} = {self.weighted_bank_pct:.1f}%) + "
            f"Holders: {self.holder_votes}/{self.total_holders} "
            f"({self.holder_votes_pct:.1f}% × {HOLDER_WEIGHT:.0%} = {self.weighted_holder_pct:.1f}%) "
            f"= {self.total_quorum_pct:.1f}% (threshold: {QUORUM_THRESHOLD:.0f}%)"
        )


class TSSKeyShare:
    """A single participant's key share in the TSS ceremony."""

    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self._private_share = SigningKey.generate(curve=SECP256k1)
        self.public_key = self._private_share.get_verifying_key()

    def sign_partial(self, message_hash: bytes) -> bytes:
        """Sign a message hash with this participant's key share."""
        return self._private_share.sign(message_hash)


class MPC_TSS_Protocol:
    """
    Multi-Party Computation Threshold Signature Scheme.

    Banks participate in a key ceremony to generate distributed key shares.
    A t-of-n threshold of 60% (40% banks + 60% holders) is required to
    produce a valid aggregate TSS signature.
    """

    def __init__(self):
        self.malaysian_banks: Dict[str, TSSKeyShare] = {}
        self.chinese_banks: Dict[str, TSSKeyShare] = {}
        self.myr_holders: Dict[str, TSSKeyShare] = {}   # mock stablecoin holders
        self.cny_holders: Dict[str, TSSKeyShare] = {}
        self._ceremony_done = False

    def key_ceremony(
        self,
        num_myr_banks: int = 1820,
        num_cny_banks: int = 3800,
        num_holders_per_side: int = 1000,
    ) -> None:
        """
        MPC Key Ceremony: distribute key shares among all participants.

        In production, this uses Distributed Key Generation (DKG) so that
        no single party ever holds the full private key.
        """
        if self._ceremony_done:
            logger.debug("Key ceremony already completed — skipping.")
            return

        logger.info("Starting MPC-TSS Key Ceremony…")

        bank_names_myr = ["Maybank", "CIMB", "PublicBank", "RHB"]
        bank_names_cny = ["ICBC", "ABC", "BOC", "CCB"]

        # Malaysian banks
        for i in range(num_myr_banks):
            name = bank_names_myr[i % len(bank_names_myr)]
            key = f"{name}_{i}"
            self.malaysian_banks[key] = TSSKeyShare(f"MYR_BNK_{key}")

        # Chinese banks
        for i in range(num_cny_banks):
            name = bank_names_cny[i % len(bank_names_cny)]
            key = f"{name}_{i}"
            self.chinese_banks[key] = TSSKeyShare(f"CNY_BNK_{key}")

        # Mock stablecoin holder key shares (representative sample)
        for i in range(num_holders_per_side):
            self.myr_holders[f"MYR_HOLDER_{i}"] = TSSKeyShare(f"MYR_HLD_{i}")
            self.cny_holders[f"CNY_HOLDER_{i}"] = TSSKeyShare(f"CNY_HLD_{i}")

        total = (
            len(self.malaysian_banks) + len(self.chinese_banks)
            + len(self.myr_holders) + len(self.cny_holders)
        )
        logger.info(
            f"Key ceremony complete: {total} shares distributed "
            f"(MYR banks={len(self.malaysian_banks)}, CNY banks={len(self.chinese_banks)}, "
            f"MYR holders={len(self.myr_holders)}, CNY holders={len(self.cny_holders)})"
        )
        self._ceremony_done = True

    def calculate_quorum(
        self,
        bank_votes: int,
        holder_votes: int,
        side: str,
        total_holders: int = 1000,
    ) -> QuorumResult:
        """
        Compute weighted quorum result.

        Total quorum = (bank_votes% × 40%) + (holder_votes% × 60%)
        Threshold = 60%
        """
        if side.upper() == "MYR":
            total_banks = len(self.malaysian_banks)
        else:
            total_banks = len(self.chinese_banks)

        if total_banks == 0:
            raise RuntimeError("Key ceremony has not been run yet.")

        bank_votes = min(bank_votes, total_banks)
        holder_votes = min(holder_votes, total_holders)

        bank_pct = (bank_votes / total_banks) * 100.0
        holder_pct = (holder_votes / total_holders) * 100.0

        weighted_bank = bank_pct * BANK_WEIGHT
        weighted_holder = holder_pct * HOLDER_WEIGHT
        total_quorum = weighted_bank + weighted_holder

        return QuorumResult(
            bank_votes=bank_votes,
            holder_votes=holder_votes,
            total_banks=total_banks,
            total_holders=total_holders,
            bank_votes_pct=bank_pct,
            holder_votes_pct=holder_pct,
            weighted_bank_pct=weighted_bank,
            weighted_holder_pct=weighted_holder,
            total_quorum_pct=total_quorum,
            approved=total_quorum >= QUORUM_THRESHOLD,
            side=side.upper(),
        )

    def generate_tss_signature(
        self,
        tx_hash: str,
        quorum: QuorumResult,
        num_signing_banks: int = 5,
        num_signing_holders: int = 10,
    ) -> str:
        """
        Aggregate partial signatures into a single TSS signature.

        In a real implementation this uses Schnorr or FROST aggregation.
        Here we hash the concatenation of partial signatures as a mock.

        Raises ValueError if quorum not approved.
        """
        if not quorum.approved:
            raise ValueError(
                f"Quorum not reached for {quorum.side}: "
                f"{quorum.total_quorum_pct:.1f}% < {QUORUM_THRESHOLD:.0f}%"
            )

        # Hash the transaction data
        h = hashes.Hash(hashes.SHA256())
        h.update(tx_hash.encode("utf-8"))
        msg_digest = h.finalize()

        partial_sigs: List[bytes] = []

        # Select signing participants based on side
        if quorum.side == "MYR":
            bank_pool = list(self.malaysian_banks.values())
            holder_pool = list(self.myr_holders.values())
        else:
            bank_pool = list(self.chinese_banks.values())
            holder_pool = list(self.cny_holders.values())

        for share in bank_pool[:num_signing_banks]:
            partial_sigs.append(share.sign_partial(msg_digest))

        for share in holder_pool[:num_signing_holders]:
            partial_sigs.append(share.sign_partial(msg_digest))

        if not partial_sigs:
            raise RuntimeError("No signing participants available.")

        # Mock aggregation: SHA-256 over all partial signatures
        aggregated = hashlib.sha256(b"".join(partial_sigs)).hexdigest()
        logger.info(
            f"TSS signature generated: {len(partial_sigs)} partial sigs aggregated "
            f"({num_signing_banks} banks + {num_signing_holders} holders)"
        )
        return aggregated
