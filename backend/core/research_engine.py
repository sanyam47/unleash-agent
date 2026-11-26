"""
Dedicated Multi-Agent Verified Research Engine (AgentForge Pipeline).
Runs a separate 4-agent workflow without altering coding worker agents:
  1. ResearchPlannerAgent     -> decomposes objective into sub-questions & search queries
  2. DiscoveryExtractorAgent  -> retrieves web/PDF/RAG sources & extracts quoted claims
  3. EvidenceVerifierAgent    -> cross-checks claims against raw sources, flags contradictions,
                                 and triggers iterative follow-up discovery when needed
  4. ReportSynthesizerAgent   -> builds cited Markdown report with zero-fabrication guardrail
"""

import datetime
import html
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from backend.core.agent_engine import call_unified_chat, sanitize_project_name
from backend.core.agent_progress import set_project_plan, set_project_progress
from backend.core.agent_tools import (
    get_project_dir,
    read_document_file,
    read_project_file,
    search_web_docs,
)


@dataclass
class ResearchSource:
    source_id: str
    title: str
    location: str
    source_type: str  # "web" | "pdf" | "docx" | "pptx" | "file" | "rag"
    snippet: str
    raw_text: str
    reliability_score: float = 0.65
    reliability_tier: str = "MEDIUM"
    source_date: str = ""
    freshness_status: str = "UNKNOWN"  # "CURRENT" | "RECENT" | "OUTDATED" | "UNKNOWN"
    retrieved_at: float = field(default_factory=time.time)


@dataclass
class ResearchClaim:
    claim_id: str
    subquestion: str
    claim: str
    quote: str
    source_id: str
    status: str = "UNVERIFIED"  # "VERIFIED" | "CONFLICTING" | "UNVERIFIED"
    confidence_score: int = 0
    verification_note: str = ""


def _score_source_reliability(location: str, source_type: str) -> Tuple[float, str]:
    """Scores source authority (0.0-1.0) based on domain/document type."""
    loc = (location or "").lower()
    if source_type in ("pdf", "docx", "pptx"):
        return 0.90, "HIGH"
    if any(k in loc for k in (".gov/", ".gov.", ".edu/", ".edu.", "arxiv.org", "ieee.org", "acm.org", "nature.com", "pubmed", "ietf.org", "w3.org", "nist.gov", "github.com", "//docs.", "//developer.")):
        return 0.92, "HIGH"
    if any(k in loc for k in ("wikipedia.org", "reuters.com", "apnews.com", "bbc.com", "iso.org")) or source_type in ("rag", "file"):
        return 0.78, "MEDIUM-HIGH"
    if any(k in loc for k in ("reddit.com", "quora.com", "medium.com", "substack.com", "blogspot.com", "wordpress.com")):
        return 0.48, "LOW"
    return 0.65, "MEDIUM"


def _root_domain(location: str) -> str:
    """Extracts root domain (or local/rag identifier) for independent-source corroboration."""
    loc = (location or "").strip()
    if loc.startswith(("http://", "https://")):
        host = (urlparse(loc).hostname or "").lower()
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    return loc.lower()


def _detect_source_date_and_freshness(location: str, source_type: str, raw_text: str) -> Tuple[str, str]:
    """Extracts upload/publish date (file mtime, PDF metadata, or URL/text year) and classifies freshness."""
    current_year = datetime.datetime.now().year
    detected_date = ""
    detected_year: Optional[int] = None

    # 1. Local / uploaded file mtime (or PDF metadata if available)
    if source_type in ("pdf", "docx", "pptx", "file") and location and not location.startswith(("http://", "https://", "rag://", "search://")):
        try:
            p = Path(location)
            if p.exists():
                dt = datetime.datetime.fromtimestamp(p.stat().st_mtime)
                detected_date = dt.strftime("%Y-%m-%d")
                detected_year = dt.year
                if source_type == "pdf":
                    try:
                        import fitz
                        doc = fitz.open(str(p))
                        meta = doc.metadata or {}
                        doc.close()
                        raw_d = str(meta.get("modDate") or meta.get("creationDate") or "")
                        ym = re.search(r"(20\d{2}|19\d{2})", raw_d)
                        if ym:
                            detected_year = int(ym.group(1))
                            detected_date = f"{detected_year} (PDF meta)"
                    except Exception:
                        pass
        except Exception:
            pass

    # 2. Web URL or text date fallback
    if detected_year is None:
        m = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", f"{location} {raw_text[:2000]}")
        if m:
            detected_date = m.group(0)
            detected_year = int(m.group(1))
        else:
            years = [int(y) for y in re.findall(r"\b(20[0-3]\d)\b", f"{location} {raw_text[:2500]}") if 2005 <= int(y) <= current_year + 1]
            if years:
                detected_year = max(years)
                detected_date = str(detected_year)

    if detected_year is None:
        return "", "UNKNOWN"
    age = current_year - detected_year
    if age <= 1:
        return detected_date, "CURRENT"
    if age <= 3:
        return detected_date, "RECENT"
    return detected_date, "OUTDATED"


