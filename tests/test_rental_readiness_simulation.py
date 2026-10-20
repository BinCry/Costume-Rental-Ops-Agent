from typing import Any

from app.agent_tools.overdue import simulate as simulate_overdue
from app.agent_tools.readiness import simulate


def _context(units: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "observedAt": "2026-10-17T10:00:00+00:00",
        "primaryOrder": {
            "id": "00000000-0000-0000-0000-000000000010",
            "plannedStartAt": "2026-10-17T12:00:00+00:00",
            "plannedDueAt": "2026-10-18T12:00:00+00:00",
            "version": 7,
            "item": {"id": "00000000-0000-0000-0000-000000000011"},
        },
        "affectedOrder": {"id": "00000000-0000-0000-0000-000000000012"},
        "currentUnit": {"id": "00000000-0000-0000-0000-000000000013"},
        "earliestReadyAt": "2026-10-17T13:00:00+00:00",
        "replacementUnits": units,
    }


def test_simulation_sorts_units_deterministically_and_never_freezes_an_action() -> None:
    snapshot, options, recommended, outcome = simulate(
        _context(
            [
                {"id": "00000000-0000-0000-0000-000000000022", "unitCode": "B-02"},
                {"id": "00000000-0000-0000-0000-000000000021", "unitCode": "A-01"},
            ]
        )
    )

    assert outcome == "READY"
    assert recommended == "reallocate:00000000-0000-0000-0000-000000000021"
    assert [option["targetUnit"]["unitCode"] for option in options] == ["A-01", "B-02"]
    preview = options[0]["actionPreview"]
    assert preview["toolName"] == "reallocate_rental_item"
    assert "payloadHash" not in preview
    assert snapshot["before"]["feasible"] is False


def test_simulation_returns_no_feasible_option_without_inventory() -> None:
    _, options, recommended, outcome = simulate(_context([]))

    assert options == []
    assert recommended is None
    assert outcome == "NO_FEASIBLE_OPTION"


def test_simulation_supports_allocated_unit_not_ready_without_an_affected_order() -> None:
    context = _context([{"id": "00000000-0000-0000-0000-000000000021", "unitCode": "A-01"}])
    context.update(
        {
            "ruleCode": "ALLOCATED_UNIT_NOT_READY",
            "affectedOrder": None,
            "reasonCodes": ["STATUS_NOT_READY"],
        }
    )

    snapshot, _, recommended, outcome = simulate(context)

    assert outcome == "READY"
    assert recommended == "reallocate:00000000-0000-0000-0000-000000000021"
    assert snapshot["ruleCode"] == "ALLOCATED_UNIT_NOT_READY"
    assert snapshot["affectedOrder"] is None
    assert snapshot["before"]["reasonCodes"] == ["STATUS_NOT_READY"]


def test_schedule_conflict_proposes_reallocation_only_for_a_confirmed_later_order() -> None:
    context = _context([{"id": "00000000-0000-0000-0000-000000000021", "unitCode": "A-01"}])
    context.update(
        {
            "ruleCode": "UNIT_SCHEDULE_CONFLICT",
            "primaryOrder": {
                **context["primaryOrder"],
                "item": {
                    "id": "00000000-0000-0000-0000-000000000011",
                    "allocationStatus": "CONFIRMED",
                },
            },
            "reasonCodes": ["UNIT_SCHEDULE_OVERLAP"],
        }
    )

    snapshot, options, recommended, outcome = simulate(context)

    assert outcome == "READY"
    assert recommended == "reallocate:00000000-0000-0000-0000-000000000021"
    assert options[0]["optionType"] == "REALLOCATE_SAME_BRANCH"
    assert snapshot["before"]["ruleCode"] == "UNIT_SCHEDULE_CONFLICT"


def test_schedule_conflict_hands_off_when_later_order_is_already_active() -> None:
    context = _context([{"id": "00000000-0000-0000-0000-000000000021", "unitCode": "A-01"}])
    context.update(
        {
            "ruleCode": "UNIT_SCHEDULE_CONFLICT",
            "primaryOrder": {
                **context["primaryOrder"],
                "item": {
                    "id": "00000000-0000-0000-0000-000000000011",
                    "allocationStatus": "ACTIVE",
                },
            },
        }
    )

    _, options, recommended, outcome = simulate(context)

    assert outcome == "NO_FEASIBLE_OPTION"
    assert options == []
    assert recommended is None


def test_preparation_delay_recommends_manual_non_executable_work() -> None:
    context = {
        "ruleCode": "ORDER_PREPARATION_DELAYED",
        "observedAt": "2026-10-17T10:00:00+00:00",
        "primaryOrder": {
            "id": "00000000-0000-0000-0000-000000000010",
            "status": "CONFIRMED",
            "plannedStartAt": "2026-10-17T11:00:00+00:00",
            "plannedDueAt": "2026-10-18T11:00:00+00:00",
            "version": 7,
            "items": [],
        },
        "affectedOrder": None,
        "currentUnit": None,
        "allocatedUnits": [
            {
                "id": "00000000-0000-0000-0000-000000000013",
                "unitCode": "A-01",
                "operationalStatus": "READY",
            }
        ],
    }

    snapshot, options, recommended, outcome = simulate(context)

    assert outcome == "READY"
    assert recommended == "start-preparation"
    assert snapshot["ruleCode"] == "ORDER_PREPARATION_DELAYED"
    assert options == [
        {
            "optionId": "start-preparation",
            "optionType": "START_PREPARATION",
            "feasible": True,
            "executable": False,
            "rank": 1,
            "reasonCodes": ["UNITS_READY", "MANUAL_PREPARATION_REQUIRED"],
        }
    ]
    assert "actionPreview" not in options[0]


def test_overdue_return_escalates_without_creating_an_executable_action() -> None:
    context = {
        "ruleCode": "RENTAL_RETURN_OVERDUE",
        "observedAt": "2026-10-19T12:00:00+00:00",
        "primaryOrder": {
            "id": "00000000-0000-0000-0000-000000000010",
            "status": "ACTIVE",
            "plannedStartAt": "2026-10-16T09:00:00+00:00",
            "plannedDueAt": "2026-10-18T09:00:00+00:00",
            "version": 4,
        },
        "lateGraceMinutes": 60,
        "graceDeadline": "2026-10-18T10:00:00+00:00",
        "overdueMinutes": 1560,
        "activeUnits": [
            {
                "itemId": "00000000-0000-0000-0000-000000000011",
                "unitId": "00000000-0000-0000-0000-000000000012",
            }
        ],
        "downstreamReadinessRisk": False,
        "escalationRequired": True,
    }

    snapshot, options, recommended, outcome = simulate_overdue(context)

    assert outcome == "READY"
    assert recommended == "escalate-overdue-return"
    assert snapshot["ruleCode"] == "RENTAL_RETURN_OVERDUE"
    assert [option["optionType"] for option in options] == [
        "ESCALATE_OVERDUE_RETURN",
        "CONTACT_CUSTOMER_FOR_RETURN",
    ]
    assert all(option["executable"] is False for option in options)
    assert all("actionPreview" not in option for option in options)
