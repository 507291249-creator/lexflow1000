from __future__ import annotations

from .. import models


STANDARD_WORKFLOW = [
    ("material_understanding", "材料理解", "读取材料并形成案件材料摘要。"),
    ("fact_structuring", "事实结构化", "提取、分类并等待人工确认案件事实。"),
    ("issue_identification", "争点识别", "识别需要优先处理的法律与事实争点。"),
    ("legal_research", "法律检索", "基于 mock 规则定位适用规范和证明重点。"),
    ("similar_case_analysis", "类案分析", "匹配现有 Legal Memory 中的可复用经验。"),
    ("integrated_argument", "综合论证", "组织支持观点、反方观点与证据策略。"),
    ("document_generation", "文书生成", "生成可供人工编辑的劳动仲裁文书初稿。"),
    ("human_review", "人工复核", "由承办律师确认事实、争点和 AI 输出。"),
    ("knowledge_deposition", "知识沉淀", "将已批准的工作结论转为候选 Legal Memory。"),
]


def structured_analysis(case: models.Case, issues: list[models.CaseIssue]) -> dict:
    issue_titles = [item.title for item in issues] or ["劳动关系与解除行为"]
    return {
        "core_conclusion": "现有材料足以支持优先围绕劳动关系、解除行为及工资差额开展仲裁主张，但解除依据和工资构成仍需补强。",
        "risk_level": "中",
        "main_reasons": [
            "工资流水、入职沟通和工作管理痕迹可形成劳动关系的初步证明链。",
            "解除通知的原始载体与送达过程会直接影响违法解除主张的稳定性。",
        ],
        "supporting_basis": [
            "《劳动合同法》关于劳动关系建立、书面劳动合同和违法解除的规则。",
            f"本案已识别争点：{'、'.join(issue_titles[:3])}。",
        ],
        "counter_arguments": [
            "被申请人可能主张双方属于合作或劳务关系。",
            "被申请人可能主张解除系员工主动离职或已协商一致。",
        ],
        "uncertainties": [
            "尚未核验解除通知的完整聊天上下文与原始设备。",
            "工资构成、奖金与加班费计算基础仍待当事人补充。",
        ],
        "next_evidence": [
            "导出并固定解除通知、工作安排和考勤的原始记录。",
            "补充银行流水、个税记录及工资条以核对工资基数。",
        ],
        "confidence": "0.74",
        "case_context": f"{case.claimant} 与 {case.employer} 的劳动仲裁争议。",
    }


def analysis_content(result: dict) -> str:
    return "\n".join([
        f"核心结论：{result['core_conclusion']}",
        f"风险等级：{result['risk_level']}",
        "主要理由：" + "；".join(result["main_reasons"]),
        "支持依据：" + "；".join(result["supporting_basis"]),
        "反方观点：" + "；".join(result["counter_arguments"]),
        "不确定事项：" + "；".join(result["uncertainties"]),
        "下一步证据：" + "；".join(result["next_evidence"]),
        f"AI 置信度：{result['confidence']}",
    ])


def mock_facts(case: models.Case, source_document: str) -> list[dict]:
    return [
        {
            "category": "劳动关系",
            "ai_fact": f"{case.claimant} 在 {case.employer} 接受工作安排并提供劳动，双方存在劳动关系的初步迹象。",
            "source_document": source_document,
            "confidence": "高",
        },
        {
            "category": "工资支付",
            "ai_fact": "现有材料显示存在工资支付与工资标准约定线索，具体金额和构成需要与流水、工资条核验。",
            "source_document": source_document,
            "confidence": "中",
        },
        {
            "category": "解除行为",
            "ai_fact": "双方对劳动关系终止的原因存在争议，需固定解除通知、送达时间与完整沟通上下文。",
            "source_document": source_document,
            "confidence": "中",
        },
    ]


def mock_issues() -> list[dict]:
    return [
        {
            "title": "双方是否构成劳动关系",
            "description": "需要从用工管理、劳动报酬和工作从属性三个维度核验。",
            "analysis_hint": "优先整理入职沟通、工作安排、考勤与工资流水。",
        },
        {
            "title": "解除行为是否具有合法依据",
            "description": "需要查明解除通知的主体、理由、送达和程序。",
            "analysis_hint": "固定解除通知原件及完整聊天记录。",
        },
        {
            "title": "仲裁请求及金额计算是否完整",
            "description": "需要核对工资基数、未签合同期间和相关补偿项目。",
            "analysis_hint": "补充工资条、银行流水和社保缴费记录。",
        },
    ]
