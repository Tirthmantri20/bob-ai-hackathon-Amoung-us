/**
 * Header — SupplyGuard AI branding, backend health, and Granite AI status.
 */

interface HeaderProps {
  backendHealthy: boolean
  watsonxLive: boolean | null
}

export default function Header({ backendHealthy, watsonxLive }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-gray-800 bg-gray-950 px-6 py-4">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight text-white">
          SupplyGuard <span className="text-blue-400">AI</span>
        </h1>
        <p className="text-xs text-gray-500 font-medium tracking-widest uppercase">
          Control Tower
        </p>
      </div>

      <div className="flex items-center gap-4">
        {/* Backend health */}
        <div className="flex items-center gap-1.5">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              backendHealthy ? 'bg-green-500' : 'bg-red-500'
            }`}
            aria-hidden="true"
          />
          <span className="text-xs text-gray-400">
            {backendHealthy ? 'API Online' : 'API Offline'}
          </span>
        </div>

        {/* Granite AI status */}
        {watsonxLive === true && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-green-400" aria-hidden="true" />
            <span className="text-xs text-green-400 font-medium">🤖 AI Live</span>
          </div>
        )}
        {watsonxLive === false && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-gray-500" aria-hidden="true" />
            <span className="text-xs text-gray-400">⚙️ AI Fallback</span>
          </div>
        )}
      </div>
    </header>
  )
}
