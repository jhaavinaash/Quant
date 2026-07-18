import { Outlet, NavLink } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { NAVIGATION_ITEMS } from '../constants/navigation';
import { authService } from '../services/authService';
import { LogOut, User } from 'lucide-react';
import { useEffect, useState } from 'react';
import { formatDate } from '../utils/formatters';

const MainLayout = () => {
  const [time, setTime] = useState(new Date());
  
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans">
      <aside className="w-56 bg-slate-900 border-r border-slate-800 flex flex-col shadow-xl">
        <div className="h-14 flex items-center px-6 border-b border-slate-800 font-bold text-amber-500 tracking-wider text-lg">
          QUANT CENTER
        </div>
        {/* Navigation... */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {NAVIGATION_ITEMS.map((item) => (
             <NavLink key={item.path} to={item.path} className={({ isActive }) => 
                `flex items-center gap-3 px-4 py-2.5 rounded-sm text-sm ${isActive ? 'bg-slate-800 text-amber-400 border-l-2 border-amber-500' : 'text-slate-400 hover:text-slate-200'}`
             }>{item.label}</NavLink>
          ))}
        </nav>
        <button onClick={() => { authService.logout(); window.location.href = ROUTES.LOGIN; }} 
                className="flex items-center gap-3 px-6 py-4 text-sm text-slate-500 hover:text-red-400 border-t border-slate-800">
          <LogOut size={16} /> Logout
        </button>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 border-b border-slate-800 bg-slate-900 flex items-center justify-between px-6">
          <div />
          <div className="flex items-center gap-6 text-sm text-slate-400">
            <span className="flex items-center gap-2">{formatDate(time)} | {time.toLocaleTimeString('en-GB')} IST</span>
            <div className="w-px h-4 bg-slate-800" />
            <span className="flex items-center gap-2 text-slate-200"><User size={16}/> TRADER_01</span>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6 bg-slate-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;