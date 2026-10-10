import { useState } from 'react';
import type { Navigate } from '../App';
import {
  Button,
  EmptyState,
  Feedback,
  Field,
  Icon,
  MoneyBreakdown,
  SelectField,
  StatusLabel,
  TextAreaField,
} from '../components/ui';
import { money, orderStatus } from '../components/support';
import { useFixtureResource } from '../components/useFixtureResource';
import { branches, fixtureAdapter, returnSnapshots } from '../fixtures/adapter';
import type { DemoScenario, Order } from '../fixtures/types';

const loadOrders = (scenario: DemoScenario) => fixtureAdapter.listOrders(scenario);

export function OrderDetailShell({
  scenario,
  mode,
  go,
  initialOrderId,
  initialBranch,
}: {
  scenario: DemoScenario;
  mode: 'handover' | 'return';
  go: Navigate;
  initialOrderId: string;
  initialBranch: string;
}) {
  const [branch, setBranch] = useState(initialBranch);
  const [orderId, setOrderId] = useState(initialOrderId);
  const [barcode, setBarcode] = useState('');
  const [matchedCode, setMatchedCode] = useState('');
  const [matchedCodes, setMatchedCodes] = useState<string[]>([]);
  const [scanIssue, setScanIssue] = useState('');
  const [scanBusy, setScanBusy] = useState(false);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [returnConditions, setReturnConditions] = useState<
    Record<string, 'PASSED' | 'PENDING_ASSESSMENT'>
  >({});
  const [method, setMethod] = useState<'CASH' | 'BANK_TRANSFER'>('CASH');
  const [rentPreview, setRentPreview] = useState(false);
  const [depositPreview, setDepositPreview] = useState(false);
  const [note, setNote] = useState('');
  const [result, setResult] = useState<{ text: string; signature: string } | null>(null);
  const { loading, data, error, retry } = useFixtureResource(scenario, loadOrders);
  const eligible = (data ?? []).filter(
    (entry) =>
      entry.branch === branch &&
      (mode === 'handover'
        ? entry.status === 'READY_FOR_PICKUP'
        : ['ACTIVE', 'RETURN_INSPECTION'].includes(entry.status)),
  );
  const order: Order | undefined = eligible.find((entry) => entry.id === orderId);
  const rental = order?.money.find((line) => line.label === 'Tiền thuê');
  const deposit = order?.money.find((line) => line.label === 'Tiền cọc');
  const settlement = order ? returnSnapshots[order.id] : undefined;
  const scannedItems =
    order?.items.filter((item) => !!item.unitCode && matchedCodes.includes(item.unitCode)) ?? [];
  const allReturnItemsScanned = !!order && scannedItems.length === order.items.length;
  const requiresChecks = order
    ? (mode === 'return' ? scannedItems : order.items).flatMap((item) =>
        mode === 'return'
          ? [`${item.id}-accessories`]
          : [`${item.id}-condition`, `${item.id}-accessories`],
      )
    : [];
  const allChecked =
    requiresChecks.length > 0 &&
    requiresChecks.every((key) => checks[key]) &&
    (mode === 'handover' || scannedItems.every((item) => !!returnConditions[item.id]));
  const needsAssessment =
    mode === 'return' &&
    scannedItems.some((item) => returnConditions[item.id] === 'PENDING_ASSESSMENT');
  const needsAssessmentNote = needsAssessment && !note.trim();
  const snapshotConditionMismatch =
    mode === 'return' &&
    !!settlement &&
    allReturnItemsScanned &&
    allChecked &&
    scannedItems.every((item) => returnConditions[item.id] === 'PASSED') &&
    (settlement.damageFee > 0 || settlement.missingFee > 0);
  const onOrderChange = (id: string) => {
    setOrderId(id);
    setBarcode('');
    setMatchedCode('');
    setMatchedCodes([]);
    setChecks({});
    setReturnConditions({});
    setRentPreview(false);
    setDepositPreview(false);
    setNote('');
    setScanIssue('');
    setResult(null);
    if (id)
      window.history.replaceState(
        null,
        '',
        `/van-hanh/don-thue/${encodeURIComponent(id)}/${mode === 'handover' ? 'giao' : 'tra'}`,
      );
  };
  const lookup = async () => {
    setScanBusy(true);
    setScanIssue('');
    setMatchedCode('');
    setResult(null);
    try {
      const hit = await fixtureAdapter.lookupBarcode(barcode, branch, scenario);
      if (hit.order.id !== order?.id) {
        setScanIssue(
          `Mã ${barcode.toUpperCase()} thuộc đơn ${hit.order.id}, không khớp đơn ${order?.id}. Chưa ghi nhận giao/trả.`,
        );
      } else {
        const code = hit.order.items[hit.itemIndex].unitCode ?? '';
        setMatchedCode(code);
        setMatchedCodes((current) => (current.includes(code) ? current : [...current, code]));
      }
    } catch (caught) {
      setScanIssue(caught instanceof Error ? caught.message : 'Chưa tra cứu được mã bộ.');
    } finally {
      setScanBusy(false);
    }
  };
  const restricted =
    ['permission', 'version', 'cancelled', 'conflict', 'unitBlocked'].includes(scenario) ||
    (mode === 'return' && scenario === 'refundFailed' && order?.id === 'RT-1033');
  const effectiveMethod = scenario === 'bankPending' ? 'BANK_TRANSFER' : method;
  const allScanned =
    !!order && order.items.every((item) => !!item.unitCode && matchedCodes.includes(item.unitCode));
  const scannedEnough = mode === 'handover' ? allScanned : scannedItems.length > 0;
  const previewSignature = JSON.stringify([
    scenario,
    mode,
    branch,
    order?.id,
    order?.version,
    matchedCodes,
    checks,
    returnConditions,
    effectiveMethod,
    rentPreview,
    depositPreview,
    note,
  ]);
  const previewHandover = () => {
    if (
      !order ||
      !allScanned ||
      !allChecked ||
      !rentPreview ||
      !depositPreview ||
      effectiveMethod !== 'CASH' ||
      restricted
    )
      return;
    setResult({
      text: 'Checklist và tiền mặt đã đủ trong bản xem trước. Chỉ backend mới có thể xác nhận giao, thu tiền và chuyển đơn sang Đang thuê. Chưa có thay đổi nào được lưu.',
      signature: previewSignature,
    });
  };
  const previewReturn = () => {
    if (!order || !scannedEnough || !allChecked || needsAssessmentNote || restricted) return;
    setResult({
      text: needsAssessment
        ? `Đã xem trước nhận ${scannedItems.length}/${order.items.length} bộ có vấn đề cần đánh giá. Ghi chú được giữ trong phiên demo; cọc vẫn đang giữ, chưa tính phí hoặc hoàn tiền. Backend cần tạo biên bản PENDING_ASSESSMENT và phân công xử lý.`
        : order.status === 'ACTIVE'
          ? scannedItems.length < order.items.length
            ? `Đã xem trước nhận ${scannedItems.length}/${order.items.length} bộ. Bộ chưa quét vẫn ở khách; chưa quyết toán hoặc hoàn cọc. Backend cần xác nhận trạng thái từng dòng.`
            : 'Đã xem trước kết quả kiểm tra. Backend cần ghi nhận trả để chuyển đơn sang Đang kiểm tra đồ trả; chưa hoàn cọc.'
          : 'Đã xem trước quyết toán. Backend cần xác nhận cấn trừ, hoàn cọc và điều kiện hoàn tất; bản demo chưa ghi giao dịch.',
      signature: previewSignature,
    });
  };
  return (
    <div className="page staff-page task-page">
      <div className="staff-page-heading">
        <div>
          <p className="eyebrow">
            {mode === 'handover' ? 'UI-09 · GIAO TRANG PHỤC' : 'UI-11 · NHẬN TRẢ TRANG PHỤC'}
          </p>
          <h1>{mode === 'handover' ? 'Giao trang phục' : 'Nhận trả trang phục'}</h1>
          <p>
            {mode === 'handover'
              ? 'Đối chiếu từng bộ và từng khoản thu trước khi giao.'
              : 'Kiểm từng bộ, đối chiếu phí và quyết toán cọc.'}
          </p>
        </div>
        <Button variant="secondary" onClick={() => go('orders', { order: order?.id ?? orderId })}>
          <Icon name="arrow" size={17} /> Về đơn thuê
        </Button>
      </div>
      <div className="task-toolbar">
        <SelectField
          label="Chi nhánh thao tác"
          value={branch}
          onChange={(event) => {
            setBranch(event.target.value);
            onOrderChange('');
          }}
        >
          {branches.map((entry) => (
            <option key={entry}>{entry}</option>
          ))}
        </SelectField>
        <SelectField
          label="Đơn đang xử lý"
          value={order?.id ?? ''}
          onChange={(event) => onOrderChange(event.target.value)}
        >
          <option value="">{eligible.length === 0 ? 'Không có đơn' : 'Chọn đơn'}</option>
          {eligible.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {entry.id} · {entry.customer}
            </option>
          ))}
        </SelectField>
      </div>
      {order && (
        <nav className="task-jump-nav" aria-label="Các bước xử lý đơn">
          <a href="#task-scan">
            1. Quét mã · {matchedCodes.length}/{order.items.length}
          </a>
          <a href="#task-check">2. Kiểm tình trạng</a>
          <a href="#task-money">3. {mode === 'handover' ? 'Thu tiền' : 'Quyết toán'}</a>
        </nav>
      )}
      {scenario === 'permission' && (
        <Feedback tone="danger" title="Bạn không còn quyền xử lý đơn tại chi nhánh này">
          Không gửi thao tác cũ. Chuyển chi nhánh có quyền hoặc về tổng quan.
        </Feedback>
      )}
      {scenario === 'cancelled' && (
        <Feedback tone="danger" title="Đơn đã hủy trong lúc bạn thao tác">
          Mở lịch sử đơn và về hàng đợi; không giao hoặc nhận trả theo dữ liệu cũ.
        </Feedback>
      )}
      {scenario === 'version' && (
        <Feedback tone="warning" title="Đơn đã thay đổi từ lúc bạn mở">
          Kiểm tra phiên bản và trạng thái mới trước khi tiếp tục. Checklist chưa gửi vẫn được giữ.
        </Feedback>
      )}
      {scenario === 'conflict' && (
        <Feedback tone="warning" title="Bộ vừa thay đổi khả dụng">
          Mã bộ cần được kiểm tra lại trên đơn; không tự thay bộ và không ghi giao/trả.
        </Feedback>
      )}
      {scenario === 'unitBlocked' && (
        <Feedback tone="warning" title="Bộ đang vệ sinh hoặc sửa chữa">
          Bộ chưa sẵn sàng cho giao/nhận tiếp theo. Báo quản lý hoặc chọn bộ/kỳ khác trên đơn.
        </Feedback>
      )}
      {error && (
        <Feedback
          tone="danger"
          title="Không tải được đơn"
          action={
            <Button variant="secondary" onClick={retry}>
              Thử lại
            </Button>
          }
        >
          {error}
        </Feedback>
      )}
      {loading && (
        <div className="task-skeleton">
          <div className="shimmer" />
          <div className="shimmer" />
        </div>
      )}
      {!loading && !error && !order && (
        <EmptyState
          title={
            orderId
              ? `Không tìm thấy đơn ${orderId} phù hợp tại ${branch}`
              : mode === 'handover'
                ? 'Chưa có đơn sẵn sàng giao tại chi nhánh này'
                : 'Chưa có đơn cần nhận trả tại chi nhánh này'
          }
          action={
            <Button variant="secondary" onClick={() => go('orders')}>
              Mở danh sách đơn
            </Button>
          }
        />
      )}
      {!loading && !error && order && (
        <div className="task-layout">
          <div className="task-main">
            <section className="task-order-card">
              <div className="task-order-top">
                <div>
                  <p className="eyebrow">ĐƠN ĐANG MỞ · {order.id}</p>
                  <h2>{order.customer}</h2>
                  <p>
                    {order.phone} · {order.branch}
                  </p>
                </div>
                <StatusLabel
                  text={orderStatus[order.status].text}
                  tone={orderStatus[order.status].tone}
                />
              </div>
              <div className="task-order-meta">
                <span>
                  <Icon name="calendar" size={17} /> Nhận: {order.pickup}
                </span>
                <span>
                  <Icon name="clock" size={17} /> Hẹn trả: {order.returnAt}
                </span>
              </div>
            </section>
            <section className="task-card" id="task-scan">
              <div className="task-card-heading">
                <span className="round-step">01</span>
                <div>
                  <p className="eyebrow">TRA CỨU BỘ VẬT LÝ</p>
                  <h2>Quét hoặc nhập barcode</h2>
                </div>
              </div>
              <p className="section-help">
                Quét chỉ tra cứu; không tự ghi nhận giao hoặc trả. Mã phải khớp đơn và chi nhánh
                đang mở.
              </p>
              <div className="scan-form">
                <Field
                  label="Barcode bộ trang phục"
                  placeholder={mode === 'handover' ? 'Ví dụ: BC-028' : 'Ví dụ: BC-031'}
                  value={barcode}
                  onChange={(event) => {
                    setBarcode(event.target.value);
                    setScanIssue('');
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      void lookup();
                    }
                  }}
                />
                <Button
                  onClick={() => {
                    void lookup();
                  }}
                  loading={scanBusy}
                >
                  <Icon name="scan" size={18} /> Tra cứu
                </Button>
              </div>
              {scanIssue && (
                <Feedback
                  tone="danger"
                  title={
                    scenario === 'barcodeOtherBranch'
                      ? 'Mã thuộc chi nhánh khác'
                      : 'Chưa tìm thấy bộ phù hợp'
                  }
                >
                  {scanIssue}
                </Feedback>
              )}
              {matchedCode && (
                <Feedback tone="success" title={`${matchedCode} khớp đơn ${order.id}`}>
                  <span>
                    {order.items.find((item) => item.unitCode === matchedCode)?.costume} ·{' '}
                    {order.items.find((item) => item.unitCode === matchedCode)?.variant} ·{' '}
                    {order.customer} · hạn trả {order.returnAt}
                  </span>
                </Feedback>
              )}
              <div className="expected-units">
                <span>Mã cần đối chiếu:</span>
                {order.items.map((item) => (
                  <span
                    className={
                      'barcode-chip' +
                      (matchedCodes.includes(item.unitCode ?? '') ? ' scanned' : '')
                    }
                    key={item.id}
                  >
                    {matchedCodes.includes(item.unitCode ?? '') ? '✓ ' : ''}
                    {item.unitCode ?? 'Chưa gán mã'}
                  </span>
                ))}
              </div>
              {mode === 'return' && order.items.length > 1 && (
                <p className="section-help" role="status">
                  Đã quét {scannedItems.length}/{order.items.length} bộ. Bộ chưa quét vẫn ở khách;
                  cọc chỉ được quyết toán khi backend xác nhận điều kiện trả.
                </p>
              )}
            </section>
            <section className="task-card" id="task-check">
              <div className="task-card-heading">
                <span className="round-step">02</span>
                <div>
                  <p className="eyebrow">
                    {mode === 'handover' ? 'TRƯỚC KHI GIAO' : 'KHI NHẬN TRẢ'}
                  </p>
                  <h2>{mode === 'handover' ? 'Tình trạng và phụ kiện' : 'Kiểm tra từng bộ'}</h2>
                </div>
              </div>
              {order.items.map((item) => (
                <div className="check-unit" key={item.id}>
                  <div className="check-unit-head">
                    <strong>
                      {item.costume} · {item.variant}
                    </strong>
                    <span>{item.unitCode}</span>
                  </div>
                  {mode === 'handover' && (
                    <label className="check-row">
                      <input
                        type="checkbox"
                        aria-label={`Kiểm tra tình trạng xuất ${item.unitCode ?? item.costume}`}
                        checked={!!checks[`${item.id}-condition`]}
                        disabled={!matchedCodes.includes(item.unitCode ?? '')}
                        onChange={(event) =>
                          setChecks((current) => ({
                            ...current,
                            [`${item.id}-condition`]: event.target.checked,
                          }))
                        }
                      />
                      <span>Đã kiểm tra tình trạng xuất của bộ</span>
                    </label>
                  )}
                  <label className="check-row">
                    <input
                      type="checkbox"
                      aria-label={`Đối chiếu phụ kiện ${item.unitCode ?? item.costume}`}
                      checked={!!checks[`${item.id}-accessories`]}
                      disabled={!matchedCodes.includes(item.unitCode ?? '')}
                      onChange={(event) =>
                        setChecks((current) => ({
                          ...current,
                          [`${item.id}-accessories`]: event.target.checked,
                        }))
                      }
                    />
                    <span>
                      {mode === 'handover'
                        ? 'Đã đối chiếu phụ kiện thực giao'
                        : 'Đã đối chiếu phụ kiện thiếu/hỏng'}
                    </span>
                  </label>
                  {mode === 'return' && matchedCodes.includes(item.unitCode ?? '') && (
                    <SelectField
                      label={`Kết quả kiểm ${item.unitCode ?? item.costume}`}
                      value={returnConditions[item.id] ?? ''}
                      onChange={(event) =>
                        setReturnConditions((current) => ({
                          ...current,
                          [item.id]: event.target.value as 'PASSED' | 'PENDING_ASSESSMENT',
                        }))
                      }
                    >
                      <option value="">Chọn kết quả sau khi kiểm</option>
                      <option value="PASSED">Đạt · không thấy vấn đề</option>
                      <option value="PENDING_ASSESSMENT">Cần đánh giá hư hỏng hoặc thiếu</option>
                    </SelectField>
                  )}
                </div>
              ))}
              <TextAreaField
                label={
                  needsAssessment
                    ? 'Mô tả vấn đề cần đánh giá (bắt buộc)'
                    : 'Ghi chú tình trạng / lý do phí'
                }
                rows={3}
                required={needsAssessment}
                placeholder="Ghi lại điều cần xử lý; nội dung chỉ tồn tại trong phiên demo"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              {needsAssessment && (
                <Feedback tone="warning" title="Chờ đánh giá, tiếp tục giữ cọc">
                  Ghi rõ dấu hiệu và bộ liên quan. Chưa chốt phí, cấn trừ hoặc hoàn cọc từ lựa chọn
                  này; cần biên bản và người xử lý ở backend.
                </Feedback>
              )}
              <p className="section-help">
                Ảnh bằng chứng cần dịch vụ lưu trữ và quyền truy cập; prototype chưa tải ảnh lên.
              </p>
            </section>
            <section className="task-card" id="task-money">
              <div className="task-card-heading">
                <span className="round-step">03</span>
                <div>
                  <p className="eyebrow">{mode === 'handover' ? 'THU TẠI QUẦY' : 'QUYẾT TOÁN'}</p>
                  <h2>
                    {mode === 'handover' ? 'Tiền thuê và tiền cọc' : 'Phí, cấn trừ và hoàn cọc'}
                  </h2>
                </div>
              </div>
              {mode === 'handover' ? (
                <>
                  <SelectField
                    label="Phương thức thu (bản xem trước)"
                    value={effectiveMethod}
                    disabled={scenario === 'bankPending'}
                    onChange={(event) => {
                      setMethod(event.target.value as 'CASH' | 'BANK_TRANSFER');
                      setRentPreview(false);
                      setDepositPreview(false);
                    }}
                  >
                    <option value="CASH">Tiền mặt</option>
                    <option value="BANK_TRANSFER">Chuyển khoản</option>
                  </SelectField>
                  <div className="collection-table">
                    <div className="collection-head">
                      <span>Khoản</span>
                      <span>Cần thu</span>
                      <span>Đánh dấu nhận (demo)</span>
                      <span>Còn thiếu</span>
                    </div>
                    <div>
                      <strong>Tiền thuê</strong>
                      <span>
                        <span className="collection-mobile-label">Cần thu</span>
                        {money(rental?.amount ?? 0)}
                      </span>
                      <span>
                        <span className="collection-mobile-label">Đã đánh dấu nhận</span>
                        {effectiveMethod === 'CASH' && rentPreview
                          ? money(rental?.amount ?? 0)
                          : money(0)}
                      </span>
                      <span>
                        <span className="collection-mobile-label">Còn thiếu</span>
                        {effectiveMethod === 'CASH' && rentPreview
                          ? money(0)
                          : money(rental?.amount ?? 0)}
                      </span>
                    </div>
                    <div>
                      <strong>Tiền cọc</strong>
                      <span>
                        <span className="collection-mobile-label">Cần thu</span>
                        {money(deposit?.amount ?? 0)}
                      </span>
                      <span>
                        <span className="collection-mobile-label">Đã đánh dấu nhận</span>
                        {effectiveMethod === 'CASH' && depositPreview
                          ? money(deposit?.amount ?? 0)
                          : money(0)}
                      </span>
                      <span>
                        <span className="collection-mobile-label">Còn thiếu</span>
                        {effectiveMethod === 'CASH' && depositPreview
                          ? money(0)
                          : money(deposit?.amount ?? 0)}
                      </span>
                    </div>
                  </div>
                  {effectiveMethod === 'CASH' ? (
                    <div className="cash-checks">
                      <p className="section-help">
                        Chỉ xem trước việc đối chiếu tiền mặt; chưa ghi giao dịch hoặc giao bộ.
                      </p>
                      <label className="check-row">
                        <input
                          type="checkbox"
                          checked={rentPreview}
                          onChange={(event) => setRentPreview(event.target.checked)}
                        />
                        <span>Xem trước: đã nhận tiền thuê bằng tiền mặt</span>
                      </label>
                      <label className="check-row">
                        <input
                          type="checkbox"
                          checked={depositPreview}
                          onChange={(event) => setDepositPreview(event.target.checked)}
                        />
                        <span>Xem trước: đã nhận tiền cọc bằng tiền mặt</span>
                      </label>
                    </div>
                  ) : (
                    <Feedback tone="warning" title="Chuyển khoản chưa đối soát">
                      Chưa xác nhận tiền đã nhận. Kiểm tra giao dịch và chỉ ghi nhận sau đối soát;
                      bản demo không kết nối ngân hàng.
                    </Feedback>
                  )}
                  {scenario === 'bankPending' && (
                    <Feedback tone="warning" title="Giao dịch đang chờ xác minh">
                      Không đánh dấu Đã thu hoặc giao bộ cho đến khi đối soát xong.
                    </Feedback>
                  )}
                </>
              ) : (
                settlement &&
                allReturnItemsScanned &&
                allChecked &&
                !needsAssessment && (
                  <>
                    <div className="settlement-table">
                      <div>
                        <span>Cọc đang giữ</span>
                        <strong>{money(settlement.heldDeposit)}</strong>
                      </div>
                      <div>
                        <span>Phí trễ / hỏng / thiếu</span>
                        <strong>
                          {money(settlement.lateFee)} / {money(settlement.damageFee)} /{' '}
                          {money(settlement.missingFee)}
                        </strong>
                      </div>
                      <div>
                        <span>Cấn trừ</span>
                        <strong>{money(settlement.offset)}</strong>
                      </div>
                      <div>
                        <span>Đã hoàn</span>
                        <strong>{money(settlement.refunded)}</strong>
                      </div>
                      <div className="settlement-total">
                        <span>Còn dự kiến hoàn</span>
                        <strong>{money(settlement.remainingRefund)}</strong>
                      </div>
                    </div>
                    <p className="section-help">
                      Đây là snapshot fixture. Phí và số hoàn thực tế phải do backend quyết toán;
                      giao diện không tự tính.
                    </p>
                    {snapshotConditionMismatch && (
                      <Feedback tone="warning" title="Kết quả kiểm khác snapshot phí">
                        Bộ được chọn là Đạt nhưng snapshot vẫn có phí hỏng hoặc thiếu. Đối chiếu
                        chứng từ trước khi quyết toán; giao diện không tự sửa số tiền.
                      </Feedback>
                    )}
                    {scenario === 'refundFailed' && (
                      <Feedback tone="danger" title="Hoàn cọc chưa thành công">
                        Giao dịch RF-DEMO-01 chưa hoàn tất. Giữ nguyên lịch sử refund; xem lý do và
                        thử lại theo quyền sau khi kiểm tra, tránh hoàn trùng.
                      </Feedback>
                    )}
                  </>
                )
              )}
              {mode === 'return' &&
                !needsAssessment &&
                (!settlement || !allReturnItemsScanned || !allChecked) && (
                  <Feedback
                    title={
                      !allReturnItemsScanned
                        ? 'Chưa đối chiếu đủ barcode để xem quyết toán'
                        : !allChecked
                          ? 'Chưa hoàn tất kiểm từng bộ'
                          : 'Chưa có snapshot quyết toán'
                    }
                  >
                    {!allReturnItemsScanned
                      ? scannedItems.length === 0
                        ? 'Chưa quét bộ nào trong phiên này. Đối chiếu barcode trước khi xem số quyết toán; cọc vẫn đang giữ.'
                        : 'Còn barcode chưa quét trong phiên này. Theo dõi tình trạng từng bộ và tiếp tục giữ cọc; chưa dùng số dự kiến hoàn để chốt tiền.'
                      : !allChecked
                        ? 'Đối chiếu phụ kiện và chọn kết quả kiểm cho từng bộ đã quét trước khi xem số tiền.'
                        : 'Cần backend trả số phí, cấn trừ và khoản còn hoàn từ chứng từ trước khi quyết toán.'}
                  </Feedback>
                )}
              {mode === 'return' && (
                <p className="section-help">
                  Phương thức hoàn cọc qua SePay chưa chốt. Chỉ hiển thị trạng thái giao dịch thực
                  tế; không suy ra đã hoàn từ số dự kiến hoàn.
                </p>
              )}
              {result?.signature === previewSignature && !restricted && (
                <Feedback tone="success" title="Đã kiểm tra điều kiện trong phiên demo">
                  {result.text}
                </Feedback>
              )}
              {mode === 'return' && result?.signature === previewSignature && !restricted && (
                <div
                  className="return-review"
                  aria-label="Tóm tắt các bộ đã kiểm trong bản xem trước"
                >
                  <strong>
                    Đã kiểm {scannedItems.length}/{order.items.length} bộ
                  </strong>
                  <ul>
                    {scannedItems.map((item) => (
                      <li key={item.id}>
                        {item.unitCode} ·{' '}
                        {returnConditions[item.id] === 'PASSED' ? 'Đạt' : 'Chờ đánh giá'}
                      </li>
                    ))}
                  </ul>
                  {scannedItems.length < order.items.length && (
                    <p>
                      Còn ở khách:{' '}
                      {order.items
                        .filter((item) => !matchedCodes.includes(item.unitCode ?? ''))
                        .map((item) => item.unitCode)
                        .join(', ')}
                    </p>
                  )}
                </div>
              )}
              <div className="task-final">
                <Button
                  onClick={mode === 'handover' ? previewHandover : previewReturn}
                  disabled={
                    !scannedEnough ||
                    !allChecked ||
                    needsAssessmentNote ||
                    restricted ||
                    (mode === 'handover' &&
                      (!rentPreview || !depositPreview || effectiveMethod === 'BANK_TRANSFER'))
                  }
                >
                  {mode === 'handover'
                    ? 'Kiểm tra điều kiện giao'
                    : order.status === 'ACTIVE'
                      ? `Xem trước nhận ${scannedItems.length}/${order.items.length} bộ`
                      : 'Xem trước quyết toán'}
                </Button>
                {!scannedEnough && (
                  <p role="status">
                    {mode === 'handover'
                      ? 'Quét đủ các mã bộ của đơn trước khi kiểm tra.'
                      : 'Quét ít nhất một mã bộ của đơn trước khi kiểm tra.'}
                  </p>
                )}
                {scannedEnough && !allChecked && (
                  <p role="status">
                    {mode === 'return'
                      ? 'Đối chiếu phụ kiện và chọn kết quả kiểm cho các bộ đã quét.'
                      : 'Đánh dấu tình trạng và phụ kiện cho mọi bộ của đơn.'}
                  </p>
                )}
                {needsAssessmentNote && (
                  <p role="status">Mô tả vấn đề cần đánh giá trước khi xem kết quả nhận trả.</p>
                )}
                {mode === 'handover' &&
                  scannedEnough &&
                  allChecked &&
                  effectiveMethod === 'CASH' &&
                  (!rentPreview || !depositPreview) && (
                    <p role="status">
                      Đối chiếu riêng tiền thuê và tiền cọc trước khi xem điều kiện giao.
                    </p>
                  )}
                <p>
                  {mode === 'handover'
                    ? 'Chỉ backend có thể xác nhận thu tiền và chuyển đơn sang Đang thuê.'
                    : 'Cọc chỉ hoàn sau kiểm tra và quyết toán được xác nhận.'}
                </p>
              </div>
            </section>
          </div>
          <aside className="task-side">
            <MoneyBreakdown lines={order.money} title="Trạng thái tiền của đơn" />
            <div className="task-side-note">
              <p className="eyebrow">TRẠNG THÁI NHIỀU CHIỀU</p>
              <p>
                <strong>Đơn:</strong> {orderStatus[order.status].text}
              </p>
              <p>
                <strong>Bộ:</strong>{' '}
                {order.items.map((item) => `${item.unitCode} · ${item.unitStatus}`).join(', ')}
              </p>
              <p>
                <strong>Cọc:</strong> {deposit?.status}
              </p>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
