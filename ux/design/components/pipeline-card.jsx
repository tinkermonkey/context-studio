// Pipeline visual card — used on dashboard + pipelines page

function PipelineCard({ pipeline, compact, onOpen }) {
  const p = pipeline;
  const statusChip = {
    running: (
      <span className="chip cyan">
        <span className="dot" style={{ animation: "pulse 1.6s infinite" }}></span>running
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
        <div style={{ minWidth: 0 }}>
          <div className="row gap-12">
            <div className="name">{p.name}</div>
            {statusChip}
            {targetChip}
          </div>
          <div className="desc">{p.description}</div>
        </div>
        <div className="row gap-12">
          <button className="btn btn-ghost btn-sm" onClick={() => onOpen && onOpen(p)}>
            <Icon name="play" /> Run
          </button>
          <button className="btn btn-ghost btn-sm btn-icon">
            <Icon name="more" />
          </button>
        </div>
      </div>
      <div className="pipeline-card-flow">
        {p.flow.map((n, i) => (
          <Fragment key={i}>
            <div className="flow-node" data-kind={n.kind}>
              <div className="ic">
                <Icon
                  name={
                    n.kind === "source"
                      ? "reference"
                      : n.kind === "extract"
                        ? "sparkle"
                        : n.kind === "resolve"
                          ? "link"
                          : "database"
                  }
                  size={13}
                />
              </div>
              <div>
                <div className="name">{n.name}</div>
                <div className="sub">{n.sub}</div>
              </div>
            </div>
            {i < p.flow.length - 1 && <div className="flow-arrow"></div>}
          </Fragment>
        ))}
      </div>
      <div className="pipeline-card-foot">
        <div className="stat-item">
          <span className="l">last run</span>
          <span className="v">{p.lastRun}</span>
        </div>
        <div className="stat-item">
          <span className="l">ingested</span>
          <span className="v">{p.recent.ingested}</span>
        </div>
        <div className="stat-item">
          <span className="l">created</span>
          <span className="v">+{p.recent.created}</span>
        </div>
        <div className="stat-item">
          <span className="l">updated</span>
          <span className="v">~{p.recent.updated}</span>
        </div>
        <div className="stat-item">
          <span className="l">errors</span>
          <span
            className="v"
            style={{ color: p.recent.errors ? "var(--accent-rose)" : "var(--canvas-fg-1)" }}
          >
            {p.recent.errors}
          </span>
        </div>
      </div>
    </div>
  );
}

window.PipelineCard = PipelineCard;
