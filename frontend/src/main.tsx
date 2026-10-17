import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import AdminMemory from "./AdminMemory";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {window.location.pathname === "/admin" ? <AdminMemory /> : <App />}
  </React.StrictMode>
);
