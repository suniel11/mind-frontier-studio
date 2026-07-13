from __future__ import annotations

from dataclasses import dataclass

from app.visual_continuity import config as vc_config


@dataclass(frozen=True)
class CostGuardResult:
    planner_estimated_cost_usd: float
    estimated_image_cost_saved_usd: float
    estimated_net_cost_saved_usd: float
    estimated_render_time_saved_seconds: float
    estimated_net_time_saved_seconds: float
    should_disable_for_cost: bool
    should_disable_for_time: bool
    should_disable_grouping: bool


def estimate_planner_cost_usd(*, input_tokens: int | None, output_tokens: int | None) -> float:
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    return round(
        input_tokens * vc_config.text_price_per_1m_input_usd() / 1_000_000
        + output_tokens * vc_config.text_price_per_1m_output_usd() / 1_000_000,
        6,
    )


def estimate_image_cost_saved_usd(reused_images: int) -> float:
    return round(max(0, reused_images) * vc_config.image_price_usd(), 6)


def estimate_render_time_saved_seconds(reused_images: int) -> float:
    return round(max(0, reused_images) * vc_config.estimated_seconds_per_image(), 2)


def evaluate(
    *,
    planner_input_tokens: int | None,
    planner_output_tokens: int | None,
    reused_images: int,
    planner_execution_time: float = 0.0,
) -> CostGuardResult:
    """Deterministic economic safeguard (spec: "Never spend more money
    trying to save money"). Grouping is disabled for this project if
    *either* is true: the planner call itself cost at least as much in
    dollars as the images it let us skip, or -- just as importantly, since
    reducing render time was the feature's original goal -- the planner's
    own wall-clock time was at least as long as the render time it saved.
    A project can be dollar-positive and still time-negative (verified
    against real productions: one sampled case took 56s to plan and only
    unlocked ~31s of estimated image-generation savings), and shipping a
    production that is *slower* than before defeats the point even when it
    is technically cheaper.
    """

    planner_cost = estimate_planner_cost_usd(
        input_tokens=planner_input_tokens, output_tokens=planner_output_tokens
    )
    image_savings = estimate_image_cost_saved_usd(reused_images)
    net_cost = round(image_savings - planner_cost, 6)

    time_saved = estimate_render_time_saved_seconds(reused_images)
    net_time = round(time_saved - planner_execution_time, 2)

    should_disable_for_cost = planner_cost >= image_savings
    should_disable_for_time = planner_execution_time >= time_saved

    return CostGuardResult(
        planner_estimated_cost_usd=planner_cost,
        estimated_image_cost_saved_usd=image_savings,
        estimated_net_cost_saved_usd=net_cost,
        estimated_render_time_saved_seconds=time_saved,
        estimated_net_time_saved_seconds=net_time,
        should_disable_for_cost=should_disable_for_cost,
        should_disable_for_time=should_disable_for_time,
        should_disable_grouping=should_disable_for_cost or should_disable_for_time,
    )
