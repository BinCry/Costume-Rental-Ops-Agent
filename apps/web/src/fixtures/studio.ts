import { fixtureCatalog, fixtureOrders, fixtureClock } from './adapter';
import {
  FixtureIssue,
  type BookingDraft,
  type DemoScenario,
  type OrderStatus,
  type QuoteSnapshot,
} from './types';

export type UnitStatus = 'INBOUND' | 'READY' | 'CLEANING' | 'REPAIR' | 'IN_TRANSFER' | 'RETIRED';
export type TransferStatus =
  'REQUESTED' | 'APPROVED' | 'IN_TRANSIT' | 'RECEIVED' | 'REJECTED' | 'CANCELLED';
export type CaseStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';
export type UserStatus = 'PENDING' | 'ACTIVE' | 'LOCKED' | 'INACTIVE';
export interface Variant {
  code: string;
  modelId: string;
  size: string;
  color: string;
  edition?: string;
  fit: string;
  price: number;
  deposit: number;
  replacement: number;
}
export interface CostumeDetail {
  id: string;
  name: string;
  category: string;
  description: string;
  material: string;
  accessories: string[];
  imagePosition: 'left' | 'center' | 'right' | 'missing';
  variants: Variant[];
}
export interface UnitBlock {
  type: 'CLEANING' | 'REPAIR' | 'INSPECTION';
  from: string;
  until: string;
  reason: string;
  status: 'PLANNED' | 'IN_PROGRESS' | 'COMPLETED';
}
export interface Unit {
  barcode: string;
  variantCode: string;
  model: string;
  variant: string;
  branch: string;
  status: UnitStatus;
  condition: string;
  available: boolean;
  blocks: UnitBlock[];
  history: string[];
}
export interface Customer {
  code: string;
  name: string;
  phone: string;
  email: string;
  preferredBranch: string;
  history: string[];
  interactions: string[];
}
export interface Employee {
  code: string;
  name: string;
  email: string;
  accountStatus: UserStatus;
  employmentStatus: 'ACTIVE' | 'ON_LEAVE' | 'TERMINATED';
  assignments: { branch: string; roleCode: string }[];
}
export interface Permission {
  code: string;
  group: string;
  label: string;
  description: string;
  scope: 'OWN' | 'BRANCH' | 'ALL';
}
export interface Role {
  code: string;
  name: string;
  group: 'ADMIN' | 'STAFF' | 'CUSTOMER';
  permissions: string[];
}
export interface Branch {
  code: string;
  name: string;
  address: string;
  status: 'ACTIVE' | 'INACTIVE';
  timezone: string;
}
export interface Transfer {
  code: string;
  from: string;
  to: string;
  status: TransferStatus;
  units: { barcode: string; out?: string; received?: string; in?: string }[];
  note: string;
  version: number;
  history: string[];
}
export interface Case {
  code: string;
  customerCode: string;
  branch: string;
  orderId?: string;
  subject: string;
  description: string;
  priority: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
  status: CaseStatus;
  owner?: string;
  history: string[];
}
export interface Policy {
  code: string;
  from: string;
  to?: string;
  billingMode: 'ROLLING_24_HOURS' | 'CALENDAR_DAY';
  minDays: number;
  maxDays: number;
  quoteHours: number;
  cancelHours: number;
  reason: string;
}
export interface ReportSnapshot {
  branch: string;
  period: string;
  rentalCount: number;
  rentalRevenue: number;
  depositsHeld: number;
  overdueUnits: number;
  transactions: { status: string; count: number }[];
  refunds: { status: string; count: number }[];
}
export interface CustomerOrder {
  id: string;
  customerCode: string;
  status: OrderStatus;
  branch: string;
  pickup: string;
  due: string;
  costume: string;
  variant: string;
  rental: number;
  deposit: number;
  extra: number;
  refund: number;
  rentalStatus: string;
  depositStatus: string;
  refundStatus: string;
  returnStatus: string;
  history: string[];
  reason?: string;
  canCancel: boolean;
}

const details: CostumeDetail[] = fixtureCatalog.map((item, index) => ({
  id: item.id,
  name: item.name,
  category: item.category,
  description: item.description,
  material: ['Lụa pha mềm', 'Twill nhẹ', 'Satin mờ', 'Voan mềm'][index],
  accessories: index === 1 ? ['Áo khoác', 'Quần'] : ['Trang phục chính', 'Phụ kiện đi kèm theo bộ'],
  imagePosition: item.imagePosition,
  variants: item.sizes.map((size, n) => ({
    code: `${item.id.toUpperCase()}-${size}`,
    modelId: item.id,
    size,
    color: item.colors[0],
    edition: n ? 'Tiêu chuẩn' : undefined,
    fit:
      size === 'S' ? 'Dáng ôm vừa, tham khảo số đo tại studio' : 'Dáng vừa, nên thử tại chi nhánh',
    price: item.priceFrom,
    deposit: item.depositFrom,
    replacement: [1700000, 2350000, 1900000, 1500000][index],
  })),
}));

