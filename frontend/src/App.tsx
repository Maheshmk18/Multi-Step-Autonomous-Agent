import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Activity,
  ArrowUpRight,
  Check,
  CircleAlert,
  Clock3,
  Database,
  Mail,
  MessageSquareText,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  SquarePen,
  X,
} from "lucide-react";

type RunEvent = {
  node?: string;
  agent?: string;
  status?: string;
  tool?: string;
  reason?: string;
};

type Run = {
  id: string;
  message: string;
  status: string;
  created_at: string;
  final_answer?: string | null;
  results: Array<{ agent: string; task: string; content: string }>;
  sources: Array<{ title: string; url: string }>;
  events: RunEvent[];
  pending_approval?: { id: string; tool_name: string; arguments: Record<string, unknown> } | null;
  error?: string | null;
};

type Approval = {
  id: string;
  run_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  message: string;
  created_at: string;
};

type Connectors = {
  groq: boolean;
  mongodb_data: boolean;
  tavily: boolean;
  gmail: boolean;
  langsmith: boolean;
};

type Tab = "new" | "runs" | "approvals";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(API_BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail || "The request could not be completed.");
  }
  return response.json() as Promise<T>;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function App() {
  const [tab, setTab] = useState<Tab>("new");
  const [runs, setRuns] = useState<Run[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [connectors, setConnectors] = useState<Connectors | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [editedArguments, setEditedArguments] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [nextRuns, nextApprovals, nextConnectors] = await Promise.all([
        api<Run[]>("/api/runs"),
        api<Approval[]>("/api/approvals"),
        api<Connectors>("/api/connectors"),
      ]);
      setRuns(nextRuns);
      setApprovals(nextApprovals);
      setConnectors(nextConnectors);
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Cannot reach the API.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1800);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const activeRun = useMemo(
    () => runs.find((run) => run.id === activeRunId) || null,
    [activeRunId, runs],
  );

  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = message.trim();
    if (!normalized || busy) return;
    setBusy(true);
    setError("");
    try {
      const run = await api<Run>("/api/runs", {
        method: "POST",
        body: JSON.stringify({ message: normalized }),
      });
      setActiveRunId(run.id);
      setMessage("");
      setTab("new");
      await refresh();
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Could not start the run.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(approval: Approval, action: "approve" | "edit" | "reject") {
    setBusy(true);
    setError("");
    try {
      let argumentsValue: Record<string, unknown> | undefined;
      if (action === "edit") {
        argumentsValue = JSON.parse(editedArguments[approval.id] || "{}") as Record<
          string,
          unknown
        >;
      }
      await api("/api/approvals/" + encodeURIComponent(approval.id) + "/decision", {
        method: "POST",
        body: JSON.stringify({ action, arguments: argumentsValue }),
      });
      setEditedArguments((current) => {
        const next = { ...current };
        delete next[approval.id];
        return next;
      });
      await refresh();
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : "Could not save decision.");
    } finally {
      setBusy(false);
    }
  }

  const navItems: Array<{ id: Tab; label: string; icon: typeof MessageSquareText }> = [
    { id: "new", label: "New run", icon: Plus },
    { id: "runs", label: "Run history", icon: Activity },
    { id: "approvals", label: "Approvals", icon: ShieldCheck },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Sparkles size={18} /></div>
          <div>
            <strong>Agent Console</strong>
            <span>Multi-agent workspace</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <nav className="navigation" aria-label="Main navigation">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              className={"nav-item" + (tab === id ? " active" : "")}
              key={id}
              onClick={() => setTab(id)}
              type="button"
            >
              <Icon size={17} />
              <span>{label}</span>
              {id === "approvals" && approvals.length > 0 && (
                <span className="nav-count">{approvals.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="connection-title">CONNECTORS</div>
          <ConnectorRow label="Groq" icon={<Sparkles size={15} />} connected={connectors?.groq} />
          <ConnectorRow
            label="MongoDB"
            icon={<Database size={15} />}
            connected={connectors?.mongodb_data}
          />
          <ConnectorRow label="Tavily" icon={<Search size={15} />} connected={connectors?.tavily} />
          <ConnectorRow label="Gmail" icon={<Mail size={15} />} connected={connectors?.gmail} />
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <div className="eyebrow">AGENT WORKSPACE</div>
            <h1>{tab === "new" ? "Run an agent" : tab === "runs" ? "Run history" : "Approvals"}</h1>
          </div>
          <div className="topbar-right">
            <span className="system-status"><span className="status-dot" /> Local workspace</span>
            <button className="new-button" onClick={() => setTab("new")} type="button">
              <Plus size={16} /> New run
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <CircleAlert size={17} />
            <span>{error}</span>
            <button aria-label="Dismiss" onClick={() => setError("")} type="button"><X size={16} /></button>
          </div>
        )}

        {tab === "new" && (
          <section className="workspace-content">
            <div className="intro-block">
              <div className="intro-icon"><Sparkles size={20} /></div>
              <div>
                <h2>What should the agent work on?</h2>
                <p>Research the web, review Gmail, or look up data in your allowed MongoDB collections.</p>
              </div>
            </div>

            <form className="composer-card" onSubmit={startRun}>
              <label className="sr-only" htmlFor="agent-request">Describe a task</label>
              <textarea
                id="agent-request"
                maxLength={8000}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Ask a question or describe a task…"
                value={message}
              />
              <div className="composer-footer">
                <span>Gmail actions pause for your approval</span>
                <button className="run-button" disabled={!message.trim() || busy} type="submit">
                  {busy ? "Starting…" : "Run agent"} <ArrowUpRight size={16} />
                </button>
              </div>
            </form>

            {activeRun && <RunDetail run={activeRun} />}

            {!activeRun && (
              <div className="examples-row">
                <span>Try an example</span>
                <button onClick={() => setMessage("Research the top three vector databases and compare their strengths.")} type="button">
                  Compare vector databases
                </button>
                <button onClick={() => setMessage("Find the latest unread emails and summarize the main requests.")} type="button">
                  Summarize recent email
                </button>
              </div>
            )}
          </section>
        )}

        {tab === "runs" && (
          <section className="list-content">
            {runs.length === 0 ? (
              <EmptyState icon={<Activity size={20} />} title="No runs yet" detail="Your completed and active runs will appear here." />
            ) : (
              <div className="run-layout">
                <div className="run-list">
                  {runs.map((run) => (
                    <button
                      className={"run-list-item" + (activeRunId === run.id ? " selected" : "")}
                      key={run.id}
                      onClick={() => setActiveRunId(run.id)}
                      type="button"
                    >
                      <div className="run-item-head">
                        <span className="run-item-icon"><MessageSquareText size={16} /></span>
                        <StatusBadge status={run.status} />
                      </div>
                      <strong>{run.message}</strong>
                      <span className="run-date"><Clock3 size={13} /> {formatDate(run.created_at)}</span>
                    </button>
                  ))}
                </div>
                <div className="run-detail-column">
                  {activeRun ? (
                    <RunDetail run={activeRun} />
                  ) : (
                    <EmptyState icon={<SquarePen size={20} />} title="Select a run" detail="Choose a run to see its progress and result." />
                  )}
                </div>
              </div>
            )}
          </section>
        )}

        {tab === "approvals" && (
          <section className="list-content">
            <div className="section-heading">
              <div>
                <h2>Review requested actions</h2>
                <p>Every Gmail draft or send waits here until you approve, edit, or reject it.</p>
              </div>
              <span className="count-pill">{approvals.length} pending</span>
            </div>
            {approvals.length === 0 ? (
              <EmptyState icon={<ShieldCheck size={20} />} title="You're all caught up" detail="The agent will pause here before making a Gmail change." />
            ) : (
              <div className="approval-list">
                {approvals.map((approval) => {
                  const original = JSON.stringify(approval.arguments, null, 2);
                  const edited = editedArguments[approval.id];
                  return (
                    <article className="approval-card" key={approval.id}>
                      <div className="approval-head">
                        <div className="approval-title">
                          <span className="approval-icon"><Mail size={17} /></span>
                          <div>
                            <strong>{titleCase(approval.tool_name)}</strong>
                            <span>{formatDate(approval.created_at)}</span>
                          </div>
                        </div>
                        <span className="pending-pill">Needs review</span>
                      </div>
                      <p className="approval-message">{approval.message}</p>
                      <label className="field-label" htmlFor={"approval-" + approval.id}>Email details</label>
                      <textarea
                        className="approval-json"
                        id={"approval-" + approval.id}
                        onChange={(event) =>
                          setEditedArguments((current) => ({
                            ...current,
                            [approval.id]: event.target.value,
                          }))
                        }
                        spellCheck={false}
                        value={edited ?? original}
                      />
                      <div className="approval-actions">
                        <button className="text-button reject-button" disabled={busy} onClick={() => void decide(approval, "reject")} type="button">
                          Reject
                        </button>
                        <div>
                          <button className="secondary-button" disabled={busy || edited === undefined} onClick={() => void decide(approval, "edit")} type="button">
                            Edit &amp; approve
                          </button>
                          <button className="approve-button" disabled={busy} onClick={() => void decide(approval, "approve")} type="button">
                            <Check size={15} /> Approve
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

function ConnectorRow({
  label,
  icon,
  connected,
}: {
  label: string;
  icon: ReactNode;
  connected?: boolean;
}) {
  return (
    <div className="connector-row">
      <span className="connector-icon">{icon}</span>
      <span>{label}</span>
      <span className={"connector-state" + (connected ? " connected" : "")}>
        {connected === undefined ? "…" : connected ? "Ready" : "Setup"}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={"status-badge status-" + status.replaceAll("_", "-")}>{titleCase(status)}</span>;
}

function EmptyState({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{icon}</span>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

function RunDetail({ run }: { run: Run }) {
  return (
    <article className="run-detail-card">
      <div className="detail-header">
        <div>
          <div className="eyebrow">RUN DETAILS</div>
          <h2>{run.message}</h2>
        </div>
        <StatusBadge status={run.status} />
      </div>
      <div className="detail-meta"><Clock3 size={14} /> Started {formatDate(run.created_at)}</div>

      {run.pending_approval && (
        <div className="inline-approval">
          <ShieldCheck size={17} />
          <span>Waiting for approval: <strong>{titleCase(run.pending_approval.tool_name)}</strong></span>
        </div>
      )}

      {(run.events || []).length > 0 && (
        <div className="activity-section">
          <h3>Activity</h3>
          <div className="activity-list">
            {run.events.map((event, index) => (
              <div className="activity-item" key={run.id + "-event-" + index}>
                <span className="activity-node"><span /></span>
                <div>
                  <strong>{titleCase(event.agent || event.node || "Agent")}</strong>
                  <span>
                    {event.tool ? titleCase(event.tool) + " · " : ""}
                    {titleCase(event.status || "completed")}
                    {event.reason ? " · " + event.reason : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {run.final_answer && (
        <div className="answer-section">
          <h3>Result</h3>
          <div className="answer-text">{run.final_answer}</div>
        </div>
      )}

      {run.sources?.length > 0 && (
        <div className="source-section">
          <h3>Sources</h3>
          {run.sources.map((source) => (
            <a href={source.url} key={source.url} rel="noreferrer" target="_blank">
              <span>{source.title}</span><ArrowUpRight size={14} />
            </a>
          ))}
        </div>
      )}

      {run.error && <div className="run-error"><CircleAlert size={16} /> {run.error}</div>}
    </article>
  );
}

export default App;
