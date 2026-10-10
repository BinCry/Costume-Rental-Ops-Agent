import type {
  BookingDraft,
  CatalogItem,
  DemoScenario,
  Order,
  QueueTask,
  QuoteSnapshot,
  UnitOption,
} from './types';
import { FixtureIssue } from './types';

export const fixturePeriod = { pickup: '2026-10-10T09:00', returnAt: '2026-10-12T09:00' };
export const fixtureClock = new Date('2026-10-03T15:30:00+07:00');

export const branches = ['Chi nhánh Quận 1', 'Chi nhánh Thủ Đức'];

const catalog: CatalogItem[] = [
  {
    id: 'ao-dai-lina',
    name: 'Áo dài Lina',
    category: 'Áo dài',
    sizes: ['S', 'M'],
    colors: ['Hồng phấn'],
    imagePosition: 'left',
    priceFrom: 320000,
    depositFrom: 500000,
    availableAtFixturePeriod: true,
    description: 'Tà áo mềm nhẹ cho những khoảnh khắc thật riêng.',
  },
  {
    id: 'suit-aria',
    name: 'Suit Aria',
    category: 'Suit',
    sizes: ['M', 'L'],
    colors: ['Kem'],
    imagePosition: 'center',
    priceFrom: 420000,
    depositFrom: 700000,
    availableAtFixturePeriod: true,
    description: 'Đường cắt hiện đại, dễ phối cho nhiều dịp.',
  },
  {
    id: 'dam-rouge',
    name: 'Đầm Rouge',
    category: 'Đầm',
    sizes: ['S', 'M'],
    colors: ['Đỏ berry'],
    imagePosition: 'right',
    priceFrom: 390000,
    depositFrom: 600000,
    availableAtFixturePeriod: false,
    description: 'Sắc berry nổi bật với phom dáng tối giản.',
  },
  {
    id: 'ao-dai-may',
    name: 'Áo dài Mây',
    category: 'Áo dài',
    sizes: ['M', 'L'],
    colors: ['Trắng'],
    imagePosition: 'missing',
    priceFrom: 280000,
    depositFrom: 450000,
    availableAtFixturePeriod: true,
    description: 'Một lựa chọn nhẹ nhàng cho ngày đặc biệt.',
  },
];

const q1Units: UnitOption[] = [
  {
    code: 'BC-001',
    variant: 'Áo dài Lina · M / Hồng phấn',
    status: 'READY',
    availableAtFixturePeriod: true,
  },
  {
    code: 'BC-012',
    variant: 'Áo dài Lina · M / Hồng phấn',
    status: 'READY',
    availableAtFixturePeriod: true,
  },
  {
    code: 'BC-014',
    variant: 'Áo dài Lina · M / Hồng phấn',
    status: 'READY',
    availableAtFixturePeriod: true,
  },
  {
    code: 'BC-018',
    variant: 'Áo dài Lina · M / Hồng phấn',
    status: 'CLEANING',
    availableAtFixturePeriod: false,
    note: 'Đang vệ sinh; chưa có giờ sẵn sàng trong fixture',
  },
  {
    code: 'BC-019',
    variant: 'Áo dài Lina · M / Hồng phấn',
    status: 'REPAIR',
    availableAtFixturePeriod: false,
    note: 'Đang sửa chữa',
  },
];

