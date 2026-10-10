import { useState } from 'react';
import {
  Button,
  ConfirmDialog,
  Feedback,
  Field,
  SelectField,
  TextAreaField,
  StatusLabel,
} from '../components/ui';
import { money } from '../components/support';
import {
  BranchSelector,
  FilterBar,
  InlineIssue,
  KeyFacts,
  PageHeading,
  Panel,
  PermissionGroup,
  SearchField,
  StateGate,
  Timeline,
} from '../components/studio';
import { useFixtureResource } from '../components/useFixtureResource';
import { useMobileDetailReveal } from '../components/useMobileDetailReveal';
import {
  permissions,
  studioAdapter,
  type Branch,
  type CostumeDetail,
  type Employee,
  type Policy,
  type Variant,
} from '../fixtures/studio';
import type { DemoScenario } from '../fixtures/types';

const issueText = (error: unknown) =>
  error instanceof Error ? error.message : 'Thao tác chưa hoàn tất.';
const accountLabels: Record<Employee['accountStatus'], string> = {
  PENDING: 'Chờ kích hoạt',
  ACTIVE: 'Đang hoạt động',
  LOCKED: 'Bị khóa',
  INACTIVE: 'Ngừng sử dụng',
};
const employmentLabels: Record<Employee['employmentStatus'], string> = {
  ACTIVE: 'Đang làm việc',
  ON_LEAVE: 'Tạm nghỉ',
  TERMINATED: 'Đã nghỉ',
};
const staffRoleLabels: Record<string, string> = {
  SALES_STAFF: 'Nhân viên bán hàng',
  INVENTORY_STAFF: 'Nhân viên kho',
};

