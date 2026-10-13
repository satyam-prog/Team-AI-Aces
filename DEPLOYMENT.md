# Vercel + Supabase deployment

This project can serve its frontend and Python API on Vercel. Supabase is used
for persistent PostgreSQL data, password authentication, and private artifact
storage. Vercel's local filesystem is temporary and must not be used as the
production database or artifact store.

## 1. Create the Supabase project

1. Create a Supabase project and save its database password securely.
2. In **Project Settings → Database**, copy the **Transaction pooler** connection
   string. Use this for `DATABASE_URL`; it is intended for serverless clients.
   Replace any password placeholder and URL-encode special characters in the
   password.
3. In **Project Settings → API Keys**, copy the project URL, the public/anon
   key, and the `service_role` secret key. The service-role key must only be
   used by the server.
4. In **Storage → New bucket**, create a bucket named `student-artifacts`.
   Keep it **private**. Limit it to 3 MB and allow only PDF, PNG, and JPEG
   files.
5. In **Authentication → Users**, create institution-approved users. The
   Supabase Auth email must also have a matching application profile in the
   `users` table. Students also need a corresponding `students` row with the
   matching email. Public registration and demo sign-in are disabled by
   default on Vercel.

The Python application creates its tables on first startup. Do not run
`supabase_schema.sql` against a database containing data: that legacy script
contains table-drop statements and is not the deployment migration.

## 2. Add the repository to Vercel

1. Push this project to GitHub. In the GitHub **Add .gitignore** menu, choose
   **None** because the repository already contains `.gitignore`.
2. In Vercel, select **Add New → Project**, import the GitHub repository, and
   use the repository root as the **Root Directory** (the folder containing
   `vercel.json`).
3. Leave the Framework Preset as **Other** and do not add a separate build
   command or output directory. The repository's `vercel.json` configures the
   Python function, static files, and routes.

## 3. Configure Vercel environment variables

In **Vercel → Project → Settings → Environment Variables**, add the following.
Select **Production**; also select **Preview** if preview deployments should
connect to a separate/test Supabase project.

| Name | Value to enter |
| --- | --- |
| `DATABASE_URL` | Supabase **Transaction pooler** PostgreSQL connection string |
| `EDUEAGLE_SECRET_KEY` | A newly generated private 64-character hexadecimal value |
| `EDUEAGLE_ENV` | `production` |
| `EDUEAGLE_DEMO_MODE` | `false` |
| `EDUEAGLE_SEED_DEMO_DATA` | `false` |
| `SUPABASE_URL` | Supabase project URL, such as `https://<project-ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase public/anon key, used only for Auth password verification |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase `service_role` secret key; never put this in frontend code or GitHub |
| `SUPABASE_STORAGE_BUCKET` | `student-artifacts` |

Generate `EDUEAGLE_SECRET_KEY` locally in PowerShell. This prints 64 random
hexadecimal characters:

```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
[BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
```

Paste the printed 64-character value as the variable's **Value**, not the
command. Do not send it in chat or add it to GitHub. Never upload `.env`; only
`.env.example` belongs in the repository.

The artifact API caps individual files at 3 MB so the base64-encoded request
fits within Vercel Functions' request-body limit.

After saving the values, redeploy the latest commit from **Vercel → Deployments**.
Vercel does not apply newly added environment variables to an already-built
deployment.

## 4. Check the deployment

- Open the deployment's **Visit** URL. The root URL should show the app.
- Open `<deployment-url>/api/config`; it should return JSON with
  `"demo_auth_enabled": false`.
- Confirm the deployment logs show successful database initialization. If not,
  check that the connection string is the Supabase Transaction pooler URL and
  that all required environment variables are present.
- Test a login with an account created in Supabase Auth and an application
  profile with the same email in `users`. The assigned application role comes
  from that database profile, not from a role supplied by the browser.
- Test an artifact upload and download with a non-sensitive test document.

## Production-use limitation

This repository still contains demo-oriented features and seeded fictional
student records for local evaluation. On Vercel, demo seeding, role-switch
login, public student registration, and simulated OTP login are disabled by
default. The production login path verifies email/password with Supabase Auth,
then looks up the user's role in the application's `users` table.

Do not use this deployment with real student records until the institution has
reviewed the application's privacy, authorization, data-import, audit,
retention, and recovery requirements. Production database setup does not by
itself provide a reviewed student-data import workflow or make every
demo-oriented feature production-safe.
