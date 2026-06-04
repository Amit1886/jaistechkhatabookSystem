import React from "react";

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="workspace-tabs">
      {tabs.map((tab) => (
        <button key={tab.id} className={tab.id === active ? "active" : ""} onClick={() => onChange(tab.id)}>
          {tab.title}
        </button>
      ))}
    </div>
  );
}

