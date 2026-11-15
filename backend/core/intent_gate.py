import re
from typing import Tuple

def classify_user_action_intent(prompt: str) -> Tuple[bool, str]:
    """
    Antigravity Frontier Intent Gate:
    Determines whether a user prompt is:
    - CONVERSATIONAL / INFORMATIONAL (False): Questions, explanations, general chat, advice.
      -> Must respond directly in chat. NEVER create files or workspaces.
    - ACTION / CODE / BUILD (True): Explicit instruction to write, create, build, fix, refactor, or test software.
      -> Route to agentic execution loop.
    """
    clean = (prompt or "").strip().lower()
    if not clean:
        return False, "empty"

    # Explicit question patterns -> Conversational
    question_starters = (
        "what", "why", "how", "who", "when", "where", "can you explain",
        "tell me about", "explain", "describe", "what do you know",
        "do you know", "is it possible", "should i", "which is better",
        "compare", "difference between", "hello", "hi", "hey"
    )

    # Check if prompt begins with an inquiry and has no direct imperative coding verb
    starts_as_question = any(clean.startswith(q) for q in question_starters) or clean.endswith("?")
    
    # Strong imperative software creation verbs
    build_verbs = (
        r"\b(build|create|make|code|implement|generate|develop|scaffold|write an app|write a script|write a program)\b",
        r"\b(refactor|fix the bug|fix error|repair|debug this file|patch|edit file)\b",
        r"\b(add feature|add endpoint|create endpoint|add route|setup routes)\b",
        r"\b(mount workspace|clone repo|run test|verify code)\b"
    )

    has_build_verb = any(re.search(pattern, clean) for pattern in build_verbs)

    # If it is framed purely as an informational question without imperative build directive -> Conversational
    if starts_as_question and not has_build_verb:
        return False, "inquiry"

    # If it explicitly has an imperative build verb -> Action
    if has_build_verb:
        return True, "build_task"

    # Heuristic: If prompt mentions code syntax/trace without asking to build -> Question
    if any(k in clean for k in ("error trace", "stack trace", "why is", "what does this mean")):
        return False, "diagnosis_inquiry"

    # Default to False (conversational) unless explicit build instruction is detected
    return False, "general_chat"
