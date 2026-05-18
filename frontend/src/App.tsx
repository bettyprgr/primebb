import { Route, Routes } from "react-router-dom";
import { DashboardLayout } from "./layout/DashboardLayout";
import { DashboardHome } from "./pages/DashboardHome";
import { ToolLauncher } from "./pages/ToolLauncher";
import { ConfigPage } from "./pages/ConfigPage";
import { NotFound } from "./pages/NotFound";
import { AccountsPage } from "./features/accounts/AccountsPage";
import { BrowsersPage } from "./features/browsers/BrowsersPage";
import { TasksPage } from "./features/tasks/TasksPage";
import { ServicesPage } from "./features/services/ServicesPage";
import { SocialPumperWorkspace } from "./features/social-pumper/SocialPumperWorkspace";
import { AmazonCreationWorkspace } from "./features/amazon-creation/AmazonCreationWorkspace";

export function App() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<DashboardHome />} />
        <Route path="tools" element={<ToolLauncher />} />
        <Route path="tools/social-pumper" element={<SocialPumperWorkspace />} />
        <Route path="tools/amazon-creation" element={<AmazonCreationWorkspace />} />
        <Route path="accounts" element={<AccountsPage />} />
        <Route path="browsers" element={<BrowsersPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="services" element={<ServicesPage />} />
        <Route path="config" element={<ConfigPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
