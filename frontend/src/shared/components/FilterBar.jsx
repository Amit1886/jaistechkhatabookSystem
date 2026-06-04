import React from "react";
import { Button } from "./Button";

export function FilterBar({ children, onReset, onApply }) {
  return (
    <div className="filter-bar">
      <div>{children}</div>
      <div>
        <Button variant="ghost" size="sm" onClick={onReset}>Reset</Button>
        <Button size="sm" onClick={onApply}>Apply</Button>
      </div>
    </div>
  );
}

