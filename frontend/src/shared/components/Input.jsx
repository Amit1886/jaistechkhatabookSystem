import React from "react";

export function Input({ label, required, hint, error, className = "", ...props }) {
  return (
    <label className={`erp-field ${className}`}>
      {label && (
        <span>
          {label}
          {required ? " *" : ""}
        </span>
      )}
      <input aria-invalid={Boolean(error)} {...props} />
      {hint && <small>{hint}</small>}
      {error && <strong>{error}</strong>}
    </label>
  );
}

