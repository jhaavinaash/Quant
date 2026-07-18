import { useEffect, useState } from 'react';
import { instrumentService } from '../services/instrumentService';
import { InstrumentPaginatedResponse } from '../types';

const PAGE_SIZE = 10;

const Instruments = () => {
  const [data, setData] = useState<InstrumentPaginatedResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInstruments = async (page: number) => {
    setLoading(true);
    setError(null);

    try {
      const response = await instrumentService.getInstruments(page, PAGE_SIZE);
      setData(response);
      setCurrentPage(page);
    } catch {
      setError('Failed to load instruments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInstruments(1);
  }, []);

  if (loading) return <div className="p-8">Loading...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  const totalPages = Math.ceil((data?.total_count || 0) / PAGE_SIZE);

  const startPage = Math.max(1, currentPage - 2);
  const endPage = Math.min(totalPages, currentPage + 2);

  const visiblePages = [];
  for (let page = startPage; page <= endPage; page++) {
    visiblePages.push(page);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Instruments</h1>

      <table className="w-full bg-slate-900 rounded-lg">
        <thead>
          <tr className="border-b border-slate-800 text-left">
            <th className="p-4">Symbol</th>
            <th className="p-4">Exchange</th>
            <th className="p-4">Type</th>
          </tr>
        </thead>

        <tbody>
          {data?.items.map((instr) => (
            <tr key={instr.id} className="border-b border-slate-800">
              <td className="p-4">{instr.symbol}</td>
              <td className="p-4">{instr.exchange}</td>
              <td className="p-4">{instr.asset_type}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex items-center justify-center gap-2 mt-6">
        <button
          onClick={() => fetchInstruments(currentPage - 1)}
          disabled={currentPage === 1}
          className="px-3 py-2 bg-slate-800 rounded disabled:opacity-40"
        >
          Previous
        </button>

        {visiblePages.map((page) => (
          <button
            key={page}
            onClick={() => fetchInstruments(page)}
            className={`px-3 py-2 rounded ${
              currentPage === page
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800'
            }`}
          >
            {page}
          </button>
        ))}

        <button
          onClick={() => fetchInstruments(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="px-3 py-2 bg-slate-800 rounded disabled:opacity-40"
        >
          Next
        </button>
      </div>

      <div className="text-center text-slate-400 mt-3">
        Page {currentPage} of {totalPages} · {data?.total_count || 0} instruments
      </div>
    </div>
  );
};

export default Instruments;