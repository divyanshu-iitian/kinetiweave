import {
  ArrowClockwise,
  Check,
  CheckCircle,
  Cube,
  DownloadSimple,
  Gauge,
  Package,
  Robot,
  Warning,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  environmentPackageUrl,
  fetchEnvironments,
  validateEnvironment,
} from "../api";
import type { EnvironmentRecord } from "../types";

interface EnvironmentWorkspaceProps {
  selected: EnvironmentRecord | null;
  onSelected: (environment: EnvironmentRecord) => void;
  onError: (message: string) => void;
}

export function EnvironmentWorkspace({
  selected,
  onSelected,
  onError,
}: EnvironmentWorkspaceProps) {
  const [environments, setEnvironments] = useState<EnvironmentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [validatingId, setValidatingId] = useState<string | null>(null);

  useEffect(() => {
    void fetchEnvironments()
      .then((result) => {
        setEnvironments(result);
        if (!selected && result[0]) onSelected(result[0]);
      })
      .catch((reason: Error) => onError(reason.message))
      .finally(() => setLoading(false));
  }, [onError, onSelected, selected]);

  const active = useMemo(
    () =>
      environments.find((environment) => environment.id === selected?.id) ??
      selected ??
      environments[0] ??
      null,
    [environments, selected],
  );

  const handleValidate = useCallback(async () => {
    if (!active) return;
    setValidatingId(active.id);
    try {
      const updated = await validateEnvironment(active.id);
      setEnvironments((current) =>
        current.map((environment) =>
          environment.id === updated.id ? updated : environment,
        ),
      );
      onSelected(updated);
    } catch (reason) {
      onError(
        reason instanceof Error ? reason.message : "Physics validation failed.",
      );
    } finally {
      setValidatingId(null);
    }
  }, [active, onError, onSelected]);

  return (
    <div className="environment-page panel-scroll">
      <header className="environment-hero">
        <div>
          <p className="environment-overline">Simulation workspace</p>
          <h1>RL Environments</h1>
          <p>
            Contact-driven MuJoCo tasks with inspectable observations, rewards,
            and physics evidence.
          </p>
        </div>
        <span className="environment-count">
          <Robot size={18} /> {environments.length} environments
        </span>
      </header>

      {loading ? (
        <EnvironmentSkeleton />
      ) : environments.length === 0 ? (
        <div className="environment-empty">
          <Package size={44} weight="thin" />
          <h2>No environments yet</h2>
          <p>
            Open an object, enter its measured scale and mass, then build a
            contact-driven task.
          </p>
        </div>
      ) : (
        <div className="environment-layout">
          <div className="environment-list" aria-label="RL environments">
            {environments.map((environment) => (
              <button
                type="button"
                key={environment.id}
                className={
                  environment.id === active?.id
                    ? "environment-row active"
                    : "environment-row"
                }
                onClick={() => onSelected(environment)}
              >
                <span className={`environment-glyph ${environment.status}`}>
                  {environment.validation?.status === "passed" ? (
                    <CheckCircle size={19} />
                  ) : (
                    <Warning size={19} />
                  )}
                </span>
                <span>
                  <strong>{environment.name}</strong>
                  <small>
                    {environment.task_template.replaceAll("-", " ")} · {" "}
                    {environment.validation?.status ??
                      (environment.status === "blocked" ? "blocked" : "legacy")}
                  </small>
                </span>
                <time>{new Date(environment.created_at).toLocaleDateString()}</time>
              </button>
            ))}
          </div>

          {active && (
            <article className="environment-detail">
              <div className="environment-detail-heading">
                <div>
                  <span
                    className={`status-label ${
                      active.status === "ready" ? "succeeded" : "failed"
                    }`}
                  >
                    {active.status}
                  </span>
                  <h2>{active.name}</h2>
                  <code>{active.gymnasium_id}</code>
                </div>
                <div className="environment-actions">
                  {active.validation && (
                    <button
                      className="secondary-action"
                      type="button"
                      disabled={validatingId === active.id}
                      onClick={() => void handleValidate()}
                    >
                      <ArrowClockwise
                        size={17}
                        className={validatingId === active.id ? "working" : ""}
                      />
                      {validatingId === active.id ? "Running…" : "Re-run check"}
                    </button>
                  )}
                  {active.status === "ready" && (
                    <a
                      className="primary-action"
                      href={environmentPackageUrl(active)}
                      download
                    >
                      <DownloadSimple size={18} /> Export package
                    </a>
                  )}
                </div>
              </div>

              {active.validation ? (
                <ValidationEvidence environment={active} />
              ) : active.status === "blocked" ? (
                <div className="legacy-environment-note build-blocked-note">
                  <Warning size={20} />
                  <div>
                    <strong>Environment build blocked</strong>
                    <p>
                      {active.validation_errors[0] ??
                        "The generated model did not pass its build checks."}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="legacy-environment-note">
                  <Warning size={20} />
                  <div>
                    <strong>Legacy force-controlled package</strong>
                    <p>
                      Rebuild this environment from Objects to get embodied
                      contact control and deterministic physics evidence.
                    </p>
                  </div>
                </div>
              )}

              <section className="task-contract">
                <div className="detail-section-heading">
                  <div>
                    <h3>Task contract</h3>
                    <p>What the policy controls and what it can observe.</p>
                  </div>
                  <span>{active.task_template.replaceAll("-", " ")}</span>
                </div>
                <dl>
                  <div>
                    <dt>Embodiment</dt>
                    <dd>
                      {active.metadata.task_model?.controller ??
                        (active.status === "blocked"
                          ? "not generated"
                          : "legacy direct force")}
                    </dd>
                  </div>
                  <div>
                    <dt>Action</dt>
                    <dd>
                      {active.metadata.task_model?.action ??
                        (active.status === "blocked"
                          ? "not generated"
                          : "3D object force")}
                    </dd>
                  </div>
                  <div>
                    <dt>Observation</dt>
                    <dd>
                      {active.metadata.task_model?.observation ??
                        (active.status === "blocked"
                          ? "not generated"
                          : "flat state vector")}
                    </dd>
                  </div>
                  <div>
                    <dt>Reward</dt>
                    <dd>
                      {active.metadata.task_model?.reward ??
                        (active.status === "blocked"
                          ? "not generated"
                          : "task-specific dense")}
                    </dd>
                  </div>
                </dl>
              </section>

              <div className="environment-specs">
                <div>
                  <small>Simulator</small>
                  <strong>MuJoCo</strong>
                </div>
                <div>
                  <small>Mass</small>
                  <strong>{active.mass_kg.toLocaleString()} kg</strong>
                </div>
                <div>
                  <small>Longest side</small>
                  <strong>{active.target_size_m.toLocaleString()} m</strong>
                </div>
                <div>
                  <small>Episode</small>
                  <strong>{active.max_episode_steps.toLocaleString()} steps</strong>
                </div>
              </div>

              <div className="package-flow" aria-label="Generated package contents">
                <span>
                  <Cube size={20} />
                  <strong>Measured object</strong>
                  <small>Visual + collision</small>
                </span>
                <i />
                <span>
                  <Robot size={20} />
                  <strong>Embodied control</strong>
                  <small>Actuated contact</small>
                </span>
                <i />
                <span>
                  <Package size={20} />
                  <strong>
                    {active.status === "blocked"
                      ? "Package blocked"
                      : "Training package"}
                  </strong>
                  <small>
                    {active.status === "blocked"
                      ? "Resolve build checks"
                      : "Gymnasium + MJCF"}
                  </small>
                </span>
              </div>
              <p className="validation-note">
                Computational validation catches malformed or unstable models;
                it does not replace real-world system identification.
              </p>
            </article>
          )}
        </div>
      )}
    </div>
  );
}

