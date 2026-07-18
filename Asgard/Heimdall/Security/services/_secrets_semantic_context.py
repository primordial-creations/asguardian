"""
Semantic context scoring for secrets detection (plan 07.3, DEEPTHINK_03 s3).

Layer-1 regex+entropy detection stays authoritative for *whether* a token
looks like a secret (DEEPTHINK_01: secrets are never AST-ified). This
module adds an orthogonal semantic signal on top of that: how strongly the
surrounding code implies the value is actually a live credential, based on
(a) the identifier it's assigned to and (b) whether it visibly flows into
an auth-shaped sink on the same line/window.

This is intentionally a small, explainable scoring function -- not a taint
engine -- so its behavior is auditable per DEEPTHINK_08 s3's epistemic
honesty requirement. Score is folded into (not a replacement for) the
existing entropy/pattern confidence, and is capped so it can raise
confidence into "certain" but a low semantic score alone never suppresses
a high-entropy finding (secrets are never test-suppressed, and semantic
uncertainty must not either).
"""

import re
from typing import Optional

# Identifier fragments that strongly imply a live secret when the LHS of
# an assignment contains them.
_HIGH_SIGNAL_IDENTIFIERS = re.compile(
    r"(?:aws_secret_access_key|secret_access_key|api_secret|client_secret|"
    r"private_key|access_token|auth_token|oauth_token|refresh_token|"
    r"session_secret|signing_key|encryption_key|db_password|database_password)",
    re.IGNORECASE,
)

# Identifier fragments that are weakly correlated with a secret (generic
# "key"/"token"/"secret"/"password" words alone) -- present but ambiguous.
_MEDIUM_SIGNAL_IDENTIFIERS = re.compile(
    r"(?:password|passwd|secret|token|api_key|apikey|credential)",
    re.IGNORECASE,
)

# Identifiers that indicate the matched value is NOT actually secret
# material even if it happens to be high-entropy (hash/id/fingerprint
# fields commonly hold high-entropy non-secret values).
_LOW_SIGNAL_IDENTIFIERS = re.compile(
    r"(?:commit_hash|commit_sha|checksum|fingerprint|uuid|request_id|"
    r"trace_id|correlation_id|etag|content_hash|file_hash|revision)",
    re.IGNORECASE,
)

# Behavioral proof: the value visibly flows into an auth-shaped sink
# (header assignment, URL query param, Authorization: Bearer, etc.) in
# the same line or immediate surrounding context.
_BEHAVIORAL_SINK = re.compile(
    r"(?:Authorization|authorization)\s*[:=]|"
    r"Bearer\s|"
    r"headers\s*\[\s*[\"']Authorization[\"']\s*\]|"
    r"\.set_header\(|"
    r"requests\.(?:get|post|put)\([^)]*(?:headers|auth)=",
    re.VERBOSE if False else 0,
)

# process.env / os.environ proximity -- the value is being *read from* an
# env var, not hardcoded; near-zero semantic score (plan text: "drop").
_ENV_PROXIMITY = re.compile(
    r"process\.env|os\.environ|os\.getenv|getenv\(|ENV\[|System\.getenv",
)


def _identifier_before_match(line: str, match_start_in_line: int) -> str:
    """Extract the assignment-target identifier text preceding the match on this line."""
    prefix = line[:match_start_in_line]
    # Grab the trailing identifier-ish token before an '=' or ':'.
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]{1,60})\s*[:=]\s*[\"']?$", prefix)
    return m.group(1) if m else ""


def semantic_score(
    line: str,
    match_start_in_line: int,
    context_window: str,
) -> float:
    """
    Score how strongly the surrounding code implies a live credential.

    Returns a float in [0.0, 1.0]:
        1.0  -- behavioral proof (flows into an auth-shaped sink)
        0.95 -- high-signal identifier name
        0.6  -- medium-signal (generic secret/password/token wording)
        0.1  -- low-signal identifier (hash/uuid/etag -- likely not a
                secret even if high-entropy) or env-var proximity
        0.4  -- no identifiable signal either way (neutral default)
    """
    identifier = _identifier_before_match(line, match_start_in_line)

    if _ENV_PROXIMITY.search(context_window):
        return 0.1
    if _LOW_SIGNAL_IDENTIFIERS.search(identifier):
        return 0.1
    if _BEHAVIORAL_SINK.search(context_window):
        return 1.0
    if _HIGH_SIGNAL_IDENTIFIERS.search(identifier):
        return 0.95
    if _MEDIUM_SIGNAL_IDENTIFIERS.search(identifier):
        return 0.6
    return 0.4


def fold_semantic_score(base_confidence: float, sem_score: float) -> float:
    """
    Fold the semantic score into the pattern/entropy confidence.

    Behavioral proof (1.0) can push confidence to "certain" even for a
    borderline pattern match. Low-signal identifiers pull confidence down
    but never below a floor -- semantic uncertainty is not proof of safety
    (unresolved-origin != safe, same principle as the deserialization/SSRF
    provenance resolvers), so the floor keeps the finding visible rather
    than disappearing it.
    """
    if sem_score >= 0.95:
        folded = max(base_confidence, 0.9 + (sem_score - 0.95) * 2)
    elif sem_score <= 0.15:
        folded = max(0.3, base_confidence - 0.25)
    else:
        # Neutral-to-medium signal: small nudge proportional to distance
        # from the neutral midpoint (0.4), never a large swing on its own.
        folded = base_confidence + (sem_score - 0.4) * 0.3
    return round(max(0.0, min(1.0, folded)), 2)
