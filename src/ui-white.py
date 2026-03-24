"""
ui.py – Streamlit interface for the L2 MPC-TSS Stablecoin Bridge (XRPL Testnet)

Run with:
    streamlit run ui.py
"""

import queue
import threading
import time

import streamlit as st

from l2_bridge import (
    BRIDGE_FEE,
    MYR_TO_XRP,
    NUM_CNY_BANKS,
    NUM_HOLDERS,
    NUM_MYR_BANKS,
    XRP_TO_CNY,
    L2_Bridge,
)
from mpc_tss import QUORUM_THRESHOLD

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CrossL2 | MPC-TSS Bridge",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styles ───────────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}

/* Dark background */
.stApp { background: #0a0e1a; color: #e8eaf6; }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #111827 0%, #1a2035 100%);
    border: 1px solid #2a3a5e;
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
}
.metric-card .label {
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #6b7db3;
    margin-bottom: 6px;
}
.metric-card .value {
    font-family: 'Space Mono', monospace;
    font-size: 26px;
    font-weight: 700;
    color: #7ee8fa;
}
.metric-card .sub {
    font-size: 12px;
    color: #4a5a80;
    margin-top: 4px;
}

/* Quorum gauge */
.quorum-bar-wrapper {
    background: #111827;
    border: 1px solid #2a3a5e;
    border-radius: 12px;
    padding: 18px 22px 14px;
    margin-bottom: 12px;
}
.quorum-title { font-size: 12px; letter-spacing: 2px; color: #6b7db3; text-transform: uppercase; margin-bottom: 10px; }
.quorum-bar-track {
    background: #1e2a42;
    border-radius: 999px;
    height: 14px;
    position: relative;
    overflow: hidden;
}
.quorum-bar-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.8s ease;
}
.quorum-bar-fill.approved { background: linear-gradient(90deg, #00e676, #69f0ae); }
.quorum-bar-fill.pending  { background: linear-gradient(90deg, #ffa726, #ffca28); }
.quorum-bar-fill.rejected { background: linear-gradient(90deg, #ef5350, #e57373); }
.quorum-pct { font-family: 'Space Mono', monospace; font-size: 13px; color: #7ee8fa; margin-top: 6px; }

/* Log panel */
.log-panel {
    background: #080c18;
    border: 1px solid #1e2a42;
    border-radius: 10px;
    padding: 16px 18px;
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: #a0aec0;
    height: 340px;
    overflow-y: auto;
}
.log-line { margin: 2px 0; line-height: 1.6; }
.log-line.KEY_CEREMONY { color: #b388ff; }
.log-line.L2_DEPLOY    { color: #80cbc4; }
.log-line.MYR_AUTH     { color: #ffcc02; }
.log-line.CNY_SETTLE   { color: #69f0ae; }
.log-line.UNL          { color: #7ee8fa; }
.log-line.SETUP        { color: #90caf9; }
.log-line.ERROR        { color: #ef9a9a; }
.log-ts { color: #2d3748; margin-right: 6px; }

/* Step tracker */
.step-row { display: flex; align-items: center; gap: 12px; margin: 8px 0; }
.step-dot {
    width: 12px; height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}
.step-dot.done    { background: #00e676; box-shadow: 0 0 6px #00e676; }
.step-dot.active  { background: #ffca28; box-shadow: 0 0 8px #ffca28; animation: pulse 1s infinite; }
.step-dot.waiting { background: #2a3a5e; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.step-label { font-size: 13px; color: #8a9bc0; }
.step-label.done { color: #e8eaf6; }

/* Tx hash chip */
.tx-chip {
    background: #111827;
    border: 1px solid #2a3a5e;
    border-radius: 6px;
    padding: 6px 12px;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #7ee8fa;
    word-break: break-all;
}

/* Header */
.hero-title {
    font-family: 'Hack Nerd Font Mono';
    font-size: 38px;
    font-weight: 800;
    color: #e8eaf6;
    letter-spacing: -1px;
    margin-bottom: 0;
}
.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: #4a5a80;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 6px;
}

/* Input styling */
.stNumberInput input { background: #111827 !important; border-color: #2a3a5e !important; color: #e8eaf6 !important; }
div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #00bcd4, #00e676);
    color: #0a0e1a;
    font-weight: 700;
    font-size: 15px;
    border: none;
    border-radius: 8px;
    padding: 12px 32px;
    width: 100%;
    letter-spacing: 1px;
}
div[data-testid="stButton"] button:disabled {
    background: #1e2a42 !important;
    color: #4a5a80 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state defaults ───────────────────────────────────────────────────

for key, default in {
    "running": False,
    "done": False,
    "log_lines": [],
    "result": None,
    "myr_quorum": None,
    "cny_quorum": None,
    "current_step": -1,
    "wallets": {},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Constants ────────────────────────────────────────────────────────────────

STEPS = [
    ("SETUP", "Faucet Wallets"),
    ("KEY_CEREMONY", "MPC Key Ceremony"),
    ("L2_DEPLOY", "L2 Hook Deployment"),
    ("MYR_AUTH", "MYR Authorization"),
    ("UNL", "XRPL UNL Validation"),
    ("CNY_SETTLE", "CNY Settlement"),
]

STEP_TAGS = [s[0] for s in STEPS]


# ── Helpers ──────────────────────────────────────────────────────────────────


def step_index(tag: str) -> int:
    try:
        return STEP_TAGS.index(tag)
    except ValueError:
        return -1


def quorum_gauge(label: str, quorum, threshold: float = 60.0) -> str:
    pct = min(quorum.total_quorum_pct, 100)
    css_class = "approved" if quorum.approved else "pending"
    status = "✅ Approved" if quorum.approved else "⏳ Pending"
    return f"""
<div class="quorum-bar-wrapper">
  <div class="quorum-title">{label}</div>
  <div class="quorum-bar-track">
    <div class="quorum-bar-fill {css_class}" style="width:{pct:.1f}%"></div>
  </div>
  <div class="quorum-pct">
    {quorum.total_quorum_pct:.1f}% total &nbsp;|&nbsp;
    Banks {quorum.bank_votes_pct:.1f}% ({quorum.weighted_bank_pct:.1f}% weighted) &nbsp;|&nbsp;
    Holders {quorum.holder_votes_pct:.1f}% ({quorum.weighted_holder_pct:.1f}% weighted) &nbsp;|&nbsp;
    {status}
  </div>
</div>
"""


def render_step_tracker(current_step: int) -> str:
    rows = []
    for i, (tag, label) in enumerate(STEPS):
        if i < current_step:
            dot_cls, lbl_cls = "done", "done"
            icon = "✓"
        elif i == current_step:
            dot_cls, lbl_cls = "active", ""
            icon = "▶"
        else:
            dot_cls, lbl_cls = "waiting", ""
            icon = "○"
        rows.append(
            f'<div class="step-row">'
            f'<div class="step-dot {dot_cls}"></div>'
            f'<span class="step-label {lbl_cls}">{icon} {label}</span>'
            f"</div>"
        )
    return "".join(rows)


def render_log(lines: list) -> str:
    if not lines:
        return '<div class="log-panel"><span style="color:#2d3748">Waiting for bridge execution…</span></div>'
    rows = []
    for ts, tag, msg in lines[-60:]:
        rows.append(
            f'<div class="log-line {tag}"><span class="log-ts">{ts}</span>{msg}</div>'
        )
    return f'<div class="log-panel">{"".join(rows)}</div>'


# ── Bridge thread ─────────────────────────────────────────────────────────────


def run_bridge_thread(amount_myr: float, msg_queue: queue.Queue) -> None:
    """Run the bridge in a background thread, pushing log events to the queue."""

    def callback(step: str, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        msg_queue.put(("LOG", ts, step, message))
        msg_queue.put(("STEP", step))

    try:
        bridge = L2_Bridge(callback=callback)

        # Patch to capture quorum results
        original_myr = bridge.myr_authorization
        original_cny = bridge.cny_settlement

        def patched_myr(amount):
            result = original_myr(amount)
            if bridge.tx_log:
                q = bridge.tx_log[-1].quorum
                if q:
                    msg_queue.put(("MYR_QUORUM", q))
            return result

        def patched_cny(amount):
            result = original_cny(amount)
            if bridge.tx_log:
                q = bridge.tx_log[-1].quorum
                if q:
                    msg_queue.put(("CNY_QUORUM", q))
            return result

        bridge.myr_authorization = patched_myr
        bridge.cny_settlement = patched_cny

        result = bridge.run_full_bridge(amount_myr)
        msg_queue.put(("DONE", result))
    except Exception as exc:
        msg_queue.put(("ERROR", str(exc)))


# ── Layout ────────────────────────────────────────────────────────────────────

# Header
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="hero-title">CrossL2 Bridge</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-sub">MPC-TSS · XRPL Testnet · MYR → CNY</div>',
        unsafe_allow_html=True,
    )
with col_h2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
<div style="text-align:right;font-size:11px;color:#2d3748;font-family:'Space Mono',monospace;line-height:1.8">
POC · Testnet Only<br>
60% quorum threshold<br>
40% banks + 60% holders
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown(
    "<hr style='border-color:#1e2a42;margin:8px 0 24px'>", unsafe_allow_html=True
)

# ── Main layout: left panel (input + steps + quorum) | right panel (log + result)
left, right = st.columns([1, 1.8], gap="large")

with left:
    st.markdown("#### Bridge Parameters")

    amount_myr = st.number_input(
        "Amount (RM)",
        min_value=1.0,
        max_value=1_000_000.0,
        value=1000.0,
        step=100.0,
        format="%.2f",
        disabled=st.session_state.running,
    )

    # Live FX preview
    cny_preview = amount_myr * (1 / MYR_TO_XRP) * XRP_TO_CNY * (1 - BRIDGE_FEE)
    xrp_intermediate = amount_myr / MYR_TO_XRP

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(
            f'<div class="metric-card"><div class="label">RM In</div>'
            f'<div class="value">{amount_myr:,.0f}</div>'
            f'<div class="sub">MYR</div></div>',
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f'<div class="metric-card"><div class="label">via XRP</div>'
            f'<div class="value">{xrp_intermediate:,.1f}</div>'
            f'<div class="sub">intermediate</div></div>',
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            f'<div class="metric-card"><div class="label">CNY Out</div>'
            f'<div class="value">{cny_preview:,.1f}</div>'
            f'<div class="sub">CNY</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div style=\"font-size:11px;color:#2d3748;margin:8px 0 16px;font-family:'Space Mono',monospace\">"
        f"Fee: {BRIDGE_FEE * 100:.1f}% &nbsp;|&nbsp; "
        f"MYR/XRP: {MYR_TO_XRP} &nbsp;|&nbsp; "
        f"XRP/CNY: {XRP_TO_CNY:.3f}</div>",
        unsafe_allow_html=True,
    )

    # Governance parameters
    with st.expander("⚙️ Governance Parameters", expanded=False):
        st.markdown(
            f"""
| Parameter | Value |
|-----------|-------|
| Quorum Threshold | {QUORUM_THRESHOLD:.0f}% |
| Bank Weight | 40% |
| Holder Weight | 60% |
| MYR Banks | {NUM_MYR_BANKS:,} |
| CNY Banks | {NUM_CNY_BANKS:,} |
| Holders (each side) | {NUM_HOLDERS:,} |
"""
        )

    # Start button
    if not st.session_state.running and not st.session_state.done:
        if st.button("🚀  Execute Bridge", use_container_width=True):
            st.session_state.running = True
            st.session_state.done = False
            st.session_state.log_lines = []
            st.session_state.result = None
            st.session_state.myr_quorum = None
            st.session_state.cny_quorum = None
            st.session_state.current_step = 0
            st.session_state._msg_queue = queue.Queue()
            t = threading.Thread(
                target=run_bridge_thread,
                args=(amount_myr, st.session_state._msg_queue),
                daemon=True,
            )
            t.start()
            st.rerun()

    elif st.session_state.done:
        if st.button("🔄  New Transaction", use_container_width=True):
            for k in [
                "running",
                "done",
                "log_lines",
                "result",
                "myr_quorum",
                "cny_quorum",
                "current_step",
                "wallets",
            ]:
                st.session_state[k] = {
                    "running": False,
                    "done": False,
                    "log_lines": [],
                    "result": None,
                    "myr_quorum": None,
                    "cny_quorum": None,
                    "current_step": -1,
                    "wallets": {},
                }[k]
            st.rerun()
    else:
        st.button("⏳  Running…", disabled=True, use_container_width=True)

    # Step tracker
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Pipeline Steps")
    st.markdown(
        render_step_tracker(st.session_state.current_step),
        unsafe_allow_html=True,
    )

    # Quorum gauges
    if st.session_state.myr_quorum or st.session_state.cny_quorum:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Quorum Results")

    if st.session_state.myr_quorum:
        st.markdown(
            quorum_gauge(
                "MYR Side — Malaysian Banks & Holders", st.session_state.myr_quorum
            ),
            unsafe_allow_html=True,
        )
    if st.session_state.cny_quorum:
        st.markdown(
            quorum_gauge(
                "CNY Side — Chinese Banks & Holders", st.session_state.cny_quorum
            ),
            unsafe_allow_html=True,
        )


with right:
    st.markdown("#### Bridge Log")
    log_placeholder = st.empty()
    log_placeholder.markdown(
        render_log(st.session_state.log_lines), unsafe_allow_html=True
    )

    # Result panel
    if st.session_state.done and st.session_state.result:
        r = st.session_state.result
        st.markdown("<br>", unsafe_allow_html=True)
        st.success("✅ Transaction Complete")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f'<div class="metric-card"><div class="label">MYR Sent</div>'
                f'<div class="value">RM {r["myr_amount"]:,.2f}</div></div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f'<div class="metric-card"><div class="label">CNY Received</div>'
                f'<div class="value">¥{r["cny_amount"]:,.4f}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("**Transaction Hashes**")
        for label, key in [
            ("Deploy", "deploy_hash"),
            ("MYR→USDC", "myr_tx_hash"),
            ("USDC→CNY", "cny_tx_hash"),
        ]:
            st.markdown(
                f'<div style="margin-bottom:6px"><span style="font-size:11px;color:#6b7db3;text-transform:uppercase;letter-spacing:1px">{label}</span>'
                f'<div class="tx-chip">{r[key]}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f"[🔗 View on Testnet Explorer]({r['explorer_url']})",
            unsafe_allow_html=True,
        )

# ── Polling loop ──────────────────────────────────────────────────────────────

if st.session_state.running:
    q: queue.Queue = st.session_state.get("_msg_queue")
    if q:
        updated = False
        try:
            for _ in range(40):  # drain up to 40 messages per rerun
                msg = q.get_nowait()
                updated = True

                if msg[0] == "LOG":
                    _, ts, tag, text = msg
                    st.session_state.log_lines.append((ts, tag, text))

                elif msg[0] == "STEP":
                    tag = msg[1]
                    idx = step_index(tag)
                    if idx >= 0:
                        st.session_state.current_step = idx

                elif msg[0] == "MYR_QUORUM":
                    st.session_state.myr_quorum = msg[1]

                elif msg[0] == "CNY_QUORUM":
                    st.session_state.cny_quorum = msg[1]

                elif msg[0] == "DONE":
                    st.session_state.result = msg[1]
                    st.session_state.running = False
                    st.session_state.done = True
                    st.session_state.current_step = len(STEPS)

                elif msg[0] == "ERROR":
                    st.session_state.log_lines.append(
                        (time.strftime("%H:%M:%S"), "ERROR", f"❌ {msg[1]}")
                    )
                    st.session_state.running = False

        except queue.Empty:
            pass

        # Update log in place without full rerun when possible
        log_placeholder.markdown(
            render_log(st.session_state.log_lines), unsafe_allow_html=True
        )

        time.sleep(0.5)
        st.rerun()
