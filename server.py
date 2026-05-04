#!/usr/bin/env python3
from __future__ import annotations

import cgi
import datetime as dt
import hashlib
import hmac
import html
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import textwrap
import time
from http import HTTPStatus, cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("ROSH_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("ROSH_UPLOAD_DIR", DATA_DIR / "uploads"))
DB_PATH = DATA_DIR / "portfolio.db"
SECRET_PATH = DATA_DIR / ".session_secret"
COOKIE_NAME = "rosh_admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
ACCENTS = ("sunrise", "ocean", "forest", "night", "ember")


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                headline TEXT NOT NULL,
                current_role TEXT NOT NULL,
                location TEXT NOT NULL,
                email TEXT NOT NULL,
                linkedin_url TEXT NOT NULL,
                hero_note TEXT NOT NULL,
                about_intro TEXT NOT NULL,
                about_story TEXT NOT NULL,
                about_image TEXT NOT NULL DEFAULT '',
                looking_for TEXT NOT NULL,
                hobbies_intro TEXT NOT NULL,
                now_note TEXT NOT NULL,
                focus_points TEXT NOT NULL,
                roles_of_interest TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hobbies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                accent TEXT NOT NULL DEFAULT 'sunrise',
                image_path TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK (kind IN ('project', 'article')),
                title TEXT NOT NULL,
                slug TEXT NOT NULL,
                summary TEXT NOT NULL,
                body_markdown TEXT NOT NULL,
                accent TEXT NOT NULL DEFAULT 'sunrise',
                cover_image TEXT NOT NULL DEFAULT '',
                published_on TEXT NOT NULL,
                featured INTEGER NOT NULL DEFAULT 0,
                published INTEGER NOT NULL DEFAULT 1,
                read_time TEXT NOT NULL DEFAULT '4 min read',
                tags TEXT NOT NULL DEFAULT '',
                UNIQUE(kind, slug)
            );

            CREATE TABLE IF NOT EXISTS admin_user (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        profile_columns = {row["name"] for row in conn.execute("PRAGMA table_info(profile)").fetchall()}
        if "about_image" not in profile_columns:
            conn.execute("ALTER TABLE profile ADD COLUMN about_image TEXT NOT NULL DEFAULT ''")

        profile_exists = conn.execute("SELECT 1 FROM profile WHERE id = 1").fetchone()
        if not profile_exists:
            conn.execute(
                """
                INSERT INTO profile (
                    id, name, headline, current_role, location, email, linkedin_url,
                    hero_note, about_intro, about_story, about_image, looking_for, hobbies_intro,
                    now_note, focus_points, roles_of_interest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "Roshni Bhandula",
                    "Turning customer, product, and revenue data into clearer business decisions",
                    "Lead Analyst at Cvent",
                    "Jersey City, NJ",
                    "roshnibhandula@gmail.com",
                    "https://www.linkedin.com/in/roshni-bhandula",
                    "I use this portfolio to show how I structure business questions, build analytics frameworks, and translate findings into decisions leaders can act on.",
                    "I am an analytics professional with 6+ years of experience across business intelligence, performance reporting, customer insights, and workflow improvement. At Cvent, I work on turning complex commercial and product data into decisions that improve customer outcomes, team execution, and revenue performance.",
                    "What energizes me most is translating noisy business questions into something decision-ready. I enjoy building analysis frameworks, repeatable reporting, and clear narratives that help stakeholders see what is changing, why it matters, and what to do next. This website is where I turn that work into projects, case studies, and practical reflections.",
                    "",
                    "I am targeting business analytics, business intelligence, customer insights, and strategy-facing roles where I can combine analytical depth with clear stakeholder communication.",
                    "A few interests outside work help me stay observant, communicate more clearly, and keep a balanced perspective.",
                    "Right now, I am refining this portfolio into sharper proof for analytics, BI, and customer insights roles: clearer case studies, better framing, and faster recruiter comprehension.",
                    "Business intelligence and reporting systems\nCustomer and revenue insights\nStructured stakeholder communication\nWorkflow simplification and automation",
                    "Business analytics and business intelligence roles\nCustomer insights and strategy roles\nRevenue, commercial, or performance analytics roles\nOperations and process improvement roles",
                ),
            )

        hobby_count = conn.execute("SELECT COUNT(*) AS count FROM hobbies").fetchone()["count"]
        if hobby_count == 0:
            conn.executemany(
                """
                INSERT INTO hobbies (title, description, accent, image_path, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Weekend Photo Walks",
                        "I enjoy capturing everyday details that usually go unnoticed. It trains my eye for patterns, mood, and the little things that shape a full experience.",
                        "ocean",
                        "",
                        1,
                    ),
                    (
                        "Travel and Local Explorations",
                        "New neighborhoods, hidden cafes, and short trips give me fresh ideas. I love noticing how spaces, service, and storytelling influence how people feel.",
                        "sunrise",
                        "",
                        2,
                    ),
                    (
                        "Reading for Perspective",
                        "I keep returning to books and essays on communication, growth, and work. They help me turn experience into clearer thinking and better decisions.",
                        "forest",
                        "",
                        3,
                    ),
                ],
            )

        entry_count = conn.execute("SELECT COUNT(*) AS count FROM entries").fetchone()["count"]
        if entry_count == 0:
            conn.executemany(
                """
                INSERT INTO entries (
                    kind, title, slug, summary, body_markdown, accent, cover_image,
                    published_on, featured, published, read_time, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "project",
                        "Personal Brand Visibility System",
                        "personal-brand-visibility-system",
                        "A practical system for turning day-to-day work into portfolio stories, reflection notes, and shareable proof of growth.",
                        textwrap.dedent(
                            """
                            ## The idea

                            I wanted a way to make my work more visible without waiting for a major milestone. The goal was simple: capture useful pieces of my day-to-day experience and shape them into something others can understand.

                            ## What I built

                            - A repeatable note-taking rhythm after projects and meetings
                            - A structure for converting work experience into blog-style reflections
                            - A portfolio plan that groups my work into projects, articles, and personal interests

                            ## Why it matters

                            This project is less about self-promotion and more about clarity. It helps me communicate what I am learning, what kinds of problems I enjoy, and how I approach growth.

                            ## Next step

                            I am expanding this system into a living website where each article and project can show both the story and the proof behind it.
                            """
                        ).strip(),
                        "sunrise",
                        "",
                        "2026-04-11",
                        1,
                        1,
                        "5 min read",
                        "career growth, portfolio, personal branding",
                    ),
                    (
                        "project",
                        "Event Workflow Reflection Board",
                        "event-workflow-reflection-board",
                        "An internal thinking exercise for mapping handoffs, communication loops, and execution details that influence experience quality.",
                        textwrap.dedent(
                            """
                            ## Context

                            Event technology work often sits at the intersection of people, tools, and timing. Even small handoff gaps can affect the final experience.

                            ## Focus

                            This reflection board is my way of documenting:

                            - where communication becomes clearer or more complex
                            - where preparation reduces last-minute pressure
                            - where customer-facing quality depends on internal coordination

                            ## Outcome

                            The value of this exercise is in seeing work more systemically. It helps me notice where operational detail and user experience are tightly connected.
                            """
                        ).strip(),
                        "night",
                        "",
                        "2026-04-09",
                        0,
                        1,
                        "4 min read",
                        "event tech, operations, workflow",
                    ),
                    (
                        "article",
                        "What Working in Event Tech Is Teaching Me About Clear Communication",
                        "event-tech-clear-communication",
                        "A reflection on how customer experience, timing, and internal alignment all depend on communication that is both precise and empathetic.",
                        textwrap.dedent(
                            """
                            ## Communication is never just messaging

                            In event technology, communication often becomes the invisible layer that shapes everything else. It affects how smoothly teams coordinate, how clearly customers understand next steps, and how confidently problems get solved.

                            ## What I keep noticing

                            - clear communication reduces uncertainty
                            - timely communication builds trust
                            - empathetic communication changes the tone of a difficult moment

                            ## What this means for my career

                            One of the strengths I want my portfolio to show is that I care about execution and communication together. I do not see them as separate skills.
                            """
                        ).strip(),
                        "ocean",
                        "",
                        "2026-04-08",
                        1,
                        1,
                        "3 min read",
                        "communication, event tech, learning",
                    ),
                    (
                        "article",
                        "Why I Am Documenting My Work in Public",
                        "why-i-am-documenting-my-work",
                        "A note on visibility, confidence, and the importance of making professional growth easier for others to understand.",
                        textwrap.dedent(
                            """
                            ## Visibility matters

                            Many people are doing meaningful work that never becomes visible outside a conversation or a resume bullet. I do not want my learning to stay hidden like that.

                            ## Public documentation changes the game

                            Writing about work pushes me to:

                            - think more clearly
                            - notice patterns faster
                            - explain outcomes in a way that others can follow

                            ## The real goal

                            I am not trying to sound perfect. I am trying to become easier to understand. That feels more honest and more useful for hiring leaders too.
                            """
                        ).strip(),
                        "ember",
                        "",
                        "2026-04-05",
                        0,
                        1,
                        "3 min read",
                        "career, writing, visibility",
                    ),
                ],
            )
        conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_session_secret() -> bytes:
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_PATH.read_text(encoding="utf-8").strip().encode("utf-8")


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, digest_hex: str) -> bool:
    _, calculated = hash_password(password, salt_hex)
    return hmac.compare_digest(calculated, digest_hex)


def create_session_token() -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"1:{expires}"
    signature = hmac.new(load_session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def is_valid_session(token: str | None) -> bool:
    if not token:
        return False
    parts = token.split(":")
    if len(parts) != 3:
        return False
    user_id, expires_text, signature = parts
    if user_id != "1" or not expires_text.isdigit():
        return False
    expected = hmac.new(
        load_session_secret(),
        f"{user_id}:{expires_text}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    return int(expires_text) >= int(time.time())


def admin_configured(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM admin_user WHERE id = 1").fetchone() is not None


def fetch_profile(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return dict(row) if row else {}


def fetch_hobbies(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM hobbies ORDER BY sort_order ASC, id ASC"
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_hobby(conn: sqlite3.Connection, hobby_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM hobbies WHERE id = ?", (hobby_id,)).fetchone()
    return dict(row) if row else None


def fetch_entries(
    conn: sqlite3.Connection,
    *,
    kind: str | None = None,
    published_only: bool = False,
    featured_only: bool = False,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if published_only:
        clauses.append("published = 1")
    if featured_only:
        clauses.append("featured = 1")
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT * FROM entries
        {where_clause}
        ORDER BY featured DESC, published_on DESC, id DESC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_entry_by_slug(conn: sqlite3.Connection, kind: str, slug: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM entries WHERE kind = ? AND slug = ? AND published = 1",
        (kind, slug),
    ).fetchone()
    return dict(row) if row else None


def fetch_entry(conn: sqlite3.Connection, entry_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return dict(row) if row else None


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "entry"


def unique_slug(
    conn: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    provided_slug: str,
    exclude_id: int | None = None,
) -> str:
    base = slugify(provided_slug or title)
    candidate = base
    suffix = 2
    while True:
        if exclude_id is None:
            row = conn.execute(
                "SELECT id FROM entries WHERE kind = ? AND slug = ?",
                (kind, candidate),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM entries WHERE kind = ? AND slug = ? AND id != ?",
                (kind, candidate, exclude_id),
            ).fetchone()
        if row is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value or "")
    except ValueError:
        return default


def parse_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def split_paragraphs(value: str) -> list[str]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", value.strip()) if chunk.strip()]
    return chunks


def format_date(value: str) -> str:
    try:
        date_value = dt.date.fromisoformat(value)
    except ValueError:
        return value
    return date_value.strftime("%B %d, %Y")


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def entry_url(entry: dict) -> str:
    return f"/{'projects' if entry['kind'] == 'project' else 'articles'}/{entry['slug']}"


def safe_join(base: Path, relative: str) -> Path | None:
    normalized = Path(unquote(relative).lstrip("/"))
    candidate = (base / normalized).resolve()
    base_resolved = base.resolve()
    if candidate == base_resolved or base_resolved in candidate.parents:
        return candidate
    return None


def collect_media() -> list[dict]:
    media_items: list[dict] = []
    if not UPLOAD_DIR.exists():
        return media_items
    for path in sorted(UPLOAD_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        media_items.append(
            {
                "name": path.name,
                "url": f"/uploads/{path.name}",
                "size": human_size(stat.st_size),
                "updated_at": dt.datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y %I:%M %p"),
            }
        )
    return media_items


def save_image_upload(field: cgi.FieldStorage | None, prefix: str) -> str:
    if field is None or not getattr(field, "filename", ""):
        return ""
    filename = Path(field.filename).name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Only image uploads are supported.")
    safe_name = slugify(Path(filename).stem)[:48] or prefix
    target = UPLOAD_DIR / f"{prefix}-{safe_name}-{int(time.time())}-{secrets.token_hex(3)}{suffix}"
    total = 0
    with target.open("wb") as output_file:
        while True:
            chunk = field.file.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_SIZE:
                target.unlink(missing_ok=True)
                raise ValueError("Image is too large. Please keep uploads under 10 MB.")
            output_file.write(chunk)
    return f"/uploads/{target.name}"


def delete_media_by_url(url: str) -> None:
    if not url.startswith("/uploads/"):
        return
    path = safe_join(UPLOAD_DIR, url.removeprefix("/uploads/"))
    if path and path.exists():
        path.unlink()


def render_text_block(value: str, class_name: str = "rich-copy") -> str:
    paragraphs = "".join(f"<p>{html.escape(chunk)}</p>" for chunk in split_paragraphs(value))
    return f'<div class="{class_name}">{paragraphs}</div>'


INLINE_PATTERN = re.compile(
    r"!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*"
)
BLOCK_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def external_link_attrs(url: str) -> str:
    return ' target="_blank" rel="noreferrer"' if url.startswith("http") else ""


def render_inline_markdown(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in INLINE_PATTERN.finditer(text):
        parts.append(html.escape(text[cursor:match.start()], quote=False))
        if match.group(1) is not None:
            alt = html.escape(match.group(1), quote=True)
            url = html.escape(match.group(2).strip(), quote=True)
            parts.append(f'<img class="inline-markdown-image" src="{url}" alt="{alt}" loading="lazy">')
        elif match.group(3) is not None:
            label = html.escape(match.group(3), quote=False)
            url = html.escape(match.group(4).strip(), quote=True)
            parts.append(f'<a href="{url}"{external_link_attrs(match.group(4).strip())}>{label}</a>')
        elif match.group(5) is not None:
            parts.append(f"<code>{html.escape(match.group(5), quote=False)}</code>")
        elif match.group(6) is not None:
            parts.append(f"<strong>{html.escape(match.group(6), quote=False)}</strong>")
        elif match.group(7) is not None:
            parts.append(f"<em>{html.escape(match.group(7), quote=False)}</em>")
        cursor = match.end()
    parts.append(html.escape(text[cursor:], quote=False))
    return "".join(parts)


def render_markdown_image(token: str) -> str:
    match = BLOCK_IMAGE_PATTERN.fullmatch(token.strip())
    if not match:
        return f"<p>{render_inline_markdown(token)}</p>"
    alt, url = match.groups()
    alt_text = html.escape(alt, quote=True)
    url_value = html.escape(url.strip(), quote=True)
    caption = f"<figcaption>{html.escape(alt)}</figcaption>" if alt else ""
    return (
        f'<figure class="article-figure"><img src="{url_value}" alt="{alt_text}" '
        f'loading="lazy">{caption}</figure>'
    )


def render_markdown(text: str) -> str:
    if not text.strip():
        return "<p>This section is coming soon.</p>"

    lines = text.replace("\r\n", "\n").split("\n")
    pieces: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None
    quote_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False

    def flush_paragraph() -> None:
        if paragraph:
            pieces.append(f"<p>{render_inline_markdown(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            tag = "ol" if list_kind == "ol" else "ul"
            items_html = "".join(f"<li>{render_inline_markdown(item)}</li>" for item in list_items)
            pieces.append(f"<{tag}>{items_html}</{tag}>")
            list_items.clear()
            list_kind = None

    def flush_quote() -> None:
        if quote_lines:
            quote_html = "<br>".join(render_inline_markdown(line) for line in quote_lines)
            pieces.append(f"<blockquote><p>{quote_html}</p></blockquote>")
            quote_lines.clear()

    for raw_line in lines + [""]:
        stripped = raw_line.strip()

        if in_code_block:
            if stripped.startswith("```"):
                code_html = html.escape("\n".join(code_lines))
                pieces.append(f"<pre><code>{code_html}</code></pre>")
                code_lines.clear()
                in_code_block = False
            else:
                code_lines.append(raw_line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            flush_quote()
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_quote()
            in_code_block = True
            continue

        if stripped == "---":
            flush_paragraph()
            flush_list()
            flush_quote()
            pieces.append("<hr>")
            continue

        if BLOCK_IMAGE_PATTERN.fullmatch(stripped):
            flush_paragraph()
            flush_list()
            flush_quote()
            pieces.append(render_markdown_image(stripped))
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            flush_quote()
            level = len(heading_match.group(1))
            pieces.append(f"<h{level}>{render_inline_markdown(heading_match.group(2))}</h{level}>")
            continue

        quote_match = re.match(r"^>\s?(.*)$", stripped)
        if quote_match:
            flush_paragraph()
            flush_list()
            quote_lines.append(quote_match.group(1))
            continue

        unordered_match = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if unordered_match or ordered_match:
            flush_paragraph()
            flush_quote()
            desired_kind = "ol" if ordered_match else "ul"
            item_text = ordered_match.group(1) if ordered_match else unordered_match.group(1)
            if list_kind and list_kind != desired_kind:
                flush_list()
            list_kind = desired_kind
            list_items.append(item_text)
            continue

        flush_list()
        flush_quote()
        paragraph.append(stripped)

    if in_code_block and code_lines:
        code_html = html.escape("\n".join(code_lines))
        pieces.append(f"<pre><code>{code_html}</code></pre>")

    return "\n".join(pieces)


def render_cover(title: str, accent: str, image_path: str, label: str) -> str:
    if image_path:
        return (
            f'<div class="cover-media"><img src="{html.escape(image_path, quote=True)}" '
            f'alt="{html.escape(title, quote=True)}" loading="lazy"></div>'
        )
    initials = "".join(chunk[0] for chunk in title.split()[:2]).upper() or "RB"
    return (
        f'<div class="cover-placeholder tone-{html.escape(accent, quote=True)}">'
        f'<span class="cover-pill">{html.escape(label)}</span>'
        f'<strong>{html.escape(initials)}</strong>'
        f"<p>{html.escape(title)}</p>"
        f"</div>"
    )


def render_entry_card(entry: dict) -> str:
    tags = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in parse_csv(entry["tags"]))
    meta = f"{format_date(entry['published_on'])} • {html.escape(entry['read_time'])}"
    label = "Project" if entry["kind"] == "project" else "Article"
    live_action = ""
    if entry["slug"] == "company-intelligence-assistant":
        live_action = """
            <div class="story-card__actions">
                <a class="button" href="https://company-intelligence-assistant.onrender.com/" target="_blank" rel="noreferrer">Launch Live App</a>
            </div>
        """
    return textwrap.dedent(
        f"""
        <article class="story-card reveal" data-reveal>
            <a class="story-card__link" href="{entry_url(entry)}">
                {render_cover(entry["title"], entry["accent"], entry["cover_image"], label)}
                <div class="story-card__content">
                    <div class="eyebrow">{label}</div>
                    <h3>{html.escape(entry["title"])}</h3>
                    <p>{html.escape(entry["summary"])}</p>
                    <div class="story-meta">{meta}</div>
                    <div class="tag-row">{tags}</div>
                </div>
            </a>{live_action}
        </article>
        """
    ).strip()


def render_hobby_card(hobby: dict) -> str:
    media_html = (
        f'<img src="{html.escape(hobby["image_path"], quote=True)}" alt="{html.escape(hobby["title"], quote=True)}" loading="lazy">'
        if hobby["image_path"]
        else (
            f'<div class="hobby-placeholder tone-{html.escape(hobby["accent"], quote=True)}">'
            f"<span>Hobby</span><strong>{html.escape(hobby['title'])}</strong></div>"
        )
    )
    description_html = (
        f"<p>{render_inline_markdown(hobby['description'])}</p>"
        if hobby["description"].strip()
        else ""
    )
    return textwrap.dedent(
        f"""
        <article class="hobby-card reveal" data-reveal>
            <div class="hobby-card__media">{media_html}</div>
            <div class="hobby-card__content">
                <h3>{html.escape(hobby["title"])}</h3>
                {description_html}
            </div>
        </article>
        """
    ).strip()


def parse_csv(value: str) -> list[str]:
    return [chunk.strip() for chunk in value.split(",") if chunk.strip()]


def selected(value: str, expected: str) -> str:
    return " selected" if value == expected else ""


def checked(value: bool) -> str:
    return " checked" if value else ""


def public_navigation(active: str) -> str:
    items = [
        ("Home", "/", "home"),
        ("Projects", "/projects", "projects"),
        ("Insights", "/articles", "articles"),
        ("About", "/#about", "about"),
        ("Contact", "/#contact", "contact"),
    ]
    links = []
    for label, url, key in items:
        class_name = "nav-link active" if active == key else "nav-link"
        links.append(f'<a class="{class_name}" href="{url}">{label}</a>')
    return "".join(links)


def page_shell(title: str, body: str, *, active: str, description: str, admin_view: bool = False) -> str:
    header = (
        '<header class="site-header">'
        '<div class="brand"><a href="/">RB</a></div>'
        f'<nav class="site-nav">{public_navigation(active)}</nav>'
        "</header>"
        if not admin_view
        else ""
    )
    admin_class = " admin-view" if admin_view else ""
    script = textwrap.dedent(
        """
        <script>
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-visible');
            }
          });
        }, { threshold: 0.12 });

        document.querySelectorAll('[data-reveal]').forEach((node) => observer.observe(node));
        const params = new URLSearchParams(window.location.search);
        const editorSelector = params.has('edit_entry') ? '#story-editor' : params.has('edit_hobby') ? '#hobby-editor' : '';
        if (editorSelector) {
          const editor = document.querySelector(editorSelector);
          const firstField = editor?.querySelector('input[name="title"], textarea[name="description"], textarea[name="body_markdown"]');
          if (editor) {
            requestAnimationFrame(() => {
              editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
              if (firstField) {
                firstField.focus({ preventScroll: true });
                if (typeof firstField.select === 'function') {
                  firstField.select();
                }
              }
            });
          }
        }
        </script>
        """
    )
    return textwrap.dedent(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>{html.escape(title)}</title>
            <meta name="description" content="{html.escape(description, quote=True)}">
            <link rel="stylesheet" href="/static/style.css">
        </head>
        <body class="site-body{admin_class}">
            <div class="ambient ambient-one"></div>
            <div class="ambient ambient-two"></div>
            {header}
            <main class="page-main">{body}</main>
            {script}
        </body>
        </html>
        """
    )


