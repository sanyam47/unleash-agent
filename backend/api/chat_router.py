import os
import sys
import json
import time
import zipfile
import subprocess
import urllib.request
import urllib.error
import threading
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

router = APIRouter(tags=["Local Chat Arena"])

def get_ollama_base_url() -> str:
    try:
        from backend.core.cloud_gpu_bridge import CloudGpuBridge
        return CloudGpuBridge.get_active_inference_url()
    except Exception:
        return os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

OLLAMA_BASE_URL = get_ollama_base_url()


class PullModelRequest(BaseModel):
    model_tag: str = Field(..., description="Ollama library model tag, e.g. 'qwen2.5-coder:1.5b'")
    custom_name: Optional[str] = Field(None, description="Custom alias/name to give the model before registering")


class AliasExistingRequest(BaseModel):
    source_model: str = Field(..., description="Name of already downloaded model in Ollama, e.g. dolphin3:latest")
    custom_name: str = Field(..., description="Custom name/alias for the model")


class ImportGGUFRequest(BaseModel):
    model_name: str = Field(..., description="Name for the registered model")
    gguf_path: str = Field(..., description="Absolute or relative path to .gguf file on local drive")
    system_prompt: Optional[str] = Field(None, description="Optional custom system prompt")


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str
    images: Optional[List[str]] = Field(default=None, description="Optional list of base64-encoded image strings")


class ChatRequest(BaseModel):
    model: str = Field(default="dolphin3:latest", description="Ollama model name")
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=64, le=16384)
    context_window: int = Field(default=4096, ge=1024, le=65536, description="Context window size (num_ctx)")
    use_rag: bool = Field(default=True, description="Enable local Cybersecurity RAG context retrieval")
    skill_ids: Optional[List[str]] = Field(default=None, description="Optional active skill IDs to inject")
    agentic: bool = Field(default=False, description="Enable autonomous Antigravity ReAct agent loop")
    project_name: Optional[str] = Field(default=None, description="Workspace project name for autonomous file generation")
    skip_agentic_prompt: bool = Field(default=False, description="Skip agentic confirmation proposal and continue in pure text")


