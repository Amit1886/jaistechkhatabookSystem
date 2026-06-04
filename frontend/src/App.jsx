import React from "react";
import EnterpriseUIEngine from "./engine/EnterpriseUIEngine";
import RuntimeErrorBoundary from "./components/enterprise/RuntimeErrorBoundary";

export default function App() {
  return (
    <RuntimeErrorBoundary>
      <EnterpriseUIEngine />
    </RuntimeErrorBoundary>
  );
}
