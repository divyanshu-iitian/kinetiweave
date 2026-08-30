import {
  CheckCircle,
  Cube,
  DownloadSimple,
  Package,
  Robot,
  Warning,
} from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { environmentPackageUrl, fetchEnvironments } from "../api";
import type { EnvironmentRecord } from "../types";

interface EnvironmentWorkspaceProps {
  selected: EnvironmentRecord | null;
  onSelected: (environment: EnvironmentRecord) => void;
  onError: (message: string) => void;
}

export function EnvironmentWorkspace({ selected, onSelected, onError }: EnvironmentWorkspaceProps) {
  const [environments, setEnvironments] = useState<EnvironmentRecord[]>([]);

  useEffect(() => {
    void fetchEnvironments()
      .then((result) => {
        setEnvironments(result);
        if (!selected && result[0]) onSelected(result[0]);
      })
      .catch((reason: Error) => onError(reason.message));
  }, [onError, onSelected, selected]);

  const active = selected ?? environments[0] ?? null;

  return (
    <div className="environment-page panel-scroll">
      <header className="environment-hero">
        <div>
          <span className="section-kicker">Simulation workspace</span>
          <h1>RL Environments</h1>
          <p>Portable MuJoCo physics, Gymnasium API, and explicit collision provenance.</p>
        </div>
        <span className="environment-count"><Robot size={18} /> {environments.length} environments</span>
      </header>
      {environments.length === 0 ? (
        <div className="environment-empty">
          <Package size={44} weight="thin" />
          <h2>No environments yet</h2>
          <p>Open an object, enter its physical scale and mass, then build its first RL environment.</p>
        </div>
      ) : (
        <div className="environment-layout">
          <div className="environment-list" aria-label="RL environments">
            {environments.map((environment) => (
              <button
                type="button"
                key={environment.id}
                className={environment.id === active?.id ? "environment-row active" : "environment-row"}
                onClick={() => onSelected(environment)}
              >
                <span className={`environment-glyph ${environment.status}`}>
                  {environment.status === "ready" ? <CheckCircle size={19} /> : <Warning size={19} />}
                </span>
                <span><strong>{environment.name}</strong><small>{environment.task_template.replaceAll("-", " ")}</small></span>
                <time>{new Date(environment.created_at).toLocaleDateString()}</time>
              </button>
            ))}
          </div>
          {active && (
            <article className="environment-detail">
              <div className="environment-detail-heading">
                <span className={`status-label ${active.status === "ready" ? "succeeded" : "failed"}`}>{active.status}</span>
                <h2>{active.name}</h2>
                <code>{active.gymnasium_id}</code>
              </div>
              <div className="environment-specs">
                <div><small>Simulator</small><strong>MuJoCo</strong></div>
                <div><small>Mass</small><strong>{active.mass_kg.toLocaleString()} kg</strong></div>
                <div><small>Longest side</small><strong>{active.target_size_m.toLocaleString()} m</strong></div>
                <div><small>Episode</small><strong>{active.max_episode_steps.toLocaleString()} steps</strong></div>
              </div>
              <div className="package-flow" aria-label="Generated package contents">
                <span><Cube size={20} /><strong>Object</strong><small>GLB source</small></span>
                <i />
                <span><Package size={20} /><strong>Physics</strong><small>Convex STL + XML</small></span>
                <i />
                <span><Robot size={20} /><strong>Agent API</strong><small>Gymnasium</small></span>
              </div>
              {active.validation_errors.length > 0 && (
                <div className="diagnostic-block"><Warning size={20} /><div><strong>Build blocked</strong>{active.validation_errors.map((error) => <p key={error}>{error}</p>)}</div></div>
              )}
              {active.status === "ready" && (
                <a className="primary-action package-download" href={environmentPackageUrl(active)} download>
                  <DownloadSimple size={19} /> Download runnable package
                </a>
              )}
              <p className="validation-note">Generated baseline: validate inertia, friction, reward semantics, and contact behavior before training claims.</p>
            </article>
          )}
        </div>
      )}
    </div>
  );
}
