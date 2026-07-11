from .. import models


def generate_risk(case: models.Case, evidences: list[models.Evidence]) -> dict:
    names = " ".join(item.name for item in evidences)
    risks = []
    if "工资" not in names:
        risks.append("缺少工资流水或工资条，劳动关系与工资标准证明力不足。")
    if "解除" not in names and "微信" not in names:
        risks.append("缺少解除通知或聊天记录，违法解除事实可能难以固定。")
    if "入职" not in names:
        risks.append("缺少入职时间证据，二倍工资和赔偿金期间计算存在不确定性。")
    if not risks:
        risks.append("核心证据链较完整，但仍需核验原始载体、时间戳和主体身份。")
    risks.append("金额计算需结合实际工资、工作年限、当地仲裁口径进行人工复核。")
    return {"title": "证据缺口与风险提示", "content": "\n".join(f"- {item}" for item in risks)}
