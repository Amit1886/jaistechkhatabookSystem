import React, { useEffect, useState } from "react";
import { Button, DataTable, KPIWidget } from "../components";
import { reportingApi } from "../../services/reportingApi";
import { ReportChart } from "./ReportChart";
import { ReportFilterPanel } from "./ReportFilterPanel";

export function ReportViewer({ reportKey = "tax_gst_invoice_sales" }) {
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(nextPage = page) {
    setLoading(true);
    setError("");
    try {
      const data = await reportingApi.run(reportKey, { filters, page: nextPage, page_size: 25 });
      setResult(data);
      setPage(nextPage);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function exportReport(format) {
    const blob = await reportingApi.export(reportKey, { filters, format, page_size: 5000 });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  useEffect(() => {
    run(1);
  }, [reportKey]);

  return (
    <div className="report-viewer">
      <ReportFilterPanel
        filters={result?.template_filters || result?.filters_available}
        value={filters}
        onChange={setFilters}
        onReset={() => setFilters({})}
        onRun={() => run(1)}
      />
      {error && <div className="enterprise-alert">{error}</div>}
      <div className="report-toolbar">
        <span>{loading ? "Loading..." : `${result?.count ?? 0} rows`}</span>
        <div>
          <Button variant="ghost" onClick={() => exportReport("csv")}>CSV</Button>
          <Button variant="ghost" onClick={() => exportReport("excel")}>Excel</Button>
          <Button variant="ghost" onClick={() => exportReport("pdf")}>PDF</Button>
          <Button variant="ghost" onClick={() => exportReport("print")}>Print</Button>
        </div>
      </div>
      <div className="report-kpis">
        {Object.entries(result?.summary || {}).map(([key, value]) => <KPIWidget key={key} label={key} value={String(value)} />)}
      </div>
      <ReportChart title={result?.name || "Report Chart"} chart={result?.chart} />
      <DataTable title={result?.name || "Report"} rows={result?.rows || []} columns={result?.columns || []} />
      <div className="report-pagination">
        <Button variant="ghost" disabled={page <= 1} onClick={() => run(page - 1)}>Previous</Button>
        <span>Page {page}</span>
        <Button variant="ghost" disabled={!result?.has_next} onClick={() => run(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

