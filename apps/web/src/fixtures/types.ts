export type DemoScenario =
  | 'normal'
  | 'loading'
  | 'empty'
  | 'error'
  | 'conflict'
  | 'version'
  | 'cancelled'
  | 'permission'
  | 'bankPending'
  | 'refundFailed'
  | 'barcodeMissing'
  | 'barcodeOtherBranch'
  | 'unitBlocked';

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';
export type OrderStatus =
  | 'DRAFT'
  | 'PENDING_CONFIRMATION'
  | 'CONFIRMED'
  | 'PREPARING'
  | 'READY_FOR_PICKUP'
  | 'ACTIVE'
  | 'RETURN_INSPECTION'
  | 'COMPLETED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'NO_SHOW';

export interface CatalogItem {
  id: string;
  name: string;
  category: string;
  sizes: string[];
  colors: string[];
  imagePosition: 'left' | 'center' | 'right' | 'missing';
  priceFrom: number;
  depositFrom: number;
  availableAtFixturePeriod: boolean;
  description: string;
}

export interface UnitOption {
  code: string;
  variant: string;
  status: 'READY' | 'CLEANING' | 'REPAIR';
  availableAtFixturePeriod: boolean;
  note?: string;
}

export interface OrderItem {
  id: string;
  costume: string;
  variant: string;
  unitCode?: string;
  unitStatus?: string;
}

export interface MoneyLine {
  label: string;
  amount: number;
  status: string;
  tone: Tone;
}

export interface Order {
  id: string;
  status: OrderStatus;
  version: number;
  customer: string;
  phone: string;
  branch: string;
  pickup: string;
  returnAt: string;
  dayPolicy: string;
  items: OrderItem[];
  money: MoneyLine[];
  history: string[];
  note: string;
  eligibleUnits: UnitOption[];
}

export interface QueueTask {
  id: string;
  orderId: string;
  due: string;
  customer: string;
  phone: string;
  barcode?: string;
  task: string;
  urgency: string;
  group: 'Quá hạn' | 'Trong 2 giờ tới' | 'Hôm nay' | 'Chờ xác nhận lâu';
  kind: 'pending' | 'handover' | 'return' | 'overdue' | 'payment';
  owner: string;
  branch: string;
  workDate: string;
  status: 'Cần xử lý' | 'Đang xử lý';
}

export interface BookingDraft {
  costumeId: string;
  variant: string;
  quantity: number;
  branch: string;
  pickup: string;
  returnAt: string;
  name: string;
  phone: string;
  note: string;
}

export interface QuoteSnapshot {
  id: string;
  expiresAt: string;
  daysLabel: string;
  pricePerDay: number;
  quantity: number;
  rental: number;
  deposit: number;
  discount: number;
  amountDueAtPickup: number;
  policy: string;
}

export class FixtureIssue extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}