def render_home(profile: dict, hobbies: list[dict], projects: list[dict], articles: list[dict]) -> str:
    focus_items = parse_lines(profile["focus_points"])
    role_items = parse_lines(profile["roles_of_interest"])
    focus_html = "".join(
        (
            '<div class="focus-card reveal" data-reveal>'
            f'<span class="focus-index">0{index + 1}</span>'
            f"<h3>{html.escape(item)}</h3>"
            f"<p>{html.escape(item)} delivered through structured analysis, stakeholder alignment, and decision-ready communication.</p>"
            "</div>"
        )
        for index, item in enumerate(focus_items)
    )
    roles_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in role_items
    )
    role_pills = "".join(f'<span class="tag">{html.escape(item)}</span>' for item in role_items)
    hobbies_html = "".join(render_hobby_card(hobby) for hobby in hobbies)
    project_cards = "".join(render_entry_card(entry) for entry in projects[:2])
    article_cards = "".join(render_entry_card(entry) for entry in articles[:2])
    summary_cards = [
        ("Experience", "6+ years across BI, reporting, and insights"),
        ("Current Role", profile["current_role"]),
        ("Core Strength", "Turning analysis into clear stakeholder decisions"),
        ("Base", profile["location"]),
    ]
    summary_html = "".join(
        (
            '<div class="summary-card reveal" data-reveal>'
            f'<span class="summary-card__label">{html.escape(label)}</span>'
            f"<strong>{html.escape(value)}</strong>"
            "</div>"
        )
        for label, value in summary_cards
    )
    about_image_html = (
        '<div class="about-portrait reveal" data-reveal>'
        f'<img src="{html.escape(profile["about_image"], quote=True)}" alt="{html.escape(profile["name"], quote=True)} portrait" loading="lazy">'
        "</div>"
        if profile.get("about_image")
        else ""
    )
    article_heading = "Writing that shows how I frame and communicate the work"
    article_empty = (
        '<div class="empty-state">Writing samples will appear here as they are published.</div>'
        if not article_cards
        else ""
    )
    body = textwrap.dedent(
        f"""
        <section class="hero-section">
            <div class="hero-shell">
                <div class="hero-copy reveal is-visible" data-reveal>
                    <div class="eyebrow">Analytics Portfolio</div>
                    <h1>{html.escape(profile["headline"])}</h1>
                    <p class="hero-lead">{html.escape(profile["hero_note"])}</p>
                    <div class="hero-meta">
                        <span>{html.escape(profile["name"])}</span>
                        <span>{html.escape(profile["current_role"])}</span>
                        <span>{html.escape(profile["location"])}</span>
                    </div>
                    <div class="hero-actions">
                        <a class="button" href="/projects">View Projects</a>
                        <a class="button button--secondary" href="/articles">Read Insights</a>
                    </div>
                </div>
                <aside class="hero-aside">
                    <div class="hero-panel reveal" data-reveal>
                        <div class="hero-panel__label">Current Focus</div>
                        <p>{html.escape(profile["now_note"])}</p>
                        <div class="tag-row">{role_pills}</div>
                    </div>
                    <div class="hero-panel hero-panel--compact reveal" data-reveal>
                        <div class="hero-panel__label">What You Will Find Here</div>
                        <p>Selected case studies, applied analytics thinking, and portfolio-ready proof for business intelligence, customer insights, and strategy-facing roles.</p>
                        <a class="inline-link" href="#featured-work">Start with featured work</a>
                    </div>
                </aside>
            </div>
            <div class="summary-strip">{summary_html}</div>
        </section>

        <section class="content-section" id="featured-work">
            <div class="section-heading reveal" data-reveal>
                <div class="eyebrow">Featured Case Studies</div>
                <h2>Selected work that shows how I approach analytics and decisions</h2>
                <p>These projects are the fastest way to understand how I frame questions, structure analysis, and turn findings into action.</p>
            </div>
            <div class="story-grid">{project_cards}</div>
            <div class="section-link-row"><a class="inline-link" href="/projects">Browse all projects</a></div>
        </section>

        <section id="about" class="content-section content-section--split">
            <div class="about-intro-stack">
                <div class="section-heading reveal" data-reveal>
                    <div class="eyebrow">Professional Overview</div>
                    <h2>{html.escape(profile["name"])}</h2>
                    <p>{html.escape(profile["about_intro"])}</p>
                </div>
                {about_image_html}
            </div>
            <div class="section-copy reveal" data-reveal>
                {render_text_block(profile["about_story"])}
                <div class="callout-card">
                    <span class="eyebrow">Target Roles</span>
                    <p>{html.escape(profile["looking_for"])}</p>
                    <div class="tag-row">{role_pills}</div>
                </div>
            </div>
        </section>

        <section class="content-section">
            <div class="section-heading reveal" data-reveal>
                <div class="eyebrow">Capabilities</div>
                <h2>How I tend to create value</h2>
                <p>The common thread across my work is turning ambiguity into structure, then using that structure to help teams move with more clarity.</p>
            </div>
            <div class="focus-grid">{focus_html}</div>
        </section>

        <section class="content-section">
            <div class="section-heading reveal" data-reveal>
                <div class="eyebrow">Role Alignment</div>
                <h2>Where this portfolio is strongest</h2>
            </div>
            <div class="opportunity-card reveal" data-reveal>
                <ul class="opportunity-list">{roles_html}</ul>
            </div>
        </section>

        <section class="content-section">
            <div class="section-heading reveal" data-reveal>
                <div class="eyebrow">Writing & Communication</div>
                <h2>{article_heading}</h2>
                <p>Strong analysis travels further when it is explained well. These pieces show how I translate observations into clear, useful narratives.</p>
            </div>
            <div class="story-grid">{article_cards or article_empty}</div>
            <div class="section-link-row"><a class="inline-link" href="/articles">Browse all insights</a></div>
        </section>

        <section id="hobbies" class="content-section">
            <div class="section-heading reveal" data-reveal>
                <div class="eyebrow">Outside Work</div>
                <h2>Interests that sharpen perspective beyond the dashboard</h2>
                <p>{html.escape(profile["hobbies_intro"])}</p>
            </div>
            <div class="hobby-grid hobby-grid--compact">{hobbies_html}</div>
        </section>

        <section id="contact" class="content-section content-section--cta">
            <div class="cta-panel reveal" data-reveal>
                <div>
                    <div class="eyebrow">Let’s Connect</div>
                    <h2>If you are hiring in analytics, business intelligence, or customer insights, I would love to connect.</h2>
                </div>
                <div class="cta-links">
                    <a class="button" href="mailto:{html.escape(profile["email"], quote=True)}">Email Me</a>
                    <a class="button button--secondary" href="{html.escape(profile["linkedin_url"], quote=True)}" target="_blank" rel="noreferrer">LinkedIn</a>
                </div>
            </div>
        </section>
        """
    )
    return page_shell(
        f"{profile['name']} | Portfolio",
        body,
        active="home",
        description=profile["hero_note"],
    )