export function CatalogAdminPage({ scenario }: { scenario: DemoScenario }) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.details);
  const [selected, setSelected] = useState('ao-dai-lina');
  const [model, setModel] = useState<CostumeDetail>();
  const [variant, setVariant] = useState<Variant>();
  const [issue, setIssue] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const saveModel = async () => {
    if (!model?.name.trim()) {
      setIssue('Nhập tên mẫu.');
      return;
    }
    setBusy(true);
    setIssue('');
    try {
      await studioAdapter.saveModel(model, scenario);
      setNotice('Đã lưu mẫu trong fixture.');
      retry();
    } catch (e) {
      setIssue(issueText(e));
    } finally {
      setBusy(false);
    }
  };
  const saveVariant = async () => {
    if (
      !variant?.size ||
      !variant.color ||
      variant.price < 0 ||
      variant.deposit < 0 ||
      variant.replacement < 0
    ) {
      setIssue('Kiểm tra size, màu và các khoản tiền.');
      return;
    }
    setBusy(true);
    setIssue('');
    try {
      await studioAdapter.saveVariant(variant, scenario);
      setNotice('Đã lưu biến thể và giá hiện hành trong fixture. Đơn cũ giữ snapshot.');
      retry();
    } catch (e) {
      setIssue(issueText(e));
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
      emptyTitle="Chưa có mẫu trang phục"
    >
      {(items) => {
        const current =
          model?.id === selected ? model : (items.find((i) => i.id === selected) ?? items[0]);
        const editing = model?.id === current.id ? model : current;
        return (
          <div className="page">
            <PageHeading
              eyebrow="QUẢN TRỊ / DANH MỤC"
              title="Mẫu, biến thể & giá"
              description="Giá thuê/ngày, cọc và giá thay thế được đặt trên biến thể, dùng chung toàn chuỗi."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    const id = `mau-demo-${items.length + 1}`;
                    setSelected(id);
                    setModel({
                      id,
                      name: '',
                      category: 'Trang phục',
                      description: '',
                      material: '',
                      accessories: [],
                      imagePosition: 'missing',
                      variants: [],
                    });
                    setVariant(undefined);
                  }}
                >
                  + Tạo mẫu
                </Button>
              }
            />
            <div className="feature-two-column">
              <div>
                <Panel title="Danh mục mẫu">
                  <div className="feature-card-list">
                    {items.map((item) => (
                      <button
                        className={`feature-list-row selectable ${selected === item.id ? 'selected' : ''}`}
                        key={item.id}
                        onClick={() => {
                          setSelected(item.id);
                          setModel(undefined);
                          setVariant(undefined);
                        }}
                      >
                        <strong>{item.name}</strong>
                        <span>
                          {item.category} · {item.variants.length} biến thể
                        </span>
                        <small>{item.id}</small>
                      </button>
                    ))}
                  </div>
                </Panel>
                <Panel title="Thông tin mẫu">
                  <div className="feature-filters">
                    <Field
                      label="Tên mẫu"
                      value={editing.name}
                      onChange={(e) => setModel({ ...editing, name: e.target.value })}
                    />
                    <Field
                      label="Loại trang phục"
                      value={editing.category}
                      onChange={(e) => setModel({ ...editing, category: e.target.value })}
                    />
                    <Field
                      label="Chất liệu"
                      value={editing.material}
                      onChange={(e) => setModel({ ...editing, material: e.target.value })}
                    />
                  </div>
                  <TextAreaField
                    label="Mô tả"
                    value={editing.description}
                    onChange={(e) => setModel({ ...editing, description: e.target.value })}
                  />
                  <Field
                    label="Phụ kiện (cách nhau bằng dấu phẩy)"
                    value={editing.accessories.join(', ')}
                    onChange={(e) =>
                      setModel({
                        ...editing,
                        accessories: e.target.value
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                  />
                  <p className="muted small-note">
                    Ảnh hiện dùng media fixture. Tải ảnh, sắp xếp và lưu media phụ thuộc dịch vụ lưu
                    trữ/backend.
                  </p>
                  <Button loading={busy} onClick={() => void saveModel()}>
                    Lưu mẫu
                  </Button>
                </Panel>
              </div>
              <div>
                <Panel
                  title="Biến thể & giá"
                  action={
                    <Button
                      variant="quiet"
                      onClick={() =>
                        setVariant({
                          code: `${current.id.toUpperCase()}-NEW`,
                          modelId: current.id,
                          size: '',
                          color: '',
                          fit: '',
                          price: 0,
                          deposit: 0,
                          replacement: 0,
                        })
                      }
                    >
                      + Biến thể
                    </Button>
                  }
                >
                  <div className="variant-pills">
                    {current.variants.map((v) => (
                      <button
                        key={v.code}
                        className={variant?.code === v.code ? 'active' : ''}
                        onClick={() => setVariant(v)}
                      >
                        {v.size} · {v.color}
                      </button>
                    ))}
                  </div>
                  {variant ? (
                    <div className="stack-form">
                      <p className="muted">
                        {variant.code} · biến thể {variant.modelId}
                      </p>
                      <div className="feature-filters">
                        <Field
                          label="Size"
                          value={variant.size}
                          onChange={(e) => setVariant({ ...variant, size: e.target.value })}
                        />
                        <Field
                          label="Màu"
                          value={variant.color}
                          onChange={(e) => setVariant({ ...variant, color: e.target.value })}
                        />
                        <Field
                          label="Edition"
                          value={variant.edition ?? ''}
                          onChange={(e) => setVariant({ ...variant, edition: e.target.value })}
                        />
                        <Field
                          type="number"
                          min="0"
                          label="Giá thuê / ngày (đ)"
                          value={variant.price}
                          onChange={(e) =>
                            setVariant({ ...variant, price: Number(e.target.value) })
                          }
                        />
                        <Field
                          type="number"
                          min="0"
                          label="Tiền cọc (đ)"
                          value={variant.deposit}
                          onChange={(e) =>
                            setVariant({ ...variant, deposit: Number(e.target.value) })
                          }
                        />
                        <Field
                          type="number"
                          min="0"
                          label="Giá thay thế (đ)"
                          value={variant.replacement}
                          onChange={(e) =>
                            setVariant({ ...variant, replacement: Number(e.target.value) })
                          }
                        />
                      </div>
                      <TextAreaField
                        label="Ghi chú phom dáng"
                        value={variant.fit}
                        onChange={(e) => setVariant({ ...variant, fit: e.target.value })}
                      />
                      <Feedback tone="warning" title="Giá snapshot trên đơn">
                        Sửa giá hiện hành không thay đổi giá, cọc hoặc số ngày trên đơn đã lập.
                      </Feedback>
                      <Button loading={busy} onClick={() => void saveVariant()}>
                        Lưu biến thể & giá
                      </Button>
                    </div>
                  ) : (
                    <p className="muted">Chọn biến thể để sửa giá hoặc tạo mới.</p>
                  )}
                </Panel>
                <InlineIssue text={issue} conflict={scenario === 'version'} />
                {notice && (
                  <Feedback tone="success" title="Đã lưu">
                    {notice}
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

export function EmployeesPage({ scenario }: { scenario: DemoScenario }) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.employees);
  const [selected, setSelected] = useState('NV-001');
  const [editing, setEditing] = useState<Employee>();
  const [issue, setIssue] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [assignmentBranch, setAssignmentBranch] = useState('Chi nhánh Quận 1');
  const [assignmentRole, setAssignmentRole] = useState('SALES_STAFF');
  const [pendingEmployee, setPendingEmployee] = useState('');
  const { detailRef, revealDetail } = useMobileDetailReveal<HTMLDivElement>();
  const save = async () => {
    if (!editing?.name.trim() || !editing.email.includes('@')) {
      setIssue('Nhập tên và email hợp lệ.');
      return;
    }
    setBusy(true);
    setIssue('');
    try {
      await studioAdapter.saveEmployee(editing, scenario);
      setNotice('Đã lưu nhân viên và phân công trong fixture.');
      setEditing(undefined);
      retry();
    } catch (e) {
      setIssue(issueText(e));
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
      emptyTitle="Chưa có nhân viên"
    >
      {(items) => {
        const current = items.find((x) => x.code === selected) ?? items[0];
        const person = editing?.code === selected ? editing : current;
        return (
          <div className="page">
            <PageHeading
              eyebrow="QUẢN TRỊ / NHÂN SỰ"
              title="Nhân viên & phân công"
              description="Thông tin nhân viên tách khỏi role được gán tại từng chi nhánh."
              action={
                <Button
                  variant="secondary"
                  disabled={!!editing}
                  onClick={() => {
                    const code = `NV-DEMO-${items.length + 1}`;
                    setSelected(code);
                    setEditing({
                      code,
                      name: '',
                      email: '',
                      accountStatus: 'PENDING',
                      employmentStatus: 'ACTIVE',
                      assignments: [],
                    });
                    revealDetail();
                  }}
                >
                  + Tạo nhân viên chờ kích hoạt
                </Button>
              }
            />
            <div className="feature-two-column">
              <Panel title="Danh sách nhân viên">
                <SearchField label="Tìm tên hoặc email" value={search} onChange={setSearch} />
                <div className="feature-card-list">
                  {items
                    .filter((x) =>
                      `${x.name} ${x.email}`.toLowerCase().includes(search.toLowerCase()),
                    )
                    .map((x) => (
                      <button
                        className={`feature-list-row selectable ${person.code === x.code ? 'selected' : ''}`}
                        key={x.code}
                        onClick={() => {
                          if (editing && selected !== x.code) {
                            setPendingEmployee(x.code);
                            return;
                          }
                          setSelected(x.code);
                          setEditing(undefined);
                          revealDetail();
                        }}
                      >
                        <strong>
                          {x.name} · {x.code}
                        </strong>
                        <span>{x.email}</span>
                        <small>
                          Tài khoản: {accountLabels[x.accountStatus]} · Việc làm:{' '}
                          {employmentLabels[x.employmentStatus]}
                        </small>
                      </button>
                    ))}
                </div>
              </Panel>
              <div
                ref={detailRef}
                tabIndex={-1}
                role="region"
                aria-label="Hồ sơ nhân viên đang chọn"
              >
                <Panel title={`Hồ sơ ${person.code}`}>
                  <div className="feature-filters">
                    <Field
                      label="Họ tên"
                      value={person.name}
                      onChange={(e) => setEditing({ ...person, name: e.target.value })}
                    />
                    <Field
                      label="Email Google dự kiến"
                      value={person.email}
                      onChange={(e) => setEditing({ ...person, email: e.target.value })}
                    />
                    <SelectField
                      label="Trạng thái tài khoản"
                      value={person.accountStatus}
                      onChange={(e) =>
                        setEditing({
                          ...person,
                          accountStatus: e.target.value as Employee['accountStatus'],
                        })
                      }
                    >
                      {(['PENDING', 'ACTIVE', 'LOCKED', 'INACTIVE'] as const).map((x) => (
                        <option value={x} key={x}>
                          {accountLabels[x]}
                        </option>
                      ))}
                    </SelectField>
                    <SelectField
                      label="Trạng thái làm việc"
                      value={person.employmentStatus}
                      onChange={(e) =>
                        setEditing({
                          ...person,
                          employmentStatus: e.target.value as Employee['employmentStatus'],
                        })
                      }
                    >
                      {(['ACTIVE', 'ON_LEAVE', 'TERMINATED'] as const).map((x) => (
                        <option value={x} key={x}>
                          {employmentLabels[x]}
                        </option>
                      ))}
                    </SelectField>
                  </div>
                  <h3>Vai trò theo chi nhánh</h3>
                  {person.assignments.map((a, i) => (
                    <div className="feature-list-row" key={i}>
                      <strong>{a.branch}</strong>
                      <span>{staffRoleLabels[a.roleCode] ?? a.roleCode}</span>
                      <Button
                        variant="quiet"
                        onClick={() =>
                          setEditing({
                            ...person,
                            assignments: person.assignments.filter((_, n) => n !== i),
                          })
                        }
                      >
                        Bỏ phân công
                      </Button>
                    </div>
                  ))}
                  <div className="feature-filters">
                    <BranchSelector
                      label="Chi nhánh phân công"
                      value={assignmentBranch}
                      onChange={setAssignmentBranch}
                    />
                    <SelectField
                      label="Thêm role tại chi nhánh"
                      value={assignmentRole}
                      onChange={(event) => setAssignmentRole(event.target.value)}
                    >
                      <option value="SALES_STAFF">Nhân viên bán hàng</option>
                      <option value="INVENTORY_STAFF">Nhân viên kho</option>
                    </SelectField>
                  </div>
                  <Button
                    variant="secondary"
                    disabled={person.assignments.some(
                      (entry) =>
                        entry.branch === assignmentBranch && entry.roleCode === assignmentRole,
                    )}
                    onClick={() =>
                      setEditing({
                        ...person,
                        assignments: [
                          ...person.assignments,
                          { branch: assignmentBranch, roleCode: assignmentRole },
                        ],
                      })
                    }
                  >
                    {person.assignments.some(
                      (entry) =>
                        entry.branch === assignmentBranch && entry.roleCode === assignmentRole,
                    )
                      ? 'Vai trò đã được gán'
                      : '+ Gán role mẫu'}
                  </Button>
                  <p className="muted small-note">
                    Quyền thực tế được backend tính từ các role của nhân viên ở chi nhánh đang chọn.
                  </p>
                  <div className="feature-actions">
                    <Button disabled={!editing} loading={busy} onClick={() => void save()}>
                      Lưu hồ sơ & phân công
                    </Button>
                    {editing && (
                      <Button variant="secondary" onClick={() => setEditing(undefined)}>
                        Bỏ thay đổi
                      </Button>
                    )}
                  </div>
                  {editing && (
                    <p className="field-hint" role="status">
                      Có thay đổi chưa lưu trong hồ sơ này.
                    </p>
                  )}
                </Panel>
                <InlineIssue text={issue} />
                {notice && (
                  <Feedback tone="success" title="Đã lưu">
                    {notice}
                  </Feedback>
                )}
              </div>
            </div>
            {pendingEmployee && (
              <ConfirmDialog
                title="Chưa lưu thay đổi nhân viên"
                confirmText="Bỏ thay đổi và mở hồ sơ khác"
                onClose={() => setPendingEmployee('')}
                onConfirm={() => {
                  setSelected(pendingEmployee);
                  setEditing(undefined);
                  setPendingEmployee('');
                  revealDetail();
                }}
              >
                <p>Thông tin và phân công đang sửa sẽ mất. Bạn có thể quay lại để lưu trước.</p>
              </ConfirmDialog>
            )}
          </div>
        );
      }}
    </StateGate>
  );
}

export function BranchesPage({ scenario }: { scenario: DemoScenario }) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.branches);
  const [selected, setSelected] = useState('HCM-Q1');
  const [editing, setEditing] = useState<Branch>();
  const [issue, setIssue] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Chưa có chi nhánh"
    >
      {(items) => {
        const existingBranch = items.find((x) => x.code === selected);
        const current = existingBranch ?? items[0];
        const branch = editing?.code === selected ? editing : current;
        const obligations = existingBranch
          ? studioAdapter.branchObligations(existingBranch.name)
          : { orders: 0, units: 0, transfers: 0 };
        const hasObligations = obligations.orders + obligations.units + obligations.transfers > 0;
        const closingExisting = existingBranch?.status === 'ACTIVE' && branch.status === 'INACTIVE';
        return (
          <div className="page">
            <PageHeading
              eyebrow="QUẢN TRỊ / CHI NHÁNH"
              title="Chi nhánh"
              description="Mỗi bộ có chi nhánh hiện tại; nhận/trả cùng chi nhánh trong đơn thuê."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    const code = `CN-DEMO-${items.length + 1}`;
                    setSelected(code);
                    setEditing({
                      code,
                      name: '',
                      address: '',
                      timezone: 'Asia/Ho_Chi_Minh',
                      status: 'ACTIVE',
                    });
                  }}
                >
                  + Thêm chi nhánh
                </Button>
              }
            />
            <div className="feature-two-column">
              <Panel title="Danh sách chi nhánh">
                <div className="feature-card-list">
                  {items.map((x) => (
                    <button
                      className={`feature-list-row selectable ${selected === x.code ? 'selected' : ''}`}
                      key={x.code}
                      onClick={() => {
                        setSelected(x.code);
                        setEditing(undefined);
                      }}
                    >
                      <strong>{x.name}</strong>
                      <span>{x.address}</span>
                      <small>
                        {x.code} · {x.status}
                      </small>
                    </button>
                  ))}
                </div>
              </Panel>
              <Panel title={`Thông tin ${branch.code}`}>
                <div className="stack-form">
                  <Field
                    label="Tên chi nhánh"
                    value={branch.name}
                    onChange={(e) => setEditing({ ...branch, name: e.target.value })}
                  />
                  <Field
                    label="Địa chỉ"
                    value={branch.address}
                    onChange={(e) => setEditing({ ...branch, address: e.target.value })}
                  />
                  <Field
                    label="Timezone"
                    value={branch.timezone}
                    onChange={(e) => setEditing({ ...branch, timezone: e.target.value })}
                  />
                  <SelectField
                    label="Trạng thái"
                    value={branch.status}
                    onChange={(e) =>
                      setEditing({ ...branch, status: e.target.value as Branch['status'] })
                    }
                  >
                    <option value="ACTIVE">Đang hoạt động</option>
                    <option value="INACTIVE">Ngừng hoạt động</option>
                  </SelectField>
                  {closingExisting && (
                    <Feedback
                      tone={hasObligations ? 'warning' : 'info'}
                      title="Kiểm tra trước khi ngừng chi nhánh"
                    >
                      Trong fixture: {obligations.orders} đơn đang xử lý · {obligations.units} bộ
                      còn tại chi nhánh · {obligations.transfers} phiếu điều chuyển mở.
                      {hasObligations
                        ? ' Cần xử lý các nghĩa vụ này trước khi lưu trạng thái ngừng hoạt động.'
                        : ' Fixture không còn các nghĩa vụ trên. Backend vẫn phải kiểm tra khoản thu/hoàn và hồ sơ hỗ trợ trước khi chốt.'}
                    </Feedback>
                  )}
                  <Button
                    disabled={closingExisting && hasObligations}
                    loading={busy}
                    onClick={() => {
                      void (async () => {
                        if (!branch.name.trim()) {
                          setIssue('Nhập tên chi nhánh.');
                          return;
                        }
                        setBusy(true);
                        setIssue('');
                        try {
                          await studioAdapter.saveBranch(branch, scenario);
                          retry();
                        } catch (e) {
                          setIssue(issueText(e));
                        } finally {
                          setBusy(false);
                        }
                      })();
                    }}
                  >
                    Lưu chi nhánh
                  </Button>
                  <InlineIssue text={issue} />
                </div>
              </Panel>
            </div>
          </div>
        );
      }}
    </StateGate>
  );
}