const orders: Order[] = [
  {
    id: 'RT-1024',
    status: 'PENDING_CONFIRMATION',
    version: 3,
    customer: 'Nguyễn An',
    phone: '0900 000 124',
    branch: branches[0],
    pickup: '10/10/2026 · 09:00',
    returnAt: '12/10/2026 · 09:00',
    dayPolicy: 'Chu kỳ 24 giờ · policy fixture',
    items: [
      { id: '01', costume: 'Áo dài Lina', variant: 'M / Hồng phấn' },
      { id: '02', costume: 'Áo dài Lina', variant: 'M / Hồng phấn' },
    ],
    money: [
      { label: 'Tiền thuê', amount: 1280000, status: 'Chưa thu', tone: 'neutral' },
      { label: 'Tiền cọc', amount: 1000000, status: 'Chưa thu', tone: 'neutral' },
      { label: 'Phụ phí / hoàn', amount: 0, status: 'Chưa phát sinh', tone: 'neutral' },
    ],
    history: ['03/10 · Khách gửi yêu cầu thuê', '03/10 · Chờ nhân viên kiểm tra lịch và gán bộ'],
    note: 'Cần đủ 2 bộ cùng size.',
    eligibleUnits: q1Units,
  },
  {
    id: 'RT-1028',
    status: 'READY_FOR_PICKUP',
    version: 5,
    customer: 'Trần Minh',
    phone: '0900 000 128',
    branch: branches[0],
    pickup: '03/10/2026 · 16:30',
    returnAt: '05/10/2026 · 16:30',
    dayPolicy: 'Chu kỳ 24 giờ · policy fixture',
    items: [
      {
        id: '01',
        costume: 'Suit Aria',
        variant: 'M / Kem',
        unitCode: 'BC-028',
        unitStatus: 'Sẵn sàng',
      },
    ],
    money: [
      { label: 'Tiền thuê', amount: 840000, status: 'Chưa thu', tone: 'neutral' },
      { label: 'Tiền cọc', amount: 700000, status: 'Chưa thu', tone: 'neutral' },
      { label: 'Phụ phí / hoàn', amount: 0, status: 'Chưa phát sinh', tone: 'neutral' },
    ],
    history: ['03/10 · Đã xác nhận và gán BC-028', '03/10 · Sẵn sàng nhận đồ'],
    note: 'Khách nhận tại quầy Quận 1.',
    eligibleUnits: [],
  },
  {
    id: 'RT-1031',
    status: 'ACTIVE',
    version: 7,
    customer: 'Lê Hà',
    phone: '0900 000 131',
    branch: branches[0],
    pickup: '01/10/2026 · 14:00',
    returnAt: '03/10/2026 · 14:00',
    dayPolicy: 'Chu kỳ 24 giờ · policy fixture',
    items: [
      {
        id: '01',
        costume: 'Đầm Rouge',
        variant: 'S / Đỏ berry',
        unitCode: 'BC-031',
        unitStatus: 'Đang ở khách',
      },
    ],
    money: [
      { label: 'Tiền thuê', amount: 780000, status: 'Đã thu', tone: 'success' },
      { label: 'Tiền cọc', amount: 600000, status: 'Đang giữ', tone: 'info' },
      { label: 'Phụ phí / hoàn', amount: 0, status: 'Chưa phát sinh', tone: 'neutral' },
    ],
    history: ['01/10 · Đã giao BC-031', '01/10 · Đã thu thuê và cọc bằng tiền mặt'],
    note: 'Kiểm tra phụ kiện khi trả.',
    eligibleUnits: [],
  },
  {
    id: 'RT-1033',
    status: 'RETURN_INSPECTION',
    version: 9,
    customer: 'Phạm Vy',
    phone: '0900 000 133',
    branch: branches[0],
    pickup: '29/09/2026 · 09:00',
    returnAt: '01/10/2026 · 09:00',
    dayPolicy: 'Chu kỳ 24 giờ · policy fixture',
    items: [
      {
        id: '01',
        costume: 'Áo dài Lina',
        variant: 'S / Hồng phấn',
        unitCode: 'BC-033',
        unitStatus: 'Đang kiểm tra',
      },
    ],
    money: [
      { label: 'Tiền thuê', amount: 640000, status: 'Đã thu', tone: 'success' },
      { label: 'Tiền cọc', amount: 500000, status: 'Đang giữ', tone: 'info' },
      { label: 'Phụ phí / hoàn', amount: 0, status: 'Chờ quyết toán', tone: 'warning' },
    ],
    history: ['29/09 · Đã giao BC-033', '01/10 · Đã nhận lại bộ; đang kiểm tra'],
    note: 'Kiểm tra vết bẩn ở tà áo.',
    eligibleUnits: [],
  },
  {
    id: 'RT-1035',
    status: 'ACTIVE',
    version: 4,
    customer: 'Đỗ Nhi',
    phone: '0900 000 135',
    branch: branches[0],
    pickup: '02/10/2026 · 10:00',
    returnAt: '04/10/2026 · 10:00',
    dayPolicy: 'Chu kỳ 24 giờ · policy fixture',
    items: [
      {
        id: '01',
        costume: 'Áo dài Lina',
        variant: 'M / Hồng phấn',
        unitCode: 'BC-035',
        unitStatus: 'Đang ở khách',
      },
      {
        id: '02',
        costume: 'Áo dài Lina',
        variant: 'M / Hồng phấn',
        unitCode: 'BC-036',
        unitStatus: 'Đang ở khách',
      },
    ],
    money: [
      { label: 'Tiền thuê', amount: 1280000, status: 'Đã thu', tone: 'success' },
      { label: 'Tiền cọc', amount: 1000000, status: 'Đang giữ', tone: 'info' },
      { label: 'Phụ phí / hoàn', amount: 0, status: 'Chưa phát sinh', tone: 'neutral' },
    ],
    history: ['02/10 · Đã giao BC-035 và BC-036', '02/10 · Đã thu thuê và cọc'],
    note: 'Fixture để kiểm tra luồng trả từng bộ; chưa quyết toán.',
    eligibleUnits: [],
  },
];

