import { useState } from 'react';
import type { Navigate } from '../App';
import { Button, EmptyState, Feedback, Field, Icon, SelectField } from '../components/ui';
import { useFixtureResource } from '../components/useFixtureResource';
import { WorkQueueItem } from '../components/WorkQueueItem';
import { branches, fixtureAdapter, fixtureClock } from '../fixtures/adapter';
import type { DemoScenario, QueueTask } from '../fixtures/types';

const loadQueue = (scenario: DemoScenario) => fixtureAdapter.listQueue(scenario);
const groups: QueueTask['group'][] = ['Quá hạn', 'Trong 2 giờ tới', 'Hôm nay', 'Chờ xác nhận lâu'];
const summary: { label: string; kind: QueueTask['kind']; short: string }[] = [
  { label: 'Chờ xác nhận', kind: 'pending', short: 'Cần duyệt' },
  { label: 'Giao trong ngày', kind: 'handover', short: 'Sắp giao' },
  { label: 'Trả trong ngày', kind: 'return', short: 'Sắp trả' },
  { label: 'Quá hạn', kind: 'overdue', short: 'Cần theo dõi' },
  { label: 'Giao dịch cần xử lý', kind: 'payment', short: 'Tiền' },
];

export function DashboardPage({ scenario, go }: { scenario: DemoScenario; go: Navigate }) {
  const [branch, setBranch] = useState(branches[0]);
  const [kind, setKind] = useState('all');
  const [priority, setPriority] = useState('all');
  const [taskStatus, setTaskStatus] = useState('all');
  const [workDate, setWorkDate] = useState('2026-10-03');
  const [search, setSearch] = useState('');
  const [stale, setStale] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const { loading, data, error, retry } = useFixtureResource(scenario, loadQueue);
  const scoped = (data ?? []).filter((task) => task.branch === branch && !stale.includes(task.id));
  const visible = scoped.filter(
    (task) =>
      (kind === 'all' || task.kind === kind) &&
      (priority === 'all' || task.group === priority) &&
      (taskStatus === 'all' || task.status === taskStatus) &&
      (!workDate || task.workDate === workDate) &&
      `${task.orderId} ${task.customer} ${task.phone} ${task.barcode ?? ''} ${task.task}`
        .toLocaleLowerCase('vi')
        .includes(search.toLocaleLowerCase('vi')),
  );
  const openTask = (task: QueueTask) => {
    if (scenario === 'conflict') {
      setStale((current) => [...current, task.id]);
      setNotice(
        `${task.orderId} vừa được người khác xử lý và đã rời hàng đợi. Bộ lọc hiện tại được giữ.`,
      );
      return;
    }
    go('orders', { order: task.orderId });
  };
  const dateText = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    dateStyle: 'full',
    timeStyle: 'short',
  }).format(fixtureClock);
  return (
    <div className="page staff-page dashboard-page">
      <div className="staff-page-heading">
        <div>
          <p className="eyebrow">UI-06 · BẢNG VIỆC NHÂN VIÊN</p>
          <h1>Chào buổi làm việc 👋</h1>
          <p>Những việc cần chú ý tại chi nhánh của bạn.</p>
        </div>
        <div className="date-pill">
          <Icon name="calendar" size={18} />
          Giờ fixture · {dateText}
        </div>
      </div>
      <div className="staff-toolbar">
        <SelectField
          label="Chi nhánh đang làm việc"
          value={branch}
          onChange={(event) => {
            setBranch(event.target.value);
            setKind('all');
          }}
        >
          {branches.map((entry) => (
            <option key={entry}>{entry}</option>
          ))}
        </SelectField>
        <Field
          label="Tìm mã đơn, barcode hoặc số điện thoại"
          placeholder="Ví dụ: RT-1024, BC-028..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <SelectField
          label="Loại việc"
          value={kind}
          onChange={(event) => setKind(event.target.value)}
        >
          <option value="all">Tất cả việc</option>
          {summary.map((entry) => (
            <option key={entry.kind} value={entry.kind}>
              {entry.label}
            </option>
          ))}
        </SelectField>
      </div>
      <div className="queue-extra-filters">
        <SelectField
          label="Mức ưu tiên"
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          <option value="all">Tất cả mức</option>
          {groups.map((entry) => (
            <option key={entry}>{entry}</option>
          ))}
        </SelectField>
        <SelectField
          label="Trạng thái việc"
          value={taskStatus}
          onChange={(event) => setTaskStatus(event.target.value)}
        >
          <option value="all">Tất cả trạng thái</option>
          <option>Cần xử lý</option>
          <option>Đang xử lý</option>
        </SelectField>
        <Field
          label="Ngày cần xử lý"
          type="date"
          value={workDate}
          onChange={(event) => setWorkDate(event.target.value)}
        />
      </div>
      <section className="queue-summary" aria-label="Tóm tắt hàng đợi">
        {summary.map((entry) => (
          <button
            key={entry.kind}
            className={`queue-counter ${kind === entry.kind ? 'selected' : ''}`}
            onClick={() => setKind(entry.kind)}
          >
            <span>{entry.label}</span>
            <strong>
              {loading ? '—' : scoped.filter((task) => task.kind === entry.kind).length}
            </strong>
            <small>
              {entry.short} <Icon name="arrow" size={14} />
            </small>
          </button>
        ))}
      </section>
      <div className="queue-heading">
        <div>
          <p className="eyebrow">THEO THỨ TỰ ƯU TIÊN</p>
          <h2>Ưu tiên xử lý</h2>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            setNotice('');
            setStale([]);
            retry();
          }}
        >
          <Icon name="refresh" size={17} /> Làm mới
        </Button>
      </div>
      {notice && (
        <Feedback tone="warning" title="Hàng đợi đã thay đổi">
          {notice}
        </Feedback>
      )}
      {scenario === 'permission' && (
        <Feedback tone="danger" title="Bạn không còn quyền xử lý đơn tại chi nhánh này">
          Chuyển sang chi nhánh được cấp quyền hoặc về tổng quan. Không gửi thao tác cũ.
        </Feedback>
      )}
      {error && (
        <Feedback
          tone="danger"
          title="Không tải được hàng đợi"
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
        <div className="queue-skeleton" aria-label="Đang tải hàng đợi">
          {[1, 2, 3, 4].map((entry) => (
            <div className="shimmer" key={entry} />
          ))}
        </div>
      )}
      {!loading && !error && visible.length === 0 && (
        <EmptyState title="Chưa có việc cần xử lý ở chi nhánh này">
          Các bộ lọc đang áp dụng có thể chưa có kết quả.
          <div className="empty-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setSearch('');
                setKind('all');
                setPriority('all');
                setTaskStatus('all');
                setWorkDate('2026-10-03');
              }}
            >
              Xóa bộ lọc
            </Button>
            <Button variant="quiet" onClick={() => go('orders')}>
              Mở danh sách đơn
            </Button>
          </div>
        </EmptyState>
      )}
      {!loading && !error && visible.length > 0 && (
        <div className="work-groups">
          {groups.map((group) => {
            const tasks = visible.filter((task) => task.group === group);
            return tasks.length ? (
              <section key={group} className="work-group">
                <div className="work-group-heading">
                  <h3>{group}</h3>
                  <span>{tasks.length} việc</span>
                </div>
                <div className="work-list">
                  {tasks.map((task) => (
                    <WorkQueueItem key={task.id} task={task} onOpen={() => openTask(task)} />
                  ))}
                </div>
              </section>
            ) : null;
          })}
        </div>
      )}
      <p className="fixture-caption">
        Ngưỡng “trong 2 giờ” và các mốc hạn chỉ là dữ liệu minh họa. SLA thực tế cần cấu hình theo
        chính sách studio.
      </p>
    </div>
  );
}
