// =========================================================================
// Pipeline card — name + status + flow strip + foot stats
// Four step kinds: source · extract · resolve · write (each color-coded)
// =========================================================================
function PipelineCard({ pipeline, compact, onOpen, onRun }) {
  const p = pipeline;

  const statusChip = {
    running: (
      <span className="chip cyan">
        <span className="dot" style={{ animation: "pulse-out 1.6s infinite" }}></span>running
      </span>
    ),
    success: (
      <span className="chip emerald">
        <span className="dot"></span>success
      </span>
    ),
    idle: (
      <span className="chip gray">
        <span className="dot"></span>idle
      </span>
    ),
    failed: (
      <span className="chip rose">
        <span className="dot"></span>failed
      </span>
    ),
  }[p.status];

  const targetChip = {
    Schema: (
      <span className="chip violet">
        <span className="dot"></span>schema
      </span>
    ),
    Data: (
      <span className="chip emerald">
        <span className="dot"></span>data
      </span>
    ),
    "Schema + Data": (
      <span className="chip cyan">
        <span className="dot"></span>schema + data
      </span>
    ),
  }[p.target];

  return (
    <div className="pipeline-card">
      <div className="pipeline-card-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="row gap-12" style={{ alignItems: "baseline" }}>
            <div className="name">{p.name}</div>
            <span className="muted mono" style={{ fontSize: 11 }}>
              {p.id}
            </span>
          </div>
          <div className="desc">{p.description}</div>
          <div className="chips">
            {statusChip}
            {targetChip}
            {p.tags?.map((t) => (
              <span key={t} className="chip mono">
                {t}
              </span>
            ))}
          </div>
        </div>
        <div className="row gap-12" style={{ flexShrink: 0 }}>
          {p.status === "running" ? (
            <button className="btn btn-ghost btn-sm">
              <Icon name="pause" size={11} /> Cancel
            </button>
          ) : (
            <button className="btn btn-accent btn-sm" onClick={() => onRun && onRun(p)}>
              <Icon name="play" size={11} /> Run
            </button>
          )}
          <button className="btn btn-ghost btn-sm btn-icon" title="More">
            <Icon name="more" size={13} />
          </button>
        </div>
      </div>

      <div className="pipeline-card-flow">
        {p.flow.flatMap((n, i, arr) => [
          <div key={"n" + i} className="flow-node" data-kind={n.kind}>
            <div className="ic">
              <Icon name={n.ic} size={13} />
            </div>
            <div>
              <div className="name">{n.name}</div>
              <div className="sub">{n.sub}</div>
            </div>
          </div>,
          i < arr.length - 1 ? <div key={"a" + i} className="flow-arrow"></div> : null,
        ])}
      </div>

      <div className="pipeline-card-foot">
        <div className="stat-item">
          <span className="l">last run</span>
          <span className="v">{p.lastRun}</span>
        </div>
        <div className="stat-item">
          <span className="l">ingested</span>
          <span className="v">{p.recent.ingested.toLocaleString()}</span>
        </div>
        <div className="stat-item">
          <span className="l">created</span>
          <span className="v ok">+{p.recent.created}</span>
        </div>
        <div className="stat-item">
          <span className="l">updated</span>
          <span className="v">~{p.recent.updated}</span>
        </div>
        <div className="stat-item">
          <span className="l">errors</span>
          <span className={"v" + (p.recent.errors ? " err" : "")}>{p.recent.errors}</span>
        </div>
      </div>
    </div>
  );
}

window.PipelineCard = PipelineCard;
