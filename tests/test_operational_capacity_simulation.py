from app.agent_tools.capacity import simulate


def test_capacity_shortfall_recommends_only_non_executable_guidance() -> None:
    context = {
        "ruleCode": "OPERATIONAL_CAPACITY_SHORTFALL",
        "observedAt": "2026-10-19T12:00:00+00:00",
        "branchId": "20000000-0000-4000-8000-000000000001",
        "capacityWindow": {
            "id": "20000000-0000-4000-8000-000000000002",
            "startsAt": "2026-10-19T11:00:00+00:00",
            "endsAt": "2026-10-19T16:00:00+00:00",
            "availableMinutes": 120,
            "remainingAvailableMinutes": 80,
        },
        "requiredMinutes": 240,
        "remainingRequiredMinutes": 200,
        "capacityGapMinutes": 120,
        "workload": [],
    }

    snapshot, options, recommended, outcome = simulate(context)

    assert outcome == "READY"
    assert recommended == "escalate-capacity-shortfall"
    assert snapshot["ruleCode"] == "OPERATIONAL_CAPACITY_SHORTFALL"
    assert [option["optionType"] for option in options] == [
        "ESCALATE_CAPACITY_SHORTFALL",
        "REPRIORITIZE_OPERATIONAL_TASKS",
    ]
    assert all(option["executable"] is False for option in options)
    assert all("actionPreview" not in option for option in options)


def test_small_capacity_gap_recommends_manual_reprioritization() -> None:
    context = {
        "observedAt": "2026-10-19T12:00:00+00:00",
        "branchId": "20000000-0000-4000-8000-000000000001",
        "capacityWindow": {
            "availableMinutes": 300,
            "remainingAvailableMinutes": 200,
        },
        "requiredMinutes": 330,
        "remainingRequiredMinutes": 230,
        "capacityGapMinutes": 30,
        "workload": [],
    }

    _, options, recommended, outcome = simulate(context)

    assert outcome == "READY"
    assert recommended == "reprioritize-operational-tasks"
    assert [option["optionType"] for option in options] == ["REPRIORITIZE_OPERATIONAL_TASKS"]
