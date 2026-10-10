import type { Unit, UnitBlock } from '../fixtures/studio';

export const unitStatusLabels: Record<Unit['status'], string> = {
  INBOUND: 'Chờ nhập',
  READY: 'Sẵn sàng',
  CLEANING: 'Đang vệ sinh',
  REPAIR: 'Đang sửa',
  IN_TRANSFER: 'Đang điều chuyển',
  RETIRED: 'Ngừng sử dụng',
};
export const blockTypeLabels: Record<UnitBlock['type'], string> = {
  CLEANING: 'vệ sinh',
  REPAIR: 'sửa chữa',
  INSPECTION: 'kiểm tra',
};
export const conditionLabels: Record<string, string> = {
  GOOD: 'Tốt',
  FAIR: 'Cần theo dõi',
  DAMAGED: 'Hư hỏng',
  POOR: 'Kém',
  UNINSPECTED: 'Chưa kiểm tra',
};
export const blockStatusLabels: Record<UnitBlock['status'], string> = {
  PLANNED: 'Đã lên lịch',
  IN_PROGRESS: 'Đang thực hiện',
  COMPLETED: 'Đã hoàn tất',
};
