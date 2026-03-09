import React from "react";
import { RouterProvider } from "react-router-dom";

import { router } from "./router";
import { usePluginStore } from "./store/plugin-store";
import { useSecurityStore } from "./store/security-store";
import { useSettingsStore } from "./store/settings-store";

export function Bootstrap() {
  const hydrateSettings = useSettingsStore((s) => s.hydrate);
  const hydrateSecurity = useSecurityStore((s) => s.hydrate);
  const hydratePlugins = usePluginStore((s) => s.hydrate);

  React.useEffect(() => {
    void Promise.all([hydrateSettings(), hydrateSecurity(), hydratePlugins()]);
  }, [hydrateSettings, hydrateSecurity, hydratePlugins]);

  return <RouterProvider router={router} />;
}
