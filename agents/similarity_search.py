import re

from .. import models


def recommend_memories(case: models.Case, memories: list[models.LegalMemory], limit: int = 5) -> list[dict]:
    query_terms = _terms(" ".join([case.title, case.summary, case.claimant, case.employer]))
    scored = []
    for memory in memories:
        memory_terms = _terms(" ".join([memory.title, memory.scenario, memory.legal_issue, memory.rule_summary, memory.tags or ""]))
        overlap = query_terms & memory_terms
        score = len(overlap) / max(len(query_terms), 1)
        if score > 0:
            scored.append((score, overlap, memory))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": memory.id,
            "title": memory.title,
            "legal_issue": memory.legal_issue,
            "scenario": memory.scenario,
            "decision_pattern": memory.decision_pattern,
            "tags": [tag.strip() for tag in (memory.tags or "").split(",") if tag.strip()],
            "score": round(score, 2),
            "matched_terms": sorted(overlap),
        }
        for score, overlap, memory in scored[:limit]
    ]


def _terms(text: str) -> set[str]:
    words = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]+", text.lower()))
    legal_keywords = {
        "劳动关系",
        "未签合同",
        "未签书面劳动合同",
        "劳动合同",
        "二倍工资",
        "工资流水",
        "工资",
        "违法解除",
        "解除",
        "微信",
        "聊天记录",
        "考勤",
        "入职时间",
        "证据链",
        "赔偿金",
    }
    words.update(keyword for keyword in legal_keywords if keyword in text)
    stop = {"申请人", "被申请人", "案件", "公司", "劳动", "仲裁"}
    return {word for word in words if word not in stop}
