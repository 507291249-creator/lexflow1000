"""Provider-neutral redaction helpers for the C1 user review workflow.

The service deliberately returns offsets and replacement instructions instead of
Presidio objects. A future Presidio recognizer can be added behind this small
boundary without coupling routes, ORM models, or the frontend to that library.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Sequence


ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
ID_CHECK_CODES = "10X98765432"
USCC_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"
USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)


@dataclass(frozen=True)
class RedactionCandidate:
    entity_type: str
    start_offset: int
    end_offset: int
    replacement: str
    action: str
    confidence: float
    rule_code: str
    original_fingerprint: str


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _partial_phone(value: str) -> str:
    return f"{value[:3]}****{value[-4:]}"


def _partial_email(value: str) -> str:
    local, _, domain = value.partition("@")
    return f"{(local[:1] or '*')}***@{domain}"


def _partial_address(value: str) -> str:
    province_city = re.match(r"^(.{2,3}?(?:省|市|自治区|特别行政区).{0,3}?(?:市|区|县)?)", value)
    return f"{province_city.group(1) if province_city else value[:4]}***"


class RedactionService:
    """Small rule-based recognizer suitable for Chinese legal-demo text.

    It intentionally avoids loading a heavyweight NLP model. Subject names from
    the case registration form are supplied as a dictionary, while structured
    identifiers use checksum-aware validation to reduce false positives.
    """

    priority = {
        "身份证": 100,
        "统一社会信用代码": 95,
        "银行卡": 90,
        "手机号": 80,
        "邮箱": 75,
        "固定电话": 70,
        "IP地址": 60,
        "企业名称": 50,
        "自然人姓名": 50,
        "地址": 45,
        "自定义敏感信息": 40,
    }

    def validate_id_card(self, value: str) -> bool:
        if not re.fullmatch(r"\d{17}[\dXx]", value):
            return False
        try:
            datetime.strptime(value[6:14], "%Y%m%d")
        except ValueError:
            return False
        total = sum(int(number) * weight for number, weight in zip(value[:17], ID_WEIGHTS))
        return ID_CHECK_CODES[total % 11] == value[-1].upper()

    def validate_bank_card(self, value: str) -> bool:
        digits = re.sub(r"[ -]", "", value)
        if not digits.isdigit() or not 13 <= len(digits) <= 19:
            return False
        total = 0
        for position, char in enumerate(reversed(digits)):
            number = int(char)
            if position % 2:
                number *= 2
                if number > 9:
                    number -= 9
            total += number
        return total % 10 == 0

    def validate_uscc(self, value: str) -> bool:
        value = value.upper()
        if len(value) != 18 or any(char not in USCC_CHARS for char in value):
            return False
        total = sum(USCC_CHARS.index(char) * weight for char, weight in zip(value[:17], USCC_WEIGHTS))
        expected = USCC_CHARS[(31 - total % 31) % 31]
        return value[-1] == expected

    @staticmethod
    def validate_ip(value: str) -> bool:
        parts = value.split(".")
        return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)

    def create_alias(self, entity_type: str, used_aliases: Iterable[str]) -> str:
        used = set(used_aliases)
        prefix = "公司" if entity_type == "企业名称" else "自然人"
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for index in range(1, 1000):
            suffix = labels[index - 1] if index <= len(labels) else str(index)
            candidate = f"{prefix}{suffix}"
            if candidate not in used:
                return candidate
        return f"{prefix}999"

    def _candidate(
        self,
        value: str,
        start: int,
        end: int,
        entity_type: str,
        replacement: str,
        action: str,
        confidence: float,
        rule_code: str,
    ) -> RedactionCandidate:
        return RedactionCandidate(
            entity_type=entity_type,
            start_offset=start,
            end_offset=end,
            replacement=replacement,
            action=action,
            confidence=confidence,
            rule_code=rule_code,
            original_fingerprint=fingerprint(value),
        )

    def detect(
        self,
        source_text: str,
        *,
        subject_names: Sequence[str] = (),
        aliases: Mapping[str, str] | None = None,
    ) -> list[RedactionCandidate]:
        alias_map = dict(aliases or {})
        candidates: list[RedactionCandidate] = []
        used_aliases = set(alias_map.values())

        def add_match(match: re.Match[str], entity_type: str, replacement: str, action: str, confidence: float, rule: str) -> None:
            value = match.group(0)
            candidates.append(self._candidate(value, match.start(), match.end(), entity_type, replacement, action, confidence, rule))

        for match in re.finditer(r"(?<![0-9Xx])\d{17}[\dXx](?![0-9])", source_text):
            if self.validate_id_card(match.group(0)):
                add_match(match, "身份证", "身份证件号码", "full_replace", 0.99, "cn_id_card")
        for match in re.finditer(r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{18}(?![0-9A-Z])", source_text, flags=re.IGNORECASE):
            if self.validate_uscc(match.group(0)):
                add_match(match, "统一社会信用代码", "统一社会信用代码", "full_replace", 0.99, "cn_uscc")
        for match in re.finditer(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", source_text):
            value = match.group(0)
            digits = re.sub(r"[ -]", "", value)
            if self.validate_bank_card(value):
                add_match(match, "银行卡", f"银行卡尾号{digits[-4:]}", "partial_mask", 0.98, "bank_luhn")
        for match in re.finditer(r"(?<!\d)1[3-9]\d{9}(?!\d)", source_text):
            add_match(match, "手机号", _partial_phone(match.group(0)), "partial_mask", 0.98, "cn_mobile")
        for match in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", source_text):
            add_match(match, "邮箱", _partial_email(match.group(0)), "partial_mask", 0.96, "email")
        for match in re.finditer(r"(?<!\d)(?:0\d{2,3}[- ]?)?\d{7,8}(?:[-转xX]\d{1,6})?(?!\d)", source_text):
            value = match.group(0)
            if not re.fullmatch(r"\d{11}", value):
                add_match(match, "固定电话", f"{value[:3]}****", "partial_mask", 0.88, "landline")
        for match in re.finditer(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", source_text):
            if self.validate_ip(match.group(0)):
                octets = match.group(0).split(".")
                add_match(match, "IP地址", f"{octets[0]}.{octets[1]}.x.x", "partial_mask", 0.95, "ipv4")

        # Conservative address assistance: reviewers can adjust or remove every
        # match, avoiding broad NLP inference across legal narrative text.
        address_pattern = r"(?:[\u4e00-\u9fff]{2,12}(?:省|自治区|市))?[\u4e00-\u9fff]{2,12}(?:市|区|县)[\u4e00-\u9fff0-9一二三四五六七八九十-]{0,32}(?:路|街|道|巷|号|栋|室)"
        for match in re.finditer(address_pattern, source_text):
            add_match(match, "地址", _partial_address(match.group(0)), "partial_mask", 0.70, "address_pattern")

        for name in sorted({name.strip() for name in subject_names if name and name.strip() and name.strip() not in {"待识别", "未知"}}, key=len, reverse=True):
            entity_type = "企业名称" if re.search(r"公司|企业|集团|商行|工厂|事务所|中心", name) else "自然人姓名"
            for match in re.finditer(re.escape(name), source_text):
                name_fingerprint = fingerprint(name)
                alias = alias_map.get(name_fingerprint)
                if not alias:
                    alias = self.create_alias(entity_type, used_aliases)
                    used_aliases.add(alias)
                    alias_map[name_fingerprint] = alias
                candidates.append(self._candidate(name, match.start(), match.end(), entity_type, alias, "consistent_alias", 0.90, "case_subject"))

        return self.resolve_overlaps(candidates)

    def resolve_overlaps(self, candidates: Sequence[RedactionCandidate]) -> list[RedactionCandidate]:
        selected: list[RedactionCandidate] = []
        for candidate in sorted(
            candidates,
            key=lambda item: (-self.priority.get(item.entity_type, 0), item.start_offset, -(item.end_offset - item.start_offset)),
        ):
            if candidate.start_offset >= candidate.end_offset:
                continue
            overlap = any(
                candidate.start_offset < current.end_offset and candidate.end_offset > current.start_offset
                for current in selected
            )
            if not overlap:
                selected.append(candidate)
        return sorted(selected, key=lambda item: (item.start_offset, item.end_offset))

    def validate(self, source_text: str, candidates: Sequence[RedactionCandidate]) -> None:
        previous_end = -1
        for item in sorted(candidates, key=lambda current: current.start_offset):
            if not 0 <= item.start_offset < item.end_offset <= len(source_text):
                raise ValueError("敏感项位置超出原文范围")
            if item.start_offset < previous_end:
                raise ValueError("敏感项存在重叠，请先调整位置")
            previous_end = item.end_offset

    def apply(self, source_text: str, candidates: Sequence[RedactionCandidate]) -> str:
        # ORM rows and candidates both have the fields below. Rebuild without
        # relying on an internal provider type.
        active = [
            item for item in candidates
            if getattr(item, "action", "full_replace") != "keep"
            and getattr(item, "review_status", "待确认") not in {"已驳回", "已移除", "已保留"}
        ]
        normalized = [
            RedactionCandidate(
                entity_type=item.entity_type,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                replacement=item.replacement,
                action=item.action,
                confidence=float(getattr(item, "confidence", 1.0)),
                rule_code=item.rule_code,
                original_fingerprint=item.original_fingerprint,
            )
            for item in active
        ]
        self.validate(source_text, normalized)
        result = source_text
        for item in reversed(normalized):
            result = f"{result[:item.start_offset]}{item.replacement}{result[item.end_offset:]}"
        return result

    def build_preview(self, source_text: str, candidates: Sequence[RedactionCandidate]) -> str:
        return self.apply(source_text, candidates)

    def manual_item(
        self,
        source_text: str,
        *,
        start_offset: int,
        end_offset: int,
        entity_type: str,
        replacement: str,
        action: str,
        confidence: float = 1.0,
        rule_code: str = "manual",
    ) -> RedactionCandidate:
        if not 0 <= start_offset < end_offset <= len(source_text):
            raise ValueError("人工标记的位置无效")
        original = source_text[start_offset:end_offset]
        if not replacement:
            if entity_type == "地址":
                replacement = _partial_address(original)
            elif entity_type == "企业名称":
                replacement = self.create_alias(entity_type, ())
                action = "consistent_alias"
            elif entity_type == "自然人姓名":
                replacement = self.create_alias(entity_type, ())
                action = "consistent_alias"
            else:
                replacement = f"{entity_type}已脱敏"
        return self._candidate(original, start_offset, end_offset, entity_type, replacement, action, confidence, rule_code)
