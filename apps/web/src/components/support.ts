import type { OrderStatus, Tone } from '../fixtures/types';

export const money = (value: number) => `${new Intl.NumberFormat('vi-VN').format(value)} đ`;

export const orderStatus: Record<OrderStatus, { text: string; tone: Tone }> = {
  DRAFT: { text: 'Bản nháp', tone: 'neutral' },
  PENDING_CONFIRMATION: { text: 'Chờ studio xác nhận', tone: 'warning' },
  CONFIRMED: { text: 'Đã xác nhận', tone: 'success' },
  PREPARING: { text: 'Đang chuẩn bị', tone: 'info' },
  READY_FOR_PICKUP: { text: 'Sẵn sàng nhận', tone: 'info' },
  ACTIVE: { text: 'Đang thuê', tone: 'info' },
  RETURN_INSPECTION: { text: 'Đang kiểm tra đồ trả', tone: 'warning' },
  COMPLETED: { text: 'Hoàn tất', tone: 'success' },
  REJECTED: { text: 'Studio từ chối', tone: 'danger' },
  CANCELLED: { text: 'Đã hủy', tone: 'neutral' },
  NO_SHOW: { text: 'Không đến nhận', tone: 'warning' },
};
