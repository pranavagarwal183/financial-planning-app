from __future__ import annotations

import base64
import logging
import mimetypes
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

@dataclass
class Investor:
    """Investor whose plan is being generated."""
    name: str
    title: str = "Mr."   # Mr. / Ms. / Mrs. / Dr.

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Investor name cannot be empty.")
        self.name = self.name.strip()


@dataclass
class Advisor:
    """Advisor / firm details shown in the PDF header, footer, and contact page."""
    firm_name: str = "AGARWAL FINANCIAL SERVICES"
    firm_subtitle: str = ""
    firm_tagline: str = "Securing Your Future"
    firm_amfi_tag: str = "Amfi Registered Mutual Fund Distributor"
    advisor_name: str = "SUSHIL S AGARWAL"
    advisor_role: str = "CEO & Founder"
    mobile: str = "98244 48111"
    support_lines: str = "98244 48113 / 98244 48116"
    office_address: str = (
        "318, Pride Sapphire, Opp. Golden Super Market, Off. Amin Marg, "
        "Rajkot – 360 001"
    )
    city: str = "Rajkot"
    serving_since: str = "2002"
    clients_count: str = "2,200+"
    years_of_service: str = "23 Years"
    logo_path: str = "Logo.jpg"


@dataclass
class SIPConfig:
    """Configuration for the SIP (accumulation) phase."""
    monthly_sip: int = 40000          # ₹/month
    duration_years: int = 25
    cagr_low: float = 0.12            # 12% conservative
    cagr_high: float = 0.15           # 15% optimistic
    step_up_rate: float = 0.10        # 10% annual step-up

    funds: List[Tuple[str, str, str]] = field(default_factory=lambda: [
        ("Large Cap Equity",         "Bluechip / Nifty 50 Index Fund",  "Moderate"),
        ("Flexi Cap / Multi Cap",    "Diversified Multi Cap Fund",      "Mod-High"),
        ("Mid Cap Equity",           "Mid Cap Growth Fund",             "High"),
        ("Small Cap Equity",         "Small Cap Opportunity Fund",      "Very High"),
        ("International / Thematic", "Global / Sectoral Fund",          "High"),
    ])

    def __post_init__(self) -> None:
        if self.monthly_sip <= 0:
            raise ValueError("monthly_sip must be positive.")
        if self.duration_years <= 0:
            raise ValueError("duration_years must be positive.")
        if not 0 < self.cagr_low < self.cagr_high:
            raise ValueError("cagr_low must be > 0 and < cagr_high.")
        if self.step_up_rate < 0:
            raise ValueError("step_up_rate cannot be negative.")
        if not self.funds:
            raise ValueError("At least one fund must be configured.")


@dataclass
class SWPConfig:
    """Configuration for the SWP (withdrawal) phase post-accumulation."""
    duration_years: int = 30
    return_low: float = 0.06          # 6% post-retirement return
    return_high: float = 0.08         # 8% post-retirement return

    def __post_init__(self) -> None:
        if self.duration_years <= 0:
            raise ValueError("SWP duration_years must be positive.")
        if not 0 < self.return_low < self.return_high:
            raise ValueError("return_low must be > 0 and < return_high.")
def sip_future_value_flat(monthly_sip: float, annual_rate: float, years: int) -> float:
    """Future value of a constant monthly SIP, compounded monthly."""
    monthly_rate = annual_rate / 12
    months = years * 12
    fv = 0.0
    for _ in range(months):
        fv = fv * (1 + monthly_rate) + monthly_sip
    return fv


def sip_future_value_stepup(starting_sip: float, annual_rate: float, years: int,
                             step_up_rate: float) -> float:
    """Future value of a SIP that increases annually by step_up_rate."""
    monthly_rate = annual_rate / 12
    fv = 0.0
    current_sip = starting_sip
    for _ in range(years):
        for _ in range(12):
            fv = fv * (1 + monthly_rate) + current_sip
        current_sip *= (1 + step_up_rate)
    return fv


def total_invested_flat(monthly_sip: float, years: int) -> float:
    """Total amount invested over the SIP duration with no step-up."""
    return monthly_sip * 12 * years


def total_invested_stepup(starting_sip: float, years: int, step_up_rate: float) -> float:
    """Total amount invested over the SIP duration with annual step-up."""
    return sum(starting_sip * ((1 + step_up_rate) ** y) * 12 for y in range(years))


def sip_at_year_n_stepup(starting_sip: float, year: int, step_up_rate: float) -> float:
    """SIP amount in year N (after N-1 step-ups)."""
    return starting_sip * ((1 + step_up_rate) ** (year - 1))


def swp_full_utilization(corpus: float, annual_return: float, years: int) -> float:
    """
    Monthly withdrawal that exactly depletes the corpus over `years` years.

    Standard annuity formula:
        PMT = PV × r × (1+r)^n / ((1+r)^n − 1)
    where r is the monthly rate and n is the number of months.
    """
    r = annual_return / 12
    n = years * 12
    return corpus * r * (1 + r) ** n / ((1 + r) ** n - 1)


# =============================================================================
# NUMBER FORMATTING (Indian style: Lakhs / Crores)
# =============================================================================

def format_inr(value: float) -> str:
    """Format a rupee value as Lakhs or Crores, e.g. '₹7.5 Cr' or '₹85 L'."""
    if value >= 1_00_00_000:
        return f"₹{value / 1_00_00_000:.1f} Cr"
    if value >= 1_00_000:
        return f"₹{value / 1_00_000:.0f} L"
    return f"₹{value:,.0f}"


def format_inr_exact(value: float) -> str:
    """Format with two decimals, e.g. '₹7.52 Cr' or '₹84.95 L'."""
    if value >= 1_00_00_000:
        return f"₹{value / 1_00_00_000:.2f} Cr"
    if value >= 1_00_000:
        return f"₹{value / 1_00_000:.2f} L"
    return f"₹{value:,.0f}"


def format_inr_rupees(value: float) -> str:
    """Format using Indian comma grouping, e.g. '₹40,000' or '₹3,93,989'."""
    n = int(round(value))
    s = str(n)
    if len(s) <= 3:
        return f"₹{s}"
    last3 = s[-3:]
    rest = s[:-3]
    parts: List[str] = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return f"₹{','.join(parts)},{last3}"

MAX_BAR_PX = 170


def scale_bars(values: List[float], max_px: int = MAX_BAR_PX) -> List[int]:
    """Scale a list of values to bar heights in pixels (preserves proportions)."""
    if not values:
        return []
    max_v = max(values)
    if max_v <= 0:
        return [1 for _ in values]
    return [max(2, int(v / max_v * max_px)) for v in values]


# =============================================================================
# HTML/CSS
# =============================================================================