def render_story_listing(profile: dict, title: str, description: str, entries: list[dict], active: str) -> str:
    cards = "".join(render_entry_card(entry) for entry in entries)
    empty_state = ""
    if not cards:
        empty_state = '<div class="empty-state">No stories are published here yet.</div>'
    if active == "projects":
        eyebrow = "Selected Work"
        panel_label = "Recruiter View"
        panel_copy = (
            "These case studies are designed to make it easy for hiring teams to see how I approach business questions, KPI design, workflow analysis, and stakeholder-ready recommendations."
        )
        cta_heading = "Looking for analytics work that pairs rigor with clarity?"
        cta_secondary = "Email"
        cta_secondary_href = f'mailto:{html.escape(profile["email"], quote=True)}'
        cta_secondary_attrs = ""
    else:
        eyebrow = "Insights & Writing"
        panel_label = "What This Shows"
        panel_copy = (
            "These articles show how I explain ambiguity, connect details to larger business context, and communicate with enough clarity for cross-functional stakeholders."
        )
        cta_heading = "Want a clearer view of how I think and communicate?"
        cta_secondary = "LinkedIn"
        cta_secondary_href = html.escape(profile["linkedin_url"], quote=True)
        cta_secondary_attrs = ' target="_blank" rel="noreferrer"'
    body = textwrap.dedent(
        f"""
        <section class="listing-hero listing-hero--split">
            <div class="reveal is-visible" data-reveal>
                <div class="eyebrow">{eyebrow}</div>
                <h1>{html.escape(title)}</h1>
                <p>{html.escape(description)}</p>
            </div>
            <aside class="listing-panel reveal" data-reveal>
                <div class="hero-panel__label">{panel_label}</div>
                <p>{panel_copy}</p>
            </aside>
        </section>
        <section class="content-section">
            <div class="story-grid">{cards or empty_state}</div>
        </section>
        <section class="content-section content-section--cta">
            <div class="cta-panel reveal" data-reveal>
                <div>
                    <div class="eyebrow">Continue The Conversation</div>
                    <h2>{cta_heading}</h2>
                </div>
                <div class="cta-links">
                    <a class="button" href="/">Back Home</a>
                    <a class="button button--secondary" href="{cta_secondary_href}"{cta_secondary_attrs}>{cta_secondary}</a>
                </div>
            </div>
        </section>
        """
    )
    return page_shell(
        f"{title} | {profile['name']}",
        body,
        active=active,
        description=description,
    )


