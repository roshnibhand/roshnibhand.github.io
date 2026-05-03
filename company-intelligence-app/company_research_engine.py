from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

DEFAULT_USER_AGENT = "CompanyResearchAssistant/1.0 contact@example.com"
DEFAULT_TIMEOUT = 18


_ENV_LOADED = False
_SEC_INDEX: Optional[List[Dict[str, Any]]] = None


@dataclass
class CompanyMatch:
    cik: str
    ticker: str
    title: str


@dataclass
class Filing:
    form: str
    filed: str
    report_date: str
    accession: str
    document: str
    url: str


@dataclass
class FinancialMetric:
    label: str
    value: str
    fiscal_period: str
    filed: str


@dataclass
class NewsItem:
    title: str
    link: str
    published: str


@dataclass
class ResearchSection:
    question: str
    short_label: str
    answer: str


@dataclass
class ResearchReport:
    company: CompanyMatch
    fiscal_year_end: str = ""
    sic_description: str = ""
    state_of_incorporation: str = ""
    recent_filings: List[Filing] = field(default_factory=list)
    financials: List[FinancialMetric] = field(default_factory=list)
    news: List[NewsItem] = field(default_factory=list)
    sections: List[ResearchSection] = field(default_factory=list)
    ai_summary: str = ""
    fallback_summary: str = ""
    engine: str = "local"
    notes: List[str] = field(default_factory=list)


RESEARCH_QUESTIONS = [
    (
        "What does this company do?",
        "Core business",
        "Core business, product/service, and industry",
    ),
    (
        "How does it make money?",
        "Revenue model",
        "Revenue model and primary sources",
    ),
    (
        "Who are its customers?",
        "Customers",
        "Target market, segments, and buyer personas",
    ),
    (
        "Who are its competitors?",
        "Competition",
        "Direct and indirect competitors, and differentiation",
    ),
    (
        "What is its financial health?",
        "Financial health",
        "Revenue, growth rate, funding stage or public status, and profitability signals",
    ),
    (
        "Where and how does it operate?",
        "Operations",
        "HQ, global presence, headcount, remote/hybrid posture",
    ),
    (
        "What is the company culture and trajectory?",
        "Culture and trajectory",
        "Mission, values, leadership, hiring momentum, and recent news",
    ),
    (
        "Who leads the company?",
        "Leadership",
        "CEO, founders or major executives, their education where publicly available, and what they have done so far",
    ),
    (
        "What is the final perspective?",
        "Strengths and weaknesses",
        "A balanced perspective on the organization's biggest strengths, weaknesses, and what to watch",
    ),
]


def load_local_env(env_path: Optional[str] = None) -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT)


def _fetch_bytes(url: str, accept: str = "application/json") -> bytes:
    headers = {
        "User-Agent": _user_agent(),
        "Accept": accept,
        "Accept-Encoding": "identity",
    }
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read()


def _fetch_json(url: str) -> Dict[str, Any]:
    data = _fetch_bytes(url)
    return json.loads(data.decode("utf-8"))


def _clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_json_object(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return json.loads(cleaned[start : end + 1])
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise ValueError("Gemini did not return parseable JSON.")


def _normalize_research_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"sections": payload}
    return {}


def _extract_grounding_sources(response: Any) -> List[NewsItem]:
    sources: List[NewsItem] = []
    try:
        candidates = getattr(response, "candidates", []) or []
        metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
        chunks = getattr(metadata, "grounding_chunks", []) if metadata else []
    except Exception:
        chunks = []

    seen = set()
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        uri = getattr(web, "uri", "") if web else ""
        title = getattr(web, "title", "") if web else ""
        if not uri or uri in seen:
            continue
        seen.add(uri)
        sources.append(NewsItem(title=title or uri, link=uri, published="Gemini Search source"))
        if len(sources) >= 8:
            break
    return sources


def _sections_from_payload(payload: Any) -> List[ResearchSection]:
    payload = _normalize_research_payload(payload)
    raw_sections = payload.get("sections") or []
    by_question = {}
    ordered_answers: List[str] = []
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if isinstance(item, dict):
                question = str(item.get("question", "")).strip()
                answer = str(item.get("answer", "")).strip()
                by_question[question.lower()] = answer
                if answer:
                    ordered_answers.append(answer)

    sections: List[ResearchSection] = []
    for index, (question, short_label, detail) in enumerate(RESEARCH_QUESTIONS):
        answer = by_question.get(question.lower(), "")
        if not answer and index < len(ordered_answers):
            answer = ordered_answers[index]
        if not answer:
            answer = f"Not enough reliable public information was found. Verify this area through the company website, recent news, or recruiter conversations. Focus area: {detail}."
        sections.append(ResearchSection(question=question, short_label=short_label, answer=answer))
    return sections