CSS = """
@page { size: 1280px 880px; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica', 'Arial', sans-serif; background: #fff; color: #333; }

.page { width: 1280px; height: 880px; position: relative; page-break-after: always; background: #fff; overflow: hidden; }
.page:last-child { page-break-after: auto; }

.header { background: #6b1d2e; height: 110px; padding: 0 45px; display: flex; align-items: center; justify-content: space-between; color: #fff; }
.logo-box { background: #fff; border-radius: 10px; padding: 8px 14px; display: flex; align-items: center; justify-content: center; gap: 10px; min-width: 230px; min-height: 80px; }
.logo-box img { max-height: 70px; max-width: 280px; width: auto; height: auto; object-fit: contain; display: block; }
.logo-icon { width: 36px; height: 36px; background: #6b1d2e; border-radius: 50%; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: bold; position: relative; }
.logo-icon::before { content: ''; position: absolute; inset: 3px; border: 1.5px solid #fff; border-radius: 50%; }
.logo-text { line-height: 1.1; }
.logo-text .tag { font-size: 8px; color: #a0636f; font-style: italic; letter-spacing: 0.5px; }
.logo-text .name { color: #6b1d2e; font-weight: 800; font-size: 18px; letter-spacing: 0.5px; }
.logo-text .sub { color: #6b1d2e; font-weight: 600; font-size: 13px; }
.logo-text .amfi { color: #8a4855; font-size: 7px; font-style: italic; }
.header-title { font-size: 22px; font-weight: 800; letter-spacing: 1px; }

.footer { position: absolute; bottom: 0; left: 0; right: 0; height: 44px; background: #6b1d2e; color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 40px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }

.content { padding: 30px 40px; height: calc(880px - 110px - 44px); background: #fdf6ed; }

.subheader-italic { text-align: right; font-style: italic; color: #555; font-size: 15px; margin-bottom: 18px; }

.plan-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 18px; }
.plan-card { background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
.plan-card-header { padding: 13px; text-align: center; color: #fff; font-weight: 800; font-size: 14px; letter-spacing: 0.5px; }
.plan-a-header { background: #6b1d2e; }
.plan-b-header { background: #1f5fa8; }
.plan-row { display: flex; justify-content: space-between; padding: 10px 18px; font-size: 13px; border-bottom: 1px solid #f0eae0; }
.plan-row:last-child { border-bottom: none; }
.plan-row .label { color: #444; }
.plan-row .val { font-weight: 700; }
.val-red { color: #6b1d2e; }
.val-blue { color: #1f5fa8; }
.val-green { color: #2d8a4a; }
.val-gold { color: #b77c1a; }

.highlight-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
.highlight { padding: 16px; border-radius: 8px; text-align: center; }
.h-label { font-size: 11px; color: #555; margin-bottom: 6px; }
.h-value { font-size: 22px; font-weight: 800; }
.h-purple { background: #efe4f0; }
.h-purple .h-value { color: #6b1d2e; }
.h-blue { background: #dfeaf7; }
.h-blue .h-value { color: #1f5fa8; }
.h-yellow { background: #fbefc7; }
.h-yellow .h-value { color: #b77c1a; }
.h-green { background: #dceee0; }
.h-green .h-value { color: #2d8a4a; }

.tagline-band { margin-top: 16px; border: 1px dashed #c9a9a9; padding: 10px; text-align: center; font-style: italic; color: #6b1d2e; font-size: 13px; border-radius: 4px; }

table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; font-size: 12px; }
table th { background: #6b1d2e; color: #fff; text-align: left; padding: 11px 14px; font-weight: 700; }
table.blue-head th { background: #1f5fa8; }
table.gold-head th { background: #b77c1a; }
table.green-head th { background: #2d8a4a; }
table td { padding: 10px 14px; border-bottom: 1px solid #f0eae0; }
table tr:last-child td { border-bottom: none; }
table tr.total-row td { background: #f6ecf0; color: #6b1d2e; font-weight: 700; }

.section-title { text-align: center; font-weight: 700; color: #6b1d2e; margin-bottom: 10px; font-size: 14px; }
.section-title.blue { color: #1f5fa8; }

.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 18px; }
.chart-card { background: #fff; border-radius: 10px; padding: 14px; }
.chart-title { text-align: center; font-weight: 700; color: #6b1d2e; margin-bottom: 8px; font-size: 13px; }
.chart-title.green { color: #2d8a4a; }
.chart-title.blue { color: #1f5fa8; }
.chart-area { display: flex; align-items: flex-end; justify-content: space-around; height: 180px; padding: 0 10px 6px; border-bottom: 1px solid #eee; }
.bar-group { display: flex; gap: 3px; align-items: flex-end; flex: 1; justify-content: center; }
.bar { width: 28px; position: relative; text-align: center; }
.bar .val-label { position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 10px; font-weight: 700; white-space: nowrap; }
.bar-wine-light { background: #c99aa4; }
.bar-wine { background: #6b1d2e; }
.bar-green-light { background: #8bc49a; }
.bar-green { background: #2d8a4a; }
.bar-blue { background: #1f5fa8; }
.x-axis { display: flex; justify-content: space-around; font-size: 10px; color: #666; margin-top: 4px; padding: 0 10px; }
.legend { display: flex; justify-content: center; gap: 18px; margin-top: 8px; font-size: 11px; color: #444; }
.legend-item { display: flex; align-items: center; gap: 5px; }
.legend-swatch { width: 14px; height: 10px; }

.step-grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
.step-card { background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }
.step-head { padding: 10px; text-align: center; color: #fff; font-size: 12px; font-weight: 800; letter-spacing: 0.5px; }
.sh-red { background: #6b1d2e; }
.sh-green { background: #2d8a4a; }
.sh-blue { background: #1f5fa8; }
.sh-gold { background: #b77c1a; }
.step-body { padding: 14px; text-align: center; }
.step-body .main { font-size: 15px; font-weight: 800; margin-bottom: 6px; }
.step-body .main.red { color: #6b1d2e; }
.step-body .main.green { color: #2d8a4a; }
.step-body .main.blue { color: #1f5fa8; }
.step-body .main.gold { color: #b77c1a; }
.step-body .small { font-size: 11px; color: #555; line-height: 1.4; }

.benefits-box { background: #fcf2d2; border-radius: 8px; padding: 16px; border: 1px solid #f0e2a3; }
.benefits-box h3 { color: #b77c1a; font-size: 14px; margin-bottom: 8px; }
.benefits-box ul { list-style: none; font-size: 12px; }
.benefits-box ul li { padding: 3px 0; color: #555; }
.protip { background: #fff; padding: 10px; border-radius: 6px; margin-top: 10px; font-size: 11px; color: #555; }
.protip b { color: #6b1d2e; }

.two-col-swp { display: grid; grid-template-columns: 2fr 1fr; gap: 18px; }

.note-band { background: #e8f3ea; padding: 12px 16px; border-radius: 6px; font-size: 12px; color: #2d5a38; margin-top: 14px; }
.note-band b { color: #2d8a4a; }

.disclaimer-small { text-align: center; font-size: 10px; color: #888; font-style: italic; margin-top: 8px; }

.final-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 30px 0; }
.final-stat { background: #fff; border-radius: 10px; padding: 24px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
.final-stat .big { font-size: 36px; font-weight: 800; margin-bottom: 6px; }
.final-stat .small { font-size: 13px; color: #666; }

.contact-card { background: #fff; border-radius: 10px; overflow: hidden; margin-top: 20px; }
.contact-card-head { background: #6b1d2e; color: #fff; padding: 14px; text-align: center; font-weight: 800; letter-spacing: 0.5px; }
.contact-row { display: flex; padding: 12px 22px; border-bottom: 1px solid #f0eae0; font-size: 13px; }
.contact-row:last-child { border: 0; }
.contact-row .label { color: #6b1d2e; font-weight: 700; width: 90px; }

.quote-band { background: #efe4f0; padding: 22px; text-align: center; border-radius: 8px; font-style: italic; color: #6b1d2e; font-size: 18px; font-weight: 600; }
"""