def render_story_detail(profile: dict, entry: dict) -> str:
    tags = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in parse_csv(entry["tags"]))
    breadcrumb_parent = "/projects" if entry["kind"] == "project" else "/articles"
    breadcrumb_label = "Projects" if entry["kind"] == "project" else "Insights"
    related_href = "/articles" if entry["kind"] == "project" else "/projects"
    related_label = "Read related insights" if entry["kind"] == "project" else "Browse related case studies"
    role_copy = (
        "This project reflects the kind of role I am targeting: work that requires clear problem framing, analytical depth, and communication that helps teams act."
        if entry["kind"] == "project"
        else "This article reflects how I communicate analytical thinking, explain tradeoffs, and make complex work easier for others to understand."
    )
    live_project_tile = ""
    live_sidecard = ""
    if entry["slug"] == "company-intelligence-assistant":
        live_project_tile = """
        <section class="live-project-tile">
            <div>
                <div class="eyebrow">Live App</div>
                <h2>Try the Company Intelligence Assistant</h2>
                <p>Search any company and download an AI-generated Company Intelligence Snapshot as a PowerPoint deck.</p>
            </div>
            <a class="button" href="https://company-intelligence-assistant.onrender.com/" target="_blank" rel="noreferrer">Launch Live App</a>
        </section>
        """
        live_sidecard = """
                <div class="detail-sidecard__group live-sidecard">
                    <div class="eyebrow">Live App</div>
                    <h3>Use the tool</h3>
                    <p>Open the live Render app to search any company and export the result as a PPT deck.</p>
                    <a class="button" href="https://company-intelligence-assistant.onrender.com/" target="_blank" rel="noreferrer">Launch Live App</a>
                </div>
        """
    body = textwrap.dedent(
        f"""
        <section class="detail-hero">
            <div class="breadcrumb"><a href="/">Home</a> / <a href="{breadcrumb_parent}">{breadcrumb_label}</a></div>
            <div class="detail-hero__grid">
                <div class="detail-hero__copy">
                    <div class="eyebrow">{'Project' if entry['kind'] == 'project' else 'Article'}</div>
                    <h1>{html.escape(entry["title"])}</h1>
                    <p class="hero-lead">{html.escape(entry["summary"])}</p>
                    <div class="story-meta">{format_date(entry["published_on"])} • {html.escape(entry["read_time"])}</div>
                    <div class="tag-row">{tags}</div>
                </div>
                <div class="detail-cover">
                    {render_cover(entry["title"], entry["accent"], entry["cover_image"], breadcrumb_label[:-1])}
                </div>
            </div>
        </section>{live_project_tile}
        <section class="detail-layout">
            <article class="article-body">
                {render_markdown(entry["body_markdown"])}
            </article>
            <aside class="detail-sidecard">{live_sidecard}
                <div class="detail-sidecard__group">
                    <div class="eyebrow">Why This Matters</div>
                    <p>{role_copy}</p>
                    <div class="tag-row">{tags}</div>
                </div>
                <div class="detail-sidecard__group">
                    <div class="eyebrow">Continue Exploring</div>
                    <a class="inline-link" href="{related_href}">{related_label}</a>
                    <a class="inline-link" href="{html.escape(profile["linkedin_url"], quote=True)}" target="_blank" rel="noreferrer">Connect on LinkedIn</a>
                </div>
            </aside>
        </section>
        """
    )
    return page_shell(
        f"{entry['title']} | {profile['name']}",
        body,
        active="projects" if entry["kind"] == "project" else "articles",
        description=entry["summary"],
    )


