"""
Environment weight profiles for composite scoring (DEEPTHINK_05 §3).

Profiles adjust dimension WEIGHTS only — never rule truth. The same
artifact yields identical findings and identical dimension sub-scores
under every profile; only the composite weighting differs. This keeps
dev/prod structural parity (DEEPTHINK_02 conclusion): a minikube chart
is not graded F for missing a PDB, but the finding is still reported.
"""

from typing import Dict

from Asgard.Volundr.Validation.models.score_models import ScoreDimension

#: Named environment profiles. Weights are normalized at scoring time.
ENVIRONMENT_PROFILES: Dict[str, Dict[ScoreDimension, float]] = {
    "production": {
        ScoreDimension.SECURITY: 0.40,
        ScoreDimension.OPERABILITY: 0.30,
        ScoreDimension.COMPLETENESS: 0.15,
        ScoreDimension.MAINTAINABILITY: 0.15,
    },
    "staging": {
        ScoreDimension.SECURITY: 0.40,
        ScoreDimension.OPERABILITY: 0.25,
        ScoreDimension.COMPLETENESS: 0.20,
        ScoreDimension.MAINTAINABILITY: 0.15,
    },
    "development": {
        ScoreDimension.SECURITY: 0.45,
        ScoreDimension.OPERABILITY: 0.15,
        ScoreDimension.COMPLETENESS: 0.20,
        ScoreDimension.MAINTAINABILITY: 0.20,
    },
    "sandbox": {
        ScoreDimension.SECURITY: 0.50,
        ScoreDimension.OPERABILITY: 0.05,
        ScoreDimension.COMPLETENESS: 0.20,
        ScoreDimension.MAINTAINABILITY: 0.25,
    },
}


def profile_weights(environment: str) -> Dict[ScoreDimension, float]:
    """Weights for a named environment (unknown names fall back to production)."""
    return dict(
        ENVIRONMENT_PROFILES.get(environment, ENVIRONMENT_PROFILES["production"])
    )
