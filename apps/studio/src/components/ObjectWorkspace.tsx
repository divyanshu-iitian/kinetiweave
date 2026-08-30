import {
  ArrowRight,
  CheckCircle,
  Cube,
  FileArrowUp,
  Ruler,
  Warning,
} from "@phosphor-icons/react";
import { Select } from "@radix-ui/themes";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";

import {
  assetGeometryUrl,
  createEnvironment,
  fetchAssets,
  importGeometry,
} from "../api";
import type {
  AssetRecord,
  EnvironmentRecord,
  TaskTemplate,
} from "../types";

const GeometryViewport = lazy(() =>
  import("./GeometryViewport").then((module) => ({
    default: module.GeometryViewport,
  })),
);

interface ObjectWorkspaceProps {
  refreshKey: number;
  onEnvironmentCreated: (environment: EnvironmentRecord) => void;
  onError: (message: string) => void;
}

export function ObjectWorkspace({
  refreshKey,
  onEnvironmentCreated,
  onError,
}: ObjectWorkspaceProps) {
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [mass, setMass] = useState("0.25");
  const [size, setSize] = useState("0.15");
  const [steps, setSteps] = useState("500");
  const [task, setTask] = useState<TaskTemplate>("stabilize");

  useEffect(() => {
    void fetchAssets()
      .then((result) => {
        setAssets(result);
        setActiveId((current) => current ?? result[0]?.id ?? null);
      })
      .catch((reason: Error) => onError(reason.message));
  }, [onError, refreshKey]);

  const active = assets.find((asset) => asset.id === activeId) ?? assets[0] ?? null;
  const dimensions = useMemo(
    () => active?.dimensions_model.map((value) => value.toPrecision(3)).join(" × "),
    [active],
  );

  async function handleImport(file: File) {
    setUploadProgress(0);
    try {
      const asset = await importGeometry(file, setUploadProgress);
      setAssets((current) => [asset, ...current]);
      setActiveId(asset.id);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Geometry import failed.");
    } finally {
      setUploadProgress(null);
    }
  }

  async function handleCreate() {
    if (!active) return;
    setCreating(true);
    try {
      const environment = await createEnvironment({
        asset_id: active.id,
        name: `${active.name} ${task === "stabilize" ? "Stability" : "Push"}`,
        task_template: task,
        mass_kg: Number(mass),
        target_size_m: Number(size),
        max_episode_steps: Number(steps),
      });
      onEnvironmentCreated(environment);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Environment build failed.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="workbench object-workbench">
      <aside className="capture-panel panel-scroll" aria-label="Object library">
        <div className="panel-heading">
          <div>
            <span className="section-kicker">Persistent catalog</span>
            <h1>Object Library</h1>
          </div>
        </div>
        <label className="geometry-import">
          <FileArrowUp size={21} />
          <span>
            <strong>Import CAD or mesh</strong>
            <small>STEP, STL, OBJ, PLY, 3MF, GLB</small>
          </span>
          <input
            type="file"
            accept=".step,.stp,.stl,.obj,.ply,.off,.3mf,.glb,.gltf"
            onChange={(event) => {
              const file = event.target.files?.item(0);
              if (file) void handleImport(file);
              event.target.value = "";
            }}
          />
        </label>
        {uploadProgress !== null && (
          <div className="upload-meter">
            <span style={{ width: `${Math.max(uploadProgress * 100, 3)}%` }} />
            <p>Importing {Math.round(uploadProgress * 100)}%</p>
          </div>
        )}
        <div className="section-title-row library-title">
          <h2>{assets.length} saved objects</h2>
        </div>
        {assets.length === 0 ? (
          <div className="library-empty">
            <Cube size={28} />
            <p>Successful captures and imported CAD will stay here.</p>
          </div>
        ) : (
          <div className="object-list">
            {assets.map((asset) => (
              <button
                type="button"
                key={asset.id}
                className={asset.id === active?.id ? "object-row active" : "object-row"}
                onClick={() => setActiveId(asset.id)}
              >
                <Cube size={20} weight={asset.id === active?.id ? "fill" : "regular"} />
                <span>
                  <strong>{asset.name}</strong>
                  <small>{asset.geometry_kind} · {asset.vertex_count.toLocaleString()} vertices</small>
                </span>
                <ArrowRight size={15} />
              </button>
            ))}
          </div>
        )}
      </aside>

      <section className="viewport-panel" aria-label="Object viewport">
        <div className="viewport-toolbar">
          <div><Cube size={17} /><span>{active?.name ?? "No object selected"}</span></div>
          {active && <span className="status-label succeeded">{active.geometry_kind}</span>}
        </div>
        <Suspense fallback={<div className="viewport-state">Loading 3D workspace</div>}>
          <GeometryViewport
            modelUrl={active ? assetGeometryUrl(active) : null}
            activeJob={null}
            emptyTitle="Your reusable objects live here."
            emptyBody="Capture a video or import engineering geometry to begin."
          />
        </Suspense>
      </section>

      <aside className="inspector-panel panel-scroll" aria-label="Object setup">
        {!active ? (
          <div className="inspector-empty">
            <Ruler size={24} />
            <h2>Select an object</h2>
            <p>Review geometry and define real physical values before simulation.</p>
          </div>
        ) : (
          <div className="inspector-content object-inspector">
            <section>
              <span className="section-kicker">Geometry evidence</span>
              <h2>{active.rl_eligible ? "Ready for physical setup" : "Geometry needs review"}</h2>
              <dl className="property-list">
                <div><dt>Source</dt><dd>{active.source}</dd></div>
                <div><dt>Bounds</dt><dd>{dimensions}</dd></div>
                <div><dt>Faces</dt><dd>{active.face_count.toLocaleString()}</dd></div>
                <div><dt>Watertight</dt><dd>{active.watertight === null ? "n/a" : active.watertight ? "yes" : "no"}</dd></div>
              </dl>
            </section>
            {active.warnings.length > 0 && (
              <section className="warning-list">
                {active.warnings.map((warning) => <p key={warning}><Warning size={16} />{warning}</p>)}
              </section>
            )}
            <section className="rl-builder">
              <span className="section-kicker">RL environment</span>
              <h3>Define physical truth</h3>
              <p className="quiet-copy">Scale and mass cannot be inferred reliably from one video.</p>
              <label><span>Task</span><Select.Root value={task} onValueChange={(value) => setTask(value as TaskTemplate)}><Select.Trigger /><Select.Content><Select.Item value="stabilize">Stabilize object</Select.Item><Select.Item value="push-to-target">Push to target</Select.Item></Select.Content></Select.Root></label>
              <div className="number-grid">
                <label><span>Mass (kg)</span><input type="number" min="0.001" step="0.01" value={mass} onChange={(event) => setMass(event.target.value)} /></label>
                <label><span>Longest side (m)</span><input type="number" min="0.001" step="0.01" value={size} onChange={(event) => setSize(event.target.value)} /></label>
              </div>
              <label><span>Episode steps</span><input type="number" min="10" max="100000" value={steps} onChange={(event) => setSteps(event.target.value)} /></label>
              <button className="primary-action" type="button" disabled={!active.rl_eligible || creating || Number(mass) <= 0 || Number(size) <= 0} onClick={() => void handleCreate()}>
                {creating ? "Building package…" : <><CheckCircle size={18} /> Build RL environment</>}
              </button>
            </section>
          </div>
        )}
      </aside>
    </div>
  );
}
