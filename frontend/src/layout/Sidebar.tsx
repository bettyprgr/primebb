import { NavLink } from "react-router-dom";
import { Badge } from "../components/Badge";

const sections = [
  { title: "PrimeBB", links: [{ to: "/", label: "Dashboard" }, { to: "/tools", label: "Tool Launcher" }] },
  { title: "Tools", links: [{ to: "/tools/social-pumper", label: "Social Pumper" }, { to: "/tools/amazon-creation", label: "Amazon Creation" }] },
  { title: "Core", links: [{ to: "/accounts", label: "Accounts" }, { to: "/browsers", label: "Browsers" }, { to: "/tasks", label: "Tasks" }, { to: "/services", label: "Services" }, { to: "/config", label: "Config" }] },
];

export function Sidebar({ connected }: { connected: boolean }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">P</span>
        <strong>PrimeBB</strong>
        <Badge tone={connected ? "success" : "warning"} style={{ marginLeft: "auto" }}>
          {connected ? "Connected" : "Offline"}
        </Badge>
      </div>
      {sections.map((section) => (
        <nav key={section.title} className="nav-section">
          <h3>{section.title}</h3>
          {section.links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === "/"} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              {link.label}
            </NavLink>
          ))}
        </nav>
      ))}
    </aside>
  );
}

