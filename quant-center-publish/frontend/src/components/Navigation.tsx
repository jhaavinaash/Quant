import React from 'react';
import { NavLink } from 'react-router-dom';

/**
 * Navigation Component:
 * Controls workspace switching. Includes centralized brand logo and active path tracking.
 */
const Navigation: React.FC = () => {
  const navItems = [
    { name: 'Dashboard', path: '/' },
    { name: 'Brokers', path: '/brokers' },
    { name: 'Instruments', path: '/instruments' },
    { name: 'Health', path: '/health' },
    { name: 'Settings', path: '/settings' },
  ];

  return (
    <nav className="p-4 space-y-2">
      {/* Sidebar Brand Identity */}
      <div className="mb-8 flex justify-center">
        <img
          src="/logo/quantcenter-logo.png"
          alt="Quant Center"
          className="h-12"
        />
      </div>

      {/* Navigation Items */}
      {navItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) =>
            `block px-4 py-2 rounded-lg transition-colors duration-200 ${
              isActive 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
            }`
          }
        >
          {item.name}
        </NavLink>
      ))}
    </nav>
  );
};

export default Navigation;