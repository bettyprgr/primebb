import { useOutletContext } from "react-router-dom";
import type { usePrimeBbWebSocket } from "../../api/websocket";
import { SocialPumperRunForm } from "./SocialPumperRunForm";

export function SocialPumperWorkspace() {
  const live = useOutletContext<ReturnType<typeof usePrimeBbWebSocket>>();

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>Social Pumper</h1>
        <p>Gmail authentication and Google OAuth connection for YouTube, Quora, Reddit, X, and eBay.</p>
      </div>
      <SocialPumperRunForm live={live} />
    </div>
  );
}
