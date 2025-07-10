import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

const Login = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const success = await login(username, password);
      if (!success) {
        setError("Nom d'utilisateur ou mot de passe incorrect.");
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Une erreur est survenue lors de la connexion. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden font-sans" style={{ background: 'linear-gradient(to bottom right, #CCEFFF, #A0E0EF, #90E0EF, #B3F0FF)', backgroundSize: '400% 400%', animation: 'gradient-animation 15s ease infinite' }}>
      {/* Water droplet animations */}
      <div className="absolute inset-0 z-0">
        {[...Array(15)].map((_, i) => ( // Increased number of drops
          <div
            key={i}
            className="absolute rounded-full opacity-30 animate-water-drop"
            style={{
              width: `${Math.random() * 25 + 15}px`, // Slightly larger drops
              height: `${Math.random() * 25 + 15}px`,
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDuration: `${Math.random() * 6 + 6}s`, // Longer animation duration
              animationDelay: `${Math.random() * 4}s`,
              backgroundColor: 'var(--color-accent)',
              filter: 'blur(2px)', // Soften the drops
            }}
          />
        ))}
      </div>

      {/* Formulaire */}
      <div className="relative z-10 w-full max-w-lg mx-auto p-4 lg:p-0 animate-fade-in-up"> {/* Increased max-w-md to max-w-lg */}
        <div className="backdrop-blur-md p-8 sm:p-10 rounded-3xl shadow-3xl transition-all duration-500 transform hover:shadow-4xl" style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-muted)' }}>
          {/* Logo and Title */}
          <div className="flex flex-col items-center mb-8">
            <img
              src="onee-logo.png" // Assurez-vous que le chemin d'accès au logo est correct
              alt="ONEE - Office National de l'Électricité et de l'Eau Potable"
              className="w-24 h-24 mb-4 rounded-full shadow-lg p-2 object-contain ring-2" // Slightly larger logo
              style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-primary)' }}
            />
            <h2 className="text-4xl sm:text-5xl font-extrabold text-center tracking-tight mb-2 leading-tight" style={{ color: 'var(--color-primary)' }}>
              Portail ONEE Eau
            </h2>
            <p className="text-lg text-center" style={{ color: 'var(--color-text)' }}>Accédez à votre espace professionnel </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 border-l-4 rounded-lg flex items-start shadow-sm animate-fade-in" style={{ backgroundColor: 'rgba(var(--color-danger-rgb), 0.1)', borderColor: 'var(--color-danger)' }}>
              <svg className="w-6 h-6 mr-3 mt-1" fill="currentColor" viewBox="0 0 20 20" style={{ color: 'var(--color-danger)' }}>
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-base font-medium" style={{ color: 'var(--color-text)' }}>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Username Input */}
            <div>
              <label htmlFor="username" className="block text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
                Nom d'utilisateur
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style={{ color: 'var(--color-muted)' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                  </svg>
                </div>
                <input
                  type="text"
                  id="username"
                  className="w-full pl-10 pr-4 py-3 rounded-xl focus:ring-2 bg-white transition-all duration-300 placeholder-gray-400"
                  style={{
                    border: '1px solid var(--color-muted)',
                    color: 'var(--color-text)',
                    '--tw-ring-color': 'var(--color-primary)',
                    '--tw-focus-border-color': 'var(--color-primary)'
                  }}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={loading}
                  placeholder="Votre identifiant ONEE"
                  autoComplete="username"
                />
              </div>
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-semibold mb-2" style={{ color: 'var(--color-text)' }}>
                Mot de passe
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style={{ color: 'var(--color-muted)' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2v5a2 2 0 01-2 2H9a2 2 0 01-2-2V9a2 2 0 012-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v2M7 7h10"></path>
                  </svg>
                </div>
                <input
                  type="password"
                  id="password"
                  className="w-full pl-10 pr-4 py-3 rounded-xl focus:ring-2 bg-white transition-all duration-300 placeholder-gray-400"
                  style={{
                    border: '1px solid var(--color-muted)',
                    color: 'var(--color-text)',
                    '--tw-ring-color': 'var(--color-primary)',
                    '--tw-focus-border-color': 'var(--color-primary)'
                  }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  placeholder="Votre mot de passe confidentiel"
                  autoComplete="current-password"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full text-white py-3 px-4 rounded-xl font-bold shadow-lg focus:outline-none focus:ring-3 focus:ring-offset-2 transition-all duration-300 transform hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center text-lg"
              style={{
                backgroundColor: 'var(--color-primary)',
                '--tw-ring-color': 'var(--color-primary)',
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--color-secondary)'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary)'}
            >
              {loading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Connexion en cours...
                </span>
              ) : (
                <span className="flex items-center">
                  Se connecter
                  <svg className="ml-2 h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 9l3 3m0 0l-3 3m3-3H8m-5 0h2.5M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2z"></path>
                  </svg>
                </span>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-10 text-center">
            <p className="text-sm leading-relaxed" style={{ color: 'var(--color-muted)' }}>
              &copy; {new Date().getFullYear()} ONEE - Office National de l'Électricité et de l'Eau Potable. Tous droits réservés.
            </p>
            <p className="text-xs mt-2">
              <a href="#" className="hover:underline" style={{ color: 'var(--color-primary)' }}>Politique de confidentialité</a> | <a href="#" className="hover:underline" style={{ color: 'var(--color-primary)' }}>Conditions d'utilisation</a>
            </p>
          </div>
        </div>
      </div>

      {/* Tailwind CSS keyframes for animations and custom properties */}
      <style jsx>{`
        :root {
          --color-primary: #0077B6;
          --color-secondary: #00B4D8;
          --color-accent: #90E0EF;
          --color-background:rgb(234, 244, 245); /* This is less critical with the new gradient */
          --color-surface: #FFFFFF;
          --color-text: #023047;
          --color-muted: #8ECAE6;
          --color-success: #00C49A;
          --color-warning: #FFD166;
          --color-danger: #EF476F;
          --color-danger-rgb: 239, 71, 111; /* RGB pour l'opacité */
        }

        @keyframes fade-in-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in-up {
          animation: fade-in-up 0.6s ease-out forwards;
        }

        @keyframes water-drop {
          0% {
            transform: translateY(0) scale(0);
            opacity: 0;
          }
          20% {
            opacity: 0.3;
            transform: translateY(0) scale(1);
          }
          100% {
            transform: translateY(100vh) scale(1.5);
            opacity: 0;
          }
        }
        .animate-water-drop {
          animation: water-drop infinite;
        }

        @keyframes gradient-animation {
          0% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
          100% {
            background-position: 0% 50%;
          }
        }

        .shadow-3xl {
          box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04), 0 0 0 1px rgba(0, 0, 0, 0.06);
        }

        .hover\\:shadow-4xl:hover {
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.06);
        }
      `}</style>
    </div>
  );
};

export default Login;