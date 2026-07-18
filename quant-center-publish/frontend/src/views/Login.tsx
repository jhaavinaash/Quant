import { useState } from 'react';
import { authService } from '../services/authService';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await authService.login(username, password);
      window.location.href = '/'; // Force reload to re-verify session
    } catch {
      setError('Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-slate-950">
      <form onSubmit={handleSubmit} className="bg-slate-900 p-8 rounded-lg w-96">
        <h2 className="text-white text-xl mb-4">Quant Center Login</h2>
        {error && <p className="text-red-500 mb-4">{error}</p>}
        <input className="w-full p-2 mb-4 bg-slate-800 text-white" placeholder="Username" onChange={(e) => setUsername(e.target.value)} />
        <input className="w-full p-2 mb-4 bg-slate-800 text-white" type="password" placeholder="Password" onChange={(e) => setPassword(e.target.value)} />
        <button disabled={loading} className="w-full bg-blue-600 text-white p-2">
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
};

export default Login;