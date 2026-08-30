import {
  ArrowClockwise,
  Check,
  CheckCircle,
  DownloadSimple,
  Fingerprint,
  Gauge,
  Play,
  Scales,
  WaveSine,
  Warning,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  benchmarkReportUrl,
  fetchActuatedLinkContract,
  fetchLatestBenchmark,
  runActuatedLinkBenchmark,
} from "../api";
import type {
  ActuatedLinkContract,
  BenchmarkReport,
  TracePoint,
} from "../types";

interface BenchmarkWorkspaceProps {
  onError: (message: string) => void;
}

export function BenchmarkWorkspace({ onError }: BenchmarkWorkspaceProps) {
  const [contract, setContract] = useState<ActuatedLinkContract | null>(null);
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    void Promise.all([fetchActuatedLinkContract(), fetchLatestBenchmark()])
      .then(([nextContract, latest]) => {
        setContract(nextContract);
        setReport(latest);
      })
      .catch((reason: Error) => onError(reason.message))
      .finally(() => setLoading(false));
  }, [onError]);

  const handleRun = useCallback(async () => {
    setRunning(true);
    try {
      setReport(await runActuatedLinkBenchmark());
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Benchmark failed.");
    } finally {
      setRunning(false);
    }
  }, [onError]);

  if (loading || !contract) return <BenchmarkSkeleton />;

  return (
    <div className="benchmark-page panel-scroll">
      <header className="benchmark-hero">
        <div>
          <p className="environment-overline">Reproducibility laboratory</p>
          <h1>Physics, with receipts.</h1>
          <p>
            One versioned contract. Two independent dynamics paths. Every
            parameter, state sample, tolerance, and trace hash exposed.
          </p>
        </div>
        <div className="benchmark-actions">
          {report && (
            <a className="secondary-action" href={benchmarkReportUrl} download>
              <DownloadSimple size={17} /> Export evidence
            </a>
          )}
          <button
            className="primary-action"
            type="button"
            disabled={running}
            onClick={() => void handleRun()}
          >
            {running ? (
              <ArrowClockwise className="working" size={18} />
            ) : (
              <Play size={18} weight="fill" />
            )}
            {running ? "Running 401 samples…" : report ? "Run again" : "Run benchmark"}
          </button>
        </div>
      </header>

      <section className="benchmark-contract" aria-label="Benchmark contract">
        <div className="benchmark-contract-heading">
          <span>
            <Fingerprint size={18} /> Immutable contract
          </span>
          <code>{contract.schema_version}</code>
        </div>
        <div className="contract-parameters">
          <ContractValue label="Timestep" value={`${contract.timestep_s} s`} />
          <ContractValue label="Gravity" value={`${contract.gravity_m_s2} m/s²`} />
          <ContractValue label="Link" value={`${contract.link_mass_kg} kg · ${contract.link_length_m} m`} />
          <ContractValue label="Damping" value={`${contract.joint_damping_nms_rad} N·m·s/rad`} />
          <ContractValue label="Initial state" value={`${contract.initial_angle_rad} rad · ${contract.initial_velocity_rad_s} rad/s`} />
          <ContractValue label="Duration" value={`${contract.duration_s} s`} />
        </div>
      </section>

      {!report ? (
        <section className="benchmark-empty">
          <WaveSine size={42} weight="thin" />
          <h2>No evidence generated yet</h2>
          <p>
            Run the bounded experiment to compile the contract, execute both
            solvers, replay MuJoCo, and persist a portable JSON report.
          </p>
        </section>
      ) : (
        <BenchmarkEvidence report={report} />
      )}
    </div>
  );
}

