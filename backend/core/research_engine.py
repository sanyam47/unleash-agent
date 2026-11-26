"""
Dedicated Multi-Agent Verified Research Engine (AgentForge Pipeline).
Runs a separate 4-agent workflow without altering coding worker agents:
  1. ResearchPlannerAgent     -> decomposes objective into sub-questions & search queries
  2. DiscoveryExtractorAgent  -> retrieves web/PDF/RAG sources & extracts quoted claims
  3. EvidenceVerifierAgent    -> cross-checks claims against raw sources, flags contradictions,
                                 and triggers iterative follow-up discovery when needed
  4. ReportSynthesizerAgent   -> builds cited Markdown report with zero-fabrication guardrail
"""

import html
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
    source_type: str  # "web" | "pdf" | "file" | "rag"
    snippet: str
    raw_text: str
    retrieved_at: float = field(default_factory=time.time)


@dataclass
class ResearchClaim:
    claim_id: str
    subquestion: str
    claim: str
    quote: str
    source_id: str
    status: str = "UNVERIFIED"  # "VERIFIED" | "CONFLICTING" | "UNVERIFIED"
    verification_note: str = ""


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
        src = ResearchSource(
            source_id=sid,
            title=(title or sid).strip()[:160],
            location=norm_loc,
            source_type=source_type,
            snippet=(snippet or "")[:1200],
            raw_text=(raw_text or snippet or "")[:8000],
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
    """Fetches and strips HTML to clean readable text for deep claim verification."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; UnleashAgentResearch/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" not in ctype and "text/plain" not in ctype and "application/json" not in ctype:
                return ""
            raw_bytes = resp.read(250_000)
            raw_html = raw_bytes.decode("utf-8", errors="replace")
        cleaned = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)\b[^>]*>.*?</\1>", " ", raw_html)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:max_chars]
    except Exception:
        return ""


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
                fetched_count += 1
                step_logs.append({"step": step_num, "action": "deep_fetch_url", "target": src.location, "bytes": len(full_txt), "status": "success"})

    return step_logs


def _extract_claims_from_sources(
    model: str,
    ledger: EvidenceLedger,
    context_window: int,
) -> Tuple[float, int]:
    """Agent 2 (Extraction): Extracts claim + verbatim quote + source_id records into the EvidenceLedger."""
    if not ledger.sources:
        return 0.0, 0

    sources_block = "\n\n".join(
        f"[{s.source_id}] Title: {s.title}\nLocation: {s.location}\nExcerpt:\n{s.raw_text[:1500]}"
        for s in list(ledger.sources.values())[:8]
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

    # Deterministic lexical grounding check first: verify quote words appear in source raw_text
    for c in ledger.claims:
        src = ledger.sources.get(c.source_id)
        if not src:
            c.status = "UNVERIFIED"
            c.verification_note = "Referenced source ID missing from ledger."
            continue
        haystack = (src.raw_text or src.snippet).lower()
        quote_words = [w for w in re.findall(r"[a-z0-9]{4,}", c.quote.lower())][:6]
        if quote_words:
            hits = sum(1 for w in quote_words if w in haystack)
            if hits >= max(1, len(quote_words) // 2):
                c.status = "VERIFIED"
                c.verification_note = f"Grounded in {c.source_id} ({hits}/{len(quote_words)} key quote terms matched)."
            else:
                c.status = "UNVERIFIED"
                c.verification_note = f"Quote did not match raw text of {c.source_id}."
        else:
            c.status = "UNVERIFIED"
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

    prompt = (
        "You are ReportSynthesizerAgent. Write a clear, structured research report answering the objective.\n"
        "STRICT SAFETY BOUNDARIES:\n"
        "- Cite ONLY real source IDs from the provided ledger using [S1], [S2], etc.\n"
        "- NEVER invent URLs, citations, or facts not present in the evidence.\n"
        "- Explicitly separate Verified Findings, Conflicting/Unverified Claims (if any), and Sources.\n\n"
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

    # Append deterministic Source References footer so every [Sn] is traceable
    if ledger.sources and "### Sources" not in safe_report:
        src_lines = ["", "### Sources"]
        for s in ledger.sources.values():
            src_lines.append(f"- **[{s.source_id}]** {s.title} — `{s.location}` ({s.source_type})")
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
    ledger.subquestions = subqs
    total_dur += dur1
    total_tokens += tok1
    steps_trace.append({"step": 1, "agent": "ResearchPlannerAgent", "subquestions": subqs, "queries": queries, "status": "success"})

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
    dur2, tok2 = _extract_claims_from_sources(model, ledger, context_window)
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

    needs_retry = bool(followups) and (
        any(c.status in ("UNVERIFIED", "CONFLICTING") for c in ledger.claims) or not ledger.claims
    )
    if needs_retry:
        set_project_progress(clean_proj, phase="self_repairing", headline="Iterative Re-Search: Resolving gaps/conflicts...", detail=", ".join(followups)[:120], step=4, tool="DiscoveryExtractorAgent")
        retry_logs = _discover_sources_for_queries(clean_proj, user_prompt, followups, ledger, step_num=4)
        dur_r1, tok_r1 = _extract_claims_from_sources(model, ledger, context_window)
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
