"""数据模型：CompetitorUpdate dataclass"""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CompetitorUpdate:
    title: str
    source_url: str
    id: Optional[int] = None
    publish_date: Optional[str] = None
    collected_at: Optional[str] = None
    competitor: Optional[str] = None
    category: Optional[str] = "待评估"
    summary: Optional[str] = None
    source_platform: Optional[str] = None
    source_mode: Optional[str] = "manual_excel"
    business_value: Optional[str] = None
    querit_status: Optional[str] = "待评估"
    gap_analysis: Optional[str] = None
    suggested_action: Optional[str] = None
    priority: Optional[str] = "中"
    review_status: Optional[str] = "待审核"
    follow_up_status: Optional[str] = "待处理"
    week_id: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "CompetitorUpdate":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> dict:
        return asdict(self)