let units: Unit[] = [
  {
    barcode: 'BC-001',
    variantCode: 'AO-DAI-LINA-M',
    model: 'Áo dài Lina',
    variant: 'M / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'GOOD',
    available: true,
    blocks: [],
    history: ['01/10 · Kiểm tra, sẵn sàng cho thuê'],
  },
  {
    barcode: 'BC-012',
    variantCode: 'AO-DAI-LINA-M',
    model: 'Áo dài Lina',
    variant: 'M / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'GOOD',
    available: true,
    blocks: [],
    history: ['02/10 · Nhập kho'],
  },
  {
    barcode: 'BC-014',
    variantCode: 'AO-DAI-LINA-M',
    model: 'Áo dài Lina',
    variant: 'M / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'GOOD',
    available: true,
    blocks: [],
    history: ['02/10 · Kiểm và sẵn sàng cho thuê'],
  },
  {
    barcode: 'BC-018',
    variantCode: 'AO-DAI-LINA-M',
    model: 'Áo dài Lina',
    variant: 'M / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'CLEANING',
    condition: 'FAIR',
    available: false,
    blocks: [
      {
        type: 'CLEANING',
        from: '03/10 08:00',
        until: '04/10 18:00',
        reason: 'Vệ sinh sau lượt thuê',
        status: 'IN_PROGRESS',
      },
    ],
    history: ['03/10 · Bắt đầu vệ sinh'],
  },
  {
    barcode: 'BC-019',
    variantCode: 'AO-DAI-LINA-M',
    model: 'Áo dài Lina',
    variant: 'M / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'REPAIR',
    condition: 'DAMAGED',
    available: false,
    blocks: [
      {
        type: 'REPAIR',
        from: '02/10 09:00',
        until: '06/10 18:00',
        reason: 'Sửa khóa kéo',
        status: 'IN_PROGRESS',
      },
    ],
    history: ['02/10 · Báo hỏng khóa kéo'],
  },
  {
    barcode: 'BC-028',
    variantCode: 'SUIT-ARIA-M',
    model: 'Suit Aria',
    variant: 'M / Kem',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'GOOD',
    available: false,
    blocks: [],
    history: ['03/10 · Đã gán cho RT-1028'],
  },
  {
    barcode: 'BC-031',
    variantCode: 'DAM-ROUGE-S',
    model: 'Đầm Rouge',
    variant: 'S / Đỏ berry',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'GOOD',
    available: false,
    blocks: [],
    history: ['01/10 · Đã giao cho RT-1031'],
  },
  {
    barcode: 'BC-033',
    variantCode: 'AO-DAI-LINA-S',
    model: 'Áo dài Lina',
    variant: 'S / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'FAIR',
    available: false,
    blocks: [],
    history: ['01/10 · Nhận trả, chờ kiểm tra'],
  },
  ...['BC-035', 'BC-036'].map((barcode): Unit => ({
    barcode,
    variantCode: 'AO-DAI-LINA-M',
    model: 'Áo dài Lina',
    variant: 'M / Hồng phấn',
    branch: 'Chi nhánh Quận 1',
    status: 'READY',
    condition: 'GOOD',
    available: false,
    blocks: [],
    history: [`02/10 · Đã giao cho RT-1035 (${barcode})`],
  })),
  {
    barcode: 'BC-205',
    variantCode: 'AO-DAI-MAY-M',
    model: 'Áo dài Mây',
    variant: 'M / Trắng',
    branch: 'Chi nhánh Thủ Đức',
    status: 'IN_TRANSFER',
    condition: 'GOOD',
    available: false,
    blocks: [],
    history: ['01/10 · Nhập kho Thủ Đức'],
  },
  {
    barcode: 'BC-220',
    variantCode: 'SUIT-ARIA-L',
    model: 'Suit Aria',
    variant: 'L / Kem',
    branch: 'Chi nhánh Thủ Đức',
    status: 'INBOUND',
    condition: 'UNINSPECTED',
    available: false,
    blocks: [],
    history: ['03/10 · Chờ kiểm tra nhập kho'],
  },
  {
    barcode: 'BC-223',
    variantCode: 'DAM-ROUGE-M',
    model: 'Đầm Rouge',
    variant: 'M / Đỏ berry',
    branch: 'Chi nhánh Thủ Đức',
    status: 'RETIRED',
    condition: 'POOR',
    available: false,
    blocks: [],
    history: ['29/09 · Ngừng sử dụng'],
  },
];
const customers: Customer[] = [
  {
    code: 'KH-001',
    name: 'Nguyễn An',
    phone: '0900 000 124',
    email: 'an@example.test',
    preferredBranch: 'Chi nhánh Quận 1',
    history: ['RT-1024 · Chờ xác nhận'],
    interactions: ['03/10 · Khách gửi yêu cầu thuê Áo dài Lina'],
  },
  {
    code: 'KH-002',
    name: 'Trần Minh',
    phone: '0900 000 128',
    email: 'minh@example.test',
    preferredBranch: 'Chi nhánh Quận 1',
    history: ['RT-1028 · Sẵn sàng nhận'],
    interactions: ['03/10 · Nhân viên xác nhận giờ nhận đồ'],
  },
  {
    code: 'KH-003',
    name: 'Lê Hà',
    phone: '0900 000 131',
    email: 'ha@example.test',
    preferredBranch: 'Chi nhánh Quận 1',
    history: ['RT-1031 · Đang thuê'],
    interactions: ['01/10 · Đã nhận Đầm Rouge'],
  },
  {
    code: 'KH-004',
    name: 'Phạm Vy',
    phone: '0900 000 133',
    email: 'vy@example.test',
    preferredBranch: 'Chi nhánh Quận 1',
    history: ['RT-1033 · Đang kiểm tra đồ trả'],
    interactions: ['01/10 · Nhận trả, hẹn quyết toán cọc'],
  },
  {
    code: 'KH-005',
    name: 'Đỗ Nhi',
    phone: '0900 000 135',
    email: 'nhi@example.test',
    preferredBranch: 'Chi nhánh Quận 1',
    history: ['RT-1035 · Đang thuê 2 bộ'],
    interactions: ['02/10 · Đã nhận hai bộ Áo dài Lina'],
  },
];
const branches: Branch[] = [
  {
    code: 'HCM-Q1',
    name: 'Chi nhánh Quận 1',
    address: 'Quận 1, TP. Hồ Chí Minh',
    status: 'ACTIVE',
    timezone: 'Asia/Ho_Chi_Minh',
  },
  {
    code: 'HCM-TD',
    name: 'Chi nhánh Thủ Đức',
    address: 'TP. Thủ Đức, TP. Hồ Chí Minh',
    status: 'ACTIVE',
    timezone: 'Asia/Ho_Chi_Minh',
  },
];
const employees: Employee[] = [
  {
    code: 'NV-001',
    name: 'Hà Nguyễn',
    email: 'ha.nv@example.test',
    accountStatus: 'ACTIVE',
    employmentStatus: 'ACTIVE',
    assignments: [{ branch: 'Chi nhánh Quận 1', roleCode: 'SALES_STAFF' }],
  },
  {
    code: 'NV-002',
    name: 'Thu Lê',
    email: 'thu.nv@example.test',
    accountStatus: 'PENDING',
    employmentStatus: 'ACTIVE',
    assignments: [{ branch: 'Chi nhánh Quận 1', roleCode: 'SALES_STAFF' }],
  },
  {
    code: 'NV-003',
    name: 'Minh Trần',
    email: 'minh.nv@example.test',
    accountStatus: 'LOCKED',
    employmentStatus: 'ON_LEAVE',
    assignments: [{ branch: 'Chi nhánh Thủ Đức', roleCode: 'INVENTORY_STAFF' }],
  },
  {
    code: 'NV-004',
    name: 'Khoa Phạm',
    email: 'khoa.nv@example.test',
    accountStatus: 'ACTIVE',
    employmentStatus: 'ACTIVE',
    assignments: [{ branch: 'Chi nhánh Thủ Đức', roleCode: 'INVENTORY_STAFF' }],
  },
];
export const permissions: Permission[] = [
  ['branches.manage.all', 'Quản trị', 'Quản lý chi nhánh', 'Tạo và cập nhật chi nhánh', 'ALL'],
  ['staff.manage.all', 'Quản trị', 'Quản lý nhân viên', 'Tạo và phân công nhân viên', 'ALL'],
  ['rbac.manage.all', 'Quản trị', 'Cấu hình vai trò', 'Tick quyền của role', 'ALL'],
  [
    'catalog.manage.all',
    'Quản trị',
    'Quản lý danh mục và giá',
    'Sửa mẫu, biến thể và giá toàn chuỗi',
    'ALL',
  ],
  ['catalog.read.all', 'Quản trị', 'Xem danh mục', 'Xem mẫu và biến thể toàn chuỗi', 'ALL'],
  ['inventory.read.branch', 'Kho', 'Xem bộ', 'Tra bộ tại chi nhánh', 'BRANCH'],
  [
    'inventory.manage.branch',
    'Kho',
    'Quản lý bộ và block',
    'Cập nhật bộ, vệ sinh và sửa chữa',
    'BRANCH',
  ],
  ['transfers.manage.branch', 'Kho', 'Điều chuyển', 'Xử lý phiếu điều chuyển chi nhánh', 'BRANCH'],
  ['rentals.read.own', 'Đơn thuê', 'Xem đơn của tôi', 'Khách xem đơn của mình', 'OWN'],
  [
    'rentals.manage.own',
    'Đơn thuê',
    'Quản lý đơn của tôi',
    'Khách gửi và hủy yêu cầu trong phạm vi cho phép',
    'OWN',
  ],
  [
    'rentals.read.branch',
    'Đơn thuê',
    'Xem đơn chi nhánh',
    'Xem đơn tại chi nhánh được gán',
    'BRANCH',
  ],
  [
    'rentals.manage.branch',
    'Đơn thuê',
    'Xử lý đơn chi nhánh',
    'Xác nhận, giao và nhận trả theo quy trình',
    'BRANCH',
  ],
  [
    'payments.read.branch',
    'Thanh toán',
    'Xem giao dịch',
    'Xem thu, cọc và hoàn tại chi nhánh',
    'BRANCH',
  ],
  [
    'payments.manage.branch',
    'Thanh toán',
    'Ghi nhận giao dịch',
    'Thu tiền thuê, cọc và phụ phí',
    'BRANCH',
  ],
  ['crm.read.branch', 'CRM', 'Xem khách hàng', 'Xem hồ sơ và case trong chi nhánh', 'BRANCH'],
  ['crm.manage.branch', 'CRM', 'Xử lý case', 'Tạo và cập nhật case trong chi nhánh', 'BRANCH'],
  [
    'reports.read.branch',
    'Quản trị',
    'Xem báo cáo chi nhánh',
    'Xem số liệu tại chi nhánh được gán',
    'BRANCH',
  ],
  ['reports.read.all', 'Quản trị', 'Xem báo cáo toàn chuỗi', 'Xem số liệu mọi chi nhánh', 'ALL'],
].map(([code, group, label, description, scope]) => ({
  code,
  group,
  label,
  description,
  scope: scope as Permission['scope'],
}));
const roles: Role[] = [
  {
    code: 'ADMIN',
    name: 'Quản trị chuỗi',
    group: 'ADMIN',
    permissions: permissions.map((p) => p.code),
  },
  {
    code: 'SALES_STAFF',
    name: 'Nhân viên bán hàng',
    group: 'STAFF',
    permissions: [
      'catalog.read.all',
      'inventory.read.branch',
      'rentals.read.branch',
      'rentals.manage.branch',
      'payments.read.branch',
      'payments.manage.branch',
      'crm.read.branch',
      'crm.manage.branch',
      'reports.read.branch',
    ],
  },
  {
    code: 'INVENTORY_STAFF',
    name: 'Nhân viên kho',
    group: 'STAFF',
    permissions: [
      'catalog.read.all',
      'inventory.read.branch',
      'inventory.manage.branch',
      'transfers.manage.branch',
      'rentals.read.branch',
    ],
  },
  {
    code: 'CUSTOMER',
    name: 'Khách hàng',
    group: 'CUSTOMER',
    permissions: ['catalog.read.all', 'rentals.read.own', 'rentals.manage.own'],
  },
];
export const fixtureEmployees = employees;
export const fixtureRoles = roles;
const transfers: Transfer[] = [
  {
    code: 'DC-001',
    from: 'Chi nhánh Quận 1',
    to: 'Chi nhánh Thủ Đức',
    status: 'REQUESTED',
    units: [{ barcode: 'BC-012' }, { barcode: 'BC-014' }],
    note: 'Bổ sung size M cho Thủ Đức',
    version: 1,
    history: ['03/10 · Hà Nguyễn tạo yêu cầu'],
  },
  {
    code: 'DC-002',
    from: 'Chi nhánh Thủ Đức',
    to: 'Chi nhánh Quận 1',
    status: 'IN_TRANSIT',
    units: [{ barcode: 'BC-205', out: 'GOOD' }],
    note: 'Điều phối áo dài',
    version: 3,
    history: ['02/10 · Đã duyệt', '03/10 · Đã xuất kho'],
  },
];
const cases: Case[] = [
  {
    code: 'CS-001',
    customerCode: 'KH-004',
    branch: 'Chi nhánh Quận 1',
    orderId: 'RT-1033',
    subject: 'Kiểm tra vết bẩn sau trả',
    description: 'Cần xác nhận tình trạng tà áo và trao đổi với khách.',
    priority: 'HIGH',
    status: 'OPEN',
    history: ['01/10 · Thu Lê tạo case'],
  },
  {
    code: 'CS-002',
    customerCode: 'KH-003',
    branch: 'Chi nhánh Quận 1',
    orderId: 'RT-1031',
    subject: 'Nhắc hạn trả',
    description: 'Liên hệ xác nhận thời gian trả.',
    priority: 'NORMAL',
    status: 'IN_PROGRESS',
    owner: 'Hà Nguyễn',
    history: ['03/10 · Hà Nguyễn nhận case'],
  },
];
const policies: Policy[] = [
  {
    code: 'POLICY-2025',
    from: '01/01/2025',
    billingMode: 'ROLLING_24_HOURS',
    minDays: 1,
    maxDays: 30,
    quoteHours: 24,
    cancelHours: 24,
    reason: 'Áp dụng chính sách thuê theo chu kỳ 24 giờ',
  },
  {
    code: 'POLICY-2024',
    from: '01/01/2024',
    to: '31/12/2024',
    billingMode: 'CALENDAR_DAY',
    minDays: 1,
    maxDays: 30,
    quoteHours: 12,
    cancelHours: 24,
    reason: 'Phiên bản lịch sử',
  },
];
const reports: ReportSnapshot[] = [
  {
    branch: 'Chi nhánh Quận 1',
    period: 'Tháng 10/2026 · fixture',
    rentalCount: 4,
    rentalRevenue: 1420000,
    depositsHeld: 1100000,
    overdueUnits: 1,
    transactions: [
      { status: 'SUCCEEDED', count: 4 },
      { status: 'PENDING', count: 1 },
    ],
    refunds: [
      { status: 'REQUESTED', count: 1 },
      { status: 'FAILED', count: 0 },
    ],
  },
  {
    branch: 'Chi nhánh Thủ Đức',
    period: 'Tháng 10/2026 · fixture',
    rentalCount: 0,
    rentalRevenue: 0,
    depositsHeld: 0,
    overdueUnits: 0,
    transactions: [
      { status: 'SUCCEEDED', count: 0 },
      { status: 'PENDING', count: 0 },
    ],
    refunds: [
      { status: 'REQUESTED', count: 0 },
      { status: 'FAILED', count: 0 },
    ],
  },
];
const customerOrders: CustomerOrder[] = [
  {
    id: 'RT-1024',
    customerCode: 'KH-001',
    status: 'PENDING_CONFIRMATION',
    branch: 'Chi nhánh Quận 1',
    pickup: '10/10/2026 · 09:00',
    due: '12/10/2026 · 09:00',
    costume: 'Áo dài Lina',
    variant: 'M / Hồng phấn × 2',
    rental: 1280000,
    deposit: 1000000,
    extra: 0,
    refund: 0,
    rentalStatus: 'Chưa thu',
    depositStatus: 'Chưa thu',
    refundStatus: 'Chưa phát sinh',
    returnStatus: 'Chưa giao',
    history: ['03/10 · Gửi yêu cầu thuê', '03/10 · Chờ studio xác nhận'],
    canCancel: true,
  },
  {
    id: 'RT-1028',
    customerCode: 'KH-002',
    status: 'READY_FOR_PICKUP',
    branch: 'Chi nhánh Quận 1',
    pickup: '03/10/2026 · 16:30',
    due: '05/10/2026 · 16:30',
    costume: 'Suit Aria',
    variant: 'M / Kem',
    rental: 840000,
    deposit: 700000,
    extra: 0,
    refund: 0,
    rentalStatus: 'Chưa thu',
    depositStatus: 'Chưa thu',
    refundStatus: 'Chưa phát sinh',
    returnStatus: 'Chưa giao',
    history: ['03/10 · Đã gán bộ BC-028', '03/10 · Sẵn sàng nhận'],
    canCancel: false,
  },
  {
    id: 'RT-1031',
    customerCode: 'KH-003',
    status: 'ACTIVE',
    branch: 'Chi nhánh Quận 1',
    pickup: '01/10/2026 · 14:00',
    due: '03/10/2026 · 14:00',
    costume: 'Đầm Rouge',
    variant: 'S / Đỏ berry',
    rental: 780000,
    deposit: 600000,
    extra: 0,
    refund: 0,
    rentalStatus: 'Đã thu',
    depositStatus: 'Đang giữ',
    refundStatus: 'Chưa phát sinh',
    returnStatus: 'Chưa trả',
    history: ['01/10 · Đã giao BC-031', '01/10 · Đã thu thuê và cọc'],
    canCancel: false,
  },
  {
    id: 'RT-1033',
    customerCode: 'KH-004',
    status: 'RETURN_INSPECTION',
    branch: 'Chi nhánh Quận 1',
    pickup: '29/09/2026 · 09:00',
    due: '01/10/2026 · 09:00',
    costume: 'Áo dài Lina',
    variant: 'S / Hồng phấn',
    rental: 640000,
    deposit: 500000,
    extra: 0,
    refund: 0,
    rentalStatus: 'Đã thu',
    depositStatus: 'Đang giữ',
    refundStatus: 'Chờ quyết toán',
    returnStatus: 'Đang kiểm tra',
    history: ['29/09 · Đã giao BC-033', '01/10 · Đã nhận trả'],
    canCancel: false,
  },
  {
    id: 'RT-1035',
    customerCode: 'KH-005',
    status: 'ACTIVE',
    branch: 'Chi nhánh Quận 1',
    pickup: '02/10/2026 · 10:00',
    due: '04/10/2026 · 10:00',
    costume: 'Áo dài Lina · 2 bộ',
    variant: 'M / Hồng phấn',
    rental: 1280000,
    deposit: 1000000,
    extra: 0,
    refund: 0,
    rentalStatus: 'Đã thu',
    depositStatus: 'Đang giữ',
    refundStatus: 'Chưa phát sinh',
    returnStatus: 'Chưa trả',
    history: ['02/10 · Đã giao BC-035 và BC-036', '02/10 · Đã thu thuê và cọc'],
    canCancel: false,
  },
];
export interface ActiveUnit {
  barcode: string;
  costume: string;
  variant: string;
  customer: string;
  phone: string;
  orderId: string;
  pickedUp: string;
  due: string;
  overdue: boolean;
  branch: string;
  accessories: string[];
}
const activeUnits = (): ActiveUnit[] =>
  fixtureOrders.flatMap((order) =>
    order.status === 'ACTIVE'
      ? order.items
          .filter((item) => item.unitCode)
          .map((item) => ({
            barcode: item.unitCode!,
            costume: item.costume,
            variant: item.variant,
            customer: order.customer,
            phone: order.phone,
            orderId: order.id,
            pickedUp: order.pickup,
            due: order.returnAt,
            overdue: order.id === 'RT-1031',
            branch: order.branch,
            accessories: ['Phụ kiện đi kèm theo bộ'],
          }))
      : [],
  );