def render_admin_header() -> str:
    return textwrap.dedent(
        """
        <header class="admin-header">
            <div>
                <div class="eyebrow">Admin Dashboard</div>
                <h1>Content manager</h1>
            </div>
            <div class="admin-header__actions">
                <a class="button button--secondary" href="/" target="_blank" rel="noreferrer">View Site</a>
                <form method="post" action="/admin/logout">
                    <button class="button" type="submit">Log Out</button>
                </form>
            </div>
        </header>
        """
    ).strip()


def render_flash(flash: str | None, error: str | None) -> str:
    notices = []
    if flash:
        notices.append(f'<div class="notice notice--success">{html.escape(flash)}</div>')
    if error:
        notices.append(f'<div class="notice notice--error">{html.escape(error)}</div>')
    return "".join(notices)


def render_admin_dashboard(conn: sqlite3.Connection, query: dict[str, list[str]]) -> str:
    profile = fetch_profile(conn)
    hobbies = fetch_hobbies(conn)
    entries = fetch_entries(conn)
    edit_hobby = fetch_hobby(conn, safe_int(query.get("edit_hobby", ["0"])[0])) if query.get("edit_hobby") else None
    edit_entry = fetch_entry(conn, safe_int(query.get("edit_entry", ["0"])[0])) if query.get("edit_entry") else None
    flash = query.get("flash", [None])[0]
    error = query.get("error", [None])[0]
    published_entries = [entry for entry in entries if entry["published"]]
    unpublished_entries = [entry for entry in entries if not entry["published"]]
    media_items = collect_media()

    hobby_form = render_hobby_form(edit_hobby)
    entry_form = render_entry_form(edit_entry)
    hobby_editor_class = " section-card--editing" if edit_hobby else ""
    entry_editor_class = " section-card--editing" if edit_entry else ""
    existing_hobbies = (
        "".join(render_hobby_admin_card(hobby, active_id=edit_hobby["id"] if edit_hobby else None) for hobby in hobbies)
        or '<div class="empty-state">No hobbies added yet.</div>'
    )
    existing_entries = (
        "".join(render_entry_admin_card(entry, active_id=edit_entry["id"] if edit_entry else None) for entry in entries)
        or '<div class="empty-state">No stories created yet.</div>'
    )
    media_grid = "".join(render_media_card(item) for item in media_items) or '<div class="empty-state">No images uploaded yet.</div>'

    body = textwrap.dedent(
        f"""
        <div class="admin-shell">
            {render_admin_header()}
            {render_flash(flash, error)}

            <section class="dashboard-metrics">
                <div class="metric-card">
                    <span>Published Stories</span>
                    <strong>{len(published_entries)}</strong>
                </div>
                <div class="metric-card">
                    <span>Draft / Hidden</span>
                    <strong>{len(unpublished_entries)}</strong>
                </div>
                <div class="metric-card">
                    <span>Hobbies</span>
                    <strong>{len(hobbies)}</strong>
                </div>
                <div class="metric-card">
                    <span>Uploaded Images</span>
                    <strong>{len(media_items)}</strong>
                </div>
            </section>

            <section id="profile" class="admin-section">
                <div class="section-heading section-heading--tight">
                    <div class="eyebrow">Profile</div>
                    <h2>Public intro and positioning</h2>
                </div>
                <div class="section-card">
                    <p class="admin-note">
                        Seed content here is intentionally editable. I could not reliably verify your exact LinkedIn profile from public search results, so I shaped the starting copy around your Cvent background and your goal of becoming more visible to hiring leaders.
                    </p>
                    {render_profile_form(profile)}
                </div>
            </section>

            <section id="hobbies" class="admin-section admin-section--split">
                <div>
                    <div class="section-heading section-heading--tight">
                        <div class="eyebrow">Hobbies</div>
                        <h2>Add personal moments and images</h2>
                    </div>
                    <div id="hobby-editor" class="section-card section-card--editor{hobby_editor_class}">{hobby_form}</div>
                </div>
                <div>
                    <div class="section-heading section-heading--tight">
                        <div class="eyebrow">Current Hobby Cards</div>
                        <h2>What visitors see today</h2>
                    </div>
                    <div class="admin-list">{existing_hobbies}</div>
                </div>
            </section>

            <section id="stories" class="admin-section admin-section--split">
                <div>
                    <div class="section-heading section-heading--tight">
                        <div class="eyebrow">Stories</div>
                        <h2>Projects and blog posts</h2>
                    </div>
                    <div id="story-editor" class="section-card section-card--editor{entry_editor_class}">{entry_form}</div>
                </div>
                <div>
                    <div class="section-heading section-heading--tight">
                        <div class="eyebrow">Library</div>
                        <h2>Existing content</h2>
                    </div>
                    <div class="admin-list">{existing_entries}</div>
                </div>
            </section>

            <section id="media" class="admin-section">
                <div class="section-heading section-heading--tight">
                    <div class="eyebrow">Media</div>
                    <h2>Upload images once and reuse them across your site</h2>
                </div>
                <div class="section-card">
                    <form class="stack-form" method="post" action="/admin/media/upload" enctype="multipart/form-data">
                        <label>
                            <span>Upload one or more images</span>
                            <input type="file" name="media_files" accept="image/*" multiple>
                        </label>
                        <button class="button" type="submit">Upload</button>
                        <p class="field-help">After uploading, use the file URL in a blog post with Markdown like <code>![Alt text](/uploads/your-file.jpg)</code>.</p>
                    </form>
                </div>
                <div class="media-grid">{media_grid}</div>
            </section>
        </div>
        """
    )
    return page_shell(
        "Admin Dashboard | Roshni Portfolio",
        body,
        active="",
        description="Admin dashboard",
        admin_view=True,
    )


def render_profile_form(profile: dict) -> str:
    return textwrap.dedent(
        f"""
        <form class="stack-form" method="post" action="/admin/profile">
            <div class="form-grid">
                <label><span>Name</span><input type="text" name="name" value="{html.escape(profile['name'], quote=True)}" required></label>
                <label><span>Current role</span><input type="text" name="current_role" value="{html.escape(profile['current_role'], quote=True)}" required></label>
                <label><span>Location</span><input type="text" name="location" value="{html.escape(profile['location'], quote=True)}" required></label>
                <label><span>Email</span><input type="email" name="email" value="{html.escape(profile['email'], quote=True)}" required></label>
                <label class="full-span"><span>LinkedIn URL</span><input type="url" name="linkedin_url" value="{html.escape(profile['linkedin_url'], quote=True)}" required></label>
                <label class="full-span"><span>Headline</span><input type="text" name="headline" value="{html.escape(profile['headline'], quote=True)}" required></label>
                <label class="full-span"><span>Hero note</span><textarea name="hero_note" rows="3" required>{html.escape(profile['hero_note'])}</textarea></label>
                <label class="full-span"><span>About intro</span><textarea name="about_intro" rows="4" required>{html.escape(profile['about_intro'])}</textarea></label>
                <label class="full-span"><span>About story</span><textarea name="about_story" rows="6" required>{html.escape(profile['about_story'])}</textarea></label>
                <label class="full-span"><span>About image URL</span><input type="text" name="about_image" value="{html.escape(profile.get('about_image', ''), quote=True)}" placeholder="/uploads/profile-image.jpg"></label>
                <label class="full-span"><span>Looking for</span><textarea name="looking_for" rows="4" required>{html.escape(profile['looking_for'])}</textarea></label>
                <label class="full-span"><span>Hobbies intro</span><textarea name="hobbies_intro" rows="3" required>{html.escape(profile['hobbies_intro'])}</textarea></label>
                <label class="full-span"><span>Current focus note</span><textarea name="now_note" rows="3" required>{html.escape(profile['now_note'])}</textarea></label>
                <label><span>Focus points</span><textarea name="focus_points" rows="5" required>{html.escape(profile['focus_points'])}</textarea></label>
                <label><span>Roles of interest</span><textarea name="roles_of_interest" rows="5" required>{html.escape(profile['roles_of_interest'])}</textarea></label>
            </div>
            <button class="button" type="submit">Save Profile</button>
        </form>
        """
    ).strip()


