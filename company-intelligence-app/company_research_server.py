from __future__ import annotations

import html
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Sequence

from company_research_deck import build_company_research_pptx, slugify_filename
from company_research_engine import Filing, FinancialMetric, NewsItem, ResearchReport, research_company


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT") or os.environ.get("COMPANY_RESEARCH_PORT", "8010"))


def escape(text: str) -> str:
    return html.escape(text or "", quote=True)


def render_financials(metrics: Sequence[FinancialMetric]) -> str:
    if not metrics:
        return "<p class=\"muted\">No standardized financial metrics were returned.</p>"
    return "".join(
        f"""
        <tr>
          <td>{escape(metric.label)}</td>
          <td>{escape(metric.value)}</td>
          <td>{escape(metric.fiscal_period)}</td>
          <td>{escape(metric.filed)}</td>
        </tr>
        """
        for metric in metrics
    )


def render_filings(filings: Sequence[Filing]) -> str:
    if not filings:
        return "<p class=\"muted\">No recent 10-K, 10-Q, 8-K, or proxy filings were returned.</p>"
    return "".join(
        f"""
        <li>
          <a href="{escape(filing.url)}" target="_blank" rel="noreferrer">{escape(filing.form)}</a>
          <span>{escape(filing.filed)}</span>
          <small>Report date: {escape(filing.report_date or "n/a")}</small>
        </li>
        """
        for filing in filings
    )


def render_news(news_items: Sequence[NewsItem]) -> str:
    if not news_items:
        return "<p class=\"muted\">No recent RSS headlines were returned.</p>"
    return "".join(
        f"""
        <li>
          <a href="{escape(item.link)}" target="_blank" rel="noreferrer">{escape(item.title)}</a>
          <small>{escape(item.published)}</small>
        </li>
        """
        for item in news_items
    )


def render_notes(notes: Sequence[str]) -> str:
    if not notes:
        return ""
    return "<div class=\"notice\">" + "".join(f"<p>{escape(note)}</p>" for note in notes) + "</div>"


def render_sections(report: ResearchReport) -> str:
    if not report.sections:
        return f"""
        <section class="panel wide">
          <div class="panel-title">
            <h3>AI-generated snapshot</h3>
            <button type="button" onclick="copyBrief()">Copy snapshot</button>
          </div>
          <pre id="brief-output">{escape(report.ai_summary or report.fallback_summary)}</pre>
        </section>
        """

    cards = []
    for section in report.sections:
        cards.append(
            f"""
            <section class="panel question-card">
              <p class="section-label">{escape(section.short_label)}</p>
              <h3>{escape(section.question)}</h3>
              <p>{escape(section.answer)}</p>
            </section>
            """
        )
    return "".join(cards)


def build_result(report: ResearchReport) -> str:
    summary = report.ai_summary or report.fallback_summary
    engine_label = "Gemini + Google Search" if report.engine == "gemini" else "Local summary"
    company_meta = []
    if report.company.ticker:
        company_meta.append(report.company.ticker)
    if report.company.cik:
        company_meta.append(f"CIK {report.company.cik}")
    if report.sic_description:
        company_meta.append(report.sic_description)
    meta_text = " · ".join(company_meta) if company_meta else "General company research"
    deck_href = f"/deck.pptx?company={urllib.parse.quote(report.company.title)}"

    return f"""
    <section class="result-band">
      <div class="result-header">
        <div>
          <p class="eyebrow">Research report</p>
          <h2>{escape(report.company.title)}</h2>
          <p class="muted">{escape(meta_text)}</p>
        </div>
        <div class="result-actions">
          <div class="status">{escape(engine_label)}</div>
          <a class="download-link" href="{escape(deck_href)}">Download PPT</a>
        </div>
      </div>
      {render_notes(report.notes)}
      <div class="grid">
        <section class="panel wide ai-banner">
          <div class="panel-title">
            <h3>Company Intelligence Snapshot</h3>
            <button type="button" onclick="copyBrief()">Copy snapshot</button>
          </div>
          <pre id="brief-output">{escape(summary)}</pre>
        </section>

        {render_sections(report)}

        <section class="panel">
          <h3>Grounded sources</h3>
          <ul class="link-list">{render_news(report.news)}</ul>
        </section>
      </div>
    </section>
    """


