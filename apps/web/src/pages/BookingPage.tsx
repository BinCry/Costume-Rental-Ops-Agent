import { useEffect, useRef, useState } from 'react';
import type { Navigate } from '../App';
import {
  Button,
  EmptyState,
  Feedback,
  Field,
  Icon,
  SelectField,
  SkeletonGrid,
  TextAreaField,
} from '../components/ui';
import { money } from '../components/support';
import { useFixtureResource } from '../components/useFixtureResource';
import { branches, fixtureAdapter, fixtureCatalog, fixturePeriod } from '../fixtures/adapter';
import { studioAdapter } from '../fixtures/studio';
import type { BookingDraft, DemoScenario, QuoteSnapshot } from '../fixtures/types';

const steps = ['Trang phục', 'Lựa chọn', 'Nhận và trả', 'Báo giá', 'Người thuê', 'Xác nhận'];
const loadCatalog = (scenario: DemoScenario) => fixtureAdapter.listCatalog(scenario);
const baseDraft: BookingDraft = {
  costumeId: 'ao-dai-lina',
  variant: 'M / Hồng phấn',
  quantity: 1,
  branch: branches[0],
  pickup: fixturePeriod.pickup,
  returnAt: fixturePeriod.returnAt,
  name: '',
  phone: '',
  note: '',
};
const initialDraft = (costumeId?: string, context?: URLSearchParams): BookingDraft => {
  const selected = fixtureCatalog.find((entry) => entry.id === costumeId);
  const variants = selected?.sizes.map((size) => `${size} / ${selected.colors[0]}`) ?? [];
  const requestedVariant = context?.get('variant') ?? '';
  const requestedBranch = context?.get('branch');
  const requestedPickup = context?.get('pickup');
  const requestedReturn = context?.get('returnAt');
  return {
    ...baseDraft,
    costumeId: costumeId ?? baseDraft.costumeId,
    variant: variants.includes(requestedVariant)
      ? requestedVariant
      : (variants[0] ?? baseDraft.variant),
    branch:
      requestedBranch && branches.includes(requestedBranch) ? requestedBranch : baseDraft.branch,
    pickup: requestedPickup?.trim() ? requestedPickup : baseDraft.pickup,
    returnAt: requestedReturn?.trim() ? requestedReturn : baseDraft.returnAt,
  };
};

