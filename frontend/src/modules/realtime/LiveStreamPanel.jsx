import React from "react";
import { useLiveStream } from "./useLiveStream";

const streams = [
  { key: "leads_live", label: "Leads", color: "bg-blue-500" },
  { key: "earnings_live", label: "Earnings", color: "bg-lime-500" },
  { key: "sales_live", label: "Sales", color: "bg-rose-500" },
  { key: "marketing_live", label: "Marketing", color: "bg-amber-500" },
];

function StreamCard({ stream }) {
  const messages = useLiveStream(stream.key);
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${stream.color}`} />
          <span className="text-sm font-semibold">{stream.label}</span>
        </div>
        <span className="text-[11px] text-slate-500">{messages.length} events</span>
      </div>
      <div className="max-h-64 space-y-2 overflow-y-auto pr-1 text-xs text-slate-700">
        {messages.length === 0 && <div className="text-slate-400">Waiting for events...</div>}
        {messages.map((msg, idx) => (
          <pre key={idx} className="rounded bg-slate-50 px-2 py-1">
            {JSON.stringify(msg, null, 2)}
          </pre>
        ))}
      </div>
    </div>
  );
}

export default function LiveStreamPanel() {
  return (
    <div className="space-y-3">
      {streams.map((s) => (
        <StreamCard key={s.key} stream={s} />
      ))}
    </div>
  );
}
