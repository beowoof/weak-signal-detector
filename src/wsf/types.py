from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

NON_VOTING_DERIVED = frozenset({"fusion.domain_covar", "talk_vs_motion.residual"})


class Family(StrEnum):
    facility_tempo = "facility_tempo"
    coverage_asymmetry = "coverage_asymmetry"
    cheap_talk_vs_costly_motion = "cheap_talk_vs_costly_motion"
    cross_domain_covariance = "cross_domain_covariance"
    dyadic_counterpart = "dyadic_counterpart"
    official_residue = "official_residue"
    official_posture = "official_posture"
    attention_without_admission = "attention_without_admission"
    absence_as_absence = "absence_as_absence"


class IndicatorStatus(StrEnum):
    instantiated = "instantiated"
    uninstantiated = "uninstantiated"
    derived = "derived"


class CostClass(StrEnum):
    costly = "costly"
    soft = "soft"
    info = "info"


class CausalDomain(StrEnum):
    physical_activity = "physical_activity"
    mobility = "mobility"
    bureaucratic = "bureaucratic"
    information = "information"
    public_attention = "public_attention"
    market = "market"
    digital_infrastructure = "digital_infrastructure"
    spatial_restriction = "spatial_restriction"
    domestic_financial_conditions = "domestic_financial_conditions"
    declared_posture = "declared_posture"


class SubjectControl(StrEnum):
    no = "no"
    partly = "partly"
    yes = "yes"


class Polarity(StrEnum):
    high_unusual = "high_unusual"
    low_unusual = "low_unusual"
    either = "either"


class IndicatorSpec(BaseModel):
    id: str
    family: Family
    hypothesis: str
    status: IndicatorStatus
    cost_class: CostClass
    polarity: Polarity = Polarity.high_unusual
    in_basket: bool
    source_system: str | None = None
    connector: str | None = None
    series_id: str | None = None
    computed_from: list[str] = Field(default_factory=list)
    uninstantiated_reason: str | None = None
    expected_baseline_id: str | None = None
    causal_domain: CausalDomain | None = None
    collector: str | None = None
    subject_controls_signal: SubjectControl | None = None
    notes: str = ""

    @model_validator(mode="after")
    def status_consistent(self) -> IndicatorSpec:
        if self.status is IndicatorStatus.instantiated:
            if not (self.connector and self.series_id and self.source_system):
                raise ValueError(
                    f"{self.id}: instantiated requires connector, series_id, source_system"
                )
            if self.causal_domain is None or not self.collector:
                raise ValueError(
                    f"{self.id}: instantiated requires causal_domain and collector"
                )
            if self.subject_controls_signal is None:
                raise ValueError(f"{self.id}: instantiated requires subject_controls_signal")
            if self.family is Family.absence_as_absence and not self.expected_baseline_id:
                raise ValueError(f"{self.id}: absence requires expected_baseline_id")
        elif self.status is IndicatorStatus.derived:
            if self.connector is not None:
                raise ValueError(f"{self.id}: derived must not have a connector")
            if not self.series_id or not self.computed_from:
                raise ValueError(f"{self.id}: derived requires series_id and computed_from")
            if self.id in NON_VOTING_DERIVED and self.in_basket:
                raise ValueError(f"{self.id}: residual/covariance singletons cannot vote")
        else:
            if not self.uninstantiated_reason:
                raise ValueError(f"{self.id}: uninstantiated requires a reason")
            if self.connector is not None or self.in_basket:
                raise ValueError(f"{self.id}: uninstantiated cannot connect or vote")
        return self


class PeriodClass(StrEnum):
    quiet = "quiet"
    high_tension_non_mobilisation = "high_tension_non_mobilisation"
    mobilisation_reversed = "mobilisation_reversed"
    overt_action = "overt_action"


class Split(StrEnum):
    development = "development"
    held_out = "held_out"


class PeriodWindow(BaseModel):
    id: str
    focal_actor: str
    counterpart_actor: str | None = None
    period_class: PeriodClass
    split: Split
    start: date
    end: date
    lookback_start: date
    query_id: str
    notes: str = ""

    @model_validator(mode="after")
    def dates_consistent(self) -> PeriodWindow:
        if not self.lookback_start < self.start <= self.end:
            raise ValueError(f"{self.id}: require lookback_start < start <= end")
        if self.query_id != self.id:
            raise ValueError(f"{self.id}: query_id must equal period id")
        return self


class Observation(BaseModel):
    version_id: str
    series_id: str
    period_id: str
    event_time: datetime
    available_at: datetime
    retrieved_at: datetime
    value: float | None
    quality: Literal["ok", "missing", "source_down"]
    extra: str = "{}"


class FeatureRow(BaseModel):
    period_id: str
    series_id: str
    cutoff: date
    expected_event_date: date
    current_event_time: datetime | None
    age_days: int | None
    raw: float | None
    baseline_mu: float | None
    baseline_sigma: float | None
    n_baseline: int
    z: float | None
    missing: bool
    silence: bool
    flagged: bool


class Alert(BaseModel):
    period_id: str
    start: date
    end: date
    n_flagged: int
    n_costly_flagged: int
    contributing_families: list[str]
    contributing_source_systems: list[str]
    contributing_causal_domains: list[str] = Field(default_factory=list)
    contributing_series: list[str]
