# JobOS Resume Builder v2.0 — Render Deployment Setup Guide

This guide is for the person hosting the app. Complete every section before the app goes live.
End users only need an email address to log in — this setup is your job, not theirs.

---

## What You Need (Accounts + Keys)

| Service | What For | Where to Get It |
|---|---|---|
| GitHub | Host the code | github.com |
| Render | Host the app | render.com |
| Google AI Studio | Gemini Flash (resume parsing) | aistudio.google.com → Get API Key |
| Anthropic | Claude Sonnet (resume rewriting) | console.anthropic.com → API Keys |
| Gmail | OTP delivery to users | Your Gmail account + App Password |
| Razorpay | Payment collection | dashboard.razorpay.com |

---

## Step 1 — Generate Your Secrets (Do This First, Locally)

You need three generated values before you touch Render. Run these on your machine.

### 1a. SESSION_SECRET

A random 32-character string used to sign session tokens.

```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

Copy the output. This is your `SESSION_SECRET`.

### 1b. ENCRYPTION_KEY

A Fernet symmetric key used to encrypt your SMTP password at rest.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output. This is your `ENCRYPTION_KEY`. **Never regenerate this key after launch** — it will corrupt all stored encrypted data.

### 1c. SMTP_PASSWORD_ENCRYPTED

Your Gmail App Password, encrypted with the key from Step 1b.

First, generate a Gmail App Password:
- Google Account → Security → 2-Step Verification → App Passwords
- Create one named "JobOS Resume Builder"
- Copy the 16-character password

Then encrypt it:

```bash
python -c "
from cryptography.fernet import Fernet
key = 'PASTE_YOUR_ENCRYPTION_KEY_HERE'
password = 'PASTE_YOUR_16_CHAR_APP_PASSWORD_HERE'
f = Fernet(key.encode())
print(f.encrypt(password.encode()).decode())
"
```

Copy the output. This is your `SMTP_PASSWORD_ENCRYPTED`.

---

## Step 2 — Get Your API Keys

### Anthropic (Claude Sonnet — resume rewriting)
1. Go to console.anthropic.com → API Keys → Create Key
2. Copy the key (starts with `sk-ant-`)

### Google AI Studio (Gemini Flash — resume parsing)
1. Go to aistudio.google.com → Get API Key → Create API Key
2. Copy the key

### Razorpay (Payment collection)
1. Go to dashboard.razorpay.com → Settings → API Keys → Generate Test Key Pair
2. Copy both `Key ID` (starts with `rzp_test_`) and `Key Secret`
3. When ready for live payments: generate a Live Key Pair and swap them

---

## Step 3 — Deploy on Render

### 3a. Push your code to GitHub
```bash
git push origin feature/phase-02-upload-parse
```

### 3b. Create the Render service
1. Go to dashboard.render.com → New → Web Service
2. Connect GitHub → select your `resume-builder-v2` repo
3. Render detects `render.yaml` automatically → click **Apply**
4. It will read the service config (Docker, standard plan, 1 GB disk at `/app/data`)

### 3c. Set secret environment variables in Render dashboard

`render.yaml` pre-fills the non-secret values. You must manually add the secrets below.

Go to your service → **Environment** tab → add each variable:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key (`sk-ant-...`) |
| `GEMINI_API_KEY` | Your Gemini API key |
| `DEEPSEEK_API_KEY` | Your DeepSeek key (optional — only if you switch `LLM_REWRITE_PROVIDER=deepseek`) |
| `SESSION_SECRET` | Output from Step 1a |
| `ENCRYPTION_KEY` | Output from Step 1b |
| `SMTP_USER` | Your Gmail address (`you@gmail.com`) |
| `SMTP_PASSWORD_ENCRYPTED` | Output from Step 1c |
| `RAZORPAY_KEY_ID` | Your Razorpay Key ID |
| `RAZORPAY_KEY_SECRET` | Your Razorpay Key Secret |
| `APP_BASE_URL` | Leave blank for now — set after first deploy (Step 4) |

Click **Save Changes** → Render will redeploy.

---

## Step 4 — Set APP_BASE_URL After First Deploy

Once Render finishes the first deploy, it assigns you a URL like:
```
https://jobos-resume-builder.onrender.com
```

Go back to Environment tab → set:

| Variable | Value |
|---|---|
| `APP_BASE_URL` | `https://your-service-name.onrender.com` (no trailing slash) |

