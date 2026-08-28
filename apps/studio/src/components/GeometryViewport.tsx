import {
  Bounds,
  Center,
  Environment,
  Grid,
  OrbitControls,
  useGLTF,
} from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Component, Suspense, type ErrorInfo, type ReactNode } from "react";
import { BoxArrowUp, Cube, Warning } from "@phosphor-icons/react";

import type { JobRecord } from "../types";

interface GeometryViewportProps {
  modelUrl: string | null;
  activeJob: JobRecord | null;
  onChooseVideo: (file: File) => void;
}

export function GeometryViewport({
  modelUrl,
  activeJob,
  onChooseVideo,
}: GeometryViewportProps) {
  if (!activeJob) return <EmptyViewport onChooseVideo={onChooseVideo} />;
  if (activeJob.status === "failed") {
    return (
      <div className="viewport-state error-state">
        <Warning size={34} weight="duotone" />
        <h2>Reconstruction stopped</h2>
        <p>
          {activeJob.error_detail ??
            "The local engine could not finish this capture."}
        </p>
      </div>
    );
  }
  if (!modelUrl) return <ProcessingViewport job={activeJob} />;

  return (
    <div className="canvas-wrap">
      <ViewerErrorBoundary>
        <Canvas
          camera={{
            position: [2.8, 2.2, 3.2],
            fov: 42,
            near: 0.01,
            far: 10_000,
          }}
          dpr={[1, 1.75]}
          gl={{ antialias: true, powerPreference: "high-performance" }}
        >
          <color attach="background" args={["#10110f"]} />
          <ambientLight intensity={1.1} />
          <directionalLight position={[4, 7, 5]} intensity={2.2} />
          <Suspense fallback={null}>
            <Bounds fit clip observe margin={1.2}>
              <Center>
                <GltfModel url={modelUrl} />
              </Center>
            </Bounds>
            <Environment preset="warehouse" environmentIntensity={0.35} />
          </Suspense>
          <Grid
            args={[20, 20]}
            cellSize={0.25}
            cellThickness={0.5}
            cellColor="#3f423a"
            sectionSize={1}
            sectionThickness={0.8}
            sectionColor="#64695b"
            fadeDistance={16}
            infiniteGrid
          />
          <OrbitControls makeDefault enableDamping dampingFactor={0.08} />
        </Canvas>
      </ViewerErrorBoundary>
      <div className="viewport-help">
        Drag to orbit. Scroll to zoom. Right-drag to pan.
      </div>
    </div>
  );
}

function GltfModel({ url }: { url: string }) {
  const gltf = useGLTF(url);
  return <primitive object={gltf.scene} />;
}

function EmptyViewport({
  onChooseVideo,
}: {
  onChooseVideo: (file: File) => void;
}) {
  return (
    <div className="viewport-state empty-viewport">
      <div className="empty-object">
        <Cube size={64} weight="thin" />
      </div>
      <h2>Your capture becomes inspectable geometry.</h2>
      <p>Keep the object still and walk one smooth orbit around it.</p>
      <label className="viewport-upload">
        <BoxArrowUp size={17} /> Upload capture
        <input
          type="file"
          accept="video/*"
          onChange={(event) => {
            const file = event.target.files?.item(0);
            if (file) onChooseVideo(file);
          }}
        />
      </label>
    </div>
  );
}

function ProcessingViewport({ job }: { job: JobRecord }) {
  return (
    <div className="viewport-state processing-viewport">
      <div className="scan-object" aria-hidden="true">
        <Cube size={72} weight="thin" />
        <span />
      </div>
      <h2>
        {job.status === "queued"
          ? "Waiting for the local worker"
          : "Recovering shape and camera motion"}
      </h2>
      <p>{job.message}</p>
    </div>
  );
}

class ViewerErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("3D viewer failed", error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="viewport-state error-state">
          <Warning size={32} />
          <h2>Could not display this artifact</h2>
          <p>
            Download the GLB from the inspector and review the browser console.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
