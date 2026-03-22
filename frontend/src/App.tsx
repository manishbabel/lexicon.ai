import { useState } from "react";
import { WebSocketProvider } from "./components/WebSocketProvider";
import Meeting from "./pages/Meeting";
import Settings from "./pages/Settings";

type Page = "meeting" | "settings";

export default function App() {
  const [page, setPage] = useState<Page>("meeting");

  return (
    <WebSocketProvider>
      {page === "meeting" && (
        <Meeting onOpenSettings={() => setPage("settings")} />
      )}
      {page === "settings" && (
        <Settings onBack={() => setPage("meeting")} />
      )}
    </WebSocketProvider>
  );
}
