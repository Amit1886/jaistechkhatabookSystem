(function () {
  function csvEscape(value) {
    const text = String(value ?? "");
    if (text.includes('"') || text.includes(",") || text.includes("\n")) {
      return '"' + text.replaceAll('"', '""') + '"';
    }
    return text;
  }

  function tableToCsv(table) {
    const rows = [];
    const trs = Array.from(table.querySelectorAll("tr")).filter(function (tr) {
      return tr.offsetParent !== null;
    });

    trs.forEach(function (tr) {
      const cells = Array.from(tr.querySelectorAll("th,td")).map(function (td) {
        return csvEscape(td.innerText.trim());
      });
      if (cells.length) rows.push(cells.join(","));
    });
    return rows.join("\n");
  }

  function downloadBlob(filename, blob) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function printTable(table) {
    const html = `
      <html>
      <head>
        <meta charset="utf-8">
        <title>Print</title>
        <style>
          body{font-family:system-ui,Arial,sans-serif;padding:16px}
          table{width:100%;border-collapse:collapse}
          th,td{border:1px solid #e5e7eb;padding:8px;font-size:12px}
          th{background:#f8fafc}
        </style>
      </head>
      <body>${table.outerHTML}</body>
      </html>`;
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
    w.print();
    w.close();
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-export]");
    if (!btn) return;
    const action = btn.getAttribute("data-export");
    const tableSelector = btn.getAttribute("data-export-table");
    const table = tableSelector ? document.querySelector(tableSelector) : btn.closest("[data-export-scope]")?.querySelector("table");
    if (!table) return;

    if (action === "print") {
      printTable(table);
      return;
    }

    if (action === "excel") {
      const csv = tableToCsv(table);
      downloadBlob((btn.getAttribute("data-export-name") || "export") + ".csv", new Blob([csv], { type: "text/csv;charset=utf-8" }));
      return;
    }

    if (action === "pdf") {
      window.print();
    }
  });
})();