export function RolesPage({ scenario }: { scenario: DemoScenario }) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.roles);
  const [selected, setSelected] = useState('SALES_STAFF');
  const [draft, setDraft] = useState<string[]>();
  const [issue, setIssue] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingRole, setPendingRole] = useState('');
  const [permissionSearch, setPermissionSearch] = useState('');
  const { detailRef, revealDetail } = useMobileDetailReveal<HTMLDivElement>();
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Chưa có vai trò"
    >
      {(roles) => {
        const role = roles.find((r) => r.code === selected) ?? roles[0];
        const checked = draft ?? role.permissions;
        const changed =
          checked.length !== role.permissions.length ||
          checked.some((code) => !role.permissions.includes(code));
        const addedPermissions = checked.filter((code) => !role.permissions.includes(code));
        const removedPermissions = role.permissions.filter((code) => !checked.includes(code));
        const groups = ['Đơn thuê', 'Giao / trả', 'Thanh toán', 'Kho', 'CRM', 'Quản trị'];
        return (
          <div className="page">
            <PageHeading
              eyebrow="QUẢN TRỊ / PHÂN QUYỀN"
              title="Quyền theo vai trò"
              description="Chọn một vai trò, tick mã quyền có sẵn. Scope thuộc định nghĩa quyền và không đổi tại màn hình này."
            />
            <div className={`role-layout ${changed ? 'has-unsaved-role' : ''}`}>
              <Panel title="Vai trò">
                <div className="feature-card-list">
                  {roles.map((r) => (
                    <button
                      className={`feature-list-row selectable ${role.code === r.code ? 'selected' : ''}`}
                      key={r.code}
                      onClick={() => {
                        if (changed && r.code !== role.code) {
                          setPendingRole(r.code);
                          return;
                        }
                        setSelected(r.code);
                        setDraft(undefined);
                        setIssue('');
                        revealDetail();
                      }}
                    >
                      <strong>{r.name}</strong>
                      <span>
                        {r.code} · {r.group}
                      </span>
                      <small>{r.permissions.length} quyền</small>
                    </button>
                  ))}
                </div>
              </Panel>
              <div
                ref={detailRef}
                tabIndex={-1}
                role="region"
                aria-label="Quyền của vai trò đang chọn"
              >
                <Panel title={role.name}>
                  <p className="muted">
                    Quyền được chọn áp dụng cho vai trò này. Phân công vai trò cho nhân viên theo
                    chi nhánh ở màn hình nhân sự.
                  </p>
                  <KeyFacts
                    rows={[
                      { label: 'Nhóm', value: role.group },
                      { label: 'Mã vai trò', value: role.code },
                      { label: 'Đã chọn', value: `${checked.length} mã quyền` },
                    ]}
                  />
                  <SearchField
                    label="Tìm quyền theo tên hoặc mã"
                    value={permissionSearch}
                    onChange={setPermissionSearch}
                  />
                </Panel>
                <div className="permission-groups">
                  {groups.map((group) => {
                    const matching = permissions.filter(
                      (p) =>
                        p.group === group &&
                        `${p.label} ${p.code} ${p.description}`
                          .toLocaleLowerCase('vi')
                          .includes(permissionSearch.toLocaleLowerCase('vi')),
                    );
                    return permissionSearch && !matching.length ? null : (
                      <PermissionGroup
                        title={group}
                        key={group}
                        permissions={matching}
                        selected={checked}
                        filtered={Boolean(permissionSearch)}
                        onToggle={(code) =>
                          setDraft(
                            checked.includes(code)
                              ? checked.filter((x) => x !== code)
                              : [...checked, code],
                          )
                        }
                        onSelectAll={() =>
                          setDraft([...new Set([...checked, ...matching.map((item) => item.code)])])
                        }
                        onClear={() =>
                          setDraft(
                            checked.filter((code) => !matching.some((item) => item.code === code)),
                          )
                        }
                      />
                    );
                  })}
                </div>
                {permissionSearch &&
                  !permissions.some((p) =>
                    `${p.label} ${p.code} ${p.description}`
                      .toLocaleLowerCase('vi')
                      .includes(permissionSearch.toLocaleLowerCase('vi')),
                  ) && <p className="muted">Không có quyền khớp từ khóa.</p>}
                {role.group === 'ADMIN' && changed && !checked.includes('rbac.manage.all') && (
                  <Feedback tone="warning" title="Vai trò quản trị sắp mất quyền sửa phân quyền">
                    Backend cần bảo vệ quản trị viên cuối cùng trước khi cho phép lưu thay đổi này.
                  </Feedback>
                )}
                {changed && (
                  <Panel title="Xem trước thay đổi quyền">
                    <p className="muted">
                      {addedPermissions.length} quyền được thêm · {removedPermissions.length} quyền
                      được bỏ.
                    </p>
                    {addedPermissions.map((code) => (
                      <p className="permission-change" key={`add-${code}`}>
                        <strong>Thêm</strong>{' '}
                        {permissions.find((item) => item.code === code)?.label ?? code}
                        <code>{code}</code>
                      </p>
                    ))}
                    {removedPermissions.map((code) => (
                      <p className="permission-change" key={`remove-${code}`}>
                        <strong>Bỏ</strong>{' '}
                        {permissions.find((item) => item.code === code)?.label ?? code}
                        <code>{code}</code>
                      </p>
                    ))}
                  </Panel>
                )}
                {changed && (
                  <div className="feature-actions role-save-bar" role="status">
                    <span>
                      Chưa lưu: +{addedPermissions.length} / −{removedPermissions.length} quyền
                    </span>
                    <Button
                      disabled={busy}
                      loading={busy}
                      onClick={() => {
                        void (async () => {
                          setBusy(true);
                          setIssue('');
                          try {
                            await studioAdapter.saveRole(
                              { ...role, permissions: checked },
                              scenario,
                            );
                            setDraft(undefined);
                            setNotice(
                              'Đã lưu quyền vào fixture. API sau này phải kiểm quyền mỗi thao tác.',
                            );
                            retry();
                          } catch (e) {
                            setIssue(issueText(e));
                          } finally {
                            setBusy(false);
                          }
                        })();
                      }}
                    >
                      Lưu quyền vai trò
                    </Button>
                    <Button variant="secondary" onClick={() => setDraft(undefined)}>
                      Bỏ thay đổi
                    </Button>
                  </div>
                )}
                <InlineIssue text={issue} conflict={scenario === 'version'} />
                {notice && (
                  <Feedback tone="success" title="Đã lưu">
                    {notice}
                  </Feedback>
                )}
              </div>
            </div>
            {pendingRole && (
              <ConfirmDialog
                title="Chưa lưu quyền vai trò"
                confirmText="Bỏ thay đổi và mở vai trò khác"
                onClose={() => setPendingRole('')}
                onConfirm={() => {
                  setSelected(pendingRole);
                  setDraft(undefined);
                  setPendingRole('');
                  revealDetail();
                }}
              >
                <p>Các checkbox vừa thay đổi sẽ mất. Bạn có thể quay lại để lưu trước.</p>
              </ConfirmDialog>
            )}
          </div>
        );
      }}
    </StateGate>
  );
}

