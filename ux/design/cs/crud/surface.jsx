// =========================================================================
// Context Studio — EntitySurface
// The reusable master/detail surface used by every schema & data page:
//   • SelectableTable (left)  +  EntityInspector (right, 1fr / 420px)
//   • row selection → BulkBar with delete + per-type bulk operations
//   • per-row RowMenu (Edit / Duplicate / Delete)
//   • CascadeDeleteDialog for single + bulk deletes
//   • imperative startCreate()/startCreateChild() via ref (header + palette
//     + contextual "+ child" all funnel through it)
// =========================================================================

const EntitySurface = forwardRef(function EntitySurface(
  {
    type,
    rows,
    columns,
    bulkOps = [{ id: "delete", label: "Delete", icon: "trash", danger: true, kind: "delete" }],
    createContext,
    inspectorEmpty,
    inspectorWidth = 420,
    childAction,
  },
  ref,
) {
  const data = useCS();
  const col = CSStore.collectionOf[type];
  const collection = data[col];

  const [selectedId, setSelectedId] = useState(null);
  const [mode, setMode] = useState("view"); // view | edit | create
  const [initialDraft, setInitialDraft] = useState(null);
  const [draftKey, setDraftKey] = useState(0);
  const [selection, setSelection] = useState(() => new Set());
  const [del, setDel] = useState({ open: false, target: null, ids: null });
  const [bulkOp, setBulkOp] = useState(null); // {op, value}

  const entity = selectedId ? collection.find((x) => x.id === selectedId) : null;
  // Create now shares the right-rail space with the details panel (table stays visible).
  const isCreate = mode === "create";
  const showRail = (mode === "view" || mode === "edit") && !!entity;
  const isEmpty = collection.length === 0;

  // imperative API for page header / command palette / contextual add
  const startCreate = (ctx) => {
    setInitialDraft(newDraft(type, ctx || (createContext ? createContext() : {})));
    setSelectedId(null);
    setMode("create");
    setDraftKey((k) => k + 1);
  };
  useImperativeHandle(ref, () => ({ startCreate }), [type, createContext]);

  const selectRow = (row) => {
    setSelectedId(row.id);
    setMode("view");
  };
  const enterEdit = () => setMode("edit");
  const done = () => setMode("view");
  const onCreated = (id) => {
    setSelectedId(id);
    setMode("view");
  };
  const cancelCreate = () => {
    setMode(entity ? "view" : "view");
    setInitialDraft(null);
  };

  const duplicate = (e) => {
    const base = { ...e };
    if (base.identifier) {
      base.identifier = base.identifier + "_copy";
      base.id = "";
    } else {
      base.id = (base.id || "") + "_copy";
    }
    base.title = (base.title || base.name || "") + " (copy)";
    base.version = undefined;
    base.updated = undefined;
    setInitialDraft(base);
    setSelectedId(null);
    setMode("create");
    setDraftKey((k) => k + 1);
  };

  const askDelete = (e) => setDel({ open: true, target: e, ids: null });
  const confirmDelete = () => {
    if (del.ids) {
      CSStore.bulkRemove(type, del.ids);
      setSelection(new Set());
    } else if (del.target) {
      CSStore.remove(type, del.target.id);
      if (selectedId === del.target.id) setSelectedId(null);
    }
    setDel({ open: false, target: null, ids: null });
  };

  // selection
  const toggle = (id) =>
    setSelection((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const toggleAll = (on) => setSelection(on ? new Set(rows.map((r) => r.id)) : new Set());
  const clearSel = () => setSelection(new Set());

  const rowActions = () => [
    { id: "edit", label: "Edit", icon: "edit" },
    { id: "duplicate", label: "Duplicate", icon: "copy" },
    ...(childAction
      ? [{ id: "__child", label: childAction.label, icon: childAction.icon || "plus" }]
      : []),
    { type: "separator" },
    { id: "delete", label: "Delete…", icon: "trash", danger: true },
  ];
  const onRowAction = (row, a) => {
    if (a === "edit") {
      setSelectedId(row.id);
      setMode("edit");
    }
    if (a === "duplicate") duplicate(row);
    if (a === "__child" && childAction) childAction.onTrigger(row);
    if (a === "delete") askDelete(row);
  };

  // bulk ops
  const runBulk = (opId) => {
    const op = bulkOps.find((o) => o.id === opId);
    if (!op) return;
    if (op.kind === "delete") {
      setDel({ open: true, target: null, ids: [...selection] });
      return;
    }
    setBulkOp({
      op,
      value: op.default ?? (op.options && op.options[0] ? op.options[0].value : ""),
    });
  };
  const applyBulk = () => {
    const { op, value } = bulkOp;
    const patch = op.apply ? op.apply(value, data) : { [op.field]: value };
    CSStore.bulkUpdate(type, [...selection], patch, op.label + " · " + value);
    setBulkOp(null);
    setSelection(new Set());
  };

  return (
    <>
      {isCreate || !isEmpty ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isCreate || showRail ? `1fr ${inspectorWidth}px` : "1fr",
            gap: 14,
            alignItems: "start",
          }}
        >
          <SelectableTable
            columns={columns}
            data={rows}
            selectedId={selectedId}
            onRowClick={selectRow}
            selection={selection}
            onToggle={toggle}
            onToggleAll={toggleAll}
            rowActions={rowActions}
            onRowAction={onRowAction}
          />
          {isCreate ? (
            <CreateDrawer
              inline
              key={`create-${draftKey}`}
              type={type}
              initialDraft={initialDraft}
              onCreated={onCreated}
              onClose={cancelCreate}
            />
          ) : showRail && entity ? (
            <EntityInspector
              key={`${entity.id}-${mode}`}
              type={type}
              entity={entity}
              mode={mode}
              onEnterEdit={enterEdit}
              onDone={done}
              onDelete={() => askDelete(entity)}
              onDuplicate={() => duplicate(entity)}
            />
          ) : null}
        </div>
      ) : (
        <CreateEmptyState
          icon={(inspectorEmpty && inspectorEmpty.icon) || "layout"}
          noun={CSStore.NICE[type]}
          onCreate={() => startCreate()}
        />
      )}

      <BulkBar
        count={selection.size}
        label={CSStore.NICE[type]}
        actions={bulkOps.map((o) => ({ id: o.id, label: o.label, icon: o.icon, danger: o.danger }))}
        onAction={runBulk}
        onClear={clearSel}
      />

      <CascadeDeleteDialog
        open={del.open}
        type={type}
        target={del.target}
        ids={del.ids}
        onClose={() => setDel({ open: false, target: null, ids: null })}
        onConfirm={confirmDelete}
      />

      {bulkOp && (
        <Modal
          isOpen
          onClose={() => setBulkOp(null)}
          title={bulkOp.op.title || bulkOp.op.label}
          subtitle={`Applies to ${selection.size} selected ${CSStore.NICE[type]}${selection.size === 1 ? "" : "s"}.`}
          footer={
            <>
              <Button variant="ghost" onClick={() => setBulkOp(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={applyBulk}>
                Apply
              </Button>
            </>
          }
        >
          {bulkOp.op.kind === "segmented" ? (
            <SegmentedControl
              value={bulkOp.value}
              onChange={(v) => setBulkOp((b) => ({ ...b, value: v }))}
              options={bulkOp.op.options}
            />
          ) : (
            <Field label={bulkOp.op.fieldLabel || "Value"}>
              <Select value={bulkOp.value} onChange={(v) => setBulkOp((b) => ({ ...b, value: v }))}>
                {bulkOp.op.options.map((o) => (
                  <Select.Item key={o.value} value={o.value} description={o.description}>
                    {o.label}
                  </Select.Item>
                ))}
              </Select>
            </Field>
          )}
        </Modal>
      )}
    </>
  );
});

window.EntitySurface = EntitySurface;
