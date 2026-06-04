import { useEffect, useState } from "react";
import { enterpriseApi } from "../services/enterpriseApi";
import { setErpState } from "../store/erpUiStore";

export function useEnterpriseMetadata() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    enterpriseApi.ensureDemoSession()
      .then(() => Promise.allSettled([
        enterpriseApi.appConfig(),
        enterpriseApi.liveData(),
        enterpriseApi.apiStatus(),
        enterpriseApi.reports(),
      ]))
      .then(([config, liveData, apiStatus, reports]) => {
        if (!alive) return;
        const appConfig = config.status === "fulfilled" ? config.value : {};
        const live = liveData.status === "fulfilled" ? liveData.value : appConfig.live_data || {};
        setErpState({
          booted: true,
          appConfig,
          sidebar: appConfig.sidebar || appConfig.menu || [],
          launcher: appConfig.launcher || appConfig.modules || [],
          buttons: appConfig.buttons || appConfig.dashboard_config?.quick_actions || [],
          permissions: appConfig.permissions || {},
          liveData: live,
          reports: reports.status === "fulfilled" ? reports.value.results || reports.value : appConfig.reports || [],
          apiStatus: apiStatus.status === "fulfilled" ? apiStatus.value : appConfig.api_status || {},
          activity: {
            users_online: live.sales?.live_users || 0,
            active_devices: live.sales?.active_devices || 0,
          },
          notifications: live.notifications || [],
          engineDashboard: appConfig.dashboard_config || null,
          brand: {
            name: appConfig.app_name || appConfig.branding?.brand_name || "Billentra OS",
            accent: appConfig.branding?.accent || "#f59e0b",
          },
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return { loading, error };
}
