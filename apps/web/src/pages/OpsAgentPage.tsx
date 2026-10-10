import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import type { Navigate } from '../App';
import { Button, Icon, StatusLabel } from '../components/ui';
import { PageHeading, Panel } from '../components/studio';
import { fixtureAdapter, fixtureClock } from '../fixtures/adapter';
import type { DemoScenario, QueueTask, Tone } from '../fixtures/types';
import { useFixtureResource } from '../components/useFixtureResource';

interface SourceNote {
  title: string;
  detail: string;
  status: string;
  tone: Tone;
  excerpt: string;
}

interface AgentMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  sources?: SourceNote[];
  demoOnly?: boolean;
}

interface KnowledgeSource extends SourceNote {
  id: string;
  coverage: string;
  kind: string;
}

type OpsSection = 'overview' | 'queue' | 'runbooks' | 'knowledge' | 'activity' | 'assistant';
type QueueFilter = 'all' | QueueTask['kind'];

const opsSections: { id: OpsSection; label: string }[] = [
  { id: 'overview', label: 'Tổng quan' },
  { id: 'queue', label: 'Hàng đợi' },
  { id: 'runbooks', label: 'Quy trình' },
  { id: 'knowledge', label: 'Nguồn tri thức' },
  { id: 'activity', label: 'Nhật ký' },
  { id: 'assistant', label: 'Hỏi Agent' },
];

const sources = {
  businessRules: {
    title: 'Yêu cầu sản phẩm Ops Agent',
    detail: 'Mục 4 · FR-17 và FR-18',
    status: 'Đặc tả prototype',
    tone: 'info',
    excerpt:
      'Agent không tự cập nhật đơn, tiền, quyền, giá hoặc chính sách; không tự tính kết quả khi quy tắc chưa được xác nhận.',
  },
  handoff: {
    title: 'Định hướng sản phẩm Ops Agent',
    detail: 'Mục 5 · Lời hứa sản phẩm',
    status: 'Định hướng',
    tone: 'neutral',
    excerpt: 'Agent hỗ trợ công việc, nêu nguồn và phân biệt rõ thông tin, đề xuất với thao tác đã được hệ thống xác nhận.',
  },
  paymentReview: {
    title: 'Yêu cầu sản phẩm Ops Agent',
    detail: 'Luồng AT-04 · payment/refund pending',
    status: 'Tiêu chí prototype',
    tone: 'info',
    excerpt: 'Trạng thái pending phải được gọi là đang chờ; không diễn đạt như giao dịch đã thu hoặc đã hoàn.',
  },
  paymentRules: {
    title: 'Yêu cầu sản phẩm Ops Agent',
    detail: 'Mục 3 · Nhãn nguồn và trạng thái',
    status: 'Đặc tả prototype',
    tone: 'info',
    excerpt:
      'Câu trả lời phải phân biệt DOC, DEMO, nguồn đã cấu hình, đề xuất và nội dung chưa xác minh.',
  },
  handoffDecisions: {
    title: 'Yêu cầu sản phẩm Ops Agent',
    detail: 'Mục 9 · Quyết định còn mở',
    status: 'Cần xác minh',
    tone: 'warning',
    excerpt: 'Nguồn dữ liệu, quyền, policy nghiệp vụ và thao tác được phép cần được chủ sản phẩm xác nhận.',
  },
  returnFlow: {
    title: 'Yêu cầu sản phẩm Ops Agent',
    detail: 'Mục 4 · FR-18',
    status: 'Đặc tả prototype',
    tone: 'warning',
    excerpt:
      'Khi policy về phí, hư hỏng hoặc refund chưa được xác nhận, Agent không tự tính kết quả.',
  },
} satisfies Record<string, SourceNote>;

const knowledgeSources: KnowledgeSource[] = [
  {
    id: 'product-requirements',
    kind: 'YÊU CẦU OPS AGENT',
    title: 'Yêu cầu sản phẩm Ops Agent',
    detail: 'Mục 3–4 · nguồn, trạng thái và yêu cầu an toàn',
    status: 'Đặc tả prototype',
    tone: 'info',
    coverage: 'Nguồn · câu trả lời · giới hạn thao tác',
    excerpt:
      'Mô tả phạm vi dự kiến của Agent; chưa phải SOP vận hành được duyệt.',
  },
  {
    id: 'product-direction',
    kind: 'ĐỊNH HƯỚNG SẢN PHẨM',
    title: 'Định hướng sản phẩm Ops Agent',
    detail: 'Mục 5–8 · nguyên tắc, giai đoạn và ranh giới',
    status: 'Tài liệu định hướng',
    tone: 'neutral',
    coverage: 'Phát triển độc lập · phạm vi Agent',
    excerpt:
      'Ops Agent là capability bổ sung trong ứng dụng riêng; không thay thế web nghiệp vụ Studio.',
  },
  {
    id: 'demo-runbooks',
    kind: 'NỘI DUNG DEMO',
    title: 'Checklist minh họa',
    detail: 'Nội dung giao diện · không phải SOP đã duyệt',
    status: 'DEMO',
    tone: 'warning',
    coverage: 'Đơn · thanh toán · giao nhận',
    excerpt: 'Các bước hiển thị để minh họa giao diện. Hãy dùng SOP được tổ chức phê duyệt khi xử lý thật.',
  },
];