# =============================================================================
# LOGO HANDLING
# =============================================================================

def _logo_html(advisor: Advisor) -> str:
    """
    Build the logo HTML.

    If `advisor.logo_path` points to an existing file, the image is base64-
    encoded and embedded directly in the HTML so the resulting PDF is fully
    self-contained. If the file is missing, a CSS-drawn fallback logo with
    the firm's text details is used.
    """
    if advisor.logo_path and Path(advisor.logo_path).is_file():
        try:
            with open(advisor.logo_path, "rb") as f:
                img_bytes = f.read()
            b64 = base64.b64encode(img_bytes).decode("ascii")
            mime, _ = mimetypes.guess_type(advisor.logo_path)
            mime = mime or "image/jpeg"
            return (
                f'<div class="logo-box">'
                f'<img src="data:{mime};base64,{b64}" alt="{advisor.firm_name}" />'
                f'</div>'
            )
        except OSError as e:
            logger.warning("Could not read logo at %s: %s. Using text fallback.",
                            advisor.logo_path, e)

    # Fallback: CSS-drawn logo with firm text
    return f"""
<div class="logo-box">
  <div class="logo-icon">:</div>
  <div class="logo-text">
    <div class="tag">{advisor.firm_tagline}</div>
    <div class="name">{advisor.firm_name}</div>
    <div class="sub">{advisor.firm_subtitle}</div>
    <div class="amfi">{advisor.firm_amfi_tag}</div>
  </div>
</div>
"""


def _header_html(advisor: Advisor, page_title: str) -> str:
    return f"""
<div class="header">
  {_logo_html(advisor)}
  <div class="header-title">{page_title}</div>
</div>
"""


def _footer_html(advisor: Advisor) -> str:
    return f"""
<div class="footer">
  <span>{advisor.advisor_name}</span>
  <span>{advisor.advisor_role}, {advisor.firm_name.title()} {advisor.firm_subtitle.title()}</span>
  <span>{advisor.mobile}</span>
  <span>Serving {advisor.clients_count} Clients Since {advisor.years_of_service}</span>
</div>
"""


# =============================================================================
# PAGE BUILDERS
# =============================================================================

def _page_cover(investor: Investor, advisor: Advisor,
                sip: SIPConfig, swp: SWPConfig) -> str:
    """Page 1: Cover & summary cards."""
    flat_low = sip_future_value_flat(sip.monthly_sip, sip.cagr_low, sip.duration_years)
    flat_high = sip_future_value_flat(sip.monthly_sip, sip.cagr_high, sip.duration_years)
    step_low = sip_future_value_stepup(sip.monthly_sip, sip.cagr_low,
                                        sip.duration_years, sip.step_up_rate)
    step_high = sip_future_value_stepup(sip.monthly_sip, sip.cagr_high,
                                         sip.duration_years, sip.step_up_rate)

    return f"""
<div class="page">
  {_header_html(advisor, "PERSONALIZED FINANCIAL PLANNING")}

  <div class="content">
    <div class="subheader-italic">Prepared exclusively for {investor.title} {investor.name.upper()}</div>

    <div class="plan-grid">
      <div class="plan-card">
        <div class="plan-card-header plan-a-header">PLAN A &mdash; EQUITY SIP (FLAT vs STEP-UP)</div>
        <div class="plan-row"><span class="label">Monthly Equity SIP:</span><span class="val val-red">{format_inr_rupees(sip.monthly_sip)}</span></div>
        <div class="plan-row"><span class="label">Duration:</span><span class="val val-red">{sip.duration_years} Years</span></div>
        <div class="plan-row"><span class="label">Funds:</span><span class="val val-red">{len(sip.funds)} Equity Funds @ {format_inr_rupees(sip.monthly_sip / len(sip.funds))} each</span></div>
        <div class="plan-row"><span class="label">Scenarios:</span><span class="val val-red">Flat SIP vs {int(sip.step_up_rate*100)}% Annual Step-Up</span></div>
        <div class="plan-row"><span class="label">Expected CAGR:</span><span class="val val-red">{int(sip.cagr_low*100)}% &ndash; {int(sip.cagr_high*100)}%</span></div>
        <div class="plan-row"><span class="label">Post {sip.duration_years} Yrs:</span><span class="val val-red">SWP for next {swp.duration_years} Years</span></div>
        <div class="plan-row"><span class="label">Goal:</span><span class="val val-red">Long-Term Wealth Creation</span></div>
      </div>
      <div class="plan-card">
        <div class="plan-card-header plan-b-header">PLAN B &mdash; SWP (POST {sip.duration_years} YEARS)</div>
        <div class="plan-row"><span class="label">SWP Duration:</span><span class="val val-blue">{swp.duration_years} Years</span></div>
        <div class="plan-row"><span class="label">Withdrawal Phase:</span><span class="val val-blue">Year {sip.duration_years+1} &ndash; Year {sip.duration_years + swp.duration_years}</span></div>
        <div class="plan-row"><span class="label">Post-Retirement Return:</span><span class="val val-blue">{int(swp.return_low*100)}% &ndash; {int(swp.return_high*100)}% p.a.</span></div>
        <div class="plan-row"><span class="label">Strategy:</span><span class="val val-blue">Full Utilization (Annuity)</span></div>
        <div class="plan-row"><span class="label">Flat SIP Corpus (Yr {sip.duration_years}):</span><span class="val val-green">{format_inr(flat_low)} &ndash; {format_inr(flat_high)}</span></div>
        <div class="plan-row"><span class="label">Step-Up Corpus (Yr {sip.duration_years}):</span><span class="val val-green">{format_inr(step_low)} &ndash; {format_inr(step_high)}</span></div>
        <div class="plan-row"><span class="label">Goal:</span><span class="val val-blue">Tax-Efficient Monthly Income</span></div>
      </div>
    </div>

    <div class="highlight-row">
      <div class="highlight h-purple">
        <div class="h-label">Monthly SIP</div>
        <div class="h-value">{format_inr_rupees(sip.monthly_sip)}</div>
      </div>
      <div class="highlight h-blue">
        <div class="h-label">Accumulation Period</div>
        <div class="h-value">{sip.duration_years} Years</div>
      </div>
      <div class="highlight h-yellow">
        <div class="h-label">SWP Period</div>
        <div class="h-value">{swp.duration_years} Years</div>
      </div>
      <div class="highlight h-green">
        <div class="h-label">Equity CAGR</div>
        <div class="h-value">{int(sip.cagr_low*100)}% &ndash; {int(sip.cagr_high*100)}%</div>
      </div>
    </div>

    <div class="tagline-band">{advisor.firm_amfi_tag} | {advisor.city}</div>
  </div>

  {_footer_html(advisor)}
</div>
"""


