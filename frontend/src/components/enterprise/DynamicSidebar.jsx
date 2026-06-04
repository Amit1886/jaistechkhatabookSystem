import React from "react";
import { openWorkspaceTab, togglePinned, useErpStore } from "../../store/erpUiStore";

function titleOf(item) {
  return item.title || item.label || item.name || item.key;
}

function routeOf(item) {
  return item.route || item.url || item.web_url || `/${item.key}`;
}

function SidebarItem({ item, depth = 0 }) {
  const pinned = useErpStore((state) => state.pinned);
  const isPinned = pinned.includes(item.key);
  const title = titleOf(item);
  const open = () => {
    if (item.is_group && item.children?.length) return;
    openWorkspaceTab({ id: item.module || item.key, title, type: "module", route: routeOf(item), module: item.module || item.key });
  };

  return (
    <div className="dynamic-menu-group">
      <button className={item.is_group ? "dynamic-menu-item group" : "dynamic-menu-item"} style={{ paddingLeft: 12 + depth * 14 }} onClick={open}>
        <span className="dynamic-menu-icon">{(item.icon || title.slice(0, 1)).slice(0, 2).toUpperCase()}</span>
        <span>{title}</span>
        {item.badge && <small>{item.badge}</small>}
      </button>
      {!item.is_group && (
        <button className="pin-btn" onClick={() => togglePinned(item.key)} aria-label="Pin module">
          {isPinned ? "*" : "+"}
        </button>
      )}
      {item.children?.map((child) => <SidebarItem item={child} key={child.key} depth={depth + 1} />)}
    </div>
  );
}

export default function DynamicSidebar() {
  const sidebar = useErpStore((state) => state.sidebar);
  const pinned = useErpStore((state) => state.pinned);
  const brand = useErpStore((state) => state.brand);
  const flatItems = sidebar.flatMap((item) => [item, ...(item.children || [])]);
  const pinnedItems = flatItems.filter((item) => pinned.includes(item.key));

  return (
    <aside className="enterprise-sidebar">
      <div className="enterprise-brand">
        <strong>{brand.name}</strong>
        <span>Demo Business</span>
      </div>
      {pinnedItems.length > 0 && (
        <div className="sidebar-section">
          <label>Pinned</label>
          {pinnedItems.map((item) => (
            <button key={item.key} className="dynamic-menu-item compact" onClick={() => openWorkspaceTab({ id: item.module || item.key, title: titleOf(item), type: "module", route: routeOf(item), module: item.module || item.key })}>
              <span>{titleOf(item)}</span>
            </button>
          ))}
        </div>
      )}
      <div className="sidebar-section">
        <label>Modules</label>
        {sidebar.map((item) => <SidebarItem item={item} key={item.key} />)}
      </div>
    </aside>
  );
}
