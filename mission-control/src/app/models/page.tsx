type ModelUsage = {
  model: string;
  calls: number;
  lastUsedAt?: string;
  rateLimits: number;
};

// TODO: Replace with ingestion from OpenClaw session logs / events.
const mock: ModelUsage[] = [
  { model: "openai-codex/gpt-5.2", calls: 0, rateLimits: 0 },
  { model: "anthropic/claude-opus-4-6", calls: 0, rateLimits: 0 },
  { model: "anthropic/claude-sonnet-4-5", calls: 0, rateLimits: 0 },
];

export default function ModelsPage() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-semibold">AI model usage</h1>
      <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
        Overview of how each model was used, plus rate limit events.
      </p>

      <div className="mt-8 rounded-xl border">
        <div className="grid grid-cols-12 border-b px-4 py-3 text-xs text-muted-foreground">
          <div className="col-span-6">Model</div>
          <div className="col-span-2">Calls</div>
          <div className="col-span-2">Rate limits</div>
          <div className="col-span-2">Last used</div>
        </div>
        {mock.map((m) => (
          <div
            key={m.model}
            className="grid grid-cols-12 px-4 py-3 border-b last:border-b-0"
          >
            <div className="col-span-6 text-sm font-medium">{m.model}</div>
            <div className="col-span-2 text-sm">{m.calls}</div>
            <div className="col-span-2 text-sm">{m.rateLimits}</div>
            <div className="col-span-2 text-sm text-muted-foreground">
              {m.lastUsedAt ? new Date(m.lastUsedAt).toLocaleString() : "—"}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 text-sm text-muted-foreground">
        Next step: add an ingestion pipeline that records model + errors (429s)
        into Convex.
      </div>
    </main>
  );
}
