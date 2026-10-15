import pytest

from app.knowledge import service
from app.models import ActorContext, SearchResult


def source() -> SearchResult:
    return SearchResult(
        document_id="status-definitions",
        heading="Trạng thái đơn thuê",
        citation="Danh mục trạng thái nghiệp vụ — Trạng thái đơn thuê",
        domain="shared",
        status="verified_from_system",
        business_authority=False,
        content="Đơn đã xác nhận không đồng nghĩa khách đã thanh toán.",
        score=0.9,
    )


def approved_policy_source() -> SearchResult:
    return SearchResult(
        document_id="rental-policy-2025",
        heading="Trả trễ",
        citation="Chính sách thuê và hoàn cọc hiện hành — Trả trễ",
        domain="policies",
        status="approved",
        business_authority=True,
        content=(
            "Khách có 60 phút miễn trễ. Sau đó phí trả trễ bằng 20% "
            "tiền thuê cơ bản cho mỗi ngày trễ."
        ),
        score=0.95,
    )


def test_prompt_distinguishes_system_facts_from_business_policy() -> None:
    system, _user = service._prompt("Đơn đã xác nhận nghĩa là gì?", "Nguồn kiểm thử")

    assert "verified_from_system" in system
    assert "không từ chối chỉ vì business_authority=false" in system
    assert "approved và business_authority=true" in system


def test_generated_citation_section_is_removed() -> None:
    answer = "Đơn đã được xác nhận.\n\n**Tham khảo:**\n- Nguồn do model tự thêm"

    assert service._strip_generated_citations(answer) == "Đơn đã được xác nhận."


def test_generated_source_reference_section_is_removed() -> None:
    answer = "Đơn đã được xác nhận.\n\n**Nguồn tham khảo:**\n- Nguồn do model tự thêm"

    assert service._strip_generated_citations(answer) == "Đơn đã được xác nhận."


def test_generated_inline_citations_are_removed() -> None:
    answer = (
        "Phí trả trễ là 20% mỗi ngày"
        '【source citation="Chính sách — Trả trễ" status="approved"】.\n\n'
        'Nguồn: <source citation="Chính sách — Trả trễ"/>'
    )

    assert service._strip_generated_citations(answer) == "Phí trả trễ là 20% mỗi ngày."


def test_generated_verbose_reference_line_is_removed() -> None:
    answer = (
        "Phí trả trễ là 20% mỗi ngày.\n\n"
        "*Tham khảo: Chính sách thuê — Trả trễ*"
        '【source citation="Chính sách thuê — Trả trễ"】'
    )

    assert service._strip_generated_citations(answer) == "Phí trả trễ là 20% mỗi ngày."


def test_standalone_inline_source_tag_is_removed() -> None:
    answer = 'Phí trả trễ là 20% mỗi ngày <source citation="Chính sách — Trả trễ"/>'

    assert service._strip_generated_citations(answer) == "Phí trả trễ là 20% mỗi ngày"


def test_paired_source_wrapper_is_removed() -> None:
    answer = (
        "Phí trả trễ là 20% mỗi ngày. "
        '<source citation="Chính sách — Trả trễ">Tham khảo chính sách</source>'
    )

    assert service._strip_generated_citations(answer) == "Phí trả trễ là 20% mỗi ngày."


@pytest.mark.asyncio
async def test_answer_returns_citations_and_provisional_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search(*_args: object, **_kwargs: object) -> list[SearchResult]:
        return [source()]

    async def fake_completion(_system: str, _user: str) -> str:
        return "Đơn đã được cửa hàng xác nhận, nhưng chưa có nghĩa là đã thanh toán."

    monkeypatch.setattr(service, "search_knowledge", fake_search)
    monkeypatch.setattr(service, "_usable_sources", lambda results: results)
    monkeypatch.setattr(service, "generate_completion", fake_completion)

    actor = ActorContext(user_id="customer", audiences=("customer", "shared"))
    answer = await service.answer_knowledge(actor, "Đơn đã xác nhận nghĩa là gì?", 5)

    assert answer.outcome == "answered"
    assert answer.provisional is True
    assert [item.document_id for item in answer.sources] == ["status-definitions"]


@pytest.mark.asyncio
async def test_answer_uses_approved_policy_for_fee_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search(*_args: object, **_kwargs: object) -> list[SearchResult]:
        return [approved_policy_source()]

    async def fake_completion(_system: str, _user: str) -> str:
        return "Khách có 60 phút miễn trễ, sau đó phí là 20% tiền thuê cơ bản mỗi ngày trễ."

    monkeypatch.setattr(service, "search_knowledge", fake_search)
    monkeypatch.setattr(service, "_usable_sources", lambda results: results)
    monkeypatch.setattr(service, "generate_completion", fake_completion)

    actor = ActorContext(user_id="customer", audiences=("customer", "shared"))
    answer = await service.answer_knowledge(actor, "Phí trả trễ là bao nhiêu?", 5)

    assert answer.outcome == "answered"
    assert answer.provisional is False
    assert [item.document_id for item in answer.sources] == ["rental-policy-2025"]


