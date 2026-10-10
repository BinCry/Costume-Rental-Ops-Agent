import { useState } from 'react';
import type { Navigate } from '../App';
import { Button, Feedback, Field, SelectField, TextAreaField, StatusLabel } from '../components/ui';
import {
  BarcodeLookup,
  BranchSelector,
  FilterBar,
  InlineIssue,
  KeyFacts,
  PageHeading,
  Panel,
  SearchField,
  StateGate,
  Timeline,
  UnitDetailPanel,
} from '../components/studio';
import { blockTypeLabels, conditionLabels, unitStatusLabels } from '../components/statusLabels';
import { useFixtureResource } from '../components/useFixtureResource';
import { useMobileDetailReveal } from '../components/useMobileDetailReveal';
import {
  studioAdapter,
  type Transfer,
  type TransferStatus,
  type Unit,
  type UnitBlock,
} from '../fixtures/studio';
import type { DemoScenario } from '../fixtures/types';

const transferStatus: Record<TransferStatus, string> = {
  REQUESTED: 'Chờ duyệt',
  APPROVED: 'Đã duyệt',
  IN_TRANSIT: 'Đang vận chuyển',
  RECEIVED: 'Đã nhận đủ',
  REJECTED: 'Từ chối',
  CANCELLED: 'Đã hủy',
};