function ValidationEvidence({ environment }: { environment: EnvironmentRecord }) {
  const validation = environment.validation;
  if (!validation) return null;
  return (
    <section
      className={`validation-evidence ${validation.status}`}
      aria-label="Physics validation evidence"
    >
      <div className="validation-verdict">
        <span>
          {validation.status === "passed" ? (
            <Check size={20} weight="bold" />
          ) : (
            <Warning size={20} weight="fill" />
          )}
        </span>
        <div>
          <strong>
            {validation.status === "passed"
              ? "Physics checks passed"
              : "Physics check failed"}
          </strong>
          <small>
            {validation.simulated_seconds.toFixed(1)} simulated seconds · {" "}
            {new Date(validation.checked_at).toLocaleString()}
          </small>
        </div>
      </div>
      <div className="validation-metrics">
        <Metric
          icon={<Gauge />}
          label="Finite rollout"
          value={validation.finite_rollout ? "Yes" : "No"}
        />
        <Metric
          icon={<Robot />}
          label="Pusher contacts"
          value={validation.pusher_object_contacts.toLocaleString()}
        />
        <Metric
          icon={<Package />}
          label="Target residual"
          value={`${validation.final_target_error_m.toFixed(3)} m`}
        />
        <Metric
          icon={<Cube />}
          label="Model dimensions"
          value={`${validation.nq}q · ${validation.nu}u`}
        />
      </div>
      <div className="validation-checks">
        {validation.checks.map((check) => (
          <p key={check}>
            <CheckCircle size={15} /> {check}
          </p>
        ))}
      </div>
    </section>
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
    <div>
      <span>{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}

function EnvironmentSkeleton() {
  return (
    <div className="environment-layout" aria-label="Loading environments">
      <div className="environment-list skeleton-list">
        <span />
        <span />
        <span />
      </div>
      <div className="environment-detail skeleton-detail">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
