# Roshni Portfolio Website

This project now supports two modes:

- local authoring mode with the Python admin dashboard
- GitHub Pages hosting mode with a static export of the public website

## Why there are two modes

GitHub Pages can host only static files. That means the public website can live on GitHub Pages, but the Python admin dashboard cannot run there.

The workflow is:

1. run the local Python app
2. edit content in the admin dashboard
3. generate the static site
4. push the generated files to GitHub

## Local authoring mode

Start the local CMS and preview server:

```bash
python3 server.py
```

Then open:

- public site: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- admin: [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)

The first admin visit will ask you to create a password.

## What you can edit from the dashboard

- profile content for the homepage
- hobbies and personal image cards
- projects
- articles / blog posts
- uploaded media assets

## Build for GitHub Pages

After updating content locally, generate the static site:

```bash
python3 build_static.py
```

This creates or refreshes:

- `index.html`
- `projects/` static pages
- `articles/` static pages
- `uploads/` public image files
- `404.html`
- `sitemap.xml`
- `robots.txt`
- `CNAME`
- `.nojekyll`

## Publish to GitHub

Typical publish flow:

```bash
git add .
git commit -m "Publish portfolio updates"
git push origin main
```

## Markdown support in stories

The story editor supports lightweight Markdown, including:

- headings with `#`, `##`, `###`
- paragraphs
- bullet lists
- numbered lists
- blockquotes with `>`
- code fences with triple backticks
- links with `[text](url)`
- images with `![Alt text](/uploads/file-name.jpg)`

## Data and uploads

When the local app runs, it creates:

- `data/portfolio.db` for content
- `data/uploads/` for uploaded images
- `data/.session_secret` for admin sessions

The `data/` folder stays local. The GitHub Pages site uses the generated static files instead.

## Custom domain

`build_static.py` writes a `CNAME` file for:

```text
roshnibhandula.com
```

After pushing to GitHub, connect your DNS to GitHub Pages in your domain provider and GitHub Pages settings.

## If you want a live online admin dashboard later

Keep the current Python app and move hosting to a Python-friendly platform such as Render, Railway, Fly.io, or a VM. GitHub Pages is excellent for the public site, but not for a live server-backed CMS.
