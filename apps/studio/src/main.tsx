import "@radix-ui/themes/styles.css";
import "./styles.css";

import { Theme } from "@radix-ui/themes";
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

function Root() {
  const [appearance, setAppearance] = useState<"dark" | "light">(() => {
    const stored = localStorage.getItem("kinetiweave-theme");
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  });

  useEffect(() => {
    localStorage.setItem("kinetiweave-theme", appearance);
    document.documentElement.dataset.theme = appearance;
  }, [appearance]);

  return (
    <Theme
      appearance={appearance}
      accentColor="orange"
      grayColor="olive"
      radius="medium"
    >
      <App appearance={appearance} onAppearanceChange={setAppearance} />
    </Theme>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