const pause = () => new Promise<void>((resolve) => window.setTimeout(resolve, 320));
const check = (scenario: DemoScenario, write = false) => {
  if (scenario === 'error')
    throw new FixtureIssue(
      'NETWORK',
      'Không kết nối được dữ liệu. Nội dung đang nhập được giữ lại.',
    );
  if (scenario === 'permission')
    throw new FixtureIssue(
      'PERMISSION',
      'Quyền tại chi nhánh này đã bị thu hồi. Chưa có thay đổi nào được lưu.',
    );
  if (write && scenario === 'version')
    throw new FixtureIssue(
      'VERSION',
      'Bản ghi đã được cập nhật ở nơi khác. Tải lại để xem phiên bản mới trước khi thao tác.',
    );
  if (write && scenario === 'conflict')
    throw new FixtureIssue(
      'UNIT_CONFLICT',
      'Bộ vừa được gán trong thao tác khác. Hãy kiểm tra khả dụng và chọn lại.',
    );
};
const list = async <T>(data: T[], scenario: DemoScenario): Promise<T[]> => {
  await pause();
  check(scenario);
  return scenario === 'empty' ? [] : structuredClone(data);
};
const mutate = async <T>(scenario: DemoScenario, change: () => T): Promise<T> => {
  await pause();
  check(scenario, true);
  return structuredClone(change());
};
const syncCatalog = (model: CostumeDetail) => {
  if (!model.variants.length) return;
  const values = {
    name: model.name,
    category: model.category,
    description: model.description,
    sizes: [...new Set(model.variants.map((v) => v.size))],
    colors: [...new Set(model.variants.map((v) => v.color))],
    priceFrom: Math.min(...model.variants.map((v) => v.price)),
    depositFrom: Math.min(...model.variants.map((v) => v.deposit)),
  };
  const existing = fixtureCatalog.find((item) => item.id === model.id);
  if (existing) Object.assign(existing, values);
  else
    fixtureCatalog.push({
      id: model.id,
      ...values,
      imagePosition: model.imagePosition,
      availableAtFixturePeriod: false,
    });
};
const branchObligations = (name: string) => ({
  orders: fixtureOrders.filter(
    (order) =>
      order.branch === name &&
      [
        'PENDING_CONFIRMATION',
        'CONFIRMED',
        'PREPARING',
        'READY_FOR_PICKUP',
        'ACTIVE',
        'RETURN_INSPECTION',
      ].includes(order.status),
  ).length,
  units: units.filter((unit) => unit.branch === name && unit.status !== 'RETIRED').length,
  transfers: transfers.filter(
    (transfer) =>
      (transfer.from === name || transfer.to === name) &&
      ['REQUESTED', 'APPROVED', 'IN_TRANSIT'].includes(transfer.status),
  ).length,
});

