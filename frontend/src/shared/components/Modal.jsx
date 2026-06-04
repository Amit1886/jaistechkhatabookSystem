import React from "react";
import { Button } from "./Button";

export function Modal({ open, title, children, onClose, footer }) {
  if (!open) return null;
  return (
    <div className="erp-modal-layer" onMouseDown={onClose}>
      <section className="erp-modal" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
        </header>
        <div className="erp-modal__body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </section>
    </div>
  );
}