class EvidenceLedger:
    """Shared research memory storing sources, claims, and contradiction records."""

    def __init__(self, objective: str, project_name: str):
        self.objective = objective
        self.project_name = project_name
        self.subquestions: List[str] = []
        self.sources: Dict[str, ResearchSource] = {}
        self.claims: List[ResearchClaim] = []
        self.contradictions: List[Dict[str, Any]] = []
        self._seen_locations: Set[str] = set()
        self._seen_claims: Set[Tuple[str, str]] = set()

    def add_source(
        self,
        title: str,
        location: str,
        source_type: str,
        snippet: str,
        raw_text: str = "",
    ) -> ResearchSource:
        norm_loc = location.strip()
        if norm_loc in self._seen_locations:
            for s in self.sources.values():
                if s.location.strip() == norm_loc:
                    return s
        sid = f"S{len(self.sources) + 1}"
        rel_score, rel_tier = _score_source_reliability(norm_loc, source_type)
        s_date, freshness = _detect_source_date_and_freshness(norm_loc, source_type, raw_text or snippet)
        src = ResearchSource(
            source_id=sid,
            title=(title or sid).strip()[:160],
            location=norm_loc,
            source_type=source_type,
            snippet=(snippet or "")[:1200],
            raw_text=(raw_text or snippet or "")[:8000],
            reliability_score=rel_score,
            reliability_tier=rel_tier,
            source_date=s_date,
            freshness_status=freshness,
        )
        self.sources[sid] = src
        if norm_loc:
            self._seen_locations.add(norm_loc)
        return src

    def add_claim(
        self,
        subquestion: str,
        claim: str,
        quote: str,
        source_id: str,
        status: str = "UNVERIFIED",
        verification_note: str = "",
    ) -> Optional[ResearchClaim]:
        if source_id not in self.sources:
            return None
        norm_claim = re.sub(r"\s+", " ", (claim or "").lower()).strip()
        dedup_key = (source_id, norm_claim)
        if not norm_claim or dedup_key in self._seen_claims:
            return None
        self._seen_claims.add(dedup_key)
        cid = f"C{len(self.claims) + 1}"
        rec = ResearchClaim(
            claim_id=cid,
            subquestion=subquestion.strip()[:200],
            claim=claim.strip()[:400],
            quote=quote.strip()[:400],
            source_id=source_id,
            status=status,
            verification_note=verification_note,
        )
        self.claims.append(rec)
        return rec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "subquestions": self.subquestions,
            "sources": [asdict(s) for s in self.sources.values()],
            "claims": [asdict(c) for c in self.claims],
            "contradictions": self.contradictions,
        }


def _get_model_profile(model: str) -> Dict[str, Any]:
    """Adapts research batch sizes & retry scaffolding between small local 7-14B models and large/cloud LLMs."""
    m = (model or "").lower()
    is_large = any(
        tok in m
        for tok in (
            "gpt-", "o1", "o3", "o4", "gemini", "claude", "deepseek",
            "32b", "34b", "70b", "72b", "405b", "mixtral", "sonnet", "opus", "pro",
        )
    )
    if is_large:
        return {
            "tier": "large",
            "max_queries": 4,
            "max_sources_extract": 12,
            "excerpt_chars": 2500,
            "max_fetch_urls": 4,
        }
    return {
        "tier": "small_local",
        "max_queries": 3,
        "max_sources_extract": 6,
        "excerpt_chars": 1300,
        "max_fetch_urls": 3,
    }