def _sections_from_research_text(text: str) -> List[ResearchSection]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    heading_patterns = []
    for index, (question, short_label, _) in enumerate(RESEARCH_QUESTIONS):
        escaped = re.escape(question)
        heading_patterns.append((index, question, short_label, re.compile(rf"(?im)^\s*(?:#+\s*)?(?:\*\*)?{escaped}(?:\*\*)?\s*:?\s*$")))

    matches = []
    for index, question, short_label, pattern in heading_patterns:
        match = pattern.search(normalized)
        if match:
            matches.append((match.start(), match.end(), index, question, short_label))
    if not matches:
        return []

    matches.sort(key=lambda item: item[0])
    section_by_index = {}
    for position, (_, end, index, question, short_label) in enumerate(matches):
        next_start = matches[position + 1][0] if position + 1 < len(matches) else len(normalized)
        answer = normalized[end:next_start].strip()
        answer = re.sub(r"^\s*[-:*]+\s*", "", answer)
        answer = re.sub(r"\n{2,}", "\n", answer).strip()
        if answer:
            section_by_index[index] = ResearchSection(question=question, short_label=short_label, answer=answer)

    return [section_by_index[index] for index in sorted(section_by_index)]


def _structure_research_text(client: Any, types: Any, model: str, query: str, research_text: str) -> Optional[Dict[str, Any]]:
    questions_text = "\n".join(
        f"- {question} -- {detail}" for question, _, detail in RESEARCH_QUESTIONS
    )
    prompt = f"""
Convert the research below into valid JSON for a company research app.

Company searched: {query}

Required questions:
{questions_text}

Return only valid JSON in this exact shape:
{{
  "company_name": "best current company name",
  "status_line": "AI-generated with Gemini and Google Search; verify important facts.",
  "sections": [
    {{"question": "What does this company do?", "answer": "3-5 sentence answer"}},
    {{"question": "How does it make money?", "answer": "3-5 sentence answer"}},
    {{"question": "Who are its customers?", "answer": "3-5 sentence answer"}},
    {{"question": "Who are its competitors?", "answer": "3-5 sentence answer"}},
    {{"question": "What is its financial health?", "answer": "3-5 sentence answer"}},
    {{"question": "Where and how does it operate?", "answer": "3-5 sentence answer"}},
    {{"question": "What is the company culture and trajectory?", "answer": "3-5 sentence answer"}},
    {{"question": "Who leads the company?", "answer": "CEO, founders or major executives, education where public, and what they have done so far"}},
    {{"question": "What is the final perspective?", "answer": "Balanced view of strengths, weaknesses, and what to watch"}}
  ]
}}

Research to structure:
{research_text}
""".strip()
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception:
        return None
    text = getattr(response, "text", "") or ""
    if not text.strip():
        return None
    try:
        return _extract_json_object(text)
    except Exception:
        return None


def _summary_from_sections(company_name: str, sections: Sequence[ResearchSection]) -> str:
    parts = [
        f"AI-generated Company Intelligence Snapshot for {company_name}. Verify important facts before using in applications, networking, or business decisions."
    ]
    for section in sections:
        parts.append(f"\n{section.question}\n{section.answer}")
    return "\n".join(parts).strip()


def _compact_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\b(inc|corp|corporation|company|co|plc|ltd|limited|class|common|stock)\b", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def load_company_index() -> List[Dict[str, Any]]:
    global _SEC_INDEX
    if _SEC_INDEX is not None:
        return _SEC_INDEX

    payload = _fetch_json(SEC_TICKERS_URL)
    companies: List[Dict[str, Any]] = []
    for item in payload.values():
        cik = str(item.get("cik_str", "")).zfill(10)
        ticker = str(item.get("ticker", "")).upper()
        title = str(item.get("title", "")).strip()
        if cik and ticker and title:
            companies.append({"cik": cik, "ticker": ticker, "title": title})
    _SEC_INDEX = companies
    return companies


def find_company(query: str) -> CompanyMatch:
    query = query.strip()
    if not query:
        raise ValueError("Enter a company name or ticker.")

    companies = load_company_index()
    upper_query = query.upper()
    for company in companies:
        if company["ticker"] == upper_query:
            return CompanyMatch(company["cik"], company["ticker"], company["title"])

    compact_query = _compact_name(query)
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for company in companies:
        compact_title = _compact_name(company["title"])
        score = 0
        if compact_title == compact_query:
            score += 100
        if compact_title.startswith(compact_query):
            score += 70
        if compact_query and compact_query in compact_title:
            score += 50
        query_terms = set(compact_query.split())
        title_terms = set(compact_title.split())
        score += 8 * len(query_terms & title_terms)
        if score:
            scored.append((score, company))

    if not scored:
        raise ValueError("I could not find that public company in the SEC ticker list. Try the stock ticker, like AAPL or MSFT.")

    scored.sort(key=lambda item: item[0], reverse=True)
    company = scored[0][1]
    return CompanyMatch(company["cik"], company["ticker"], company["title"])


