"""
Env-var interpolation immunity for generated pipelines.

A ``run:`` script containing ``${{ ... }}`` is a script-injection primitive:
GitHub Actions performs textual substitution *before* the shell parses the
script, so attacker-controlled context values (PR titles, branch names,
issue bodies, commit messages) become shell code. The fix is structural:
every expression is hoisted into an ``env:`` variable and the script
references ``"$VAR"`` instead — the shell then treats the value as data,
never as code.

This pass runs on ``StepConfig`` objects before platform rendering, so all
emitters share the same immunity guarantee: zero ``${{`` ever appears
inside a rendered ``run:`` string.
"""

import re
from typing import Dict, List, Tuple

from Asgard.Volundr.CICD.models.cicd_models import StepConfig

_EXPR_RE = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")

# Contexts an attacker can influence (DEEPTHINK_04 Domain A). Everything is
# hoisted regardless; this list drives severity in the validation engine.
UNTRUSTED_CONTEXT_RE = re.compile(
    r"github\.(event\.|head_ref|base_ref)|inputs\."
)


def _env_name(expression: str, taken: Dict[str, str]) -> str:
    """Derive a stable shell-safe env var name for an expression."""
    base = re.sub(r"[^A-Za-z0-9]+", "_", expression).strip("_").upper()
    if not base or base[0].isdigit():
        base = f"CTX_{base}"
    name = base
    suffix = 2
    while name in taken and taken[name] != expression:
        name = f"{base}_{suffix}"
        suffix += 1
    return name


def harden_step(step: StepConfig) -> StepConfig:
    """Rewrite ``${{ ... }}`` in a step's run script into env indirection."""
    if not step.run or "${{" not in step.run:
        return step

    env: Dict[str, str] = dict(step.env)
    taken: Dict[str, str] = {}
    for name, value in env.items():
        match = _EXPR_RE.fullmatch(value.strip()) if isinstance(value, str) else None
        if match:
            taken[name] = match.group(1)

    def _replace(match: "re.Match[str]") -> str:
        expression = match.group(1)
        for name, expr in taken.items():
            if expr == expression:
                return f'"${name}"'
        name = _env_name(expression, taken)
        taken[name] = expression
        env[name] = "${{ " + expression + " }}"
        return f'"${name}"'

    new_run = _EXPR_RE.sub(_replace, step.run)
    return step.model_copy(update={"run": new_run, "env": env})


def harden_steps(steps: List[StepConfig]) -> List[StepConfig]:
    """Apply interpolation immunity to every step in a job."""
    return [harden_step(step) for step in steps]


def find_untrusted_interpolations(script: str) -> List[Tuple[str, bool]]:
    """List ``(expression, is_untrusted)`` for expressions in a script."""
    found = []
    for match in _EXPR_RE.finditer(script or ""):
        expression = match.group(1)
        found.append((expression, bool(UNTRUSTED_CONTEXT_RE.search(expression))))
    return found
