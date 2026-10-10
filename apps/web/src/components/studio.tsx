import { useState, type ReactNode } from 'react';
import { Button, EmptyState, Feedback, Field, SelectField, StatusLabel } from './ui';
import { money } from './support';
import type { DemoScenario, Tone } from '../fixtures/types';
import type { Permission, Unit } from '../fixtures/studio';
import { studioAdapter } from '../fixtures/studio';
import {
  blockStatusLabels,
  blockTypeLabels,
  conditionLabels,
  unitStatusLabels,
} from './statusLabels';

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="feature-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="feature-heading-action">{action}</div>}
    </div>
  );
}
export function Panel({
  title,
  children,
  action,
  className = '',
}: {
  title?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`feature-panel ${className}`}>
      {title && (
        <div className="feature-panel-head">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function KeyFacts({ rows }: { rows: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="key-facts">
      {rows.map((row) => (
        <div key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
export function Timeline({ items }: { items: string[] }) {
  return items.length ? (
    <ol className="feature-timeline">
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>{item}</li>
      ))}
    </ol>
  ) : (
    <p className="muted">Chưa có hoạt động nào.</p>
  );
}
export function StateGate<T>({
  loading,
  error,
  data,
  retry,
  children,
  emptyTitle = 'Chưa có dữ liệu',
}: {
  loading: boolean;
  error?: string;
  data?: T[];
  retry: () => void;
  children: (data: T[]) => ReactNode;
  emptyTitle?: string;
}) {
  if (loading)
    return (
      <div className="page">
        <div className="feature-skeleton shimmer" role="status">
          Đang tải dữ liệu…
        </div>
      </div>
    );
  if (error)
    return (
      <div className="page">
        <Feedback
          tone="danger"
          title="Không tải được dữ liệu"
          action={
            <Button variant="secondary" onClick={retry}>
              Thử lại
            </Button>
          }
        >
          {error}
        </Feedback>
      </div>
    );
  if (!data?.length)
    return (
      <div className="page">
        <EmptyState title={emptyTitle}>
          Thử điều chỉnh bộ lọc hoặc chọn tình huống bình thường trong công cụ demo.
        </EmptyState>
      </div>
    );
  return <>{children(data)}</>;
}
export function InlineIssue({ text, conflict = false }: { text: string; conflict?: boolean }) {
  return text ? (
    <Feedback
      tone={conflict ? 'warning' : 'danger'}
      title={conflict ? 'Dữ liệu đã thay đổi' : 'Chưa thể hoàn tất'}
    >
      {text}
    </Feedback>
  ) : null;
}
export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="feature-filters">{children}</div>;
}
export function SearchField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <Field
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  );
}
export function BranchSelector({
  value,
  onChange,
  all = false,
  label = 'Chi nhánh',
}: {
  value: string;
  onChange: (value: string) => void;
  all?: boolean;
  label?: string;
}) {
  return (
    <SelectField label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      {all && <option value="">Tất cả chi nhánh</option>}
      <option>Chi nhánh Quận 1</option>
      <option>Chi nhánh Thủ Đức</option>
    </SelectField>
  );
}
export function DateTimeField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field
      type="datetime-local"
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
export function MoneySummary({
  rental,
  deposit,
  extra = 0,
  refund = 0,
  title = 'Chi tiết tiền',
}: {
  rental: number;
  deposit: number;
  extra?: number;
  refund?: number;
  title?: string;
}) {
  return (
    <Panel title={title}>
      <KeyFacts
        rows={[
          { label: 'Tiền thuê', value: money(rental) },
          { label: 'Cọc (không tính doanh thu)', value: money(deposit) },
          { label: 'Phụ phí', value: money(extra) },
          { label: 'Đã hoàn cọc', value: money(refund) },
        ]}
      />
    </Panel>
  );
}
export function StatusText({ text, tone = 'neutral' }: { text: string; tone?: Tone }) {
  return <StatusLabel text={text} tone={tone} />;
}
export function BarcodeLookup({
  branch,
  scenario,
  onFound,
  onError,
  autoFocus = false,
}: {
  branch: string;
  scenario: DemoScenario;
  onFound: (unit: Unit) => void;
  onError?: () => void;
  autoFocus?: boolean;
}) {
  const [code, setCode] = useState('');
  const [issue, setIssue] = useState('');
  const [busy, setBusy] = useState(false);
  const lookup = async () => {
    setBusy(true);
    setIssue('');
    try {
      onFound(await studioAdapter.barcode(code, branch, scenario));
    } catch (error) {
      onError?.();
      setIssue(error instanceof Error ? error.message : 'Không tìm thấy mã.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <div>
      <form
        className="barcode-form"
        onSubmit={(e) => {
          e.preventDefault();
          void lookup();
        }}
      >
        <Field
          label="Quét hoặc nhập barcode"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="Ví dụ: BC-031"
          autoComplete="off"
          autoFocus={autoFocus}
        />
        <Button loading={busy} type="submit">
          Tra mã
        </Button>
      </form>
      <InlineIssue
        text={issue}
        conflict={scenario === 'unitBlocked' || scenario === 'barcodeOtherBranch'}
      />
    </div>
  );
}
export function UnitDetailPanel({ unit, action }: { unit: Unit; action?: ReactNode }) {
  return (
    <Panel title={`${unit.barcode} · ${unit.model}`} action={action}>
      <KeyFacts
        rows={[
          { label: 'Biến thể', value: unit.variant },
          { label: 'Chi nhánh', value: unit.branch },
          { label: 'Vận hành', value: unitStatusLabels[unit.status] },
          {
            label: 'Khả dụng trong kỳ mẫu',
            value: unit.available ? 'Có thể kiểm tra tiếp' : 'Không khả dụng',
          },
          { label: 'Tình trạng', value: conditionLabels[unit.condition] ?? unit.condition },
        ]}
      />
      <h3>Block đang có</h3>
      {unit.blocks.length ? (
        unit.blocks.map((block, index) => (
          <div className="feature-list-row" key={index}>
            <strong>
              {blockTypeLabels[block.type]} · {blockStatusLabels[block.status]}
            </strong>
            <span>
              {block.from} → {block.until}
            </span>
            <small>{block.reason}</small>
          </div>
        ))
      ) : (
        <p className="muted">Không có block.</p>
      )}
      <h3>Lịch sử bộ</h3>
      <Timeline items={unit.history} />
    </Panel>
  );
}
export function PermissionGroup({
  title,
  permissions,
  selected,
  onToggle,
  onSelectAll,
  onClear,
  filtered = false,
}: {
  title: string;
  permissions: Permission[];
  selected: string[];
  onToggle: (code: string) => void;
  onSelectAll?: () => void;
  onClear?: () => void;
  filtered?: boolean;
}) {
  return (
    <Panel
      title={title}
      action={
        permissions.length && onSelectAll && onClear ? (
          <div className="permission-group-actions">
            <button
              type="button"
              disabled={permissions.every((permission) => selected.includes(permission.code))}
              onClick={onSelectAll}
            >
              {filtered ? 'Chọn các quyền hiện ra' : 'Chọn cả nhóm'}
            </button>
            <button
              type="button"
              disabled={permissions.every((permission) => !selected.includes(permission.code))}
              onClick={onClear}
            >
              {filtered ? 'Bỏ các quyền hiện ra' : 'Bỏ cả nhóm'}
            </button>
          </div>
        ) : undefined
      }
    >
      {!permissions.length && (
        <p className="muted">
          Chưa có mã quyền riêng trong seed. Giao/nhận trả hiện nằm trong rentals.manage.branch; cần
          thêm mã quyền và kiểm tra API nếu muốn tick độc lập.
        </p>
      )}
      <div className="permission-list">
        {permissions.map((permission) => (
          <label className="permission-row" key={permission.code}>
            <input
              type="checkbox"
              checked={selected.includes(permission.code)}
              onChange={() => onToggle(permission.code)}
            />
            <span>
              <strong>{permission.label}</strong>
              <small>{permission.description}</small>
              <code>
                {permission.code} · {permission.scope}
              </code>
            </span>
          </label>
        ))}
      </div>
    </Panel>
  );
}
