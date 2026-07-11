import json
from pathlib import Path

from .. import models


RULE_PATH = Path(__file__).resolve().parent.parent / "mock" / "labor_law_rules.json"


def generate_analysis(case: models.Case, evidences: list[models.Evidence]) -> dict:
    rules = json.loads(RULE_PATH.read_text(encoding="utf-8"))
    evidence_text = " ".join(item.name + item.fact_to_prove for item in evidences)
    matched = []
    for rule in rules:
        if any(keyword in (case.summary + evidence_text) for keyword in rule["evidence_focus"]) or rule["issue"] in case.summary:
            matched.append(rule)
    if not matched:
        matched = rules[:2]

    parts = [
        f"案件要点：{case.claimant} 与 {case.employer} 之间围绕劳动关系、合同签订和解除行为存在争议。",
        "初步法律分析：",
    ]
    for rule in matched:
        parts.append(f"- {rule['issue']}：{rule['rule']} 证据重点包括：{'、'.join(rule['evidence_focus'])}。")
    parts.append("策略建议：优先固定入职时间、工资支付、工作管理和解除通知四类事实，再计算可主张金额。")
    return {"title": "AI 法律分析", "content": "\n".join(parts), "rules": matched}
