"""
ai_manager.py — Core AI engine.
Every product record must pass through this module.
Removing this file MUST break the application's main purpose.
Uses Groq API with llama-3.3-70b-versatile for structured JSON responses.
"""

import os
import json
import time


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 2
TIMEOUT_SECONDS = 30


def _get_api_key():
    """Retrieve the Groq API key from environment."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        # Try loading from .env file
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return key


# ──────────────────────────────────────────────
# Core functions (required by framework)
# ──────────────────────────────────────────────

def build_prompt(record):
    """
    Construct a clear, specific prompt from the product record dict.
    Instructs the model to return structured JSON.
    """
    prompt = f"""You are an expert food retail waste-reduction analyst. Analyse the following product and return a JSON object with your assessment.

PRODUCT DATA:
- Product Name: {record.get("product_name", "Unknown")}
- Category: {record.get("category", "Unknown")}
- Quantity in Stock: {record.get("quantity", 0)}
- Current Selling Price: ${record.get("price", 0):.2f}
- Expiry Date: {record.get("expiry_date", "Unknown")}
- Days Until Expiry: {record.get("days_until_expiry", "Unknown")}
- Has Existing Discount: {record.get("has_existing_discount", False)}
- Is Member Product: {record.get("is_member", False)}

ANALYSIS INSTRUCTIONS:
1. Assess the urgency level based on days until expiry and quantity.
2. Recommend a discount percentage (0-70) considering time-to-expiry and likely demand.
3. Predict how much of the stock is likely to sell before expiry WITHOUT a discount.
4. Estimate waste cost if no action is taken (unsold quantity × price).
5. Determine a risk score from 1 (low) to 10 (critical).
6. Suggest a specific action plan.

RESPOND WITH ONLY THIS EXACT JSON STRUCTURE (no other text):
{{
    "urgency_level": "<one of: low, medium, high, critical>",
    "recommended_discount_pct": <integer 0-70>,
    "predicted_demand_units": <integer — estimated units that will sell before expiry without discount>,
    "estimated_unsold_units": <integer — quantity minus predicted demand>,
    "estimated_waste_cost": <float — estimated dollar value of wasted stock>,
    "risk_score": <integer 1-10>,
    "action_plan": "<a specific 1-2 sentence action recommendation>",
    "reasoning": "<brief explanation of the analysis>"
}}"""
    return prompt


def call_api(prompt):
    """
    Send the prompt to the Groq API.
    Catches connection errors, timeouts, and rate limits.
    Logs errors — never crashes.
    Returns the raw response text, or None on failure.
    """
    import urllib.request
    import urllib.error

    api_key = _get_api_key()
    if not api_key:
        return None

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a JSON-only response bot. You must respond with valid JSON and nothing else. No markdown, no code fences, no explanations outside the JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 512,
        "response_format": {"type": "json_object"}
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                GROQ_API_URL,
                data=payload,
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                raw_text = body["choices"][0]["message"]["content"]
                return raw_text

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass

            if e.code == 429:
                # Rate limited — back off and retry
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            else:
                return None

        except urllib.error.URLError:
            # Connection error — retry with backoff
            if attempt < MAX_RETRIES:
                time.sleep((attempt + 1) * 2)
                continue
            return None

        except Exception:
            return None

    return None


def parse_response(raw):
    """
    Extract and parse JSON from the raw API response string.
    Handles unexpected formats (e.g. markdown fences, extra text).
    Returns a dict or None on failure.
    """
    if raw is None:
        return None

    text = raw.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


def validate_response(data):
    """
    Validate the parsed response against the expected schema.
    Required keys, correct types, values in range.
    Returns (is_valid, cleaned_data_or_error_message).
    """
    if data is None:
        return False, "Response data is None"

    if not isinstance(data, dict):
        return False, "Response is not a dictionary"

    # Define required schema
    schema = {
        "urgency_level": {"type": str, "allowed": ["low", "medium", "high", "critical"]},
        "recommended_discount_pct": {"type": (int, float), "min": 0, "max": 70},
        "predicted_demand_units": {"type": (int, float), "min": 0},
        "estimated_unsold_units": {"type": (int, float), "min": 0},
        "estimated_waste_cost": {"type": (int, float), "min": 0},
        "risk_score": {"type": (int, float), "min": 1, "max": 10},
        "action_plan": {"type": str},
        "reasoning": {"type": str},
    }

    cleaned = {}
    for key, rules in schema.items():
        if key not in data:
            return False, f"Missing required key: {key}"

        value = data[key]

        # Type check
        if not isinstance(value, rules["type"]):
            # Try to coerce
            try:
                if rules["type"] == str:
                    value = str(value)
                elif rules["type"] == (int, float):
                    value = float(value)
            except (ValueError, TypeError):
                return False, f"Invalid type for {key}: expected {rules['type']}, got {type(value)}"

        # Range check for numbers
        if isinstance(value, (int, float)):
            if "min" in rules and value < rules["min"]:
                value = rules["min"]
            if "max" in rules and value > rules["max"]:
                value = rules["max"]

        # Allowed values check
        if "allowed" in rules:
            if isinstance(value, str):
                value = value.lower().strip()
            if value not in rules["allowed"]:
                return False, f"Invalid value for {key}: {value}. Allowed: {rules['allowed']}"

        cleaned[key] = value

    # Coerce numeric types to int where appropriate
    for int_key in ["recommended_discount_pct", "predicted_demand_units",
                     "estimated_unsold_units", "risk_score"]:
        if int_key in cleaned:
            cleaned[int_key] = int(round(cleaned[int_key]))

    cleaned["estimated_waste_cost"] = round(float(cleaned["estimated_waste_cost"]), 2)

    return True, cleaned


def process_record(record):
    """
    Full pipeline: build prompt → call API → parse → validate.
    Returns (success, ai_data_or_error_msg).
    This is the main entry point called by logic_manager.
    """
    prompt = build_prompt(record)
    raw = call_api(prompt)
    if raw is None:
        return False, "API call failed — check connection and API key"

    parsed = parse_response(raw)
    if parsed is None:
        return False, "Failed to parse AI response as JSON"

    is_valid, result = validate_response(parsed)
    if not is_valid:
        return False, f"AI response validation failed: {result}"

    return True, result