def _filing_url(cik: str, accession: str, document: str) -> str:
    accession_clean = accession.replace("-", "")
    cik_clean = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/{document}"


def fetch_submissions(company: CompanyMatch) -> Dict[str, Any]:
    return _fetch_json(SEC_SUBMISSIONS_URL.format(cik=company.cik))


def parse_recent_filings(company: CompanyMatch, submissions: Dict[str, Any]) -> List[Filing]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filed_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])

    filings: List[Filing] = []
    wanted_forms = {"10-K", "10-Q", "8-K", "DEF 14A"}
    for form, filed, report_date, accession, document in zip(forms, filed_dates, report_dates, accessions, documents):
        if form not in wanted_forms:
            continue
        filings.append(
            Filing(
                form=form,
                filed=filed or "",
                report_date=report_date or "",
                accession=accession or "",
                document=document or "",
                url=_filing_url(company.cik, accession or "", document or ""),
            )
        )
        if len(filings) >= 8:
            break
    return filings


def _format_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.1f}M"
    return f"{sign}${value:,.0f}"


def _latest_usd_fact(facts: Dict[str, Any], names: Iterable[str]) -> Optional[Dict[str, Any]]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    candidates: List[Dict[str, Any]] = []
    for name in names:
        fact = us_gaap.get(name, {})
        usd_items = fact.get("units", {}).get("USD", [])
        for item in usd_items:
            if "val" not in item or not item.get("filed"):
                continue
            candidates.append(item)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.get("filed", ""), item.get("end", "")), reverse=True)
    return candidates[0]


def fetch_financials(company: CompanyMatch) -> List[FinancialMetric]:
    facts = _fetch_json(SEC_FACTS_URL.format(cik=company.cik))
    metric_map = [
        ("Revenue", ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")),
        ("Net income", ("NetIncomeLoss", "ProfitLoss")),
        ("Operating income", ("OperatingIncomeLoss",)),
        ("Total assets", ("Assets",)),
        ("Total liabilities", ("Liabilities",)),
        ("Cash and equivalents", ("CashAndCashEquivalentsAtCarryingValue", "Cash")),
    ]

    metrics: List[FinancialMetric] = []
    for label, names in metric_map:
        item = _latest_usd_fact(facts, names)
        if not item:
            continue
        fiscal = " ".join(part for part in (str(item.get("fy", "")), str(item.get("fp", ""))) if part)
        metrics.append(
            FinancialMetric(
                label=label,
                value=_format_money(float(item.get("val", 0))),
                fiscal_period=fiscal.strip(),
                filed=item.get("filed", ""),
            )
        )
    return metrics


def fetch_news(ticker: str) -> List[NewsItem]:
    url = YAHOO_RSS_URL.format(ticker=urllib.parse.quote(ticker.upper()))
    data = _fetch_bytes(url, accept="application/rss+xml, application/xml, text/xml")
    root = ET.fromstring(data)
    items: List[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = _clean(item.findtext("title", ""))
        link = _clean(item.findtext("link", ""))
        published = _clean(item.findtext("pubDate", ""))
        if title:
            items.append(NewsItem(title=title, link=link, published=published))
        if len(items) >= 6:
            break
    return items


def _build_fallback_summary(report: ResearchReport) -> str:
    metric_text = ", ".join(f"{metric.label.lower()}: {metric.value}" for metric in report.financials[:4])
    filing_text = ", ".join(f"{filing.form} filed {filing.filed}" for filing in report.recent_filings[:4])
    news_text = "; ".join(news.title for news in report.news[:3])
    industry = report.sic_description or "its reported industry"

    return textwrap.dedent(
        f"""
        {report.company.title} ({report.company.ticker}) is a public company in {industry}.

        How it makes money:
        Review the latest 10-K or 10-Q for the exact business model, revenue segments, customers, and geographic exposure. Current financial signals available from SEC facts include {metric_text or "limited standardized metrics"}.

        Recent signals:
        Recent filings include {filing_text or "no 10-K/10-Q/8-K items returned in the first SEC batch"}. Recent headline signals include {news_text or "no RSS headlines returned"}.

        Risks to research before an interview:
        Look for revenue concentration, margin pressure, customer demand changes, regulation, competition, debt, and any risk-factor language in the latest 10-K.

        Interview prep questions:
        1. Which business segment is the biggest growth driver right now?
        2. What metric best shows whether the company is winning in its market?
        3. How does the team use data to improve customer experience or profitability?
        4. What risks mentioned in the latest filing matter most for this role?
        """
    ).strip()


def _report_context(report: ResearchReport) -> str:
    return json.dumps(
        {
            "company": report.company.__dict__,
            "industry": report.sic_description,
            "fiscal_year_end": report.fiscal_year_end,
            "state": report.state_of_incorporation,
            "financials": [metric.__dict__ for metric in report.financials],
            "recent_filings": [filing.__dict__ for filing in report.recent_filings],
            "news": [news.__dict__ for news in report.news],
        },
        indent=2,
    )


def _gemini_summary(report: ResearchReport) -> Optional[str]:
    load_local_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        report.notes.append("Gemini API key was not found, so the app used the local summary.")
        return None

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        report.notes.append(f"Gemini package could not be loaded: {exc}")
        return None

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])
    prompt = f"""
You are a practical company research assistant for job applications and networking.
Use the provided SEC/public-data context and Google Search grounding for recent real-time context.
If something is uncertain, say what to verify in the latest filing or current news.

Return a concise report with these headings:
Business summary
How the company makes money
Recent signals
Risks to know
Competitors to research
Interview questions

Public-data context:
{_report_context(report)}
""".strip()

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as exc:
        report.notes.append(f"Gemini summary was unavailable: {exc}")
        return None

    text = getattr(response, "text", "") or ""
    return text.strip() or None


