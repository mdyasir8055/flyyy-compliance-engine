import json
import re
import time

import httpx

from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
FALLBACK_MODEL = "openai/gpt-oss-120b"


def _extract_json(text: str):
    """Groq/Llama sometimes wraps JSON in prose or code fences - strip that out."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)


def _chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = None) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured on the server")

    attempted = [settings.groq_model or FALLBACK_MODEL]
    if settings.groq_model != FALLBACK_MODEL:
        attempted.append(FALLBACK_MODEL)

    last_error = None
    for model in attempted:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            resp = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 404:
                last_error = RuntimeError(f"Groq model '{model}' is unavailable (404)")
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code == 404:
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("Groq request failed without a response")


_EXTRACTION_CHUNK_SIZE = 8000  # chars per chunk - conservative for free-tier token/rate limits


def extract_controls_from_policy(policy_text: str) -> list[dict]:
    chunks = [policy_text[i:i + _EXTRACTION_CHUNK_SIZE]
              for i in range(0, len(policy_text), _EXTRACTION_CHUNK_SIZE)] or [""]

    all_controls: list[dict] = []
    seen: set[tuple] = set()
    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        if idx > 0:
            time.sleep(3)  # space out calls to stay under per-minute token rate limits
        for control in _extract_controls_chunk(chunk, chunk_index=idx):
            key = (control.get("target"), control.get("metric"))
            if key not in seen:
                seen.add(key)
                all_controls.append(control)
    print(f"[extract_controls_from_policy] processed {len(chunks)} chunk(s), "
          f"extracted {len(all_controls)} unique control(s) total")
    return all_controls


def _extract_controls_chunk(policy_text: str, chunk_index: int = 0) -> list[dict]:
    """Extract controls from a single chunk of policy text. Returns [] on parse
    failure so one bad chunk can't take down the whole extraction - but logs
    the failure so it's visible in backend logs instead of silently vanishing."""
    system = (
        "You are a compliance engineer. You read security/compliance policy documents "
        "and extract concrete, measurable controls that can be automatically evaluated "
        "against infrastructure evidence. Respond with ONLY a JSON array, no prose."
    )
    user = f"""Extract compliance controls from the policy text excerpt below. This may be
one part of a larger multi-page policy document, so only extract what this excerpt actually
specifies - do not assume context you don't see here.

For each control return an object with these exact fields:
- "target": the system/resource the control applies to (e.g. "production_database_server")
- "metric": the measurable property (e.g. "cpu_utilization", "mfa_enabled", "tls_version")
- "operator": one of "<", ">", ">=", "<=", "=", "!="
- "threshold": the expected value as a string (e.g. "85%", "true", "1.2")
- "severity": one of "High", "Medium", "Low"

Extract every distinct control this excerpt specifies. If this excerpt contains no
extractable requirements (e.g. it's pure narrative text with no concrete rule), return
an empty array.

Policy text excerpt:
---
{policy_text}
---

Respond with ONLY the JSON array."""

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    for attempt in range(2):
        try:
            content = _chat(messages, max_tokens=3000)
            result = _extract_json(content)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"[extract_controls_chunk] chunk {chunk_index} attempt {attempt+1} failed: {e}")
            if attempt == 0:
                time.sleep(8)  # back off and retry once before giving up on this chunk
            else:
                return []
    return []


def reconcile_evidence(controls: list[dict], evidence: dict) -> list[dict]:
    """
    Ask Groq/Llama to map compliance controls to matching assets in arbitrary,
    differently-named evidence JSON. This is the step that lets the app accept
    ANY policy PDF against ANY evidence shape/naming convention, instead of
    requiring exact string matches between control.target and asset name.

    Returns a list of:
    [
      {
        "control_id": "<id>",
        "matches": [
          {
            "asset_name": "<identifier of the asset in the evidence>",
            "matched_field": "<raw field name in evidence holding this metric>",
            "value": <raw value copied exactly from evidence>,
            "confidence": "high" | "medium" | "low",
            "note": "<one short sentence explaining the mapping>"
          }
        ]
      }
    ]
    An empty "matches" list means the control has no corresponding evidence.
    Low-confidence matches are still returned (never silently dropped) so the
    caller can decide how to treat them - callers should treat "low" as
    "needs review" rather than a confident pass/fail.
    """
    system = (
        "You are a compliance evidence-matching engine. You are given a list of "
        "compliance controls (each with a target category and a metric) and a raw "
        "evidence JSON blob describing real infrastructure assets, in whatever shape "
        "or naming convention it was provided. Your job is to map each control to "
        "every asset in the evidence that it applies to, and identify which field in "
        "that asset's data represents the control's metric - even if the field name, "
        "asset naming convention, or JSON structure differs from the control's wording. "
        "Respond with ONLY a JSON array, no prose, no markdown fences."
    )

    controls_payload = [
        {
            "id": c.get("id"),
            "target": c.get("target"),
            "metric": c.get("metric"),
            "operator": c.get("operator"),
            "threshold": c.get("threshold"),
        }
        for c in controls
    ]

    user = f"""Controls to match:
{json.dumps(controls_payload, indent=2)}

Raw evidence JSON (asset inventory, arbitrary shape/naming):
---
{json.dumps(evidence)[:12000]}
---

For EACH control above, find every asset in the evidence it applies to. A control's
"target" is a category (e.g. "production_database_server"), so it may match multiple
assets of that type, or assets with entirely different naming (e.g. "prod-db-01",
"db-server-east-1"). Use each asset's type/tags/role/context to decide fit, not just
literal name similarity. For each match, find the specific field in that asset's raw
data that holds the value for the control's "metric" (field names may differ, e.g.
metric "encryption_at_rest" might appear as "isEncrypted" or "enc_enabled").

Return ONLY a JSON array, one object per control, in this exact shape:
[
  {{
    "control_id": "<the control's id>",
    "matches": [
      {{
        "asset_name": "<the identifier this asset uses in the evidence>",
        "matched_field": "<the raw field name that holds the metric value>",
        "value": <the raw value, copied exactly as it appears in evidence>,
        "confidence": "high" | "medium" | "low",
        "note": "<one short sentence explaining why this asset/field was matched>"
      }}
    ]
  }}
]

If a control has no matching asset anywhere in the evidence, return "matches": [] for it.
Respond with ONLY the JSON array."""

    content = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
    )
    result = _extract_json(content)
    if not isinstance(result, list):
        raise ValueError("Expected a JSON array from Groq reconciliation")
    return result


def generate_audit_reasoning(control: dict, actual_value, passed: bool) -> str:
    """Ask Groq/Llama to write a short, human-readable audit reasoning sentence."""
    system = (
        "You are a compliance auditor writing concise, plain-English reasoning "
        "for why a control passed or failed. One or two sentences only, no preamble."
    )
    user = (
        f"Control: {control.get('metric')} on {control.get('target')}\n"
        f"Rule: value {control.get('operator')} {control.get('threshold')}\n"
        f"Observed value: {actual_value}\n"
        f"Result: {'PASSED' if passed else 'FAILED'}\n\n"
        "Write the audit reasoning sentence."
    )
    try:
        return _chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
        ).strip()
    except Exception:
        # Fall back to a deterministic sentence if Groq is unavailable
        verb = "meets" if passed else "does not meet"
        return (
            f"{control.get('metric')} for {control.get('target')} is {actual_value}, "
            f"which {verb} the required threshold of {control.get('operator')} {control.get('threshold')}."
        )