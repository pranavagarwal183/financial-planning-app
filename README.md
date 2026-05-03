# Financial Planning Generator

Internal web app for financial advisors to generate branded SIP + SWP planning PDFs for clients.

Built with Python, Streamlit, and Playwright. Deployable for free on Streamlit Community Cloud.

## Features

- **SIP accumulation projections** — Flat SIP vs annual Step-Up SIP at customizable CAGR ranges
- **SWP withdrawal projections** — Full-utilization annuity calculations with custom return assumptions
- **6-page branded PDF output** — Cover, fund structure, year-wise growth charts, SWP plan, summary, contact
- **Custom branding** — Upload your firm's logo or use a `Logo.jpg` file in the repo
- **Web UI** — No installation needed for end users; everything runs in the browser
- **Privacy-friendly** — Generated PDFs are streamed directly to the user's browser; no client data is stored

## Quick start (local)

```bash
git clone <your-repo-url>
cd financial-planning-generator
pip install -r requirements.txt
playwright install chromium
streamlit run financial_planning_app.py
```

The app opens at `http://localhost:8501`.

## Deploy free on Streamlit Community Cloud

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for step-by-step instructions. It takes about 10 minutes and gives you a permanent shareable URL.

## Project structure

```
.
├── financial_planning_app.py         # Streamlit web UI
├── financial_planning_generator.py   # PDF generation engine
├── requirements.txt                  # Python dependencies
├── packages.txt                      # System libraries (for cloud hosting)
├── Logo.jpg                          # Your firm's logo (optional)
├── README.md                         # This file
├── DEPLOYMENT.md                     # Free hosting guide
├── LICENSE                           # MIT
└── .gitignore                        # Ignores generated PDFs, caches, etc.
```

## Programmatic use

The generator can also be imported and used directly without the web UI:

```python
from financial_planning_generator import (
    generate_plan, Investor, Advisor, SIPConfig, SWPConfig,
)

generate_plan(
    investor=Investor(name="Pranjal Gupta", title="Mr."),
    advisor=Advisor(logo_path="Logo.jpg"),
    sip=SIPConfig(monthly_sip=40_000, duration_years=25),
    swp=SWPConfig(duration_years=30),
    output_path="output.pdf",
)
```

## Configuration

### `Investor`
| Field | Description |
|---|---|
| `name` | Client's full name (required) |
| `title` | Mr. / Ms. / Mrs. / Dr. (default: Mr.) |

### `Advisor`
Firm and contact details shown in the PDF header, footer, and contact page. All fields have sensible defaults — override only what you need.

| Field | Default |
|---|---|
| `firm_name` | "AGARWAL" |
| `firm_subtitle` | "FINANCIAL SERVICES" |
| `logo_path` | "Logo.jpg" |
| `advisor_name` | "SUSHIL S AGARWAL" |
| `mobile` | "98244 48111" |
| ... | (see `financial_planning_generator.py`) |

### `SIPConfig`
| Field | Default |
|---|---|
| `monthly_sip` | 40000 |
| `duration_years` | 25 |
| `cagr_low` | 0.12 (12%) |
| `cagr_high` | 0.15 (15%) |
| `step_up_rate` | 0.10 (10%) |
| `funds` | 5 default equity funds |

### `SWPConfig`
| Field | Default |
|---|---|
| `duration_years` | 30 |
| `return_low` | 0.06 (6%) |
| `return_high` | 0.08 (8%) |

## How it works

```
Form submission
    ↓
Validate inputs → build Investor / Advisor / SIPConfig / SWPConfig
    ↓
Generate HTML from templates (with brand-styled CSS)
    ↓
Render HTML to PDF via headless Chromium (Playwright)
    ↓
Stream PDF bytes to browser via st.download_button
```

PDF rendering takes ~5 seconds. The temp HTML and PDF files are cleaned up immediately after the bytes are read into memory.

## Customizing the design

- **Colors:** Edit the `CSS` constant in `financial_planning_generator.py`. Brand colors are `#6b1d2e` (maroon), `#1f5fa8` (blue), `#2d8a4a` (green), `#b77c1a` (gold).
- **Pages:** Each page is a `_page_*()` function returning HTML. Add new ones, then include them in `build_html()`.
- **Logo:** Replace `Logo.jpg` in the repo root, or upload via the web UI.
- **Default funds:** Edit the `funds` field in `SIPConfig`.

## Testing

```bash
# Run the generator directly to verify it works
python -c "from financial_planning_generator import generate_plan, Investor; \
    generate_plan(Investor(name='Test'), output_path='/tmp/test.pdf')"
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Playwright is required` error | Run `pip install playwright && playwright install chromium` |
| `Executable doesn't exist` | Run `playwright install chromium` (downloads the browser) |
| PDF blank or formatting broken | Run `playwright install --with-deps chromium` to install system libs |
| Streamlit doesn't reload | Press `R` in the browser, or click "Always rerun" |
| Logo doesn't appear | Check the file is named `Logo.jpg` (case-sensitive) and is in the same folder |

## Contributing

This is an internal tool. Pull requests welcome from team members.

## License

MIT — see [`LICENSE`](LICENSE).

## Disclaimer

Mutual Fund investments are subject to market risks. Read all scheme-related documents carefully before investing. This tool generates illustrative projections — actual returns will vary.