def _gemini_web_research(query: str, report: ResearchReport) -> bool:
    load_local_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        report.notes.append("Gemini API key was not found. Add GEMINI_API_KEY to research companies with web search.")
        return False

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        report.notes.append(f"Gemini package could not be loaded: {exc}")
        return False

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])
    questions_text = "\n".join(
        f"- {question} -- {detail}" for question, _, detail in RESEARCH_QUESTIONS
    )
    prompt = f"""
You are a practical company research assistant for job applications, networking, and interview prep.
Research this company using Google Search grounding: {query}

Answer these exact questions:
{questions_text}

Write a concise research note with one section for each question. Use the exact question text as each heading.

Rules:
- If the company is private, say that public financial detail may be limited.
- Prefer current public sources, company pages, reputable news, investor pages, and official filings when available.
- Do not invent exact revenue, valuation, funding, customer counts, or employee counts unless current sources clearly support them.
- Do not invent education credentials. If education is not public or not clearly sourced, say it is not publicly confirmed.
- Make the output useful for someone preparing for a job application or networking conversation.
- Do not use SEC list matching. Use web search for current research.
- Mention uncertainty directly when web evidence is thin.
""".strip()

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as exc:
        report.notes.append(f"Gemini search summary was unavailable: {exc}")
        return False

    text = getattr(response, "text", "") or ""
    if not text.strip():
        report.notes.append("Gemini returned an empty response.")
        return False

    try:
        payload = _extract_json_object(text)
    except Exception:
        payload = _structure_research_text(client, types, model, query, text)

    if payload:
        payload = _normalize_research_payload(payload)
        company_name = str(payload.get("company_name", "")).strip()
        if company_name:
            report.company.title = company_name
        report.sections = _sections_from_payload(payload)
        report.ai_summary = _summary_from_sections(report.company.title, report.sections)
    else:
        report.sections = _sections_from_research_text(text)
        if report.sections:
            report.ai_summary = _summary_from_sections(report.company.title, report.sections)
            report.notes.append("Gemini returned prose instead of clean JSON, so the app structured the result from headings without a second AI call.")
        else:
            payload = _structure_research_text(client, types, model, query, text)
            if payload:
                payload = _normalize_research_payload(payload)
                company_name = str(payload.get("company_name", "")).strip()
                if company_name:
                    report.company.title = company_name
                report.sections = _sections_from_payload(payload)
                report.ai_summary = _summary_from_sections(report.company.title, report.sections)
                report.notes.append("Gemini response needed one extra formatting pass.")
            else:
                report.notes.append("Gemini structured formatting was unavailable, so the raw AI response is shown.")
                report.ai_summary = text.strip()

    report.news = _extract_grounding_sources(response)
    report.engine = "gemini"
    return True


def research_company(query: str) -> ResearchReport:
    query = query.strip()
    if not query:
        raise ValueError("Enter a company name.")
    company = CompanyMatch(cik="", ticker="", title=query)
    report = ResearchReport(
        company=company,
        notes=[
            "AI-generated information: this report uses Gemini with Google Search grounding. Verify important facts before relying on them."
        ],
    )

    if not _gemini_web_research(query, report):
        report.fallback_summary = (
            "Gemini web research was unavailable. Check GEMINI_API_KEY, internet access, and Gemini API quota."
        )
        report.engine = "local"
    return report
