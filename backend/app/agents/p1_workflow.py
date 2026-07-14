from __future__ import annotations

import re
from typing import Any

from .. import models
from .llm_provider import generate_structured
from .research_connectors import research_context


P1_INITIAL_WORKFLOW = [
    ("fact_extraction", "事实提取", "读取现场输入与上传材料，生成可人工确认的事实框架。"),
]


def fact_extraction(case: models.Case, material_text: str) -> dict[str, Any]:
    context = f"案件标题：{case.title}\n申请人：{case.claimant}\n被申请人：{case.employer}\n材料：\n{material_text[:14000]}"
    return generate_structured(
        task="fact_extraction",
        instructions="请提取结构化事实。关键事实和待确认事实均使用数组；时间线使用日期与事件字段。",
        context=context,
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "case_summary": {"type": "string"},
                "parties": {"type": "object", "additionalProperties": False, "properties": {"claimant": {"type": "string"}, "employer": {"type": "string"}, "other_parties": {"type": "array", "items": {"type": "string"}}}, "required": ["claimant", "employer", "other_parties"]},
                "key_facts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"category": {"type": "string"}, "content": {"type": "string"}, "confidence": {"type": "string"}, "source": {"type": "string"}}, "required": ["category", "content", "confidence", "source"]}},
                "timeline": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"date": {"type": "string"}, "event": {"type": "string"}}, "required": ["date", "event"]}},
                "pending_facts": {"type": "array", "items": {"type": "string"}},
                "fact_confidence": {"type": "string"},
            },
            "required": ["case_summary", "parties", "key_facts", "timeline", "pending_facts", "fact_confidence"],
        },
        fallback=lambda: _fallback_facts(case, material_text),
    )


def issue_identification(case: models.Case, facts: list[models.CaseFact]) -> dict[str, Any]:
    fact_lines = "\n".join(f"- {item.human_fact or item.ai_fact}" for item in facts if item.status == "已确认")
    return generate_structured(
        task="issue_identification",
        instructions="请从已确认事实中识别劳动争议争点。每项必须写明重要程度和关联事实，不能引入材料外争点。",
        context=f"案件：{case.title}\n已确认事实：\n{fact_lines}",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "issues": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "importance": {"type": "string"}, "related_facts": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "description", "importance", "related_facts"]}},
            },
            "required": ["issues"],
        },
        fallback=lambda: _fallback_issues(facts),
    )


def legal_analysis(
    case: models.Case,
    issue: models.CaseIssue,
    facts: list[models.CaseFact],
    memory_context: list[dict[str, Any]],
    supplementary_material: str = "",
) -> dict[str, Any]:
    fact_lines = "\n".join(f"- {item.human_fact or item.ai_fact}" for item in facts if item.status == "已确认")
    context = (
        f"案件：{case.title}\n争点：{issue.title}\n争点描述：{issue.description}\n已确认事实：\n{fact_lines}\n"
        f"可复用法律记忆：{memory_context}\n补充材料：{supplementary_material}\n"
        f"外部数据源占位结果：{research_context(issue.title)}"
    )
    return generate_structured(
        task="legal_analysis",
        instructions="请针对单一争点完成基础法律分析。适用法律应写出规则名称或条款方向；不要把不确定事实当成既定事实。",
        context=context,
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "core_conclusion": {"type": "string"},
                "risk_level": {"type": "string"},
                "main_reasons": {"type": "array", "items": {"type": "string"}},
                "applicable_law": {"type": "array", "items": {"type": "string"}},
                "counter_arguments": {"type": "array", "items": {"type": "string"}},
                "uncertainties": {"type": "array", "items": {"type": "string"}},
                "evidence_needs": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "string"},
            },
            "required": ["core_conclusion", "risk_level", "main_reasons", "applicable_law", "counter_arguments", "uncertainties", "evidence_needs", "confidence"],
        },
        fallback=lambda: _fallback_analysis(issue, facts, supplementary_material),
    )


