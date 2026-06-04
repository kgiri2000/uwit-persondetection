import React, { useState } from 'react'
import { useRoomStore } from '../store/useRoomStore'
import { KeyRound, ShieldAlert, Monitor, User } from 'lucide-react'

export const LoginScreen: React.FC = () => {
  const { setAuth, setUserName } = useRoomStore()
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<'host' | 'guest' | 'observer'>('guest')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, role, name }),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setUserName(name || 'Anonymous')
        setAuth(true, role)
      } else {
        setError(data.message || 'Authentication Failed')
      }
    } catch (err) {
      console.error('Login request failed:', err)
      setError('Connection to server failed. Please check backend status.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-uw-brown/30 via-uw-darkBg to-uw-darkBg px-4">
      <div className="w-full max-w-md p-8 bg-uw-cardBg/60 backdrop-blur-xl border border-gray-800 rounded-2xl shadow-2xl relative overflow-hidden">
        {/* Decorative Gold Glow in Background */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-uw-gold/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 bg-uw-gold/10 text-uw-gold flex items-center justify-center rounded-xl mb-4 border border-uw-gold/30">
            <Monitor size={30} />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white m-0">
            UW Kiosk System
          </h1>
          <p className="text-sm text-gray-400 mt-1">Smart Service Center Console</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Your Name
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-500">
                <User size={18} />
              </span>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                className="w-full pl-10 pr-4 py-3 bg-black/40 border border-gray-800 focus:border-uw-gold focus:ring-1 focus:ring-uw-gold text-white rounded-lg placeholder-gray-600 transition-all duration-200 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Password
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-500">
                <KeyRound size={18} />
              </span>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter room password"
                className="w-full pl-10 pr-4 py-3 bg-black/40 border border-gray-800 focus:border-uw-gold focus:ring-1 focus:ring-uw-gold text-white rounded-lg placeholder-gray-600 transition-all duration-200 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Select Access Mode
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as 'host' | 'guest' | 'observer')}
              className="w-full px-4 py-3 bg-black/40 border border-gray-800 focus:border-uw-gold focus:ring-1 focus:ring-uw-gold text-white rounded-lg transition-all duration-200 outline-none"
            >
              <option value="guest">Guest (Remote Operator)</option>
              <option value="host">Host (Kiosk Console)</option>
              <option value="observer">Observer (Free View)</option>
            </select>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-500 text-sm bg-red-500/10 border border-red-500/20 px-4 py-3 rounded-lg animate-shake">
              <ShieldAlert size={16} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 bg-uw-gold hover:bg-uw-gold/90 text-black font-bold rounded-lg shadow-lg hover:shadow-uw-gold/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed text-base cursor-pointer"
          >
            {loading ? 'Entering Room...' : 'Enter Room'}
          </button>
        </form>
      </div>
    </div>
  )
}
