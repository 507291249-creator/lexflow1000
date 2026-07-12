from .. import models


def generate_evidences(case: models.Case, documents: list[models.Document]) -> list[dict]:
    text = "\n".join(doc.raw_text for doc in documents) + "\n" + (case.summary or "")
    evidences: list[dict] = []

    def add(name: str, category: str, fact: str, strength: str, notes: str):
        evidences.append({
            "name": name,
            "category": category,
            "fact_to_prove": fact,
            "source_document": documents[0].filename if documents else "案件摘要",
            "strength": strength,
            "notes": notes,
        })

    if "工资" in text or "银行" in text:
        add("工资流水", "劳动关系", "证明双方存在持续用工和工资支付关系", "high", "建议补充银行流水原件或电子回单。")
    if "微信" in text or "聊天" in text:
        add("微信/工作群聊天记录", "用工管理", "证明工作安排、解除通知或公司管理事实", "medium", "需保留原始载体并导出完整上下文。")
    if "未" in text and "合同" in text:
        add("未签书面劳动合同事实说明", "合同订立", "证明超过法定期限未签书面劳动合同", "medium", "可与入职通知、工资流水共同使用。")
    if "解除" in text or "不用来上班" in text:
        add("解除通知截图", "解除争议", "证明用人单位作出解除劳动关系的意思表示", "high", "需要标明发送人身份和发送日期。")
    if "入职" in text:
        add("入职通知或邮件", "入职时间", "证明入职日期、岗位与薪资约定", "high", "用于计算二倍工资和赔偿金期间。")

    if not evidences:
        add("案件材料摘要", "基础事实", "初步证明案件事实，需要继续补强原始材料", "low", "当前材料较少，建议上传工资、考勤、聊天记录。")

    return evidences
