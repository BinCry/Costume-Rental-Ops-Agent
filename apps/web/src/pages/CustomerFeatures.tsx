import { useEffect, useRef, useState } from 'react';
import type { Navigate } from '../App';
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Feedback,
  Field,
  SelectField,
  StatusLabel,
} from '../components/ui';
import { money, orderStatus } from '../components/support';
import {
  BranchSelector,
  DateTimeField,
  FilterBar,
  InlineIssue,
  KeyFacts,
  MoneySummary,
  PageHeading,
  Panel,
  StateGate,
  Timeline,
} from '../components/studio';
import { useFixtureResource } from '../components/useFixtureResource';
import { branches, fixturePeriod } from '../fixtures/adapter';
import { studioAdapter, type CustomerOrder } from '../fixtures/studio';
import type { DemoScenario } from '../fixtures/types';

export function CostumeDetailPage({
  id,
  scenario,
  go,
  initialContext,
}: {
  id: string;
  scenario: DemoScenario;
  go: Navigate;
  initialContext: URLSearchParams;
}) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.details);
  const requestedPickup = initialContext.get('pickup');
  const requestedReturn = initialContext.get('returnAt');
  const requestedBranch = initialContext.get('branch');
  const [variantCode, setVariantCode] = useState(initialContext.get('variantCode') ?? '');
  const [branch, setBranch] = useState(
    requestedBranch && branches.includes(requestedBranch) ? requestedBranch : branches[0],
  );
  const [pickup, setPickup] = useState(
    requestedPickup?.trim() ? requestedPickup : fixturePeriod.pickup,
  );
  const [due, setDue] = useState(
    requestedReturn?.trim() ? requestedReturn : fixturePeriod.returnAt,
  );
  const [photo, setPhoto] = useState(0);
  const catalogContext = Object.fromEntries(
    [...initialContext.entries()].filter(([key]) => key !== 'id'),
  );
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Chưa có trang phục để xem"
    >
      {(items) => {
        const item = items.find((value) => value.id === id);
        if (!item)
          return (
            <div className="page">
              <EmptyState title="Không tìm thấy mẫu trang phục">
                <Button onClick={() => go('catalog', catalogContext)}>Về bộ sưu tập</Button>
              </EmptyState>
            </div>
          );
        const variant =
          item.variants.find((value) => value.code === variantCode) ?? item.variants[0];
        const known =
          branch === 'Chi nhánh Quận 1' &&
          pickup === fixturePeriod.pickup &&
          due === fixturePeriod.returnAt;
        const available = known && item.id !== 'dam-rouge' && scenario !== 'conflict';
        return (
          <div className="page">
            <button
              className="text-link"
              onClick={() => go('catalog', { ...catalogContext, branch, pickup, returnAt: due })}
            >
              ← Bộ sưu tập
            </button>
            <div className="costume-detail-grid">
              <div>
                <div
                  className={`detail-photo costume-${item.imagePosition} detail-photo-${photo}`}
                  role="img"
                  aria-label={`Ảnh minh họa ${item.name}, góc ${photo + 1}`}
                />
                <div className="photo-thumbs" aria-label="Chọn góc ảnh minh họa">
                  {[0, 1, 2].map((n) => (
                    <button
                      key={n}
                      onClick={() => setPhoto(n)}
                      aria-pressed={photo === n}
                      aria-label={`Xem ảnh ${n + 1}`}
                      className={`costume-${item.imagePosition} ${photo === n ? 'selected' : ''}`}
                    />
                  ))}
                </div>
                <p className="muted small-note">
                  Ảnh biên tập minh họa; ảnh từng biến thể cần kết nối media từ API.
                </p>
              </div>
              <div>
                <p className="eyebrow">{item.category} · Bộ sưu tập</p>
                <h1>{item.name}</h1>
                <p className="lead">{item.description}</p>
                <div className="detail-rule">
                  <h2>Chất liệu và phom dáng</h2>
                  <p>
                    {item.material}. {variant.fit}
                  </p>
                </div>
                <div className="detail-rule">
                  <h2>Phụ kiện</h2>
                  <p>{item.accessories.join(' · ')}</p>
                </div>
                <Panel title="Chọn size / màu">
                  <div className="variant-pills">
                    {item.variants.map((value) => (
                      <button
                        key={value.code}
                        className={variant.code === value.code ? 'active' : ''}
                        onClick={() => setVariantCode(value.code)}
                        aria-pressed={variant.code === value.code}
                      >
                        {value.size} · {value.color}
                        {value.edition ? ` · ${value.edition}` : ''}
                      </button>
                    ))}
                  </div>
                  <KeyFacts
                    rows={[
                      { label: 'Giá thuê / ngày', value: money(variant.price) },
                      { label: 'Tiền cọc', value: money(variant.deposit) },
                      { label: 'Giá thay thế theo biến thể', value: money(variant.replacement) },
                    ]}
                  />
                </Panel>
                <Panel title="Kiểm tra khoảng thuê">
                  <div className="feature-filters">
                    <BranchSelector value={branch} onChange={setBranch} />
                    <DateTimeField label="Nhận" value={pickup} onChange={setPickup} />
                    <DateTimeField label="Trả" value={due} onChange={setDue} />
                  </div>
                  <Feedback
                    tone={known ? (available ? 'success' : 'warning') : 'info'}
                    title={
                      known
                        ? available
                          ? 'Có khả năng còn bộ theo kỳ mẫu'
                          : 'Không có bộ phù hợp theo kỳ mẫu'
                        : 'Chưa có dữ liệu khả dụng cho kỳ này'
                    }
                  >
                    Việc xem khả dụng không giữ bộ. Nhân viên sẽ duyệt và gán từng bộ sau khi bạn
                    gửi yêu cầu.
                  </Feedback>
                </Panel>
                <div className="feature-actions">
                  <Button
                    onClick={() =>
                      go('booking', {
                        costume: item.id,
                        variant: `${variant.size} / ${variant.color}`,
                        branch,
                        pickup,
                        returnAt: due,
                      })
                    }
                  >
                    Bắt đầu đặt thuê
                  </Button>
                </div>
                <p className="muted small-note">
                  Tiền thuê và cọc thu lúc nhận. Trả tại chính chi nhánh nhận; hoàn cọc sau kiểm tra
                  tình trạng.
                </p>
              </div>
            </div>
          </div>
        );
      }}
    </StateGate>
  );
}

