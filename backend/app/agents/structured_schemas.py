"""Server-side contracts for every P1 structured AI task."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartyOutput(StrictModel):
    claimant: str
    employer: str
    other_parties: list[str] = Field(default_factory=list)


class FactItemOutput(StrictModel):
    category: str
    content: str
    confidence: str
    source: str


class TimelineItemOutput(StrictModel):
    date: str
    event: str


class FactExtractionOutput(StrictModel):
    case_summary: str
    parties: PartyOutput
    key_facts: list[FactItemOutput] = Field(default_factory=list)
    timeline: list[TimelineItemOutput] = Field(default_factory=list)
    pending_facts: list[str] = Field(default_factory=list)
    fact_confidence: str


class IssueItemOutput(StrictModel):
    title: str
    description: str
    importance: str
    related_fact_ids: list[str] = Field(default_factory=list)


class IssueIdentificationOutput(StrictModel):
    issues: list[IssueItemOutput] = Field(default_factory=list)


class LegalAnalysisOutput(StrictModel):
    core_conclusion: str
    risk_level: str
    main_reasons: list[str] = Field(default_factory=list)
    legal_directions: list[str] = Field(default_factory=list)
    counter_arguments: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    evidence_needs: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    confidence: str