export function PoliciesPage({ scenario }: { scenario: DemoScenario }) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.policies);
  const [selected, setSelected] = useState('POLICY-2025');
  const [draft, setDraft] = useState<Policy>();
  const [issue, setIssue] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Chưa có chính sách"
    >
      {(items) => {
        const policy = items.find((p) => p.code === selected) ?? items[0];
        return (
          <div className="page">
            <PageHeading
              eyebrow="QUẢN TRỊ / CHÍNH SÁCH"
              title="Phiên bản chính sách thuê"
              description="Đơn giữ snapshot chính sách tại thời điểm lập. Sửa bằng cách tạo phiên bản mới có thời điểm hiệu lực."
              action={
                <Button
                  variant="secondary"
                  onClick={() =>
                    setDraft({
                      ...policy,
                      code: `POLICY-DEMO-${items.length + 1}`,
                      from: '',
                      to: undefined,
                      reason: '',
                    })
                  }
                >
                  + Phiên bản mới
                </Button>
              }
            />
            <div className="feature-two-column">
              <Panel title="Lịch sử phiên bản">
                <div className="feature-card-list">
                  {items.map((p) => (
                    <button
                      className={`feature-list-row selectable ${selected === p.code ? 'selected' : ''}`}
                      key={p.code}
                      onClick={() => setSelected(p.code)}
                    >
                      <strong>{p.code}</strong>
                      <span>
                        {p.from} → {p.to ?? 'Hiện hành'}
                      </span>
                      <small>
                        {p.billingMode === 'ROLLING_24_HOURS' ? 'Chu kỳ 24 giờ' : 'Ngày lịch'}
                      </small>
                    </button>
                  ))}
                </div>
              </Panel>
              <div>
                <Panel title={policy.code}>
                  <StatusLabel
                    text={policy.to ? 'Lịch sử' : 'Đang hiệu lực theo fixture'}
                    tone={policy.to ? 'neutral' : 'success'}
                  />
                  <KeyFacts
                    rows={[
                      { label: 'Bắt đầu', value: policy.from },
                      { label: 'Kết thúc', value: policy.to ?? 'Chưa có' },
                      {
                        label: 'Đếm ngày',
                        value:
                          policy.billingMode === 'ROLLING_24_HOURS'
                            ? '24 giờ liên tục'
                            : 'Ngày lịch',
                      },
                      { label: 'Số ngày', value: `${policy.minDays}–${policy.maxDays}` },
                      { label: 'Báo giá hiệu lực', value: `${policy.quoteHours} giờ` },
                      { label: 'Hủy miễn phí trước', value: `${policy.cancelHours} giờ` },
                      { label: 'Lý do thay đổi', value: policy.reason },
                    ]}
                  />
                  <h3>Audit</h3>
                  <Timeline items={[`${policy.from} · Tạo ${policy.code}: ${policy.reason}`]} />
                </Panel>
                {draft && (
                  <Panel title="Tạo phiên bản fixture">
                    <div className="feature-filters">
                      <Field
                        label="Mã phiên bản"
                        value={draft.code}
                        onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                      />
                      <Field
                        type="date"
                        label="Ngày hiệu lực"
                        value={draft.from}
                        onChange={(e) => setDraft({ ...draft, from: e.target.value })}
                      />
                      <SelectField
                        label="Cách đếm ngày"
                        value={draft.billingMode}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            billingMode: e.target.value as Policy['billingMode'],
                          })
                        }
                      >
                        <option value="ROLLING_24_HOURS">Chu kỳ 24 giờ</option>
                        <option value="CALENDAR_DAY">Ngày lịch</option>
                      </SelectField>
                      <Field
                        type="number"
                        min="1"
                        label="Số ngày tối thiểu"
                        value={draft.minDays}
                        onChange={(e) => setDraft({ ...draft, minDays: Number(e.target.value) })}
                      />
                      <Field
                        type="number"
                        min="1"
                        label="Số ngày tối đa"
                        value={draft.maxDays}
                        onChange={(e) => setDraft({ ...draft, maxDays: Number(e.target.value) })}
                      />
                    </div>
                    <TextAreaField
                      label="Lý do thay đổi"
                      value={draft.reason}
                      onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
                    />
                    <Button
                      loading={busy}
                      onClick={() => {
                        void (async () => {
                          if (
                            !draft.from ||
                            !draft.reason.trim() ||
                            draft.maxDays < draft.minDays
                          ) {
                            setIssue('Nhập ngày hiệu lực, lý do và số ngày hợp lệ.');
                            return;
                          }
                          setBusy(true);
                          setIssue('');
                          try {
                            await studioAdapter.savePolicy(draft, scenario);
                            setSelected(draft.code);
                            setDraft(undefined);
                            retry();
                          } catch (e) {
                            setIssue(issueText(e));
                          } finally {
                            setBusy(false);
                          }
                        })();
                      }}
                    >
                      Tạo phiên bản
                    </Button>
                  </Panel>
                )}
                <InlineIssue text={issue} />
              </div>
            </div>
          </div>
        );
      }}
    </StateGate>
  );
}

