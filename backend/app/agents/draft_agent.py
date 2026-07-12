from typing import Optional

from .. import models


def generate_draft(case: models.Case, analysis: Optional[str], evidences: list[models.Evidence]) -> dict:
    evidence_list = "\n".join(f"{idx + 1}. {item.name}：{item.fact_to_prove}" for idx, item in enumerate(evidences))
    content = f"""劳动仲裁申请书（初稿）

申请人：{case.claimant}
被申请人：{case.employer}

仲裁请求：
1. 请求确认申请人与被申请人之间存在劳动关系；
2. 请求被申请人支付未签订书面劳动合同的二倍工资差额；
3. 请求被申请人支付违法解除劳动关系赔偿金；
4. 请求被申请人承担本案相关法律责任。

事实与理由：
{case.summary}

根据现有材料，申请人能够提交以下证据：
{evidence_list or "1. 当前证据尚待补充。"}

法律分析摘要：
{analysis or "待补充法律分析。"}

以上初稿由 LexFlow MVP 自动生成，建议律师结合原始材料、当地裁审口径和金额计算表进一步修订。
"""
    return {"title": "劳动仲裁申请书初稿", "content": content}
