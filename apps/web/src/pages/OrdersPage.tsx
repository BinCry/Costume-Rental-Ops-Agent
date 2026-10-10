import { useEffect, useRef, useState } from 'react';
import type { Navigate } from '../App';
import { DataTable } from '../components/DataTable';
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Feedback,
  Field,
  Icon,
  MoneyBreakdown,
  SelectField,
  StatusLabel,
  TextAreaField,
} from '../components/ui';
import { orderStatus } from '../components/support';
import { useFixtureResource } from '../components/useFixtureResource';
import { branches, fixtureAdapter, fixtureCatalog } from '../fixtures/adapter';
import { studioAdapter } from '../fixtures/studio';
import type { DemoScenario, Order, OrderStatus } from '../fixtures/types';

const loadOrders = (scenario: DemoScenario) => fixtureAdapter.listOrders(scenario);
const groupDefs: { label: string; statuses: OrderStatus[] }[] = [
  { label: 'Chờ xác nhận', statuses: ['PENDING_CONFIRMATION'] },
  { label: 'Sắp giao', statuses: ['CONFIRMED', 'PREPARING', 'READY_FOR_PICKUP'] },
  { label: 'Đang thuê', statuses: ['ACTIVE'] },
  { label: 'Cần kiểm tra', statuses: ['RETURN_INSPECTION'] },
  { label: 'Khác', statuses: ['DRAFT', 'COMPLETED', 'REJECTED', 'CANCELLED', 'NO_SHOW'] },
];

