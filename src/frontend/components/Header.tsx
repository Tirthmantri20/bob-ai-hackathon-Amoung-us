/**
 * Header — SupplyGuard AI branding, backend health, and Granite AI status.
 */

interface HeaderProps {
  backendHealthy: boolean
  watsonxLive: boolean | null
}

export default function Header({ backendHealthy, watsonxLive }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3.5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white text-lg font-black shadow-sm">
          S
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-slate-900 leading-tight">
            SupplyGuard <span className="text-blue-600">AI</span>
          </h1>
          <p className="text-xs text-slate-500 font-medium">
            Control Tower &bull; Cold-Chain Intelligence
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Backend health */}
        <div
          className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border ${
            backendHealthy
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}
        >
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              backendHealthy ? 'bg-emerald-500' : 'bg-red-500'
            }`}
            aria-hidden="true"
          />
          <span>{backendHealthy ? 'API Online' : 'API Offline'}</span>
        </div>

        {/* Granite AI status */}
        {watsonxLive === true && (
          <div className="flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700 border border-blue-200">
            <span className="inline-block h-2 w-2 rounded-full bg-blue-500 animate-pulse" aria-hidden="true" />
            <span>🤖 AI Live</span>
          </div>
        )}
        {watsonxLive === false && (
          <div className="flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 border border-slate-200">
            <span className="inline-block h-2 w-2 rounded-full bg-slate-400" aria-hidden="true" />
            <span>⚙️ AI Fallback</span>
          </div>
        )}
      </div>
    </header>
  )
}