def build_page(query: str = "", result: Optional[ResearchReport] = None, errors: Sequence[str] = ()) -> str:
    error_block = ""
    if errors:
        error_block = "<div class=\"errors\">" + "".join(
            f"<div class=\"error\">{escape(error)}</div>" for error in errors
        ) + "</div>"

    result_block = build_result(result) if result else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Company Intelligence Assistant</title>
  <style>
    :root {{
      --bg: #f7f8f3;
      --ink: #172026;
      --muted: #63707a;
      --line: #d7ddd2;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-2: #a43f2b;
      --soft: #e8f2ed;
      --shadow: 0 16px 42px rgba(23, 32, 38, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .shell {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 26px 0 48px;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--line);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
    }}
    .brand-mark {{
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: var(--ink);
      color: white;
      font-weight: 900;
    }}
    .topbar a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
      gap: 34px;
      align-items: end;
      padding: 42px 0 26px;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--accent-2);
      text-transform: uppercase;
      letter-spacing: .12em;
      font-size: .76rem;
      font-weight: 800;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{
      max-width: 760px;
      margin-bottom: 14px;
      font-size: clamp(2.35rem, 6vw, 5.6rem);
      line-height: .94;
      letter-spacing: 0;
    }}
    .lede {{
      max-width: 760px;
      color: var(--muted);
      font-size: 1.04rem;
      line-height: 1.65;
    }}
    .search-panel, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .search-panel {{
      padding: 18px;
    }}
    .loading-layer {{
      position: fixed;
      inset: 0;
      z-index: 20;
      display: none;
      place-items: center;
      padding: 24px;
      background: rgba(247, 248, 243, .88);
      backdrop-filter: blur(8px);
    }}
    .loading-layer.active {{
      display: grid;
    }}
    .loading-box {{
      width: min(520px, 100%);
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: var(--shadow);
    }}
    .loading-title {{
      margin: 0 0 8px;
      font-size: 1.1rem;
      font-weight: 900;
    }}
    .loading-message {{
      min-height: 54px;
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }}
    .progress {{
      height: 8px;
      margin-top: 16px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--soft);
    }}
    .progress span {{
      display: block;
      width: 42%;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
      animation: glide 1.35s ease-in-out infinite alternate;
    }}
    @keyframes glide {{
      from {{ transform: translateX(-8%); }}
      to {{ transform: translateX(150%); }}
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 800;
    }}
    .search-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
    }}
    input {{
      min-width: 0;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px 14px;
      color: var(--ink);
      font: inherit;
      background: #fbfcfa;
    }}
    button {{
      border: 0;
      border-radius: 8px;
      padding: 12px 15px;
      background: var(--ink);
      color: #fff;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      white-space: nowrap;
    }}
    .hint {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: .9rem;
      line-height: 1.45;
    }}
    .errors, .notice {{
      display: grid;
      gap: 8px;
      margin: 4px 0 18px;
    }}
    .error, .notice p {{
      margin: 0;
      padding: 12px 14px;
      border-radius: 8px;
      font-weight: 700;
    }}
    .error {{
      background: #fde8e3;
      color: #8e2f1f;
      border: 1px solid #efc1b6;
    }}
    .notice p {{
      background: var(--soft);
      color: #24574f;
      border: 1px solid #c5ddd5;
    }}
    .result-band {{
      padding-top: 16px;
    }}
    .result-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 14px;
    }}
    .result-header h2 {{
      margin-bottom: 7px;
      font-size: clamp(1.7rem, 3vw, 2.5rem);
      line-height: 1.05;
    }}
    .status {{
      padding: 9px 12px;
      border-radius: 8px;
      background: var(--soft);
      color: var(--accent);
      font-weight: 800;
      white-space: nowrap;
    }}
    .result-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .download-link {{
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      padding: 9px 12px;
      border-radius: 8px;
      background: var(--ink);
      color: #fff;
      text-decoration: none;
      white-space: nowrap;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .wide {{
      grid-column: 1 / -1;
    }}
    .panel {{
      padding: 17px;
      min-width: 0;
      overflow: hidden;
    }}
    .panel-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .panel h3 {{
      margin-bottom: 12px;
      font-size: 1rem;
    }}
    .question-card p:last-child {{
      margin-bottom: 0;
      color: #24313a;
      line-height: 1.62;
    }}
    .section-label {{
      margin-bottom: 7px;
      color: var(--accent-2);
      font-size: .76rem;
      font-weight: 900;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      font-family: inherit;
      line-height: 1.6;
      color: #24313a;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: .92rem;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: .76rem;
      text-transform: uppercase;
      letter-spacing: .06em;
    }}
    .link-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 11px;
    }}
    .link-list li {{
      display: grid;
      gap: 4px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--line);
    }}
    a {{
      color: var(--accent);
      font-weight: 800;
      overflow-wrap: anywhere;
    }}
    small, .muted {{
      color: var(--muted);
      line-height: 1.45;
    }}
    .secondary-link {{
      display: inline-block;
      margin-top: 13px;
    }}
    @media (max-width: 820px) {{
      .hero,
      .grid {{
        grid-template-columns: 1fr;
      }}
      .search-row,
      .result-header,
      .panel-title {{
        grid-template-columns: 1fr;
        flex-direction: column;
        align-items: stretch;
      }}
      h1 {{
        font-size: 2.55rem;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <nav class="topbar" aria-label="Top navigation">
      <div class="brand"><span class="brand-mark">C</span>Company Intelligence Assistant</div>
      <a href="/">New search</a>
    </nav>

    <section class="hero">
      <div>
        <p class="eyebrow">Public-data AI project</p>
        <h1>Understand any company before you engage with it.</h1>
        <p class="lede">
          Enter any company name. Gemini uses Google Search grounding to create an AI-generated Company Intelligence Snapshot
          covering business model, customers, competitors, financial signals, operations, leadership, culture, and strategic perspective.
        </p>
      </div>
      <form class="search-panel" method="get" action="/" id="research-form">
        <label for="company">Company name or ticker</label>
        <div class="search-row">
          <input id="company" name="company" value="{escape(query)}" placeholder="AAPL, Microsoft, Cvent">
          <button type="submit">Research</button>
        </div>
        <p class="hint">Try Cvent, Databricks, Stripe, Anthropic, Microsoft, Nvidia, or any company you are applying to.</p>
      </form>
    </section>

    {error_block}
    {result_block}
  </main>
  <div class="loading-layer" id="loading-layer" role="status" aria-live="polite" aria-hidden="true">
    <div class="loading-box">
      <p class="loading-title">Building your Company Intelligence Snapshot...</p>
      <p class="loading-message" id="loading-message">Asking Gemini to put on its tiny analyst glasses.</p>
      <div class="progress" aria-hidden="true"><span></span></div>
    </div>
  </div>
  <script>
    const loadingLines = [
      "Asking Gemini to put on its tiny analyst glasses.",
      "Sorting the useful signals from the corporate confetti.",
      "Checking whether the company makes money, vibes, or both.",
      "Reading the internet so you do not have to open twenty tabs.",
      "Politely interrogating public sources.",
      "Looking for the CEO, the business model, and the plot twist.",
      "Turning search results into something slide-worthy."
    ];

    const form = document.getElementById('research-form');
    const layer = document.getElementById('loading-layer');
    const message = document.getElementById('loading-message');
    if (form && layer && message) {{
      form.addEventListener('submit', () => {{
        layer.classList.add('active');
        layer.setAttribute('aria-hidden', 'false');
        let index = 0;
        message.textContent = loadingLines[index];
        setInterval(() => {{
          index = (index + 1) % loadingLines.length;
          message.textContent = loadingLines[index];
        }}, 2600);
      }});
    }}

    function copyBrief() {{
      const output = document.getElementById('brief-output');
      if (!output) return;
      navigator.clipboard.writeText(output.innerText);
    }}
  </script>
</body>
</html>"""


class CompanyResearchHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def send_html(self, html_text: str, status: int = 200) -> None:
        body = html_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_pptx(self, report: ResearchReport) -> None:
        body = build_company_research_pptx(report)
        filename = f"{slugify_filename(report.company.title)}_company_research.pptx"
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in {"/", "/index.html", "/deck.pptx"}:
            self.send_error(404, "Not found")
            return

        params = urllib.parse.parse_qs(parsed.query)
        query = (params.get("company") or [""])[0].strip()
        if not query:
            self.send_html(build_page())
            return

        try:
            result = research_company(query)
        except Exception as exc:
            self.send_html(build_page(query=query, errors=[str(exc)]), status=400)
            return

        if parsed.path == "/deck.pptx":
            self.send_pptx(result)
            return

        self.send_html(build_page(query=query, result=result))


def main() -> None:
    server = HTTPServer((HOST, PORT), CompanyResearchHandler)
    print(f"Company Intelligence Assistant running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
