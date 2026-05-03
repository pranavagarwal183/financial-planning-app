# Free Hosting Guide

Three options ranked by ease. For internal use, **Option 1 (Streamlit Community Cloud) is recommended**.

---

## Option 1: Streamlit Community Cloud — Recommended

**Cost:** Free forever | **Time:** ~10 minutes | **Result:** Permanent URL accessible from any device

### Prerequisites

- A GitHub account (free at https://github.com)
- All files from this repo committed and pushed

### Steps

**1. Push your code to GitHub**

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/financial-planning-generator.git
git push -u origin main
```

Choose **Private** repository visibility if your `Logo.jpg` or any branding contains proprietary content.

**2. Deploy on Streamlit Cloud**

1. Visit https://streamlit.io/cloud and sign in with GitHub
2. Click **"New app"**
3. Select your repository
4. Branch: `main`, Main file path: `financial_planning_app.py`
5. Click **"Deploy"**

The first deployment takes ~5–8 minutes (it installs Python packages, then Playwright's Chromium on first form submission).

**3. Get your URL**

Streamlit gives you a permanent URL like `https://<your-app-name>.streamlit.app`. Bookmark it. Share with the team.

### Restricting access

By default, anyone with the URL can use the app. To restrict to your team only:

1. Streamlit Cloud → your app → **Settings** → **Sharing**
2. Toggle on "Require viewers to log in"
3. Add team members' email addresses

### Free tier limits

| Resource | Free Limit | Will you hit it? |
|---|---|---|
| Apps | 1 private + unlimited public | ✅ One app is enough |
| RAM | 1 GB | ✅ App uses ~250 MB |
| CPU | Shared | ✅ Adequate for occasional use |
| Sleep | After 7 days idle, wakes in ~30s | ✅ Daily use keeps warm |

---

## Option 2: Local hosting on the office computer

**Cost:** Free | **Time:** ~5 minutes | **Best for:** 1–3 users on the same office network, all client data must stay on-premise

### One-time setup

```bash
git clone <your-repo-url>
cd financial-planning-generator
pip install -r requirements.txt
playwright install chromium
```

### Running

```bash
streamlit run financial_planning_app.py --server.address 0.0.0.0
```

Streamlit prints two URLs:
- **Local URL:** `http://localhost:8501` — only on this PC
- **Network URL:** `http://192.168.x.x:8501` — anyone on the office Wi-Fi

Share the Network URL with your team. They open it in their browser; no install needed on their end.

### Auto-start on Windows boot

To keep the app always running:

1. Create `start_app.bat`:

   ```bat
   @echo off
   cd /d "C:\path\to\financial-planning-generator"
   streamlit run financial_planning_app.py --server.address 0.0.0.0 --server.headless true
   ```

2. Press `Win+R`, type `shell:startup`, press Enter
3. Drop `start_app.bat` into the folder that opens
4. Reboot — the app now starts automatically

### Caveats

- The app only works while your PC is on
- If your office router gives the PC a new IP after reboot, the URL changes. Set a static IP on your router for the host PC to fix this.
- Doesn't work for remote employees

---

## Option 3: Hugging Face Spaces

**Cost:** Free | **Time:** ~10 minutes | **Use as backup if Streamlit Cloud has issues**

1. Sign up at https://huggingface.co
2. Click **"New Space"** → choose **"Streamlit"** as the SDK
3. Make it **Private**
4. Upload all repository files
5. Wait for build to finish
6. URL format: `https://huggingface.co/spaces/<your-username>/<space-name>`

Hugging Face provides 16 GB RAM on the free tier, vs. Streamlit Cloud's 1 GB — useful as a fallback.

---

## Which one should you choose?

For an advisor team's internal use:

- **Default choice: Streamlit Community Cloud.** Truly free, real URL, works from any device. The app stores no client data — generated PDFs go straight to the user's browser.
- **Privacy-first alternative: Local on office PC.** Choose this only if your firm has a strict policy against any data passing through external servers, even temporarily.

---

## Upgrading later (if needed)

If you eventually want a custom domain, dedicated resources, or 100+ concurrent users:

| Service | Free | Paid (when needed) |
|---|---|---|
| Streamlit Cloud | 1 private app | "Streamlit for Teams" — overkill for most |
| Render | Sleeps when idle | $7/mo always-on |
| Railway | $5 free credit/month | ~$5/mo for this app |
| Fly.io | 3 free VMs | ~$2–5/mo |

For an advisor team's typical scale, you won't need to upgrade.

---

## Troubleshooting deployment

**"Module not found: playwright" on Streamlit Cloud**
→ Confirm `playwright>=1.40.0` is in `requirements.txt` and was committed to GitHub.

**"Browser executable doesn't exist" on first request**
→ Normal. The auto-install hook in `financial_planning_app.py` runs `playwright install chromium` on first PDF generation. Takes ~30 seconds. Subsequent generations are instant.

**App stuck on "First-time setup" for >2 minutes**
→ The Streamlit Cloud build may have failed silently. Check the deployment logs in the Streamlit Cloud dashboard, then click "Reboot app".

**PDF formatting looks broken**
→ Make sure `packages.txt` is in the repo root and contains all 16 system libraries. These are installed by Streamlit Cloud as `apt-get install` packages before Python deps.

**Logo doesn't appear**
→ Ensure `Logo.jpg` is committed to the repo and not blocked by `.gitignore`. The `.gitignore` shipped here doesn't ignore `Logo.jpg`, but verify with `git status` before pushing.
