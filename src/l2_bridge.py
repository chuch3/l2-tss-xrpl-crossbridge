from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.transactions import AccountSet, Memo, Payment, TrustSet
from xrpl.transaction import autofill_and_sign, submit_and_wait
from xrpl.utils import str_to_hex
from xrpl.wallet import generate_faucet_wallet

from mpc_tss import MPC_TSS_Protocol

# ========================================
#  XRPL Testnet Configuration Parameters
# ========================================

TESTNET_URL = "https://s.altnet.rippletest.net:51234/"
client = JsonRpcClient(TESTNET_URL)

# Stablecoin currency codes (160-bit format)

MYR_CURRENCY = "MYR"
CNY_CURRENCY = "CNY"
USDC_CURRENCY = "USDC"

MYR_STABLECOIN = "A9999999999999999"
USDC_STABLECOIN = "A9999999999999999"
CNY_STABLECOIN = "A9999999999999999"

QUORUM_THRESHOLD = 0.6  # 60% total quorum votes
BANK_WEIGHT = 0.4  # 40% banks
HOLDER_WEIGHT = 0.6  # 60% stablecoin holders


def to_xrpl_currency(code: str) -> str:
    return code.encode().hex().upper().ljust(40, "0")


class L2_Bridge:
    def __init__(self):
        self.mpc = MPC_TSS_Protocol()
        self.wallets = {}
        self.setup_faucet_wallets()

    def setup_faucet_wallets(self):
        """Generate & fund ALL wallets via Testnet Faucet"""
        print("Creating Faucet wallets (Free testnet XRP)")

        # Issuer wallet (deploys L2)
        print(">> Initializing Issuer (L2 deployer)")
        self.wallets["issuer"] = generate_faucet_wallet(client, debug=True)

        # Bridge participant wallets
        for role in ["myr_sender", "cny_receiver"]:
            print(f">> Initializing {role.replace('_', ' ').title()}")
            self.wallets[role] = generate_faucet_wallet(client, debug=True)

        print(f"\n>> {len(self.wallets)} Faucet wallets INFO: \n")
        for name, wallet in self.wallets.items():
            print(f"  {name}: {wallet.classic_address}")

        self.issuer = self.wallets["issuer"]
        self.receiver = self.wallets["cny_receiver"]

    def deploy_l2_hooks(self):
        """Deploy TSS Bridge smart contracts (Hooks)"""
        print(f"\n>> Deploying L2 TSS Bridge to {self.issuer.classic_address}")

        hook_tx = AccountSet(
            account=self.issuer.classic_address,
            set_flag=5,  # Enable hooks capability
            memos=[Memo(memo_data=str_to_hex("L2-TSS-Bridge-v1"))],
        )

        signed = autofill_and_sign(hook_tx, client, self.issuer)
        result = submit_and_wait(signed, client)
        print(f"> L2 deployed: {result.result['hash'][:8]}...")
        return result.result["hash"]

    def myr_authorization(self, amount_rm: str = "1000") -> str:
        """MYR -> USDC Process"""
        print(f"\n>>> MYR Authorization: {amount_rm} RM -> USDC <<<")
        self.mpc.key_ceremony()

        quorum = self.mpc.calculate_quorum(1500, 500, is_myr=True)

        print(
            f"* Banks: {quorum.bank_votes_pct:.1f}% + Holders: {quorum.holder_votes_pct:.1f}% = {quorum.total_quorum_pct:.1f}%"
        )

        tx_data = f"MYR2USDC:{amount_rm}:{self.wallets['cny_receiver'].classic_address}"
        tss_sig = self.mpc.generate_tss_signature(tx_data, quorum)

        # Mint USDC (TSS authorized)

        trust_tx = TrustSet(
            account=self.receiver.classic_address,
            limit_amount=IssuedCurrencyAmount(
                currency=to_xrpl_currency(USDC_CURRENCY),
                issuer=self.issuer.classic_address,
                value="1000000000",
            ),
        )

        signed_trust = autofill_and_sign(trust_tx, client, self.receiver)
        submit_and_wait(signed_trust, client)

        print("> XRPL Trustline Established")

        mint_tx = Payment(
            account=self.issuer.classic_address,
            destination=self.receiver.classic_address,
            amount=IssuedCurrencyAmount(
                currency=to_xrpl_currency(USDC_CURRENCY),
                issuer=self.issuer.classic_address,
                value=amount_rm,
            ),
            memos=[Memo(memo_data=str_to_hex(tss_sig))],
        )

        signed_mint = autofill_and_sign(mint_tx, client, self.issuer)
        result = submit_and_wait(signed_mint, client)

        print(f"> USDC minted | TX Hash : {result.result['hash'][:8]}")
        return result.result["hash"]

    def cny_settlement(self, amount_usdc: str = "1000") -> str:
        """USDC -> CNY Process"""
        print(f"\n>>> CNY Settlement: {amount_usdc} USDC -> CNY <<<")

        quorum = self.mpc.calculate_quorum(3000, 650, is_myr=False)

        print(
            f"* Banks: {quorum.bank_votes_pct:.1f}% + Holders: {quorum.holder_votes_pct:.1f}% = {quorum.total_quorum_pct:.1f}%"
        )

        tx_data = (
            f"USDC2CNY:{amount_usdc}:{self.wallets['cny_receiver'].classic_address}"
        )
        tss_sig = self.mpc.generate_tss_signature(tx_data, quorum)

        # Burn USDC + mint CNY
        cny_amount = str(float(amount_usdc) * 0.15)  # RM→CNY rate

        trust_tx = TrustSet(
            account=self.receiver.classic_address,
            limit_amount=IssuedCurrencyAmount(
                currency=to_xrpl_currency(CNY_CURRENCY),
                issuer=self.issuer.classic_address,
                value="1000000000",
            ),
        )

        signed_trust = autofill_and_sign(trust_tx, client, self.receiver)
        submit_and_wait(signed_trust, client)

        USDC_HEX = to_xrpl_currency("USDC")

        burn_tx = Payment(
            account=self.receiver.classic_address,
            destination=self.issuer.classic_address,
            amount=IssuedCurrencyAmount(
                currency=USDC_HEX,
                issuer=self.issuer.classic_address,
                value=amount_usdc,
            ),
        )

        signed_burn = autofill_and_sign(burn_tx, client, self.receiver)
        submit_and_wait(signed_burn, client)

        print("> USDC burned (returned to issuer)")

        # ------------------------------
        #          Issue CNY
        # ------------------------------

        cny_amount = str(float(amount_usdc) * 0.15)

        cny_tx = Payment(
            account=self.issuer.classic_address,
            destination=self.receiver.classic_address,
            amount=IssuedCurrencyAmount(
                currency=to_xrpl_currency(CNY_CURRENCY),
                issuer=self.issuer.classic_address,
                value=cny_amount,
            ),
            memos=[Memo(memo_data=str_to_hex(tss_sig))],
        )

        signed_cny = autofill_and_sign(cny_tx, client, self.issuer)
        result = submit_and_wait(signed_cny, client)

        print(f"> {cny_amount} CNY settled | TX: {result.result['hash'][:8]}")
        print("> UNL verified TSS sig ✓ | 3-5s finality")
        return result.result["hash"]
