"""Deterministic business skills for the single operations agent.

Skills are playbooks, not autonomous agents.  They restrict the model to a
small tool set and define the checks required before a goal can be completed.
"""

from dataclasses import dataclass

from app.agent_tools.models import (
    AgentGoalConstraints,
    AgentGoalSpec,
    AgentGoalType,
    AgentPlanStep,
)


@dataclass(frozen=True)
class BusinessSkill:
    name: str
    goal_types: frozenset[AgentGoalType]
    allowed_tools: tuple[str, ...]
    workflow: tuple[tuple[str, str | None, str], ...]
    requires_confirmation: bool = False
    requires_approval: bool = False


SKILLS: tuple[BusinessSkill, ...] = (
    BusinessSkill(
        "policy_answer_with_citations",
        frozenset({AgentGoalType.KNOWLEDGE_ANSWER}),
        ("search_knowledge",),
        (("Search approved knowledge", "search_knowledge", "At least one valid citation"),),
    ),
    BusinessSkill(
        "rental_order_investigation",
        frozenset(
            {
                AgentGoalType.RENTAL_ORDER_LOOKUP,
                AgentGoalType.RENTAL_ORDER_SEARCH,
                AgentGoalType.PAYMENT_SUMMARY,
            }
        ),
        ("find_rental_orders", "get_rental_order", "get_payment_summary"),
        (
            ("Resolve the requested order", "find_rental_orders", "Requested order is identified"),
            (
                "Read authoritative order data",
                "get_rental_order",
                "Order scope matches the request",
            ),
            ("Summarize only observed facts", None, "Answer is grounded in evidence"),
        ),
    ),
    BusinessSkill(
        "availability_and_schedule",
        frozenset(
            {
                AgentGoalType.AVAILABILITY_CHECK,
                AgentGoalType.UNIT_SCHEDULE,
            }
        ),
        ("check_availability", "get_unit_schedule"),
        (
            (
                "Check availability for the exact period",
                "check_availability",
                "Candidate unit is available",
            ),
            ("Read unit schedule when requested", "get_unit_schedule", "Schedule scope matches"),
        ),
    ),
    BusinessSkill(
        "rental_reallocation",
        frozenset({AgentGoalType.RENTAL_REALLOCATION}),
        ("check_availability", "get_rental_order", "reallocate_rental_item"),
        (
            (
                "Read the order and current allocation",
                "get_rental_order",
                "Current allocation is known",
            ),
            (
                "Check availability for the exact period",
                "check_availability",
                "Candidate unit is available",
            ),
            (
                "Freeze the requested reallocation",
                "reallocate_rental_item",
                "Arguments match observed records",
            ),
            ("Read back the order", "get_rental_order", "New allocation is verified"),
        ),
        requires_confirmation=True,
    ),
    BusinessSkill(
        "rental_extension",
        frozenset({AgentGoalType.RENTAL_EXTENSION}),
        ("get_rental_order", "check_availability", "extend_rental_order"),
        (
            (
                "Read the current order and version",
                "get_rental_order",
                "Current due time and version are known",
            ),
            (
                "Check availability through the new due time",
                "check_availability",
                "No conflicting allocation is observed",
            ),
            ("Freeze the extension", "extend_rental_order", "Expected version is fresh"),
            ("Read back the order", "get_rental_order", "New due time is verified"),
        ),
        requires_confirmation=True,
    ),
    BusinessSkill(
        "rental_cancellation",
        frozenset({AgentGoalType.RENTAL_CANCELLATION}),
        ("get_rental_order", "cancel_rental_order"),
        (
            (
                "Read the current order and version",
                "get_rental_order",
                "Order is cancellable and version is fresh",
            ),
            (
                "Freeze the cancellation reason",
                "cancel_rental_order",
                "Requester sees the exact cancellation payload",
            ),
            ("Read back the order", "get_rental_order", "Cancelled state is verified"),
        ),
        requires_confirmation=True,
    ),
    BusinessSkill(
        "unit_block_management",
        frozenset({AgentGoalType.UNIT_BLOCK_CHANGE}),
        (
            "get_unit_block",
            "get_unit_schedule",
            "create_unit_block",
            "update_unit_block",
            "cancel_unit_block",
        ),
        (
            (
                "Read the unit schedule or existing block",
                "get_unit_schedule",
                "Current schedule is known",
            ),
            ("Freeze one block mutation", None, "Mutation arguments are complete"),
            ("Read back the block", "get_unit_block", "Block state is verified"),
        ),
        requires_confirmation=True,
    ),
    BusinessSkill(
        "stock_transfer_lookup",
        frozenset({AgentGoalType.STOCK_TRANSFER_LOOKUP}),
        ("get_stock_transfer",),
        (("Read the requested transfer", "get_stock_transfer", "Transfer ID and scope match"),),
    ),
    BusinessSkill(
        "cross_branch_transfer",
        frozenset({AgentGoalType.STOCK_TRANSFER_CREATE}),
        (
            "get_stock_transfer",
            "create_stock_transfer",
        ),
        (
            (
                "Read transfer context",
                "get_stock_transfer",
                "Transfer scope and version are known when applicable",
            ),
            ("Freeze the transfer action", None, "Source, destination and items are explicit"),
            ("Obtain requester confirmation", None, "Frozen payload is confirmed"),
            ("Obtain branch-scoped approval", None, "Approver permission is rechecked"),
            ("Read back the transfer", "get_stock_transfer", "Transfer state is verified"),
        ),
        requires_confirmation=True,
        requires_approval=True,
    ),
    BusinessSkill(
        "stock_transfer_decision_routing",
        frozenset({AgentGoalType.STOCK_TRANSFER_DECISION}),
        (),
        (
            (
                "Resume an existing approval through the approval endpoint",
                None,
                "Approver permission and branch scope are rechecked",
            ),
        ),
        requires_approval=True,
    ),
    BusinessSkill(
        "payment_checkout",
        frozenset({AgentGoalType.PAYMENT_CHECKOUT}),
        ("get_rental_order", "create_payment_checkout", "get_payment_by_idempotency_key"),
        (
            ("Read the rental order", "get_rental_order", "Order and branch scope are known"),
            (
                "Freeze checkout details",
                "create_payment_checkout",
                "Amount and purpose are explicit",
            ),
            ("Obtain confirmation and financial approval", None, "Both gates pass"),
            (
                "Read back by idempotency key",
                "get_payment_by_idempotency_key",
                "Checkout creation is verified",
            ),
        ),
        requires_confirmation=True,
        requires_approval=True,
    ),
    BusinessSkill(
        "refund_request",
        frozenset({AgentGoalType.REFUND_REQUEST}),
        ("get_payment", "request_refund", "get_refund_by_idempotency_key"),
        (
            ("Read the original payment", "get_payment", "Payment and branch scope are known"),
            ("Freeze refund request", "request_refund", "Amount and reason are explicit"),
            ("Obtain confirmation and financial approval", None, "Both gates pass"),
            (
                "Read back by idempotency key",
                "get_refund_by_idempotency_key",
                "Refund request is verified",
            ),
        ),
        requires_confirmation=True,
        requires_approval=True,
    ),
    BusinessSkill(
        "grounded_general_assistance",
        frozenset({AgentGoalType.GENERAL_ASSISTANCE}),
        ("search_knowledge",),
        (
            (
                "Search approved knowledge when relevant",
                "search_knowledge",
                "Any factual answer has a valid citation",
            ),
            ("Ask for clarification when scope is unclear", None, "No business fact is invented"),
        ),
    ),
)


def select_skill(goal_type: AgentGoalType) -> BusinessSkill | None:
    return next((skill for skill in SKILLS if goal_type in skill.goal_types), None)


def attach_skill(goal: AgentGoalSpec, max_steps: int = 6) -> AgentGoalSpec:
    """Attach an auditable skill plan and its hard tool boundary to a goal."""
    skill = select_skill(goal.goal_type)
    if skill is None:
        return goal
    plan = tuple(
        AgentPlanStep(order=index, action=action, tool_name=tool, verification=verification)
        for index, (action, tool, verification) in enumerate(skill.workflow, start=1)
    )
    return goal.model_copy(
        update={
            "skill_name": skill.name,
            "constraints": AgentGoalConstraints(
                allowed_tools=skill.allowed_tools,
                requires_confirmation=skill.requires_confirmation,
                requires_approval=skill.requires_approval,
                max_steps=max_steps,
            ),
            "plan": plan,
        }
    )


def skill_allows_tool(goal: AgentGoalSpec, tool_name: str) -> bool:
    return tool_name in goal.constraints.allowed_tools
