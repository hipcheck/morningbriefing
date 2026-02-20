import { readFileSync, readdirSync } from "fs";
import path from "path";

type MemoryDoc = {
  id: string;
  title: string;
  file: string;
  preview: string;
};

// Server-rendered file read (works on server deployments if files are bundled).
// For real usage, you probably want to store memories in Convex and/or fetch from
// your OpenClaw host via an authenticated API.
function loadMemoryDocs(): MemoryDoc[] {
  const root = process.cwd();
  const docs: MemoryDoc[] = [];

  // MEMORY.md
  try {
    const p = path.join(root, "..", "MEMORY.md");
    const content = readFileSync(p, "utf8");
    docs.push({
      id: "memory-md",
      title: "MEMORY.md",
      file: p,
      preview: content.slice(0, 500),
    });
  } catch {
    // ignore
  }

  // memory/*.md (daily notes)
  try {
    const dir = path.join(root, "..", "memory");
    const files = readdirSync(dir).filter((f) => f.endsWith(".md"));
    for (const f of files.slice(0, 20)) {
      const p = path.join(dir, f);
      const content = readFileSync(p, "utf8");
      docs.push({
        id: f,
        title: f,
        file: p,
        preview: content.slice(0, 500),
      });
    }
  } catch {
    // ignore
  }

  return docs;
}

export default function MemoryPage() {
  const docs = loadMemoryDocs();

  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-semibold">Memory</h1>
      <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
        Beautiful documents + fast search across assistant memories.
      </p>

      <div className="mt-6">
        <input
          className="w-full rounded-lg border px-3 py-2 text-sm"
          placeholder="Search (stub) — next step: implement real search in Convex"
          disabled
        />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        {docs.length ? (
          docs.map((d) => (
            <article key={d.id} className="rounded-xl border p-4">
              <div className="font-medium">{d.title}</div>
              <pre className="mt-3 text-xs whitespace-pre-wrap text-muted-foreground">
                {d.preview}
                {d.preview.length >= 500 ? "\n…" : ""}
              </pre>
            </article>
          ))
        ) : (
          <div className="text-sm text-muted-foreground">
            No memory docs found in this deployment environment yet.
          </div>
        )}
      </div>

      <div className="mt-10 text-sm text-muted-foreground">
        Next step: store and index memories in Convex (or ingest from OpenClaw
        via webhook) so it works on Vercel.
      </div>
    </main>
  );
}
