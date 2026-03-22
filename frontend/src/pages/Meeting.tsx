import Header from "../components/Header";
import MeetingPrep from "../components/MeetingPrep";
import MeetingDigest from "../components/MeetingDigest";
import Teleprompter from "../components/Teleprompter";
import SuggestionPanel from "../components/SuggestionPanel";
import StatusBar from "../components/StatusBar";
import AgentChatPanel from "../components/AgentChatPanel";
import { useMeeting } from "../hooks/useMeeting";
import { usePersona } from "../hooks/usePersona";

export default function Meeting({ onOpenSettings }: { onOpenSettings?: () => void }) {
  const {
    meeting,
    suggestions,
    agentChat,
    prepResult,
    isListening,
    audioLevel,
    audioError,
    isAgentResponding,
    prepare,
    start,
    pause,
    stop,
    sendAgentPrompt,
  } = useMeeting();
  const { persona, available: availablePersonas, switchPersona } = usePersona();

  const isPreMeeting = meeting.status === "idle" || meeting.status === "preparing";
  const isDigest = meeting.status === "ended" && suggestions.length > 0;
  const isLive = meeting.status === "active" || meeting.status === "paused";

  return (
    <div className="flex flex-col h-dvh bg-bg">
      <Header
        meeting={meeting}
        onStart={() => start()}
        onPause={pause}
        onStop={stop}
        onOpenSettings={onOpenSettings}
        persona={persona}
        availablePersonas={availablePersonas}
        onPersonaChange={switchPersona}
      />

      {isDigest ? (
        <MeetingDigest
          suggestions={suggestions}
          meeting={meeting}
          onNewMeeting={() => start()}
        />
      ) : isPreMeeting || meeting.status === "ended" ? (
        <MeetingPrep
          isPreparing={meeting.status === "preparing"}
          prepResult={prepResult}
          onPrepare={prepare}
          onStart={() => start()}
        />
      ) : isLive ? (
        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <div className="flex min-h-0 flex-1 flex-col">
            <Teleprompter suggestions={suggestions} />
            <div className="flex-1 min-h-0">
              <SuggestionPanel suggestions={suggestions} />
            </div>
          </div>
          <div className="min-h-[320px] border-t border-border lg:min-h-0 lg:w-[380px] lg:border-l lg:border-t-0">
            <AgentChatPanel
              messages={agentChat}
              isResponding={isAgentResponding}
              onSend={sendAgentPrompt}
            />
          </div>
        </div>
      ) : null}

      <StatusBar
        meeting={meeting}
        persona={persona.label}
        isListening={isListening}
        audioLevel={audioLevel}
        audioError={audioError}
      />
    </div>
  );
}