Save → Render redeploys. This is required for Razorpay payment callbacks to work.

---

## Step 5 — Verify the Deploy

1. Open your Render URL in a browser
2. You should see the Login page
3. Enter your own email → you should receive an OTP within 30 seconds
4. Log in → go through Upload → Review → Download flow end-to-end with a test resume

If OTP email does not arrive: check SMTP_USER and SMTP_PASSWORD_ENCRYPTED are correct.

---

## Environment Variables — Full Reference

### Pre-filled by render.yaml (no action needed)

| Variable | Value | Notes |
|---|---|---|
| `LLM_REWRITE_PROVIDER` | `claude` | Claude Sonnet as primary rewriter |
| `LLM_EXTRACT_PROVIDER` | `gemini` | Gemini Flash as primary parser |
| `LLM_REWRITE_MODEL` | `claude-sonnet-4-6` | |
| `GEMINI_EXTRACT_MODEL` | `gemini-2.0-flash` | |
| `PAYMENT_PROVIDER` | `razorpay` | |
| `RESUME_DOWNLOAD_PRICE_INR` | `99` | Change if needed |
| `AUTH_DB_PATH` | `/app/data/resume_builder.db` | Persists on the 1 GB disk |
| `SOURCE_FOLDER` | `/app/data/input` | |
| `DEST_FOLDER` | `/app/data/output` | |
| `SMTP_HOST` | `smtp.gmail.com` | |
| `SMTP_PORT` | `587` | |
| `OTP_EXPIRY_MINUTES` | `10` | |
| `SESSION_EXPIRY_HOURS` | `24` | |
| `MAX_REVISIONS` | `3` | Max rewrites per session |
| `LOG_LEVEL` | `INFO` | |

### You must set these in the Render dashboard

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | |
| `GEMINI_API_KEY` | Yes | |
| `SESSION_SECRET` | Yes | Generate once — do not rotate after launch |
| `ENCRYPTION_KEY` | Yes | Generate once — **never** rotate after launch |
| `SMTP_USER` | Yes | Gmail address |
| `SMTP_PASSWORD_ENCRYPTED` | Yes | Fernet-encrypted Gmail App Password |
| `RAZORPAY_KEY_ID` | Yes | |
| `RAZORPAY_KEY_SECRET` | Yes | |
| `APP_BASE_URL` | Yes | Set after first deploy |
| `DEEPSEEK_API_KEY` | No | Only if switching rewrite provider to DeepSeek |

---

## Switching LLM Providers (Optional)

To switch the rewrite engine from Claude to DeepSeek:
- Set `LLM_REWRITE_PROVIDER=deepseek` in Render dashboard
- Ensure `DEEPSEEK_API_KEY` is set

To switch the extract engine from Gemini to Claude Haiku:
- Set `LLM_EXTRACT_PROVIDER=claude` in Render dashboard

No code changes required — provider routing is handled entirely by env vars.

---

## Cost Reference (Per 1,000 Candidates Processed)

| Stack | Cost |
|---|---|
| Gemini Flash (extract) + Claude Sonnet (rewrite) | ~$110 |
| Gemini Flash (extract) + DeepSeek V3 (rewrite) | ~$9 |

The default stack (Gemini + Claude) prioritises quality. Switch to DeepSeek if cost is a concern.

---

## Disk and Data

- All data (SQLite DB, uploaded files, generated PDFs) lives on the Render persistent disk at `/app/data`
- Disk size: 1 GB (standard plan)
- If you delete the Render service, the disk and all data are lost — export the DB first if needed

---

## Common Issues

**OTP not arriving**
- Check `SMTP_USER` is correct
- Verify `SMTP_PASSWORD_ENCRYPTED` was generated with the same `ENCRYPTION_KEY` that is set in Render
- Gmail must have 2FA enabled and an App Password used (not your regular password)

**Payment callback not working**
- `APP_BASE_URL` must be set to exactly your Render URL with no trailing slash
- Use Razorpay Test keys during testing, Live keys for real payments

**App crashes on start**
- Check Render logs → usually a missing required env var
- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `SESSION_SECRET`, and `ENCRYPTION_KEY` are the most commonly missed

**Slow first load**
- Standard plan cold starts can take 30–60 seconds after inactivity
- Render keeps the service warm on paid plans — this is normal behaviour
