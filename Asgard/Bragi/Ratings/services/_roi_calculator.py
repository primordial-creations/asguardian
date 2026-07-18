"""
Bragi ROI Calculator

Finite-difference marginal-ROI ranking over the composite score model
(Plan 01 Phase C). The model is differentiable per metric utility: for each
metric we apply a standard improvement step, recompute the final score, and
rank the resulting deltas. Cap-lifting actions are special-cased because
removing a non-compensatory gate can dwarf any marginal utility gain.
"""

from typing import List

from Asgard.Bragi.Ratings.models._scoring_models import FileQualityScore, ROIAction

DEFAULT_STEP = 0.10

_ACTION_HINTS = {
    "bug_density": "Fix highest-severity bugs to reduce weighted issue density",
    "debt_ratio": "Pay down technical debt items to reduce the debt ratio",
    "complexity": "Refactor the most complex function below the threshold",
    "duplication": "Deduplicate the largest cloned block",
    "cycles": "Break a dependency cycle",
    "loc_penalty": "Split the file into smaller modules",
    "doc_coverage": "Document public functions",
    "type_coverage": "Add type annotations",
}


def compute_roi_actions(
    score: FileQualityScore, step: float = DEFAULT_STEP, top_n: int = 5
) -> List[ROIAction]:
    """
    Rank improvement actions by estimated final-score gain.

    Uses a finite-difference step on each metric utility, recomputing the
    hierarchical WAM/WGM with the same weights the engine used.
    """
    actions: List[ROIAction] = []

    # Cap-lifting action first: recompute without the cap.
    if score.cap.applied and score.cap.ceiling < score.base_score:
        actions.append(ROIAction(
            metric_id="cap",
            description=(
                f"Resolve: {score.cap.reason} - lifts the score cap from "
                f"{score.cap.ceiling:.2f} back to base {score.base_score:.2f}"
            ),
            score_delta=score.base_score - score.final_score,
            lifts_cap=True,
        ))

    measured = [c for c in score.category_scores if c.score is not None]
    total_cat_weight = sum(c.weight for c in measured) or 1.0

    for cat in measured:
        total_w = sum(u.weight for u in cat.utilities) or 1.0
        for u in cat.utilities:
            if u.utility >= 1.0:
                continue
            bumped_u = min(u.utility + step, 1.0)
            new_cat = cat.score + (bumped_u - u.utility) * (u.weight / total_w)
            # Recompute the WGM with this category's score replaced.
            product = 1.0
            for other in measured:
                value = new_cat if other is cat else other.score
                product *= max(value, 1e-9) ** (other.weight / total_cat_weight)
            new_final = min(product, score.cap.ceiling)
            delta = new_final - score.final_score
            if delta <= 0:
                continue
            actions.append(ROIAction(
                metric_id=u.metric_id,
                description=_ACTION_HINTS.get(u.metric_id, f"Improve {u.metric_id}"),
                score_delta=delta,
                lifts_cap=False,
            ))

    actions.sort(key=lambda a: a.score_delta, reverse=True)
    return actions[:top_n]
