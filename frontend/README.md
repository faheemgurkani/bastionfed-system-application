<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run the BastionFed frontend

This contains everything you need to run the frontend locally against the unified FastAPI backend.

## Run Locally

**Prerequisites:** Node.js 18+

1. Copy env template: `cp .env.example .env.local` (or obtain `.env.local` from the frontend lead)
2. Set `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Install and run:

```bash
npm install
npm run dev
```

Full stack setup: [SETUP_GUIDE.md](../SETUP_GUIDE.md)

## BastionBot

The `/bastionbot` page now uses the backend API instead of calling Gemini directly from the browser.

- requires Google sign-in
- uses per-user conversation history and memory
- shows grounded source citations in the UI

## Production vs dev mode

- **Dev mode** on the home page (`Continue in dev mode`) only works when the backend has `DEMO_MODE=1`. It uses the read-only **demo tenant** — no real customer data, no BastionBot mutations.
- **Production sign-in** (Google or Firebase email/password) uses your configured Firebase project and real tenant data. Enable **Email/Password** in the Firebase console for invited client users.
