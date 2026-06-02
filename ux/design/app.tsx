// =========================================================================
// Context Studio — App router
// Hash routing (#r=…), keyboard shortcuts, overlays.
// =========================================================================

function App() {
  const initialRoute = (() => {
    const h = (location.hash || "").match(/r=([^&]+)/);
    return h ? decodeURIComponent(h[1]) : "dashboard";
  })();
  const [route, setRoute] = useState(initialRoute);
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [wsOpen, setWsOpen] = useState(false);
  const [newClassOpen, setNewClassOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  // ⌘K toggle
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
      if (e.key === "Escape") {
        setPaletteOpen(false);
        setWsOpen(false);
        setNewClassOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Persist route to hash
  useEffect(() => {
    location.hash = "r=" + encodeURIComponent(route);
  }, [route]);

  // Sync route from hash on back/forward
  useEffect(() => {
    const onHash = () => {
      const m = (location.hash || "").match(/r=([^&]+)/);
      if (m) setRoute(decodeURIComponent(m[1]));
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (r) => {
    setRoute(r);
    setPaletteOpen(false);
    setWsOpen(false);
  };

  // Toast helper
  const pushToast = (t) => {
    const id = Date.now() + Math.random();
    setToasts((ts) => [...ts, { ...t, id }]);
    setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 4500);
  };

  // ---- Route → page ----
  const Page = (() => {
    if (route === "dashboard") return <DashboardPage onNav={navigate} />;
    if (route.startsWith("schema/"))
      return (
        <SchemaPage route={route} onNav={navigate} onOpenNewClass={() => setNewClassOpen(true)} />
      );
    if (route === "data/individuals") return <IndividualsPage onNav={navigate} />;
    if (route.startsWith("data/")) return <StubPage route={route} />;
    if (route.startsWith("pipelines")) return <PipelinesPage route={route} onNav={navigate} />;
    if (route.startsWith("reference")) return <ReferencePage route={route} onNav={navigate} />;
    if (route === "graph") return <GraphViewPage onNav={navigate} />;
    if (route === "settings") return <SettingsPage />;
    return <StubPage route={route} />;
  })();

  return (
    <div className="desktop">
      <div className="app-shell">
        <Sidebar
          route={route}
          onNav={navigate}
          collapsed={collapsed}
          onToggle={() => setCollapsed((v) => !v)}
        />
        <div className="workspace">
          <Topbar
            route={route}
            onPalette={() => setPaletteOpen(true)}
            onSwitchWs={() => setWsOpen(true)}
          />
          <div className="canvas-area">{Page}</div>
        </div>
      </div>
      <Statusbar />

      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} onNav={navigate} />}
      {wsOpen && <WorkspaceSwitcher onClose={() => setWsOpen(false)} />}

      <Modal
        open={newClassOpen}
        onClose={() => setNewClassOpen(false)}
        title={<>New class</>}
        subtitle={
          <>
            Classes belong to a concept scheme and inherit property definitions from their parent.
          </>
        }
        footer={
          <>
            <span className="modal-foot-hint">POST /classes</span>
            <button className="btn btn-ghost" onClick={() => setNewClassOpen(false)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                setNewClassOpen(false);
                pushToast({
                  kind: "success",
                  title: "Class created",
                  subtitle: "cls_neuron_motor · sch_cell_bio",
                });
              }}
            >
              Create class
            </button>
          </>
        }
      >
        <div className="field">
          <div className="lab">
            Identifier<span className="hint-r">snake_case · required</span>
          </div>
          <input className="input mono" defaultValue="cls_neuron_motor" autoFocus />
          <div className="hint">
            Must match <span className="mono">/^cls_[a-z][a-z0-9_]*$/</span>
          </div>
        </div>
        <div className="field">
          <div className="lab">Display title</div>
          <input className="input" defaultValue="Motor neuron" />
        </div>
        <div className="field">
          <div className="lab">Concept scheme</div>
          <select
            className="select"
            style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 12.5 }}
          >
            {window.CS_DATA.concept_schemes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} · {s.id}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <div className="lab">
            Parent class<span className="hint-r">optional</span>
          </div>
          <select
            className="select"
            style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 12.5 }}
          >
            <option value="">— none —</option>
            {window.CS_DATA.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} · {c.id}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <div className="lab">Description</div>
          <textarea
            className="input"
            rows={3}
            defaultValue="Motor neurons carry signals from the central nervous system to muscle fibers."
          />
        </div>
      </Modal>

      <ToastStack toasts={toasts} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
