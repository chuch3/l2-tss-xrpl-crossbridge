"""
POC L2 MPC-TSS Stablecoin Bridge over XRPL/ODL
Testnet Faucet Wallet Implementation

t-of-n 60% quorum: 40% banks + 60% stablecoin holders → single TSS signature

Reference: https://xrpl.org/docs/tutorials/payments/send-xrp
"""

import logging
import sys

from l2_bridge import L2_Bridge, MYR_TO_XRP, XRP_TO_CNY, BRIDGE_FEE

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

BANNER = r"""
 ▄▄▄▄▄▄▄                           ▄▄ ▄▄▄▄▄▄▄  
███▀▀▀▀▀                           ██ ▀▀▀▀████
███      ████▄ ▄███▄ ▄█▀▀▀ ▄█▀▀▀   ██    ▄██▀ 
███      ██ ▀▀ ██ ██ ▀███▄ ▀███▄   ██  ▄███▄▄▄
▀███████ ██    ▀███▀ ▄▄▄█▀ ▄▄▄█▀   ██ ████████  :)
"""


def print_step(step: str, message: str) -> None:
    print(f"  [{step:12s}] {message}")


def main() -> None:
    print(BANNER)
    print("POC L2 MPC-TSS Stablecoin Bridge — XRPL Testnet")
    print("=" * 72)

    # Input
    try:
        raw = input("\nEnter RM amount to bridge (default 100): ").strip()
        amount_myr = float(raw) if raw else 100.0
        if amount_myr <= 0:
            raise ValueError
    except ValueError:
        print("Invalid amount. Using 100 RM.")
        amount_myr = 100.0

    # Preview exchange info
    cny_preview = amount_myr * (1 / MYR_TO_XRP) * XRP_TO_CNY * (1 - BRIDGE_FEE)
    print(f"\n  Exchange : RM{amount_myr:,.2f}  →  CNY{cny_preview:,.4f}")
    print(f"  Fee      : {BRIDGE_FEE*100:.1f}% bridge fee")
    print(f"  Route    : MYR → USDC → CNY  (via XRPL)")
    print("-" * 72)

    bridge = L2_Bridge(callback=print_step)

    try:
        result = bridge.run_full_bridge(amount_myr)
    except Exception as exc:
        print(f"\n[ERROR] Bridge failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 72)
    print("[!!] TRANSACTION COMPLETE [!!]")
    print(f"  RM{result['myr_amount']:,.2f}  →  CNY{result['cny_amount']:,.4f}")
    print(f"  Deploy TX : {result['deploy_hash'][:24]}…")
    print(f"  MYR TX    : {result['myr_tx_hash'][:24]}…")
    print(f"  CNY TX    : {result['cny_tx_hash'][:24]}…")
    print(f"  Explorer  : {result['explorer_url']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
