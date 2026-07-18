export const TradingTable = ({ headers, children }: { headers: string[], children: React.ReactNode }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm text-left border-collapse">
      <thead>
        <tr className="border-b border-slate-800 bg-slate-900 text-slate-500">
          {headers.map((h) => (
            <th key={h} className="px-4 py-3 font-medium uppercase tracking-wider text-[11px]">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="text-slate-300 divide-y divide-slate-800">
        {children}
      </tbody>
    </table>
  </div>
);