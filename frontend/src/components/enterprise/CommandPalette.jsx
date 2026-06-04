import React, { useMemo, useState } from "react";
import { openWorkspaceTab, setErpState, useErpStore } from "../../store/erpUiStore";
import { useGlobalSearch } from "../../shared/search/useGlobalSearch";

export default function CommandPalette() {
  const open = useErpStore((state) => state.commandOpen);
  const sidebar = useErpStore((state) => state.sidebar);
  const [query, setQuery] = useState("");
  const globalSearch = useGlobalSearch();
  const items = useMemo(() => sidebar.flatMap((item) => [item, ...(item.children || [])]), [sidebar]);
  const labelOf = (item) => item.label || item.title || item.name || item.key || "";
  const routeOf = (item) => item.url || item.route || item.web_url || item.route_name || "";
  const results = items.filter((item) => labelOf(item).toLowerCase().includes(query.toLowerCase())).slice(0, 8);

  if (!open) return null;

  return (
    <div className="command-layer" onMouseDown={() => setErpState({ commandOpen: false })}>
      <div className="command-palette" onMouseDown={(event) => event.stopPropagation()}>
        <input
          autoFocus
          placeholder="Search invoices, customers, products, reports..."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            globalSearch.setQuery(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") globalSearch.search(query);
          }}
        />
        <div className="command-results">
          {results.map((item) => (
            <button
              key={item.key}
              onClick={() => {
                openWorkspaceTab({ id: item.module || item.key, title: labelOf(item), type: "module", route: routeOf(item), module: item.module || item.key });
                setErpState({ commandOpen: false });
              }}
            >
              <span>{labelOf(item)}</span>
              <small>{routeOf(item) || "metadata item"}</small>
            </button>
          ))}
          {globalSearch.loading && <button>Searching records...</button>}
          {globalSearch.results.map((item) => (
            <button key={`${item.scope}-${item.id}`} onClick={() => item.url && window.location.assign(item.url)}>
              <span>{item.title}</span>
              <small>{item.scope} · {item.subtitle}</small>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