def _extract_json_block(text: str) -> Any:
    """Extracts the first JSON object or array from an LLM response."""
    raw = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = raw.find(open_ch)
        end = raw.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                pass
    return None


def _run_research_planner(
    model: str,
    objective: str,
    context_window: int,
) -> Tuple[List[str], List[str], float, int]:
    """Agent 1: Breaks the research objective into sub-questions and search queries."""
    prompt = (
        "You are ResearchPlannerAgent. Break the user's research objective into 2 to 4 concise "
        "sub-questions and 2 to 4 targeted web/document search queries.\n"
        "Return ONLY valid JSON: "
        '{"subquestions": ["..."], "queries": ["..."]}\n\n'
        f"Objective: {objective}"
    )
    resp = call_unified_chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        context_window=context_window,
    )
    parsed = _extract_json_block(resp.get("content", "")) or {}
    subqs = [str(x).strip() for x in (parsed.get("subquestions") or []) if str(x).strip()][:4]
    queries = [str(x).strip() for x in (parsed.get("queries") or []) if str(x).strip()][:4]
    if not subqs:
        subqs = [objective]
    if not queries:
        queries = [objective[:120]]
    return subqs, queries, float(resp.get("duration_sec", 0.1)), int(resp.get("eval_tokens", 0))


def _fetch_url_text(url: str, max_chars: int = 8000) -> str:
    """Fetches clean readable text via HTTP, falling back to Playwright browser_extract for JS-rendered pages."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return ""
    cleaned = ""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; UnleashAgentResearch/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" in ctype or "text/plain" in ctype or "application/json" in ctype:
                raw_bytes = resp.read(250_000)
                raw_html = raw_bytes.decode("utf-8", errors="replace")
                cleaned = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)\b[^>]*>.*?</\1>", " ", raw_html)
                cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
                cleaned = html.unescape(cleaned)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
    except Exception:
        cleaned = ""

    if len(cleaned) >= 150:
        return cleaned[:max_chars]

    # Automatic Playwright sandbox fallback for JS-rendered or anti-bot pages
    try:
        from backend.core.browser_pilot import browser_extract
        b_res = browser_extract(url=url)
        b_txt = (b_res.get("text") or b_res.get("content") or "").strip() if isinstance(b_res, dict) else ""
        if len(b_txt) > len(cleaned):
            return b_txt[:max_chars]
    except Exception:
        pass
    return cleaned[:max_chars]


def _discover_sources_for_queries(
    project_name: str,
    objective: str,
    queries: List[str],
    ledger: EvidenceLedger,
    step_num: int,
) -> List[Dict[str, Any]]:
    """Agent 2 (Retrieval): Gathers local PDF/file paths, RAG context, and web search results."""
    step_logs: List[Dict[str, Any]] = []

    # 1. Inspect any local PDF, DOCX, PPTX, or text document paths mentioned in the objective
    path_matches = re.findall(
        r'(?:[A-Za-z]:[\\/][^\s"\'<>]+?\.(?:pdf|docx|pptx|md|txt|csv|json)|[^\s"\'<>]+?\.(?:pdf|docx|pptx))',
        objective,
        re.IGNORECASE,
    )
    for raw_path in path_matches[:4]:
        clean_path = raw_path.strip(".,;:\"'()")
        ext = Path(clean_path).suffix.lower()
        if ext in (".pdf", ".docx", ".pptx"):
            res = read_document_file(project_name, clean_path, start_page=1, end_page=10)
            if res.get("status") == "success":
                pages = res.get("pages") or []
                label = "Slide" if ext == ".pptx" else "Page"
                joined = "\n\n".join(f"[{label} {p['page']}] {p['text']}" for p in pages if p.get("text"))
                ledger.add_source(
                    title=Path(clean_path).name,
                    location=clean_path,
                    source_type=ext.lstrip("."),
                    snippet=joined[:1000],
                    raw_text=joined,
                )
            step_logs.append({"step": step_num, "action": "read_document", "target": clean_path, "status": res.get("status", "error")})
        else:
            res = read_project_file(project_name, clean_path, start_line=1, end_line=200)
            if res.get("status") == "success":
                txt = res.get("content", "")
                ledger.add_source(
                    title=Path(clean_path).name,
                    location=clean_path,
                    source_type="file",
                    snippet=txt[:1000],
                    raw_text=txt,
                )
            step_logs.append({"step": step_num, "action": "read_file", "target": clean_path, "status": res.get("status", "error")})

    # 2. Query local Knowledge Base (RAG) if available
    try:
        from backend.core.cyber_rag import search_rag
        rag_hits = search_rag(objective, top_k=3) or []
        for idx, hit in enumerate(rag_hits):
            text_val = hit.get("content") or hit.get("text") or ""
            src_name = hit.get("source") or hit.get("title") or f"Local Knowledge #{idx + 1}"
            if text_val.strip():
                ledger.add_source(
                    title=str(src_name),
                    location=f"rag://{src_name}",
                    source_type="rag",
                    snippet=text_val[:1000],
                    raw_text=text_val,
                )
    except Exception:
        pass

    # Smart Doc-vs-Web Routing: if local document(s) were attached/loaded and the prompt doesn't ask for external web comparison, focus locally
    has_local_docs = any(s.source_type in ("pdf", "docx", "pptx", "file") for s in ledger.sources.values())
    wants_web = any(
        kw in objective.lower()
        for kw in ("web", "internet", "online", "search", "compare with", "official page", "official site", "news", "latest")
    )
    if has_local_docs and not wants_web:
        step_logs.append({"step": step_num, "action": "smart_route", "mode": "document_focused", "status": "success"})
        return step_logs

    # 3. Web search across planned queries (graceful fallback on failed searches)
    for q in queries[:4]:
        try:
            w_res = search_web_docs(q, project_name=project_name)
            results = w_res.get("results") or w_res.get("items") or []
            if isinstance(results, list):
                for item in results[:3]:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url") or item.get("link") or item.get("href") or ""
                    title = item.get("title") or url or q
                    snippet = item.get("snippet") or item.get("body") or item.get("content") or ""
                    if url or snippet:
                        ledger.add_source(
                            title=str(title),
                            location=str(url or f"search://{q}"),
                            source_type="web",
                            snippet=str(snippet),
                            raw_text=str(snippet),
                        )
            step_logs.append({"step": step_num, "action": "search_web_docs", "query": q, "status": w_res.get("status", "success")})
        except Exception as exc:
            step_logs.append({"step": step_num, "action": "search_web_docs", "query": q, "status": "error", "error": str(exc)})

    # 4. Deep-fetch top 3 web URLs so verification checks full article text, not just short snippets
    fetched_count = 0
    for src in list(ledger.sources.values()):
        if fetched_count >= 3:
            break
        if src.source_type == "web" and src.location.startswith(("http://", "https://")) and len(src.raw_text) < 400:
            full_txt = _fetch_url_text(src.location)
            if len(full_txt) > len(src.raw_text):
                src.raw_text = full_txt
                src.source_date, src.freshness_status = _detect_source_date_and_freshness(src.location, src.source_type, full_txt)
                fetched_count += 1
                step_logs.append({"step": step_num, "action": "deep_fetch_url", "target": src.location, "bytes": len(full_txt), "status": "success"})

    return step_logs


def _extract_claims_from_sources(
    model: str,
    ledger: EvidenceLedger,
    context_window: int,
    max_sources: int = 8,
    excerpt_chars: int = 1500,
) -> Tuple[float, int]:
    """Agent 2 (Extraction): Extracts claim + verbatim quote + source_id records into the EvidenceLedger."""
    if not ledger.sources:
        return 0.0, 0

    sources_block = "\n\n".join(
        f"[{s.source_id}] Title: {s.title}\nLocation: {s.location}\nExcerpt:\n{s.raw_text[:excerpt_chars]}"
        for s in list(ledger.sources.values())[:max_sources]
    )
    subq_text = "\n".join(f"- {sq}" for sq in ledger.subquestions)
    prompt = (
        "You are DiscoveryExtractorAgent. Extract factual claims and supporting verbatim quotes "
        "ONLY from the sources provided below. Never invent source IDs or quotes.\n"
        "Return ONLY valid JSON: "
        '{"claims": [{"subquestion": "...", "claim": "...", "quote": "...", "source_id": "S1"}]}\n\n'
        f"Sub-questions:\n{subq_text}\n\nSources:\n{sources_block}"
    )
    resp = call_unified_chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        context_window=context_window,
    )
    parsed = _extract_json_block(resp.get("content", "")) or {}
    for item in (parsed.get("claims") or [])[:16]:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("source_id") or "").strip()
        claim_txt = str(item.get("claim") or "").strip()
        quote_txt = str(item.get("quote") or "").strip()
        subq = str(item.get("subquestion") or (ledger.subquestions[0] if ledger.subquestions else ledger.objective))
        if sid in ledger.sources and claim_txt:
            ledger.add_claim(subquestion=subq, claim=claim_txt, quote=quote_txt, source_id=sid)

    return float(resp.get("duration_sec", 0.1)), int(resp.get("eval_tokens", 0))


def _verify_evidence_and_detect_conflicts(
    model: str,
    ledger: EvidenceLedger,
    context_window: int,
) -> Tuple[List[str], float, int]:
    """
    Agent 3 (EvidenceVerifierAgent):
    Checks each claim against raw source text + compares across sources.
    Returns follow-up queries if critical gaps or contradictions are found.
    """
    if not ledger.claims:
        return [f"{ledger.objective[:90]} evidence statistics"], 0.0, 0

    # Deterministic lexical + exact substring + number + domain-independent + freshness scoring
    for c in ledger.claims:
        src = ledger.sources.get(c.source_id)
        if not src:
            c.status = "UNVERIFIED"
            c.confidence_score = 10
            c.verification_note = "Referenced source ID missing from ledger."
            continue
        raw_low = (src.raw_text or src.snippet).lower()
        norm_haystack = re.sub(r"\s+", " ", raw_low)
        norm_quote = re.sub(r"\s+", " ", (c.quote or "").lower()).strip()
        quote_words = [w for w in re.findall(r"[a-z0-9]{4,}", norm_quote)][:6]

        src_domain = _root_domain(src.location)
        corroborating = sum(
            1 for other in ledger.claims
            if other.source_id != c.source_id
            and other.subquestion == c.subquestion
            and other.status != "CONFLICTING"
            and _root_domain(ledger.sources[other.source_id].location) != src_domain
        )

        # Numeric consistency check: numbers/percentages in the claim must appear in source text
        claim_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", c.claim))
        src_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", raw_low))
        missing_nums = [n for n in claim_nums if n not in src_nums]

        freshness_adj = -10 if src.freshness_status == "OUTDATED" else 0

        if missing_nums:
            c.status = "UNVERIFIED"
            c.confidence_score = 25
            c.verification_note = f"Number mismatch: {', '.join(missing_nums)} not found in {c.source_id}."
        elif quote_words:
            exact_sub = bool(norm_quote and len(norm_quote) >= 12 and norm_quote in norm_haystack)
            hits = sum(1 for w in quote_words if w in norm_haystack)
            match_ratio = 1.0 if exact_sub else min(0.85, hits / len(quote_words))
            base_conf = int(round(src.reliability_score * 55 + match_ratio * 35 + (10 if corroborating > 0 else 0) + freshness_adj))
            if exact_sub or hits >= max(1, len(quote_words) // 2):
                c.status = "VERIFIED"
                c.confidence_score = max(35, min(100, base_conf))
                mode_tag = "exact quote" if exact_sub else f"{hits}/{len(quote_words)} terms"
                c.verification_note = f"Grounded in {c.source_id} ({src.reliability_tier}, {src.freshness_status}, {mode_tag})."
            else:
                c.status = "UNVERIFIED"
                c.confidence_score = min(35, max(10, base_conf // 2))
                c.verification_note = f"Quote did not match raw text of {c.source_id}."
        else:
            c.status = "UNVERIFIED"
            c.confidence_score = int(round(src.reliability_score * 30))
            c.verification_note = "No verbatim quote provided."

    claims_json = json.dumps(
        [{"claim_id": c.claim_id, "claim": c.claim, "source_id": c.source_id, "status": c.status} for c in ledger.claims],
        indent=2,
    )
    prompt = (
        "You are EvidenceVerifierAgent. Review these extracted claims across sources.\n"
        "Identify any contradictions between claims, or gaps where claims are UNVERIFIED.\n"
        "Return ONLY valid JSON: "
        '{"contradictions": [{"claim_ids": ["C1", "C2"], "summary": "..."}], '
        '"followup_queries": ["..."]}\n\n'
        f"Claims:\n{claims_json}"
    )
    resp = call_unified_chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        context_window=context_window,
    )
    parsed = _extract_json_block(resp.get("content", "")) or {}
    contradictions = parsed.get("contradictions") or []
    for con in contradictions[:5]:
        if isinstance(con, dict) and con.get("summary"):
            ledger.contradictions.append(con)
            for cid in (con.get("claim_ids") or []):
                for cl in ledger.claims:
                    if cl.claim_id == cid:
                        cl.status = "CONFLICTING"
                        cl.confidence_score = max(15, cl.confidence_score - 35)
                        cl.verification_note = str(con.get("summary"))[:180]

    followups = [str(q).strip() for q in (parsed.get("followup_queries") or []) if str(q).strip()][:2]
    return followups, float(resp.get("duration_sec", 0.1)), int(resp.get("eval_tokens", 0))


def _sanitize_citations(report_text: str, valid_source_ids: Set[str]) -> str:
    """Zero-Fabrication Guardrail: removes any [S<n>] citation that is not in valid_source_ids."""
    def _repl(match: re.Match) -> str:
        sid = match.group(1)
        return f"[{sid}]" if sid in valid_source_ids else "[unverified]"
    return re.sub(r"\[(S\d+)\]", _repl, report_text)


def _synthesize_verified_report(
    model: str,
    ledger: EvidenceLedger,
    context_window: int,
) -> Tuple[str, float, int]:
    """Agent 4 (ReportSynthesizerAgent): Produces structured, citation-grounded report."""
    verified = [c for c in ledger.claims if c.status == "VERIFIED"]
    conflicting = [c for c in ledger.claims if c.status == "CONFLICTING"]
    unverified = [c for c in ledger.claims if c.status == "UNVERIFIED"]

    evidence_payload = {
        "objective": ledger.objective,
        "verified_claims": [asdict(c) for c in verified],
        "conflicting_claims": [asdict(c) for c in conflicting],
        "unverified_claims": [asdict(c) for c in unverified],
        "contradictions": ledger.contradictions,
        "sources": [{"id": s.source_id, "title": s.title, "location": s.location} for s in ledger.sources.values()],
    }

    empty_verified_rule = (
        "- verified_claims is EMPTY: do NOT invent or list any Verified Findings; state 'None — see Conflicting/Unverified Claims below.'\n"
        if not verified
        else ""
    )
    prompt = (
        "You are ReportSynthesizerAgent. Write a clear, structured research report answering the objective.\n"
        "STRICT SAFETY BOUNDARIES:\n"
        "- Cite ONLY real source IDs from the provided ledger using [S1], [S2], etc.\n"
        "- NEVER invent URLs, citations, or facts not present in the evidence.\n"
        "- Explicitly separate Verified Findings, Conflicting/Unverified Claims (if any), and Sources.\n"
        f"{empty_verified_rule}\n"
        f"Evidence Ledger:\n{json.dumps(evidence_payload, indent=2)[:12000]}"
    )
    resp = call_unified_chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.25,
        context_window=context_window,
    )
    raw_report = (resp.get("content") or "").strip()
    if not raw_report:
        lines = [f"## Verified Research Report: {ledger.objective}", "", "### Verified Claims"]
        for c in verified:
            lines.append(f"- {c.claim} [{c.source_id}]")
        if not verified:
            lines.append("- No claims passed source-text verification.")
        raw_report = "\n".join(lines)

    safe_report = _sanitize_citations(raw_report, set(ledger.sources.keys()))

    # Deterministic guard: never allow Verified Findings bullets when verified_claims is empty
    if not verified:
        safe_report = re.sub(
            r"(?is)(?:^|\n)(?:#+\s*)?Verified Findings\s*:?[\s\S]*?(?=\n(?:#+\s*)?(?:Conflicting|Unverified|Sources)\b)",
            "\n### Verified Findings\n- None (no claims reached independent VERIFIED status; see Conflicting / Unverified Claims below).\n\n",
            safe_report,
        )

    # Append deterministic Source References footer so every [Sn] is traceable
    if ledger.sources and "### Sources" not in safe_report:
        src_lines = ["", "### Sources"]
        for s in ledger.sources.values():
            date_info = f" · {s.source_date} ({s.freshness_status})" if s.source_date else ""
            src_lines.append(f"- **[{s.source_id}]** {s.title} — `{s.location}` ({s.source_type} · {s.reliability_tier} authority: {int(round(s.reliability_score * 100))}%{date_info})")
        safe_report = safe_report + "\n" + "\n".join(src_lines)

    return safe_report, float(resp.get("duration_sec", 0.1)), int(resp.get("eval_tokens", 0))


def run_verified_research_pipeline(
    model: str,
    user_prompt: str,
    project_name: Optional[str] = None,
    context_window: int = 8192,
) -> Dict[str, Any]:
    """Executes the full 4-agent Verified Research lifecycle with live SSE progress."""
    clean_proj = sanitize_project_name(project_name or f"research_{int(time.time())}")
    profile = _get_model_profile(model)
    ledger = EvidenceLedger(objective=user_prompt, project_name=clean_proj)
    steps_trace: List[Dict[str, Any]] = []
    total_dur = 0.0
    total_tokens = 0

    # Plan Checklist
    set_project_plan(
        clean_proj,
        [
            {"title": "Decompose research objective", "status": "in_progress"},
            {"title": "Discover & extract source evidence", "status": "pending"},
            {"title": "Verify claims & resolve conflicts", "status": "pending"},
            {"title": "Synthesize cited research report", "status": "pending"},
        ],
    )

    # 1. ResearchPlannerAgent
    set_project_progress(clean_proj, phase="planning", headline="ResearchPlannerAgent: Decomposing objective...", detail=user_prompt[:120], step=1, tool="ResearchPlannerAgent")
    subqs, queries, dur1, tok1 = _run_research_planner(model, user_prompt, context_window)
    queries = queries[: profile["max_queries"]]
    ledger.subquestions = subqs
    total_dur += dur1
    total_tokens += tok1
    steps_trace.append({"step": 1, "agent": "ResearchPlannerAgent", "subquestions": subqs, "queries": queries, "model_tier": profile["tier"], "status": "success"})

    # 2. DiscoveryExtractorAgent
    set_project_plan(
        clean_proj,
        [
            {"title": "Decompose research objective", "status": "done"},
            {"title": "Discover & extract source evidence", "status": "in_progress"},
            {"title": "Verify claims & resolve conflicts", "status": "pending"},
            {"title": "Synthesize cited research report", "status": "pending"},
        ],
    )
    set_project_progress(clean_proj, phase="executing", headline=f"DiscoveryExtractorAgent: Querying {len(queries)} source(s)...", detail=", ".join(queries)[:120], step=2, tool="DiscoveryExtractorAgent")
    disc_logs = _discover_sources_for_queries(clean_proj, user_prompt, queries, ledger, step_num=2)
    dur2, tok2 = _extract_claims_from_sources(
        model,
        ledger,
        context_window,
        max_sources=profile["max_sources_extract"],
        excerpt_chars=profile["excerpt_chars"],
    )
    total_dur += dur2
    total_tokens += tok2
    steps_trace.extend(disc_logs)

    # 3. EvidenceVerifierAgent (+ 1 iterative follow-up round if gaps/contradictions detected)
    set_project_plan(
        clean_proj,
        [
            {"title": "Decompose research objective", "status": "done"},
            {"title": "Discover & extract source evidence", "status": "done"},
            {"title": "Verify claims & resolve conflicts", "status": "in_progress"},
            {"title": "Synthesize cited research report", "status": "pending"},
        ],
    )
    set_project_progress(clean_proj, phase="validating", headline=f"EvidenceVerifierAgent: Auditing {len(ledger.claims)} claim(s)...", detail=f"Cross-checking {len(ledger.sources)} retrieved source(s)", step=3, tool="EvidenceVerifierAgent")
    followups, dur3, tok3 = _verify_evidence_and_detect_conflicts(model, ledger, context_window)
    total_dur += dur3
    total_tokens += tok3

    verified_cnt = sum(1 for c in ledger.claims if c.status == "VERIFIED")
    conflict_cnt = sum(1 for c in ledger.claims if c.status == "CONFLICTING")
    doc_focused = any(s.get("action") == "smart_route" and s.get("mode") == "document_focused" for s in disc_logs)
    skip_large_retry = (profile["tier"] == "large" and verified_cnt >= 2 and conflict_cnt == 0)
    skip_doc_retry = (doc_focused and verified_cnt >= 1 and conflict_cnt == 0)

    needs_retry = bool(followups) and not skip_large_retry and not skip_doc_retry and (
        any(c.status in ("UNVERIFIED", "CONFLICTING") for c in ledger.claims) or not ledger.claims
    )
    if needs_retry:
        set_project_progress(clean_proj, phase="self_repairing", headline="Iterative Re-Search: Resolving gaps/conflicts...", detail=", ".join(followups)[:120], step=4, tool="DiscoveryExtractorAgent")
        retry_logs = _discover_sources_for_queries(clean_proj, user_prompt, followups, ledger, step_num=4)
        dur_r1, tok_r1 = _extract_claims_from_sources(
            model,
            ledger,
            context_window,
            max_sources=profile["max_sources_extract"],
            excerpt_chars=profile["excerpt_chars"],
        )
        _, dur_r2, tok_r2 = _verify_evidence_and_detect_conflicts(model, ledger, context_window)
        total_dur += dur_r1 + dur_r2
        total_tokens += tok_r1 + tok_r2
        steps_trace.extend(retry_logs)

    # 4. ReportSynthesizerAgent
    set_project_plan(
        clean_proj,
        [
            {"title": "Decompose research objective", "status": "done"},
            {"title": "Discover & extract source evidence", "status": "done"},
            {"title": "Verify claims & resolve conflicts", "status": "done"},
            {"title": "Synthesize cited research report", "status": "in_progress"},
        ],
    )
    set_project_progress(clean_proj, phase="coding", headline="ReportSynthesizerAgent: Generating cited report...", detail="Applying zero-fabrication citation guardrail", step=5, tool="ReportSynthesizerAgent")
    report_md, dur4, tok4 = _synthesize_verified_report(model, ledger, context_window)
    total_dur += dur4
    total_tokens += tok4

    # Persist auditable trace
    try:
        proj_dir = get_project_dir(clean_proj)
        os.makedirs(proj_dir, exist_ok=True)
        (proj_dir / "research_trace.json").write_text(json.dumps(ledger.to_dict(), indent=2), encoding="utf-8")
    except Exception:
        pass

    set_project_plan(
        clean_proj,
        [
            {"title": "Decompose research objective", "status": "done"},
            {"title": "Discover & extract source evidence", "status": "done"},
            {"title": "Verify claims & resolve conflicts", "status": "done"},
            {"title": "Synthesize cited research report", "status": "done"},
        ],
    )
    set_project_progress(
        clean_proj,
        phase="completed",
        headline=f"Verified Research Complete ({len(ledger.sources)} sources, {len(ledger.claims)} claims)",
        detail="All citations grounded in retrieved evidence",
        step=5,
        tool="ReportSynthesizerAgent",
    )

    return {
        "reply": report_md,
        "agentic": True,
        "research_mode": True,
        "project_name": clean_proj,
        "created_files": [],
        "steps": steps_trace,
        "research_ledger": ledger.to_dict(),
        "telemetry": {
            "eval_tokens": total_tokens,
            "eval_duration_sec": round(total_dur, 2),
            "tokens_per_second": round(total_tokens / max(total_dur, 0.1), 1),
            "step_count": len(steps_trace),
        },
    }
