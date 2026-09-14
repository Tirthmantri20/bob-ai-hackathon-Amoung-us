'use client'

/**
 * AddDisruptionModal — form to create a new disruption via POST /api/disruptions/
 */

import { useState } from 'react'
import { api } from '@/services/api'

interface AddDisruptionModalProps {
  onClose: () => void
  onCreated: () => void
}

const TYPE_OPTIONS = [
  'SEVERE_WEATHER',
  'PORT_CONTAINER_HOLD',
  'ROADWORK_CONGESTION',
  'TRAFFIC_ACCIDENT',
]

const SEVERITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

function genId(): string {
  return `DIS-${Math.floor(600 + Math.random() * 400)}`
}

export default function AddDisruptionModal({ onClose, onCreated }: AddDisruptionModalProps) {
  const [form, setForm] = useState({
    id: genId(),
    type: TYPE_OPTIONS[0],
    severity: 'MEDIUM',
    title: '',
    affected_corridor: '',
    start_time: new Date().toISOString().slice(0, 16),
    expected_end_time: '',
    impact_delay_hours: '2',
    recommended_reroute: '',
    geometry_lat: '',
    geometry_lon: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.createDisruption({
        id: form.id,
        type: form.type,
        severity: form.severity,
        title: form.title,
        affected_corridor: form.affected_corridor || null,
        start_time: new Date(form.start_time).toISOString(),
        expected_end_time: form.expected_end_time
          ? new Date(form.expected_end_time).toISOString()
          : null,
        impact_delay_hours: form.impact_delay_hours ? parseFloat(form.impact_delay_hours) : null,
        recommended_reroute: form.recommended_reroute || null,
        geometry_lat: form.geometry_lat ? parseFloat(form.geometry_lat) : null,
        geometry_lon: form.geometry_lon ? parseFloat(form.geometry_lon) : null,
      })
      onCreated()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create disruption')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <h2 className="text-base font-bold text-slate-900">Add New Disruption</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none" aria-label="Close">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-3">
          {error && (
            <p className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</p>
          )}

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Disruption ID *</span>
              <input name="id" value={form.id} onChange={handleChange} required
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Type *</span>
              <select name="type" value={form.type} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500">
                {TYPE_OPTIONS.map((t) => <option key={t}>{t}</option>)}
              </select>
            </label>
            <label className="col-span-2 block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Title *</span>
              <input name="title" value={form.title} onChange={handleChange} required placeholder="e.g. Winter Storm Warning - I-90"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Severity *</span>
              <select name="severity" value={form.severity} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500">
                {SEVERITY_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Impact Delay (hrs)</span>
              <input name="impact_delay_hours" type="number" step="0.5" min="0" value={form.impact_delay_hours} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="col-span-2 block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Affected Corridor</span>
              <input name="affected_corridor" value={form.affected_corridor} onChange={handleChange} placeholder="e.g. I-90 Eastbound"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Start Time *</span>
              <input name="start_time" type="datetime-local" value={form.start_time} onChange={handleChange} required
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Expected End Time</span>
              <input name="expected_end_time" type="datetime-local" value={form.expected_end_time} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="col-span-2 block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Recommended Reroute</span>
              <input name="recommended_reroute" value={form.recommended_reroute} onChange={handleChange} placeholder="e.g. US-1 North"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Latitude</span>
              <input name="geometry_lat" type="number" step="0.0001" value={form.geometry_lat} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Longitude</span>
              <input name="geometry_lon" type="number" step="0.0001" value={form.geometry_lon} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </label>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-60">
              {saving ? 'Saving…' : 'Create Disruption'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