def render_hobby_form(hobby: dict | None) -> str:
    hobby = hobby or {
        "id": "",
        "title": "",
        "description": "",
        "accent": "sunrise",
        "image_path": "",
        "sort_order": len(ACCENTS),
    }
    is_editing = bool(hobby.get("id"))
    title = f'Editing hobby: {hobby["title"]}' if is_editing else "Add a hobby"
    intro = (
        '<p class="editor-status">You are updating this hobby card now. Change the fields below, then save to publish the update.</p>'
        if is_editing
        else '<p class="editor-status">Add a title, short description, and optional image to create a new hobby card.</p>'
    )
    cancel_link = '<a class="inline-link" href="/admin#hobby-editor">Cancel editing</a>' if is_editing else ""
    image_preview = (
        f'<div class="image-preview"><img src="{html.escape(hobby["image_path"], quote=True)}" alt="{html.escape(hobby["title"], quote=True)}"></div>'
        if hobby["image_path"]
        else ""
    )
    remove_button = (
        '<label class="checkbox-row"><input type="checkbox" name="remove_image" value="1"> Remove current image</label>'
        if hobby["image_path"]
        else ""
    )
    return textwrap.dedent(
        f"""
        <div class="editor-toolbar">
            <div class="form-title">{html.escape(title)}</div>
            {cancel_link}
        </div>
        {intro}
        <form class="stack-form" method="post" action="/admin/hobbies/save" enctype="multipart/form-data">
            <input type="hidden" name="id" value="{html.escape(str(hobby['id']), quote=True)}">
            <input type="hidden" name="existing_image_path" value="{html.escape(hobby['image_path'], quote=True)}">
            <label><span>Title</span><input type="text" name="title" value="{html.escape(hobby['title'], quote=True)}" required{' autofocus' if is_editing else ''}></label>
            <label><span>Description</span><textarea name="description" rows="4" required>{html.escape(hobby['description'])}</textarea></label>
            <div class="form-grid">
                <label>
                    <span>Accent</span>
                    <select name="accent">
                        {accent_options(hobby["accent"])}
                    </select>
                </label>
                <label>
                    <span>Sort order</span>
                    <input type="number" name="sort_order" value="{html.escape(str(hobby['sort_order']), quote=True)}">
                </label>
            </div>
            <label><span>Upload image</span><input type="file" name="image_file" accept="image/*"></label>
            {image_preview}
            {remove_button}
            <button class="button" type="submit">{'Update Hobby' if is_editing else 'Add Hobby'}</button>
        </form>
        """
    ).strip()


def render_entry_form(entry: dict | None) -> str:
    entry = entry or {
        "id": "",
        "kind": "project",
        "title": "",
        "slug": "",
        "summary": "",
        "body_markdown": "",
        "accent": "sunrise",
        "cover_image": "",
        "published_on": dt.date.today().isoformat(),
        "featured": 0,
        "published": 1,
        "read_time": "4 min read",
        "tags": "",
    }
    is_editing = bool(entry.get("id"))
    story_kind = entry["kind"].title()
    title = f'Editing {story_kind}: {entry["title"]}' if is_editing else "Add a project or article"
    intro = (
        f'<p class="editor-status">This {html.escape(entry["kind"])} is loaded into the editor. Update the content below, then click save.</p>'
        if is_editing
        else '<p class="editor-status">Choose project or article, write your story, and save when you are ready to publish it.</p>'
    )
    cancel_link = '<a class="inline-link" href="/admin#story-editor">Cancel editing</a>' if is_editing else ""
    image_preview = (
        f'<div class="image-preview"><img src="{html.escape(entry["cover_image"], quote=True)}" alt="{html.escape(entry["title"], quote=True)}"></div>'
        if entry["cover_image"]
        else ""
    )
    remove_button = (
        '<label class="checkbox-row"><input type="checkbox" name="remove_cover" value="1"> Remove current cover image</label>'
        if entry["cover_image"]
        else ""
    )
    return textwrap.dedent(
        f"""
        <div class="editor-toolbar">
            <div class="form-title">{html.escape(title)}</div>
            {cancel_link}
        </div>
        {intro}
        <form class="stack-form" method="post" action="/admin/entries/save" enctype="multipart/form-data">
            <input type="hidden" name="id" value="{html.escape(str(entry['id']), quote=True)}">
            <input type="hidden" name="existing_cover_image" value="{html.escape(entry['cover_image'], quote=True)}">
            <div class="form-grid">
                <label>
                    <span>Type</span>
                    <select name="kind">
                        <option value="project"{selected(entry["kind"], "project")}>Project</option>
                        <option value="article"{selected(entry["kind"], "article")}>Article</option>
                    </select>
                </label>
                <label>
                    <span>Published date</span>
                    <input type="date" name="published_on" value="{html.escape(entry['published_on'], quote=True)}" required>
                </label>
                <label class="full-span">
                    <span>Title</span>
                    <input type="text" name="title" value="{html.escape(entry['title'], quote=True)}" required{' autofocus' if is_editing else ''}>
                </label>
                <label>
                    <span>Slug</span>
                    <input type="text" name="slug" value="{html.escape(entry['slug'], quote=True)}" placeholder="auto-generated-if-left-blank">
                </label>
                <label>
                    <span>Read time</span>
                    <input type="text" name="read_time" value="{html.escape(entry['read_time'], quote=True)}" required>
                </label>
                <label class="full-span">
                    <span>Summary</span>
                    <textarea name="summary" rows="3" required>{html.escape(entry['summary'])}</textarea>
                </label>
                <label>
                    <span>Accent</span>
                    <select name="accent">
                        {accent_options(entry["accent"])}
                    </select>
                </label>
                <label>
                    <span>Tags</span>
                    <input type="text" name="tags" value="{html.escape(entry['tags'], quote=True)}" placeholder="comma, separated, tags">
                </label>
                <label class="full-span">
                    <span>Body (Markdown supported)</span>
                    <textarea name="body_markdown" rows="14" required>{html.escape(entry['body_markdown'])}</textarea>
                </label>
                <label class="full-span">
                    <span>Cover image</span>
                    <input type="file" name="cover_file" accept="image/*">
                </label>
                <div class="checkbox-group full-span">
                    <label class="checkbox-row"><input type="checkbox" name="featured" value="1"{checked(bool(entry["featured"]))}> Featured on the homepage</label>
                    <label class="checkbox-row"><input type="checkbox" name="published" value="1"{checked(bool(entry["published"]))}> Visible on the public website</label>
                </div>
            </div>
            {image_preview}
            {remove_button}
            <p class="field-help">Tip: you can upload images in the Media section, then insert them into the body with <code>![Alt text](/uploads/file-name.jpg)</code>.</p>
            <button class="button" type="submit">{'Update Story' if is_editing else 'Create Story'}</button>
        </form>
        """
    ).strip()


def accent_options(current: str) -> str:
    labels = {
        "sunrise": "Sunrise",
        "ocean": "Ocean",
        "forest": "Forest",
        "night": "Night",
        "ember": "Ember",
    }
    return "".join(
        f'<option value="{accent}"{selected(current, accent)}>{label}</option>'
        for accent, label in labels.items()
    )


def render_hobby_admin_card(hobby: dict, active_id: int | None = None) -> str:
    media = (
        f'<img src="{html.escape(hobby["image_path"], quote=True)}" alt="{html.escape(hobby["title"], quote=True)}">'
        if hobby["image_path"]
        else f'<div class="mini-placeholder tone-{html.escape(hobby["accent"], quote=True)}">{html.escape(hobby["title"][:2].upper())}</div>'
    )
    active_class = " is-active" if active_id == hobby["id"] else ""
    return textwrap.dedent(
        f"""
        <article class="admin-item-card{active_class}">
            <div class="admin-item-card__media">{media}</div>
            <div class="admin-item-card__content">
                <h3>{html.escape(hobby["title"])}</h3>
                <p>{html.escape(hobby["description"])}</p>
                <div class="admin-actions">
                    <form method="get" action="/admin">
                        <input type="hidden" name="edit_hobby" value="{hobby['id']}">
                        <button class="link-button" type="submit">Edit</button>
                    </form>
                    <form method="post" action="/admin/hobbies/delete" onsubmit="return confirm('Delete this hobby?');">
                        <input type="hidden" name="id" value="{hobby['id']}">
                        <button class="ghost-button" type="submit">Delete</button>
                    </form>
                </div>
            </div>
        </article>
        """
    ).strip()


