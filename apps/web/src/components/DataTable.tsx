import { useState } from 'react';
import type { ReactNode } from 'react';
import { Button, Field, Icon, SelectField } from './ui';

export interface TableColumn<T> {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
}

export function DataTable<T extends { id: string }>({
  rows,
  columns,
  selectedId,
  onSelect,
  pageSize = 6,
  emptyText = 'Không có dữ liệu phù hợp',
  searchKey,
  filterKey,
  filterLabel = 'Bộ lọc',
  filterDisplay = (value: string) => value,
}: {
  rows: T[];
  columns: TableColumn<T>[];
  selectedId?: string;
  onSelect?: (row: T) => void;
  pageSize?: number;
  emptyText?: string;
  searchKey?: (row: T) => string;
  filterKey?: (row: T) => string;
  filterLabel?: string;
  filterDisplay?: (value: string) => string;
}) {
  const [sort, setSort] = useState<{ key: string; direction: 1 | -1 }>();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const filterValues = filterKey ? [...new Set(rows.map(filterKey))] : [];
  const filtered = rows.filter(
    (row) =>
      (!filterKey || filter === 'all' || filterKey(row) === filter) &&
      (searchKey ? searchKey(row) : JSON.stringify(row))
        .toLocaleLowerCase('vi')
        .includes(search.toLocaleLowerCase('vi')),
  );
  const column = columns.find((entry) => entry.key === sort?.key);
  const sorted = column?.sortValue
    ? [...filtered].sort((a, b) => {
        const first = column.sortValue?.(a);
        const second = column.sortValue?.(b);
        return (
          (typeof first === 'number' && typeof second === 'number'
            ? first - second
            : String(first).localeCompare(String(second), 'vi')) * (sort?.direction ?? 1)
        );
      })
    : filtered;
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const shown = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  if (rows.length === 0) return <p className="table-empty">{emptyText}</p>;
  return (
    <div className="data-table-wrap">
      <div className="table-toolbar">
        <Field
          label="Tìm trong bảng"
          placeholder="Barcode, biến thể..."
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
        {filterKey && (
          <SelectField
            label={filterLabel}
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="all">Tất cả</option>
            {filterValues.map((value) => (
              <option key={value} value={value}>
                {filterDisplay(value)}
              </option>
            ))}
          </SelectField>
        )}
      </div>
      <div className="data-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((entry) => (
                <th key={entry.key} scope="col">
                  {entry.sortValue ? (
                    <button
                      type="button"
                      onClick={() => {
                        setSort((current) => ({
                          key: entry.key,
                          direction: current?.key === entry.key && current.direction === 1 ? -1 : 1,
                        }));
                        setPage(1);
                      }}
                    >
                      {entry.title} <span aria-hidden="true">↕</span>
                    </button>
                  ) : (
                    entry.title
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr
                key={row.id}
                className={selectedId === row.id ? 'selected' : ''}
                onClick={onSelect ? () => onSelect(row) : undefined}
                tabIndex={onSelect ? 0 : undefined}
                onKeyDown={
                  onSelect
                    ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          onSelect(row);
                        }
                      }
                    : undefined
                }
              >
                {columns.map((entry) => (
                  <td key={entry.key} data-label={entry.title}>
                    {entry.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 && <p className="table-empty">{emptyText}</p>}
      </div>
      {pageCount > 1 && (
        <div className="table-pagination">
          <span>
            Trang {currentPage} / {pageCount}
          </span>
          <div>
            <Button
              variant="quiet"
              disabled={currentPage === 1}
              onClick={() => setPage(currentPage - 1)}
              aria-label="Trang trước"
            >
              <Icon name="arrow" size={17} />
            </Button>
            <Button
              variant="quiet"
              disabled={currentPage === pageCount}
              onClick={() => setPage(currentPage + 1)}
              aria-label="Trang sau"
            >
              <Icon name="arrow" size={17} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
