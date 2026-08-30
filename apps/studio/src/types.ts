export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";
export type JobStage =
  | "uploaded"
  | "inspecting"
  | "extracting"
  | "reconstructing"
  | "finalizing"
  | "complete";
export type CaptureProfile = "fast" | "balanced" | "quality";
export type BackendChoice = "auto" | "da3" | "colmap";
export type GeometryKind = "point-cloud" | "mesh" | "cad";
export type EnvironmentStatus = "draft" | "ready" | "blocked";
export type TaskTemplate = "stabilize" | "push-to-target";

export interface Artifact {
  name: string;
  kind: string;
  relative_path: string;
  size_bytes: number;
  media_type: string;
  experimental: boolean;
}

export interface CaptureReport {
  probe: {
    width: number;
    height: number;
    fps: number;
    frame_count: number;
    duration_seconds: number;
  };
  selected_frames: number;
  median_sharpness: number;
  median_motion_px: number | null;
  warnings: string[];
}

export interface JobRecord {
  id: string;
  created_at: string;
  updated_at: string;
  status: JobStatus;
  stage: JobStage;
  progress: number;
  message: string;
  input_name: string;
  input_path: string;
  profile: CaptureProfile;
  backend_requested: BackendChoice;
  backend_used: string | null;
  error_code: string | null;
  error_detail: string | null;
  artifacts: Artifact[];
  metadata: {
    capture?: CaptureReport;
    reconstruction?: Record<string, unknown>;
    warnings?: string[];
  };
}

export interface SystemCapabilities {
  os: string;
  cpu: string;
  logical_cores: number;
  ram_gb: number | null;
  gpu: string | null;
  gpu_vram_gb: number | null;
  cuda_available: boolean;
  cuda_runtime: string | null;
  da3_available: boolean;
  colmap_available: boolean;
  colmap_path: string | null;
  ffmpeg_available: boolean;
  recommended_backend: string | null;
  recommended_profile: CaptureProfile;
  limitations: string[];
}

export interface AssetRecord {
  id: string;
  created_at: string;
  updated_at: string;
  name: string;
  source: "capture" | "import";
  source_job_id: string | null;
  source_filename: string;
  original_path: string;
  visual_path: string;
  geometry_kind: GeometryKind;
  media_type: string;
  size_bytes: number;
  vertex_count: number;
  face_count: number;
  dimensions_model: [number, number, number];
  watertight: boolean | null;
  rl_eligible: boolean;
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface EnvironmentRecord {
  id: string;
  created_at: string;
  updated_at: string;
  name: string;
  asset_id: string;
  status: EnvironmentStatus;
  task_template: TaskTemplate;
  simulator: "mujoco";
  gymnasium_id: string;
  max_episode_steps: number;
  mass_kg: number;
  target_size_m: number;
  scale_to_meters: number;
  package_path: string | null;
  validation_errors: string[];
  metadata: Record<string, unknown>;
}

export interface EnvironmentCreate {
  asset_id: string;
  name: string;
  task_template: TaskTemplate;
  mass_kg: number;
  target_size_m: number;
  max_episode_steps: number;
}