export function BookingPage({
  scenario,
  go,
  costumeId,
  initialContext,
  onCustomerCreated,
}: {
  scenario: DemoScenario;
  go: Navigate;
  costumeId?: string;
  initialContext: URLSearchParams;
  onCustomerCreated?: (code: string) => void;
}) {
  const [step, setStep] = useState(() => {
    const selected = fixtureCatalog.find((entry) => entry.id === costumeId);
    if (!selected) return 0;
    return selected.sizes.some(
      (size) => `${size} / ${selected.colors[0]}` === initialContext.get('variant'),
    )
      ? 2
      : 1;
  });
  const [draft, setDraft] = useState<BookingDraft>(() => initialDraft(costumeId, initialContext));
  const [quote, setQuote] = useState<QuoteSnapshot>();
  const [issue, setIssue] = useState('');
  const [busy, setBusy] = useState(false);
  const [submittedId, setSubmittedId] = useState('');
  const quoteRequestRef = useRef(0);
  const submittingRef = useRef(false);
  const panelRef = useRef<HTMLElement>(null);
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);
  const successHeadingRef = useRef<HTMLHeadingElement>(null);
  const issueRef = useRef<HTMLDivElement>(null);
  const previousStepRef = useRef(step);
  useEffect(() => {
    if (previousStepRef.current === step) return;
    previousStepRef.current = step;
    stepHeadingRef.current?.focus();
    stepHeadingRef.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [step]);
  useEffect(() => {
    if (!issue) return;
    const invalidField = panelRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]');
    (invalidField ?? issueRef.current)?.focus();
  }, [issue]);
  useEffect(() => {
    if (submittedId) successHeadingRef.current?.focus();
  }, [submittedId]);
  const { loading, data, error, retry } = useFixtureResource(scenario, loadCatalog);
  const item = fixtureCatalog.find((entry) => entry.id === draft.costumeId);
  const choices = item ? item.sizes.map((size) => `${size} / ${item.colors[0]}`) : [];
  const update = <K extends keyof BookingDraft>(key: K, value: BookingDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
    if (['costumeId', 'variant', 'quantity', 'branch', 'pickup', 'returnAt'].includes(key)) {
      quoteRequestRef.current += 1;
      setQuote(undefined);
      if (!submittingRef.current) setBusy(false);
    }
    setIssue('');
  };
  const canContinue = () => {
    if (step === 0 && !item) return 'Hãy chọn một mẫu trang phục.';
    if (
      step === 1 &&
      (!choices.includes(draft.variant) || draft.quantity < 1 || draft.quantity > 2)
    )
      return 'Chọn size/màu và số bộ hợp lệ trong fixture (1–2 bộ).';
    if (
      step === 2 &&
      (!draft.branch || !draft.pickup || !draft.returnAt || draft.returnAt <= draft.pickup)
    )
      return 'Chọn cùng chi nhánh và kỳ nhận/trả hợp lệ.';
    if (step === 3 && !quote) return 'Cần tải báo giá fixture còn hiệu lực để tiếp tục.';
    if (step === 4 && (!draft.name.trim() || !/^0[0-9 ]{8,12}$/.test(draft.phone.trim())))
      return 'Nhập tên và số điện thoại liên hệ hợp lệ.';
    return '';
  };
  const next = () => {
    const message = canContinue();
    if (message) {
      setIssue(message);
      return;
    }
    setIssue('');
    if (step === 2) {
      setStep(3);
      void loadQuote();
      return;
    }
    setStep((current) => Math.min(current + 1, 5));
  };
  const loadQuote = async () => {
    const requestId = ++quoteRequestRef.current;
    setBusy(true);
    setIssue('');
    try {
      const result = await fixtureAdapter.getQuote(draft, scenario);
      if (requestId === quoteRequestRef.current) setQuote(result);
    } catch (caught) {
      if (requestId === quoteRequestRef.current) {
        setQuote(undefined);
        setIssue(caught instanceof Error ? caught.message : 'Chưa tải được báo giá.');
      }
    } finally {
      if (requestId === quoteRequestRef.current) setBusy(false);
    }
  };
  const submit = async () => {
    if (submittingRef.current || submittedId) return;
    const message = canContinue();
    if (message || !quote) {
      setIssue(message || 'Cần báo giá hợp lệ.');
      return;
    }
    submittingRef.current = true;
    setBusy(true);
    setIssue('');
    try {
      const id = await fixtureAdapter.submitBooking(draft, quote, scenario);
      onCustomerCreated?.(studioAdapter.recordBooking(id, draft, quote));
      setSubmittedId(id);
    } catch (caught) {
      setIssue(caught instanceof Error ? caught.message : 'Chưa gửi được yêu cầu.');
    } finally {
      submittingRef.current = false;
      setBusy(false);
    }
  };
  if (submittedId)
    return (
      <div className="page booking-page">
        <div className="booking-success">
          <span className="success-symbol">
            <Icon name="check" size={32} />
          </span>
          <p className="eyebrow">YÊU CẦU ĐÃ GỬI · FIXTURE</p>
          <h1 tabIndex={-1} ref={successHeadingRef}>
            Yêu cầu demo đã được tạo
          </h1>
          <p className="success-code">
            Mã yêu cầu <strong>{submittedId}</strong>
          </p>
          <Feedback tone="warning" title="Yêu cầu chưa giữ trang phục cho đến khi studio xác nhận.">
            Yêu cầu đã lưu trong bộ nhớ fixture để bạn xem ở “Đơn của tôi”. Studio thật chưa nhận
            yêu cầu; cần API để lưu và xử lý trên máy chủ.
          </Feedback>
          <Button onClick={() => go('myRentalDetail', { order: submittedId })}>
            Theo dõi yêu cầu <Icon name="arrow" size={18} />
          </Button>
        </div>
      </div>
    );
  return (
    <div className="page booking-page">
      <div className="booking-heading">
        <div>
          <p className="eyebrow">UI-03 · ĐẶT THUÊ</p>
          <h1>Gửi yêu cầu thuê</h1>
          <p>Chọn bộ, thời gian và xem báo giá trước khi gửi.</p>
        </div>
        <div className="booking-step-count">Bước {step + 1} / 6</div>
      </div>
      <div className="step-progress" aria-label="Tiến độ đặt thuê">
        {steps.map((label, index) => (
          <button
            key={label}
            className={index === step ? 'active' : index < step ? 'done' : ''}
            onClick={() => {
              if (index < step) {
                setIssue('');
                setStep(index);
              }
            }}
            disabled={index > step}
            aria-current={index === step ? 'step' : undefined}
            aria-label={`Bước ${index + 1}: ${label}`}
          >
            <span>{index < step ? <Icon name="check" size={15} /> : index + 1}</span>
            <small>{label}</small>
          </button>
        ))}
      </div>
      <div className="booking-layout">
        <section className="booking-panel" ref={panelRef}>
          <div className="panel-intro">
            <span className="step-number">0{step + 1}</span>
            <div>
              <p className="eyebrow">BƯỚC {step + 1} / 6</p>
              <h2 ref={stepHeadingRef} tabIndex={-1} className="booking-step-heading">
                {steps[step]}
              </h2>
            </div>
          </div>
          {error && (
            <Feedback
              tone="danger"
              title="Không tải được mẫu trang phục"
              action={
                <Button variant="secondary" onClick={retry}>
                  Thử lại
                </Button>
              }
            >
              {error}
            </Feedback>
          )}
          {scenario === 'empty' && !loading && (
            <EmptyState
              title="Chưa có trang phục trong fixture này"
              action={
                <Button variant="secondary" onClick={() => go('catalog')}>
                  Về catalog
                </Button>
              }
            />
          )}
          {loading && <SkeletonGrid count={2} />}
          {!loading && !error && scenario !== 'empty' && (
            <>
              {step === 0 && (
                <div className="booking-costumes">
                  {data?.map((entry) => (
                    <button
                      key={entry.id}
                      className={`booking-costume ${draft.costumeId === entry.id ? 'selected' : ''}`}
                      onClick={() => {
                        update('costumeId', entry.id);
                        setDraft((current) => ({
                          ...current,
                          costumeId: entry.id,
                          variant: `${entry.sizes[0]} / ${entry.colors[0]}`,
                        }));
                      }}
                    >
                      <span
                        className={`booking-costume-image costume-${entry.imagePosition}`}
                        role="img"
                        aria-label={`Ảnh minh họa ${entry.name}`}
                      />
                      <span>
                        <strong>{entry.name}</strong>
                        <small>
                          {entry.category} · Từ {money(entry.priceFrom)}/ngày
                        </small>
                      </span>
                      {draft.costumeId === entry.id && <Icon name="check" size={20} />}
                    </button>
                  ))}
                </div>
              )}
              {step === 1 && (
                <div className="form-stack">
                  <SelectField
                    label="Biến thể · size / màu"
                    value={draft.variant}
                    onChange={(event) => update('variant', event.target.value)}
                  >
                    <option value="">Chọn biến thể</option>
                    {choices.map((choice) => (
                      <option key={choice}>{choice}</option>
                    ))}
                  </SelectField>
                  <SelectField
                    label="Số bộ"
                    value={draft.quantity}
                    onChange={(event) => update('quantity', Number(event.target.value))}
                  >
                    <option value={1}>1 bộ</option>
                    <option value={2}>2 bộ</option>
                  </SelectField>
                  <Feedback tone="info" title="Mỗi bộ vật lý được quản lý riêng">
                    Nếu thuê nhiều bộ, mỗi bộ sẽ là một dòng riêng sau khi studio gán mã. Chọn biến
                    thể ở đây chưa giữ bộ.
                  </Feedback>
                </div>
              )}
              {step === 2 && (
                <div className="form-stack">
                  <SelectField
                    label="Chi nhánh nhận và trả"
                    value={draft.branch}
                    onChange={(event) => update('branch', event.target.value)}
                  >
                    {branches.map((entry) => (
                      <option key={entry}>{entry}</option>
                    ))}
                  </SelectField>
                  <div className="two-fields">
                    <Field
                      label="Nhận đồ"
                      type="datetime-local"
                      value={draft.pickup}
                      onChange={(event) => update('pickup', event.target.value)}
                      error={issue && !draft.pickup ? 'Chọn thời điểm nhận đồ.' : undefined}
                    />
                    <Field
                      label="Trả đồ"
                      type="datetime-local"
                      value={draft.returnAt}
                      onChange={(event) => update('returnAt', event.target.value)}
                      error={
                        issue && (!draft.returnAt || draft.returnAt <= draft.pickup)
                          ? 'Thời điểm trả phải sau thời điểm nhận.'
                          : undefined
                      }
                    />
                  </div>
                  <p className="inline-note">
                    <Icon name="pin" size={17} /> Nhận và trả cùng chi nhánh. Cách tính ngày sẽ theo
                    policy của báo giá, không tính trên trình duyệt.
                  </p>
                </div>
              )}
              {step === 3 && (
                <div className="form-stack">
                  <Feedback tone="info" title="Báo giá do fixture adapter cung cấp">
                    Bản demo chỉ có snapshot cho kỳ thuê mẫu. Khi nối backend, API báo giá sẽ cung
                    cấp số ngày, tiền và thời hạn.
                  </Feedback>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      void loadQuote();
                    }}
                    loading={busy}
                  >
                    <Icon name="refresh" size={18} />{' '}
                    {quote ? 'Tải lại báo giá' : 'Tải báo giá minh họa'}
                  </Button>
                  {quote && (
                    <div className="quote-card">
                      <div>
                        <span>Mã báo giá</span>
                        <strong>{quote.id}</strong>
                      </div>
                      <div>
                        <span>Thời gian tính thuê</span>
                        <strong>{quote.daysLabel}</strong>
                      </div>
                      <div>
                        <span>Giá/ngày × số bộ</span>
                        <strong>
                          {money(quote.pricePerDay)} × {quote.quantity}
                        </strong>
                      </div>
                      <div>
                        <span>Tiền thuê</span>
                        <strong>{money(quote.rental)}</strong>
                      </div>
                      <div>
                        <span>Tiền cọc</span>
                        <strong>{money(quote.deposit)}</strong>
                      </div>
                      <div>
                        <span>Giảm giá</span>
                        <strong>{money(quote.discount)}</strong>
                      </div>
                      <div className="quote-total">
                        <span>Dự kiến thu khi nhận</span>
                        <strong>{money(quote.amountDueAtPickup)}</strong>
                      </div>
                      <small>
                        Hiệu lực đến: {quote.expiresAt} · {quote.policy}
                      </small>
                    </div>
                  )}
                </div>
              )}
              {step === 4 && (
                <div className="form-stack">
                  <div className="google-placeholder">
                    <button
                      className="button button-secondary"
                      type="button"
                      disabled
                      aria-label="Đăng nhập Google chưa kết nối trong prototype"
                    >
                      G&nbsp; Đăng nhập bằng Google
                    </button>
                    <span>
                      Đăng nhập Google sẽ được kết nối khi có dịch vụ xác thực. Bạn vẫn có thể nhập
                      liên hệ để xem luồng demo.
                    </span>
                  </div>
                  <Field
                    label="Họ và tên người thuê"
                    placeholder="Ví dụ: Nguyễn An"
                    autoComplete="name"
                    value={draft.name}
                    onChange={(event) => update('name', event.target.value)}
                    error={issue && !draft.name.trim() ? 'Nhập tên người thuê.' : undefined}
                  />
                  <Field
                    label="Số điện thoại"
                    placeholder="09xx xxx xxx"
                    type="tel"
                    autoComplete="tel"
                    value={draft.phone}
                    onChange={(event) => update('phone', event.target.value)}
                    error={
                      issue && !/^0[0-9 ]{8,12}$/.test(draft.phone.trim())
                        ? 'Nhập số điện thoại hợp lệ.'
                        : undefined
                    }
                  />
                  <TextAreaField
                    label="Ghi chú cho studio (không bắt buộc)"
                    rows={4}
                    placeholder="Thông tin cần lưu ý khi nhận đồ"
                    value={draft.note}
                    onChange={(event) => update('note', event.target.value)}
                  />
                </div>
              )}
              {step === 5 && (
                <div className="confirm-summary">
                  <div>
                    <span>Trang phục</span>
                    <strong>
                      {item?.name} · {draft.variant} · {draft.quantity} bộ
                    </strong>
                  </div>
                  <div>
                    <span>Chi nhánh</span>
                    <strong>{draft.branch}</strong>
                  </div>
                  <div>
                    <span>Nhận / trả</span>
                    <strong>
                      {draft.pickup.replace('T', ' ')} → {draft.returnAt.replace('T', ' ')}
                    </strong>
                  </div>
                  <div>
                    <span>Người thuê</span>
                    <strong>
                      {draft.name} · {draft.phone}
                    </strong>
                  </div>
                  <div>
                    <span>Tiền thuê / cọc</span>
                    <strong>
                      {money(quote?.rental ?? 0)} / {money(quote?.deposit ?? 0)}
                    </strong>
                  </div>
                  <p className="inline-note">
                    Điều kiện hủy và chính sách áp dụng cần được xác nhận từ backend trước khi triển
                    khai thật. Bản demo không tự đặt ra phí hủy.
                  </p>
                  <Feedback
                    tone="warning"
                    title="Yêu cầu chưa giữ trang phục cho đến khi studio xác nhận."
                  >
                    Bạn chỉ trả tiền thuê và cọc khi nhận đồ tại chi nhánh.
                  </Feedback>
                </div>
              )}
            </>
          )}
          {issue && (
            <div ref={issueRef} tabIndex={-1}>
              <Feedback tone="danger" title="Chưa thể tiếp tục">
                {issue}
              </Feedback>
            </div>
          )}
          <div className="step-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setIssue('');
                if (step === 0) go('catalog');
                else setStep(step - 1);
              }}
            >
              {step === 0 ? 'Về catalog' : 'Quay lại'}
            </Button>
            {step < 5 ? (
              <Button onClick={next} disabled={loading || !!error || scenario === 'empty'}>
                Đi tiếp <Icon name="arrow" size={18} />
              </Button>
            ) : (
              <Button
                onClick={() => {
                  void submit();
                }}
                loading={busy}
                disabled={!quote}
              >
                Gửi yêu cầu thuê <Icon name="arrow" size={18} />
              </Button>
            )}
          </div>
        </section>
        <aside className="booking-sidebar">
          <div className="sidebar-note">
            <span className="eyebrow">TÓM TẮT YÊU CẦU</span>
            <h3>{item?.name ?? 'Chưa chọn mẫu'}</h3>
            <p>
              {draft.variant || 'Chưa chọn biến thể'} · {draft.quantity} bộ
            </p>
            <div className="sidebar-divider" />
            <p>
              <Icon name="pin" size={16} /> {draft.branch}
            </p>
            <p>
              <Icon name="calendar" size={16} />{' '}
              {draft.pickup ? draft.pickup.replace('T', ' ') : 'Chưa chọn ngày nhận'}
            </p>
            {quote ? (
              <>
                <div className="sidebar-divider" />
                <div className="sidebar-money">
                  <span>Tiền thuê</span>
                  <strong>{money(quote.rental)}</strong>
                </div>
                <div className="sidebar-money">
                  <span>Tiền cọc</span>
                  <strong>{money(quote.deposit)}</strong>
                </div>
                <small>Thu khi nhận đồ · Theo báo giá fixture</small>
              </>
            ) : (
              <small>Chưa có báo giá cho lựa chọn hiện tại.</small>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
