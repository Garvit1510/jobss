import React, { useEffect, useRef, useState } from "react";

export function CamPreview({ stream, className = "", testid = "proctor-cam" }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream;
  }, [stream]);
  return <video ref={ref} autoPlay muted playsInline className={`bg-ink object-cover -scale-x-100 ${className}`} data-testid={testid} />;
}

export function MicMeter({ levelRef, testid = "proctor-mic-meter" }) {
  const [lvl, setLvl] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setLvl(levelRef.current), 200);
    return () => clearInterval(t);
  }, [levelRef]);
  return (
    <div className="h-2.5 w-full border-2 border-ink bg-offwhite" data-testid={testid}>
      <div className={`h-full transition-[width] duration-150 ${lvl > 48 ? "bg-brand-red" : "bg-brand-green"}`} style={{ width: `${lvl}%` }} />
    </div>
  );
}