const suggestedQuestions = [
  {
    category: 'ĐƠN THUÊ',
    title: 'Đơn online đang chờ xác nhận cần làm gì?',
    prompt: 'Đơn online đang chờ xác nhận thì nhân viên cần làm gì?',
  },
  {
    category: 'THANH TOÁN',
    title: 'Chuyển khoản chờ đối soát đã được tính là đã thu chưa?',
    prompt: 'Chuyển khoản chờ đối soát có được tính là đã thu không?',
  },
  {
    category: 'NHẬN TRẢ',
    title: 'Khi đồ trả bị hỏng thì bước tiếp theo là gì?',
    prompt: 'Khi khách trả đồ bị hỏng thì bước tiếp theo là gì?',
  },
];

const runbooks = [
  {
    id: 'confirmation',
    category: 'ĐƠN THUÊ',
    title: 'Duyệt đơn online',
    status: 'Checklist minh họa · cần SOP duyệt',
    tone: 'warning' as const,
    summary: 'Ví dụ giao diện; quy trình chính thức cần lấy từ SOP được tổ chức phê duyệt.',
    question: 'Đơn online đang chờ xác nhận thì nhân viên cần làm gì?',
    sources: [sources.businessRules, sources.handoffDecisions, sources.handoff],
    steps: [
      'Đối chiếu trạng thái và kỳ thuê trên hệ thống nghiệp vụ có thẩm quyền.',
      'Kiểm tra khả dụng của bộ theo nguồn dữ liệu được cấu hình.',
      'Để nhân viên có quyền xử lý; Ops Agent không xác nhận hoặc từ chối đơn.',
    ],
  },
  {
    id: 'payment',
    category: 'THANH TOÁN',
    title: 'Đối soát chuyển khoản',
    status: 'Đối chiếu nguồn trước khi kết luận',
    tone: 'warning' as const,
    summary: 'Giữ trạng thái pending là đang chờ; demo chưa kết nối nguồn thanh toán.',
    question: 'Chuyển khoản chờ đối soát có được tính là đã thu không?',
    sources: [sources.paymentReview, sources.paymentRules],
    steps: [
      'Kiểm tra trạng thái giao dịch tại nguồn thanh toán được cấu hình.',
      'Không diễn đạt giao dịch pending thành đã thu hoặc đã hoàn.',
      'Nếu chưa có nguồn xác nhận, báo rõ không thể xác minh giao dịch cụ thể.',
    ],
  },
  {
    id: 'handover',
    category: 'GIAO ĐỒ',
    title: 'Chuẩn bị bàn giao bộ',
    status: 'Checklist minh họa · cần SOP duyệt',
    tone: 'info' as const,
    summary: 'Các điểm kiểm tra gợi ý; SOP giao nhận chính thức chưa được kết nối.',
    question: 'Trước khi bàn giao một đơn thuê cần kiểm tra những gì?',
    sources: [sources.handoff, sources.paymentReview],
    steps: [
      'Đối chiếu đơn và người nhận trên hệ thống nghiệp vụ có thẩm quyền.',
      'Kiểm tra mã bộ theo quy trình được tổ chức phê duyệt.',
      'Nhân viên thực hiện bước giao; demo không ghi thay đổi.',
    ],
  },
  {
    id: 'return',
    category: 'NHẬN TRẢ',
    title: 'Kiểm tra tình trạng khi trả',
    status: 'Phí / hoàn cọc chưa chốt',
    tone: 'warning' as const,
    summary: 'Không suy diễn phí hoặc hoàn cọc khi policy và SOP chưa được xác nhận.',
    question: 'Khi khách trả đồ bị hỏng thì bước tiếp theo là gì?',
    sources: [sources.returnFlow, sources.handoffDecisions],
    steps: [
      'Để nhân viên ghi nhận kết quả kiểm tra trên hệ thống có thẩm quyền.',
      'Áp dụng cách phân loại theo SOP được tổ chức phê duyệt.',
      'Chuyển quyết định phí hoặc hoàn cọc cho người có thẩm quyền; Agent không tự tính hay ghi nhận.',
    ],
  },
];

const queueFilterOptions: { value: QueueFilter; label: string }[] = [
  { value: 'all', label: 'Tất cả' },
  { value: 'pending', label: 'Chờ xác nhận' },
  { value: 'handover', label: 'Giao đồ' },
  { value: 'return', label: 'Nhận trả' },
  { value: 'payment', label: 'Thanh toán' },
  { value: 'overdue', label: 'Quá hạn' },
];

const loadQueue = (scenario: DemoScenario) => fixtureAdapter.listQueue(scenario);

