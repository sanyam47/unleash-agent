import re
from typing import Tuple

def normalize_voice_phonetics(prompt: str) -> str:
    """Corrects common acoustic speech-to-text misinterpretations for PC hardware and voice commands."""
    text = prompt or ""
    # "my friends are loud / noisy / fast" -> "my fans are loud" (common hardware fan STT error)
    text = re.sub(r"\b(my|the)?\s*friends?\s+(are|is)?\s*(so\s+)?(loud|noisy|spinning|fast|running|hot)", r"\1 fans \2 \3\4", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(loud|noisy)\s+friends?\b", r"\1 fans", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(i\s+am|i['’]m|im)?\s*(taking|talking|thiking|thikning)\s+(?:to|of|about)\b", "i am thinking to", text, flags=re.IGNORECASE)
    return text


def classify_user_action_intent(prompt: str) -> Tuple[bool, str]:
    """
    Antigravity Frontier Intent Gate:
    Determines whether a user prompt is:
    - CONVERSATIONAL / INFORMATIONAL (False): Questions, explanations, general chat, advice.
      -> Must respond directly in chat. NEVER create files or workspaces.
    - ACTION / CODE / BUILD (True): Explicit instruction to write, create, build, fix, refactor, or test software.
      -> Route to agentic execution loop.
    """
    normalized = normalize_voice_phonetics(prompt)
    clean = (normalized or "").strip().lower()
    if not clean:
        return False, "empty"

    # Check for Jarvis Host Executive OS actions (takes precedence over question starters)
    jarvis_os_patterns = (
        r"\b(?:open|launch|start)\s+(?:the\s+|my\s+)?(whatsapp|telegram|discord|slack|teams|email|mail|sms)\s+(?:and|to|then)\s+(?:send\s+(?:a\s+)?message|message|text|mail|email)\b",
        r"\b(?:you\s+didn['’]t\s+(?:actually\s+)?(?:send\s+(?:a\s+)?message\s+(?:to\s+)?|message|text)|why\s+didn['’]t\s+you\s+(?:message|text|send)|didn['’]t\s+message)\s+([a-zA-Z0-9_\s]+?)\b",
        r"\b(?:can\s+you\s+)?(?:send\s+(?:a\s+)?message|message|text|want\s+to\s+message|wanna\s+message)\s+(?:(?:to|me)\s+)?([a-zA-Z0-9_\s]+?)\s+(?:on|via|through|using)\s+(whatsapp|telegram|discord|slack|teams|email|mail|sms)\b",
        r"\b(?:can\s+you\s+)?(?:send\s+(?:a\s+)?message|message|text|want\s+to\s+message|wanna\s+message)\s+(?:me\s+)?(?:on|via|through|using)\s+(whatsapp|telegram|discord|slack|teams|email|mail|sms)\b",
        r"\b(?:can\s+you\s+)?(?:send\s+(?:a\s+)?message\s+to|message|text)\s+([a-zA-Z0-9_]+)\s+(?:saying|that|with|text)?\s*[:\"']?.*[\"']?\b",
        r"\b(?:open|launch|start|run)\s+(?:the\s+|my\s+)?(whatsapp|terminal|wt|powershell|cmd|vscode|vs\s*code|code|spotify|chrome|edge|browser|firefox|calc|calculator|notepad|settings|task\s*mgr|task\s*manager|explorer|file\s*explorer|discord|slack|teams)\b",
        r"\b(open|browse(?:\s+to)?|navigate(?:\s+to)?|go\s+to|visit)\s+(https?://\S+|www\.\S+|youtube|google|github|reddit|twitter|x\.com)",
        r"\b(what is my battery|check (?:my\s+)?battery|battery (?:level|percentage|status|remaining)|how much (?:ram|disk|memory)|ram (?:usage|stats)|cpu (?:usage|cores|stats)|disk (?:space|free|usage)|system (?:info|stats|specs|status)|hardware (?:info|specs|telemetry)|why\s+(?:is\s+)?(?:it|my\s+pc|my\s+computer|my\s+laptop|the\s+system)\s+heating|check\s+(?:system\s+)?(?:thermals|temperature|heat|diagnostics)|why\s+(?:are\s+)?the\s+fans\s+(?:so\s+)?loud)\b",
        r"\b(?:(?:my|the)\s+)?(?:fans?|friends?|pc|laptop|computer)\s+(?:are|is)?\s*(?:so\s+)?(?:loud|noisy|spinning|running\s+fast|heating\s*up|hot)\b",
        r"\b(?:why\s+(?:is|are)\s+(?:my|the)?\s*(?:fans?|friends?|pc|laptop|computer)\s+(?:so\s+)?(?:loud|noisy|hot|spinning))\b",
        r"\b(?:fan\s+noise|fan\s+speed|loud\s+fans?|loud\s+friends?|noisy\s+fans?|noisy\s+friends?)\b",
        r"\b(?:did\s+you\s+(?:check(?:ed)?|look(?:\s+at)?|inspect(?:ed)?|view|read|audit)|check|inspect|audit|read|view|show|list|get|monitor)\s+(?:the\s+|my\s+)?(?:logs?|processes?|tasks?|system|thermals?|diagnostics?|telemetry|services?|status|hardware)\b",
        r"\b(?:logs?\s+and\s+processes?|processes?\s+and\s+logs?)\b",
        r"\b(?:top\s+(?:processes|apps|cpu|ram|memory)|process\s+(?:list|status|usage)|system\s+processes|running\s+processes)\b",
        r"\b(?:did\s+you\s+(?:actually\s+)?check|did\s+you\s+really\s+check)\b",
        r"\b(?:what\s+are\s+you\s+doing|what\s+are\s+you\s+working\s+on|are\s+you\s+running\s+something|are\s+you\s+doing\s+something|are\s+you\s+busy|what\s+is\s+running|is\s+anything\s+running)\b",
        r"\b(?:what(?:[\x27\s]?s|\s+is)?\s+(?:the\s+)?weather|how(?:[\x27\s]?s|\s+is)\s+(?:the\s+)?weather|weather(?:\s+forecast|\s+report)?|temperature\s+outside|is\s+it\s+(?:raining|cold|hot|sunny|snowing)|current\s+weather)\b",
        r"\b(?:what(?:[\x27\s]?s|\s+is)?\s+(?:the\s+)?(?:time|date)|what\s+time\s+is\s+it|what\s+day\s+is\s+it|current\s+(?:time|date))\b",
        r"\b(mute(\s+volume|\s+pc|\s+audio)?|unmute|volume\s+(up|down|mute)|(?:increase|decrease|lower|raise|turn\s+(?:up|down))\s+(?:the\s+)?volume)\b",
        r"\b(clipboard|copy\s+to\s+clipboard|set\s+clipboard|get\s+clipboard|read\s+clipboard|paste\s+from\s+clipboard)\b",
        r"\b(lock\s+(?:the\s+|my\s+|this\s+)?(?:pc|computer|screen|workstation|windows|machine|desktop))\b",
        r"\b(send|show|display|trigger)\s+(?:a\s+)?(?:desktop\s+notification|toast|desktop\s+alert)\b",
        r"\b(run|execute)\s+(?:a\s+)?(?:host\s+command|host\s+cli|command\s+on\s+host)\b",
        r"\b(search|find)\s+(?:the\s+)?(?:web|online|internet|google|bing|duckduckgo)\s+(?:for\s+)?",
        r"\b(search|find|look\s+up)\s+(?:for\s+)?.+\s+(?:online|on\s+(?:the\s+)?(?:web|internet|google|bing|reddit|twitter|youtube|x\.com))\b",
        r"\b(scroll\s+(?:down|up|to\s+bottom|to\s+top))\b",
        r"\b(take\s+(?:a\s+)?screenshot\s+of\s+(?:page|website|url|web|screen))\b",
        r"\b(extract\s+(?:text|content|links)\s+from\s+(?:website|page|url|https?://))\b",
        r"\b(click\s+(?:on\s+)?(?:the\s+)?(?:button|link|element)\s+['\"`]?\w+['\"`]?)\b",
        r"\b(take|capture|grab)\s+(?:a\s+)?(?:desktop\s+screenshot|desktop\s+capture|screen\s+capture|screenshot|screen\s+photo)\b",
        r"\b(what(?:'s|\s+is|\s+'s)?\s+(?:on|in)\s+(?:my\s+|the\s+)?(?:screen|desktop|display))\b",
        r"\b(look\s+at|see|inspect|read|check|analyze)\s+(?:my\s+|the\s+)?(?:screen|desktop|display|terminal(?:\s+error)?|error\s+on\s+screen)\b",
        r"\b(what|which)\s+(?:apps|windows|applications)\s+(?:are\s+)?(?:open|running)\b",
        r"\b(list|show|display|get)\s+(?:all\s+)?(?:open|active|running)\s+(?:windows|apps|applications)\b",
        r"\b(switch\s+to|focus|bring\s+to\s+front|activate)\s+(?:window|app|application)?\s*['\"`]?\w+['\"`]?\b",
        r"\b(click|double\s+click|right\s+click)\s+(?:at\s+|on\s+)?(?:\(?\d+\s*,\s*\d+\)?|(?:the\s+)?(?:screen|desktop|button|center|icon))\b",
        r"\b(type|input|write)\s+['\"`][^'\"`]+['\"`]",
        r"\b(press|hit|send|trigger)\s+(?:the\s+)?(?:key|hotkey|shortcut|keys)?\s*(?:ctrl|alt|win|shift|enter|esc|escape|backspace|tab|space|f[1-9]|f1[0-2])\b",
        r"\b(move\s+(?:the\s+)?(?:mouse|cursor)\s+to\s+\(?\d+\s*,\s*\d+\)?)\b",
        r"\b(where\s+is\s+(?:the\s+|my\s+)?(?:mouse|cursor)|(?:mouse|cursor)\s+(?:position|coords|coordinates))\b",
        r"\b(switch|set|change)\s+(?:the\s+)?(?:voice\s+)?(?:mode\s+)?to\s+(work|cinema|movie|fast)\b",
        r"\b(turn\s+on|enable|activate)\s+(work|cinema|movie)\s+mode\b",
        r"\b(speak|say)\s+(?:aloud|out\s+loud)\b",
        r"\b(enable|turn\s+on|activate|disable|turn\s+off|deactivate)\s+(?:the\s+)?wake\s*words?\b",
        r"\b(set|change|configure|add)\s+wake\s*words?\b",
        r"\b(remember\s+(?:that\s+)?|memorize\s+(?:that\s+)?|keep\s+in\s+mind\s+(?:that\s+)?|never\s+forget)\b",
        r"\b(what\s+do\s+you\s+remember|do\s+you\s+remember|who\s+is\s+my|recall\s+(?:from\s+)?memory)\b",
        r"\b(forget\s+(?:that\s+)?|delete\s+(?:from\s+)?memory|erase\s+memory)\b",
        r"\b(start|spawn|run)\s+(?:a\s+)?(?:background\s+task|daemon\s+task)\b",
        r"\b(status\s+of\s+(?:the\s+)?(?:background\s+)?task|how\s+is\s+the\s+background\s+task|is\s+the\s+task\s+done|check\s+background\s+tasks|list\s+background\s+tasks)\b",
        r"\b(pause\s+(?:the\s+)?(?:background\s+)?task|resume\s+(?:the\s+)?(?:background\s+)?task|cancel\s+(?:the\s+)?(?:background\s+)?task|stop\s+(?:the\s+)?(?:background\s+)?task)\b",
        r"\b(always\s+ask\s+me|ask\s+me\s+every\s*time|require\s+(?:my\s+)?approval|never\s+run\s+without\s+asking|prompt\s+me\s+before)\b"
    )
    if any(re.search(pat, clean) for pat in jarvis_os_patterns):
        return True, "jarvis_os_action"

    # Check for direct Jarvis conversational greetings & check-ins
    greeting_patterns = (
        r"^(?:hey|hello|hi|he|yo|greetings|good\s+(?:morning|afternoon|evening))\s*(?:jarvis|friday|buddy|there|assistant)?[.?!]*$",
        r"^(?:jarvis|friday)[,.]?\s*(?:hey|hello|hi|yo|are\s+you\s+there)?[.?!]*$",
        r"^(?:what(?:'s|\s+is)?\s*up|whatsup|whatsapp|wassup)\s*(?:jarvis|friday)?[.?!]*$",
        r"^(?:how\s+(?:are\s+you|are\s+things|is\s+it\s+going)|are\s+you\s+there|you\s+there)\s*(?:jarvis|friday)?[.?!]*$",
        r"^(?:are\s+you\s+listening|can\s+you\s+hear\s+me|do\s+you\s+hear\s+me|you\s+listening|listening)\s*(?:jarvis|friday|to\s+me)?[.?!]*$"
    )
    if any(re.search(pat, clean) for pat in greeting_patterns):
        return True, "jarvis_greeting"

    # Check for Audio / Voice Output Checks ("can't hear you", "i can't hear you", "can't listen you", "not speaking")
    audio_check_patterns = (
        r"\b(?:(?:i|we|user)?\s*(?:can[\x27\u2019]?t|cannot|cant|don[\x27\u2019]?t|dont|couldn[\x27\u2019]?t)\s+(?:hear|listen(?:\s+to)?)\s*(?:you|anything|audio|voice)?)\b",
        r"\b(?:why\s+(?:can[\x27\u2019]?t|cannot)\s+i\s+(?:hear|listen(?:\s+to)?)\s*(?:you|anything)?)\b",
        r"\b(?:no\s+(?:sound|audio|voice)|not\s+(?:audible|speaking|saying\s+anything)|can\s+you\s+speak(?:\s+up)?|i\s+hear\s+nothing|where\s+is\s+your\s+voice|i\s+can\s+not\s+hear\s+you)\b"
    )
    if any(re.search(pat, clean) for pat in audio_check_patterns):
        return True, "jarvis_audio_check"

    # Check for natural conversational dismissal
    dismissal_patterns = (
        r"^(?:(?:thanks?|thank\s+you)(?:\s+jarvis)?(?:[,\s]+that(?:'s|\s+is)\s+all)?|that(?:'s|\s+is)\s+all|dismissed|go\s+to\s+sleep|never\s+mind|goodbye|bye\s+jarvis)[.?!]*$",
    )
    if any(re.search(pat, clean) for pat in dismissal_patterns):
        return True, "jarvis_dismissal"

    # Emergency Voice Stop / Cancel Directives
    is_negated_stop = bool(re.search(r"\b(never|didn['’]?t|did\s+not|don['’]?t|do\s+not|haven['’]?t|have\s+not|why|who|not|without|stop\s+repeating)\b", clean))
    stop_patterns = (
        r"^(?:(?:hey\s+)?(?:jarvis\s+)?)?(?:stop(?:\s+the\s+process|\s+everything|\s+execution|\s+it|\s+task|\s+running|\s+generation)?|cancel(?:\s+execution|\s+task|\s+the\s+process)?|abort|halt|pause\s+execution|terminate\s+task|kill\s+task|stop\s+it|shut\s+up)[.?!]*$",
        r"\b(?:stop\s+the\s+process|stop\s+execution|cancel\s+execution|abort\s+mission|kill\s+task|terminate\s+process|halt\s+execution)\b"
    )
    if not is_negated_stop and any(re.search(pat, clean) for pat in stop_patterns):
        return True, "jarvis_stop"

    # Explicit question patterns -> Conversational
    # Explicit question starters
    question_starters = (
        "what", "why", "how", "who", "when", "where", "can you", "could you",
        "tell me about", "explain", "describe", "what do you know",
        "do you know", "is it", "should", "would", "which is better",
        "compare", "difference between", "hello", "hi", "hey"
    )

    # Check if prompt begins with an inquiry or ends with question mark
    starts_as_question = any(clean.startswith(q) for q in question_starters) or clean.endswith("?")
    
    # Antigravity Linguistic Mood Gate:
    # Contemplative, Subjunctive, & Opinion Moods (Brainstorming / Exploratory inquiries)
    # Even if they mention "build" or "create", the mood is conversational, NOT an order to scaffold workspace files!
    opinion_and_exploratory_patterns = (
        r"\b(?:what\s+do\s+you\s+think|what\s+are\s+your\s+thoughts|your\s+opinion|what(?:['’]?s|\s+is)\s+your\s+take|do\s+you\s+think|how\s+does\s+that\s+sound)\b",
        r"\b(?:is\s+it\s+(?:a\s+)?(?:good|bad|wise|viable|feasible|possible|worth(?:while|\s+it)?)|would\s+it\s+be\s+(?:good|viable|feasible|better))\b",
        r"\b(?:how\s+(?:would|can|could|do|should)\s+(?:i|we|you|one)\b)",
        r"\b(?:how\s+to\s+(?:build|make|create|develop|code))\b",
        r"\b(?:any\s+(?:ideas?|thoughts?|suggestions?|feedback|advice|tips?|recommendations?))\b",
        r"\b(?:steps?\s+(?:to|for)\s+(?:build|make|create|develop|code))\b",
        r"\b(?:guide\s+(?:to|for|on)|tutorial\s+(?:on|for)|best\s+(?:way|practices?|approach|stack|framework|language)\s+(?:to|for))\b",
        r"\b(?:i\s+am|i['’]m|im)?\s*(?:thinking|taking|talking|planning|hoping|considering)\s+(?:to|of|about)\b",
        r"\b(?:what\s+if\s+(?:we|i)|could\s+(?:we|i)|can\s+we|should\s+(?:we|i)|would\s+it\s+be\s+better\s+to)\b",
        r"\b(?:let['’]s|lets)\s+(?:discuss|brainstorm|talk\s+about|explore)\b",
        r"\b(?:i\s+want\s+to|i['’]d\s+like\s+to|planning\s+to)\s+(?:explore|discuss|brainstorm|talk\s+about)\b",
        r"\b(?:suggest|recommend|ideas?\s+for|opinion\s+on|advice\s+on|pros\s+and\s+cons)\b"
    )
    if any(re.search(pat, clean) for pat in opinion_and_exploratory_patterns):
        return False, "brainstorming_inquiry"

    # Explicit imperative software, workstation, file, or multi-step browser commands
    imperative_build_patterns = (
        r"^(?:please\s+)?(?:build|create|make|code|implement|generate|develop|scaffold|write|setup|fix|repair|debug|refactor|add|list|read|inspect|audit|search|find|edit|modify|update|delete|remove|run|execute|test|analyze|check|summarize)\b",
        r"\b(?:build\s+(?:me|this|a|an)|create\s+(?:me|this|a|an)|code\s+(?:me|this|a|an)|implement\s+(?:this|the)|write\s+(?:a|an|the)\s+(?:script|code|app|program))\b",
        r"\b(add feature|add endpoint|create endpoint|add route|setup routes|mount workspace|clone repo|run test|verify code|list (?:the )?files|read (?:the )?(?:first|last|\d+)?\s*lines?|inspect (?:the )?file)\b",
        r"(?:[a-zA-Z]:[\\/][^\s]+|~/[^\s]+)",
        r"\b[a-zA-Z0-9_\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|md|bat|sh|yml|yaml|sql)\b"
    )
    has_imperative_build = any(re.search(pat, clean) for pat in imperative_build_patterns)

    # Multi-step browser flow (e.g. "open github and search for...", "go to X and click...")
    has_browser_flow = bool(re.search(r"\b(?:open|go\s+to|visit|navigate\s+to)\s+[a-zA-Z0-9_\-\.]+\s+(?:and|then)\s+", clean))
    if has_browser_flow:
        return True, "frontier_task"

    # If it is framed as a question and has no direct imperative/file directive -> Conversational
    if starts_as_question and not has_imperative_build:
        return False, "inquiry"

    # If it explicitly has an imperative build/workstation directive -> Action
    if has_imperative_build:
        is_pure_build = bool(re.search(r"\b(?:build|create|make|code|implement|generate|develop|scaffold)\b", clean))
        return True, ("build_task" if is_pure_build else "frontier_task")

    # Heuristic: If prompt mentions code syntax/trace without asking to build -> Question
    if any(k in clean for k in ("error trace", "stack trace", "why is", "what does this mean")):
        return False, "diagnosis_inquiry"

    # Default to False (conversational) unless explicit build instruction is detected
    return False, "general_chat"


def is_daemon_task_request(prompt: str) -> bool:
    """
    Detects whether a user directive requests asynchronous, unbounded background execution.
    E.g. 'take as much time as you need', 'run in the background', 'daemon mode', 'take your time', 'in bg mode'.
    """
    clean = (prompt or "").strip().lower()
    daemon_cues = (
        r"\b(take\s+(?:as\s+much\s+)?time|take\s+your\s+time|(?:in|to)\s+(?:the\s+)?background|run\s+.*?\s+(?:in\s+)?(?:bg|background)|(?:in\s+)?bg\s+mode|daemon\s+mode|asynchronous|unbounded|overnight)\b"
    )
    return bool(re.search(daemon_cues, clean))

