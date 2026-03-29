<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run the BastionFed frontend

This contains everything you need to run the frontend locally against the unified FastAPI backend.

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Ensure `.env.local` points to the backend:
   `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Run the app:
   `npm run dev`

## BastionBot

The `/bastionbot` page now uses the backend API instead of calling Gemini directly from the browser.

- requires Google sign-in
- uses per-user conversation history and memory
- shows grounded source citations in the UI
