// Main app — desktop-first router + chrome + tweaks

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/ {
  accent: "amber",
  shellTone: "slate",
  darkCanvas: false,
  windowChrome: true,
  showStatusBar: true,
  monoIds: true,
}; /*EDITMODE-END*/

function App() {
  const params = new URLSearchParams(location.hash.slice(1));
  const initial = params.get("r") || "dashboard";
  const [route, setRoute] = useState(initial);
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [tweaks, setTweak] = window.useTweaks
    ? window.useTweaks(TWEAK_DEFAULTS)
    : [TWEAK_DEFAULTS, () => {}];

  const nav = useCallback((r) => {
    setRoute(r);
    history.replaceState(null, "", "#r=" + r);
  }, []);

  // Apply tweaks (accent + shell tone)
  useEffect(() => {
    const root = document.documentElement;
    const accents = {
      cyan: { c1: "#22D3EE", c2: "#06B6D4", cd: "#0E7EA3" },
      violet: { c1: "#A78BFA", c2: "#8B5CF6", cd: "#6D28D9" },
      emerald: { c1: "#34D399", c2: "#10B981", cd: "#047857" },
      amber: { c1: "#FBBF24", c2: "#F59E0B", cd: "#B45309" },
    };
    const a = accents[tweaks.accent] || accents.cyan;
    root.style.setProperty("--accent-cyan", a.c1);
    root.style.setProperty("--accent-cyan-2", a.c2);
    root.style.setProperty("--accent-cyan-deep", a.cd);

    if (tweaks.shellTone === "inkwell") {
      root.style.setProperty("--shell-bg", "#070A0E");
      root.style.setProperty("--shell-bg-2", "#0A0E13");
      root.style.setProperty("--shell-surface", "#10161F");
    } else if (tweaks.shellTone === "slate") {
      root.style.setProperty("--shell-bg", "#0F1729");
      root.style.setProperty("--shell-bg-2", "#13203A");
      root.style.setProperty("--shell-surface", "#1B2949");
    } else {
      root.style.setProperty("--shell-bg", "#0B0F14");
      root.style.setProperty("--shell-bg-2", "#0F141B");
      root.style.setProperty("--shell-surface", "#131A23");
    }

    document.body.classList.toggle("with-chrome", !!tweaks.windowChrome);
    document.body.classList.toggle("no-statusbar", !tweaks.showStatusBar);
    document.body.classList.toggle("dark-canvas", !!tweaks.darkCanvas);
  }, [
    tweaks.accent,
    tweaks.shellTone,
    tweaks.windowChrome,
    tweaks.showStatusBar,
    tweaks.darkCanvas,
  ]);

  // ⌘K palette
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
      if (e.key === "Escape") {
        setPaletteOpen(false);
        setWorkspaceOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  let page;
  switch (route) {
    case "dashboard":
      page = <DashboardPage onNav={nav} />;
      break;
    case "schema/taxonomies":
      page = <TaxonomiesPage />;
      break;
    case "schema/schemes":
      page = <ConceptSchemesPage />;
      break;
    case "schema/classes":
      page = <ClassesPage />;
      break;
    case "schema/properties":
      page = <PropertiesPage />;
      break;
    case "schema/relationships":
      page = <RelationshipsPage />;
      break;
    case "data/individuals":
      page = <IndividualsPage />;
      break;
    case "data/datasets":
      page = <IndividualsPage />;
      break;
    case "pipelines/all":
    case "pipelines/runs":
    case "pipelines/flavors":
      page = <PipelinesPage />;
      break;
    case "reference/sources":
    case "reference/grounding":
      page = <ReferencePage />;
      break;
    case "settings":
      page = window.SettingsPage ? <window.SettingsPage /> : null;
      break;
    default:
      page = <DashboardPage onNav={nav} />;
  }

  return (
    <div className={"desktop-frame" + (tweaks.windowChrome ? " with-chrome" : "")}>
      {tweaks.windowChrome && (
        <Titlebar
          onPalette={() => setPaletteOpen(true)}
          onSwitchWs={() => setWorkspaceOpen(true)}
        />
      )}

      <div className={"app-shell" + (collapsed ? " collapsed" : "")}>
        <Sidebar
          route={route}
          onNav={nav}
          collapsed={collapsed}
          onToggle={() => setCollapsed(!collapsed)}
        />
        <div className="workspace">
          <Topbar
            route={route}
            onPalette={() => setPaletteOpen(true)}
            onSwitchWs={() => setWorkspaceOpen(true)}
          />
          <div className="canvas-area">{page}</div>
          {tweaks.showStatusBar && <Statusbar route={route} />}
        </div>
      </div>

      {paletteOpen && (
        <CommandPalette
          onClose={() => setPaletteOpen(false)}
          onNav={(r) => {
            nav(r);
            setPaletteOpen(false);
          }}
        />
      )}
      {workspaceOpen && <WorkspaceSwitcher onClose={() => setWorkspaceOpen(false)} />}

      {window.TweaksPanel && (
        <window.TweaksPanel title="Tweaks" defaultOpen={false}>
          <window.TweakSection title="Studio appearance">
            <window.TweakToggle
              label="Dark canvas"
              value={tweaks.darkCanvas}
              onChange={(v) => setTweak("darkCanvas", v)}
            />
            <window.TweakRadio
              label="Accent"
              value={tweaks.accent}
              onChange={(v) => setTweak("accent", v)}
              options={[
                { value: "cyan", label: "Cyan" },
                { value: "violet", label: "Violet" },
                { value: "emerald", label: "Emerald" },
                { value: "amber", label: "Amber" },
              ]}
            />
            <window.TweakRadio
              label="Shell tone"
              value={tweaks.shellTone}
              onChange={(v) => setTweak("shellTone", v)}
              options={[
                { value: "deep", label: "Deep" },
                { value: "inkwell", label: "Inkwell" },
                { value: "slate", label: "Slate" },
              ]}
            />
          </window.TweakSection>
          <window.TweakSection title="Desktop chrome">
            <window.TweakToggle
              label="Show window titlebar"
              value={tweaks.windowChrome}
              onChange={(v) => setTweak("windowChrome", v)}
            />
            <window.TweakToggle
              label="Show status bar"
              value={tweaks.showStatusBar}
              onChange={(v) => setTweak("showStatusBar", v)}
            />
          </window.TweakSection>
          <window.TweakSection title="Quick actions">
            <window.TweakButton
              label="Open command palette (⌘K)"
              onClick={() => setPaletteOpen(true)}
            />
            <window.TweakButton label="Switch workspace" onClick={() => setWorkspaceOpen(true)} />
            <window.TweakButton
              label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={() => setCollapsed(!collapsed)}
            />
          </window.TweakSection>
        </window.TweaksPanel>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <window.StoreProvider>
    <App />
    <window.ToastViewport />
  </window.StoreProvider>,
);
