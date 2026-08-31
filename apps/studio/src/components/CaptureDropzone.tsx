import { UploadSimple, VideoCamera } from "@phosphor-icons/react";
import { useRef, useState } from "react";

interface CaptureDropzoneProps {
  onFile: (file: File) => void;
  uploading: boolean;
}

export function CaptureDropzone({ onFile, uploading }: CaptureDropzoneProps) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const choose = (files: FileList | null) => {
    const file = files?.item(0);
    if (file) onFile(file);
  };

  return (
    <button
      type="button"
      className={dragging ? "dropzone dragging" : "dropzone"}
      disabled={uploading}
      onClick={() => input.current?.click()}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        choose(event.dataTransfer.files);
      }}
    >
      <input
        ref={input}
        type="file"
        accept="video/mp4,video/quicktime,video/webm,video/x-msvideo,video/x-matroska"
        onChange={(event) => choose(event.target.files)}
        tabIndex={-1}
      />
      <span className="dropzone-icon">
        <VideoCamera size={27} weight="duotone" />
      </span>
      <strong>
        {uploading ? "Storing video locally" : "Drop an orbit video"}
      </strong>
      <small>MP4, MOV, WebM, AVI or MKV. Up to 4 minutes.</small>
      <span className="dropzone-action">
        <UploadSimple size={15} /> Choose video
      </span>
    </button>
  );
}