@pytest.mark.asyncio
async def test_policy_question_excludes_non_authoritative_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_user = ""

    async def fake_search(*_args: object, **_kwargs: object) -> list[SearchResult]:
        return [source(), approved_policy_source()]

    async def fake_completion(_system: str, user: str) -> str:
        nonlocal captured_user
        captured_user = user
        return "Phí trả trễ là 20% tiền thuê cơ bản mỗi ngày trễ."

    monkeypatch.setattr(service, "search_knowledge", fake_search)
    monkeypatch.setattr(service, "_usable_sources", lambda results: results)
    monkeypatch.setattr(service, "generate_completion", fake_completion)

    actor = ActorContext(user_id="customer", audiences=("customer", "shared"))
    answer = await service.answer_knowledge(actor, "Phí trả trễ là bao nhiêu?", 5)

    assert "Đơn đã xác nhận" not in captured_user
    assert answer.provisional is False
    assert [item.document_id for item in answer.sources] == ["rental-policy-2025"]


@pytest.mark.asyncio
async def test_answer_abstains_when_model_reports_insufficient_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search(*_args: object, **_kwargs: object) -> list[SearchResult]:
        return [source()]

    async def fake_completion(_system: str, _user: str) -> str:
        return service.INSUFFICIENT_CONTEXT_SIGNAL

    monkeypatch.setattr(service, "search_knowledge", fake_search)
    monkeypatch.setattr(service, "_usable_sources", lambda results: results)
    monkeypatch.setattr(service, "generate_completion", fake_completion)

    actor = ActorContext(user_id="customer", audiences=("customer", "shared"))
    answer = await service.answer_knowledge(actor, "Giá Bitcoin hôm nay?", 5)

    assert answer.outcome == "insufficient_context"
    assert answer.sources == []
    assert answer.provisional is False


@pytest.mark.asyncio
async def test_answer_blocks_unapproved_fee_answer_before_calling_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search(*_args: object, **_kwargs: object) -> list[SearchResult]:
        return [source()]

    async def unexpected_completion(_system: str, _user: str) -> str:
        raise AssertionError("LLM must not be called for an unapproved fee question")

    monkeypatch.setattr(service, "search_knowledge", fake_search)
    monkeypatch.setattr(service, "_usable_sources", lambda results: results)
    monkeypatch.setattr(service, "generate_completion", unexpected_completion)

    actor = ActorContext(user_id="customer", audiences=("customer", "shared"))
    answer = await service.answer_knowledge(actor, "Tôi bị phạt bao nhiêu tiền?", 5)

    assert answer.outcome == "insufficient_context"
    assert answer.sources == []
    assert answer.provisional is False


@pytest.mark.parametrize(
    "query",
    [
        "Tiền cọc của tôi sẽ bị giữ lại bao nhiêu?",
        "Cọc bị trừ thế nào?",
        "Bao giờ cửa hàng có kết quả?",
        "Khi nào tôi nhận được đồ?",
        "Nhân viên được hoàn tiền không?",
        "Hủy đơn được không?",
        "Phụ thu trả trễ là gì?",
        "Giá trả trễ là bao nhiêu?",
        "Tôi bị trừ thế nào?",
        "Mất thêm bao nhiêu nếu trả muộn?",
        "Ước tính lúc nào xử lý xong?",
        "Thanh toán thành công nghĩa là gì, và phí trả trễ bao nhiêu?",
        "Đơn và thanh toán khác nhau thế nào, mức phí hủy là bao nhiêu?",
        "Hoàn tiền đang xử lý nghĩa là gì; tôi được hoàn bao nhiêu?",
    ],
)
def test_policy_sensitive_paraphrases_require_business_authority(query: str) -> None:
    assert service._requires_business_authority(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "Đơn nháp là gì?",
        "Thanh toán thành công nghĩa là gì?",
        "Đơn đã xác nhận có nghĩa là khách đã thanh toán chưa?",
        "Quy trình trả đồ gồm các bước nào?",
        "Vì sao bộ sẵn sàng nhưng chưa đặt được?",
    ],
)
def test_verified_system_explanations_do_not_require_business_authority(query: str) -> None:
    assert service._requires_business_authority(query) is False