export const studioAdapter = {
  recordBooking(id: string, draft: BookingDraft, quote: QuoteSnapshot) {
    const existing = customerOrders.find((order) => order.id === id);
    if (existing) return existing.customerCode;
    const catalog = fixtureCatalog.find((item) => item.id === draft.costumeId);
    if (!catalog) throw new FixtureIssue('NOT_FOUND', 'Không tìm thấy mẫu đã chọn.');
    let customer = customers.find((item) => item.phone === draft.phone);
    if (!customer) {
      customer = {
        code: `KH-DEMO-${customers.length + 1}`,
        name: draft.name,
        phone: draft.phone,
        email: '',
        preferredBranch: draft.branch,
        history: [],
        interactions: ['03/10 · Gửi yêu cầu fixture'],
      };
      customers.push(customer);
      window.dispatchEvent(new Event('fixture-access-updated'));
    }
    const pickup = draft.pickup.replace('T', ' · ');
    const due = draft.returnAt.replace('T', ' · ');
    const eligibleUnits = units
      .filter(
        (unit) =>
          unit.branch === draft.branch &&
          unit.model === catalog.name &&
          unit.variant === draft.variant &&
          ['READY', 'CLEANING', 'REPAIR'].includes(unit.status),
      )
      .map((unit) => ({
        code: unit.barcode,
        variant: `${catalog.name} · ${unit.variant}`,
        status: unit.status as 'READY' | 'CLEANING' | 'REPAIR',
        availableAtFixturePeriod: unit.available,
        note: unit.blocks[0]?.reason,
      }));
    fixtureOrders.push({
      id,
      status: 'PENDING_CONFIRMATION',
      version: 1,
      customer: draft.name,
      phone: draft.phone,
      branch: draft.branch,
      pickup,
      returnAt: due,
      dayPolicy: quote.policy,
      items: Array.from({ length: draft.quantity }, (_, index) => ({
        id: String(index + 1).padStart(2, '0'),
        costume: catalog.name,
        variant: draft.variant,
      })),
      money: [
        { label: 'Tiền thuê', amount: quote.rental, status: 'Chưa thu', tone: 'neutral' },
        { label: 'Tiền cọc', amount: quote.deposit, status: 'Chưa thu', tone: 'neutral' },
        { label: 'Phụ phí / hoàn', amount: 0, status: 'Chưa phát sinh', tone: 'neutral' },
      ],
      history: ['03/10 · Tạo yêu cầu fixture', '03/10 · Chờ nhân viên xác nhận, chưa giữ bộ'],
      note: 'Yêu cầu mẫu; cần kiểm tra khả dụng và gán bộ.',
      eligibleUnits,
    });
    customerOrders.unshift({
      id,
      customerCode: customer.code,
      status: 'PENDING_CONFIRMATION',
      branch: draft.branch,
      pickup,
      due,
      costume: catalog.name,
      variant: `${draft.variant} × ${draft.quantity}`,
      rental: quote.rental,
      deposit: quote.deposit,
      extra: 0,
      refund: 0,
      rentalStatus: 'Chưa thu',
      depositStatus: 'Chưa thu',
      refundStatus: 'Chưa phát sinh',
      returnStatus: 'Chưa giao',
      history: ['03/10 · Tạo yêu cầu fixture', '03/10 · Chờ studio xác nhận'],
      canCancel: true,
    });
    customer.history.unshift(`${id} · Chờ xác nhận`);
    return customer.code;
  },
  reflectConfirmation(id: string, codes: string[]) {
    const order = fixtureOrders.find((value) => value.id === id);
    if (!order) return;
    order.status = 'CONFIRMED';
    order.version += 1;
    order.items = order.items.map((item, index) => ({
      ...item,
      unitCode: codes[index],
      unitStatus: 'Đã gán',
    }));
    order.history.unshift(`03/10 · Đã xác nhận và gán ${codes.join(', ')}`);
    units = units.map((unit) =>
      codes.includes(unit.barcode)
        ? { ...unit, available: false, history: [`03/10 · Đã gán cho ${id}`, ...unit.history] }
        : unit,
    );
    const customerOrder = customerOrders.find((value) => value.id === id);
    if (customerOrder) {
      customerOrder.status = 'CONFIRMED';
      customerOrder.canCancel = false;
      customerOrder.history.unshift('03/10 · Studio đã xác nhận và gán bộ');
    }
  },
  markReadyForPickup(id: string, scenario: DemoScenario) {
    return mutate(scenario, () => {
      const order = fixtureOrders.find((value) => value.id === id);
      if (!order || !['CONFIRMED', 'PREPARING'].includes(order.status))
        throw new FixtureIssue(
          'INVALID_STATUS',
          'Đơn không ở trạng thái có thể chuẩn bị giao. Tải lại chi tiết đơn.',
        );
      if (
        order.items.some(
          (item) =>
            !item.unitCode ||
            !units.some(
              (unit) =>
                unit.barcode === item.unitCode &&
                unit.branch === order.branch &&
                unit.status === 'READY',
            ),
        )
      )
        throw new FixtureIssue(
          'UNIT_BLOCKED',
          'Có bộ chưa READY hoặc không còn ở chi nhánh. Kiểm tra từng barcode trước khi giao.',
        );
      order.status = 'READY_FOR_PICKUP';
      order.version += 1;
      order.items = order.items.map((item) => ({ ...item, unitStatus: 'Sẵn sàng' }));
      order.history.unshift('03/10 · Đã kiểm bộ và phụ kiện; sẵn sàng giao (fixture)');
      const customerOrder = customerOrders.find((value) => value.id === id);
      if (customerOrder) {
        customerOrder.status = 'READY_FOR_PICKUP';
        customerOrder.history.unshift('03/10 · Studio đã chuẩn bị xong, sẵn sàng nhận');
      }
      return order;
    });
  },
  decideOrder(
    id: string,
    action: 'REJECTED' | 'CANCELLED',
    reason: string,
    scenario: DemoScenario,
  ) {
    return mutate(scenario, () => {
      const order = fixtureOrders.find((value) => value.id === id);
      if (!order || !reason.trim())
        throw new FixtureIssue('INVALID_DECISION', 'Đơn hoặc lý do không hợp lệ.');
      order.status = action;
      order.version += 1;
      order.history.unshift(`03/10 · ${action}: ${reason}`);
      const customerOrder = customerOrders.find((value) => value.id === id);
      if (customerOrder) {
        customerOrder.status = action;
        customerOrder.reason = reason;
        customerOrder.canCancel = false;
        customerOrder.history.unshift(`03/10 · ${action}: ${reason}`);
      }
      return order;
    });
  },
  details: (scenario: DemoScenario) => list(details, scenario),
  units: (scenario: DemoScenario) => list(units, scenario),
  activeUnits: (scenario: DemoScenario) => list(activeUnits(), scenario),
  customers: (scenario: DemoScenario) => list(customers, scenario),
  employees: (scenario: DemoScenario) => list(employees, scenario),
  branches: (scenario: DemoScenario) => list(branches, scenario),
  branchObligations,
  roles: (scenario: DemoScenario) => list(roles, scenario),
  transfers: (scenario: DemoScenario) => list(transfers, scenario),
  cases: (scenario: DemoScenario) => list(cases, scenario),
  policies: (scenario: DemoScenario) => list(policies, scenario),
  reports: (scenario: DemoScenario) => list(reports, scenario),
  customerOrders: (scenario: DemoScenario) => list(customerOrders, scenario),
  async barcode(code: string, branch: string, scenario: DemoScenario) {
    await pause();
    check(scenario);
    if (scenario === 'barcodeMissing')
      throw new FixtureIssue(
        'BARCODE_MISSING',
        'Không tìm thấy barcode. Kiểm tra và quét/nhập lại.',
      );
    const unit = units.find((item) => item.barcode === code.trim().toUpperCase());
    if (!unit)
      throw new FixtureIssue(
        'BARCODE_MISSING',
        'Không tìm thấy barcode. Kiểm tra và quét/nhập lại.',
      );
    if (scenario === 'barcodeOtherBranch' || unit.branch !== branch)
      throw new FixtureIssue(
        'OTHER_BRANCH',
        `Bộ thuộc ${unit.branch}. Hãy chọn đúng chi nhánh có quyền.`,
      );
    if (scenario === 'unitBlocked' || unit.status === 'CLEANING' || unit.status === 'REPAIR')
      throw new FixtureIssue(
        'UNIT_BLOCKED',
        'Bộ đang bị chặn để vệ sinh/sửa chữa, chưa thể sử dụng.',
      );
    return structuredClone(unit);
  },
  addBlock: (code: string, block: UnitBlock, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const unit = units.find((u) => u.barcode === code);
      if (!unit) throw new FixtureIssue('NOT_FOUND', 'Không tìm thấy bộ.');
      unit.blocks.unshift(block);
      unit.available = false;
      unit.status =
        block.type === 'CLEANING' ? 'CLEANING' : block.type === 'REPAIR' ? 'REPAIR' : unit.status;
      unit.history.unshift(`03/10 · Tạo block ${block.type}: ${block.reason}`);
      return unit;
    }),
  saveVariant: (variant: Variant, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const model = details.find((d) => d.id === variant.modelId);
      if (!model) throw new FixtureIssue('NOT_FOUND', 'Không tìm thấy mẫu.');
      const index = model.variants.findIndex((v) => v.code === variant.code);
      if (index < 0) model.variants.push(variant);
      else model.variants[index] = variant;
      syncCatalog(model);
      return model;
    }),
  saveModel: (detail: CostumeDetail, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const index = details.findIndex((d) => d.id === detail.id);
      if (index < 0) details.push(detail);
      else details[index] = detail;
      syncCatalog(detail);
      return detail;
    }),
  saveEmployee: (employee: Employee, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const index = employees.findIndex((e) => e.code === employee.code);
      if (index < 0) employees.push(employee);
      else employees[index] = employee;
      window.dispatchEvent(new Event('fixture-access-updated'));
      return employee;
    }),
  saveBranch: (branch: Branch, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const index = branches.findIndex((b) => b.code === branch.code);
      if (index >= 0 && branches[index].status === 'ACTIVE' && branch.status === 'INACTIVE') {
        const obligations = branchObligations(branches[index].name);
        if (obligations.orders || obligations.units || obligations.transfers)
          throw new FixtureIssue(
            'BRANCH_OBLIGATIONS',
            `Chi nhánh còn ${obligations.orders} đơn đang xử lý, ${obligations.units} bộ vật lý và ${obligations.transfers} phiếu điều chuyển mở. Xử lý nghĩa vụ trước khi ngừng hoạt động.`,
          );
      }
      if (index < 0) branches.push(branch);
      else branches[index] = branch;
      return branch;
    }),
  saveRole: (role: Role, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const index = roles.findIndex((r) => r.code === role.code);
      if (index < 0) throw new FixtureIssue('NOT_FOUND', 'Không tìm thấy vai trò.');
      roles[index] = role;
      window.dispatchEvent(new Event('fixture-access-updated'));
      return role;
    }),
  saveTransfer: (transfer: Transfer, scenario: DemoScenario) =>
    mutate(scenario, () => {
      if (transfer.from === transfer.to || !transfer.note.trim() || !transfer.units.length)
        throw new FixtureIssue('INVALID_TRANSFER', 'Chọn hai chi nhánh khác nhau, bộ và lý do.');
      for (const item of transfer.units) {
        const unit = units.find((u) => u.barcode === item.barcode);
        if (unit?.branch !== transfer.from || unit.status !== 'READY' || !unit.available)
          throw new FixtureIssue(
            'UNIT_CONFLICT',
            `${item.barcode} không sẵn sàng tại chi nhánh xuất.`,
          );
      }
      const index = transfers.findIndex((t) => t.code === transfer.code);
      if (index < 0) transfers.unshift(transfer);
      else transfers[index] = transfer;
      return transfer;
    }),
  advanceTransfer: (
    code: string,
    next: TransferStatus,
    checked: { barcode: string; in: string }[],
    reason: string,
    scenario: DemoScenario,
  ) =>
    mutate(scenario, () => {
      const transfer = transfers.find((t) => t.code === code);
      if (!transfer) throw new FixtureIssue('NOT_FOUND', 'Không tìm thấy phiếu điều chuyển.');
      const allowed: Record<TransferStatus, TransferStatus[]> = {
        REQUESTED: ['APPROVED', 'REJECTED', 'CANCELLED'],
        APPROVED: ['IN_TRANSIT', 'CANCELLED'],
        IN_TRANSIT: ['RECEIVED'],
        RECEIVED: [],
        REJECTED: [],
        CANCELLED: [],
      };
      if (!allowed[transfer.status].includes(next))
        throw new FixtureIssue(
          'INVALID_TRANSITION',
          'Trạng thái phiếu đã thay đổi; tải lại trước khi thao tác.',
        );
      if ((next === 'REJECTED' || next === 'CANCELLED') && !reason.trim())
        throw new FixtureIssue('REASON_REQUIRED', 'Nhập lý do từ chối hoặc hủy.');
      if (next === 'IN_TRANSIT') {
        for (const item of transfer.units) {
          const unit = units.find((u) => u.barcode === item.barcode);
          if (unit?.branch !== transfer.from || unit.status !== 'READY' || !unit.available)
            throw new FixtureIssue(
              'UNIT_CONFLICT',
              `${item.barcode} không còn sẵn sàng tại chi nhánh xuất.`,
            );
        }
        transfer.units = transfer.units.map((item) => ({ ...item, out: 'GOOD' }));
        units = units.map((unit) =>
          transfer.units.some((item) => item.barcode === unit.barcode)
            ? {
                ...unit,
                status: 'IN_TRANSFER',
                available: false,
                history: [`03/10 · Xuất theo ${code}`, ...unit.history],
              }
            : unit,
        );
      }
      if (next === 'RECEIVED') {
        const outstanding = transfer.units.filter((item) => !item.received);
        const accepted = checked.filter((item) => item.in);
        if (
          !accepted.length ||
          accepted.length !== new Set(accepted.map((item) => item.barcode)).size ||
          accepted.some((item) => !outstanding.some((unit) => unit.barcode === item.barcode))
        )
          throw new FixtureIssue(
            'CHECK_REQUIRED',
            'Chọn ít nhất một bộ chưa nhận và ghi tình trạng nhận hợp lệ.',
          );
        for (const item of accepted) {
          const unit = units.find((value) => value.barcode === item.barcode);
          if (unit?.branch !== transfer.from || unit.status !== 'IN_TRANSFER')
            throw new FixtureIssue(
              'UNIT_CONFLICT',
              `${item.barcode} không còn ở trạng thái đang vận chuyển. Tải lại phiếu.`,
            );
        }
        transfer.units = transfer.units.map((item) => {
          const received = accepted.find((value) => value.barcode === item.barcode);
          return received ? { ...item, received: 'Đã nhận', in: received.in } : item;
        });
        units = units.map((unit) =>
          accepted.some((item) => item.barcode === unit.barcode)
            ? {
                ...unit,
                branch: transfer.to,
                status:
                  accepted.find((item) => item.barcode === unit.barcode)?.in === 'GOOD'
                    ? 'READY'
                    : 'INBOUND',
                available: accepted.find((item) => item.barcode === unit.barcode)?.in === 'GOOD',
                condition:
                  accepted.find((item) => item.barcode === unit.barcode)?.in ?? unit.condition,
                history: [`03/10 · Nhận theo ${code} tại ${transfer.to}`, ...unit.history],
              }
            : unit,
        );
        transfer.status = transfer.units.every((item) => item.received) ? 'RECEIVED' : 'IN_TRANSIT';
        transfer.version += 1;
        transfer.history.unshift(
          `03/10 · Đã nhận ${transfer.units.filter((item) => item.received).length}/${transfer.units.length} bộ`,
        );
        return transfer;
      }
      transfer.status = next;
      if (next === 'REJECTED' || next === 'CANCELLED')
        transfer.history.unshift(`03/10 · Lý do: ${reason}`);
      transfer.version += 1;
      const actionLabels: Record<TransferStatus, string> = {
        REQUESTED: 'Tạo yêu cầu',
        APPROVED: 'Đã duyệt',
        IN_TRANSIT: 'Đã xuất kho',
        RECEIVED: 'Đã nhận đủ',
        REJECTED: 'Đã từ chối',
        CANCELLED: 'Đã hủy',
      };
      transfer.history.unshift(`03/10 · ${actionLabels[next]}`);
      return transfer;
    }),
  saveCase: (value: Case, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const index = cases.findIndex((c) => c.code === value.code);
      if (index < 0) cases.unshift(value);
      else cases[index] = value;
      return value;
    }),
  savePolicy: (value: Policy, scenario: DemoScenario) =>
    mutate(scenario, () => {
      if (policies.some((p) => p.code === value.code))
        throw new FixtureIssue('DUPLICATE', 'Mã phiên bản chính sách đã tồn tại.');
      policies.unshift(value);
      return value;
    }),
  saveCustomer: (value: Customer, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const index = customers.findIndex((c) => c.code === value.code);
      if (index < 0) customers.unshift(value);
      else customers[index] = value;
      window.dispatchEvent(new Event('fixture-access-updated'));
      return value;
    }),
  cancelCustomerOrder: (id: string, reason: string, scenario: DemoScenario) =>
    mutate(scenario, () => {
      const order = customerOrders.find((o) => o.id === id);
      if (!order?.canCancel)
        throw new FixtureIssue(
          'CANCEL_NOT_ALLOWED',
          'Đơn này không còn đủ điều kiện hủy trong dữ liệu mẫu.',
        );
      order.status = 'CANCELLED';
      order.canCancel = false;
      order.reason = reason;
      order.history.unshift(`03/10 · Khách hủy: ${reason}`);
      const staffOrder = fixtureOrders.find((value) => value.id === id);
      if (staffOrder) {
        staffOrder.status = 'CANCELLED';
        staffOrder.version += 1;
        staffOrder.history.unshift(`03/10 · Khách hủy: ${reason}`);
      }
      return order;
    }),
  clock: fixtureClock,
};
export const fixtureCustomers = customers;