function answerFor(prompt: string): Pick<AgentMessage, 'text' | 'sources' | 'demoOnly'> {
  const normalized = prompt.toLocaleLowerCase('vi');

  if (normalized.includes('chờ') && normalized.includes('đơn')) {
    return {
      text: 'Đặc tả Ops Agent hiện chưa định nghĩa SOP duyệt đơn hoặc SLA vận hành. Hãy kiểm tra đơn trên hệ thống có thẩm quyền và làm theo quy trình đã được tổ chức phê duyệt; bản demo không xác nhận hoặc từ chối đơn.',
      sources: [sources.businessRules, sources.handoffDecisions, sources.handoff],
    };
  }

  if (normalized.includes('chuyển khoản') || normalized.includes('đã thu')) {
    return {
      text: 'Theo tiêu chí AT-04 trong yêu cầu sản phẩm, trạng thái payment/refund pending phải được gọi là đang chờ, không diễn đạt như đã thu hoặc đã hoàn. Nguồn thanh toán live chưa được cấu hình nên bản demo không thể xác minh giao dịch cụ thể.',
      sources: [sources.paymentReview, sources.paymentRules],
    };
  }

  if (normalized.includes('quá hạn') || normalized.includes('trễ hạn')) {
    return {
      text: 'Hãy đối chiếu hạn trả trên nguồn nghiệp vụ có thẩm quyền. Nếu policy tính phí trễ chưa được xác nhận, yêu cầu sản phẩm quy định Agent không tự tính phí, ghi nhận khoản phải thu hoặc thay đổi trạng thái đơn.',
      sources: [sources.handoffDecisions, sources.businessRules],
    };
  }

  if (normalized.includes('bàn giao') || normalized.includes('giao bộ')) {
    return {
      text: 'Checklist minh họa: đối chiếu đơn, người nhận, mã bộ và trạng thái giao dịch trên nguồn có thẩm quyền. Đây chưa phải SOP được duyệt; nhân viên thực hiện thao tác giao trong hệ thống nghiệp vụ, còn bản demo không ghi thay đổi.',
      sources: [sources.handoff, sources.paymentReview],
    };
  }

  if (
    normalized.includes('trả') ||
    normalized.includes('hỏng') ||
    normalized.includes('hư')
  ) {
    return {
      text: 'Yêu cầu sản phẩm quy định Agent không tự tính kết quả khi policy về hư hỏng, phí hoặc refund chưa được xác nhận. Hãy ghi nhận theo SOP được duyệt và chuyển quyết định tài chính cho người có thẩm quyền; prototype không cập nhật dữ liệu.',
      sources: [sources.returnFlow, sources.handoffDecisions],
    };
  }

  return {
    text: 'Bản giao diện này chưa kết nối mô hình hoặc nguồn dữ liệu vận hành. Tôi chưa thể trả lời câu hỏi tự do; hãy chọn một chủ đề mẫu để xem cách Ops Agent trình bày câu trả lời và nguồn. Nội dung bạn vừa nhập chỉ nằm trong phiên demo hiện tại.',
    demoOnly: true,
  };
}

function taskQuestion(task: QueueTask) {
  switch (task.kind) {
    case 'pending':
      return `Đơn thuê ${task.orderId} đang chờ xác nhận, nhân viên cần kiểm tra gì?`;
    case 'payment':
      return `Chuyển khoản của đơn ${task.orderId} đang chờ đối soát đã được tính là đã thu chưa?`;
    case 'handover':
      return `Trước khi bàn giao bộ cho đơn ${task.orderId} cần kiểm tra những gì?`;
    case 'return':
      return `Khi nhận trả bộ của đơn ${task.orderId}, cần ghi nhận tình trạng nào?`;
    case 'overdue':
      return `Đơn ${task.orderId} đang quá hạn, cần theo dõi thế nào? Có được tự tính phí không?`;
  }
}

function groupOrder(group: QueueTask['group']) {
  return ['Quá hạn', 'Trong 2 giờ tới', 'Chờ xác nhận lâu', 'Hôm nay'].indexOf(group);
}

function taskTone(task: QueueTask): Tone {
  if (task.group === 'Quá hạn') return 'danger';
  if (task.group === 'Trong 2 giờ tới' || task.group === 'Chờ xác nhận lâu') return 'warning';
  return 'info';
}