export function ReportsPage({
  scenario,
  branch,
  allBranches,
}: {
  scenario: DemoScenario;
  branch: string;
  allBranches: boolean;
}) {
  const { loading, error, data, retry } = useFixtureResource(scenario, studioAdapter.reports);
  const [filter, setFilter] = useState(branch);
  return (
    <StateGate
      loading={loading}
      error={error}
      data={data}
      retry={retry}
      emptyTitle="Chưa có báo cáo"
    >
      {(reports) => {
        const scoped = reports.filter((r) => r.branch === (allBranches ? filter : branch));
        return (
          <div className="page">
            <PageHeading
              eyebrow="QUẢN TRỊ / BÁO CÁO"
              title="Báo cáo vận hành"
              description="Snapshot fixture theo chi nhánh. Cọc đang giữ hiển thị riêng, không cộng vào doanh thu thuê."
            />
            <FilterBar>
              {allBranches ? (
                <BranchSelector value={filter} onChange={setFilter} />
              ) : (
                <p>
                  Chi nhánh được cấp quyền: <strong>{branch}</strong>
                </p>
              )}
            </FilterBar>
            {scoped.map((report) => (
              <div key={report.branch}>
                <p className="muted">
                  {report.period} · {report.branch}
                </p>
                <div className="report-grid">
                  <Panel title="Lượt thuê">
                    <strong className="report-number">{report.rentalCount}</strong>
                  </Panel>
                  <Panel title="Doanh thu tiền thuê">
                    <strong className="report-number">{money(report.rentalRevenue)}</strong>
                  </Panel>
                  <Panel title="Cọc đang giữ">
                    <strong className="report-number">{money(report.depositsHeld)}</strong>
                    <p className="muted">Khoản phải hoàn/đối soát; không là doanh thu.</p>
                  </Panel>
                  <Panel title="Bộ quá hạn">
                    <strong className="report-number">{report.overdueUnits}</strong>
                  </Panel>
                </div>
                <div className="feature-two-column">
                  <Panel title="Giao dịch">
                    <KeyFacts
                      rows={report.transactions.map((t) => ({ label: t.status, value: t.count }))}
                    />
                    {scenario === 'bankPending' && (
                      <Feedback tone="warning" title="Chuyển khoản chờ đối soát">
                        Khoản pending chưa được tính đã thu.
                      </Feedback>
                    )}
                  </Panel>
                  <Panel title="Hoàn cọc">
                    <KeyFacts
                      rows={report.refunds.map((t) => ({ label: t.status, value: t.count }))}
                    />
                    {scenario === 'refundFailed' && (
                      <Feedback tone="danger" title="Hoàn cọc thất bại">
                        Cần đối soát trạng thái; không tự thử lại giao dịch tài chính.
                      </Feedback>
                    )}
                  </Panel>
                </div>
              </div>
            ))}
          </div>
        );
      }}
    </StateGate>
  );
}
