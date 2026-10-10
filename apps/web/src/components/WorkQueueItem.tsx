import type { QueueTask } from '../fixtures/types';
import { Icon, StatusLabel } from './ui';

export function WorkQueueItem({ task, onOpen }: { task: QueueTask; onOpen: () => void }) {
  const tone =
    task.group === 'Quá hạn'
      ? 'danger'
      : task.group === 'Trong 2 giờ tới' || task.group === 'Chờ xác nhận lâu'
        ? 'warning'
        : 'info';
  return (
    <button
      className="work-item"
      type="button"
      onClick={onOpen}
      aria-label={`Mở ${task.orderId}: ${task.task}`}
    >
      <span className="work-time">
        <Icon name="clock" size={17} />
        {task.due}
      </span>
      <span className="work-main">
        <strong>{task.task}</strong>
        <small>
          <b>{task.orderId}</b> · {task.customer} · {task.status} · Phụ trách: {task.owner}
        </small>
      </span>
      <StatusLabel text={task.urgency} tone={tone} />
      <span className="work-open">
        <Icon name="arrow" size={19} />
      </span>
    </button>
  );
}
