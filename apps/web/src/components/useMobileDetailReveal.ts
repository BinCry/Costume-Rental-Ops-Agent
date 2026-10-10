import { useRef } from 'react';

export function useMobileDetailReveal<T extends HTMLElement>() {
  const detailRef = useRef<T>(null);

  const revealDetail = () => {
    if (!window.matchMedia('(max-width: 767px)').matches) return;
    window.requestAnimationFrame(() => {
      detailRef.current?.focus({ preventScroll: true });
      detailRef.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
    });
  };

  return { detailRef, revealDetail };
}