def _page_sip_structure(advisor: Advisor, sip: SIPConfig) -> str:
    """Page 2: SIP fund allocation + scenario comparison."""
    per_fund = sip.monthly_sip / len(sip.funds)
    fund_rows = "".join(
        f"""
        <tr><td>Fund {i}</td><td>{cat}</td><td>{fund_name}</td>
        <td class="val-red" style="font-weight:700;">{format_inr_rupees(per_fund)}</td><td>{risk}</td></tr>"""
        for i, (cat, fund_name, risk) in enumerate(sip.funds, 1)
    )

    flat_low = sip_future_value_flat(sip.monthly_sip, sip.cagr_low, sip.duration_years)
    flat_high = sip_future_value_flat(sip.monthly_sip, sip.cagr_high, sip.duration_years)
    step_low = sip_future_value_stepup(sip.monthly_sip, sip.cagr_low,
                                        sip.duration_years, sip.step_up_rate)
    step_high = sip_future_value_stepup(sip.monthly_sip, sip.cagr_high,
                                         sip.duration_years, sip.step_up_rate)

    flat_inv = total_invested_flat(sip.monthly_sip, sip.duration_years)
    step_inv = total_invested_stepup(sip.monthly_sip, sip.duration_years, sip.step_up_rate)
    sip_yr_n = sip_at_year_n_stepup(sip.monthly_sip, sip.duration_years, sip.step_up_rate)

    return f"""
<div class="page">
  {_header_html(advisor, "PLAN A: EQUITY SIP — LONG-TERM WEALTH CREATION")}

  <div class="content">
    <div class="section-title">SIP Investment Structure &mdash; {format_inr_rupees(sip.monthly_sip)} / Month</div>

    <table style="margin-bottom: 20px;">
      <thead>
        <tr><th style="width: 80px;">Fund #</th><th>Fund Category</th><th>Suggested Fund</th>
        <th style="width: 110px;">SIP Amt</th><th style="width: 110px;">Risk</th></tr>
      </thead>
      <tbody>{fund_rows}
        <tr class="total-row">
          <td>TOTAL</td><td>{len(sip.funds)} Funds (Diversified)</td>
          <td>Well Balanced Portfolio</td>
          <td>{format_inr_rupees(sip.monthly_sip)}</td><td>Balanced</td>
        </tr>
      </tbody>
    </table>

    <div class="section-title blue">Scenario Comparison @ {int(sip.cagr_low*100)}&ndash;{int(sip.cagr_high*100)}% CAGR</div>

    <table class="blue-head">
      <thead>
        <tr><th>Metric</th><th>Flat SIP ({int(sip.cagr_low*100)}%)</th><th>Flat SIP ({int(sip.cagr_high*100)}%)</th>
        <th>Step-Up ({int(sip.cagr_low*100)}%)</th><th>Step-Up ({int(sip.cagr_high*100)}%)</th></tr>
      </thead>
      <tbody>
        <tr><td>Starting SIP</td><td>{format_inr_rupees(sip.monthly_sip)}</td><td>{format_inr_rupees(sip.monthly_sip)}</td><td>{format_inr_rupees(sip.monthly_sip)}</td><td>{format_inr_rupees(sip.monthly_sip)}</td></tr>
        <tr><td>SIP at Year {sip.duration_years}</td><td>{format_inr_rupees(sip.monthly_sip)}</td><td>{format_inr_rupees(sip.monthly_sip)}</td><td>{format_inr_rupees(sip_yr_n)}</td><td>{format_inr_rupees(sip_yr_n)}</td></tr>
        <tr><td>Total Invested</td><td>{format_inr(flat_inv)}</td><td>{format_inr(flat_inv)}</td><td>{format_inr(step_inv)}</td><td>{format_inr(step_inv)}</td></tr>
        <tr style="font-weight:700;">
          <td>Corpus @ {sip.duration_years} Yrs*</td>
          <td class="val-green">{format_inr(flat_low)}</td>
          <td class="val-green">{format_inr(flat_high)}</td>
          <td class="val-green">{format_inr(step_low)}</td>
          <td class="val-green">{format_inr(step_high)}</td>
        </tr>
      </tbody>
    </table>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 20px;">
      <div style="background:#fff; border: 2px solid #6b1d2e; border-radius: 10px; padding: 16px; text-align:center;">
        <div style="font-size: 12px; color:#6b1d2e; margin-bottom: 6px;">Flat SIP Corpus ({sip.duration_years}Y)</div>
        <div style="font-size: 24px; font-weight: 800; color:#6b1d2e;">{format_inr(flat_low)} &ndash; {format_inr(flat_high)}</div>
      </div>
      <div style="background:#fff; border: 2px solid #2d8a4a; border-radius: 10px; padding: 16px; text-align:center;">
        <div style="font-size: 12px; color:#2d8a4a; margin-bottom: 6px;">Step-Up SIP Corpus ({sip.duration_years}Y)</div>
        <div style="font-size: 24px; font-weight: 800; color:#2d8a4a;">{format_inr(step_low)} &ndash; {format_inr(step_high)}</div>
      </div>
    </div>

    <div class="disclaimer-small">*Assumed @{int(sip.cagr_low*100)}&ndash;{int(sip.cagr_high*100)}% CAGR. Actual returns may vary. Past performance is not indicative of future results.</div>
  </div>

  {_footer_html(advisor)}
</div>
"""