def render_analysis(data: dict[str, Any]) -> str:
    return "\n".join([
        f"核心结论：{data['core_conclusion']}",
        f"风险等级：{data['risk_level']}",
        "主要理由：" + "；".join(data["main_reasons"]),
        "适用法律：" + "；".join(data["applicable_law"]),
        "反方观点：" + "；".join(data["counter_arguments"]),
        "不确定事项：" + "；".join(data["uncertainties"]),
        "证据需求：" + "；".join(data["evidence_needs"]),
        f"AI 置信度：{data['confidence']}",
    ])


def _fallback_facts(case: models.Case, material_text: str) -> dict[str, Any]:
    sentences = [item.strip() for item in re.split(r"[。；;\n]", material_text) if len(item.strip()) >= 8]
    selected = sentences[:6] or ["尚未提供足够事实，请补充入职、工资、管理关系和解除经过。"]
    key_facts = [
        {"category": _category(sentence), "content": sentence, "confidence": "中", "source": "现场输入或上传材料"}
        for sentence in selected
    ]
    pending = ["请核验关键日期、工资标准和解除通知的原始载体。"]
    return {
        "case_summary": material_text[:360] or f"{case.claimant} 与 {case.employer} 的劳动争议。",
        "parties": {"claimant": case.claimant, "employer": case.employer, "other_parties": []},
        "key_facts": key_facts,
        "timeline": [{"date": "待核验", "event": sentence[:80]} for sentence in selected[:4]],
        "pending_facts": pending,
        "fact_confidence": "中",
    }


def _fallback_issues(facts: list[models.CaseFact]) -> dict[str, Any]:
    text = " ".join(item.human_fact or item.ai_fact for item in facts)
    choices = []
    rules = [
        ("双方是否构成劳动关系", "需根据用工管理、劳动报酬和工作从属性核验。", "高"),
        ("解除或终止行为是否具有合法依据", "需核验解除理由、通知主体、送达与程序。", "高"),
        ("工资及相关补偿请求是否成立", "需核对工资基数、支付记录和计算期间。", "中"),
    ]
    for title, description, importance in rules:
        if title.startswith("双方") or any(word in text for word in ["解除", "工资", "加班", "合同"]):
            choices.append({"title": title, "description": description, "importance": importance, "related_facts": [item.human_fact or item.ai_fact for item in facts[:2]]})
    return {"issues": choices or [{"title": "劳动争议请求是否具备事实基础", "description": "需以已确认事实进一步明确请求范围。", "importance": "中", "related_facts": [item.human_fact or item.ai_fact for item in facts[:2]]}]}


def _fallback_analysis(issue: models.CaseIssue, facts: list[models.CaseFact], supplementary_material: str) -> dict[str, Any]:
    evidence = [item.human_fact or item.ai_fact for item in facts[:2]]
    return {
        "core_conclusion": f"围绕“{issue.title}”，现有已确认事实可支持形成初步主张，但仍应以原始材料核验关键节点。",
        "risk_level": "中",
        "main_reasons": [f"已确认事实与该争点存在直接关联：{item}" for item in evidence] or ["已确认事实数量不足，需要先补充材料。"],
        "applicable_law": ["《劳动合同法》关于劳动关系、劳动报酬和解除劳动合同的相关规则。"],
        "counter_arguments": ["对方可能否认劳动关系或主张已有合法解除、结算安排。"],
        "uncertainties": ["关键事实的原始载体、完整上下文和时间节点仍需核验。"],
        "evidence_needs": ["补充原始聊天记录、工资流水、考勤或工作安排记录。"] + ([f"已补充材料待核验：{supplementary_material}"] if supplementary_material else []),
        "confidence": "0.66",
    }


def _category(sentence: str) -> str:
    for word, category in [("工资", "工资支付"), ("解除", "解除行为"), ("合同", "劳动合同"), ("入职", "劳动关系"), ("考勤", "工作管理")]:
        if word in sentence:
            return category
    return "一般事实"
