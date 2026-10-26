import { createContext, useContext, useState } from "react";

// focusMode = immersive test mode: the navbar collapses to just the JobLens AI logo
// so branding stays but all navigation/profile is hidden while taking an assessment.
const UIModeContext = createContext({ focusMode: false, setFocusMode: () => {} });

export function UIModeProvider({ children }) {
  const [focusMode, setFocusMode] = useState(false);
  return <UIModeContext.Provider value={{ focusMode, setFocusMode }}>{children}</UIModeContext.Provider>;
}

export const useUIMode = () => useContext(UIModeContext);
