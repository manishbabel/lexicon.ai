import { useState, useEffect } from "react";
import { Save, Loader2, Check, Key, Cpu, ChevronLeft } from "lucide-react";

interface SettingsData {
  openai_api_key: string;
  anthropic_api_key: string;
  deepgram_api_key: string;
  default_llm_provider: string;
  default_llm_model: string;
  chief_llm_provider: string;
  chief_llm_model: string;
  software_engineer_llm_provider: string;
  software_engineer_llm_model: string;
  log_level: string;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  has_deepgram_key: boolean;
}

const PROVIDERS = ["openai", "anthropic", "litellm"];
const MODELS = ["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"];
const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-text-2 mb-1.5 block">
        {label}
        {hint && <span className="text-text-3 font-normal ml-1">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-3/50 focus:outline-none focus:border-accent transition-colors"
    />
  );
}

function Select({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  placeholder?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text focus:outline-none focus:border-accent transition-colors cursor-pointer"
    >
      {placeholder && (
        <option value="" className="text-text-3">
          {placeholder}
        </option>
      )}
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function KeyStatus({ hasKey }: { hasKey: boolean }) {
  return hasKey ? (
    <span className="text-[10px] text-term flex items-center gap-1">
      <Check size={10} /> configured
    </span>
  ) : (
    <span className="text-[10px] text-text-3">not set</span>
  );
}

export default function Settings({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Form state — only for fields user changes
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [deepgramKey, setDeepgramKey] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");
  const [chiefProvider, setChiefProvider] = useState("");
  const [chiefModel, setChiefModel] = useState("");
  const [seProvider, setSeProvider] = useState("");
  const [seModel, setSeModel] = useState("");
  const [logLevel, setLogLevel] = useState("INFO");

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d: SettingsData) => {
        setData(d);
        setProvider(d.default_llm_provider || "openai");
        setModel(d.default_llm_model || "gpt-4o");
        setChiefProvider(d.chief_llm_provider || "");
        setChiefModel(d.chief_llm_model || "");
        setSeProvider(d.software_engineer_llm_provider || "");
        setSeModel(d.software_engineer_llm_model || "");
        setLogLevel(d.log_level || "INFO");
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);

    const body: Record<string, string> = {
      default_llm_provider: provider,
      default_llm_model: model,
      chief_llm_provider: chiefProvider,
      chief_llm_model: chiefModel,
      software_engineer_llm_provider: seProvider,
      software_engineer_llm_model: seModel,
      log_level: logLevel,
    };

    // Only send keys if user typed a new one
    if (openaiKey) body.openai_api_key = openaiKey;
    if (anthropicKey) body.anthropic_api_key = anthropicKey;
    if (deepgramKey) body.deepgram_api_key = deepgramKey;

    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-text-3" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-lg mx-auto px-6 py-8">
        {/* Back */}
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-xs text-text-3 hover:text-text mb-6 transition-colors cursor-pointer"
        >
          <ChevronLeft size={14} />
          Back
        </button>

        <h1 className="text-2xl font-bold text-text tracking-tight mb-1">
          Settings
        </h1>
        <p className="text-sm text-text-3 mb-8">
          API keys and model configuration.
        </p>

        {/* API Keys */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Key size={14} className="text-text-3" />
            <h2 className="text-sm font-semibold text-text">API Keys</h2>
          </div>

          <div className="flex flex-col gap-4">
            <Field label="OpenAI" hint={data?.openai_api_key || undefined}>
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <TextInput
                    value={openaiKey}
                    onChange={setOpenaiKey}
                    placeholder="sk-..."
                    type="password"
                  />
                </div>
                <KeyStatus hasKey={data?.has_openai_key ?? false} />
              </div>
            </Field>

            <Field label="Anthropic" hint={data?.anthropic_api_key || undefined}>
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <TextInput
                    value={anthropicKey}
                    onChange={setAnthropicKey}
                    placeholder="sk-ant-..."
                    type="password"
                  />
                </div>
                <KeyStatus hasKey={data?.has_anthropic_key ?? false} />
              </div>
            </Field>

            <Field label="Deepgram" hint={data?.deepgram_api_key || undefined}>
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <TextInput
                    value={deepgramKey}
                    onChange={setDeepgramKey}
                    placeholder="dg-..."
                    type="password"
                  />
                </div>
                <KeyStatus hasKey={data?.has_deepgram_key ?? false} />
              </div>
            </Field>
          </div>
        </div>

        {/* Model Config */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Cpu size={14} className="text-text-3" />
            <h2 className="text-sm font-semibold text-text">Model Routing</h2>
          </div>

          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Default provider">
                <Select value={provider} onChange={setProvider} options={PROVIDERS} />
              </Field>
              <Field label="Default model">
                <Select value={model} onChange={setModel} options={MODELS} />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Chief provider" hint="override">
                <Select
                  value={chiefProvider}
                  onChange={setChiefProvider}
                  options={PROVIDERS}
                  placeholder="Use default"
                />
              </Field>
              <Field label="Chief model" hint="override">
                <Select
                  value={chiefModel}
                  onChange={setChiefModel}
                  options={MODELS}
                  placeholder="Use default"
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="SW Engineer provider" hint="override">
                <Select
                  value={seProvider}
                  onChange={setSeProvider}
                  options={PROVIDERS}
                  placeholder="Use default"
                />
              </Field>
              <Field label="SW Engineer model" hint="override">
                <Select
                  value={seModel}
                  onChange={setSeModel}
                  options={MODELS}
                  placeholder="Use default"
                />
              </Field>
            </div>

            <Field label="Log level">
              <Select value={logLevel} onChange={setLogLevel} options={LOG_LEVELS} />
            </Field>
          </div>
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-2"
        >
          {saving ? (
            <Loader2 size={14} className="animate-spin" />
          ) : saved ? (
            <Check size={14} />
          ) : (
            <Save size={14} />
          )}
          {saving ? "Saving..." : saved ? "Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}
