import { useEffect, useState } from 'react';
import { engineService } from '../services/engineService';
import { EngineStatus as EngineStatusType } from '../types/engine';

export const EngineStatus = () => {
  const [engines, setEngines] = useState<EngineStatusType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    engineService.getStatuses()
      .then((data) => {
        // FIX: Ensure state is always an array, even if the API returns an unexpected structure
        setEngines(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        console.error("EngineStatus load error:", err);
        setError(err.response?.data?.detail || "Failed to load engines");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-500 text-sm italic">Loading status...</div>;
  if (error) return <div className="text-red-500 text-sm">{error}</div>;

  return (
    <div className="space-y-3">
      {/* FIX: Defensive check to ensure engines is an array before mapping */}
      {Array.isArray(engines) && engines.length > 0 ? (
        engines.map((e, idx) => (
          <div key={idx} className="flex justify-between items-center text-sm">
            <span className="text-slate-300 font-medium">{e.Engine}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
              e.Status === 'SUCCESS' 
                ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-900/50' 
                : 'bg-red-900/30 text-red-400 border border-red-900/50'
            }`}>
              {e.Status}
            </span>
          </div>
        ))
      ) : (
        <div className="text-slate-500 text-sm">No status records found.</div>
      )}
    </div>
  );
};