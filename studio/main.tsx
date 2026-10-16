import React from "react";
import { createRoot } from "react-dom/client";
import { LokaWorkspace } from "../src/client/features/lokaseo/LokaWorkspace";
import "./style.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LokaWorkspace standalone />
  </React.StrictMode>,
);
