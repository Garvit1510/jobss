import React from "react";

export default function ResultTable({ table, testid, empty = "(no rows)" }) {
  if (!table) return null;
  const { columns = [], rows = [] } = table;
  if (!columns.length) return <p className="font-mono text-xs text-ink/55" data-testid={testid}>{empty}</p>;
  return (
    <div className="max-h-64 overflow-auto border-2 border-ink bg-white" data-testid={testid}>
      <table className="w-full border-collapse font-mono text-xs">
        <thead className="sticky top-0 bg-ink text-white">
          <tr>{columns.map((c, i) => <th key={i} className="border-r border-white/20 px-2 py-1.5 text-left font-bold">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-ink/10 odd:bg-offwhite">
              {r.map((v, j) => <td key={j} className="px-2 py-1 whitespace-nowrap">{v === null ? <i className="text-ink/40">NULL</i> : String(v)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="p-2 font-mono text-xs text-ink/55">{empty}</p>}
    </div>
  );
}
