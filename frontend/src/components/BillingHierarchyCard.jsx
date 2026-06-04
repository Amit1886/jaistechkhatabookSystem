import React, { useEffect, useMemo, useState } from "react";

import {
  fetchBillingHierarchy,
  updateBillingHierarchy,
} from "../services/billingHierarchyApi";

function Select({ label, value, onChange, options, disabled }) {
  return (
    <label className="flex flex-col gap-2 text-xs text-slate-700">
      <span className="font-medium">{label}</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-slate-200 bg-white px-2 py-2 text-sm"
      >
        {(options || []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function BillingHierarchyCard() {
  const [state, setState] = useState({
    loading: true,
    error: "",
    canEdit: false,
    hierarchy: null,
    current: { billing_access_level: "", billing_role_type: "", billing_child_role: "" },
    saving: false,
    savedMsg: "",
  });

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const data = await fetchBillingHierarchy();
        if (!mounted) return;
        setState((s) => ({
          ...s,
          loading: false,
          error: "",
          canEdit: Boolean(data.can_edit),
          hierarchy: data.hierarchy || {},
          current: data.current || s.current,
        }));
      } catch (e) {
        if (!mounted) return;
        setState((s) => ({
          ...s,
          loading: false,
          error: e?.message || "Failed to load",
        }));
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  const role = useMemo(() => {
    const roles = state.hierarchy?.roles || {};
    return roles[state.current.billing_role_type] || null;
  }, [state.hierarchy, state.current.billing_role_type]);

  const childOptions = useMemo(() => {
    const base = [{ value: "", label: "—" }];
    const children = role?.children || [];
    return base.concat(children.map((c) => ({ value: String(c.key || ""), label: String(c.label || c.key || "") })));
  }, [role]);

  const accessOptions = useMemo(
    () => [{ value: "", label: "—" }, { value: "admin", label: "Admin" }, { value: "user", label: "User" }],
    []
  );
  const roleTypeOptions = useMemo(
    () => [
      { value: "", label: "—" },
      { value: "sub_user", label: "Sub User" },
      { value: "supplier", label: "Supplier" },
      { value: "vendor", label: "Vendor" },
      { value: "customer", label: "Customer" },
      { value: "field_agent", label: "Field Agent" },
      { value: "ai_agent", label: "AI Agent" },
    ],
    []
  );

  async function onSave() {
    setState((s) => ({ ...s, saving: true, savedMsg: "", error: "" }));
    try {
      await updateBillingHierarchy({
        billing_access_level: state.current.billing_access_level,
        billing_role_type: state.current.billing_role_type,
        billing_child_role: state.current.billing_child_role,
      });
      setState((s) => ({ ...s, saving: false, savedMsg: "Saved." }));
      setTimeout(() => setState((s) => ({ ...s, savedMsg: "" })), 1200);
    } catch (e) {
      setState((s) => ({ ...s, saving: false, error: e?.message || "Save failed" }));
    }
  }

  if (state.loading) {
    return <div className="rounded-xl bg-white p-4 shadow-sm">Loading billing hierarchy…</div>;
  }

  return (
    <section className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Billing Hierarchy</h2>
        {!state.canEdit ? (
          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">Read-only</span>
        ) : null}
      </div>

      {state.error ? <div className="mt-2 text-xs text-red-600">{state.error}</div> : null}
      {state.savedMsg ? <div className="mt-2 text-xs text-emerald-700">{state.savedMsg}</div> : null}

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        <Select
          label="Access Level"
          value={state.current.billing_access_level}
          disabled={!state.canEdit}
          options={accessOptions}
          onChange={(v) =>
            setState((s) => ({ ...s, current: { ...s.current, billing_access_level: v } }))
          }
        />
        <Select
          label="Role Type"
          value={state.current.billing_role_type}
          disabled={!state.canEdit}
          options={roleTypeOptions}
          onChange={(v) =>
            setState((s) => ({
              ...s,
              current: { ...s.current, billing_role_type: v, billing_child_role: "" },
            }))
          }
        />
        <Select
          label="Child Role"
          value={state.current.billing_child_role}
          disabled={!state.canEdit || !state.current.billing_role_type}
          options={childOptions}
          onChange={(v) =>
            setState((s) => ({ ...s, current: { ...s.current, billing_child_role: v } }))
          }
        />
      </div>

      {role ? (
        <div className="mt-3 text-xs text-slate-600">
          <div className="font-medium text-slate-700">Capabilities</div>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {(role.key_capabilities || []).slice(0, 6).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="mt-3 text-xs text-slate-500">Select a role type to preview capabilities.</div>
      )}

      {state.canEdit ? (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            disabled={state.saving}
            onClick={onSave}
            className="rounded-full bg-teal-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {state.saving ? "Saving…" : "Save"}
          </button>
        </div>
      ) : null}
    </section>
  );
}