def _extract_vision_description(base64_image: str) -> str:
    """
    Transcribes screenshots, code, terminal traces, and errors using local moondream VLM.
    Fallback to Gemini if moondream is slow or unavailable.
    """
    try:
        # Prompt moondream for comprehensive OCR & error inspection
        prompt = (
            "Carefully analyze this image. If it contains code, terminal output, or an error message: "
            "1. Transcribe the exact error text, stack trace, and code verbatim. "
            "2. Note any highlighted lines, error markers, or file paths. "
            "3. If it is a UI or diagram, describe all visible components in detail."
        )
        v_payload = {
            "model": "moondream:latest",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64_image]
                }
            ],
            "stream": False
        }
        v_req = urllib.request.Request(
            f"{get_ollama_base_url()}/api/chat",
            data=json.dumps(v_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(v_req, timeout=35) as v_resp:
            v_data = json.loads(v_resp.read().decode("utf-8"))
            content = v_data.get("message", {}).get("content", "").strip()
            if content:
                return content
    except Exception as e:
        print(f"Moondream vision bridge error: {e}")

    return "[Attached Screenshot: Image transcription unavailable]"


@router.post("/send")
def send_chat_message(req: ChatRequest):
    """
    Universal Chat & Multimodal Gateway:
    - If the target model natively supports vision (e.g. moondream, qwen2-vl), sends images directly.
    - If the target model is text-only (e.g. dolphin3, llama3, custom LLMs), automatically routes
      images through local Moondream vision bridge to transcribe errors, code, and UI into the context seamlessly!
    """
    if not check_ollama_alive():
        raise HTTPException(status_code=503, detail="Ollama local server is not running. Please start Ollama first.")

    # Check if target model natively supports images
    native_vision_models = ["moondream", "qwen2-vl", "qwen2.5-vl", "llama3.2-vision", "llava", "bakllava"]
    is_native_vision = any(vm in req.model.lower() for vm in native_vision_models)

    # 0. Local Cybersecurity RAG Context Retrieval
    rag_sources = []
    rag_context_text = ""
    if req.use_rag:
        try:
            from backend.core.cyber_rag import search_knowledge, format_rag_context_prompt
            user_texts = [m.content for m in req.messages if m.role == "user" and m.content]
            if user_texts:
                latest_query = user_texts[-1]
                retrieved_docs = search_knowledge(latest_query, top_k=3, model_scope="all")
                if retrieved_docs and retrieved_docs[0]["score"] >= 0.20:
                    rag_sources = [
                        {
                            "id": d["id"],
                            "title": d["title"],
                            "category": d["category"],
                            "external_id": d.get("external_id"),
                            "severity": d.get("severity", "MEDIUM"),
                            "score": d["score"]
                        }
                        for d in retrieved_docs
                    ]
                    rag_context_text = format_rag_context_prompt(retrieved_docs)
        except Exception as e:
            print(f"[RAG] Context retrieval error: {e}")

    # Prepare message payload
    payload_messages = []
    base_sys = req.system_prompt.strip() if (req.system_prompt and req.system_prompt.strip()) else "You are an uncensored, highly capable, intelligent AI assistant."

    # 0.0 Epistemic Calibration & Self-Awareness of Ignorance
    epistemic_directive = (
        "\n\n### EPISTEMIC CALIBRATION & KNOWLEDGE BOUNDARY DIRECTIVES:\n"
        "1. Real-World Knowledge Limits: You must strictly distinguish between verified facts in your weights and uncertain domain entities (such as obscure biological plant/flower taxonomy, rare insects, specialized pharmacology, OBD2 codes, or proprietary exploits).\n"
        "2. Zero Hallucination Policy: When asked to identify, diagnose, or explain an entity where you lack verified high-confidence knowledge or where visual/text details are incomplete, DO NOT GUESS OR INVENT PLAUSIBLE-SOUNDING ENTITIES.\n"
        "3. Explicitly Acknowledge Ignorance: State clearly: 'I cannot identify or confirm this with high certainty based on my base weights alone.'\n"
        "4. Knowledge Acquisition: Note that an authoritative domain knowledge base can be downloaded and connected to ground your answers with 100% precision."
    )
    base_sys = f"{base_sys}{epistemic_directive}"

    # 0.01 Check for Epistemic Knowledge Gap & Premier Database Discovery
    knowledge_proposal = None
    try:
        from backend.core.knowledge_broker import detect_unknown_domain
        from backend.core.cyber_rag import DB_PATH
        import sqlite3

        existing_categories = []
        if DB_PATH.exists():
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT category FROM cyber_docs")
            existing_categories = [r[0] for r in cur.fetchall()]
            conn.close()

        user_texts_for_k = [m.content for m in req.messages if m.role == "user" and m.content]
        latest_user_text_for_k = user_texts_for_k[-1] if user_texts_for_k else ""
        knowledge_proposal = detect_unknown_domain(latest_user_text_for_k, existing_categories)
    except Exception as e:
        print(f"[KNOWLEDGE_BROKER] Detection error: {e}")

    # 0.1 Dynamic Antigravity Skill Routing & Efficiency Detection
    active_skills_names = []
    bake_recommendation = None
    skill_blocks = []
    try:
        from backend.api.skills_router import load_skills
        from backend.core.skill_router import route_skills_dynamically
        all_skills = load_skills()

        # Extract latest user message text for dynamic intent routing
        user_texts = [m.content for m in req.messages if m.role == "user"]
        latest_user_text = user_texts[-1] if user_texts else ""

        chosen, bake_recommendation, sanitized_user_text = route_skills_dynamically(
            user_prompt=latest_user_text,
            installed_skills=all_skills,
            explicit_skill_ids=req.skill_ids,
            current_model=req.model
        )
        if sanitized_user_text and req.messages and req.messages[-1].role == "user":
            req.messages[-1].content = sanitized_user_text

        if chosen:
            skill_blocks = ["\n\n### ACTIVE SPECIALIST SKILLS & OPERATIONAL RUNTIME:"]
            for s in chosen:
                active_skills_names.append(s["name"])
                skill_blocks.append(f"[{s['name'].upper()} - v{s.get('version', '1.0')}]")
                skill_blocks.append(s["system_instructions"].strip())
            base_sys = f"{base_sys}\n" + "\n".join(skill_blocks)
    except Exception as e:
        print(f"[SKILLS] Dynamic routing error: {e}")

    if rag_context_text:
        base_sys = f"{base_sys}\n\n{rag_context_text}"
    payload_messages.append({"role": "system", "content": base_sys})

    for m in req.messages:
        msg_dict = {"role": m.role, "content": m.content}
        if m.images and len(m.images) > 0:
            if is_native_vision:
                # Target model can see pixels directly
                msg_dict["images"] = m.images
            else:
                # Text-only model (Dolphin, Llama3, Custom) -> Auto-Bridge through Vision Gateway
                vision_descriptions = []
                for img_b64 in m.images:
                    desc = _extract_vision_description(img_b64)
                    vision_descriptions.append(desc)
                
                joined_desc = "\n\n".join(vision_descriptions)
                augmented_content = (
                    f"{m.content}\n\n"
                    f"[📸 Screenshot & Visual Transcription (Transcribed via Vision Gateway)]:\n"
                    f"{joined_desc}\n"
                    f"[End of Visual Context — Please analyze this error/screenshot and provide the diagnosis and solution.]"
                )
                msg_dict["content"] = augmented_content.strip()

        payload_messages.append(msg_dict)

    # 0.2 If Agentic ReAct Mode is explicitly requested by user toggle, route to autonomous agent engine
    if req.agentic:
        try:
            from backend.core.agent_engine import run_agentic_react_loop
            user_texts = [m["content"] for m in payload_messages if m["role"] == "user"]
            latest_prompt = user_texts[-1] if user_texts else "Proceed with task."
            skills_prompt_str = "\n\n".join(skill_blocks) if (chosen and 'skill_blocks' in locals()) else None

            # Pass recent conversation history so the agent understands contextual references (e.g. 'it', 'fix that', 'start button')
            prior_history = [m for m in payload_messages if m.get("role") in ("user", "assistant")][:-1]
            recent_history = prior_history[-6:] if len(prior_history) > 6 else prior_history

            agent_res = run_agentic_react_loop(
                model=req.model,
                user_prompt=latest_prompt,
                base_system_prompt=req.system_prompt or "",
                project_name=req.project_name,
                skills_prompt=skills_prompt_str,
                temperature=req.temperature or 0.4,
                context_window=req.context_window or 8192,
                chat_history=recent_history
            )

            agent_reply = agent_res["reply"]
            if knowledge_proposal and "[KNOWLEDGE_ACQUIRE_PROPOSAL:" not in agent_reply:
                agent_reply += f"\n\n[KNOWLEDGE_ACQUIRE_PROPOSAL:{knowledge_proposal['domain_key']}:{knowledge_proposal['database_name']}:{knowledge_proposal['description']}:{knowledge_proposal['source_url']}]"

            return {
                "reply": agent_reply,
                "agentic": True,
                "project_name": agent_res["project_name"],
                "created_files": agent_res["created_files"],
                "steps": agent_res["steps"],
                "telemetry": agent_res["telemetry"],
                "rag_sources": rag_sources,
                "active_skills": active_skills_names,
                "bake_recommendation": bake_recommendation,
                "knowledge_proposal": knowledge_proposal,
                "gateway_grounding": agent_res.get("gateway_grounding")
            }
        except Exception as err:
            print(f"[AGENTIC LOOP ERROR]: {err}")
            raise HTTPException(status_code=500, detail=f"Agentic loop failed: {str(err)}")

    # 0.3 If Agentic Mode is OFF but user prompt requested tool-driven file creation/modification:
    user_texts = [m["content"] for m in payload_messages if m["role"] == "user"]
    latest_prompt = user_texts[-1] if user_texts else ""
    tool_intent_pattern = r'\b(make|build|create|code|develop|generate|implement|fix|write)\b.*\b(website|site|game|dashboard|portfolio|app|tool|store|shop|snake|canvas|webgl|html|css|js|system|component|script)\b'
    tool_requested = bool(re.search(tool_intent_pattern, latest_prompt, re.IGNORECASE))

    if not req.agentic and tool_requested and not req.skip_agentic_prompt:
        proposal_text = (
            f"[AGENTIC_MODE_PROPOSAL:Creating workspace files and running code verification in the sandbox requires Agentic ReAct Mode.]\n\n"
            f"You asked to build or edit code files, but **Agentic ReAct Mode** is currently **OFF**.\n\n"
            f"In standard chat mode, I can only provide text explanations. Would you like to enable Agentic Mode to write the actual files and launch the **Live Preview**?"
        )
        return {
            "reply": proposal_text,
            "agentic": False,
            "agentic_proposal": {
                "required": True,
                "reason": "Creating project files and running verification requires Agentic ReAct tools."
            },
            "rag_sources": rag_sources,
            "active_skills": active_skills_names,
            "bake_recommendation": bake_recommendation,
            "knowledge_proposal": knowledge_proposal
        }

    ollama_payload = {
        "model": req.model,
        "messages": payload_messages,
        "stream": False,
        "options": {
            "temperature": req.temperature,
            "top_p": req.top_p,
            "num_predict": req.max_tokens,
            "num_ctx": req.context_window
        }
    }

    try:
        post_data = json.dumps(ollama_payload).encode("utf-8")
        api_req = urllib.request.Request(
            f"{get_ollama_base_url()}/api/chat",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )

        start_time = time.time()
        with urllib.request.urlopen(api_req, timeout=120) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - start_time

        msg = res_data.get("message", {})
        eval_count = res_data.get("eval_count", 0)
        eval_duration_ns = res_data.get("eval_duration", 0)
        
        # Calculate tokens/second
        tok_per_sec = 0.0
        if eval_duration_ns > 0:
            tok_per_sec = round(eval_count / (eval_duration_ns / 1e9), 2)
        elif elapsed > 0 and eval_count > 0:
            tok_per_sec = round(eval_count / elapsed, 2)

        reply_content = msg.get("content", "")
        if knowledge_proposal and "[KNOWLEDGE_ACQUIRE_PROPOSAL:" not in reply_content:
            reply_content += f"\n\n[KNOWLEDGE_ACQUIRE_PROPOSAL:{knowledge_proposal['domain_key']}:{knowledge_proposal['database_name']}:{knowledge_proposal['description']}:{knowledge_proposal['source_url']}]"

        return {
            "status": "success",
            "model": req.model,
            "reply": reply_content,
            "role": msg.get("role", "assistant"),
            "rag_sources": rag_sources,
            "active_skills": active_skills_names,
            "bake_recommendation": bake_recommendation,
            "knowledge_proposal": knowledge_proposal,
            "telemetry": {
                "eval_tokens": eval_count,
                "tokens_per_second": tok_per_sec,
                "total_duration_sec": round(elapsed, 2),
                "eval_duration_sec": round(eval_duration_ns / 1e9, 2)
            }
        }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        raise HTTPException(status_code=500, detail=f"Ollama inference error: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local engine failure: {str(e)}")


class ImportModelRequest(BaseModel):
    model_name: str
    modelfile_path: str


def check_ollama_alive() -> bool:
    try:
        req = urllib.request.Request(f"{get_ollama_base_url()}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


@router.get("/status")
def get_chat_status():
    """Checks if local Ollama server is running and accessible."""
    alive = check_ollama_alive()
    return {
        "status": "online" if alive else "offline",
        "url": OLLAMA_BASE_URL,
        "message": "Ollama local inference engine is ready" if alive else "Ollama is not running. Click Start Ollama to launch."
    }


@router.post("/start_ollama")
def start_ollama_service():
    """Starts local Ollama daemon if not already running."""
    if check_ollama_alive():
        return {"status": "already_running", "message": "Ollama is already online!"}
    
    try:
        # Launch ollama serve in background
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        # Wait up to 5 seconds for it to start
        for _ in range(10):
            time.sleep(0.5)
            if check_ollama_alive():
                return {"status": "started", "message": "Ollama started successfully!"}
        return {"status": "starting", "message": "Ollama starting in background..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch Ollama: {str(e)}")


@router.get("/models")
def get_available_models():
    """Lists all models installed in local Ollama instance with parameter sizes."""
    if not check_ollama_alive():
        return {
            "status": "offline",
            "models": [],
            "message": "Ollama is offline. Start Ollama to load local models."
        }

    try:
        req = urllib.request.Request(f"{get_ollama_base_url()}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        raw_models = data.get("models", [])
        formatted = []
        for m in raw_models:
            details = m.get("details", {})
            size_gb = round(m.get("size", 0) / (1024 ** 3), 2)
            formatted.append({
                "name": m.get("name"),
                "size_gb": size_gb,
                "parameter_size": details.get("parameter_size", "Unknown"),
                "quantization": details.get("quantization_level", "Unknown"),
                "family": details.get("family", "Unknown"),
                "modified_at": m.get("modified_at", "")[:10]
            })

        return {
            "status": "online",
            "models": formatted,
            "count": len(formatted)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading Ollama models: {str(e)}")


@router.post("/send")
def send_chat_message(req: ChatRequest):
    """
    Sends message history to local Ollama model and returns assistant response with token speed telemetry.
    """
    if not check_ollama_alive():
        raise HTTPException(status_code=503, detail="Ollama local server is not running. Please start Ollama first.")

    # Prepare message payload
    payload_messages = []
    if req.system_prompt and req.system_prompt.strip():
        payload_messages.append({"role": "system", "content": req.system_prompt.strip()})

    for m in req.messages:
        payload_messages.append({"role": m.role, "content": m.content})

    ollama_payload = {
        "model": req.model,
        "messages": payload_messages,
        "stream": False,
        "options": {
            "temperature": req.temperature,
            "top_p": req.top_p,
            "num_predict": req.max_tokens,
            "num_ctx": req.context_window
        }
    }

    try:
        post_data = json.dumps(ollama_payload).encode("utf-8")
        api_req = urllib.request.Request(
            f"{get_ollama_base_url()}/api/chat",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )

        start_time = time.time()
        with urllib.request.urlopen(api_req, timeout=120) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - start_time

        msg = res_data.get("message", {})
        eval_count = res_data.get("eval_count", 0)
        eval_duration_ns = res_data.get("eval_duration", 0)
        
        # Calculate tokens/second
        tok_per_sec = 0.0
        if eval_duration_ns > 0:
            tok_per_sec = round(eval_count / (eval_duration_ns / 1e9), 2)
        elif elapsed > 0 and eval_count > 0:
            tok_per_sec = round(eval_count / elapsed, 2)

        return {
            "status": "success",
            "model": req.model,
            "reply": msg.get("content", ""),
            "role": msg.get("role", "assistant"),
            "telemetry": {
                "eval_tokens": eval_count,
                "tokens_per_second": tok_per_sec,
                "total_duration_sec": round(elapsed, 2),
                "eval_duration_sec": round(eval_duration_ns / 1e9, 2)
            }
        }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        raise HTTPException(status_code=e.code, detail=f"Ollama Error: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failure: {str(e)}")


@router.post("/import_model")
def import_model(req: ImportModelRequest):
    """Executes 'ollama create <name> -f <modelfile>' to register a custom model."""
    if not os.path.exists(req.modelfile_path):
        raise HTTPException(status_code=404, detail=f"Modelfile not found at {req.modelfile_path}")

    try:
        result = subprocess.run(
            ["ollama", "create", req.model_name, "-f", req.modelfile_path],
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "status": "success",
            "message": f"Model '{req.model_name}' successfully registered into Ollama!",
            "output": result.stdout
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Ollama creation error: {e.stderr or e.stdout}")


@router.post("/alias_existing")
def alias_existing_model(req: AliasExistingRequest):
    """Aliases an already downloaded local model to a new custom name instantly without downloading anything."""
    if not check_ollama_alive():
        raise HTTPException(status_code=503, detail="Ollama local server is offline.")
    
    source = req.source_model.strip()
    clean_alias = re.sub(r'[^a-zA-Z0-9_\-\.:]', '-', req.custom_name.strip().lower()).strip('-')
    if not clean_alias:
        raise HTTPException(status_code=400, detail="Custom name cannot be empty.")
    
    try:
        copy_url = f"{get_ollama_base_url()}/api/copy"
        copy_data = json.dumps({"source": source, "destination": clean_alias}).encode("utf-8")
        copy_req = urllib.request.Request(copy_url, data=copy_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(copy_req, timeout=10) as resp:
            if resp.status == 200:
                return {
                    "status": "success",
                    "final_name": clean_alias,
                    "message": f"Successfully created custom model '{clean_alias}' from '{source}'!"
                }
            else:
                raise HTTPException(status_code=resp.status, detail="Failed to alias model.")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise HTTPException(status_code=e.code, detail=f"Ollama Error: {err}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def extract_model_from_zip(zip_path: str, target_dir: str) -> Dict[str, Any]:
    """Extracts a zip file and locates the model (.gguf, .bin, or Modelfile)."""
    os.makedirs(target_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(target_dir)

    found_gguf = None
    found_modelfile = None
    has_notebook_or_dataset = False

    for root, _, files in os.walk(target_dir):
        for f in files:
            lower = f.lower()
            if lower.endswith(".gguf") or lower.endswith(".bin"):
                found_gguf = os.path.join(root, f)
                break
            elif lower == "modelfile" or lower.startswith("modelfile"):
                found_modelfile = os.path.join(root, f)
            elif lower.endswith(".ipynb") or "dataset" in lower or lower == "train_headless.py":
                has_notebook_or_dataset = True
        if found_gguf:
            break

    if found_gguf:
        return {"type": "gguf", "path": found_gguf}
    elif found_modelfile:
        return {"type": "modelfile", "path": found_modelfile}
    elif has_notebook_or_dataset:
        return {"type": "starter_pack", "path": target_dir}
    else:
        return {"type": "unknown", "path": target_dir}


@router.post("/import_gguf")
def import_gguf_model(req: ImportGGUFRequest):
    """Imports a local .gguf, .zip (trained model bundle), or Modelfile directly into Ollama without downloading."""
    if not check_ollama_alive():
        raise HTTPException(status_code=503, detail="Ollama local server is offline.")
    
    clean_name = re.sub(r'[^a-zA-Z0-9_\-\.:]', '-', req.model_name.strip().lower()).strip('-')
    if not clean_name:
        raise HTTPException(status_code=400, detail="Model name cannot be empty.")
    
    clean_path = req.gguf_path.strip().strip('"').strip("'")
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=404, detail=f"File not found at: {clean_path}")

    # Case 1: ZIP Archive (e.g. from LLM Studio or Colab training)
    is_modelfile = False
    if clean_path.lower().endswith(".zip"):
        extract_dir = os.path.join(os.getcwd(), "models", f"extracted_{clean_name}")
        extracted = extract_model_from_zip(clean_path, extract_dir)
        if extracted["type"] == "gguf":
            target_file = extracted["path"]
            is_modelfile = False
        elif extracted["type"] == "modelfile":
            target_file = extracted["path"]
            is_modelfile = True
        elif extracted["type"] == "starter_pack":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{os.path.basename(clean_path)}' ({round(os.path.getsize(clean_path)/1024, 1)} KB) is a Cloud Training Starter Kit (dataset + Colab notebook), NOT the trained model weights file!\n\n"
                    "To generate your trained model:\n"
                    "1. Upload this zip or notebook to Google Colab (or Kaggle).\n"
                    "2. Run the training cells — it trains on free GPU and exports a .GGUF model (~1.2 GB).\n"
                    "3. Download that .GGUF file to your PC and import it here!\n\n"
                    "Tip: To chat right away without training, use the '⚡ Name Existing Model' tab to name one of your installed models."
                )
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"No .gguf model or Modelfile found inside '{os.path.basename(clean_path)}'. Please ensure the zip contains model weights."
            )
    elif os.path.basename(clean_path).lower().startswith("modelfile"):
        target_file = clean_path
        is_modelfile = True
    else:
        target_file = clean_path
        is_modelfile = False

    # Execute ollama create
    if is_modelfile:
        try:
            result = subprocess.run(
                ["ollama", "create", clean_name, "-f", target_file],
                capture_output=True,
                text=True,
                check=True
            )
            return {
                "status": "success",
                "final_name": clean_name,
                "message": f"Successfully registered model '{clean_name}' into Ollama!"
            }
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Ollama creation error: {e.stderr or e.stdout}")
    else:
        # GGUF file: build temp Modelfile
        modelfile_content = f'FROM "{target_file}"\n'
        if req.system_prompt:
            modelfile_content += f'SYSTEM """{req.system_prompt}"""\n'
            
        temp_modelfile = os.path.join(os.path.dirname(target_file), f"Modelfile_{clean_name}_{int(time.time())}")
        try:
            with open(temp_modelfile, "w", encoding="utf-8") as f:
                f.write(modelfile_content)
                
            result = subprocess.run(
                ["ollama", "create", clean_name, "-f", temp_modelfile],
                capture_output=True,
                text=True,
                check=True
            )
            return {
                "status": "success",
                "final_name": clean_name,
                "message": f"Successfully registered '{clean_name}' into Ollama!"
            }
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Ollama import error: {e.stderr or e.stdout}")
        finally:
            if os.path.exists(temp_modelfile):
                try:
                    os.remove(temp_modelfile)
                except Exception:
                    pass


@router.post("/upload_gguf")
async def upload_gguf_file(file: UploadFile = File(...)):
    """Uploads a local .gguf or .zip file from browser and saves/extracts to models directory."""
    models_dir = os.path.join(os.getcwd(), "models")
    os.makedirs(models_dir, exist_ok=True)
    
    file_path = os.path.join(models_dir, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024 * 8):  # 8MB chunks
                buffer.write(chunk)
                
        # If it's a zip file, extract it immediately!
        extracted_info = None
        if file.filename.lower().endswith(".zip"):
            clean_base = re.sub(r'[^a-zA-Z0-9_\-\.]', '-', os.path.splitext(file.filename)[0]).lower()
            extract_dir = os.path.join(models_dir, f"extracted_{clean_base}")
            extracted_info = extract_model_from_zip(file_path, extract_dir)
            
        return {
            "status": "success",
            "path": extracted_info["path"] if (extracted_info and extracted_info["type"] != "unknown") else file_path,
            "filename": file.filename,
            "is_zip": file.filename.lower().endswith(".zip"),
            "extracted_type": extracted_info["type"] if extracted_info else None,
            "size_mb": round(os.path.getsize(file_path) / (1024 * 1024), 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/scan_local_ggufs")
def scan_local_ggufs():
    """Scans project, cloud_packages, and user folders for existing .gguf, .zip, and Modelfile files."""
    scan_paths = [
        os.path.join(os.getcwd(), "cloud_packages"),
        os.path.join(os.getcwd(), "models"),
        os.getcwd(),
        os.path.join(os.path.expanduser("~"), "Downloads")
    ]
    found = []
    seen = set()
    for sp in scan_paths:
        if not os.path.exists(sp):
            continue
        try:
            for root, _, files in os.walk(sp):
                rel = os.path.relpath(root, sp)
                if rel.count(os.sep) > 2:
                    continue
                for f in files:
                    lower = f.lower()
                    full_p = os.path.join(root, f)
                    if full_p in seen:
                        continue

                    # 1. Direct GGUF / BIN weights
                    if lower.endswith(".gguf") or lower.endswith(".bin"):
                        seen.add(full_p)
                        try:
                            size_mb = round(os.path.getsize(full_p) / (1024 * 1024), 2)
                            found.append({
                                "name": f,
                                "path": full_p,
                                "type": "gguf",
                                "is_weights": True,
                                "size_mb": size_mb
                            })
                        except Exception:
                            pass

                    # 2. Modelfile
                    elif lower.startswith("modelfile"):
                        seen.add(full_p)
                        try:
                            size_mb = round(os.path.getsize(full_p) / (1024 * 1024), 2)
                            found.append({
                                "name": f,
                                "path": full_p,
                                "type": "modelfile",
                                "is_weights": True,
                                "size_mb": size_mb
                            })
                        except Exception:
                            pass

                    # 3. ZIP archives - inspect contents so we don't include irrelevant zips
                    elif lower.endswith(".zip"):
                        seen.add(full_p)
                        try:
                            with zipfile.ZipFile(full_p, 'r') as zf:
                                names = [n.lower() for n in zf.namelist()]
                                has_gguf = any(n.endswith(".gguf") or n.endswith(".bin") for n in names)
                                has_modelfile = any(os.path.basename(n).startswith("modelfile") for n in names)
                                is_starter = f.startswith("cloud_trainer_") or any("train_unsloth" in n or "train_headless" in n for n in names)

                                size_mb = round(os.path.getsize(full_p) / (1024 * 1024), 2)

                                if has_gguf or has_modelfile:
                                    found.append({
                                        "name": f,
                                        "path": full_p,
                                        "type": "zip",
                                        "is_weights": True,
                                        "size_mb": size_mb
                                    })
                                elif is_starter:
                                    found.append({
                                        "name": f,
                                        "path": full_p,
                                        "type": "starter_pack",
                                        "is_weights": False,
                                        "size_mb": size_mb
                                    })
                                # Non-model zip files (maven, tomcat, fifa dataset, etc.) are ignored!
                        except Exception:
                            pass
        except Exception:
            pass
            
    return {"status": "success", "files": found}




PULL_STATE = {
    "active": False,
    "status": "idle",
    "model_tag": "",
    "custom_name": "",
    "final_name": "",
    "progress": 0,
    "total_mb": 0,
    "completed_mb": 0,
    "detail": "",
    "error": None
}
PULL_LOCK = threading.Lock()


def _run_pull_task(model_tag: str, custom_name: Optional[str] = None):
    global PULL_STATE
    tag = model_tag.strip()
    alias = custom_name.strip() if custom_name and custom_name.strip() else ""

    with PULL_LOCK:
        PULL_STATE["active"] = True
        PULL_STATE["status"] = "starting"
        PULL_STATE["model_tag"] = tag
        PULL_STATE["custom_name"] = alias
        PULL_STATE["final_name"] = ""
        PULL_STATE["progress"] = 0
        PULL_STATE["total_mb"] = 0
        PULL_STATE["completed_mb"] = 0
        PULL_STATE["detail"] = f"Connecting to Ollama to pull {tag}..."
        PULL_STATE["error"] = None

    try:
        pull_url = f"{get_ollama_base_url()}/api/pull"
        pull_data = json.dumps({"model": tag, "stream": True}).encode("utf-8")
        req = urllib.request.Request(pull_url, data=pull_data, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=1800) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                try:
                    payload = json.loads(raw_line.decode("utf-8").strip())
                    status_text = payload.get("status", "")
                    total = payload.get("total", 0)
                    completed = payload.get("completed", 0)

                    pct = 0
                    total_mb = 0
                    comp_mb = 0
                    if total > 0:
                        pct = round((completed / total) * 100, 1)
                        total_mb = round(total / (1024 * 1024), 1)
                        comp_mb = round(completed / (1024 * 1024), 1)

                    with PULL_LOCK:
                        PULL_STATE["status"] = "downloading"
                        PULL_STATE["detail"] = status_text
                        if total > 0:
                            PULL_STATE["progress"] = pct
                            PULL_STATE["total_mb"] = total_mb
                            PULL_STATE["completed_mb"] = comp_mb

                    if status_text == "success":
                        break
                except Exception:
                    pass

        # Handle custom naming / aliasing
        final_registered_name = tag
        if alias:
            # Clean alias string for ollama tag format
            clean_alias = re.sub(r'[^a-zA-Z0-9_\-\.:]', '-', alias.lower()).strip('-')
            if clean_alias and clean_alias != tag:
                with PULL_LOCK:
                    PULL_STATE["status"] = "aliasing"
                    PULL_STATE["detail"] = f"Registering custom name '{clean_alias}'..."

                copy_url = f"{get_ollama_base_url()}/api/copy"
                copy_data = json.dumps({"source": tag, "destination": clean_alias}).encode("utf-8")
                copy_req = urllib.request.Request(copy_url, data=copy_data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(copy_req, timeout=30) as copy_resp:
                    if copy_resp.status == 200:
                        final_registered_name = clean_alias

        with PULL_LOCK:
            PULL_STATE["active"] = False
            PULL_STATE["status"] = "completed"
            PULL_STATE["progress"] = 100
            PULL_STATE["final_name"] = final_registered_name
            PULL_STATE["detail"] = f"Model '{final_registered_name}' successfully added and ready to use!"

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        with PULL_LOCK:
            PULL_STATE["active"] = False
            PULL_STATE["status"] = "error"
            PULL_STATE["error"] = f"HTTP {e.code}: {err_msg}"
            PULL_STATE["detail"] = f"Ollama Error: {err_msg}"
    except Exception as e:
        with PULL_LOCK:
            PULL_STATE["active"] = False
            PULL_STATE["status"] = "error"
            PULL_STATE["error"] = str(e)
            PULL_STATE["detail"] = f"Download failed: {str(e)}"


@router.post("/pull")
def pull_model_endpoint(req: PullModelRequest):
    """
    Downloads a model from Ollama library and optionally assigns it a custom user alias name.
    Runs asynchronously in the background so the UI can stream live progress.
    """
    if not check_ollama_alive():
        raise HTTPException(status_code=503, detail="Ollama local service is not running. Please start Ollama first.")

    tag = req.model_tag.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Model tag cannot be empty.")

    with PULL_LOCK:
        if PULL_STATE.get("active", False):
            raise HTTPException(status_code=409, detail=f"Download already in progress for '{PULL_STATE.get('model_tag')}'.")

    thread = threading.Thread(target=_run_pull_task, args=(tag, req.custom_name), daemon=True)
    thread.start()

    return {
        "status": "started",
        "model_tag": tag,
        "custom_name": req.custom_name,
        "message": f"Download initiated for '{tag}'"
    }


@router.get("/pull/status")
def pull_status_endpoint():
    """Returns real-time progress and status of active model download."""
    with PULL_LOCK:
        return dict(PULL_STATE)


# ========================================================
# PERSISTENT SESSION STORAGE (ANTIGRAVITY-STYLE DISK ARCHITECTURE)
# ========================================================
SESSIONS_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chat_sessions.json")
CONVERSATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "conversations")


def _load_persisted_sessions() -> List[Dict[str, Any]]:
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    sessions_map: Dict[str, Dict[str, Any]] = {}

    # 1. Load from aggregate index file if it exists
    if os.path.exists(SESSIONS_FILE_PATH):
        try:
            with open(SESSIONS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for s in data:
                        if isinstance(s, dict) and s.get("id"):
                            sessions_map[s["id"]] = s
        except Exception as e:
            print(f"Error reading {SESSIONS_FILE_PATH}: {e}")

    # 2. Disk scan: Load all discrete Antigravity-style conversation files
    try:
        for fname in os.listdir(CONVERSATIONS_DIR):
            if fname.endswith(".json"):
                fpath = os.path.join(CONVERSATIONS_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as cf:
                        s_data = json.load(cf)
                        if isinstance(s_data, dict) and s_data.get("id"):
                            sid = s_data["id"]
                            # If already in map, keep the version with more messages or newer timestamp
                            if sid in sessions_map:
                                existing_len = len(sessions_map[sid].get("messages", []))
                                new_len = len(s_data.get("messages", []))
                                if new_len >= existing_len:
                                    sessions_map[sid] = s_data
                            else:
                                sessions_map[sid] = s_data
                except Exception as file_err:
                    print(f"Error reading conversation file {fpath}: {file_err}")
    except Exception as scan_err:
        print(f"Error scanning conversations directory: {scan_err}")

    sessions = list(sessions_map.values())

    # Antigravity Rule: Purge ghost 0-message sessions if valid sessions exist
    non_empty = [s for s in sessions if len(s.get("messages", [])) > 0]
    final_sessions = non_empty if non_empty else sessions

    # Sort reverse-chronologically (newest activity first)
    final_sessions.sort(key=lambda x: (x.get("updatedAt") or x.get("createdAt") or 0), reverse=True)
    return final_sessions


def _save_persisted_sessions(sessions: List[Dict[str, Any]]) -> bool:
    try:
        os.makedirs(os.path.dirname(SESSIONS_FILE_PATH), exist_ok=True)
        os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

        # Do not allow empty 0-message sessions to overwrite real work
        non_empty = [s for s in sessions if len(s.get("messages", [])) > 0]
        sessions_to_save = non_empty if non_empty else sessions

        # 1. Save discrete Antigravity session files
        for s in sessions_to_save:
            sid = s.get("id")
            if sid:
                s_file = os.path.join(CONVERSATIONS_DIR, f"{sid}.json")
                with open(s_file, "w", encoding="utf-8") as sf:
                    json.dump(s, sf, indent=2, ensure_ascii=False)

        # 2. Save unified master index
        with open(SESSIONS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(sessions_to_save, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving {SESSIONS_FILE_PATH}: {e}")
        return False


@router.get("/sessions")
def get_chat_sessions_endpoint():
    """Returns all persisted chat sessions across all browser origins."""
    return {"status": "ok", "sessions": _load_persisted_sessions()}


@router.post("/sessions")
def save_chat_sessions_endpoint(sessions: List[Dict[str, Any]]):
    """Persists chat sessions directly to local disk in Antigravity discrete format."""
    success = _save_persisted_sessions(sessions)
    return {"status": "ok" if success else "error", "count": len(sessions)}


class UpdateTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


@router.put("/sessions/{session_id}/title")
def update_session_title_endpoint(session_id: str, req: UpdateTitleRequest):
    """Updates the title of a specific conversation."""
    sessions = _load_persisted_sessions()
    found = False
    for s in sessions:
        if s.get("id") == session_id:
            s["title"] = req.title.strip()
            s["updatedAt"] = int(time.time() * 1000)
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Session not found")
    _save_persisted_sessions(sessions)
    return {"status": "ok", "id": session_id, "title": req.title.strip()}


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """Deletes a conversation from both disk index and discrete file storage."""
    sessions = _load_persisted_sessions()
    filtered = [s for s in sessions if s.get("id") != session_id]

    # Remove individual file
    file_path = os.path.join(CONVERSATIONS_DIR, f"{session_id}.json")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Could not remove {file_path}: {e}")

    _save_persisted_sessions(filtered)
    return {"status": "ok", "deleted_id": session_id, "remaining": len(filtered)}


@router.get("/sessions/{session_id}/export")
def export_session_transcript_endpoint(session_id: str):
    """Exports conversation transcript as Markdown (Antigravity transcript style)."""
    file_path = os.path.join(CONVERSATIONS_DIR, f"{session_id}.json")
    session_data = None
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        except Exception:
            pass

    if not session_data:
        sessions = _load_persisted_sessions()
        session_data = next((s for s in sessions if s.get("id") == session_id), None)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    import datetime
    title = session_data.get("title", "Conversation")
    created_at = session_data.get("createdAt", int(time.time() * 1000))
    date_str = datetime.datetime.fromtimestamp(created_at / 1000.0).strftime("%Y-%m-%d %H:%M:%S")

    md_lines = [
        f"# {title}",
        f"**Date:** {date_str} | **Session ID:** `{session_id}` | **Model:** `{session_data.get('model', 'dolphin3:latest')}`",
        "",
        "---",
        ""
    ]

    for idx, msg in enumerate(session_data.get("messages", [])):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        md_lines.append(f"### {idx + 1}. {role}")
        md_lines.append("")
        md_lines.append(content)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(md_lines), media_type="text/markdown; charset=utf-8")


# ========================================================
# HIGH-SECURITY SANDBOX EXECUTION GATEWAY
# ========================================================
class SandboxRunRequest(BaseModel):
    code: str = Field(..., description="Source code to execute in isolated sandbox")
    language: str = Field(default="python", description="Language: 'python', 'javascript', 'batch', 'powershell'")
    timeout_seconds: Optional[float] = Field(default=4.0, ge=1.0, le=7.0, description="Execution timeout limit")
    stdin_input: Optional[str] = Field(default=None, description="Optional standard input to feed into process")


@router.post("/sandbox/run")
def run_code_in_sandbox_endpoint(req: SandboxRunRequest):
    """
    Executes code in an isolated sandbox with:
    - Pre-execution AST security screening for destructive commands
    - Ephemeral scratchpad filesystem jail
    - Hard process-group timeout with forceful termination
    - Stripped environment (no host credentials or secrets)
    - 64KB output buffer limit to protect memory
    """
    from backend.core.sandbox import execute_in_sandbox
    result = execute_in_sandbox(
        code=req.code,
        language=req.language,
        timeout_seconds=req.timeout_seconds or 4.0,
        stdin_input=req.stdin_input
    )
    return result


@router.get("/sandbox/status")
def get_sandbox_status_endpoint():
    """Returns sandbox security configuration, active isolation engine, and availability."""
    from backend.core.sandbox import (
        SANDBOX_BASE_DIR, MAX_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS,
        DEFAULT_MEMORY_LIMIT_BYTES, get_sandbox_telemetry_status
    )
    status_data = get_sandbox_telemetry_status()
    status_data.update({
        "sandbox_dir": str(SANDBOX_BASE_DIR),
        "supported_languages": ["python", "javascript", "batch", "powershell"],
        "max_timeout_seconds": MAX_TIMEOUT_SECONDS,
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "safety_measures": [
            "Pre-execution AST destructive call & base64 screening",
            "Windows Job Object 256MB hard RAM cap (MemoryError on leak)",
            "Process-group hard timeout kill (taskkill /F /T)",
            "Ephemeral scratchpad filesystem isolation",
            "Environment sanitization (secrets & credentials scrubbed)",
            "64KB max output buffer protection",
            "Auto-kill of all child processes on job closure",
            "Docker Linux Container with --network none and security tooling (pwntools, scapy, crypto)"
        ]
    })
    return status_data


@router.get("/sandbox/docker/status")
def get_docker_status_endpoint():
    """Returns whether Docker Desktop is installed, running, and if cyber-sandbox image is available."""
    import shutil
    from backend.core.sandbox import is_docker_available, is_cyber_image_available

    standard_paths = [
        r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
        r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe")
    ]
    is_installed = bool(shutil.which("docker")) or any(os.path.exists(p) for p in standard_paths)
    is_running = is_docker_available()
    image_ready = is_cyber_image_available() if is_running else False

    return {
        "status": "online" if is_running else "offline",
        "installed": is_installed,
        "running": is_running,
        "cyber_image_ready": image_ready,
        "active_engine": "docker" if is_running else "windows_job_object",
        "engine_detail": "Docker Linux Container (cyber-sandbox:latest • --network none)" if is_running else "Windows Job Object Jail (256MB RAM Cap)"
    }


@router.post("/sandbox/docker/start")
def start_docker_daemon_endpoint():
    """Starts Docker Desktop in the background on Windows."""
    import shutil
    from backend.core.sandbox import is_docker_available

    if is_docker_available():
        return {"status": "already_running", "message": "Docker Desktop is already running and ready!"}

    standard_paths = [
        r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
        r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe")
    ]
    docker_exe = None
    for p in standard_paths:
        if os.path.exists(p):
            docker_exe = p
            break

    if not docker_exe and not shutil.which("docker"):
        return {
            "status": "not_installed",
            "message": "Docker Desktop is not installed on this system yet. Run 'winget install Docker.DockerDesktop' in PowerShell."
        }

    try:
        cmd = [docker_exe] if docker_exe else ["docker", "daemon"]
        flags = subprocess.DETACHED_PROCESS if os.name == 'nt' else 0
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        return {
            "status": "starting",
            "message": "Starting Docker Desktop in background. Please wait 10-15 seconds for the engine to initialize."
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to launch Docker: {str(e)}"}


@router.post("/sandbox/docker/stop")
def stop_docker_daemon_endpoint():
    """Stops Docker Desktop processes and shuts down WSL2 to reclaim RAM immediately."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "Docker Desktop.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["taskkill", "/F", "/IM", "com.docker.backend.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["wsl", "--shutdown"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return {
            "status": "stopped",
            "message": "Docker Desktop and WSL2 VM stopped. System RAM fully reclaimed!"
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to stop Docker: {str(e)}"}



# ========================================================
# CYBERSECURITY RAG KNOWLEDGE BASE GATEWAY
# ========================================================
class IngestKnowledgeRequest(BaseModel):
    category: str = Field(..., description="'mitre_attack', 'cve', 'owasp', 'cwe', or 'custom'")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Technical breakdown, vulnerability description, or research report")
    external_id: Optional[str] = Field(None, description="e.g. CVE-2024-XXXX, T1055, CWE-89")
    severity: Optional[str] = Field(default="MEDIUM", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    detection: Optional[str] = None
    mitigation: Optional[str] = None
    tags: Optional[List[str]] = None
    model_scope: Optional[str] = Field(default="global", description="Specific model (e.g. dolphin3:latest) or 'global'")


@router.get("/rag/status")
def get_rag_status_endpoint():
    """Returns status and statistics of local cybersecurity RAG knowledge base."""
    import sqlite3
    from backend.core.cyber_rag import DB_PATH, seed_knowledge_base
    seed_knowledge_base()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cyber_docs")
    total_docs = cursor.fetchone()[0]
    cursor.execute("SELECT category, COUNT(*) FROM cyber_docs GROUP BY category")
    categories = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.execute("SELECT id, title, external_id, category, severity FROM cyber_docs ORDER BY created_at DESC LIMIT 20")
    recent = [{"id": r[0], "title": r[1], "external_id": r[2], "category": r[3], "severity": r[4]} for r in cursor.fetchall()]
    conn.close()
    return {
        "status": "online",
        "total_documents": total_docs,
        "categories": categories,
        "embedding_model": "all-MiniLM-L6-v2 (384-d normalized vector)",
        "db_path": str(DB_PATH),
        "recent_documents": recent
    }


@router.get("/rag/search")
def search_rag_endpoint(query: Optional[str] = None, q: Optional[str] = None, top_k: int = 15, category: Optional[str] = None, model_scope: Optional[str] = None):
    """Searches cybersecurity knowledge base with hybrid retrieval filtered by model scope."""
    from backend.core.cyber_rag import search_knowledge
    search_term = query or q or ""
    results = search_knowledge(search_term, top_k=top_k, category_filter=category, model_scope=model_scope)
    return {"query": search_term, "model_scope": model_scope or "all", "total_matches": len(results), "results": results}


@router.post("/rag/ingest")
def ingest_rag_endpoint(req: IngestKnowledgeRequest):
    """Adds a new custom CVE, research write-up, or attack technique to the local RAG database."""
    import uuid
    from backend.core.cyber_rag import insert_doc
    doc_id = f"{req.category}_{uuid.uuid4().hex[:8]}"
    if req.external_id:
        doc_id = f"{req.category}_{req.external_id.lower().replace('-', '_').replace(':', '_')}"
    insert_doc(
        doc_id=doc_id,
        category=req.category,
        title=req.title,
        content=req.content,
        external_id=req.external_id,
        severity=req.severity or "MEDIUM",
        detection=req.detection,
        mitigation=req.mitigation,
        tags=req.tags or [],
        model_scope=req.model_scope or "global",
        auto_embed=True
    )
    return {"status": "success", "doc_id": doc_id, "title": req.title}






# ========================================================
# AUTONOMOUS KNOWLEDGE ACQUISITION APIS
# ========================================================

class AcquireKnowledgeRequest(BaseModel):
    domain_key: str
    model: Optional[str] = "global"


@router.post("/knowledge/acquire")
def acquire_knowledge_endpoint(req: AcquireKnowledgeRequest):
    """
    Downloads and sets up the premier authoritative knowledge database for a domain,
    embeds the records into local Vector RAG, and registers a runtime specialist skill.
    """
    from backend.core.knowledge_broker import install_knowledge_database
    try:
        res = install_knowledge_database(req.domain_key, model_scope=req.model or "global")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================
# ZERO-FINE-TUNING KNOWLEDGE GATEWAY APIS
# ========================================================

@router.get("/gateway/datasets")
def get_gateway_datasets_endpoint():
    """Lists all modular reference datasets registered in the Zero-Fine-Tuning Knowledge Gateway."""
    from backend.core.knowledge_gateway import list_available_gateway_datasets
    return {"status": "success", "datasets": list_available_gateway_datasets()}


# ========================================================
# AGENTIC WORKSPACE & PROJECT FILE APIS
# ========================================================

@router.get("/agent/projects")
def list_agent_projects():
    """Lists all projects generated by autonomous agentic runs."""
    from backend.core.agent_tools import PROJECTS_ROOT
    if not PROJECTS_ROOT.exists():
        return {"projects": []}

    projects = []
    for item in PROJECTS_ROOT.iterdir():
        if item.is_dir():
            files = [f.name for f in item.rglob("*") if f.is_file()]
            projects.append({
                "name": item.name,
                "file_count": len(files),
                "files": files[:15],
                "path": str(item.resolve())
            })
    return {"projects": sorted(projects, key=lambda p: p["name"], reverse=True)}


@router.get("/agent/projects/{project_name}/files")
def get_project_files_endpoint(project_name: str):
    """Returns file tree and contents of an agent workspace project."""
    from backend.core.agent_tools import list_project_files
    return list_project_files(project_name)


@router.get("/agent/projects/{project_name}/file")
def get_project_single_file_endpoint(project_name: str, file_path: str):
    """Reads a specific file from an agent project safely."""
    from backend.core.agent_tools import read_project_file
    return read_project_file(project_name, file_path)


@router.get("/agent/projects/{project_name}/progress")
def get_project_progress_endpoint(project_name: str):
    """Returns the live real-time progress state of an active agentic task (Antigravity telemetry)."""
    from backend.core.agent_progress import get_project_progress
    return get_project_progress(project_name)


@router.get("/agent/projects/{project_name}/preview")
@router.get("/agent/projects/{project_name}/preview/")
def preview_project_root_endpoint(project_name: str):
    """Serves the root index.html file with an injected <base> tag so all relative CSS & JS files resolve flawlessly."""
    from fastapi.responses import HTMLResponse
    from backend.core.agent_tools import resolve_safe_project_path, sanitize_project_name

    clean_proj = sanitize_project_name(project_name)
    safe_path = resolve_safe_project_path(clean_proj, "index.html")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found in project workspace.")

    html = safe_path.read_text(encoding="utf-8", errors="replace")
    base_tag = f'<base href="/api/chat/agent/projects/{clean_proj}/preview/">'

    if "<head>" in html:
        html = html.replace("<head>", f"<head>\n    {base_tag}", 1)
    elif "<HEAD>" in html:
        html = html.replace("<HEAD>", f"<HEAD>\n    {base_tag}", 1)
    else:
        html = f"{base_tag}\n{html}"

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return HTMLResponse(content=html, status_code=200, headers=headers)


@router.get("/agent/projects/{project_name}/preview/{file_path:path}")
def preview_project_file_endpoint(project_name: str, file_path: str):
    """Serves static project files (HTML, CSS, JS, images) directly for live browser preview."""
    import mimetypes
    from fastapi.responses import FileResponse
    from backend.core.agent_tools import resolve_safe_project_path

    if not file_path or file_path.strip() == "/" or file_path == "index.html":
        return preview_project_root_endpoint(project_name)

    safe_path = resolve_safe_project_path(project_name, file_path)
    if safe_path.is_dir():
        safe_path = safe_path / "index.html"

    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found in project.")

    mime_type, _ = mimetypes.guess_type(str(safe_path))
    if safe_path.suffix == ".css":
        mime_type = "text/css"
    elif safe_path.suffix == ".js":
        mime_type = "application/javascript"
    elif safe_path.suffix == ".html":
        mime_type = "text/html"

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(path=safe_path, media_type=mime_type or "application/octet-stream", headers=headers)


@router.get("/agent/projects/{project_name}/{file_path:path}")
def preview_project_asset_fallback(project_name: str, file_path: str):
    """Fallback static asset resolver if browser resolves relative assets to project root."""
    return preview_project_file_endpoint(project_name, file_path)


@router.post("/agent/projects/{project_name}/open_vscode")
def open_project_vscode_endpoint(project_name: str):
    """Launches VS Code directly opening the generated workspace project directory."""
    import subprocess
    import shutil
    from backend.core.agent_tools import PROJECTS_ROOT, sanitize_project_name

    clean_proj = sanitize_project_name(project_name)
    proj_dir = (PROJECTS_ROOT / clean_proj).resolve()
    if not proj_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project workspace '{clean_proj}' does not exist.")

    code_bin = shutil.which("code") or r"C:\Users\asopa\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"
    try:
        subprocess.Popen(f'"{code_bin}" "{str(proj_dir)}"', shell=True)
        return {
            "status": "success",
            "message": f"Opened workspace '{clean_proj}' in VS Code!",
            "path": str(proj_dir),
            "vscode_url": f"vscode://file/{str(proj_dir).replace('\\', '/')}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch VS Code: {str(e)}")


@router.post("/agent/projects/{project_name}/open_folder")
def open_project_folder_endpoint(project_name: str):
    """Opens the project directory in Windows Explorer."""
    import subprocess
    from backend.core.agent_tools import PROJECTS_ROOT, sanitize_project_name

    clean_proj = sanitize_project_name(project_name)
    proj_dir = (PROJECTS_ROOT / clean_proj).resolve()
    if not proj_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project workspace '{clean_proj}' does not exist.")

    subprocess.Popen(f'explorer "{str(proj_dir)}"', shell=True)
    return {"status": "success", "path": str(proj_dir)}


class AgentInstallRequest(BaseModel):
    package: str
    install_type: str = Field(default="pip", description="'pip', 'winget', or 'npm'")


@router.post("/agent/install_package")
def install_agent_package_endpoint(req: AgentInstallRequest):
    """
    Executes user-approved installation of a package or tool with safety checks:
    - Verifies package name format (prevents shell injection)
    - Runs in subprocess with timeout
    - Returns verified installation status
    """
    import subprocess
    import shutil
    import sys

    pkg = req.package.strip()
    if not re.match(r'^[a-zA-Z0-9_\-\.\:\@\/]+$', pkg):
        raise HTTPException(status_code=400, detail="Invalid package name format.")

    cmd = []
    if req.install_type == "pip":
        python_exe = sys.executable or "python"
        cmd = [python_exe, "-m", "pip", "install", pkg]
    elif req.install_type == "npm":
        npm_exe = shutil.which("npm") or "npm"
        cmd = [npm_exe, "install", "-g", pkg]
    elif req.install_type == "winget":
        winget_exe = shutil.which("winget") or "winget"
        cmd = [winget_exe, "install", "--exact", "--id", pkg, "--silent", "--accept-package-agreements", "--accept-source-agreements"]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported install type '{req.install_type}'")

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        success = proc.returncode == 0
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")

        return {
            "status": "success" if success else "error",
            "package": pkg,
            "type": req.install_type,
            "exit_code": proc.returncode,
            "output": out[-1500:] if len(out) > 1500 else out,
            "message": f"Successfully installed '{pkg}'!" if success else f"Installation exited with code {proc.returncode}"
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"Installation of '{pkg}' timed out after 120s.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run installer: {str(e)}")


@router.get("/docker/status")
async def get_docker_status():
    """Returns current Docker daemon status and isolation capability."""
    from backend.core.container_runner import is_docker_running
    active = is_docker_running()
    return {
        "running": active,
        "mode": "docker_isolated_container" if active else "sandboxed_runner",
        "label": "Docker (--network none)" if active else "Safe Sandbox Jail"
    }


@router.post("/docker/start")
async def trigger_start_docker():
    """Starts Docker Desktop on host and waits/monitors initialization."""
    from backend.core.container_runner import start_docker_desktop
    return start_docker_desktop()



# ========================================================
# 1-CLICK CLOUD GPU BRIDGE & QUOTA/CREDIT TRACKING APIS
# ========================================================

class SwitchGpuTargetRequest(BaseModel):
    provider: str = Field(..., description="'local', 'kaggle', 'colab', or 'purchased'")
    custom_url: Optional[str] = Field(None, description="Tunnel URL, e.g. https://xxx.loca.lt or ngrok")

class UpdatePaidCreditsRequest(BaseModel):
    purchased_usd: float = Field(..., description="Total USD credits purchased")
    remaining_usd: float = Field(..., description="Current remaining USD credits")
    api_key: Optional[str] = None

@router.get("/cloud_gpu/status")
def get_cloud_gpu_bridge_status():
    """Returns current active GPU target, free tier quota limits, and remaining credits."""
    from backend.core.cloud_gpu_bridge import CloudGpuBridge
    return CloudGpuBridge.get_status()

@router.post("/cloud_gpu/switch")
def switch_cloud_gpu_target(req: SwitchGpuTargetRequest):
    """Switches active inference target between Local GPU, Free Cloud (Kaggle/Colab), or Paid."""
    from backend.core.cloud_gpu_bridge import CloudGpuBridge
    return CloudGpuBridge.switch_provider(req.provider, req.custom_url)

@router.post("/cloud_gpu/credits")
def update_paid_cloud_credits(req: UpdatePaidCreditsRequest):
    """Updates purchased and remaining balance for paid cloud GPU services (RunPod/Modal)."""
    from backend.core.cloud_gpu_bridge import CloudGpuBridge
    return CloudGpuBridge.update_paid_credits(req.purchased_usd, req.remaining_usd, req.api_key)

@router.get("/cloud_gpu/script/{provider}")
def get_one_click_cloud_script(provider: str):
    """Returns the ready-to-run 1-click script for Kaggle or Google Colab."""
    from backend.core.cloud_gpu_bridge import CloudGpuBridge
    script = CloudGpuBridge.get_cloud_one_click_script(provider)
    return {"provider": provider, "script": script}