def render_entry_admin_card(entry: dict, active_id: int | None = None) -> str:
    badge = "Featured" if entry["featured"] else "Standard"
    visibility = "Visible" if entry["published"] else "Hidden"
    active_class = " is-active" if active_id == entry["id"] else ""
    return textwrap.dedent(
        f"""
        <article class="admin-item-card admin-item-card--story{active_class}">
            <div class="mini-placeholder tone-{html.escape(entry["accent"], quote=True)}">
                {html.escape(entry["kind"][0].upper())}
            </div>
            <div class="admin-item-card__content">
                <div class="admin-item-card__topline">
                    <span class="pill">{html.escape(entry["kind"].title())}</span>
                    <span class="pill pill--muted">{badge}</span>
                    <span class="pill pill--muted">{visibility}</span>
                </div>
                <h3>{html.escape(entry["title"])}</h3>
                <p>{html.escape(entry["summary"])}</p>
                <div class="story-meta">{format_date(entry["published_on"])} • {html.escape(entry["read_time"])}</div>
                <div class="admin-actions">
                    <a class="inline-link" href="{entry_url(entry)}" target="_blank" rel="noreferrer">Open</a>
                    <form method="get" action="/admin">
                        <input type="hidden" name="edit_entry" value="{entry['id']}">
                        <button class="link-button" type="submit">Edit</button>
                    </form>
                    <form method="post" action="/admin/entries/delete" onsubmit="return confirm('Delete this story?');">
                        <input type="hidden" name="id" value="{entry['id']}">
                        <button class="ghost-button" type="submit">Delete</button>
                    </form>
                </div>
            </div>
        </article>
        """
    ).strip()


def render_media_card(item: dict) -> str:
    return textwrap.dedent(
        f"""
        <article class="media-card">
            <img src="{html.escape(item["url"], quote=True)}" alt="{html.escape(item["name"], quote=True)}" loading="lazy">
            <div class="media-card__content">
                <strong>{html.escape(item["name"])}</strong>
                <div class="story-meta">{html.escape(item["size"])} • {html.escape(item["updated_at"])}</div>
                <code>{html.escape(item["url"])}</code>
                <form method="post" action="/admin/media/delete" onsubmit="return confirm('Delete this image?');">
                    <input type="hidden" name="url" value="{html.escape(item["url"], quote=True)}">
                    <button class="ghost-button" type="submit">Delete</button>
                </form>
            </div>
        </article>
        """
    ).strip()


def render_login_page(error: str | None = None) -> str:
    notice = f'<div class="notice notice--error">{html.escape(error)}</div>' if error else ""
    body = textwrap.dedent(
        f"""
        <section class="auth-shell">
            <div class="auth-card reveal is-visible" data-reveal>
                <div class="eyebrow">Admin Login</div>
                <h1>Welcome back</h1>
                <p>Sign in to update your homepage, upload images, and publish new projects or articles.</p>
                {notice}
                <form class="stack-form" method="post" action="/admin/login">
                    <label><span>Password</span><input type="password" name="password" required></label>
                    <button class="button" type="submit">Log In</button>
                </form>
            </div>
        </section>
        """
    )
    return page_shell("Admin Login", body, active="", description="Admin login", admin_view=True)


def render_setup_page(error: str | None = None) -> str:
    notice = f'<div class="notice notice--error">{html.escape(error)}</div>' if error else ""
    body = textwrap.dedent(
        f"""
        <section class="auth-shell">
            <div class="auth-card reveal is-visible" data-reveal>
                <div class="eyebrow">First Time Setup</div>
                <h1>Create your admin password</h1>
                <p>This password protects the dashboard where you manage profile content, hobbies, stories, and media.</p>
                {notice}
                <form class="stack-form" method="post" action="/admin/setup">
                    <label><span>Password</span><input type="password" name="password" minlength="8" required></label>
                    <label><span>Confirm password</span><input type="password" name="confirm_password" minlength="8" required></label>
                    <button class="button" type="submit">Create Password</button>
                </form>
            </div>
        </section>
        """
    )
    return page_shell("Admin Setup", body, active="", description="Admin setup", admin_view=True)


def render_not_found() -> str:
    body = textwrap.dedent(
        """
        <section class="listing-hero">
            <div class="eyebrow">404</div>
            <h1>That page does not exist.</h1>
            <p>The link may be outdated, or the content may have been unpublished.</p>
            <div class="hero-actions">
                <a class="button" href="/">Back Home</a>
                <a class="button button--secondary" href="/articles">Read Insights</a>
            </div>
        </section>
        """
    )
    return page_shell("Page Not Found", body, active="", description="Page not found")


def parse_form_value(form: cgi.FieldStorage | dict[str, list[str]], key: str, default: str = "") -> str:
    if isinstance(form, cgi.FieldStorage):
        value = form.getfirst(key, default)
    else:
        values = form.get(key, [default])
        value = values[0] if values else default
    return (value or default).strip()


def parse_form_file(form: cgi.FieldStorage | dict[str, list[str]], key: str) -> cgi.FieldStorage | None:
    if not isinstance(form, cgi.FieldStorage):
        return None
    if key not in form:
        return None
    item = form[key]
    if isinstance(item, list):
        for candidate in item:
            if getattr(candidate, "filename", ""):
                return candidate
        return None
    return item if getattr(item, "filename", "") else None


def parse_form_files(form: cgi.FieldStorage | dict[str, list[str]], key: str) -> list[cgi.FieldStorage]:
    if not isinstance(form, cgi.FieldStorage) or key not in form:
        return []
    item = form[key]
    candidates = item if isinstance(item, list) else [item]
    return [candidate for candidate in candidates if getattr(candidate, "filename", "")]


