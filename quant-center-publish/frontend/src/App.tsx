import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ROUTES } from './constants/routes';
import MainLayout from './layout/MainLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import Dashboard from './views/Dashboard';
import Instruments from './views/Instruments';
import Brokers from './views/Brokers';
import Health from './views/Health';
import Settings from './views/Settings';
import Positions from './views/Positions';
import Execution from './views/Execution';
import Trades from './views/Trades';
import TradeEntry from './views/TradeEntry';
import AIScanner from './views/AIScanner';
import F1 from './views/F1';
import F1Basket from './views/F1Basket';
import Login from './views/Login'; // Assuming Login exists

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={ROUTES.LOGIN} element={<Login />} />
        
        {/* Protected Routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>
            <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
            <Route path={ROUTES.INSTRUMENTS} element={<Instruments />} />
            <Route path={ROUTES.POSITIONS} element={<Positions />} />
            <Route path={ROUTES.EXECUTION} element={<Execution />} />
            <Route path={ROUTES.TRADES} element={<Trades />} />
            <Route path={ROUTES.TRADE_ENTRY} element={<TradeEntry />} />
            <Route path={ROUTES.AI_SCANNER} element={<AIScanner />} />
            <Route path={ROUTES.F1} element={<F1 />} />
            <Route path={ROUTES.F1_BASKET} element={<F1Basket />} />
            <Route path={ROUTES.BROKERS} element={<Brokers />} />
            <Route path={ROUTES.HEALTH} element={<Health />} />
            <Route path={ROUTES.SETTINGS} element={<Settings />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;