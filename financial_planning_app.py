from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st

from financial_planning_generator import (
    Advisor,
    Investor,
    PDFGenerationError,
    SIPConfig,
    SWPConfig,
    generate_plan,
)

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Financial Planning Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Brand colors are kept inline so the app works without an external stylesheet.
st.markdown(
    """
    <style>
        .main-header {
            background: linear-gradient(135deg, #6b1d2e 0%, #8a2a3e 100%);
            color: white;
            padding: 24px 32px;
            border-radius: 10px;
            margin-bottom: 24px;
        }
        .main-header h1 { color: white; margin: 0; font-size: 28px; }
        .main-header p { color: #f0d4d9; margin: 6px 0 0 0; font-size: 14px; font-style: italic; }
        .stButton > button {
            background-color: #6b1d2e;
            color: white;
            font-weight: 700;
            padding: 10px 24px;
            border-radius: 8px;
            border: none;
        }
        .stButton > button:hover { background-color: #8a2a3e; color: white; }
        .stDownloadButton > button {
            background-color: #2d8a4a;
            color: white;
            font-weight: 700;
            padding: 10px 24px;
            border-radius: 8px;
            border: none;
        }
        .stDownloadButton > button:hover { background-color: #38a85a; color: white; }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# One-time setup: install Playwright's Chromium browser if missing.
# This is required when the app runs on a fresh container (e.g. Streamlit
# Community Cloud). On a local machine where `playwright install chromium`
# was already run, this is a no-op.
# -----------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _ensure_playwright_browser() -> bool:
    """
    Ensure Playwright's Chromium binary is available. Returns True on success.
    Cached across reruns so this runs at most once per app instance.
    """
    try:
        from playwright.sync_api import sync_playwright

        # Probe: try to launch Chromium. If it works, we're done.
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                browser.close()
            logger.info("Playwright Chromium is already installed.")
            return True
        except Exception as probe_error:
            logger.info("Chromium not found, attempting install: %s", probe_error)

        # Browser missing — install it (one-time, ~30s on first deploy).
        with st.spinner(
            "⏳ First-time setup: installing browser engine "
            "(one-time, takes ~30 seconds)..."
        ):
            result = subprocess.run(
                ["playwright", "install", "chromium"],
                capture_output=True,
                timeout=300,
                text=True,
            )
            if result.returncode != 0:
                logger.error("playwright install failed: %s", result.stderr)
                st.error(
                    "Browser setup failed. Please contact the app administrator. "
                    "Details have been logged."
                )
                return False
        logger.info("Playwright Chromium installed successfully.")
        return True
    except subprocess.TimeoutExpired:
        st.error("Browser setup timed out. Please refresh the page to try again.")
        return False
    except Exception as e:
        logger.exception("Unexpected error during Playwright setup")
        st.error(f"Setup failed: {e}")
        return False


# Run setup before showing the UI
_setup_ok = _ensure_playwright_browser()


# -----------------------------------------------------------------------------
# UI Header
# -----------------------------------------------------------------------------

st.markdown(
    """
    <div class="main-header">
        <h1>📊 Personalized Financial Planning Generator</h1>
        <p>Fill in client details below and generate a branded SIP + SWP plan as PDF</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not _setup_ok:
    st.stop()


# -----------------------------------------------------------------------------
# Helpers for the form
# -----------------------------------------------------------------------------

def _resolve_logo_path(uploaded_file, tmpdir: str) -> Optional[str]:
    """
    Decide which logo to use. Priority:
      1. The user just uploaded a logo via the form
      2. A file named 'Logo.jpg' / 'Logo.png' / 'Logo.jpeg' in the cwd
      3. None (the generator will draw a CSS fallback logo)
    """
    if uploaded_file is not None:
        ext = Path(uploaded_file.name).suffix.lower() or ".jpg"
        path = os.path.join(tmpdir, f"logo{ext}")
        with open(path, "wb") as f:
            f.write(uploaded_file.getvalue())
        return path

    for candidate in ("Logo.jpg", "Logo.jpeg", "Logo.png"):
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    return None


# -----------------------------------------------------------------------------
# Input form
# -----------------------------------------------------------------------------

with st.form("plan_form"):
    # ---- INVESTOR ----
    st.subheader("👤 Investor Details")
    col1, col2 = st.columns([1, 3])
    with col1:
        investor_title = st.selectbox("Title", ["Mr.", "Ms.", "Mrs.", "Dr."], index=0)
    with col2:
        investor_name = st.text_input(
            "Full Name",
            value="",
            placeholder="e.g., Pranav Agarwal",
        )

    st.markdown("---")

    # ---- SIP CONFIG ----
    st.subheader("📈 Plan A — SIP (Accumulation Phase)")
    col1, col2, col3 = st.columns(3)
    with col1:
        monthly_sip = st.number_input(
            "Monthly SIP (₹)",
            min_value=1000,
            max_value=10_000_000,
            value=40_000,
            step=1000,
            help="Amount invested every month",
        )
    with col2:
        sip_years = st.number_input(
            "Duration (Years)",
            min_value=1,
            max_value=40,
            value=25,
            step=1,
        )
    with col3:
        step_up_pct = st.number_input(
            "Annual Step-Up (%)",
            min_value=0.0,
            max_value=25.0,
            value=10.0,
            step=0.5,
            help="Yearly increase in SIP amount",
        )

    col1, col2 = st.columns(2)
    with col1:
        cagr_low_pct = st.number_input(
            "Conservative CAGR (%)",
            min_value=4.0,
            max_value=20.0,
            value=12.0,
            step=0.5,
        )
    with col2:
        cagr_high_pct = st.number_input(
            "Optimistic CAGR (%)",
            min_value=4.0,
            max_value=25.0,
            value=15.0,
            step=0.5,
        )

    st.markdown("---")

    # ---- SWP CONFIG ----
    st.subheader("💰 Plan B — SWP (Withdrawal Phase)")
    col1, col2, col3 = st.columns(3)
    with col1:
        swp_years = st.number_input(
            "SWP Duration (Years)",
            min_value=5,
            max_value=50,
            value=30,
            step=1,
        )
    with col2:
        return_low_pct = st.number_input(
            "Conservative Return (%)",
            min_value=3.0,
            max_value=15.0,
            value=6.0,
            step=0.5,
        )
    with col3:
        return_high_pct = st.number_input(
            "Moderate Return (%)",
            min_value=3.0,
            max_value=15.0,
            value=8.0,
            step=0.5,
        )

    st.markdown("---")

    # ---- ADVISOR / FIRM BRANDING ----
    with st.expander("🏢 Advisor / Firm Branding (optional — click to customize)"):
        st.markdown("**Firm Logo**")
        st.caption(
            "Upload your firm's logo (JPG/PNG). Recommended size: ~600×200 px. "
            "If omitted, a 'Logo.jpg' file in the app folder will be used. "
            "If neither is available, a default text logo is shown."
        )
        uploaded_logo = st.file_uploader(
            "Choose logo file",
            type=["jpg", "jpeg", "png"],
            help="Logo will appear in the top-left of every page",
            label_visibility="collapsed",
        )
        if uploaded_logo is not None:
            st.image(uploaded_logo, caption="Logo preview", width=300)

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            firm_name = st.text_input("Firm Name", value="AGARWAL")
            firm_subtitle = st.text_input("Firm Subtitle", value="FINANCIAL SERVICES")
            advisor_name = st.text_input("Advisor Name", value="SUSHIL S AGARWAL")
            advisor_role = st.text_input("Advisor Role", value="CEO & Founder")
        with col2:
            mobile = st.text_input("Mobile", value="98244 48111")
            support_lines = st.text_input(
                "Support Numbers", value="98244 48113 / 98244 48116"
            )
            city = st.text_input("City", value="Rajkot")
            serving_since = st.text_input("Serving Since", value="2002")

        office_address = st.text_input(
            "Office Address",
            value=(
                "318, Pride Sapphire, Opp. Golden Super Market, "
                "Off. Amin Marg, Rajkot – 360 001"
            ),
        )
        col1, col2 = st.columns(2)
        with col1:
            clients_count = st.text_input("Clients Count", value="2,200+")
        with col2:
            years_of_service = st.text_input("Years of Service", value="23 Years")

    st.markdown("###")
    submitted = st.form_submit_button(
        "🚀 Generate PDF",
        use_container_width=True,
        type="primary",
    )


# -----------------------------------------------------------------------------
# Generation & download
# -----------------------------------------------------------------------------

if submitted:
    # Input validation
    if not investor_name.strip():
        st.error("⚠️ Please enter the investor's name.")
        st.stop()
    if cagr_low_pct >= cagr_high_pct:
        st.error("⚠️ Optimistic CAGR must be greater than Conservative CAGR.")
        st.stop()
    if return_low_pct >= return_high_pct:
        st.error("⚠️ Moderate return must be greater than Conservative return.")
        st.stop()

    try:
        investor = Investor(name=investor_name.strip(), title=investor_title)
        sip = SIPConfig(
            monthly_sip=int(monthly_sip),
            duration_years=int(sip_years),
            cagr_low=cagr_low_pct / 100,
            cagr_high=cagr_high_pct / 100,
            step_up_rate=step_up_pct / 100,
        )
        swp = SWPConfig(
            duration_years=int(swp_years),
            return_low=return_low_pct / 100,
            return_high=return_high_pct / 100,
        )
    except ValueError as e:
        st.error(f"⚠️ Invalid input: {e}")
        st.stop()

    advisor = Advisor(
        firm_name=firm_name,
        firm_subtitle=firm_subtitle,
        advisor_name=advisor_name,
        advisor_role=advisor_role,
        mobile=mobile,
        support_lines=support_lines,
        office_address=office_address,
        city=city,
        serving_since=serving_since,
        clients_count=clients_count,
        years_of_service=years_of_service,
    )

    with st.spinner("⚙️ Generating your PDF... (takes ~5 seconds)"):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                logo_path = _resolve_logo_path(uploaded_logo, tmpdir)
                if logo_path:
                    advisor.logo_path = logo_path

                safe_name = investor.name.replace(" ", "_")
                pdf_path = os.path.join(tmpdir, f"Financial_Planning_{safe_name}.pdf")

                generate_plan(
                    investor=investor,
                    advisor=advisor,
                    sip=sip,
                    swp=swp,
                    output_path=pdf_path,
                )

                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                # Persist across reruns so the download button stays available
                st.session_state["pdf_bytes"] = pdf_bytes
                st.session_state["pdf_filename"] = (
                    f"Financial_Planning_{safe_name}.pdf"
                )
                st.session_state["investor_name"] = investor.name

            logger.info("Generated PDF for %s (%d bytes)",
                         investor.name, len(pdf_bytes))
        except PDFGenerationError as e:
            logger.exception("PDF generation failed")
            st.error(f"❌ Failed to generate PDF: {e}")
            st.stop()
        except Exception as e:
            logger.exception("Unexpected error during PDF generation")
            st.error(f"❌ Unexpected error: {e}")
            st.stop()

    st.success(f"✅ PDF generated for **{investor.title} {investor.name}**!")


# Persist download button across reruns using session_state
if "pdf_bytes" in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.download_button(
            label="📥 Download PDF",
            data=st.session_state["pdf_bytes"],
            file_name=st.session_state["pdf_filename"],
            mime="application/pdf",
            use_container_width=True,
        )

    st.info(
        f"📄 File ready: `{st.session_state['pdf_filename']}` "
        f"({len(st.session_state['pdf_bytes']) / 1024:.0f} KB) — "
        f"Click the download button above to save it."
    )


# -----------------------------------------------------------------------------
# Footer
# -----------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    """
    <div style='text-align:center; color:#888; font-size:12px;'>
        Financial Planning Generator | Built with Streamlit + Playwright<br>
        Mutual Fund investments are subject to market risks.
        Read all scheme-related documents carefully before investing.
    </div>
    """,
    unsafe_allow_html=True,
)
