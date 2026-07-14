from __future__ import annotations

import re
from typing import Any

from .. import models
from .llm_provider import generate_structured
from .research_connectors import research_context
from .structured_schemas import FactExtractionOutput, IssueIdentificationOutput, LegalAnalysisOutput


P1_INITIAL_WORKFLOW = [
    ("fact_extraction", "事实提取", "读取现场输入与上传材料，生成可人工确认的事实框架。"),
]


def fact_extraction(case: models.Case, material_text: str) -> dict[str, Any]:
    context = (
        f"案件类型：{case.case_type}\n案件标题：{case.title}\n申请人：{case.claimant}\n"
        f"被申请人：{case.employer}\n原始事实：{case.raw_facts}\n材料：\n{material_text[:14000]}"
    )
    return generate_structured(
        task="fact_extraction",
        instructions="请提取结构化事实，不作法律结论。只摘取材料中可支持的内容；关键事实和待确认事实均使用数组；时间线使用日期与事件字段。",
        context=context,
        schema={
            "type": "object", "additionalProperties": False,
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
        output_model=FactExtractionOutput,
    )


def issue_identification(case: models.Case, facts: list[models.CaseFact]) -> dict[str, Any]:
    fact_lines = "\n".join(
        f"- [事实ID:{item.id}] {item.human_fact or item.ai_fact}"
        for item in facts if item.status == "已确认"
    )
    return generate_structured(
        task="issue_identification",
        instructions=f"请从已确认事实中识别{case.case_type}争点。每项必须写明重要程度和关联事实 ID；related_fact_ids 只能填写给定的事实 ID，不能引入材料外争点。",
        context=f"案件类型：{case.case_type}\n案件：{case.title}\n已确认事实：\n{fact_lines}",
        schema={
            "type": "object", "additionalProperties": False,
            "properties": {
                "issues": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "importance": {"type": "string"}, "related_fact_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "description", "importance", "related_fact_ids"]}},
            },
            "required": ["issues"],
        },
        fallback=lambda: _fallback_issues(facts),
        output_model=IssueIdentificationOutput,
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
        f"案件类型：{case.case_type}\n案件：{case.title}\n争点：{issue.title}\n争点描述：{issue.description}\n已确认事实：\n{fact_lines}\n"
        f"可复用法律记忆：{memory_context}\n补充材料：{supplementary_material}\n"
        f"外部数据源占位结果：{research_context(issue.title)}"
    )
    return generate_structured(
        task="legal_analysis",
        instructions="请针对单一争点完成基础法律分析。legal_directions 只写基于材料的法律分析方向，不得暗示已检索权威法律数据库；不要把不确定事实当成既定事实，并提供下一步行动。",
        context=context,
        schema={
            "type": "object", "additionalProperties": False,
            "properties": {
                "core_conclusion": {"type": "string"}, "risk_level": {"type": "string"},
                "main_reasons": {"type": "array", "items": {"type": "string"}},
                "legal_directions": {"type": "array", "items": {"type": "string"}},
                "counter_arguments": {"type": "array", "items": {"type": "string"}},
                "uncertainties": {"type": "array", "items": {"type": "string"}},
                "evidence_needs": {"type": "array", "items": {"type": "string"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "string"},
            },
            "required": ["core_conclusion", "risk_level", "main_reasons", "legal_directions", "counter_arguments", "uncertainties", "evidence_needs", "next_actions", "confidence"],
        },
        fallback=lambda: _fallback_analysis(issue, facts, supplementary_material),
        output_model=LegalAnalysisOutput,
    )


def render_analysis(data: dict[str, Any]) -> str:
    return "\n".join([
        f"核心结论：{data['core_conclusion']}",
        f"风险等级：{data['risk_level']}",
        "主要理由：" + "；".join(data["main_reasons"]),
        "法律分析方向：" + "；".join(data["legal_directions"]),
        "反方观点：" + "；".join(data["counter_arguments"]),
        "不确定事项：" + "；".join(data["uncertainties"]),
        "证据需求：" + "；".join(data["evidence_needs"]),
        "下一步行动：" + "；".join(data["next_actions"]),
        f"AI 置信度：{data['confidence']}",
    ])


def _fallback_facts(case: models.Case, material_text: str) -> dict[str, Any]:
    sentences = [item.strip() for item in re.split(r"[。；;\n]", material_text) if len(item.strip()) >= 8]
    selected = sentences[:6] or ["尚未提供足够事实，请补充案件主体、关键经过、时间节点和书面材料。"]
    return {
        "case_summary": material_text[:360] or f"{case.claimant} 与 {case.employer} 的{case.case_type}。",
        "parties": {"claimant": case.claimant, "employer": case.employer, "other_parties": []},
        "key_facts": [{"category": _category(sentence), "content": sentence, "confidence": "中", "source": "现场输入或上传材料"} for sentence in selected],
        "timeline": [{"date": "待核验", "event": sentence[:80]} for sentence in selected[:4]],
        "pending_facts": ["请核验关键日期、主体身份、金额或责任承担的原始载体。"],
        "fact_confidence": "中",
    }


def _fallback_issues(facts: list[models.CaseFact]) -> dict[str, Any]:
    text = " ".join(item.human_fact or item.ai_fact for item in facts)
    rules = [
        ("案件主体及法律关系是否成立", "需根据主体身份、权利义务和实际履行情况核验。", "高"),
        ("关键行为或责任承担是否具有事实依据", "需核验关键行为、通知、履行和时间节点。", "高"),
        ("请求范围及金额计算是否成立", "需核对计算基础、期间和支付或履行记录。", "中"),
    ]
    choices = [
        {"title": title, "description": description, "importance": importance, "related_fact_ids": [str(item.id) for item in facts[:2]]}
        for title, description, importance in rules
        if title.startswith("案件主体") or any(word in text for word in ["解除", "工资", "加班", "合同", "付款", "侵权"])
    ]
    return {"issues": choices or [{"title": "案件请求是否具备事实基础", "description": "需以已确认事实进一步明确请求范围。", "importance": "中", "related_fact_ids": [str(item.id) for item in facts[:2]]}]}


def _fallback_analysis(issue: models.CaseIssue, facts: list[models.CaseFact], supplementary_material: str) -> dict[str, Any]:
    evidence = [item.human_fact or item.ai_fact for item in facts[:2]]
    return {
        "core_conclusion": f"围绕“{issue.title}”，现有已确认事实可支持形成初步主张，但仍应以原始材料核验关键节点。",
        "risk_level": "中",
        "main_reasons": [f"已确认事实与该争点存在直接关联：{item}" for item in evidence] or ["已确认事实数量不足，需要先补充材料。"],
        "legal_directions": ["围绕构成要件、举证责任和程序要求核验现有材料。"],
        "counter_arguments": ["对方可能否认关键事实、责任基础或主张已有结算、履行安排。"],
        "uncertainties": ["关键事实的原始载体、完整上下文和时间节点仍需核验。"],
        "evidence_needs": ["补充原始聊天记录、书面协议、支付凭证和履行记录。"] + ([f"已补充材料待核验：{supplementary_material}"] if supplementary_material else []),
        "next_actions": ["核验关键事实的原始载体和完整上下文。", "根据核验结果调整主张和证据清单。"],
        "confidence": "0.66",
    }


def _category(sentence: str) -> str:
    for word, category in [("工资", "工资支付"), ("解除", "解除行为"), ("合同", "合同关系"), ("入职", "关系建立"), ("考勤", "工作管理"), ("付款", "履行情况")]:
        if word in sentence:
            return category
    return "一般事实"
