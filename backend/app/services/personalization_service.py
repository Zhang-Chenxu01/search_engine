"""Personalization service — compute user preference scores and re-rank results.

Scoring is rule-based and fully explainable.  No modifications are made to
Elasticsearch — all re-ranking happens in the service layer.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.schemas.search import SearchResultItem

# ── Role → weighted keywords ──────────────────────────────────
#
# Each keyword carries a boost weight.  Longer / more specific
# keywords get higher weights because a match is more intentional.

ROLE_KEYWORDS: dict[str, dict[str, float]] = {
    "undergraduate": {
        "教务": 1.0, "课程": 1.0, "考试": 1.0, "奖学金": 1.5,
        "本科": 0.8, "选课": 1.5, "学分": 1.2, "评教": 1.5,
        "四六级": 2.0, "保研": 2.0, "双学位": 2.0, "交换": 1.5,
        "社团": 0.5, "军训": 0.8, "助学金": 1.5,
    },
    "graduate": {
        "研究生": 1.0, "科研": 1.2, "讲座": 0.8, "培养方案": 2.0,
        "导师": 1.5, "学位": 1.0, "论文": 1.2, "答辩": 2.0,
        "博士": 1.5, "硕士": 1.0, "学术": 1.0, "实验室": 1.2,
        "课题": 1.5, "基金": 1.2, "SCI": 2.0, "专利": 1.5,
    },
    "teacher": {
        "教师": 1.0, "教学": 1.0, "科研": 1.2, "项目": 1.0,
        "基金": 1.5, "申报": 1.2, "人才": 1.0, "评聘": 2.0,
        "学科": 1.0, "实验室": 1.0, "课题": 1.5,
    },
    "job_seeker": {
        "就业": 1.5, "招聘": 1.5, "实习": 1.5, "宣讲会": 2.0,
        "求职": 2.0, "春招": 2.5, "秋招": 2.5, "offer": 2.0,
        "面试": 1.5, "简历": 1.5, "职业": 1.0, "生涯": 1.0,
        "选调": 2.0, "公务员": 1.5, "企业": 0.8,
    },
    # visitor has no role keywords — neutral ranking
}

# ── Scoring weights ───────────────────────────────────────────
W_TITLE   = 2.0   # keyword / college / interest appears in title
W_CONTENT = 0.5   # keyword / college / interest appears in content snippet
W_CATEGORY = 1.5  # interest appears in category


@dataclass
class UserProfile:
    """Lightweight snapshot of the current user for personalization."""
    role: str = "visitor"
    college: str = ""
    interests: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────

def _count_keyword_hits(text: str, keywords: dict[str, float]) -> float:
    """Sum weights of *keywords* found in *text* (case-insensitive)."""
    lower = text.lower()
    total = 0.0
    for kw, weight in keywords.items():
        if kw.lower() in lower:
            total += weight
    return total


def _count_interest_hits(text: str, interests: list[str]) -> int:
    """Count how many distinct *interests* appear in *text*."""
    lower = text.lower()
    return sum(1 for i in interests if i.lower() in lower)


# ── Core scoring function ─────────────────────────────────────

def compute_preference_score(
    item: SearchResultItem,
    profile: UserProfile,
) -> float:
    """Compute a user-preference bonus for a single search result.

    The score is the sum of four sub-scores:

    1. **Role match** — keywords associated with the user's role
       appear in the title or snippet.
    2. **College match** — the user's college name appears in
       the title, source_site, or snippet.
    3. **Interest match** — the user's declared interests appear
       in the title, snippet, or category.

    Returns 0.0 if the user is a visitor with no college or interests.
    """
    score = 0.0
    title = item.title
    snippet = item.snippet
    category = item.category
    source_site = item.source_site

    # 1. Role-keyword matching
    keywords = ROLE_KEYWORDS.get(profile.role, {})
    if keywords:
        score += W_TITLE   * _count_keyword_hits(title, keywords)
        score += W_CONTENT * _count_keyword_hits(snippet, keywords)

    # 2. College matching (skip empty college)
    college = (profile.college or "").strip()
    if college:
        if college in title:
            score += W_TITLE
        if college in snippet or college in source_site:
            score += W_CONTENT

    # 3. Interest matching (skip empty list)
    if profile.interests:
        score += W_TITLE    * _count_interest_hits(title, profile.interests)
        score += W_CONTENT  * _count_interest_hits(snippet, profile.interests)
        score += W_CATEGORY * _count_interest_hits(category, profile.interests)

    return round(score, 4)


# ── Re-ranking ────────────────────────────────────────────────

def re_rank(
    items: list[SearchResultItem],
    profile: Optional[UserProfile] = None,
) -> list[SearchResultItem]:
    """Re-rank *items* by ``final_score = es_score + preference_score``.

    If *profile* is ``None`` (anonymous user), items are returned unchanged
    except that ``final_score`` equals ``es_score``.
    """
    if not items:
        return items

    profile = profile or UserProfile()  # visitor defaults → 0 bonus

    for it in items:
        es = it.es_score or 0.0
        pref = compute_preference_score(it, profile) if profile else 0.0
        it.preference_score = pref
        it.final_score = round(es + pref, 4)

    # Sort descending by final_score, then by es_score as tie-breaker
    items.sort(key=lambda x: (x.final_score or 0, x.es_score or 0), reverse=True)
    return items
