'use client'

/**
 * AddShipmentModal — form to create a new shipment via POST /api/shipments/
 */

import { useState } from 'react'
import { api } from '@/services/api'

interface AddShipmentModalProps {
  onClose: () => void
  onCreated: () => void
}

const STATUS_OPTIONS = ['PENDING', 'IN_TRANSIT', 'ALERT_DISRUPTION', 'DELIVERED', 'CANCELLED']
const CARRIER_OPTIONS = ['CRR-401', 'CRR-402', 'CRR-403', 'CRR-404', 'CRR-405']
const CATEGORY_OPTIONS = [
  'Cold Chain Grade A',
  'Ultra Cold Chain',
  'Perishable Frozen',
  'Perishable Standard',
  'Hazardous Cold Chain',
]

function genId(): string {
  return `SHP-${Math.floor(5000 + Math.random() * 5000)}`
}

export default function AddShipmentModal({ onClose, onCreated }: AddShipmentModalProps) {
  const [form, setForm] = useState({
    id: genId(),
    tracking_number: '',
    origin: '',
    destination: '',
    cargo_type: '',
    cargo_category: CATEGORY_OPTIONS[0],
    required_temp_min_c: '2',
    required_temp_max_c: '8',
    status: 'PENDING',
    carrier_id: 'CRR-401',
    current_lat: '',
    current_lon: '',
    current_location_name: '',
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
      await api.createShipment({
        id: form.id,
        tracking_number: form.tracking_number || null,
        origin: form.origin,
        destination: form.destination,
        cargo_type: form.cargo_type,
        cargo_category: form.cargo_category,
        required_temp_min_c: parseFloat(form.required_temp_min_c),
        required_temp_max_c: parseFloat(form.required_temp_max_c),
        status: form.status,
        carrier_id: form.carrier_id || null,
        current_lat: form.current_lat ? parseFloat(form.current_lat) : null,
        current_lon: form.current_lon ? parseFloat(form.current_lon) : null,
        current_location_name: form.current_location_name || null,
      })
      onCreated()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create shipment')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <h2 className="text-base font-bold text-slate-900">Add New Shipment</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none" aria-label="Close">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-3">
          {error && (
            <p className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</p>
          )}

          <div className="grid grid-cols-2 gap-3">
            <label className="col-span-2 block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Shipment ID *</span>
              <input name="id" value={form.id} onChange={handleChange} required
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Tracking Number</span>
              <input name="tracking_number" value={form.tracking_number} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Status *</span>
              <select name="status" value={form.status} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500">
                {STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Origin *</span>
              <input name="origin" value={form.origin} onChange={handleChange} required placeholder="e.g. Chicago, IL"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Destination *</span>
              <input name="destination" value={form.destination} onChange={handleChange} required placeholder="e.g. Atlanta, GA"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Cargo Type *</span>
              <input name="cargo_type" value={form.cargo_type} onChange={handleChange} required placeholder="e.g. Pharmaceuticals"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Cargo Category *</span>
              <select name="cargo_category" value={form.cargo_category} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500">
                {CATEGORY_OPTIONS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Temp Min (°C) *</span>
              <input name="required_temp_min_c" type="number" step="0.1" value={form.required_temp_min_c} onChange={handleChange} required
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Temp Max (°C) *</span>
              <input name="required_temp_max_c" type="number" step="0.1" value={form.required_temp_max_c} onChange={handleChange} required
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Carrier</span>
              <select name="carrier_id" value={form.carrier_id} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500">
                {CARRIER_OPTIONS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Current Location Name</span>
              <input name="current_location_name" value={form.current_location_name} onChange={handleChange} placeholder="e.g. Indianapolis, IN"
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Latitude</span>
              <input name="current_lat" type="number" step="0.0001" value={form.current_lat} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Longitude</span>
              <input name="current_lon" type="number" step="0.0001" value={form.current_lon} onChange={handleChange}
                className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </label>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
              {saving ? 'Saving…' : 'Create Shipment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
