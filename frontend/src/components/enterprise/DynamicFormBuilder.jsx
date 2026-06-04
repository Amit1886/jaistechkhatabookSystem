import React from "react";
import { Button, Card, Input } from "../../shared/components";

export default function DynamicFormBuilder({ schema }) {
  const fields = schema?.fields || [
    { key: "customer", label: "Customer", type: "text", required: true },
    { key: "amount", label: "Amount", type: "number", required: true },
    { key: "status", label: "Status", type: "select" },
  ];

  return (
    <Card title={schema?.name || "Dynamic Form"}>
      <form className="dynamic-form">
        {fields.map((field) => (
          <Input key={field.key} label={field.label} required={field.required} type={field.type === "number" ? "number" : "text"} placeholder={field.label} />
        ))}
        <div className="form-actions">
          <Button variant="ghost">Save Draft</Button>
          <Button>Submit</Button>
        </div>
      </form>
    </Card>
  );
}
