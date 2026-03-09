import { Navigate, createBrowserRouter } from "react-router-dom";

import { PluginsPage } from "./pages/plugins-page";
import { RepositoriesPage } from "./pages/repositories-page";
import { SettingsPage } from "./pages/settings-page";
import { WorkspacePage } from "./pages/workspace-page";
import { WorkspacePageV3 } from "./pages/workspace-page-v3";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <WorkspacePageV3 />,
  },
  {
    path: "/workspace",
    element: <WorkspacePageV3 />,
  },
  {
    path: "/workspace-v1",
    element: <WorkspacePage />,
  },
  {
    path: "/repositories",
    element: <RepositoriesPage />,
  },
  {
    path: "/settings",
    element: <SettingsPage />,
  },
  {
    path: "/plugins",
    element: <PluginsPage />,
  },
  {
    path: "*",
    element: <Navigate to="/workspace" replace />,
  },
]);
