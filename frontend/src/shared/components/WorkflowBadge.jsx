import React from "react";
import { getWorkflowState } from "../workflow/workflowStates";

export function WorkflowBadge({ state }) {
  const item = getWorkflowState(state);
  return <span className={`workflow-badge workflow-badge--${item.tone}`}>{item.label}</span>;
}

