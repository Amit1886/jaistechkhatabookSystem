import React, { useState } from "react";
import { Button, Card } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function EmployeePortal() {
  const [message, setMessage] = useState("");

  async function mark(logType) {
    await workforceApi.markAttendance({ log_type: logType, method: "manual" });
    setMessage(`Attendance ${logType} marked`);
  }

  return (
    <div className="employee-portal">
      <Card title="Self Service">
        <div className="portal-actions">
          <Button onClick={() => mark("in")}>Clock In</Button>
          <Button variant="ghost" onClick={() => mark("out")}>Clock Out</Button>
          <Button variant="ghost">Apply Leave</Button>
          <Button variant="ghost">View Payslip</Button>
        </div>
        {message && <p className="portal-message">{message}</p>}
      </Card>
      <Card title="My Work">
        <div className="feed-list">
          <p>Assigned tasks and approvals appear here.</p>
          <p>Incentives and KPIs sync from workforce metrics.</p>
          <p>Manager communication and announcements use the same notification center.</p>
        </div>
      </Card>
    </div>
  );
}