export function OrdersPage({
  scenario,
  go,
  initialOrderId,
  initialFilter,
  initialBranch,
  canManage = true,
}: {
  scenario: DemoScenario;
  go: Navigate;
  initialOrderId?: string;
  initialFilter?: string;
  initialBranch: string;
  canManage?: boolean;
}) {
  const [branch, setBranch] = useState(initialBranch);
  const [selectedId, setSelectedId] = useState(initialOrderId ?? 'RT-1024');
  const [group, setGroup] = useState(initialFilter ?? 'Tất cả');
  const [search, setSearch] = useState('');
  const [mobileDetail, setMobileDetail] = useState(!!initialOrderId);
  const [selectedUnits, setSelectedUnits] = useState<string[]>([]);
  const [unavailableUnits, setUnavailableUnits] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<'confirm' | 'reject' | 'cancel' | null>(null);
  const [reason, setReason] = useState('');
  const [localConfirmed, setLocalConfirmed] = useState(false);
  const [localCancelled, setLocalCancelled] = useState(false);
  const [proposedDue, setProposedDue] = useState('');
  const [proposedVariant, setProposedVariant] = useState('');
  const [changeNote, setChangeNote] = useState('');
  const [preparedCodes, setPreparedCodes] = useState<string[]>([]);
  const [accessoryCodes, setAccessoryCodes] = useState<string[]>([]);
  const { loading, data, error, retry } = useFixtureResource(scenario, loadOrders);
  const detailBackRef = useRef<HTMLButtonElement>(null);
  const detailRef = useRef<HTMLElement>(null);
  const selectedRowRef = useRef<HTMLButtonElement>(null);
  const noticeRef = useRef<HTMLDivElement>(null);
  const unitSelectionRef = useRef<HTMLDivElement>(null);
  const previousMobileViewRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (window.innerWidth >= 768 || loading || error) return;
    if (previousMobileViewRef.current === null && !mobileDetail) {
      previousMobileViewRef.current = false;
      return;
    }
    if (previousMobileViewRef.current === mobileDetail) return;
    previousMobileViewRef.current = mobileDetail;
    const target = mobileDetail ? detailBackRef.current : selectedRowRef.current;
    target?.focus({ preventScroll: true });
    (mobileDetail ? detailRef.current : target)?.scrollIntoView({
      block: 'start',
      behavior: 'instant',
    });
  }, [mobileDetail, loading, error]);
  useEffect(() => {
    if (!notice) return;
    noticeRef.current?.focus();
    noticeRef.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [notice]);
  const scoped = (data ?? []).filter((order) => order.branch === branch);
  const visible = scoped.filter(
    (order) =>
      (group === 'Tất cả' ||
        groupDefs.find((entry) => entry.label === group)?.statuses.includes(order.status)) &&
      `${order.id} ${order.customer} ${order.phone} ${order.items.map((item) => item.unitCode).join(' ')}`
        .toLocaleLowerCase('vi')
        .includes(search.toLocaleLowerCase('vi')),
  );
  const rawOrder =
    scoped.find((entry) => entry.id === selectedId) ?? (initialOrderId ? undefined : visible[0]);
  const order: Order | undefined =
    rawOrder && localCancelled && scenario === 'cancelled' && rawOrder.id === 'RT-1024'
      ? {
          ...rawOrder,
          status: 'CANCELLED',
          history: [...rawOrder.history, 'Phiên demo · Khách vừa hủy khi nhân viên đang duyệt'],
        }
      : rawOrder &&
          localConfirmed &&
          rawOrder.status === 'PENDING_CONFIRMATION' &&
          rawOrder.id === 'RT-1024'
        ? {
            ...rawOrder,
            status: 'CONFIRMED',
            items: rawOrder.items.map((item, index) => ({
              ...item,
              unitCode: selectedUnits[index],
              unitStatus: 'Sẵn sàng',
            })),
            history: [...rawOrder.history, 'Phiên demo · Đã chọn bộ và xem trước xác nhận'],
          }
        : rawOrder;
  const firstItem = order?.items[0];
  const relatedCostume = fixtureCatalog.find((item) => item.name === firstItem?.costume);
  const variantChoices =
    relatedCostume?.sizes.map((size) => `${size} / ${relatedCostume.colors[0]}`) ?? [];
  const currentDue = order?.returnAt.match(/(\d{2})\/(\d{2})\/(\d{4})\s*·\s*(\d{2}):(\d{2})/);
  const dueValue = currentDue
    ? `${currentDue[3]}-${currentDue[2]}-${currentDue[1]}T${currentDue[4]}:${currentDue[5]}`
    : '';
  const extensionValid = !!proposedDue && !!dueValue && proposedDue > dueValue;
  const variantValid = !!proposedVariant && proposedVariant !== firstItem?.variant;
  const assignedCodes =
    order?.items.map((item) => item.unitCode).filter((code): code is string => !!code) ?? [];
  const preparationComplete =
    !!order &&
    assignedCodes.length === order.items.length &&
    assignedCodes.every((code) => preparedCodes.includes(code) && accessoryCodes.includes(code));
  const chooseOrder = (id: string) => {
    setSelectedId(id);
    setMobileDetail(true);
    setSelectedUnits([]);
    setNotice('');
    setLocalConfirmed(false);
    setLocalCancelled(false);
    setProposedDue('');
    setProposedVariant('');
    setChangeNote('');
    setPreparedCodes([]);
    setAccessoryCodes([]);
    window.history.pushState(null, '', `/van-hanh/don-thue/${encodeURIComponent(id)}`);
  };
  const toggleUnit = (code: string) =>
    setSelectedUnits((current) =>
      current.includes(code) ? current.filter((entry) => entry !== code) : [...current, code],
    );
  const confirm = async () => {
    if (!order) return;
    setBusy(true);
    setNotice('');
    try {
      await fixtureAdapter.confirmOrder(order.id, order.version, selectedUnits, scenario);
      studioAdapter.reflectConfirmation(order.id, selectedUnits);
      setLocalConfirmed(true);
      setDialog(null);
      setNotice(
        'Đã xem trước xác nhận và gán bộ trong phiên demo. Dữ liệu không được lưu lên máy chủ.',
      );
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Chưa lưu được thay đổi.';
      setNotice(message);
      if (scenario === 'conflict') {
        setUnavailableUnits((current) => [...current, 'BC-001']);
        setSelectedUnits((current) => current.filter((code) => code !== 'BC-001'));
      }
      if (scenario === 'cancelled') setLocalCancelled(true);
      setDialog(null);
    } finally {
      setBusy(false);
    }
  };
  const previewDecision = async () => {
    if (!reason.trim()) {
      setNotice('Cần nhập lý do trước khi từ chối hoặc hủy.');
      setDialog(null);
      return;
    }
    if (!order || (dialog !== 'reject' && dialog !== 'cancel')) return;
    setBusy(true);
    try {
      await studioAdapter.decideOrder(
        order.id,
        dialog === 'reject' ? 'REJECTED' : 'CANCELLED',
        reason.trim(),
        scenario,
      );
      setNotice(
        `Đã ${dialog === 'reject' ? 'từ chối' : 'hủy'} đơn trong fixture; lý do hiển thị cho khách.`,
      );
      setDialog(null);
      retry();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : 'Không cập nhật được đơn.');
      setDialog(null);
    } finally {
      setBusy(false);
    }
  };
  const markPrepared = async () => {
    if (!order || !preparationComplete || busy) return;
    setBusy(true);
    setNotice('');
    try {
      await studioAdapter.markReadyForPickup(order.id, scenario);
      setNotice(
        'Đã kiểm đủ bộ và phụ kiện trong fixture; đơn sẵn sàng giao. Tiền thuê và cọc vẫn chưa thu.',
      );
      retry();
    } catch (caught) {
      setNotice(
        caught instanceof Error ? caught.message : 'Chưa chuyển được đơn sang sẵn sàng giao.',
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="page staff-page orders-page">
      <div className="staff-page-heading">
        <div>
          <p className="eyebrow">UI-07 · KHÔNG GIAN XỬ LÝ ĐƠN</p>
          <h1>Đơn thuê</h1>
          <p>Đọc chi tiết, kiểm tra bộ và xử lý theo đúng trạng thái.</p>
        </div>
        <StatusLabel
          text={loading ? 'Đang tải đơn' : `${scoped.length} đơn tại chi nhánh`}
          tone="neutral"
        />
      </div>
      <div className="staff-toolbar">
        <SelectField
          label="Chi nhánh"
          value={branch}
          onChange={(event) => {
            setBranch(event.target.value);
            setSelectedUnits([]);
          }}
        >
          {branches.map((entry) => (
            <option key={entry}>{entry}</option>
          ))}
        </SelectField>
        <Field
          label="Tìm mã đơn, khách hoặc barcode"
          placeholder="RT-1024, Nguyễn An, BC-..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <SelectField
          label="Nhóm trạng thái"
          value={group}
          onChange={(event) => setGroup(event.target.value)}
        >
          <option>Tất cả</option>
          {groupDefs.map((entry) => (
            <option key={entry.label}>{entry.label}</option>
          ))}
        </SelectField>
      </div>
      {notice && (
        <div ref={noticeRef} tabIndex={-1} className="notice-focus-target">
          <Feedback
            tone={notice.startsWith('Đã ') ? 'success' : 'warning'}
            title={notice.startsWith('Đã ') ? 'Thao tác fixture hoàn tất' : 'Cần kiểm tra lại'}
            action={
              notice.includes('Đơn đã thay đổi') ? (
                <Button variant="secondary" onClick={retry}>
                  Làm mới đơn
                </Button>
              ) : notice.includes('vừa hết khả dụng') ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    unitSelectionRef.current?.focus();
                    unitSelectionRef.current?.scrollIntoView({
                      block: 'start',
                      behavior: 'instant',
                    });
                  }}
                >
                  Xem bộ còn trống
                </Button>
              ) : undefined
            }
          >
            {notice}
          </Feedback>
        </div>
      )}
      {scenario === 'permission' && (
        <Feedback tone="danger" title="Bạn không còn quyền xử lý đơn tại chi nhánh này">
          Không gửi thao tác cũ. Hãy chuyển chi nhánh có quyền hoặc về bảng việc.
        </Feedback>
      )}
      {error && (
        <Feedback
          tone="danger"
          title="Không tải được danh sách đơn"
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
        <div className="workspace-skeleton">
          <div className="shimmer" />
          <div className="shimmer" />
          <div className="shimmer" />
        </div>
      )}
      {!loading && !error && scoped.length === 0 && (
        <EmptyState
          title="Chưa có đơn tại chi nhánh này"
          action={
            <Button variant="secondary" onClick={() => go('dashboard')}>
              Về bảng việc
            </Button>
          }
        />
      )}
      {!loading && !error && scoped.length > 0 && (
        <div className={`orders-workspace ${mobileDetail ? 'show-detail' : ''}`}>
          <aside className="order-groups">
            <h2>Nhóm đơn</h2>
            <button
              className={group === 'Tất cả' ? 'active' : ''}
              onClick={() => setGroup('Tất cả')}
            >
              <span>Tất cả</span>
              <b>{scoped.length}</b>
            </button>
            {groupDefs.map((entry) => (
              <button
                key={entry.label}
                className={group === entry.label ? 'active' : ''}
                onClick={() => setGroup(entry.label)}
              >
                <span>{entry.label}</span>
                <b>{scoped.filter((item) => entry.statuses.includes(item.status)).length}</b>
              </button>
            ))}
          </aside>
          <section className="order-list" aria-label="Danh sách đơn">
            <div className="order-list-head">
              <div>
                <span className="eyebrow">DANH SÁCH</span>
                <h2>{group}</h2>
              </div>
              <span>{visible.length} đơn</span>
            </div>
            {visible.length === 0 ? (
              <EmptyState title="Không có đơn phù hợp bộ lọc">
                <Button
                  variant="quiet"
                  onClick={() => {
                    setGroup('Tất cả');
                    setSearch('');
                  }}
                >
                  Xóa bộ lọc
                </Button>
              </EmptyState>
            ) : (
              visible.map((entry) => (
                <button
                  key={entry.id}
                  className={`order-list-row ${selectedId === entry.id ? 'selected' : ''}`}
                  ref={selectedId === entry.id ? selectedRowRef : undefined}
                  onClick={() => chooseOrder(entry.id)}
                >
                  <div>
                    <strong>{entry.id}</strong>
                    <small>{entry.pickup}</small>
                  </div>
                  <span>{entry.customer}</span>
                  <StatusLabel
                    text={orderStatus[entry.status].text}
                    tone={orderStatus[entry.status].tone}
                  />
                </button>
              ))
            )}
          </section>
          <section ref={detailRef} className="order-detail" aria-label="Chi tiết đơn đang chọn">
            <button
              ref={detailBackRef}
              className="back-to-list"
              onClick={() => setMobileDetail(false)}
            >
              <Icon name="arrow" size={17} /> Quay lại danh sách
            </button>
            {order ? (
              <>
                <div className="detail-head">
                  <div>
                    <p className="eyebrow">CHI TIẾT ĐƠN · PHIÊN BẢN {order.version}</p>
                    <h2>{order.id}</h2>
                    {canManage && order.status === 'PENDING_CONFIRMATION' && (
                      <a className="text-link" href="#unit-selection">
                        Đến phần chọn bộ và xác nhận ↓
                      </a>
                    )}
                  </div>
                  <StatusLabel
                    text={orderStatus[order.status].text}
                    tone={orderStatus[order.status].tone}
                  />
                </div>
                <div className="detail-section">
                  <h3>Khách và lịch thuê</h3>
                  <dl className="detail-grid">
                    <div>
                      <dt>Người thuê</dt>
                      <dd>{order.customer}</dd>
                    </div>
                    <div>
                      <dt>Liên hệ</dt>
                      <dd>{order.phone}</dd>
                    </div>
                    <div>
                      <dt>Chi nhánh</dt>
                      <dd>{order.branch}</dd>
                    </div>
                    <div>
                      <dt>Nhận đồ</dt>
                      <dd>{order.pickup}</dd>
                    </div>
                    <div>
                      <dt>Trả đồ</dt>
                      <dd>{order.returnAt}</dd>
                    </div>
                    <div>
                      <dt>Cách tính ngày</dt>
                      <dd>{order.dayPolicy}</dd>
                    </div>
                  </dl>
                </div>
                <div className="detail-section">
                  <h3>Trang phục và bộ vật lý</h3>
                  <div className="item-lines">
                    {order.items.map((item, index) => (
                      <div key={item.id} className="item-line">
                        <span className="item-index">{String(index + 1).padStart(2, '0')}</span>
                        <span>
                          <strong>{item.costume}</strong>
                          <small>{item.variant}</small>
                        </span>
                        <span className="unit-code">{item.unitCode ?? 'Chưa gán bộ'}</span>
                        {item.unitStatus && (
                          <StatusLabel
                            text={item.unitStatus}
                            tone={item.unitStatus === 'Đang ở khách' ? 'info' : 'success'}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                <MoneyBreakdown
                  lines={order.money}
                  footer={
                    <p className="money-note">
                      Số tiền theo snapshot fixture; thao tác thu/hoàn được xử lý ở luồng giao/trả.
                    </p>
                  }
                />
                {order.status === 'PENDING_CONFIRMATION' && (
                  <div
                    className="detail-section unit-selection"
                    id="unit-selection"
                    ref={unitSelectionRef}
                    tabIndex={-1}
                  >
                    <div className="section-row">
                      <div>
                        <h3>Chọn bộ khả dụng</h3>
                        <p>
                          Chọn đúng {order.items.length} mã khác nhau. Chỉ bộ READY và không vướng
                          lịch trong fixture mới chọn được.
                        </p>
                      </div>
                      <span className="selection-count">
                        {selectedUnits.length}/{order.items.length}
                      </span>
                    </div>
                    <DataTable
                      filterDisplay={(value) =>
                        value === 'READY'
                          ? 'Sẵn sàng'
                          : value === 'CLEANING'
                            ? 'Đang vệ sinh'
                            : 'Đang sửa chữa'
                      }
                      filterKey={(unit) => unit.status}
                      filterLabel="Trạng thái bộ"
                      searchKey={(unit) => `${unit.code} ${unit.variant}`}
                      rows={order.eligibleUnits.map((unit) => ({ ...unit, id: unit.code }))}
                      columns={[
                        {
                          key: 'choose',
                          title: 'Chọn',
                          render: (unit) => (
                            <input
                              type="checkbox"
                              aria-label={`Chọn bộ ${unit.code}`}
                              checked={selectedUnits.includes(unit.code)}
                              disabled={
                                !canManage ||
                                unit.status !== 'READY' ||
                                !unit.availableAtFixturePeriod ||
                                unavailableUnits.includes(unit.code) ||
                                (selectedUnits.length >= order.items.length &&
                                  !selectedUnits.includes(unit.code))
                              }
                              onChange={() => toggleUnit(unit.code)}
                              onClick={(event) => event.stopPropagation()}
                            />
                          ),
                        },
                        {
                          key: 'code',
                          title: 'Barcode',
                          render: (unit) => <strong>{unit.code}</strong>,
                          sortValue: (unit) => unit.code,
                        },
                        { key: 'variant', title: 'Biến thể', render: (unit) => unit.variant },
                        {
                          key: 'status',
                          title: 'Trạng thái / khả dụng',
                          render: (unit) => (
                            <StatusLabel
                              text={
                                unavailableUnits.includes(unit.code)
                                  ? 'Vừa hết khả dụng'
                                  : unit.status === 'READY' && unit.availableAtFixturePeriod
                                    ? 'READY · Còn theo kỳ'
                                    : unit.status === 'CLEANING'
                                      ? 'Đang vệ sinh'
                                      : 'Đang sửa chữa'
                              }
                              tone={
                                unit.status === 'READY' &&
                                unit.availableAtFixturePeriod &&
                                !unavailableUnits.includes(unit.code)
                                  ? 'success'
                                  : 'warning'
                              }
                            />
                          ),
                        },
                      ]}
                      emptyText="Không có bộ khả dụng trong fixture này"
                    />
                    {unavailableUnits.length > 0 && (
                      <Button variant="secondary" className="refresh-units" onClick={retry}>
                        <Icon name="refresh" size={17} /> Tải lại bộ còn trống
                      </Button>
                    )}
                    {scenario === 'unitBlocked' && (
                      <Feedback tone="warning" title="Bộ đang vệ sinh hoặc sửa chữa">
                        BC-018 và BC-019 không thể gán. Chọn bộ READY khác hoặc một kỳ thuê khác.
                      </Feedback>
                    )}
                    {canManage && (
                      <div className="detail-actions">
                        <Button
                          onClick={() => setDialog('confirm')}
                          disabled={
                            selectedUnits.length !== order.items.length || scenario === 'permission'
                          }
                        >
                          Xác nhận và gán {order.items.length} bộ
                        </Button>
                        <Button
                          variant="quiet"
                          disabled={scenario === 'permission'}
                          onClick={() => {
                            setReason('');
                            setDialog('reject');
                          }}
                        >
                          Từ chối
                        </Button>
                        <Button
                          variant="quiet"
                          disabled={scenario === 'permission'}
                          onClick={() => {
                            setReason('');
                            setDialog('cancel');
                          }}
                        >
                          Hủy đơn
                        </Button>
                      </div>
                    )}
                  </div>
                )}
                {canManage && order.status === 'READY_FOR_PICKUP' && (
                  <div className="detail-actions">
                    <Button onClick={() => go('handover', { order: order.id })}>
                      Mở luồng giao đồ <Icon name="arrow" size={18} />
                    </Button>
                  </div>
                )}
                {canManage && ['CONFIRMED', 'PREPARING'].includes(order.status) && (
                  <div className="detail-section order-preparation" id="order-preparation">
                    <h3>Chuẩn bị từng bộ để giao</h3>
                    <p>
                      Kiểm đúng barcode và phụ kiện thực tế. Chỉ sau khi hoàn tất, đơn mới chuyển
                      sang Sẵn sàng giao trong fixture.
                    </p>
                    {order.items.map((item) => (
                      <div className="check-unit" key={item.id}>
                        <div className="check-unit-head">
                          <strong>
                            {item.costume} · {item.variant}
                          </strong>
                          <span>{item.unitCode ?? 'Chưa gán bộ'}</span>
                        </div>
                        <label className="check-row">
                          <input
                            type="checkbox"
                            aria-label={`Đã kiểm bộ sạch và đúng barcode ${item.unitCode ?? item.costume}`}
                            disabled={!item.unitCode || busy}
                            checked={!!item.unitCode && preparedCodes.includes(item.unitCode)}
                            onChange={(event) =>
                              setPreparedCodes((current) =>
                                event.target.checked
                                  ? [...current, item.unitCode!]
                                  : current.filter((code) => code !== item.unitCode),
                              )
                            }
                          />
                          <span>Đã kiểm bộ sạch và đúng barcode</span>
                        </label>
                        <label className="check-row">
                          <input
                            type="checkbox"
                            aria-label={`Đã đủ phụ kiện đi kèm ${item.unitCode ?? item.costume}`}
                            disabled={!item.unitCode || busy}
                            checked={!!item.unitCode && accessoryCodes.includes(item.unitCode)}
                            onChange={(event) =>
                              setAccessoryCodes((current) =>
                                event.target.checked
                                  ? [...current, item.unitCode!]
                                  : current.filter((code) => code !== item.unitCode),
                              )
                            }
                          />
                          <span>Đã đủ phụ kiện đi kèm</span>
                        </label>
                      </div>
                    ))}
                    <Button
                      disabled={!preparationComplete || busy || scenario === 'permission'}
                      loading={busy}
                      onClick={() => void markPrepared()}
                    >
                      Đánh dấu sẵn sàng giao
                    </Button>
                    {!preparationComplete && (
                      <p role="status">Hoàn tất hai mục kiểm cho mỗi barcode để tiếp tục.</p>
                    )}
                  </div>
                )}
                {canManage &&
                  (order.status === 'ACTIVE' || order.status === 'RETURN_INSPECTION') && (
                    <div className="detail-actions">
                      <Button onClick={() => go('return', { order: order.id })}>
                        Mở luồng nhận trả <Icon name="arrow" size={18} />
                      </Button>
                    </div>
                  )}
                {canManage && order.status === 'ACTIVE' && (
                  <div className="detail-section order-change-panel" id="order-change">
                    <h3>Yêu cầu gia hạn</h3>
                    <p>
                      Hạn hiện tại: <strong>{order.returnAt}</strong>. Giữ nguyên đơn và bộ đang ở
                      khách trong lúc kiểm tra yêu cầu.
                    </p>
                    <Field
                      label="Hạn trả khách muốn đổi sang"
                      type="datetime-local"
                      value={proposedDue}
                      onChange={(event) => setProposedDue(event.target.value)}
                    />
                    <TextAreaField
                      label="Ghi chú trao đổi với khách"
                      rows={2}
                      value={changeNote}
                      onChange={(event) => setChangeNote(event.target.value)}
                    />
                    {proposedDue && !extensionValid && (
                      <Feedback tone="warning" title="Chọn hạn mới sau hạn hiện tại">
                        Hạn trả của đơn chưa thay đổi. Kiểm tra lại ngày giờ khách yêu cầu.
                      </Feedback>
                    )}
                    {extensionValid && (
                      <Feedback tone="info" title="Cần kiểm tra trước khi gia hạn">
                        Yêu cầu đến {proposedDue.replace('T', ' · ')} đang là bản nháp trên màn
                        hình. Backend cần kiểm tra lịch của từng barcode, tính báo giá mới và thu
                        phần phát sinh nếu có; chưa cập nhật hạn trả.
                      </Feedback>
                    )}
                  </div>
                )}
                {canManage &&
                  ['CONFIRMED', 'PREPARING', 'READY_FOR_PICKUP'].includes(order.status) && (
                    <div className="detail-section order-change-panel" id="order-change">
                      <h3>Khách muốn đổi size trước khi nhận</h3>
                      <p>
                        Biến thể đang giữ: <strong>{firstItem?.variant}</strong>. Mã bộ hiện tại chỉ
                        được thay sau khi kiểm tra lịch và báo giá lại.
                      </p>
                      <SelectField
                        label="Biến thể khách muốn đổi sang"
                        value={proposedVariant}
                        onChange={(event) => setProposedVariant(event.target.value)}
                      >
                        <option value="">Chọn biến thể cần kiểm tra</option>
                        {variantChoices
                          .filter((value) => value !== firstItem?.variant)
                          .map((value) => (
                            <option key={value}>{value}</option>
                          ))}
                      </SelectField>
                      {variantValid && (
                        <Feedback tone="info" title="Chưa đổi bộ hoặc giá của đơn">
                          Cần kiểm tra bộ đúng size tại {order.branch}, xung đột lịch và chênh lệch
                          giá/cọc trước khi xác nhận. Đây là lựa chọn xem trước, chưa được lưu.
                        </Feedback>
                      )}
                    </div>
                  )}
                <div className="detail-section history">
                  <h3>Lịch sử và ghi chú</h3>
                  <p>{order.note}</p>
                  <ol>
                    {order.history.map((entry) => (
                      <li key={entry}>{entry}</li>
                    ))}
                  </ol>
                </div>
              </>
            ) : (
              <EmptyState title="Chọn một đơn để xem chi tiết" />
            )}
          </section>
        </div>
      )}
      {dialog === 'confirm' && order && (
        <ConfirmDialog
          title={`Xác nhận ${order.id}`}
          confirmText={`Xác nhận và gán ${order.items.length} bộ`}
          onConfirm={() => {
            void confirm();
          }}
          onClose={() => setDialog(null)}
          loading={busy}
        >
          <p>
            Kiểm tra trước khi lưu: {order.items.length} bộ · {selectedUnits.join(', ')} · nhận{' '}
            {order.pickup}.
          </p>
          <p>
            Giá thuê và cọc giữ theo snapshot của đơn. Xung đột phiên bản hoặc lịch sẽ được hiển thị
            ngay tại workspace.
          </p>
        </ConfirmDialog>
      )}
      {(dialog === 'reject' || dialog === 'cancel') && (
        <ConfirmDialog
          title={dialog === 'reject' ? 'Từ chối yêu cầu' : 'Hủy đơn'}
          confirmText="Lưu lý do vào bản xem trước"
          onConfirm={() => {
            void previewDecision();
          }}
          onClose={() => setDialog(null)}
          danger
        >
          <p>
            Thao tác ảnh hưởng đến trạng thái đơn, bộ đã gán và tiền nếu có. Bản demo chỉ cho xem
            trước, chưa có API xử lý.
          </p>
          <TextAreaField
            label="Lý do bắt buộc"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
          />
        </ConfirmDialog>
      )}
    </div>
  );
}
