from .. import models


def memory_from_trace(trace: models.DecisionTrace, case: models.Case) -> dict:
    tags = trace.tags or "人工修订,劳动仲裁"
    return {
        "title": f"{case.title} 的修订经验",
        "scenario": case.summary[:500] or f"{case.claimant} 与 {case.employer} 的劳动争议案件",
        "legal_issue": "劳动仲裁文书修订与证据策略",
        "rule_summary": trace.revision_reason,
        "decision_pattern": f"AI 原建议：{trace.ai_suggestion[:300]}\n人工定稿：{trace.human_revision[:500]}",
        "tags": tags,
    }
