"""
>> POC L2 MPC-TSS Stablecoin Bridge over XRPL/ODL, XRPL Testnet Faucet Wallet Implementation
- Mock Example with Free Faucet Wallet
- t-of-n 60% quorum: 40% banks + 60% stablecoin holders into a single TSS signature

Reference : [link](https://xrpl.org/docs/tutorials/payments/send-xrp)
"""

from l2_bridge import L2_Bridge

NUM_MYR_BANKS = 1820
NUM_CNY_BANKS = 3800


# ========================================
#               Driver Code
# ========================================


def main():
    print()

    print(
        """
         ▄▄▄▄▄▄▄                           ▄▄ ▄▄▄▄▄▄▄  
        ███▀▀▀▀▀                           ██ ▀▀▀▀████
        ███      ████▄ ▄███▄ ▄█▀▀▀ ▄█▀▀▀   ██    ▄██▀ 
        ███      ██ ▀▀ ██ ██ ▀███▄ ▀███▄   ██  ▄███▄▄▄
        ▀███████ ██    ▀███▀ ▄▄▄█▀ ▄▄▄█▀   ██ ████████ :)
        """
    )

    print("\nPOC L2 MPC-TSS Stablecoin Bridge via Testnet Faucet Wallet")
    print("=" * 80)

    # User input
    RM_AMOUNT = float(input("Enter RM amount to send (e.g. 100): ") or "100")

    # Real-time rates (March 20, 2026)
    MYR_XRP_RATE = 4.67  # MYR per XRP
    XRP_CNY_RATE = 0.312  # CNY per XRP
    XRP_PRICE_MYR = 6.82  # XRP price in MYR ($1.46 × 4.67 MYR/USD)

    # Calculate outputs
    CNY_AMOUNT = (RM_AMOUNT / MYR_XRP_RATE) * XRP_CNY_RATE * 1.002  # 0.2% bridge fee
    TOTAL_DROPS = 36  # 3 tx times 12 drops
    DROP_FEE_MYR = TOTAL_DROPS * (10**6 / 1_000_000_000) * XRP_PRICE_MYR  # drops to MYR

    print(f"\n> Exchange Info : RM{RM_AMOUNT:,.2f} -> CNY{CNY_AMOUNT:,.2f}")
    print(
        f"> Fees: {TOTAL_DROPS} drops (RM{DROP_FEE_MYR:.6f}) from 3 TX (MYR -> USDC -> CNY"
    )
    print("-" * 80)

    bridge = L2_Bridge()

    # 1. Deploy L2 infrastructure
    bridge.deploy_l2_hooks()

    print("-" * 80)

    # 2. MYR -> USDC (Malaysian quorum)
    bridge.myr_authorization(str(RM_AMOUNT))

    print("-" * 80)

    # 3. XRPL UNL validates (no governance control)
    print("> XRPL UNL: TSS signature verified")

    print("-" * 80)

    # 4. USDC -> CNY (Chinese quorum)
    bridge.cny_settlement(str(RM_AMOUNT))

    print("\n[!!] TRANSACTION COMPLETE [!!]")
    print(
        f">> RM {RM_AMOUNT} → CNY{CNY_AMOUNT} | {TOTAL_DROPS} drops with RM {DROP_FEE_MYR:.6f} fee"
    )
    print(
        f">> Mock Quorum Stats : MYR ({NUM_MYR_BANKS} banks 36% + 50% holders) + CNY ({NUM_CNY_BANKS} banks 32% + 65% holders)"
    )
    print(
        f">> Testnet Explorer: https://testnet.xrpl.org/{bridge.wallets['issuer'].classic_address}"
    )


if __name__ == "__main__":
    main()
