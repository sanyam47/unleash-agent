"""
Gemini AI Client - Central module for all LLM calls in AI Trainer.
Uses google-genai (Gemini 2.0 Flash) which is FREE:
- 1500 requests/day free
- No credit card required
- Get key at: https://aistudio.google.com/apikey
"""
import os
import json
import re
from google import genai
from backend.core.config import settings

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "FILL_ME_IN":
            return None
        _client = genai.Client(api_key=api_key)
    return _client

get_gemini_client = _get_client


def gemini_available() -> bool:
    return _get_client() is not None


def _call_gemini(prompt: str) -> str:
    """Core Gemini call with resilient fallback across flash models."""
    client = _get_client()
    if client is None:
        raise RuntimeError("Gemini API key not configured")

    models_to_try = ["gemini-flash-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"]
    last_err = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            text = response.text.strip()
            return text
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"All Gemini models failed: {last_err}")


def interpret_intent_gemini(user_text: str) -> dict:
    """Extract ML intent from user text."""
    prompt = f"""You are an expert ML engineer. Analyze this user request and extract:
1. modality: one of ["text", "image", "audio", "numeric"]
2. task: one of ["classification", "regression"]
3. target_classes: list of class names the user wants to detect/classify

User request: "{user_text}"

Rules:
- For text sentiment: classes = ["positive", "negative"] or ["positive", "negative", "neutral"]
- For spam detection: classes = ["spam", "ham"]
- For any "detect X vs Y": classes = [X, Y]
- Extract ALL meaningful class names mentioned or strongly implied
- If regression (price, score, amount prediction): target_classes = []
- Return ONLY valid JSON, no explanation, no markdown

Example: {{"modality": "text", "task": "classification", "target_classes": ["spam", "ham"]}}"""

    text = _call_gemini(prompt)
    data = json.loads(text)
    return {
        "modality": data.get("modality", "text"),
        "task": data.get("task", "classification"),
        "target_classes": data.get("target_classes", ["class_a", "class_b"])
    }


def analyze_lab_instruction_gemini(model_name: str, current_classes: list, instruction: str) -> dict:
    """Analyze a Lab manipulation instruction."""
    prompt = f"""You are an AI model manipulation expert.

Model: {model_name}
Current classes: {current_classes}
User instruction: "{instruction}"

Determine the manipulation plan:
1. action: one of ["REFINE", "ADD_CLASS", "REMOVE_CLASS", "TWEAK_PARAMS"]
2. modality: one of ["text", "image", "audio", "numeric"]
3. target_classes: classes to KEEP (subset of current)
4. new_labels: NEW classes to add
5. remove_labels: existing classes to DELETE
6. reasoning: one sentence explaining what you will do

Rules:
- "add X" → new_labels=[X], action=ADD_CLASS
- "remove X" or "delete X" → remove_labels=[X], action=REMOVE_CLASS
- "improve" or "refine" → action=REFINE, keep all classes
- Be conservative - don't remove classes unless explicitly told to
- Return ONLY valid JSON, no markdown

Example: {{"action": "ADD_CLASS", "modality": "text", "target_classes": ["spam", "ham"], "new_labels": ["phishing"], "remove_labels": [], "reasoning": "Adding phishing class while keeping existing ones."}}"""

    text = _call_gemini(prompt)
    data = json.loads(text)
    return {
        "action": data.get("action", "REFINE"),
        "modality": data.get("modality", "text"),
        "target_classes": data.get("target_classes", current_classes),
        "new_labels": data.get("new_labels", []),
        "remove_labels": data.get("remove_labels", []),
        "reasoning": data.get("reasoning", "Interpreted from instruction"),
        "message": "Gemini AI analysis complete."
    }


def refine_lab_chat_gemini(previous_analysis: dict, feedback: str) -> dict:
    """Refine a lab plan based on user chat feedback."""
    prompt = f"""You are an AI model manipulation expert.

Current plan: {json.dumps(previous_analysis, indent=2)}

User feedback: "{feedback}"

Update the plan based on feedback:
- "keep X" or "don't remove X" → move X from remove_labels to target_classes
- "also add X" → append X to new_labels
- "just refine" → set action=REFINE, clear new_labels and remove_labels

Return the complete updated plan as valid JSON only, no markdown.
Same fields: action, modality, target_classes, new_labels, remove_labels, reasoning, message"""

    text = _call_gemini(prompt)
    data = json.loads(text)
    data["message"] = "Gemini AI refinement complete."
    return data


