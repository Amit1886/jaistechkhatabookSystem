import React from "react";

export function Card({ title, action, children, className = "" }) {
  return (
    <section className={`erp-card ${className}`}>
      {(title || action) && (
        <header className="erp-card__head">
          <h2>{title}</h2>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

