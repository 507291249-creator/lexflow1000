from enum import Enum

from ...schemas import WorkflowStepCode


WORKFLOW_STEP_ORDER: tuple[WorkflowStepCode, ...] = (
    "case_input",
    "materials",
    "fact_review",
    "issue_review",
    "legal_analysis",
    "report",
)

FACT_REVIEWED_STATUSES = frozenset({"已确认", "已驳回"})
ISSUE_REVIEWED_STATUSES = frozenset({"人工确认", "分析中", "已完成"})
ANALYSIS_APPROVED_STATUSES = frozenset({"已接受", "已修改"})


class BlockerCode(str, Enum):
    CASE_INPUT_MISSING = "CASE_INPUT_MISSING"
    MATERIALS_MISSING = "MATERIALS_MISSING"
    FACTS_MISSING = "FACTS_MISSING"
    FACTS_PENDING_REVIEW = "FACTS_PENDING_REVIEW"
    FACTS_STALE = "FACTS_STALE"
    ISSUES_MISSING = "ISSUES_MISSING"
    ISSUES_PENDING_REVIEW = "ISSUES_PENDING_REVIEW"
    ISSUES_STALE = "ISSUES_STALE"
    ANALYSIS_MISSING = "ANALYSIS_MISSING"
    ANALYSIS_INCOMPLETE = "ANALYSIS_INCOMPLETE"
    ANALYSIS_STALE = "ANALYSIS_STALE"
    REPORT_MISSING = "REPORT_MISSING"
    REPORT_STALE = "REPORT_STALE"


BLOCKER_ACTION_LABELS: dict[BlockerCode, str] = {
    BlockerCode.CASE_INPUT_MISSING: "补充案件事实",
    BlockerCode.MATERIALS_MISSING: "上传或录入案件材料",
    BlockerCode.FACTS_MISSING: "运行事实提取",
    BlockerCode.FACTS_PENDING_REVIEW: "复核案件事实",
    BlockerCode.FACTS_STALE: "基于当前材料重新提取事实",
    BlockerCode.ISSUES_MISSING: "运行争点识别",
    BlockerCode.ISSUES_PENDING_REVIEW: "复核案件争点",
    BlockerCode.ISSUES_STALE: "基于当前事实重新识别争点",
    BlockerCode.ANALYSIS_MISSING: "运行法律分析",
    BlockerCode.ANALYSIS_INCOMPLETE: "完成并复核法律分析",
    BlockerCode.ANALYSIS_STALE: "基于当前输入重新运行法律分析",
    BlockerCode.REPORT_MISSING: "生成法律分析报告",
    BlockerCode.REPORT_STALE: "基于当前分析重新生成报告",
}