const queue: QueueTask[] = [
  {
    id: 'q1',
    orderId: 'RT-1031',
    due: '03/10 · 14:00',
    customer: 'Lê Hà',
    phone: '0900 000 131',
    barcode: 'BC-031',
    task: 'Theo dõi trả đồ quá hạn',
    urgency: 'Quá hạn',
    group: 'Quá hạn',
    kind: 'overdue',
    owner: 'Thu',
    branch: branches[0],
    workDate: '2026-10-03',
    status: 'Cần xử lý',
  },
  {
    id: 'q2',
    orderId: 'RT-1028',
    due: '03/10 · 16:30',
    customer: 'Trần Minh',
    phone: '0900 000 128',
    barcode: 'BC-028',
    task: 'Giao bộ BC-028, thu thuê và cọc',
    urgency: 'Trong 2 giờ',
    group: 'Trong 2 giờ tới',
    kind: 'handover',
    owner: 'Hà',
    branch: branches[0],
    workDate: '2026-10-03',
    status: 'Cần xử lý',
  },
  {
    id: 'q3',
    orderId: 'RT-1033',
    due: '03/10 · 16:00',
    customer: 'Phạm Vy',
    phone: '0900 000 133',
    barcode: 'BC-033',
    task: 'Kiểm tra đồ trả và quyết toán cọc',
    urgency: 'Hôm nay',
    group: 'Hôm nay',
    kind: 'return',
    owner: 'Chưa gán',
    branch: branches[0],
    workDate: '2026-10-03',
    status: 'Đang xử lý',
  },
  {
    id: 'q4',
    orderId: 'RT-1024',
    due: '03/10 · 08:30',
    customer: 'Nguyễn An',
    phone: '0900 000 124',
    task: 'Kiểm tra lịch, chọn 2 bộ và xác nhận',
    urgency: 'Chờ lâu',
    group: 'Chờ xác nhận lâu',
    kind: 'pending',
    owner: 'Chưa gán',
    branch: branches[0],
    workDate: '2026-10-03',
    status: 'Cần xử lý',
  },
  {
    id: 'q5',
    orderId: 'RT-1028',
    due: '03/10 · 16:45',
    customer: 'Trần Minh',
    phone: '0900 000 128',
    barcode: 'BC-028',
    task: 'Đối soát chuyển khoản',
    urgency: 'Cần xử lý',
    group: 'Hôm nay',
    kind: 'payment',
    owner: 'Hà',
    branch: branches[0],
    workDate: '2026-10-03',
    status: 'Cần xử lý',
  },
];