class PortfolioHandler(BaseHTTPRequestHandler):
    server_version = "RoshniPortfolio/1.0"

    def do_GET(self) -> None:
        self._head_only = False
        self.dispatch_request()

    def do_POST(self) -> None:
        self._head_only = False
        self.dispatch_request()

    def do_HEAD(self) -> None:
        self._head_only = True
        self.dispatch_request()

    def log_message(self, format: str, *args: object) -> None:
        return

    def dispatch_request(self) -> None:
        ensure_storage()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path.startswith("/static/"):
            return self.serve_file(STATIC_DIR, path.removeprefix("/static/"))
        if path.startswith("/uploads/"):
            return self.serve_file(UPLOAD_DIR, path.removeprefix("/uploads/"))

        if self.command in {"GET", "HEAD"}:
            return self.handle_get(path, query)
        if self.command == "POST":
            return self.handle_post(path)
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def handle_get(self, path: str, query: dict[str, list[str]]) -> None:
        with get_connection() as conn:
            profile = fetch_profile(conn)

            if path == "/":
                projects = fetch_entries(conn, kind="project", published_only=True, featured_only=True) or fetch_entries(
                    conn, kind="project", published_only=True
                )
                articles = fetch_entries(conn, kind="article", published_only=True, featured_only=True) or fetch_entries(
                    conn, kind="article", published_only=True
                )
                self.send_html(render_home(profile, fetch_hobbies(conn), projects, articles))
                return

            if path == "/projects":
                entries = fetch_entries(conn, kind="project", published_only=True)
                self.send_html(
                    render_story_listing(
                        profile,
                        "Projects",
                        "A place to explain what I am building, what I am learning, and how I approach real work.",
                        entries,
                        "projects",
                    )
                )
                return

            if path == "/articles":
                entries = fetch_entries(conn, kind="article", published_only=True)
                self.send_html(
                    render_story_listing(
                        profile,
                        "Articles",
                        "Writing that helps hiring leaders see how I think, communicate, and grow through work.",
                        entries,
                        "articles",
                    )
                )
                return

            if path.startswith("/projects/"):
                slug = path.split("/", 2)[2]
                entry = fetch_entry_by_slug(conn, "project", slug)
                if entry:
                    self.send_html(render_story_detail(profile, entry))
                else:
                    self.send_html(render_not_found(), status=HTTPStatus.NOT_FOUND)
                return

            if path.startswith("/articles/"):
                slug = path.split("/", 2)[2]
                entry = fetch_entry_by_slug(conn, "article", slug)
                if entry:
                    self.send_html(render_story_detail(profile, entry))
                else:
                    self.send_html(render_not_found(), status=HTTPStatus.NOT_FOUND)
                return

            if path in {"/admin", "/admin/login", "/admin/setup"}:
                configured = admin_configured(conn)
                authed = self.is_authenticated()
                if not configured:
                    self.send_html(render_setup_page(query.get("error", [None])[0]))
                    return
                if not authed and path != "/admin/login":
                    self.redirect("/admin/login")
                    return
                if not authed:
                    self.send_html(render_login_page(query.get("error", [None])[0]))
                    return
                self.send_html(render_admin_dashboard(conn, query))
                return

            self.send_html(render_not_found(), status=HTTPStatus.NOT_FOUND)

    def handle_post(self, path: str) -> None:
        form = self.parse_form_data()
        with get_connection() as conn:
            configured = admin_configured(conn)

            if path == "/admin/setup":
                if configured:
                    self.redirect("/admin/login")
                    return
                password = parse_form_value(form, "password")
                confirm_password = parse_form_value(form, "confirm_password")
                if len(password) < 8:
                    self.redirect("/admin/setup?error=" + quote_plus("Please use at least 8 characters."))
                    return
                if password != confirm_password:
                    self.redirect("/admin/setup?error=" + quote_plus("Passwords did not match."))
                    return
                salt, digest = hash_password(password)
                conn.execute(
                    "INSERT OR REPLACE INTO admin_user (id, salt, password_hash, created_at) VALUES (1, ?, ?, ?)",
                    (salt, digest, dt.datetime.utcnow().isoformat(timespec="seconds")),
                )
                conn.commit()
                self.redirect(
                    "/admin?flash=" + quote_plus("Password created. Dashboard is ready."),
                    session_token=create_session_token(),
                )
                return

            if path == "/admin/login":
                if not configured:
                    self.redirect("/admin/setup")
                    return
                password = parse_form_value(form, "password")
                row = conn.execute("SELECT salt, password_hash FROM admin_user WHERE id = 1").fetchone()
                if not row or not verify_password(password, row["salt"], row["password_hash"]):
                    self.redirect("/admin/login?error=" + quote_plus("Incorrect password."))
                    return
                self.redirect("/admin", session_token=create_session_token())
                return

            if path == "/admin/logout":
                self.redirect("/admin/login", clear_session=True)
                return

            if not self.is_authenticated():
                self.redirect("/admin/login?error=" + quote_plus("Please log in first."))
                return

            if path == "/admin/profile":
                conn.execute(
                    """
                    UPDATE profile SET
                        name = ?, headline = ?, current_role = ?, location = ?, email = ?, linkedin_url = ?,
                        hero_note = ?, about_intro = ?, about_story = ?, about_image = ?, looking_for = ?, hobbies_intro = ?,
                        now_note = ?, focus_points = ?, roles_of_interest = ?
                    WHERE id = 1
                    """,
                    (
                        parse_form_value(form, "name"),
                        parse_form_value(form, "headline"),
                        parse_form_value(form, "current_role"),
                        parse_form_value(form, "location"),
                        parse_form_value(form, "email"),
                        parse_form_value(form, "linkedin_url"),
                        parse_form_value(form, "hero_note"),
                        parse_form_value(form, "about_intro"),
                        parse_form_value(form, "about_story"),
                        parse_form_value(form, "about_image"),
                        parse_form_value(form, "looking_for"),
                        parse_form_value(form, "hobbies_intro"),
                        parse_form_value(form, "now_note"),
                        parse_form_value(form, "focus_points"),
                        parse_form_value(form, "roles_of_interest"),
                    ),
                )
                conn.commit()
                self.redirect("/admin?flash=" + quote_plus("Profile updated.") + "#profile")
                return

            if path == "/admin/hobbies/save":
                hobby_id = safe_int(parse_form_value(form, "id"), 0)
                existing_image = parse_form_value(form, "existing_image_path")
                image_path = existing_image
                if parse_form_value(form, "remove_image") == "1":
                    image_path = ""
                upload = parse_form_file(form, "image_file")
                if upload is not None:
                    try:
                        image_path = save_image_upload(upload, "hobby")
                    except ValueError as exc:
                        self.redirect("/admin?error=" + quote_plus(str(exc)) + "#hobbies")
                        return

                payload = (
                    parse_form_value(form, "title"),
                    parse_form_value(form, "description"),
                    normalize_accent(parse_form_value(form, "accent")),
                    image_path,
                    safe_int(parse_form_value(form, "sort_order"), 0),
                )

                if hobby_id:
                    conn.execute(
                        """
                        UPDATE hobbies
                        SET title = ?, description = ?, accent = ?, image_path = ?, sort_order = ?
                        WHERE id = ?
                        """,
                        (*payload, hobby_id),
                    )
                    message = "Hobby updated."
                else:
                    conn.execute(
                        """
                        INSERT INTO hobbies (title, description, accent, image_path, sort_order)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        payload,
                    )
                    message = "Hobby added."
                conn.commit()
                self.redirect("/admin?flash=" + quote_plus(message) + "#hobbies")
                return

            if path == "/admin/hobbies/delete":
                conn.execute("DELETE FROM hobbies WHERE id = ?", (safe_int(parse_form_value(form, "id")),))
                conn.commit()
                self.redirect("/admin?flash=" + quote_plus("Hobby deleted.") + "#hobbies")
                return

            if path == "/admin/entries/save":
                entry_id = safe_int(parse_form_value(form, "id"), 0)
                kind = parse_form_value(form, "kind")
                if kind not in {"project", "article"}:
                    self.redirect("/admin?error=" + quote_plus("Choose either project or article.") + "#stories")
                    return

                existing_cover = parse_form_value(form, "existing_cover_image")
                cover_image = existing_cover
                if parse_form_value(form, "remove_cover") == "1":
                    cover_image = ""
                upload = parse_form_file(form, "cover_file")
                if upload is not None:
                    try:
                        cover_image = save_image_upload(upload, kind)
                    except ValueError as exc:
                        self.redirect("/admin?error=" + quote_plus(str(exc)) + "#stories")
                        return

                slug = unique_slug(
                    conn,
                    kind=kind,
                    title=parse_form_value(form, "title"),
                    provided_slug=parse_form_value(form, "slug"),
                    exclude_id=entry_id or None,
                )
                payload = (
                    kind,
                    parse_form_value(form, "title"),
                    slug,
                    parse_form_value(form, "summary"),
                    parse_form_value(form, "body_markdown"),
                    normalize_accent(parse_form_value(form, "accent")),
                    cover_image,
                    parse_form_value(form, "published_on") or dt.date.today().isoformat(),
                    1 if parse_form_value(form, "featured") == "1" else 0,
                    1 if parse_form_value(form, "published") == "1" else 0,
                    parse_form_value(form, "read_time") or "4 min read",
                    parse_form_value(form, "tags"),
                )

                if entry_id:
                    conn.execute(
                        """
                        UPDATE entries
                        SET kind = ?, title = ?, slug = ?, summary = ?, body_markdown = ?, accent = ?, cover_image = ?,
                            published_on = ?, featured = ?, published = ?, read_time = ?, tags = ?
                        WHERE id = ?
                        """,
                        (*payload, entry_id),
                    )
                    message = "Story updated."
                else:
                    conn.execute(
                        """
                        INSERT INTO entries (
                            kind, title, slug, summary, body_markdown, accent, cover_image,
                            published_on, featured, published, read_time, tags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        payload,
                    )
                    message = "Story created."
                conn.commit()
                self.redirect("/admin?flash=" + quote_plus(message) + "#stories")
                return

            if path == "/admin/entries/delete":
                conn.execute("DELETE FROM entries WHERE id = ?", (safe_int(parse_form_value(form, "id")),))
                conn.commit()
                self.redirect("/admin?flash=" + quote_plus("Story deleted.") + "#stories")
                return

            if path == "/admin/media/upload":
                files = parse_form_files(form, "media_files")
                if not files:
                    self.redirect("/admin?error=" + quote_plus("Choose at least one image.") + "#media")
                    return
                for file_item in files:
                    try:
                        save_image_upload(file_item, "media")
                    except ValueError as exc:
                        self.redirect("/admin?error=" + quote_plus(str(exc)) + "#media")
                        return
                self.redirect("/admin?flash=" + quote_plus("Images uploaded.") + "#media")
                return

            if path == "/admin/media/delete":
                delete_media_by_url(parse_form_value(form, "url"))
                self.redirect("/admin?flash=" + quote_plus("Image deleted.") + "#media")
                return

        self.send_error(HTTPStatus.NOT_FOUND)

    def parse_form_data(self) -> cgi.FieldStorage | dict[str, list[str]]:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" in content_type:
            return cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
                keep_blank_values=True,
            )
        content_length = safe_int(self.headers.get("Content-Length"), 0)
        body = self.rfile.read(content_length).decode("utf-8")
        return parse_qs(body, keep_blank_values=True)

    def is_authenticated(self) -> bool:
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return False
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
        morsel = jar.get(COOKIE_NAME)
        return is_valid_session(morsel.value if morsel else None)

    def serve_file(self, base: Path, relative_path: str) -> None:
        candidate = safe_join(base, relative_path)
        if not candidate or not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(str(candidate))
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(data)

    def send_html(self, html_body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = html_body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(encoded)

    def redirect(
        self,
        location: str,
        *,
        session_token: str | None = None,
        clear_session: bool = False,
    ) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        if session_token is not None:
            self.send_header(
                "Set-Cookie",
                (
                    f"{COOKIE_NAME}={session_token}; Path=/; HttpOnly; SameSite=Lax; "
                    f"Max-Age={SESSION_TTL_SECONDS}"
                ),
            )
        if clear_session:
            self.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}=deleted; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
            )
        self.end_headers()


def normalize_accent(value: str) -> str:
    return value if value in ACCENTS else "sunrise"


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    ensure_storage()
    server = ThreadingHTTPServer((host, port), PortfolioHandler)
    print(f"Serving on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    host = os.environ.get("ROSH_HOST", "127.0.0.1")
    port = safe_int(os.environ.get("ROSH_PORT"), 8000)
    run_server(host=host, port=port)
