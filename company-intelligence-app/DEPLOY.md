# Deploy Company Intelligence Assistant

GitHub Pages cannot run this app because it needs a private `GEMINI_API_KEY`.
Use a backend host such as Render, Railway, Fly.io, Cloud Run, or Vercel serverless.

## Fastest path with Render

1. Create a new Render web service.
2. Connect the repository or upload this project folder.
3. Use:
   - Build command: `python3 -m pip install -r requirements.txt`
   - Start command: `HOST=0.0.0.0 python3 company_research_server.py`
4. Add environment variables:
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL=gemini-2.5-flash`
5. After Render gives a public URL, add that URL to the portfolio project page.

## Why not GitHub Pages only?

The app calls Gemini. Putting the Gemini API key in static JavaScript would expose
the key to every website visitor, so the live searchable version needs a backend.
