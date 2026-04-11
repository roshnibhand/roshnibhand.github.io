#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import xml.sax.saxutils as xml_utils
from pathlib import Path

import server


BASE_DIR = Path(__file__).resolve().parent
SITE_URL = os.environ.get("SITE_URL", "https://roshnibhandula.com").rstrip("/")
GENERATED_DIRS = ["projects", "articles", "uploads", "admin"]
GENERATED_FILES = ["index.html", "404.html", "robots.txt", "sitemap.xml", "CNAME", ".nojekyll"]


def reset_generated_output() -> None:
    for relative in GENERATED_DIRS:
        target = BASE_DIR / relative
        if target.exists():
            shutil.rmtree(target)
    for relative in GENERATED_FILES:
        target = BASE_DIR / relative
        if target.exists():
            target.unlink()


def write_file(relative_path: str, content: str) -> None:
    target = BASE_DIR / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def write_binary_file(relative_path: str, source_path: Path) -> None:
    target = BASE_DIR / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)


def page_url(relative_path: str) -> str:
    if relative_path in {"index.html", ""}:
        return SITE_URL + "/"
    return f"{SITE_URL}/{relative_path.removesuffix('index.html').rstrip('/')}/"


def build_sitemap(entries: list[dict]) -> str:
    urls = [
        ("index.html", None),
        ("projects/index.html", None),
        ("articles/index.html", None),
    ]
    for entry in entries:
        relative = f"{'projects' if entry['kind'] == 'project' else 'articles'}/{entry['slug']}/index.html"
        urls.append((relative, entry["published_on"]))

    url_nodes = []
    for relative, lastmod in urls:
        loc = xml_utils.escape(page_url(relative))
        node = f"  <url><loc>{loc}</loc>"
        if lastmod:
            node += f"<lastmod>{xml_utils.escape(lastmod)}</lastmod>"
        node += "</url>"
        url_nodes.append(node)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_nodes)
        + "\n</urlset>\n"
    )


def copy_uploads() -> None:
    if not server.UPLOAD_DIR.exists():
        return
    for file_path in server.UPLOAD_DIR.iterdir():
        if not file_path.is_file():
            continue
        write_binary_file(f"uploads/{file_path.name}", file_path)


def build_static_site() -> None:
    server.ensure_storage()
    reset_generated_output()

    with server.get_connection() as conn:
        profile = server.fetch_profile(conn)
        hobbies = server.fetch_hobbies(conn)
        projects = server.fetch_entries(conn, kind="project", published_only=True)
        articles = server.fetch_entries(conn, kind="article", published_only=True)
        featured_projects = server.fetch_entries(conn, kind="project", published_only=True, featured_only=True) or projects
        featured_articles = server.fetch_entries(conn, kind="article", published_only=True, featured_only=True) or articles

        write_file("index.html", server.render_home(profile, hobbies, featured_projects, featured_articles))
        write_file(
            "projects/index.html",
            server.render_story_listing(
                profile,
                "Projects",
                "A place to explain what I am building, what I am learning, and how I approach real work.",
                projects,
                "projects",
            ),
        )
        write_file(
            "articles/index.html",
            server.render_story_listing(
                profile,
                "Articles",
                "Writing that helps hiring leaders see how I think, communicate, and grow through work.",
                articles,
                "articles",
            ),
        )

        all_entries = [*projects, *articles]
        for entry in all_entries:
            folder = "projects" if entry["kind"] == "project" else "articles"
            write_file(f"{folder}/{entry['slug']}/index.html", server.render_story_detail(profile, entry))

    admin_stub = server.page_shell(
        "Admin Unavailable Online",
        """
        <section class="auth-shell">
            <div class="auth-card reveal is-visible" data-reveal>
                <div class="eyebrow">Local Editing</div>
                <h1>The admin dashboard does not run on GitHub Pages.</h1>
                <p>To update this site, run the local Python app on your machine, edit content at <code>/admin</code>, then rebuild and push the static files to GitHub.</p>
            </div>
        </section>
        """,
        active="",
        description="Local-only admin dashboard",
        admin_view=True,
    )
    write_file("admin/index.html", admin_stub)
    write_file("404.html", server.render_not_found())
    write_file(".nojekyll", "")
    write_file("CNAME", "roshnibhandula.com\n")
    write_file("robots.txt", f"Sitemap: {SITE_URL}/sitemap.xml\n")
    write_file("sitemap.xml", build_sitemap([*projects, *articles]))
    copy_uploads()

    print("Static site generated for GitHub Pages.")


if __name__ == "__main__":
    build_static_site()
