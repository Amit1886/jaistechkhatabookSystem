import React from "react";

export function Button({ children, variant = "primary", size = "md", icon, className = "", ...props }) {
  return (
    <button className={`erp-btn erp-btn--${variant} erp-btn--${size} ${className}`} type="button" {...props}>
      {icon && <span className="erp-btn__icon">{icon}</span>}
      <span>{children}</span>
    </button>
  );
}