def _page_year_wise(advisor: Advisor, sip: SIPConfig) -> str:
    """Page 3: Year-wise corpus growth charts and table."""
    # Pick five evenly-spaced milestones, ending at duration_years
    step = max(1, sip.duration_years // 5)
    years = sorted({step * i for i in range(1, 6)} | {sip.duration_years})
    years = sorted(years)[-5:]

    flat_lows = [sip_future_value_flat(sip.monthly_sip, sip.cagr_low, y) for y in years]
    flat_highs = [sip_future_value_flat(sip.monthly_sip, sip.cagr_high, y) for y in years]
    step_lows = [sip_future_value_stepup(sip.monthly_sip, sip.cagr_low, y, sip.step_up_rate) for y in years]
    step_highs = [sip_future_value_stepup(sip.monthly_sip, sip.cagr_high, y, sip.step_up_rate) for y in years]

    flat_max = max(flat_highs)
    step_max = max(step_highs)
    flat_low_h = scale_bars(flat_lows + [flat_max])[:-1]
    flat_high_h = scale_bars(flat_highs + [flat_max])[:-1]
    step_low_h = scale_bars(step_lows + [step_max])[:-1]
    step_high_h = scale_bars(step_highs + [step_max])[:-1]

    def chart_bars(low_h: List[int], high_h: List[int], high_vals: List[float],
                    light_class: str, dark_class: str) -> str:
        return "".join(
            f"""
            <div class="bar-group">
              <div class="bar {light_class}" style="height:{lh}px;"></div>
              <div class="bar {dark_class}" style="height:{hh}px;"><span class="val-label">{format_inr(hv)}</span></div>
            </div>"""
            for lh, hh, hv in zip(low_h, high_h, high_vals)
        )

    flat_chart = chart_bars(flat_low_h, flat_high_h, flat_highs,
                             "bar-wine-light", "bar-wine")
    step_chart = chart_bars(step_low_h, step_high_h, step_highs,
                             "bar-green-light", "bar-green")

    x_axis = "".join(f"<span>Yr {y}</span>" for y in years)

    table_rows = "".join(
        f"""
        <tr><td>Year {y}</td>
        <td>{format_inr(fl)} &ndash; {format_inr(fh)}</td>
        <td class="val-green" style="font-weight:700;">{format_inr(sl)} &ndash; {format_inr(sh)}</td>
        <td>+{format_inr(sl - fl)}</td>
        <td>+{format_inr(sh - fh)}</td></tr>"""
        for y, fl, fh, sl, sh in zip(years, flat_lows, flat_highs, step_lows, step_highs)
    )

    max_extra = max(step_highs[-1] - flat_highs[-1], step_lows[-1] - flat_lows[-1])

    return f"""
<div class="page">
  {_header_html(advisor, f"PLAN A: YEAR-WISE CORPUS GROWTH ({int(sip.cagr_low*100)}% – {int(sip.cagr_high*100)}% CAGR)")}

  <div class="content">
    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">Flat SIP {format_inr_rupees(sip.monthly_sip)}/mo</div>
        <div class="chart-area">{flat_chart}</div>
        <div class="x-axis">{x_axis}</div>
        <div class="legend">
          <div class="legend-item"><span class="legend-swatch bar-wine-light"></span>@{int(sip.cagr_low*100)}%</div>
          <div class="legend-item"><span class="legend-swatch bar-wine"></span>@{int(sip.cagr_high*100)}%</div>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title green">{int(sip.step_up_rate*100)}% Step-Up SIP</div>
        <div class="chart-area">{step_chart}</div>
        <div class="x-axis">{x_axis}</div>
        <div class="legend">
          <div class="legend-item"><span class="legend-swatch bar-green-light"></span>@{int(sip.cagr_low*100)}%</div>
          <div class="legend-item"><span class="legend-swatch bar-green"></span>@{int(sip.cagr_high*100)}%</div>
        </div>
      </div>
    </div>

    <table>
      <thead>
        <tr><th>Year</th><th>Flat SIP Range</th><th>Step-Up Range</th>
        <th>Advantage ({int(sip.cagr_low*100)}%)</th><th>Advantage ({int(sip.cagr_high*100)}%)</th></tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>

    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 18px;">
      <div style="background:#fff; border: 2px solid #6b1d2e; border-radius: 10px; padding: 14px; text-align:center;">
        <div style="font-size: 11px; color:#6b1d2e;">Flat {sip.duration_years}Y Range</div>
        <div style="font-size: 22px; font-weight: 800; color:#6b1d2e; margin-top: 4px;">{format_inr(flat_lows[-1])} &ndash; {format_inr(flat_highs[-1])}</div>
      </div>
      <div style="background:#fff; border: 2px solid #2d8a4a; border-radius: 10px; padding: 14px; text-align:center;">
        <div style="font-size: 11px; color:#2d8a4a;">Step-Up {sip.duration_years}Y Range</div>
        <div style="font-size: 22px; font-weight: 800; color:#2d8a4a; margin-top: 4px;">{format_inr(step_lows[-1])} &ndash; {format_inr(step_highs[-1])}</div>
      </div>
      <div style="background:#fff; border: 2px solid #b77c1a; border-radius: 10px; padding: 14px; text-align:center;">
        <div style="font-size: 11px; color:#b77c1a;">Max Extra Wealth</div>
        <div style="font-size: 22px; font-weight: 800; color:#b77c1a; margin-top: 4px;">{format_inr(max_extra)}</div>
      </div>
    </div>
  </div>

  {_footer_html(advisor)}
</div>
"""


def _page_swp(advisor: Advisor, sip: SIPConfig, swp: SWPConfig) -> str:
    """Page 4: SWP withdrawal projections."""
    flat_low = sip_future_value_flat(sip.monthly_sip, sip.cagr_low, sip.duration_years)
    flat_high = sip_future_value_flat(sip.monthly_sip, sip.cagr_high, sip.duration_years)
    step_low = sip_future_value_stepup(sip.monthly_sip, sip.cagr_low,
                                        sip.duration_years, sip.step_up_rate)
    step_high = sip_future_value_stepup(sip.monthly_sip, sip.cagr_high,
                                         sip.duration_years, sip.step_up_rate)

    def w(corpus: float, rate: float) -> float:
        return swp_full_utilization(corpus, rate, swp.duration_years)

    return f"""
<div class="page">
  {_header_html(advisor, f"PLAN B: SWP — SYSTEMATIC WITHDRAWAL PLAN (Post {sip.duration_years} Years)")}

  <div class="content">
    <div class="section-title">Monthly Income Strategy &mdash; Year {sip.duration_years+1} to Year {sip.duration_years + swp.duration_years} ({swp.duration_years} Years)</div>

    <div class="step-grid-4">
      <div class="step-card">
        <div class="step-head sh-red">ACCUMULATION</div>
        <div class="step-body">
          <div class="main red">Years 1&ndash;{sip.duration_years}</div>
          <div class="small">SIP of {format_inr_rupees(sip.monthly_sip)}/mo<br>in {len(sip.funds)} Equity Funds</div>
        </div>
      </div>
      <div class="step-card">
        <div class="step-head sh-green">CORPUS BUILT</div>
        <div class="step-body">
          <div class="main green">At Year {sip.duration_years}</div>
          <div class="small">Flat: {format_inr(flat_low)} &ndash; {format_inr(flat_high)}<br>Step: {format_inr(step_low)} &ndash; {format_inr(step_high)}</div>
        </div>
      </div>
      <div class="step-card">
        <div class="step-head sh-blue">SWP PHASE</div>
        <div class="step-body">
          <div class="main blue">Years {sip.duration_years+1}&ndash;{sip.duration_years + swp.duration_years}</div>
          <div class="small">Monthly Withdrawals<br>for {swp.duration_years} Years</div>
        </div>
      </div>
      <div class="step-card">
        <div class="step-head sh-gold">FULL UTILIZATION</div>
        <div class="step-body">
          <div class="main gold">Year {sip.duration_years + swp.duration_years}</div>
          <div class="small">Corpus fully deployed<br>Maximum monthly income</div>
        </div>
      </div>
    </div>

    <div class="two-col-swp">
      <div>
        <div style="color:#6b1d2e; font-weight:700; font-size:14px; margin-bottom:8px;">Flat SIP &mdash; Full Utilization SWP ({swp.duration_years} Years)</div>
        <table style="margin-bottom: 14px;">
          <thead>
            <tr><th>Corpus @ Year {sip.duration_years}</th>
            <th>@ {int(swp.return_low*100)}% Post-Retirement Return</th>
            <th>@ {int(swp.return_high*100)}% Post-Retirement Return</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>{format_inr(flat_low)} (Flat @ {int(sip.cagr_low*100)}%)</td>
              <td style="font-weight:700;">{format_inr_exact(w(flat_low, swp.return_low))}/mo</td>
              <td class="val-green" style="font-weight:700;">{format_inr_exact(w(flat_low, swp.return_high))}/mo</td>
            </tr>
            <tr>
              <td>{format_inr(flat_high)} (Flat @ {int(sip.cagr_high*100)}%)</td>
              <td style="font-weight:700;">{format_inr_exact(w(flat_high, swp.return_low))}/mo</td>
              <td class="val-green" style="font-weight:700;">{format_inr_exact(w(flat_high, swp.return_high))}/mo</td>
            </tr>
          </tbody>
        </table>

        <div style="color:#2d8a4a; font-weight:700; font-size:14px; margin-bottom:8px;">{int(sip.step_up_rate*100)}% Step-Up SIP &mdash; Full Utilization SWP ({swp.duration_years} Years)</div>
        <table class="green-head" style="margin-bottom: 14px;">
          <thead>
            <tr><th>Corpus @ Year {sip.duration_years}</th>
            <th>@ {int(swp.return_low*100)}% Post-Retirement Return</th>
            <th>@ {int(swp.return_high*100)}% Post-Retirement Return</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>{format_inr(step_low)} (Step-Up @ {int(sip.cagr_low*100)}%)</td>
              <td style="font-weight:700;">{format_inr_exact(w(step_low, swp.return_low))}/mo</td>
              <td class="val-green" style="font-weight:700;">{format_inr_exact(w(step_low, swp.return_high))}/mo</td>
            </tr>
            <tr>
              <td>{format_inr(step_high)} (Step-Up @ {int(sip.cagr_high*100)}%)</td>
              <td style="font-weight:700;">{format_inr_exact(w(step_high, swp.return_low))}/mo</td>
              <td class="val-green" style="font-weight:700;">{format_inr_exact(w(step_high, swp.return_high))}/mo</td>
            </tr>
          </tbody>
        </table>

        <div style="color:#b77c1a; font-weight:700; font-size:14px; margin-bottom:8px;">SWP Summary &mdash; Maximum Monthly Income ({swp.duration_years}-Year Full Utilization)</div>
        <table class="gold-head">
          <thead>
            <tr><th>Scenario</th>
            <th>@ {int(swp.return_low*100)}% Post-Retirement</th>
            <th>@ {int(swp.return_high*100)}% Post-Retirement</th></tr>
          </thead>
          <tbody>
            <tr><td>Flat SIP</td>
                <td>{format_inr_exact(w(flat_low, swp.return_low))} &ndash; {format_inr_exact(w(flat_high, swp.return_low))}/mo</td>
                <td class="val-green" style="font-weight:700;">{format_inr_exact(w(flat_low, swp.return_high))} &ndash; {format_inr_exact(w(flat_high, swp.return_high))}/mo</td></tr>
            <tr><td class="val-blue" style="font-weight:700;">Step-Up SIP</td>
                <td class="val-blue">{format_inr_exact(w(step_low, swp.return_low))} &ndash; {format_inr_exact(w(step_high, swp.return_low))}/mo</td>
                <td class="val-green" style="font-weight:700;">{format_inr_exact(w(step_low, swp.return_high))} &ndash; {format_inr_exact(w(step_high, swp.return_high))}/mo</td></tr>
          </tbody>
        </table>
      </div>

      <div class="benefits-box">
        <h3>Full Utilization SWP</h3>
        <ul>
          <li>✓ Maximum monthly income</li>
          <li>✓ Tax-efficient payouts</li>
          <li>✓ Corpus deployed fully over {swp.duration_years} Years</li>
          <li>✓ Flexible &mdash; pause / adjust anytime</li>
          <li>✓ Conservative return assumptions</li>
        </ul>
        <div class="protip">
          <b>How it works:</b> Corpus earns {int(swp.return_low*100)}&ndash;{int(swp.return_high*100)}% during retirement (conservative debt-oriented portfolio) while monthly withdrawals deplete it smoothly over {swp.duration_years} years. Payouts calculated using standard annuity formula.
        </div>
      </div>
    </div>

    <div class="disclaimer-small" style="margin-top:10px;">*Full utilization = fixed monthly withdrawal that exhausts corpus exactly at Year {sip.duration_years + swp.duration_years} (Year {swp.duration_years} of SWP). Assumes corpus earns {int(swp.return_low*100)}&ndash;{int(swp.return_high*100)}% in conservative post-retirement portfolio.</div>
  </div>

  {_footer_html(advisor)}
</div>
"""


def _page_summary(advisor: Advisor, sip: SIPConfig, swp: SWPConfig) -> str:
    """Page 5: Wealth projection summary."""
    flat_low = sip_future_value_flat(sip.monthly_sip, sip.cagr_low, sip.duration_years)
    flat_high = sip_future_value_flat(sip.monthly_sip, sip.cagr_high, sip.duration_years)
    step_low = sip_future_value_stepup(sip.monthly_sip, sip.cagr_low,
                                        sip.duration_years, sip.step_up_rate)
    step_high = sip_future_value_stepup(sip.monthly_sip, sip.cagr_high,
                                         sip.duration_years, sip.step_up_rate)

    flat_inv = total_invested_flat(sip.monthly_sip, sip.duration_years)
    step_inv = total_invested_stepup(sip.monthly_sip, sip.duration_years, sip.step_up_rate)
    sip_yr_n = sip_at_year_n_stepup(sip.monthly_sip, sip.duration_years, sip.step_up_rate)

    def w(corpus: float, rate: float) -> float:
        return swp_full_utilization(corpus, rate, swp.duration_years)

    chart_max = max(flat_high, step_high)
    bars = scale_bars([flat_low, flat_high, step_low, step_high, chart_max])[:-1]
    flat_low_h, flat_high_h, step_low_h, step_high_h = bars

    swp_max = w(step_high, swp.return_high)
    swp_bars = scale_bars([
        w(flat_low, swp.return_high),
        w(flat_high, swp.return_high),
        w(step_low, swp.return_high),
        swp_max,
    ])

    return f"""
<div class="page">
  {_header_html(advisor, "WEALTH PROJECTION SUMMARY")}

  <div class="content">
    <div class="section-title">Plan A SIP &amp; Plan B SWP &mdash; Complete Comparison</div>

    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">Plan A: Flat vs Step-Up ({sip.duration_years} Yrs)</div>
        <div class="chart-area" style="padding: 0 50px;">
          <div class="bar-group">
            <div class="bar bar-wine-light" style="height:{flat_low_h}px; width:46px;"><span class="val-label">{format_inr(flat_low)}</span></div>
            <div class="bar bar-wine" style="height:{flat_high_h}px; width:46px;"><span class="val-label">{format_inr(flat_high)}</span></div>
          </div>
          <div class="bar-group">
            <div class="bar bar-green-light" style="height:{step_low_h}px; width:46px;"><span class="val-label">{format_inr(step_low)}</span></div>
            <div class="bar bar-green" style="height:{step_high_h}px; width:46px;"><span class="val-label">{format_inr(step_high)}</span></div>
          </div>
        </div>
        <div class="x-axis" style="padding: 0 50px;">
          <span>Flat</span><span>Step-Up</span>
        </div>
        <div class="legend">
          <div class="legend-item"><span class="legend-swatch bar-wine-light"></span>@{int(sip.cagr_low*100)}%</div>
          <div class="legend-item"><span class="legend-swatch bar-wine"></span>@{int(sip.cagr_high*100)}% Flat</div>
          <div class="legend-item"><span class="legend-swatch bar-green-light"></span>@{int(sip.cagr_low*100)}% Step-Up</div>
          <div class="legend-item"><span class="legend-swatch bar-green"></span>@{int(sip.cagr_high*100)}% Step-Up</div>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title blue">Plan B: SWP Monthly Income ({swp.duration_years} Yrs)</div>
        <div class="chart-area" style="padding: 0 30px;">
          <div class="bar-group">
            <div class="bar bar-blue" style="height:{swp_bars[0]}px; width:42px;"><span class="val-label">{format_inr_exact(w(flat_low, swp.return_high))}/m</span></div>
          </div>
          <div class="bar-group">
            <div class="bar bar-blue" style="height:{swp_bars[1]}px; width:42px;"><span class="val-label">{format_inr_exact(w(flat_high, swp.return_high))}/m</span></div>
          </div>
          <div class="bar-group">
            <div class="bar bar-blue" style="height:{swp_bars[2]}px; width:42px;"><span class="val-label">{format_inr_exact(w(step_low, swp.return_high))}/m</span></div>
          </div>
          <div class="bar-group">
            <div class="bar bar-blue" style="height:{swp_bars[3]}px; width:42px;"><span class="val-label">{format_inr_exact(swp_max)}/m</span></div>
          </div>
        </div>
        <div class="x-axis" style="padding: 0 30px;">
          <span>Flat {int(sip.cagr_low*100)}%</span><span>Flat {int(sip.cagr_high*100)}%</span><span>Step {int(sip.cagr_low*100)}%</span><span>Step {int(sip.cagr_high*100)}%</span>
        </div>
        <div class="legend">
          <div class="legend-item"><span class="legend-swatch bar-blue"></span>Monthly Income @ {int(swp.return_high*100)}% Post-Retirement Return</div>
        </div>
      </div>
    </div>

    <table>
      <thead>
        <tr><th>Metric</th><th>Plan A (Flat)</th><th>Plan A (Step-Up)</th><th>Plan B (SWP Phase)</th></tr>
      </thead>
      <tbody>
        <tr><td>Monthly SIP / Withdrawal</td><td>{format_inr_rupees(sip.monthly_sip)}/mo</td><td>{format_inr_rupees(sip.monthly_sip)} &rarr; {format_inr_rupees(sip_yr_n)}</td><td>Withdrawals (post Yr {sip.duration_years})</td></tr>
        <tr><td>Duration</td><td>{sip.duration_years} Years</td><td>{sip.duration_years} Years</td><td>{swp.duration_years} Years</td></tr>
        <tr><td>Total Invested / Withdrawn</td><td>{format_inr(flat_inv)}</td><td>{format_inr(step_inv)}</td><td>Spread over {swp.duration_years*12} months</td></tr>
        <tr><td>CAGR / Return Range</td><td>{int(sip.cagr_low*100)}% &ndash; {int(sip.cagr_high*100)}%</td><td>{int(sip.cagr_low*100)}% &ndash; {int(sip.cagr_high*100)}%</td><td>{int(swp.return_low*100)}% &ndash; {int(swp.return_high*100)}% post-retirement</td></tr>
        <tr style="font-weight:700;"><td>Corpus / Income Range</td>
          <td class="val-green">{format_inr(flat_low)} &ndash; {format_inr(flat_high)}</td>
          <td class="val-green">{format_inr(step_low)} &ndash; {format_inr(step_high)}</td>
          <td class="val-blue">{format_inr_exact(w(flat_low, swp.return_low))} &ndash; {format_inr_exact(w(step_high, swp.return_high))}/mo</td></tr>
      </tbody>
    </table>

    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 14px;">
      <div style="background:#fff; border: 2px solid #6b1d2e; border-radius: 10px; padding: 12px; text-align:center;">
        <div style="font-size: 10px; color:#6b1d2e;">Flat SIP Corpus ({sip.duration_years}Y)</div>
        <div style="font-size: 18px; font-weight: 800; color:#6b1d2e; margin-top: 4px;">{format_inr(flat_low)} &ndash; {format_inr(flat_high)}</div>
      </div>
      <div style="background:#fff; border: 2px solid #2d8a4a; border-radius: 10px; padding: 12px; text-align:center;">
        <div style="font-size: 10px; color:#2d8a4a;">Step-Up Corpus ({sip.duration_years}Y)</div>
        <div style="font-size: 18px; font-weight: 800; color:#2d8a4a; margin-top: 4px;">{format_inr(step_low)} &ndash; {format_inr(step_high)}</div>
      </div>
      <div style="background:#fff; border: 2px solid #1f5fa8; border-radius: 10px; padding: 12px; text-align:center;">
        <div style="font-size: 10px; color:#1f5fa8;">SWP Income (Step-Up @ {int(swp.return_high*100)}%)</div>
        <div style="font-size: 18px; font-weight: 800; color:#1f5fa8; margin-top: 4px;">{format_inr_exact(w(step_low, swp.return_high))} &ndash; {format_inr_exact(w(step_high, swp.return_high))}/mo</div>
      </div>
      <div style="background:#fff; border: 2px solid #b77c1a; border-radius: 10px; padding: 12px; text-align:center;">
        <div style="font-size: 10px; color:#b77c1a;">Total Wealth Journey</div>
        <div style="font-size: 18px; font-weight: 800; color:#b77c1a; margin-top: 4px;">{sip.duration_years + swp.duration_years} Years</div>
      </div>
    </div>

    <div class="note-band">
      <b>Key Insight:</b> A monthly SIP of {format_inr_rupees(sip.monthly_sip)} sustained for {sip.duration_years} years builds {format_inr(flat_low)}&ndash;{format_inr(step_high)} depending on return scenario and step-up choice. The {int(sip.step_up_rate*100)}% annual step-up adds up to {format_inr(step_high - flat_high)} extra wealth at the high end. Post accumulation, full-utilization SWP for {swp.duration_years} years delivers {format_inr_exact(w(flat_low, swp.return_low))}&ndash;{format_inr_exact(w(step_high, swp.return_high))} monthly income.
    </div>
  </div>

  {_footer_html(advisor)}
</div>
"""


def _page_contact(advisor: Advisor) -> str:
    """Page 6: Trusted partner / contact information."""
    return f"""
<div class="page">
  {_header_html(advisor, "YOUR TRUSTED FINANCIAL PARTNER")}

  <div class="content">
    <div class="quote-band">"{advisor.firm_tagline} &mdash; Since {advisor.serving_since}"</div>

    <div class="final-grid">
      <div class="final-stat">
        <div class="big" style="color:#6b1d2e;">{advisor.clients_count}</div>
        <div class="small">Happy Clients</div>
      </div>
      <div class="final-stat">
        <div class="big" style="color:#1f5fa8;">{advisor.years_of_service}</div>
        <div class="small">Of Trusted Service</div>
      </div>
      <div class="final-stat">
        <div class="big" style="color:#2d8a4a;">AMFI</div>
        <div class="small">Registered Distributor</div>
      </div>
    </div>

    <div class="contact-card">
      <div class="contact-card-head">GET IN TOUCH WITH US</div>
      <div class="contact-row"><span class="label">Advisor:</span><span>{advisor.advisor_name} &mdash; {advisor.advisor_role}</span></div>
      <div class="contact-row"><span class="label">Mobile:</span><span>{advisor.mobile} | Support: {advisor.support_lines}</span></div>
      <div class="contact-row"><span class="label">Office:</span><span>{advisor.office_address}</span></div>
    </div>

    <div style="background:#fdefdb; border: 1px solid #f0cc8a; padding: 12px; margin-top: 16px; border-radius: 8px; text-align:center; font-size: 12px; color: #8a4e0a; font-style: italic;">
      ⚠ Disclaimer: Mutual Fund investments are subject to market risks. Please read all scheme-related documents carefully before investing.
    </div>
  </div>

  {_footer_html(advisor)}
</div>
"""


# =============================================================================
# DOCUMENT ASSEMBLY
# =============================================================================

def build_html(investor: Investor, advisor: Advisor,
               sip: SIPConfig, swp: SWPConfig) -> str:
    """Build the full HTML document for an investor's plan."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Financial Planning - {investor.name}</title>
<style>{CSS}</style>
</head>
<body>
{_page_cover(investor, advisor, sip, swp)}
{_page_sip_structure(advisor, sip)}
{_page_year_wise(advisor, sip)}
{_page_swp(advisor, sip, swp)}
{_page_summary(advisor, sip, swp)}
{_page_contact(advisor)}
</body>
</html>
"""


# =============================================================================
# PDF RENDERING
# =============================================================================

class PDFGenerationError(RuntimeError):
    """Raised when PDF generation fails."""


def generate_plan(investor: Investor,
                  advisor: Optional[Advisor] = None,
                  sip: Optional[SIPConfig] = None,
                  swp: Optional[SWPConfig] = None,
                  output_path: Optional[str] = None) -> str:
    """
    Generate a financial planning PDF for an investor.

    Parameters
    ----------
    investor : Investor
        The client whose plan is being generated.
    advisor : Advisor, optional
        Firm/advisor branding. Defaults to Advisor() with built-in defaults.
    sip : SIPConfig, optional
        SIP accumulation parameters. Defaults to SIPConfig() defaults.
    swp : SWPConfig, optional
        SWP withdrawal parameters. Defaults to SWPConfig() defaults.
    output_path : str, optional
        Where to save the PDF. If omitted, defaults to
        'Financial_Planning_<name>.pdf' in the current working directory.

    Returns
    -------
    str
        Absolute path to the generated PDF.

    Raises
    ------
    PDFGenerationError
        If Playwright is not installed or rendering fails.
    """
    advisor = advisor or Advisor()
    sip = sip or SIPConfig()
    swp = swp or SWPConfig()

    if output_path is None:
        safe_name = investor.name.replace(" ", "_")
        output_path = f"Financial_Planning_{safe_name}.pdf"

    pdf_path = os.path.abspath(output_path)
    output_dir = os.path.dirname(pdf_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    html = build_html(investor, advisor, sip, swp)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise PDFGenerationError(
            "Playwright is required for PDF generation. Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        ) from e

    # Use a temporary HTML file in the same directory as the PDF, so
    # base64-embedded images and relative paths work consistently.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp_file:
        tmp_file.write(html)
        html_path = tmp_file.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 880})
                page = context.new_page()
                page.goto(f"file://{html_path}")
                page.wait_for_load_state("networkidle")
                page.pdf(
                    path=pdf_path,
                    width="1280px",
                    height="880px",
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
            finally:
                browser.close()
    except Exception as e:
        raise PDFGenerationError(f"Failed to render PDF: {e}") from e
    finally:
        try:
            os.unlink(html_path)
        except OSError:
            logger.debug("Could not remove temp HTML file: %s", html_path)

    logger.info("Generated PDF for %s at %s", investor.name, pdf_path)
    return pdf_path