const pause = (ms = 430) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));
let nextDemoRequest = 2048;
const failNetwork = (scenario: DemoScenario) => {
  if (scenario === 'error')
    throw new FixtureIssue(
      'NETWORK',
      'Không tải được dữ liệu fixture. Bộ lọc và dữ liệu đang nhập vẫn được giữ.',
    );
};

export const fixtureAdapter = {
  async listCatalog(scenario: DemoScenario): Promise<CatalogItem[]> {
    await pause();
    failNetwork(scenario);
    return scenario === 'empty' ? [] : catalog;
  },
  async listQueue(scenario: DemoScenario): Promise<QueueTask[]> {
    await pause();
    failNetwork(scenario);
    return scenario === 'empty' ? [] : queue;
  },
  async listOrders(scenario: DemoScenario): Promise<Order[]> {
    await pause();
    failNetwork(scenario);
    return scenario === 'empty' ? [] : orders;
  },
  async getQuote(draft: BookingDraft, scenario: DemoScenario): Promise<QuoteSnapshot> {
    await pause();
    failNetwork(scenario);
    if (scenario === 'conflict')
      throw new FixtureIssue(
        'QUOTE_EXPIRED',
        'Báo giá đã hết hiệu lực hoặc bộ vừa hết. Vui lòng cập nhật giá và lịch trước khi gửi lại.',
      );
    if (
      draft.branch !== branches[0] ||
      draft.pickup !== fixturePeriod.pickup ||
      draft.returnAt !== fixturePeriod.returnAt ||
      ![1, 2].includes(draft.quantity)
    ) {
      throw new FixtureIssue(
        'NO_FIXTURE_QUOTE',
        'Chưa có báo giá fixture cho lựa chọn này. Thông tin đã nhập được giữ để đối chiếu khi nối API thật.',
      );
    }
    const quoteFixtures: Record<
      string,
      Record<
        number,
        { pricePerDay: number; rental: number; deposit: number; amountDueAtPickup: number }
      >
    > = {
      'ao-dai-lina': {
        1: { pricePerDay: 320000, rental: 640000, deposit: 500000, amountDueAtPickup: 1140000 },
        2: { pricePerDay: 320000, rental: 1280000, deposit: 1000000, amountDueAtPickup: 2280000 },
      },
      'suit-aria': {
        1: { pricePerDay: 420000, rental: 840000, deposit: 700000, amountDueAtPickup: 1540000 },
      },
      'ao-dai-may': {
        1: { pricePerDay: 280000, rental: 560000, deposit: 450000, amountDueAtPickup: 1010000 },
      },
    };
    const item = catalog.find((entry) => entry.id === draft.costumeId);
    if (!item?.availableAtFixturePeriod)
      throw new FixtureIssue(
        'UNAVAILABLE',
        'Không còn bộ phù hợp ở chi nhánh này trong thời gian đã chọn. Hãy đổi ngày, chi nhánh hoặc mẫu.',
      );
    if (
      !item.sizes.map((size) => `${size} / ${item.colors[0]}`).includes(draft.variant) ||
      !quoteFixtures[draft.costumeId]?.[draft.quantity]
    )
      throw new FixtureIssue(
        'NO_FIXTURE_QUOTE',
        'Chưa có báo giá fixture cho biến thể và số bộ này. Lựa chọn vẫn được giữ.',
      );
    return {
      id: `Q-DEMO-${draft.costumeId}-${draft.quantity}`,
      expiresAt: '10/10/2026 · 08:30 (fixture)',
      daysLabel: '2 ngày · snapshot fixture',
      quantity: draft.quantity,
      discount: 0,
      policy: 'Chu kỳ 24 giờ · snapshot fixture',
      ...quoteFixtures[draft.costumeId][draft.quantity],
    };
  },
  async submitBooking(
    _draft: BookingDraft,
    quote: QuoteSnapshot,
    scenario: DemoScenario,
  ): Promise<string> {
    await pause(680);
    failNetwork(scenario);
    if (scenario === 'conflict')
      throw new FixtureIssue(
        'QUOTE_EXPIRED',
        'Báo giá vừa hết hiệu lực. Hãy tải lại báo giá; yêu cầu chưa được gửi.',
      );
    if (!quote.id)
      throw new FixtureIssue('QUOTE_MISSING', 'Cần báo giá còn hiệu lực trước khi gửi.');
    return `RT-DEMO-${nextDemoRequest++}`;
  },
  async confirmOrder(
    orderId: string,
    version: number,
    units: string[],
    scenario: DemoScenario,
  ): Promise<void> {
    await pause(680);
    failNetwork(scenario);
    if (scenario === 'permission')
      throw new FixtureIssue(
        'PERMISSION',
        'Bạn không còn quyền xử lý đơn tại chi nhánh này. Chưa có thay đổi nào được gửi.',
      );
    if (scenario === 'cancelled')
      throw new FixtureIssue(
        'CANCELLED',
        'Khách đã hủy đơn khi bạn đang duyệt. Không thể xác nhận; hãy xem lịch sử đơn.',
      );
    if (scenario === 'version')
      throw new FixtureIssue(
        'VERSION',
        'Đơn đã thay đổi từ lúc bạn mở. Phiên bản mới cần được kiểm tra trước khi thao tác lại.',
      );
    if (scenario === 'conflict')
      throw new FixtureIssue(
        'UNIT_CONFLICT',
        'BC-001 vừa hết khả dụng. Đã giữ các lựa chọn khác; hãy tải lại bộ còn trống và chọn mã khác.',
      );
    const order = orders.find((entry) => entry.id === orderId);
    if (
      order?.status !== 'PENDING_CONFIRMATION' ||
      version !== order.version ||
      units.length !== order.items.length ||
      new Set(units).size !== units.length ||
      units.some(
        (code) =>
          !order.eligibleUnits.some(
            (unit) =>
              unit.code === code && unit.status === 'READY' && unit.availableAtFixturePeriod,
          ),
      )
    )
      throw new FixtureIssue(
        'INVALID_FIXTURE',
        'Lựa chọn không khớp snapshot fixture hoặc bộ không khả dụng; chưa ghi thay đổi.',
      );
  },
  async lookupBarcode(
    code: string,
    branch: string,
    scenario: DemoScenario,
  ): Promise<{ order: Order; itemIndex: number }> {
    await pause(360);
    failNetwork(scenario);
    if (scenario === 'barcodeMissing' || !code.trim())
      throw new FixtureIssue(
        'BARCODE_MISSING',
        'Không tìm thấy mã bộ này. Kiểm tra và nhập lại mã; đơn đang mở vẫn được giữ.',
      );
    if (scenario === 'barcodeOtherBranch' || code.trim().toUpperCase() === 'BC-205')
      throw new FixtureIssue(
        'OTHER_BRANCH',
        'Mã bộ này thuộc Chi nhánh Thủ Đức. Hãy báo quản lý hoặc chuyển đúng chi nhánh có quyền.',
      );
    const order = orders.find(
      (entry) =>
        entry.branch === branch &&
        entry.items.some((item) => item.unitCode === code.trim().toUpperCase()),
    );
    if (!order)
      throw new FixtureIssue(
        'BARCODE_MISSING',
        'Không tìm thấy mã bộ này trong chi nhánh đang chọn. Kiểm tra và nhập lại mã.',
      );
    return {
      order,
      itemIndex: order.items.findIndex((item) => item.unitCode === code.trim().toUpperCase()),
    };
  },
};

export const fixtureCatalog = catalog;
export const fixtureOrders = orders;
export const returnSnapshots: Record<
  string,
  {
    heldDeposit: number;
    lateFee: number;
    damageFee: number;
    missingFee: number;
    offset: number;
    refunded: number;
    remainingRefund: number;
  }
> = {
  'RT-1031': {
    heldDeposit: 600000,
    lateFee: 0,
    damageFee: 0,
    missingFee: 0,
    offset: 0,
    refunded: 0,
    remainingRefund: 600000,
  },
  'RT-1033': {
    heldDeposit: 500000,
    lateFee: 0,
    damageFee: 120000,
    missingFee: 0,
    offset: 120000,
    refunded: 0,
    remainingRefund: 380000,
  },
};
