import {
  Aperture,
  ArrowClockwise,
  Check,
  CircleHalf,
  Cpu,
  Cube,
  DownloadSimple,
  FileVideo,
  Gauge,
  HardDrives,
  Info,
  Robot,
  Stack,
  Warning,
  X,
} from "@phosphor-icons/react";
import { Select, Tooltip } from "@radix-ui/themes";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  artifactUrl,
  fetchJob,
  fetchJobs,
  fetchSystem,
  uploadVideo,
} from "./api";
import { CaptureDropzone } from "./components/CaptureDropzone";
import { EnvironmentWorkspace } from "./components/EnvironmentWorkspace";
import { ObjectWorkspace } from "./components/ObjectWorkspace";
import type {
  BackendChoice,
  CaptureProfile,
  JobRecord,
  SystemCapabilities,
  EnvironmentRecord,
} from "./types";

type Appearance = "dark" | "light";
type WorkspaceView = "capture" | "objects" | "environments";

const GeometryViewport = lazy(() =>
  import("./components/GeometryViewport").then((module) => ({
    default: module.GeometryViewport,
  })),
);

interface AppProps {
  appearance: Appearance;
  onAppearanceChange: (appearance: Appearance) => void;
}

export default function App({ appearance, onAppearanceChange }: AppProps) {
  const [system, setSystem] = useState<SystemCapabilities | null>(null);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [profile, setProfile] = useState<CaptureProfile>("fast");
  const [backend, setBackend] = useState<BackendChoice>("auto");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<WorkspaceView>("capture");
  const [activeEnvironment, setActiveEnvironment] =
    useState<EnvironmentRecord | null>(null);

  const activeJob = jobs.find((job) => job.id === activeId) ?? jobs[0] ?? null;
  const geometry = activeJob?.artifacts.find(
    (artifact) => artifact.media_type === "model/gltf-binary",
  );
  const modelUrl =
    activeJob && geometry
      ? artifactUrl(activeJob, geometry.relative_path)
      : null;

  const loadInitial = useCallback(async () => {
    try {
      const [systemResult, jobResult] = await Promise.all([
        fetchSystem(),
        fetchJobs(),
      ]);
      setSystem(systemResult);
      setJobs(jobResult);
      setProfile(systemResult.recommended_profile);
      if (!activeId && jobResult.length) setActiveId(jobResult[0].id);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load the local workspace.",
      );
    }
  }, [activeId]);

  useEffect(() => {
    // Initial data is owned by the local API and must be synchronized after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (!activeJob || !["queued", "running"].includes(activeJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchJob(activeJob.id);
        setJobs((current) => [
          next,
          ...current.filter((job) => job.id !== next.id),
        ]);
      } catch (reason) {
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not refresh job progress.",
        );
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeJob]);

  const handleUpload = useCallback(
    async (file: File) => {
      setError(null);
      setUploadProgress(0);
      try {
        const job = await uploadVideo(
          file,
          profile,
          backend,
          setUploadProgress,
        );
        setJobs((current) => [job, ...current]);
        setActiveId(job.id);
      } catch (reason) {
        setError(
          reason instanceof Error ? reason.message : "Video upload failed.",
        );
      } finally {
        setUploadProgress(null);
      }
    },
    [backend, profile],
  );

  const systemSummary = useMemo(() => {
    if (!system) return "Checking hardware";
    const gpu = system.gpu ?? "CPU mode";
    const memory = system.gpu_vram_gb ? `, ${system.gpu_vram_gb} GB VRAM` : "";
    return `${gpu}${memory}`;
  }, [system]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup" aria-label="KinetiWeave Studio">
          <span className="brand-mark">
            <Aperture size={21} weight="bold" />
          </span>
          <div>
            <strong>KinetiWeave</strong>
            <span>Capture Studio</span>
          </div>
        </div>
        <nav className="workspace-nav" aria-label="Studio sections">
          <button type="button" className={view === "capture" ? "active" : ""} onClick={() => setView("capture")}>
            <Aperture size={17} /> Capture
          </button>
          <button type="button" className={view === "objects" ? "active" : ""} onClick={() => setView("objects")}>
            <Stack size={17} /> Objects
          </button>
          <button type="button" className={view === "environments" ? "active" : ""} onClick={() => setView("environments")}>
            <Robot size={17} /> Environments
          </button>
        </nav>
        <div className="topbar-actions">
          <span className="hardware-summary">
            <Cpu size={16} /> {systemSummary}
          </span>
          <Tooltip
            content={`Switch to ${appearance === "dark" ? "light" : "dark"} theme`}
          >
            <button
              className="icon-button"
              type="button"
              aria-label={`Switch to ${appearance === "dark" ? "light" : "dark"} theme`}
              onClick={() =>
                onAppearanceChange(appearance === "dark" ? "light" : "dark")
              }
            >
              <CircleHalf size={19} />
            </button>
          </Tooltip>
        </div>
      </header>

      {error && (
        <div className="global-error" role="alert">
          <X size={18} weight="bold" />
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {view === "objects" && (
        <ObjectWorkspace
          refreshKey={jobs.filter((job) => job.status === "succeeded").length}
          onError={setError}
          onEnvironmentCreated={(environment) => {
            setActiveEnvironment(environment);
            setView("environments");
          }}
        />
      )}

      {view === "environments" && (
        <EnvironmentWorkspace
          selected={activeEnvironment}
          onSelected={setActiveEnvironment}
          onError={setError}
        />
      )}

      {view === "capture" && <div className="workbench">
        <aside
          className="capture-panel panel-scroll"
          aria-label="Capture controls"
        >
          <div className="panel-heading">
            <div>
              <span className="section-kicker">New reconstruction</span>
              <h1>Turn an orbit into geometry.</h1>
            </div>
          </div>

          <CaptureDropzone
            onFile={handleUpload}
            uploading={uploadProgress !== null}
          />
          {uploadProgress !== null && (
            <div className="upload-meter" aria-live="polite">
              <span
                style={{ width: `${Math.max(uploadProgress * 100, 3)}%` }}
              />
              <p>Uploading locally {Math.round(uploadProgress * 100)}%</p>
            </div>
          )}

          <div className="control-grid">
            <label>
              <span>Compute profile</span>
              <Select.Root
                value={profile}
                onValueChange={(value) => setProfile(value as CaptureProfile)}
              >
                <Select.Trigger aria-label="Compute profile" />
                <Select.Content>
                  <Select.Item value="fast">Fast laptop</Select.Item>
                  <Select.Item value="balanced">Balanced</Select.Item>
                  <Select.Item value="quality">High detail</Select.Item>
                </Select.Content>
              </Select.Root>
            </label>
            <label>
              <span>Reconstruction engine</span>
              <Select.Root
                value={backend}
                onValueChange={(value) => setBackend(value as BackendChoice)}
              >
                <Select.Trigger aria-label="Reconstruction engine" />
                <Select.Content>
                  <Select.Item value="auto">Best available</Select.Item>
                  <Select.Item
                    value="da3"
                    disabled={system ? !system.da3_available : false}
                  >
                    DA3 Small
                    {system && !system.da3_available ? " (not installed)" : ""}
                  </Select.Item>
                  <Select.Item
                    value="colmap"
                    disabled={system ? !system.colmap_available : false}
                  >
                    COLMAP
                    {system && !system.colmap_available
                      ? " (not installed)"
                      : ""}
                  </Select.Item>
                </Select.Content>
              </Select.Root>
            </label>
          </div>

          {system && system.limitations.length > 0 && (
            <div className="capability-note">
              <Warning size={16} />
              <p>{system.limitations[0]}</p>
            </div>
          )}

          <CaptureGuide />

          <section className="recent-section">
            <div className="section-title-row">
              <h2>Recent captures</h2>
              <button
                className="text-button"
                type="button"
                onClick={() => void loadInitial()}
              >
                <ArrowClockwise size={15} /> Refresh
              </button>
            </div>
            {jobs.length === 0 ? (
              <p className="quiet-copy">
                Your local reconstruction history will appear here.
              </p>
            ) : (
              <div className="job-list">
                {jobs.map((job) => (
                  <button
                    type="button"
                    key={job.id}
                    className={
                      job.id === activeJob?.id ? "job-row active" : "job-row"
                    }
                    onClick={() => setActiveId(job.id)}
                  >
                    <JobGlyph status={job.status} />
                    <span>
                      <strong>{job.input_name}</strong>
                      <small>
                        {job.status === "running" ? job.message : job.status}
                      </small>
                    </span>
                    <time>{new Date(job.created_at).toLocaleDateString()}</time>
                  </button>
                ))}
              </div>
            )}
          </section>
        </aside>

        <section
          className="viewport-panel"
          aria-label="3D reconstruction viewport"
        >
          <div className="viewport-toolbar">
            <div>
              <Cube size={17} />
              <span>{activeJob?.input_name ?? "No capture loaded"}</span>
            </div>
            {activeJob && <StatusLabel job={activeJob} />}
          </div>
          <Suspense
            fallback={
              <div className="viewport-state">Loading 3D workspace</div>
            }
          >
            <GeometryViewport
              modelUrl={modelUrl}
              activeJob={activeJob}
              onChooseVideo={handleUpload}
            />
          </Suspense>
          {activeJob && ["queued", "running"].includes(activeJob.status) && (
            <JobProgress job={activeJob} />
          )}
        </section>

        <aside
          className="inspector-panel panel-scroll"
          aria-label="Reconstruction evidence"
        >
          <Inspector job={activeJob} system={system} />
        </aside>
      </div>}
    </main>
  );
}

function CaptureGuide() {
  const items = [
    [
      "Keep the object still",
      "Walk around it. Do not rotate it against a fixed background.",
    ],
    [
      "Hold distance",
      "Keep the whole object visible with roughly 70% overlap.",
    ],
    [
      "Use soft, bright light",
      "Avoid motion blur, reflections and changing shadows.",
    ],
    [
      "Capture every height",
      "Make one level orbit, then a slightly higher orbit.",
    ],
  ];
  return (
    <section className="capture-guide">
      <h2>Capture that reconstructs</h2>
      <div className="guide-grid">
        {items.map(([title, body], index) => (
          <div className="guide-item" key={title}>
            <span>{index + 1}</span>
            <p>
              <strong>{title}</strong>
              <small>{body}</small>
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function JobGlyph({ status }: { status: JobRecord["status"] }) {
  if (status === "succeeded")
    return <Check className="job-glyph success" size={18} weight="bold" />;
  if (status === "failed")
    return <X className="job-glyph failed" size={18} weight="bold" />;
  return <Aperture className="job-glyph working" size={18} />;
}

function StatusLabel({ job }: { job: JobRecord }) {
  return (
    <span className={`status-label ${job.status}`}>
      {job.status === "running" ? job.stage : job.status}
    </span>
  );
}

function JobProgress({ job }: { job: JobRecord }) {
  const stages = ["Inspect", "Extract", "Reconstruct", "Finalize"];
  const active = Math.min(
    Math.floor(job.progress * stages.length),
    stages.length - 1,
  );
  return (
    <div className="job-progress" aria-live="polite">
      <div className="progress-copy">
        <span>{job.message}</span>
        <strong>{Math.round(job.progress * 100)}%</strong>
      </div>
      <div className="stage-track" aria-hidden="true">
        {stages.map((stage, index) => (
          <span key={stage} className={index <= active ? "reached" : ""}>
            {stage}
          </span>
        ))}
      </div>
    </div>
  );
}

function Inspector({
  job,
  system,
}: {
  job: JobRecord | null;
  system: SystemCapabilities | null;
}) {
  if (!job) {
    return (
      <div className="inspector-empty">
        <Info size={23} />
        <h2>Evidence appears here</h2>
        <p>
          Upload a careful orbit to inspect frame quality, motion, engine
          details and artifacts.
        </p>
      </div>
    );
  }
  const capture = job.metadata.capture;
  const warnings = job.metadata.warnings ?? [];
  return (
    <div className="inspector-content">
      <section>
        <span className="section-kicker">Reconstruction evidence</span>
        <h2>
          {job.status === "succeeded"
            ? "Geometry ready for review"
            : "Processing locally"}
        </h2>
        <p className="quiet-copy">{job.message}</p>
      </section>

      {job.error_detail && (
        <section className="diagnostic-block" role="alert">
          <Warning size={19} weight="fill" />
          <div>
            <strong>{job.error_code}</strong>
            <p>{job.error_detail}</p>
          </div>
        </section>
      )}

      {capture && (
        <section>
          <h3>Capture health</h3>
          <div className="metric-grid">
            <Metric
              icon={<FileVideo />}
              label="Views"
              value={String(capture.selected_frames)}
            />
            <Metric
              icon={<Gauge />}
              label="Sharpness"
              value={capture.median_sharpness.toFixed(0)}
            />
            <Metric
              icon={<Aperture />}
              label="Motion"
              value={
                capture.median_motion_px === null
                  ? "n/a"
                  : `${capture.median_motion_px.toFixed(1)} px`
              }
            />
            <Metric
              icon={<HardDrives />}
              label="Source"
              value={`${capture.probe.width} x ${capture.probe.height}`}
            />
          </div>
        </section>
      )}

      <section>
        <h3>Compute</h3>
        <dl className="property-list">
          <div>
            <dt>Requested</dt>
            <dd>{job.backend_requested}</dd>
          </div>
          <div>
            <dt>Engine</dt>
            <dd>{job.backend_used ?? "Waiting"}</dd>
          </div>
          <div>
            <dt>Profile</dt>
            <dd>{job.profile}</dd>
          </div>
          <div>
            <dt>GPU</dt>
            <dd>{system?.gpu ?? "CPU"}</dd>
          </div>
        </dl>
      </section>

      {warnings.length > 0 && (
        <section>
          <h3>Review notes</h3>
          <div className="warning-list">
            {warnings.map((warning) => (
              <p key={warning}>
                <Warning size={16} />
                {warning}
              </p>
            ))}
          </div>
        </section>
      )}

      {job.artifacts.length > 0 && (
        <section>
          <h3>Artifacts</h3>
          <div className="artifact-list">
            {job.artifacts.map((artifact) => (
              <a
                key={artifact.relative_path}
                href={artifactUrl(job, artifact.relative_path)}
                download
              >
                <span>
                  <DownloadSimple size={17} />
                  <strong>{artifact.name}</strong>
                </span>
                <small>{formatBytes(artifact.size_bytes)}</small>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="metric">
      <span>{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
