import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { UIModeProvider } from "./context/UIMode";

// Browser extensions (password managers, wallets, anti-cheat, etc.) can throw errors inside their
// own injected scripts. Those surface in the dev "Uncaught runtime errors" overlay and block the app
// even though they are not our bug. Swallow errors that originate from an extension URL only.
const isExtensionSource = (s) => typeof s === "string" && /^(chrome|moz|safari|ms-browser)-extension:\/\//.test(s);
window.addEventListener(
  "error",
  (e) => {
    const src = e?.filename || e?.error?.stack || "";
    if (isExtensionSource(e?.filename) || (typeof src === "string" && /-extension:\/\//.test(src))) {
      e.stopImmediatePropagation();
      e.preventDefault();
    }
  },
  true
);
window.addEventListener(
  "unhandledrejection",
  (e) => {
    const stack = e?.reason?.stack || "";
    if (typeof stack === "string" && /-extension:\/\//.test(stack)) {
      e.stopImmediatePropagation();
      e.preventDefault();
    }
  },
  true
);

ReactDOM.createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <AuthProvider>
      <UIModeProvider>
        <App />
      </UIModeProvider>
    </AuthProvider>
  </BrowserRouter>
);
