# Vercel + Firebase Deployment Guide

EduEagle is designed to serve its frontend and Python serverless API on Vercel, using **Firebase Authentication** for identity management.

---

## 1. Firebase Console Configuration

### 1.1 Enable Authentication Providers
1. Go to [Firebase Console](https://console.firebase.google.com/) and open your project (`edu-eagle-dc3af`).
2. Navigate to **Build → Authentication → Sign-in method**.
3. Enable:
   - **Google**: Enable and select your project support email.
   - **Email/Password**: Enable and save.

### 1.2 Authorize Your Vercel Domain (Crucial)
Firebase blocks popups and redirects from domains not on its whitelist:
1. In Firebase Console, go to **Authentication → Settings → Authorized domains**.
2. Click **Add domain**.
3. Add:
   - `localhost` (for local development)
   - `*.vercel.app` or your exact Vercel project domain (e.g., `ai-aces.vercel.app`).
4. Click **Save**.

---

## 2. Deploy Repository to Vercel

1. Push your repository to GitHub.
2. In [Vercel Dashboard](https://vercel.com/):
   - Click **Add New → Project**.
   - Import your GitHub repository.
   - Set **Framework Preset**: `Other`.
   - Leave Root Directory as `./` (where `vercel.json` is located).

---

## 3. Configure Vercel Environment Variables

In **Vercel → Project Settings → Environment Variables**, add the following:

| Variable | Description / Value |
|---|---|
| `FIREBASE_PROJECT_ID` | `edu-eagle-dc3af` |
| `FIREBASE_API_KEY` | `AIzaSyBleX2QL92elVwZO0chnQXh_cKQe4J-jZI` |
| `FIREBASE_AUTH_DOMAIN` | `edu-eagle-dc3af.firebaseapp.com` |
| `FIREBASE_STORAGE_BUCKET` | `edu-eagle-dc3af.firebasestorage.app` |
| `FIREBASE_MESSAGING_SENDER_ID` | `1013380277371` |
| `FIREBASE_APP_ID` | `1:1013380277371:web:fc860eb6b6c2059184aede` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | *(Optional)* Full content of `serviceAccountKey.json` as a single-line JSON string |
| `EDUEAGLE_SECRET_KEY` | 64-character hexadecimal session signing key |
| `EDUEAGLE_DEMO_MODE` | `true` (enables direct roll-number and persona access) |
| `EDUEAGLE_SEED_DEMO_DATA` | `true` (populates baseline academic cohort on cold start) |
| `DATABASE_URL` | *(Optional)* PostgreSQL connection pooler if using Supabase or Neon |

### Generating `EDUEAGLE_SECRET_KEY`:
In PowerShell:
```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
[BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
```

---

## 4. Verification Checklist

1. Open `https://<your-vercel-domain>/api/config` in your browser:
   - Should return HTTP 200 with `firebase_config` containing your Firebase credentials.
2. Open `https://<your-vercel-domain>`:
   - The login screen loads without JavaScript errors in DevTools Console.
   - Click **Sign in with Google**: Firebase OAuth popup appears and signs you into your academic workspace.
   - Test student login with Roll Number `21CS042` or `STU-101`: Signs into Aarav Sharma's dashboard.
   - Test faculty login with `priya.nair@edueagle.edu` or the Dr. Priya Nair persona chip: Signs into the Faculty Portal.
