"""
Heimdall Security Hotspots - Security Hotspot Detection

A hotspot is syntactically flawless code whose safety depends on
extrinsic context (intent, provenance, topology) — never a failed
finding. Exactly six pattern families qualify (plan 08 / DEEPTHINK_10):

- Weak hashing (md5/sha1)
- Standard PRNG (random.*)
- Disabled transport security (verify=False, unverified SSL contexts)
- Permissive bindings / CORS (0.0.0.0, allow_origins=['*'])
- Opaque deserialization (pickle, marshal, unsafe yaml.load)
- cryptography.hazmat usage

Usage:
    from Asgard.Heimdall.Security.Hotspots import HotspotDetector, HotspotConfig

    detector = HotspotDetector()
    report = detector.scan(Path("./src"))
    print(f"Total hotspots: {report.total_hotspots}")
"""

__version__ = "2.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    PR_HOTSPOT_CAP,
    HotspotCategory,
    HotspotConfig,
    HotspotReport,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.Hotspots.services.hotspot_review import (
    HotspotReviewError,
    review_hotspot,
    shared_issues_audit_sink,
)
from Asgard.Heimdall.Security.Hotspots.services.pr_summary import (
    HotspotPRComments,
    build_pr_hotspot_comments,
)

__all__ = [
    "HotspotCategory",
    "HotspotConfig",
    "HotspotDetector",
    "HotspotPRComments",
    "HotspotReport",
    "HotspotReviewError",
    "PR_HOTSPOT_CAP",
    "ReviewPriority",
    "ReviewStatus",
    "SecurityHotspot",
    "build_pr_hotspot_comments",
    "review_hotspot",
    "shared_issues_audit_sink",
]