function BenchmarkEvidence({ report }: { report: BenchmarkReport }) {
  const comparison = report.comparison;
  return (
    <>
      <section className={`benchmark-verdict ${report.status}`}>
        <div className="benchmark-verdict-copy">
          <span>
            {report.status === "passed" ? (
              <Check size={22} weight="bold" />
            ) : (
              <Warning size={22} weight="fill" />
            )}
          </span>
          <div>
            <p>Numerical verdict</p>
            <h2>
              {report.status === "passed"
                ? "Independent traces agree"
                : "Trace divergence detected"}
            </h2>
            <small>
              {comparison.samples} samples · MuJoCo {report.simulator_version} · {" "}
              {new Date(report.run_at).toLocaleString()}
            </small>
          </div>
        </div>
        <div className="verdict-number">
          <strong>{scientific(comparison.max_angle_error_rad)}</strong>
          <span>max angle error · rad</span>
        </div>
      </section>

      <div className="benchmark-evidence-grid">
        <section className="trace-card">
          <div className="benchmark-section-heading">
            <div>
              <span>State trace</span>
              <h3>MuJoCo against independent RK4</h3>
            </div>
            <div className="trace-legend">
              <span><i className="reference" /> Reference</span>
              <span><i className="simulator" /> MuJoCo</span>
            </div>
          </div>
          <TraceChart
            reference={report.reference_trace}
            simulator={report.simulator_trace}
          />
          <div className="trace-metrics">
            <EvidenceMetric
              icon={<Gauge />}
              label="Angle RMSE"
              value={`${scientific(comparison.angle_rmse_rad)} rad`}
            />
            <EvidenceMetric
              icon={<WaveSine />}
              label="Velocity RMSE"
              value={`${scientific(comparison.velocity_rmse_rad_s)} rad/s`}
            />
            <EvidenceMetric
              icon={<ArrowClockwise />}
              label="Replay delta"
              value={scientific(comparison.deterministic_replay_max_error)}
            />
          </div>
        </section>

        <section className="trace-identity-card">
          <div className="benchmark-section-heading">
            <div>
              <span>Trace identity</span>
              <h3>Content-addressed evidence</h3>
            </div>
            <Fingerprint size={20} />
          </div>
          <HashRow label="Independent RK4" value={comparison.reference_trace_sha256} />
          <HashRow label="MuJoCo RK4" value={comparison.mujoco_trace_sha256} />
          <p className={comparison.reference_trace_sha256 === comparison.mujoco_trace_sha256 ? "hash-match" : "hash-mismatch"}>
            {comparison.reference_trace_sha256 === comparison.mujoco_trace_sha256 ? (
              <><CheckCircle size={16} /> Sampled traces are byte-identical after canonical rounding.</>
            ) : (
              <><Warning size={16} /> Trace hashes differ; inspect numerical tolerances.</>
            )}
          </p>
        </section>
      </div>

      <section className="parameter-evidence">
        <div className="benchmark-section-heading">
          <div>
            <span>Compile fidelity</span>
            <h3>Authored contract → compiled model</h3>
          </div>
          <span className="evidence-count"><Scales size={16} /> {report.parameters.length} parameters</span>
        </div>
        <div className="parameter-table" role="table" aria-label="Compiled parameter evidence">
          <div className="parameter-row parameter-header" role="row">
            <span>Parameter</span><span>Authored</span><span>Compiled</span><span>Δ</span>
          </div>
          {report.parameters.map((parameter) => (
            <div className="parameter-row" role="row" key={parameter.parameter}>
              <strong>{parameter.parameter}</strong>
              <span>{number(parameter.authored)} {parameter.unit}</span>
              <span>{number(parameter.compiled)} {parameter.unit}</span>
              <span className={parameter.absolute_error === 0 ? "zero-delta" : "nonzero-delta"}>
                {scientific(parameter.absolute_error)}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="benchmark-checks" aria-label="Benchmark checks">
        {report.checks.map((check) => (
          <p key={check}><CheckCircle size={17} /> {check}</p>
        ))}
      </section>
    </>
  );
}

function TraceChart({
  reference,
  simulator,
}: {
  reference: TracePoint[];
  simulator: TracePoint[];
}) {
  const paths = useMemo(() => {
    const values = [...reference, ...simulator].map((point) => point.angle_rad);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const range = Math.max(maximum - minimum, 1e-9);
    const duration = Math.max(reference.at(-1)?.time_s ?? 1, 1e-9);
    const path = (trace: TracePoint[]) =>
      trace
        .map((point, index) => {
          const x = 32 + (point.time_s / duration) * 836;
          const y = 18 + ((maximum - point.angle_rad) / range) * 194;
          return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
        })
        .join(" ");
    return { reference: path(reference), simulator: path(simulator), minimum, maximum };
  }, [reference, simulator]);

  return (
    <svg
      className="trace-chart"
      viewBox="0 0 900 250"
      role="img"
      aria-label="Actuated-link angle over time for the MuJoCo and independent RK4 traces"
    >
      {[18, 66.5, 115, 163.5, 212].map((y) => (
        <line key={y} x1="32" x2="868" y1={y} y2={y} />
      ))}
      <path className="simulator-path" d={paths.simulator} />
      <path className="reference-path" d={paths.reference} />
      <text x="32" y="238">0 s</text>
      <text x="868" y="238" textAnchor="end">2 s</text>
      <text x="38" y="31">{paths.maximum.toFixed(2)} rad</text>
      <text x="38" y="205">{paths.minimum.toFixed(2)} rad</text>
    </svg>
  );
}

function ContractValue({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function EvidenceMetric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div><span>{icon}</span><small>{label}</small><strong>{value}</strong></div>;
}

function HashRow({ label, value }: { label: string; value: string }) {
  return <div className="hash-row"><span>{label}</span><code>{value}</code></div>;
}

function BenchmarkSkeleton() {
  return <div className="benchmark-page"><div className="benchmark-skeleton"><span /><span /><span /></div></div>;
}

function scientific(value: number): string {
  return value === 0 ? "0" : value.toExponential(2);
}

function number(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toPrecision(7).replace(/0+$/, "");
}
