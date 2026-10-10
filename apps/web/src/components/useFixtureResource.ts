import { useEffect, useState } from 'react';
import type { DemoScenario } from '../fixtures/types';

export function useFixtureResource<T>(
  scenario: DemoScenario,
  loader: (scenario: DemoScenario) => Promise<T>,
) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>({ key: '' });
  const key = `${scenario}:${attempt}`;
  useEffect(() => {
    if (scenario === 'loading') return;
    let active = true;
    loader(scenario)
      .then((data) => {
        if (active) setState({ key, data });
      })
      .catch((error: unknown) => {
        if (active)
          setState({
            key,
            error: error instanceof Error ? error.message : 'Không tải được dữ liệu.',
          });
      });
    return () => {
      active = false;
    };
  }, [scenario, loader, key]);
  return {
    loading: scenario === 'loading' || state.key !== key,
    data: state.key === key ? state.data : undefined,
    error: state.key === key ? state.error : undefined,
    retry: () => setAttempt((value) => value + 1),
  };
}
