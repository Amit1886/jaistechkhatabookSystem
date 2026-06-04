import React from "react";
import { Button } from "./Button";
import { Card } from "./Card";
import { WorkflowBadge } from "./WorkflowBadge";

export function ApprovalCard({ title, amount, requester, state = "approval", onApprove, onReject }) {
  return (
    <Card className="approval-card">
      <div>
        <WorkflowBadge state={state} />
        <h3>{title}</h3>
        <p>{requester}</p>
        {amount && <strong>{amount}</strong>}
      </div>
      <div className="approval-card__actions">
        <Button variant="ghost" size="sm" onClick={onReject}>Reject</Button>
        <Button size="sm" onClick={onApprove}>Approve</Button>
      </div>
    </Card>
  );
}

