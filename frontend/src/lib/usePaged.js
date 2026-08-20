import { useEffect, useRef, useState } from "react";

/* Page a list to whatever height it has been given.
 *
 * The console never scrolls, so a list of unknown length has to page — and a
 * constant page size is wrong on every screen but one. This measures the box
 * the list actually got and derives the count from it, so a tall window shows
 * more rows rather than more empty space.
 *
 * `rowPx` is the height of one row INCLUDING its gap.
 */
export function usePaged(items, rowPx) {
  const ref = useRef(null);
  const [per, setPer] = useState(1);
  const [page, setPage] = useState(0);

  // items.length is in the deps because the list is not mounted on the first
  // render — the store is still loading and the page shows its empty state, so
  // ref.current is null and there is nothing to measure yet.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setPer(Math.max(1, Math.floor(el.clientHeight / rowPx)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [rowPx, items.length]);

  const pages = Math.max(1, Math.ceil(items.length / per));
  // A window resize can strand the view past the last page; clamp on read
  // rather than in an effect, so it never renders an empty page first.
  const cur = Math.min(page, pages - 1);
  const from = cur * per;
  return { ref, page: cur, pages, per, from, setPage,
           slice: items.slice(from, from + per) };
}