def label_text_gemini(text_input: str, target_classes: list) -> str:
    """Label a piece of text into one of the target classes."""
    prompt = f"""Classify this text into exactly ONE of these labels: {target_classes}

Text: "{text_input}"

Return ONLY the label word, nothing else. Must be one of: {target_classes}"""

    try:
        result = _call_gemini(prompt).strip().lower()
        valid = [c.lower() for c in target_classes]
        if result in valid:
            return result
        for c in valid:
            if c in result:
                return c
        return target_classes[0]
    except Exception:
        return target_classes[0]


def generate_training_data_gemini(prompt: str, target_classes: list, samples_per_class: int = 20) -> list:
    """Generate realistic synthetic training text data using Gemini."""
    all_data = []
    
    # Offline templates for fallback during rate limits
    offline_templates = {
        "spam": [
            "You have won a lottery, click here to claim your prize!",
            "Urgent: your account has been suspended. Please verify your details.",
            "Get a 50% discount on all products using coupon code WIN50",
            "Congratulations, you are selected for a free gift card.",
            "Make money fast working from home, guaranteed returns!",
            "Cheap meds online, no prescription needed.",
            "Meet hot singles in your area tonight.",
            "Your package could not be delivered, pay the shipping fee here.",
            "Special promotion just for you, don't miss out on this deal.",
            "Increase your followers by 10k today!"
        ],
        "important": [
            "Please review the attached invoice for your recent purchase.",
            "Reminder: Team meeting tomorrow at 10 AM in conference room B.",
            "Your password was successfully updated. If this wasn't you, contact support.",
            "Project deadline has been extended to next Friday.",
            "Here are the meeting notes from yesterday's discussion.",
            "Can you please approve the budget proposal by EOD?",
            "Your flight booking is confirmed. Here is your itinerary.",
            "Important update regarding your healthcare benefits.",
            "Action required: Please sign the attached document.",
            "The system will be down for maintenance this weekend.",
            "Congratulations on your promotion to Senior Analyst!",
            "You have been selected for the role of intern at our company.",
            "We are pleased to inform you that you have been selected for the interview.",
            "Congratulations, your application for the role has been accepted."
        ],
        "positive": [
            "I absolutely loved this product! Highly recommended.",
            "Great service, very fast and efficient.",
            "The food was delicious and the atmosphere was perfect.",
            "I'm so happy with my purchase, it exceeded my expectations.",
            "This is the best movie I've seen all year."
        ],
        "negative": [
            "Terrible experience, I will never buy from here again.",
            "The item arrived broken and customer service was useless.",
            "I hated this book, completely waste of time.",
            "Food was cold and tasteless. Do not go here.",
            "Worst purchase I have ever made, completely defective."
        ],
        "neutral": [
            "The package arrived on time.",
            "It is okay, nothing special but it works.",
            "I bought this yesterday.",
            "The color is exactly as shown in the picture.",
            "Standard quality, exactly what you would expect."
        ]
    }

    for cls in target_classes:
        gen_prompt = f"""Generate {samples_per_class} realistic, diverse example texts for a "{cls}" classification.
Context: {prompt}

Rules:
- Each example on its own line
- Be realistic and varied (different phrasings, lengths, styles)
- Do NOT number them, do NOT add labels, just raw text
- Make them look like real-world data

Generate {samples_per_class} examples now:"""

        try:
            text = _call_gemini(gen_prompt)
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 5]
            if len(lines) < 2:
                raise ValueError("Not enough data generated")
            for line in lines[:samples_per_class]:
                all_data.append({"text": line, "label": cls})
        except Exception as e:
            print(f"Gemini data gen error for class {cls}: {e}")
            
            # Find the best offline template
            cls_lower = cls.lower()
            matched_template = None
            for key, templates in offline_templates.items():
                if key in cls_lower:
                    matched_template = templates
                    break
            
            if matched_template:
                for i in range(samples_per_class):
                    # Duplicate and vary slightly
                    base_text = matched_template[i % len(matched_template)]
                    all_data.append({"text": f"{base_text} (sample {i})", "label": cls})
            else:
                for i in range(samples_per_class):
                    all_data.append({"text": f"This is an example text relating to the topic of {cls} - sample {i}", "label": cls})

    return all_data