export function MyRentalsPage({
  id,
  scenario,
  go,
  customerCode,
}: {
  id?: string;
  scenario: DemoScenario;
  go: Navigate;
  customerCode: string;
}) {
  const { loading, error, data, retry } = useFixtureResource(
    scenario,
    studioAdapter.customerOrders,
  );
  const [filter, setFilter] = useState('Tất cả');
  const [dialog, setDialog] = useState(false);
  const [reason, setReason] = useState('');
  const [issue, setIssue] = useState('');
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState<CustomerOrder>();
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Bạn chưa có đơn thuê"
    >
      {(orders) => {
        const ownOrders = orders.filter((order) => order.customerCode === customerCode);
        const visible = ownOrders.filter((order) => filter === 'Tất cả' || order.status === filter);
        const selected = id
          ? local?.id === id
            ? local
            : ownOrders.find((order) => order.id === id)
          : undefined;
        const confirm = async () => {
          if (!selected || !reason.trim()) {
            setIssue('Nhập lý do hủy trước khi xác nhận.');
            return;
          }
          setBusy(true);
          setIssue('');
          try {
            setLocal(await studioAdapter.cancelCustomerOrder(selected.id, reason, scenario));
            setDialog(false);
          } catch (e) {
            setIssue(e instanceof Error ? e.message : 'Không thể hủy đơn.');
            setDialog(false);
          } finally {
            setBusy(false);
          }
        };
        if (id && !selected)
          return (
            <div className="page">
              <EmptyState title="Không tìm thấy đơn của bạn">
                <Button onClick={() => go('myRentals')}>Về danh sách</Button>
              </EmptyState>
            </div>
          );
        return (
          <div className="page">
            <PageHeading
              eyebrow="TÀI KHOẢN / ĐƠN THUÊ"
              title={selected ? selected.id : 'Đơn của tôi'}
              description="Theo dõi đơn, từng khoản tiền và tiến độ hoàn cọc."
              action={
                selected ? (
                  <Button variant="secondary" onClick={() => go('myRentals')}>
                    ← Tất cả đơn
                  </Button>
                ) : undefined
              }
            />
            {selected ? (
              <div className="feature-two-column">
                <div>
                  <Panel title="Thông tin thuê">
                    <div className="feature-status-row">
                      <StatusLabel {...orderStatus[selected.status]} />
                      <StatusLabel
                        text={`Tiền thuê: ${selected.rentalStatus}`}
                        tone={selected.rentalStatus === 'Đã thu' ? 'success' : 'warning'}
                      />
                      <StatusLabel text={`Cọc: ${selected.depositStatus}`} tone="info" />
                      <StatusLabel text={`Trả: ${selected.returnStatus}`} tone="neutral" />
                    </div>
                    <KeyFacts
                      rows={[
                        { label: 'Trang phục', value: `${selected.costume} · ${selected.variant}` },
                        { label: 'Chi nhánh nhận và trả', value: selected.branch },
                        { label: 'Nhận', value: selected.pickup },
                        { label: 'Hạn trả', value: selected.due },
                      ]}
                    />
                    {selected.reason && (
                      <Feedback tone="warning" title="Lý do hủy / từ chối">
                        {selected.reason}
                      </Feedback>
                    )}
                    {selected.canCancel && (
                      <div className="destructive-area">
                        <Button variant="danger" onClick={() => setDialog(true)}>
                          Hủy yêu cầu
                        </Button>
                      </div>
                    )}
                  </Panel>
                  <Panel title="Lịch sử và biên nhận">
                    <Timeline items={selected.history} />
                    <p className="muted small-note">
                      Biên nhận điện tử sẽ xuất hiện khi API giao dịch và lưu chứng từ được triển
                      khai.
                    </p>
                  </Panel>
                </div>
                <div>
                  <MoneySummary
                    rental={selected.rental}
                    deposit={selected.deposit}
                    extra={selected.extra}
                    refund={selected.refund}
                  />
                  <Panel title="Trạng thái quyết toán">
                    <KeyFacts
                      rows={[
                        { label: 'Thanh toán thuê', value: selected.rentalStatus },
                        { label: 'Tiền cọc', value: selected.depositStatus },
                        { label: 'Hoàn cọc', value: selected.refundStatus },
                        { label: 'Nhận trả', value: selected.returnStatus },
                      ]}
                    />
                  </Panel>
                </div>
              </div>
            ) : (
              <>
                <FilterBar>
                  <SelectField
                    label="Lọc trạng thái"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    <option>Tất cả</option>
                    {Array.from(new Set(ownOrders.map((order) => order.status))).map((status) => (
                      <option key={status} value={status}>
                        {orderStatus[status].text}
                      </option>
                    ))}
                  </SelectField>
                </FilterBar>
                {visible.length ? (
                  <div className="feature-card-list">
                    {visible.map((order) => (
                      <button
                        className="rental-card"
                        key={order.id}
                        onClick={() => go('myRentalDetail', { order: order.id })}
                      >
                        <span>
                          <strong>{order.costume}</strong>
                          <small>
                            {order.id} · {order.variant}
                          </small>
                          <small>
                            {order.branch} · {order.pickup}
                          </small>
                        </span>
                        <span className="rental-card-right">
                          <StatusLabel {...orderStatus[order.status]} />
                          <strong>{money(order.rental)}</strong>
                          <small>Cọc {money(order.deposit)}</small>
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title={
                      ownOrders.length ? 'Không có đơn ở trạng thái này' : 'Bạn chưa có đơn thuê'
                    }
                  >
                    {ownOrders.length
                      ? 'Chọn trạng thái khác để xem đơn.'
                      : 'Khám phá trang phục và gửi yêu cầu thuê đầu tiên.'}
                  </EmptyState>
                )}
              </>
            )}
            <InlineIssue
              text={issue}
              conflict={scenario === 'version' || scenario === 'cancelled'}
            />
            {dialog && selected && (
              <ConfirmDialog
                title="Hủy yêu cầu thuê"
                confirmText="Xác nhận hủy"
                danger
                loading={busy}
                onClose={() => setDialog(false)}
                onConfirm={() => void confirm()}
              >
                <p>Hủy {selected.id} sẽ được lưu trong lịch sử đơn mẫu. Lý do là bắt buộc.</p>
                <Field
                  label="Lý do hủy"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  error={issue && !reason.trim() ? issue : undefined}
                />
              </ConfirmDialog>
            )}
          </div>
        );
      }}
    </StateGate>
  );
}

export function AccountPage({
  scenario,
  go,
  onRoleChange,
}: {
  scenario: DemoScenario;
  go: Navigate;
  onRoleChange: (role: 'CUSTOMER' | 'SALES_STAFF' | 'INVENTORY_STAFF' | 'ADMIN') => void;
}) {
  const [state, setState] = useState<
    'entry' | 'profile' | 'PENDING' | 'LOCKED' | 'INACTIVE' | 'unauthorized' | 'ready'
  >('entry');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState<'CUSTOMER' | 'SALES_STAFF' | 'INVENTORY_STAFF' | 'ADMIN'>(
    'CUSTOMER',
  );
  const [attempted, setAttempted] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const successRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (state === 'profile') profileRef.current?.querySelector('input')?.focus();
    if (state === 'ready') successRef.current?.focus();
  }, [state]);
  useEffect(() => {
    if (attempted) profileRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [attempted]);
  const demoStateLabels = {
    entry: 'Chưa đăng nhập',
    PENDING: 'Chờ kích hoạt',
    LOCKED: 'Đã khóa',
    INACTIVE: 'Ngừng hoạt động',
    unauthorized: 'Không có quyền',
    ready: 'Đã hoàn thiện hồ sơ',
  } as const;
  return (
    <div className="page account-page">
      <PageHeading
        eyebrow="TÀI KHOẢN"
        title="Đăng nhập & hồ sơ"
        description="Trạng thái mô phỏng để xem hành trình xác thực; chưa kết nối Google OAuth."
      />
      <div className="feature-two-column">
        <Panel title="Truy cập Studio">
          <div className="account-entry">
            <span className="brand-mark">S</span>
            <h2>Rất vui được gặp bạn</h2>
            <p>
              Đăng nhập để theo dõi đơn thuê và hồ sơ. Google sign-in cần backend xác minh token
              trước khi kích hoạt.
            </p>
            <Button variant="secondary" onClick={() => setState('profile')}>
              Tiếp tục với Google · xem mô phỏng
            </Button>
          </div>
          {state === 'profile' && (
            <div className="stack-form" ref={profileRef}>
              <Field
                label="Họ tên liên hệ"
                value={name}
                onChange={(e) => setName(e.target.value)}
                error={attempted && !name.trim() ? 'Nhập họ tên liên hệ.' : undefined}
              />
              <Field
                label="Số điện thoại"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                error={
                  attempted && !/^0[0-9 ]{8,12}$/.test(phone.trim())
                    ? 'Nhập số điện thoại hợp lệ.'
                    : undefined
                }
              />
              <Button
                onClick={() => {
                  setAttempted(true);
                  if (!name.trim() || !/^0[0-9 ]{8,12}$/.test(phone.trim())) {
                    return;
                  }
                  setAttempted(false);
                  setState('ready');
                }}
              >
                Hoàn thiện hồ sơ mẫu
              </Button>
            </div>
          )}
          {state === 'ready' && (
            <div ref={successRef} tabIndex={-1}>
              <Feedback tone="success" title="Hồ sơ mẫu đã hoàn thiện">
                Tài khoản thực tế chỉ được kích hoạt sau khi backend xác minh Google và quyền hiệu
                lực.
              </Feedback>
            </div>
          )}
          {state === 'PENDING' && (
            <Feedback tone="warning" title="Chờ kích hoạt">
              Tài khoản nhân viên cần được quản trị xác minh và gán role tại chi nhánh.
            </Feedback>
          )}
          {(state === 'LOCKED' || state === 'INACTIVE') && (
            <Feedback
              tone="danger"
              title={state === 'LOCKED' ? 'Tài khoản đã khóa' : 'Tài khoản ngừng hoạt động'}
            >
              Liên hệ quản trị studio để được hỗ trợ.
            </Feedback>
          )}
          {state === 'unauthorized' && (
            <Feedback tone="danger" title="Không có quyền">
              Vai trò hiện tại không được truy cập khu vực này.
            </Feedback>
          )}
        </Panel>
        <Panel title="Xem thử trạng thái quyền">
          <SelectField
            label="Vai trò hiệu lực mẫu"
            value={role}
            onChange={(e) => setRole(e.target.value as typeof role)}
          >
            <option value="CUSTOMER">Khách hàng</option>
            <option value="SALES_STAFF">Nhân viên bán hàng</option>
            <option value="INVENTORY_STAFF">Nhân viên kho</option>
            <option value="ADMIN">Quản trị chuỗi</option>
          </SelectField>
          <div className="variant-pills">
            {(['entry', 'PENDING', 'LOCKED', 'INACTIVE', 'unauthorized', 'ready'] as const).map(
              (value) => (
                <button
                  key={value}
                  className={state === value ? 'active' : ''}
                  onClick={() => setState(value)}
                  aria-pressed={state === value}
                >
                  {demoStateLabels[value]}
                </button>
              ),
            )}
          </div>
          <Button
            disabled={state !== 'ready' || scenario === 'permission'}
            onClick={() => {
              onRoleChange(role);
              go(
                role === 'CUSTOMER' ? 'myRentals' : role === 'ADMIN' ? 'adminCatalog' : 'dashboard',
              );
            }}
          >
            Mở khu vực theo quyền
          </Button>
          <p className="muted small-note">
            Nút điều hướng demo phản ánh vai trò chọn. API `me` sau này phải trả quyền hiệu lực tại
            chi nhánh, UI không cấp quyền thật.
          </p>
        </Panel>
      </div>
    </div>
  );
}