export function InventoryPage({
  scenario,
  branch,
  go,
  canManage = true,
}: {
  scenario: DemoScenario;
  branch: string;
  go: Navigate;
  canManage?: boolean;
}) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.units);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('Tất cả');
  const [selected, setSelected] = useState<Unit>();
  const [blockType, setBlockType] = useState<UnitBlock['type']>('CLEANING');
  const [from, setFrom] = useState('2026-10-03T09:00');
  const [until, setUntil] = useState('2026-10-04T18:00');
  const [reason, setReason] = useState('');
  const [issue, setIssue] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const { detailRef, revealDetail } = useMobileDetailReveal<HTMLDivElement>();
  const addBlock = async () => {
    if (!selected || !reason.trim() || until <= from) {
      setIssue('Nhập lý do và khoảng block hợp lệ.');
      return;
    }
    setBusy(true);
    setIssue('');
    setNotice('');
    try {
      setSelected(
        await studioAdapter.addBlock(
          selected.barcode,
          { type: blockType, from, until, reason, status: 'PLANNED' },
          scenario,
        ),
      );
      retry();
      setReason('');
      setNotice(
        `Đã tạo block ${blockTypeLabels[blockType]} cho ${selected.barcode} trong fixture.`,
      );
    } catch (e) {
      setIssue(e instanceof Error ? e.message : 'Không tạo được block.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Kho chưa có bộ trang phục"
    >
      {(units) => {
        const visible = units.filter(
          (u) =>
            u.branch === branch &&
            (filter === 'Tất cả' || u.status === filter) &&
            `${u.barcode} ${u.model} ${u.variant}`.toLowerCase().includes(search.toLowerCase()),
        );
        return (
          <div className="page">
            <PageHeading
              eyebrow="KHO / BỘ TRANG PHỤC"
              title="Kho theo barcode"
              description="Trạng thái vận hành và khả dụng theo kỳ là hai thông tin riêng."
              action={
                canManage ? (
                  <Button variant="secondary" onClick={() => go('transfers')}>
                    Phiếu điều chuyển →
                  </Button>
                ) : undefined
              }
            />
            <div className="feature-two-column">
              <div>
                <Panel title="Tra cứu bộ">
                  <BarcodeLookup
                    branch={branch}
                    scenario={scenario}
                    onFound={(unit) => {
                      setSelected(unit);
                      revealDetail();
                    }}
                    onError={() => setSelected(undefined)}
                  />
                  <FilterBar>
                    <SearchField label="Tìm barcode hoặc mẫu" value={search} onChange={setSearch} />
                    <SelectField
                      label="Trạng thái vận hành"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option>Tất cả</option>
                      {Object.entries(unitStatusLabels).map(([code, label]) => (
                        <option value={code} key={code}>
                          {label}
                        </option>
                      ))}
                    </SelectField>
                  </FilterBar>
                </Panel>
                <Panel title={`${visible.length} bộ tại ${branch}`}>
                  <div className="responsive-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Barcode</th>
                          <th>Mẫu / biến thể</th>
                          <th>Chi nhánh</th>
                          <th>Vận hành</th>
                          <th>Khả dụng kỳ mẫu</th>
                          <th>Block</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((u) => (
                          <tr key={u.barcode}>
                            <td>
                              <button
                                className="text-link"
                                onClick={() => {
                                  setSelected(u);
                                  revealDetail();
                                }}
                              >
                                {u.barcode}
                              </button>
                            </td>
                            <td>
                              {u.model}
                              <small>{u.variant}</small>
                            </td>
                            <td>{u.branch}</td>
                            <td>
                              <StatusLabel
                                text={unitStatusLabels[u.status]}
                                tone={
                                  u.status === 'READY'
                                    ? 'success'
                                    : u.status === 'REPAIR'
                                      ? 'danger'
                                      : 'warning'
                                }
                              />
                            </td>
                            <td>{u.available ? 'Có thể kiểm tra' : 'Không khả dụng'}</td>
                            <td>{u.blocks.filter((b) => b.status !== 'COMPLETED').length}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!visible.length && <p className="muted">Không có bộ phù hợp bộ lọc.</p>}
                </Panel>
              </div>
              <div ref={detailRef} tabIndex={-1} role="region" aria-label="Chi tiết bộ đang chọn">
                {selected ? (
                  <>
                    <UnitDetailPanel unit={selected} />
                    {canManage && (
                      <Panel title="Tạo block cho bộ">
                        <p className="muted">
                          Fixture hỗ trợ vệ sinh, sửa chữa và kiểm tra. Việc block có thể ảnh hưởng
                          lịch còn bộ.
                        </p>
                        <SelectField
                          label="Loại block"
                          value={blockType}
                          onChange={(e) => setBlockType(e.target.value as UnitBlock['type'])}
                        >
                          <option value="CLEANING">Vệ sinh</option>
                          <option value="REPAIR">Sửa chữa</option>
                          <option value="INSPECTION">Kiểm tra</option>
                        </SelectField>
                        <div className="feature-filters">
                          <Field
                            type="datetime-local"
                            label="Từ"
                            value={from}
                            onChange={(e) => setFrom(e.target.value)}
                          />
                          <Field
                            type="datetime-local"
                            label="Đến"
                            value={until}
                            onChange={(e) => setUntil(e.target.value)}
                          />
                        </div>
                        <TextAreaField
                          label="Lý do"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                        />
                        <Button loading={busy} onClick={() => void addBlock()}>
                          Tạo block fixture
                        </Button>
                        <InlineIssue
                          text={issue}
                          conflict={scenario === 'conflict' || scenario === 'version'}
                        />
                        {notice && (
                          <Feedback tone="success" title="Đã lưu block">
                            {notice}
                          </Feedback>
                        )}
                      </Panel>
                    )}
                  </>
                ) : (
                  <Panel title="Chọn một bộ">
                    <p className="muted">Chọn dòng hoặc quét barcode để xem block và lịch sử bộ.</p>
                  </Panel>
                )}
              </div>
            </div>
          </div>
        );
      }}
    </StateGate>
  );
}

export function TransfersPage({ scenario, branch }: { scenario: DemoScenario; branch: string }) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.transfers);
  const [selected, setSelected] = useState('DC-001');
  const [from, setFrom] = useState(branch);
  const [to, setTo] = useState(
    branch === 'Chi nhánh Quận 1' ? 'Chi nhánh Thủ Đức' : 'Chi nhánh Quận 1',
  );
  const [unitCode, setUnitCode] = useState('BC-012');
  const [note, setNote] = useState('');
  const [checks, setChecks] = useState<Record<string, string>>({});
  const [reason, setReason] = useState('');
  const [issue, setIssue] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const { detailRef, revealDetail } = useMobileDetailReveal<HTMLDivElement>();
  const save = async (value: Transfer) => {
    setBusy(true);
    setIssue('');
    setNotice('');
    try {
      const result = await studioAdapter.saveTransfer(value, scenario);
      setSelected(result.code);
      revealDetail();
      setNote('');
      setNotice(`Đã tạo ${result.code}; chờ duyệt trước khi xuất bộ.`);
      retry();
    } catch (e) {
      setIssue(e instanceof Error ? e.message : 'Không lưu được phiếu.');
    } finally {
      setBusy(false);
    }
  };
  const advance = async (transfer: Transfer, next: TransferStatus) => {
    setBusy(true);
    setIssue('');
    setNotice('');
    try {
      const result = await studioAdapter.advanceTransfer(
        transfer.code,
        next,
        Object.entries(checks).map(([barcode, grade]) => ({ barcode, in: grade })),
        reason,
        scenario,
      );
      setNotice(
        next === 'RECEIVED'
          ? `Đã nhận ${result.units.filter((item) => item.received).length}/${result.units.length} bộ. ${result.status === 'RECEIVED' ? 'Phiếu đã nhận đủ.' : 'Các bộ còn lại vẫn đang vận chuyển.'}`
          : `Phiếu ${transfer.code} đã chuyển sang ${transferStatus[next]}.`,
      );
      setChecks({});
      retry();
    } catch (e) {
      setIssue(e instanceof Error ? e.message : 'Không đổi được trạng thái.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Chưa có phiếu điều chuyển"
    >
      {(transfers) => {
        const current = transfers.find((t) => t.code === selected) ?? transfers[0];
        return (
          <div className="page">
            <PageHeading
              eyebrow="KHO / ĐIỀU CHUYỂN"
              title="Điều chuyển chi nhánh"
              description="Yêu cầu → duyệt → xuất kho → kiểm từng bộ khi nhận. Bộ chỉ đổi chi nhánh sau bước nhận."
            />
            <div className="feature-two-column">
              <div>
                <Panel title="Tạo yêu cầu">
                  <div className="feature-filters">
                    <BranchSelector
                      label="Chi nhánh xuất"
                      value={from}
                      onChange={(v) => {
                        setFrom(v);
                        setTo(v === 'Chi nhánh Quận 1' ? 'Chi nhánh Thủ Đức' : 'Chi nhánh Quận 1');
                      }}
                    />
                    <BranchSelector label="Chi nhánh nhận" value={to} onChange={setTo} />
                    <Field
                      label="Barcode bộ sẵn sàng"
                      value={unitCode}
                      onChange={(e) => setUnitCode(e.target.value.toUpperCase())}
                    />
                  </div>
                  <TextAreaField
                    label="Lý do điều chuyển"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <Button
                    onClick={() => {
                      if (from === to || !note.trim()) {
                        setIssue('Chọn hai chi nhánh khác nhau và nhập lý do.');
                        return;
                      }
                      void save({
                        code: `DC-DEMO-${transfers.length + 1}`,
                        from,
                        to,
                        status: 'REQUESTED',
                        units: [{ barcode: unitCode }],
                        note,
                        version: 1,
                        history: ['03/10 · Tạo yêu cầu fixture'],
                      });
                    }}
                  >
                    Tạo phiếu yêu cầu
                  </Button>
                </Panel>
                <Panel title="Phiếu điều chuyển">
                  <div className="feature-card-list">
                    {transfers.map((t) => (
                      <button
                        className={`feature-list-row selectable ${current.code === t.code ? 'selected' : ''}`}
                        key={t.code}
                        onClick={() => {
                          setSelected(t.code);
                          setChecks({});
                          setNotice('');
                          revealDetail();
                        }}
                      >
                        <strong>
                          {t.code} · {transferStatus[t.status]}
                        </strong>
                        <span>
                          {t.from} → {t.to}
                        </span>
                        <small>{t.units.map((u) => u.barcode).join(', ')}</small>
                      </button>
                    ))}
                  </div>
                </Panel>
              </div>
              <div
                ref={detailRef}
                tabIndex={-1}
                role="region"
                aria-label="Chi tiết phiếu điều chuyển đang chọn"
              >
                <Panel title={current.code}>
                  <StatusLabel
                    text={transferStatus[current.status]}
                    tone={
                      current.status === 'RECEIVED'
                        ? 'success'
                        : current.status === 'REJECTED' || current.status === 'CANCELLED'
                          ? 'danger'
                          : 'warning'
                    }
                  />
                  <KeyFacts
                    rows={[
                      { label: 'Từ', value: current.from },
                      { label: 'Đến', value: current.to },
                      {
                        label: 'Đã nhận',
                        value: `${current.units.filter((item) => item.received).length}/${current.units.length} bộ`,
                      },
                      { label: 'Ghi chú', value: current.note },
                      { label: 'Phiên bản', value: current.version },
                    ]}
                  />
                  <h3>Kiểm từng bộ</h3>
                  {current.units.map((u) => (
                    <div className="feature-list-row" key={u.barcode}>
                      <strong>{u.barcode}</strong>
                      <span>
                        Tình trạng xuất: {u.out ? (conditionLabels[u.out] ?? u.out) : 'Chưa xuất'} ·
                        Nhận: {u.received ?? 'Chưa nhận'}
                      </span>
                      {current.status === 'IN_TRANSIT' && !u.received ? (
                        <SelectField
                          label={`Tình trạng nhận ${u.barcode}`}
                          value={checks[u.barcode] ?? ''}
                          onChange={(e) => setChecks({ ...checks, [u.barcode]: e.target.value })}
                        >
                          <option value="">Chưa kiểm</option>
                          <option value="GOOD">Tốt</option>
                          <option value="FAIR">Cần theo dõi</option>
                          <option value="DAMAGED">Hư hỏng</option>
                        </SelectField>
                      ) : (
                        <small>
                          Tình trạng nhận: {u.in ? (conditionLabels[u.in] ?? u.in) : '—'}
                        </small>
                      )}
                    </div>
                  ))}
                  <div className="feature-actions">
                    {current.status === 'REQUESTED' && (
                      <Button disabled={busy} onClick={() => void advance(current, 'APPROVED')}>
                        Duyệt điều chuyển
                      </Button>
                    )}
                    {current.status === 'APPROVED' && (
                      <Button disabled={busy} onClick={() => void advance(current, 'IN_TRANSIT')}>
                        Kiểm và xuất bộ
                      </Button>
                    )}
                    {current.status === 'IN_TRANSIT' && (
                      <Button
                        disabled={
                          busy || !current.units.some((u) => !u.received && checks[u.barcode])
                        }
                        onClick={() => void advance(current, 'RECEIVED')}
                      >
                        Xác nhận nhận{' '}
                        {current.units.filter((u) => !u.received && checks[u.barcode]).length} bộ
                      </Button>
                    )}
                  </div>
                  {current.status === 'REQUESTED' && (
                    <div className="destructive-area">
                      <TextAreaField
                        label="Lý do từ chối hoặc hủy"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                      <div className="feature-actions">
                        <Button
                          variant="danger"
                          disabled={!reason.trim() || busy}
                          onClick={() => void advance(current, 'REJECTED')}
                        >
                          Từ chối
                        </Button>
                        <Button
                          variant="quiet"
                          disabled={!reason.trim() || busy}
                          onClick={() => void advance(current, 'CANCELLED')}
                        >
                          Hủy phiếu
                        </Button>
                      </div>
                    </div>
                  )}
                  {current.status === 'APPROVED' && (
                    <div className="destructive-area">
                      <Button variant="quiet" onClick={() => void advance(current, 'CANCELLED')}>
                        Hủy trước khi xuất
                      </Button>
                    </div>
                  )}
                  <h3>Lịch sử</h3>
                  <Timeline items={current.history} />
                </Panel>
                <InlineIssue
                  text={issue}
                  conflict={scenario === 'conflict' || scenario === 'version'}
                />
                {notice && (
                  <Feedback tone="success" title="Đã cập nhật phiếu">
                    {notice}
                  </Feedback>
                )}
                {scenario === 'unitBlocked' && (
                  <Feedback tone="warning" title="Bộ bị block">
                    Bộ đang vệ sinh hoặc sửa chữa không được xuất.
                  </Feedback>
                )}
              </div>
            </div>
          </div>
        );
      }}
    </StateGate>
  );
}