export function OpsAgentPage({
  branch,
  scenario,
  go,
}: {
  branch: string;
  scenario: DemoScenario;
  go: Navigate;
}) {
  const [section, setSection] = useState<OpsSection>('overview');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [queueFilter, setQueueFilter] = useState<QueueFilter>('all');
  const [queueSearch, setQueueSearch] = useState('');
  const [knowledgeSearch, setKnowledgeSearch] = useState('');
  const [showUnverifiedOnly, setShowUnverifiedOnly] = useState(false);
  const nextId = useRef(0);
  const latestMessageRef = useRef<HTMLLIElement>(null);
  const sectionTabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const { loading, data, error, retry } = useFixtureResource(scenario, loadQueue);
  const branchTasks = (data ?? []).filter((task) => task.branch === branch);
  const prioritizedTasks = [...branchTasks].sort((left, right) => {
    const groupDelta = groupOrder(left.group) - groupOrder(right.group);
    return groupDelta || left.due.localeCompare(right.due, 'vi');
  });
  const visibleTasks = prioritizedTasks.filter((task) => {
    const matchesKind = queueFilter === 'all' || task.kind === queueFilter;
    const query = queueSearch.trim().toLocaleLowerCase('vi');
    const content = `${task.orderId} ${task.task} ${task.customer} ${task.barcode ?? ''}`;
    return matchesKind && (!query || content.toLocaleLowerCase('vi').includes(query));
  });
  const visibleSources = knowledgeSources.filter((source) => {
    const query = knowledgeSearch.trim().toLocaleLowerCase('vi');
    const matchesQuery = `${source.title} ${source.kind} ${source.coverage}`
      .toLocaleLowerCase('vi')
      .includes(query);
    return matchesQuery && (!showUnverifiedOnly || source.tone === 'warning');
  });

  useEffect(() => {
    if (messages.length === 0) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    latestMessageRef.current?.scrollIntoView({
      block: 'nearest',
      behavior: reducedMotion ? 'auto' : 'smooth',
    });
  }, [messages]);

  const ask = (rawQuestion: string) => {
    const text = rawQuestion.trim();
    if (!text) return;

    const answer = answerFor(text);
    setMessages((current) => [
      ...current,
      { id: ++nextId.current, role: 'user', text },
      { id: ++nextId.current, role: 'assistant', ...answer },
    ]);
    setQuestion('');
    setSection('assistant');
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    ask(question);
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | undefined;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % opsSections.length;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + opsSections.length) % opsSections.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = opsSections.length - 1;
    if (nextIndex === undefined) return;
    event.preventDefault();
    setSection(opsSections[nextIndex].id);
    sectionTabRefs.current[nextIndex]?.focus();
  };

  const fixtureTime = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(fixtureClock);

  return (
    <div className="page ops-agent-page ops-console-page">
      <PageHeading
        eyebrow="TRUNG TÂM HỖ TRỢ VẬN HÀNH"
        title="Ops Agent"
        description="Theo dõi việc cần chú ý, tra quy trình và chuẩn bị bước tiếp theo cho nhân viên."
        action={<StatusLabel text="DEMO · FIXTURE" tone="warning" />}
      />

      <div className="ops-console-banner">
        <div className="ops-console-banner-copy">
          <span className="ops-agent-avatar" aria-hidden="true">
            <Icon name="spark" size={20} />
          </span>
          <div>
            <p className="eyebrow">OPS WORKSPACE</p>
            <h2>Trợ lý đang ở chế độ hướng dẫn</h2>
            <p>Dùng fixture và tài liệu sản phẩm · chưa có model, provider hay thao tác ghi.</p>
          </div>
        </div>
        <div className="ops-console-meta">
          <StatusLabel text="Chưa kết nối nguồn live" tone="neutral" />
          <span>
            <Icon name="pin" size={16} /> {branch}
          </span>
          <span>
            <Icon name="clock" size={16} /> Fixture lúc {fixtureTime}
          </span>
        </div>
      </div>

      <nav className="ops-console-tabs" role="tablist" aria-label="Các khu vực Ops Agent">
        {opsSections.map((item, index) => (
          <button
            key={item.id}
            ref={(element) => {
              sectionTabRefs.current[index] = element;
            }}
            id={`ops-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={section === item.id}
            aria-controls="ops-agent-panel"
            tabIndex={section === item.id ? 0 : -1}
            onClick={() => setSection(item.id)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
          >
            {item.id === 'overview' && <Icon name="scan" size={17} />}
            {item.id === 'queue' && <Icon name="bag" size={17} />}
            {item.id === 'runbooks' && <Icon name="check" size={17} />}
            {item.id === 'knowledge' && <Icon name="pin" size={17} />}
            {item.id === 'activity' && <Icon name="clock" size={17} />}
            {item.id === 'assistant' && <Icon name="spark" size={17} />}
            <span>{item.label}</span>
            {item.id === 'queue' && (
              <span className="ops-tab-count">{loading ? '…' : branchTasks.length}</span>
            )}
          </button>
        ))}
      </nav>

      <section
        id="ops-agent-panel"
        className="ops-agent-panel"
        role="tabpanel"
        aria-labelledby={`ops-tab-${section}`}
        tabIndex={0}
      >
        {section === 'overview' && (
          <OverviewSection
            branchTasks={prioritizedTasks}
            loading={loading}
            error={error}
            onRetry={retry}
            onOpenQueue={() => setSection('queue')}
            onAsk={ask}
            onOpenOrder={(task) => go('orders', { order: task.orderId })}
            onOpenRunbooks={() => setSection('runbooks')}
          />
        )}
        {section === 'queue' && (
          <QueueSection
            tasks={visibleTasks}
            total={branchTasks.length}
            loading={loading}
            error={error}
            retry={retry}
            filter={queueFilter}
            search={queueSearch}
            onFilterChange={setQueueFilter}
            onSearchChange={setQueueSearch}
            onAsk={ask}
            onOpenOrder={(task) => go('orders', { order: task.orderId })}
          />
        )}
        {section === 'runbooks' && <RunbooksSection onAsk={ask} />}
        {section === 'knowledge' && (
          <KnowledgeSection
            sources={visibleSources}
            search={knowledgeSearch}
            showUnverifiedOnly={showUnverifiedOnly}
            onSearchChange={setKnowledgeSearch}
            onToggleUnverified={() => setShowUnverifiedOnly((current) => !current)}
          />
        )}
        {section === 'activity' && <ActivitySection />}
        {section === 'assistant' && (
          <AssistantSection
            branch={branch}
            question={question}
            messages={messages}
            latestMessageRef={latestMessageRef}
            onQuestionChange={setQuestion}
            onSubmit={handleSubmit}
            onAsk={ask}
            onReset={() => setMessages([])}
          />
        )}
      </section>
    </div>
  );
}

function OverviewSection({
  branchTasks,
  loading,
  error,
  onRetry,
  onOpenQueue,
  onAsk,
  onOpenOrder,
  onOpenRunbooks,
}: {
  branchTasks: QueueTask[];
  loading: boolean;
  error?: string;
  onRetry: () => void;
  onOpenQueue: () => void;
  onAsk: (question: string) => void;
  onOpenOrder: (task: QueueTask) => void;
  onOpenRunbooks: () => void;
}) {
  const needsAction = branchTasks.filter((task) => task.status === 'Cần xử lý').length;
  const overdue = branchTasks.filter((task) => task.group === 'Quá hạn').length;
  const pending = branchTasks.filter((task) => task.kind === 'pending').length;
  const unverified = knowledgeSources.filter((source) => source.tone === 'warning').length;
  const metrics = [
    { label: 'Việc trong hàng đợi', value: loading ? '—' : branchTasks.length, note: 'Dữ liệu fixture', icon: 'bag' as const },
    { label: 'Cần nhân viên chú ý', value: loading ? '—' : needsAction, note: 'Chưa có agent xử lý tự động', icon: 'clock' as const },
    { label: 'Đang quá hạn', value: loading ? '—' : overdue, note: 'Theo thời điểm fixture', icon: 'calendar' as const },
    { label: 'Nguồn cần xác minh', value: unverified, note: 'Policy/SLA còn mở', icon: 'pin' as const },
  ];

  return (
    <div className="ops-section-content">
      <div className="ops-metrics-grid" aria-label="Tóm tắt Ops Agent">
        {metrics.map((metric) => (
          <article className="ops-metric-card" key={metric.label}>
            <span className="ops-metric-icon" aria-hidden="true">
              <Icon name={metric.icon} size={18} />
            </span>
            <div className="ops-metric-copy">
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>{metric.note}</small>
            </div>
          </article>
        ))}
      </div>

      <div className="ops-overview-grid">
        <Panel
          title="Việc cần chú ý"
          className="ops-queue-panel"
          action={
            <Button type="button" variant="quiet" onClick={onOpenQueue}>
              Mở hàng đợi <Icon name="arrow" size={16} />
            </Button>
          }
        >
          <QueueContent
            tasks={branchTasks.slice(0, 4)}
            loading={loading}
            error={error}
            retry={onRetry}
            onAsk={onAsk}
            onOpenOrder={onOpenOrder}
            compact
          />
        </Panel>

        <div className="ops-overview-rail">
          <Panel title="Runtime Agent" className="ops-runtime-panel">
            <div className="ops-runtime-status">
              <span className="ops-runtime-dot" aria-hidden="true" />
              <div>
                <strong>Giao diện sẵn sàng · Agent chưa chạy</strong>
                <span>Chưa cấu hình model hoặc orchestration backend.</span>
              </div>
            </div>
            <ul className="ops-runtime-list">
              <li>
                <span>Knowledge</span>
                <StatusLabel text="Snapshot local" tone="info" />
              </li>
              <li>
                <span>Ops data provider</span>
                <StatusLabel text="Chưa kết nối" tone="neutral" />
              </li>
              <li>
                <span>Tool ghi nghiệp vụ</span>
                <StatusLabel text="Đang tắt" tone="neutral" />
              </li>
            </ul>
          </Panel>

          <Panel title="Luồng xử lý có kiểm soát" className="ops-cycle-panel">
            <ol className="ops-cycle-list">
              <li><span>01</span><div><strong>Nhận diện việc</strong><small>Đọc fixture trong phạm vi</small></div></li>
              <li><span>02</span><div><strong>Đối chiếu nguồn</strong><small>Tài liệu có trạng thái rõ</small></div></li>
              <li><span>03</span><div><strong>Đề xuất checklist</strong><small>Không tự ghi thay đổi</small></div></li>
              <li><span>04</span><div><strong>Nhân viên xử lý</strong><small>Hệ thống nghiệp vụ vẫn là đích</small></div></li>
            </ol>
            <p className="ops-panel-footnote">Luồng thiết kế · chưa phải lượt chạy tự động.</p>
            <Button type="button" variant="secondary" onClick={onOpenRunbooks}>
              Xem quy trình <Icon name="arrow" size={16} />
            </Button>
          </Panel>
        </div>
      </div>

      {!loading && !error && pending > 0 && (
        <div className="ops-inline-note" role="note">
          <Icon name="pin" size={17} />
          Hàng đợi và số đếm là fixture của giao diện Studio; không phản ánh đơn hoặc tồn kho live.
        </div>
      )}
    </div>
  );
}

function QueueSection({
  tasks,
  total,
  loading,
  error,
  retry,
  filter,
  search,
  onFilterChange,
  onSearchChange,
  onAsk,
  onOpenOrder,
}: {
  tasks: QueueTask[];
  total: number;
  loading: boolean;
  error?: string;
  retry: () => void;
  filter: QueueFilter;
  search: string;
  onFilterChange: (value: QueueFilter) => void;
  onSearchChange: (value: string) => void;
  onAsk: (question: string) => void;
  onOpenOrder: (task: QueueTask) => void;
}) {
  return (
    <div className="ops-section-content">
      <div className="ops-section-heading">
        <div>
          <p className="eyebrow">ƯU TIÊN THEO FIXTURE</p>
          <h2>Hàng đợi vận hành</h2>
          <p>Chọn một việc để mở đơn trong Studio hoặc yêu cầu Agent chuẩn bị checklist.</p>
        </div>
        <StatusLabel text={`${total} việc mẫu`} tone="info" />
      </div>

      <Panel className="ops-queue-browser">
        <div className="ops-queue-toolbar">
          <label className="ops-search-field">
            <span>Tìm đơn hoặc nội dung việc</span>
            <span className="ops-search-control">
              <Icon name="search" size={17} />
              <input
                type="search"
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder="RT-1024, barcode, tên việc..."
              />
            </span>
          </label>
          <Button type="button" variant="secondary" onClick={retry} disabled={loading}>
            <Icon name="refresh" size={16} /> Tải lại fixture
          </Button>
        </div>
        <div className="ops-queue-filters" role="group" aria-label="Lọc loại việc">
          {queueFilterOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={filter === option.value}
              className={filter === option.value ? 'active' : ''}
              onClick={() => onFilterChange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <QueueContent
          tasks={tasks}
          loading={loading}
          error={error}
          retry={retry}
          onAsk={onAsk}
          onOpenOrder={onOpenOrder}
        />
        <p className="fixture-caption">
          Các mốc hạn và nhân viên phụ trách lấy từ fixture; Agent chưa nhận sự kiện hoặc cập nhật dữ liệu.
        </p>
      </Panel>
    </div>
  );
}

function QueueContent({
  tasks,
  loading,
  error,
  retry,
  onAsk,
  onOpenOrder,
  compact = false,
}: {
  tasks: QueueTask[];
  loading: boolean;
  error?: string;
  retry: () => void;
  onAsk: (question: string) => void;
  onOpenOrder: (task: QueueTask) => void;
  compact?: boolean;
}) {
  if (loading)
    return (
      <div className="ops-queue-loading" role="status" aria-label="Đang tải hàng đợi fixture">
        <div className="shimmer" />
        <div className="shimmer" />
        <div className="shimmer" />
      </div>
    );

  if (error)
    return (
      <div className="ops-queue-error" role="alert">
        <div>
          <strong>Không tải được hàng đợi fixture</strong>
          <p>{error}</p>
        </div>
        <Button type="button" variant="secondary" onClick={retry}>
          Thử lại
        </Button>
      </div>
    );

  if (tasks.length === 0)
    return (
      <div className="ops-empty-state">
        <span className="ops-empty-mark" aria-hidden="true"><Icon name="check" size={21} /></span>
        <h3>{compact ? 'Không có việc phù hợp trong fixture' : 'Không tìm thấy việc phù hợp'}</h3>
        <p>Đổi bộ lọc hoặc chọn tình huống bình thường trong thanh kiểm tra UI fixture.</p>
      </div>
    );

  return (
    <div className={`ops-task-list ${compact ? 'ops-task-list--compact' : ''}`}>
      {tasks.map((task) => (
        <article className="ops-task-card" key={task.id}>
          <div className="ops-task-main">
            <div className="ops-task-kicker">
              <span>{task.orderId}</span>
              <StatusLabel text={task.urgency} tone={taskTone(task)} />
            </div>
            <h3>{task.task}</h3>
            <p>
              {task.customer} <span aria-hidden="true">·</span> {task.due}
              <span aria-hidden="true">·</span>{' '}
              {task.owner === 'Chưa gán' ? 'Chưa phân công' : `Phụ trách ${task.owner}`}
            </p>
          </div>
          <div className="ops-task-actions">
            <Button type="button" variant="quiet" onClick={() => onAsk(taskQuestion(task))}>
              Hỏi Agent
            </Button>
            <Button type="button" variant="secondary" onClick={() => onOpenOrder(task)}>
              Mở đơn <Icon name="arrow" size={15} />
            </Button>
          </div>
        </article>
      ))}
    </div>
  );
}

function RunbooksSection({ onAsk }: { onAsk: (question: string) => void }) {
  return (
    <div className="ops-section-content">
      <div className="ops-section-heading">
        <div>
          <p className="eyebrow">CHECKLIST CÓ NGUỒN</p>
          <h2>Quy trình vận hành</h2>
          <p>Các bước tham khảo để nhân viên đối chiếu; nội dung chưa được xác nhận được đánh dấu riêng.</p>
        </div>
        <StatusLabel text="Nhân viên quyết định" tone="info" />
      </div>

      <div className="ops-runbook-grid">
        {runbooks.map((runbook) => (
          <Panel className="ops-runbook-card" key={runbook.id}>
            <div className="ops-runbook-head">
              <span className="ops-runbook-category">{runbook.category}</span>
              <StatusLabel text={runbook.status} tone={runbook.tone} />
            </div>
            <h3>{runbook.title}</h3>
            <p className="ops-runbook-summary">{runbook.summary}</p>
            <ol className="ops-runbook-steps">
              {runbook.steps.map((step, index) => (
                <li key={step}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <p>{step}</p>
                </li>
              ))}
            </ol>
            <details className="ops-runbook-sources">
              <summary>
                <Icon name="pin" size={15} />
                {runbook.sources.length} nguồn tham khảo
                <Icon name="chevron" size={15} />
              </summary>
              <SourceList items={runbook.sources} />
            </details>
            <Button type="button" variant="secondary" onClick={() => onAsk(runbook.question)}>
              Hỏi Agent về quy trình <Icon name="arrow" size={15} />
            </Button>
          </Panel>
        ))}
      </div>
    </div>
  );
}

function KnowledgeSection({
  sources: sourceList,
  search,
  showUnverifiedOnly,
  onSearchChange,
  onToggleUnverified,
}: {
  sources: KnowledgeSource[];
  search: string;
  showUnverifiedOnly: boolean;
  onSearchChange: (value: string) => void;
  onToggleUnverified: () => void;
}) {
  return (
    <div className="ops-section-content">
      <div className="ops-section-heading">
        <div>
          <p className="eyebrow">KNOWLEDGE BASE · BẢN DEMO</p>
          <h2>Nguồn tri thức</h2>
          <p>Danh mục tài liệu Ops Agent và checklist DEMO. Chưa có ingestion, indexing hay đồng bộ tự động.</p>
        </div>
        <StatusLabel text="3 nguồn khai báo tĩnh" tone="neutral" />
      </div>

      <div className="ops-knowledge-controls">
        <label className="ops-search-field">
          <span>Tìm theo tài liệu hoặc chủ đề</span>
          <span className="ops-search-control">
            <Icon name="search" size={17} />
            <input
              type="search"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Ví dụ: thanh toán, giao trả..."
            />
          </span>
        </label>
        <button
          type="button"
          className={`ops-toggle-filter ${showUnverifiedOnly ? 'active' : ''}`}
          aria-pressed={showUnverifiedOnly}
          onClick={onToggleUnverified}
        >
          Chỉ xem nguồn cần xác minh
        </button>
      </div>

      {sourceList.length === 0 ? (
        <div className="ops-empty-state ops-knowledge-empty">
          <h3>Không tìm thấy nguồn phù hợp</h3>
          <p>Thử từ khóa khác hoặc bỏ bộ lọc nguồn cần xác minh.</p>
        </div>
      ) : (
        <div className="ops-source-grid">
          {sourceList.map((source) => (
            <article className="ops-source-card" key={source.id}>
              <div className="ops-source-card-head">
                <span className="ops-runbook-category">{source.kind}</span>
                <StatusLabel text={source.status} tone={source.tone} />
              </div>
              <h3>{source.title}</h3>
              <p className="ops-source-date">{source.detail}</p>
              <span className="ops-source-coverage">{source.coverage}</span>
              <details className="ops-source-excerpt">
                <summary>Xem ghi chú nguồn</summary>
                <p>{source.excerpt}</p>
              </details>
            </article>
          ))}
        </div>
      )}

      <div className="ops-inline-note" role="note">
        <Icon name="clock" size={17} />
        Chưa có trạng thái đồng bộ hoặc truy vấn live. Tài liệu định hướng và checklist DEMO chưa phải SOP vận hành đã duyệt.
      </div>
    </div>
  );
}

function ActivitySection() {
  const auditFields = [
    'Actor và phạm vi',
    'Request / correlation ID',
    'Nguồn, phiên bản và thời điểm',
    'Tool/action cùng kết quả xác nhận',
  ];

  return (
    <div className="ops-section-content">
      <div className="ops-section-heading">
        <div>
          <p className="eyebrow">OBSERVABILITY</p>
          <h2>Nhật ký hoạt động</h2>
          <p>Đối soát lượt chạy, nguồn được dùng và kết quả từ hệ thống đích khi runtime được cấu hình.</p>
        </div>
        <StatusLabel text="Audit store chưa kết nối" tone="neutral" />
      </div>

      <Panel className="ops-activity-panel">
        <div className="ops-empty-state ops-activity-empty">
          <span className="ops-empty-mark" aria-hidden="true"><Icon name="clock" size={21} /></span>
          <h3>Chưa có nhật ký runtime</h3>
          <p>
            Bản hiện tại chưa có orchestration backend, provider hay audit store. Không có lượt chạy thật để hiển thị.
          </p>
        </div>
        <div className="ops-audit-contract">
          <div>
            <p className="eyebrow">TRƯỜNG AUDIT DỰ KIẾN</p>
            <h3>Thông tin cần lưu khi bật runtime</h3>
          </div>
          <ul>
            {auditFields.map((field) => <li key={field}>{field}</li>)}
          </ul>
        </div>
        <p className="fixture-caption">
          Chưa lưu hội thoại vào server. Nội dung chat chỉ nằm trong state của phiên trình duyệt hiện tại.
        </p>
      </Panel>
    </div>
  );
}

function AssistantSection({
  branch,
  question,
  messages,
  latestMessageRef,
  onQuestionChange,
  onSubmit,
  onAsk,
  onReset,
}: {
  branch: string;
  question: string;
  messages: AgentMessage[];
  latestMessageRef: React.RefObject<HTMLLIElement | null>;
  onQuestionChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onAsk: (question: string) => void;
  onReset: () => void;
}) {
  return (
    <div className="ops-agent-layout ops-assistant-layout">
      <section className="feature-panel ops-chat-panel" aria-label="Cuộc trò chuyện với Ops Agent">
        <div className="ops-chat-header">
          <div className="ops-agent-identity">
            <span className="ops-agent-avatar" aria-hidden="true"><Icon name="spark" size={20} /></span>
            <div>
              <h2>Hỏi Ops Agent</h2>
              <span className="ops-agent-subtitle">Trợ lý quy trình · phản hồi mẫu có nguồn</span>
            </div>
          </div>
          <Button
            type="button"
            variant="secondary"
            className="ops-new-chat"
            disabled={messages.length === 0}
            onClick={onReset}
            aria-label="Bắt đầu cuộc trò chuyện mới"
          >
            <Icon name="refresh" size={16} /> Cuộc trò chuyện mới
          </Button>
        </div>

        <div className="ops-chat-body">
          {messages.length === 0 ? (
            <div className="ops-welcome">
              <span className="ops-welcome-mark" aria-hidden="true"><Icon name="spark" size={24} /></span>
              <p className="eyebrow">HỖ TRỢ NHÂN VIÊN</p>
              <h2>Bạn cần xử lý việc gì?</h2>
              <p className="ops-welcome-copy">
                Chọn quy trình mẫu để xem Agent trình bày câu trả lời và căn cứ. Câu trả lời hiện là fixture, chưa gọi mô hình.
              </p>
              <div className="ops-suggestions" aria-label="Câu hỏi gợi ý">
                {suggestedQuestions.map((item) => (
                  <button type="button" className="ops-suggestion" key={item.category} onClick={() => onAsk(item.prompt)}>
                    <span>{item.category}</span>
                    <strong>{item.title}</strong>
                    <Icon name="arrow" size={16} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <ol className="ops-messages" aria-label="Tin nhắn" role="log" aria-live="polite">
              {messages.map((message, index) => (
                <li
                  key={message.id}
                  className={`ops-message ops-message--${message.role}`}
                  ref={index === messages.length - 1 ? latestMessageRef : undefined}
                >
                  {message.role === 'assistant' && (
                    <span className="ops-message-avatar" aria-hidden="true"><Icon name="spark" size={15} /></span>
                  )}
                  <div className="ops-message-content">
                    <span className="ops-message-author">{message.role === 'assistant' ? 'Ops Agent · demo' : 'Bạn'}</span>
                    <div className="ops-message-bubble">
                      <p>{message.text}</p>
                      {message.demoOnly && <span className="ops-demo-inline">Phản hồi demo · chưa có model/provider</span>}
                    </div>
                    {message.sources && <SourceDetails items={message.sources} />}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>

        <form className="ops-composer" onSubmit={onSubmit}>
          <label htmlFor="ops-question">Nhập câu hỏi cho Ops Agent</label>
          <div className="ops-composer-row">
            <textarea
              id="ops-question"
              value={question}
              onChange={(event) => onQuestionChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  onAsk(question);
                }
              }}
              placeholder="Ví dụ: Chuyển khoản đang chờ đối soát có được tính là đã thu không?"
              rows={2}
              aria-describedby="ops-composer-help"
            />
            <Button type="submit" disabled={!question.trim()} aria-label="Gửi câu hỏi">
              Gửi <Icon name="arrow" size={16} />
            </Button>
          </div>
          <p id="ops-composer-help" className="ops-composer-help">
            Enter để gửi · Shift + Enter để xuống dòng. Bản demo không gửi câu hỏi ra ngoài.
          </p>
        </form>
      </section>

      <aside className="ops-agent-context" aria-label="Ngữ cảnh và giới hạn Agent">
        <Panel title="Phạm vi phiên demo" className="ops-context-panel">
          <div className="ops-context-branch">
            <span className="ops-context-label">Chi nhánh fixture</span>
            <strong>{branch}</strong>
            <span className="ops-context-note">Chỉ dùng để lọc fixture trong giao diện.</span>
          </div>
          <div className="ops-source-state">
            <span className="ops-source-state-dot" aria-hidden="true" />
            <div>
              <strong>Agent chưa kết nối runtime</strong>
              <span>Không đọc nguồn live, không gọi tool và không ghi dữ liệu.</span>
            </div>
          </div>
        </Panel>
        <Panel title="Nguồn câu trả lời" className="ops-context-panel">
          <ul className="ops-source-list">
            {knowledgeSources.map((source) => (
              <li key={source.id}>
                <span className="ops-source-file">{source.title}</span>
                <span className="ops-source-meta">{source.detail}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Ranh giới thao tác" className="ops-context-panel ops-principles-panel">
          <ul className="ops-principles-list">
            <li>Không xác nhận đơn hoặc cập nhật trạng thái.</li>
            <li>Không kết luận phí hoặc số tiền hoàn.</li>
            <li>Gợi ý luôn cần nhân viên đối chiếu nguồn.</li>
          </ul>
        </Panel>
      </aside>
    </div>
  );
}

function SourceList({ items }: { items: SourceNote[] }) {
  return (
    <ul className="ops-runbook-source-list">
      {items.map((item) => (
        <li key={`${item.title}-${item.detail}`}>
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
          <StatusLabel text={item.status} tone={item.tone} />
        </li>
      ))}
    </ul>
  );
}

function SourceDetails({ items }: { items: SourceNote[] }) {
  return (
    <details className="ops-citations">
      <summary>
        <Icon name="pin" size={15} />
        {items.length} nguồn tham khảo
        <Icon name="chevron" size={15} />
      </summary>
      <ul>
        {items.map((item) => (
          <li key={`${item.title}-${item.detail}`}>
            <div className="ops-citation-heading">
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </div>
            <p>{item.excerpt}</p>
            <StatusLabel text={item.status} tone={item.tone} />
          </li>
        ))}
      </ul>
    </details>
  );
}
