import { useMemo, useState } from "react";
import { enterpriseApi } from "../../services/enterpriseApi";
import { SEARCH_SCOPES, normalizeSearchResult } from "./searchRegistry";

export function useGlobalSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  async function search(value = query) {
    const term = value.trim();
    if (!term) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const settled = await Promise.allSettled(
        SEARCH_SCOPES.map((scope) => enterpriseApi.query(scope.query, { q: term }).then((data) => ({ scope, data }))),
      );
      const next = settled.flatMap((item) => {
        if (item.status !== "fulfilled") return [];
        return (item.value.data.rows || []).map((row) => normalizeSearchResult(item.value.scope, row));
      });
      setResults(next);
    } finally {
      setLoading(false);
    }
  }

  return useMemo(() => ({ query, setQuery, results, loading, search }), [query, results, loading]);
}

