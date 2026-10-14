import { useState } from 'react'
import type { Role } from './types'

/** Flat little portraits: the Boss in a suit and tie, everyone else as an ordinary worker. */

const LOOK: Record<Role, { skin: string; hair: string }> = {
  boss: { skin: '#e8b78f', hair: '#2b2018' },
  inventory: { skin: '#c58b62', hair: '#3a2418' },
  accounting: { skin: '#f2cdaa', hair: '#7a4a2a' },
  facilities: { skin: '#8d5a3b', hair: '#1b1411' },
  customer_service: { skin: '#e3ae88', hair: '#5a2a1a' },
}

const INK = '#1d1530'

export function Person({ role, label }: { role: Role; label?: string }) {
  const { skin, hair } = LOOK[role]
  const boss = role === 'boss'
  return (
    <svg viewBox="0 0 64 64" role="img" aria-label={label ?? role.replace('_', ' ')}>
      {/* customer service wears long hair behind the shoulders */}
      {role === 'customer_service' && (
        <path d="M20.5 24 C17 36 18 46 23 50 L41 50 C46 46 47 36 43.5 24 Z" fill={hair} />
      )}

      {/* body */}
      <path d="M6 66 C6 51 18 45 32 45 C46 45 58 51 58 66 Z" style={{ fill: boss ? '#1b2650' : 'var(--agent)' }} />
      <rect x="27.5" y="36" width="9" height="10" rx="3" fill={skin} />
      {boss ? (
        <>
          <path d="M24 45 L32 58 L40 45 L36 44 L32 49 L28 44 Z" fill="#ffffff" />
          <path d="M17 49 L26 45 L31 58 L22 60 Z" fill="#27366f" />
          <path d="M47 49 L38 45 L33 58 L42 60 Z" fill="#27366f" />
          <path d="M32 48.5 L29.4 52.5 L32 63 L34.6 52.5 Z" fill="#c8312f" />
          <path d="M30 47.5 L34 47.5 L33.2 50.5 L30.8 50.5 Z" fill="#a22524" />
          <circle cx="21.5" cy="53.5" r="1.7" fill="#d4ab4f" />
        </>
      ) : (
        <>
          <path d="M25 45 L32 58 L39 45" fill="none" stroke="#fff" strokeOpacity="0.9" strokeWidth="1.7" />
          <rect x="28.3" y="56" width="7.4" height="8.5" rx="1.6" fill="#fff" />
          <rect x="29.8" y="58.3" width="4.4" height="1.4" rx="0.7" fill="#8b7fb0" />
          <rect x="29.8" y="60.8" width="3" height="1.2" rx="0.6" fill="#c9c0e0" />
        </>
      )}

      {/* head */}
      <circle cx="21.9" cy="27" r="2.3" fill={skin} />
      <circle cx="42.1" cy="27" r="2.3" fill={skin} />
      <ellipse cx="32" cy="26" rx="10" ry="11.2" fill={skin} />

      {/* hair and headgear */}
      {boss && (
        <>
          <path d="M21.4 25 C20.6 11.5 43.4 11.5 42.6 25 C40.4 19.6 36.4 17.6 32 17.6 C27.6 17.6 23.6 19.6 21.4 25 Z" fill={hair} />
          <path d="M25.3 23.4 L30.6 22.8 M33.4 22.8 L38.7 23.4" stroke={hair} strokeWidth="1.7" strokeLinecap="round" />
        </>
      )}
      {role === 'accounting' && (
        <path d="M21.8 25 C21 13.5 43 13.5 42.2 25 C40 20.8 36 19.4 32 19.4 C28 19.4 24 20.8 21.8 25 Z" fill={hair} />
      )}
      {role === 'inventory' && (
        <>
          <path d="M21 22.5 C21 11 43 11 43 22.5 Z" fill="#f3a23a" />
          <rect x="19.5" y="21.4" width="25" height="3.3" rx="1.6" fill="#d98a22" />
          <path d="M20 28.5 L21.6 28.5 L21.6 24 L20 24 Z M44 28.5 L42.4 28.5 L42.4 24 L44 24 Z" fill={hair} />
        </>
      )}
      {role === 'facilities' && (
        <>
          <path d="M20.6 22.4 C20.6 10.6 43.4 10.6 43.4 22.4 Z" fill="#f6c431" />
          <rect x="30" y="11.2" width="4" height="9.5" rx="1.4" fill="#e3ac1c" />
          <rect x="18.2" y="21.2" width="27.6" height="3.6" rx="1.8" fill="#e3ac1c" />
        </>
      )}
      {role === 'customer_service' && (
        <>
          <path d="M21.6 25 C21 13.5 43 13.5 42.4 25 C40.4 20.6 36.4 19.2 32 19.2 C27.6 19.2 23.6 20.6 21.6 25 Z" fill={hair} />
          <path d="M20.4 27 C19.6 10.6 44.4 10.6 43.6 27" fill="none" stroke={INK} strokeWidth="2.2" />
          <rect x="18.4" y="25" width="4.2" height="7.4" rx="2.1" fill={INK} />
          <rect x="41.4" y="25" width="4.2" height="7.4" rx="2.1" fill={INK} />
          <path d="M20.6 31.5 C21.4 38 26 38.4 29 37.2" fill="none" stroke={INK} strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="29.6" cy="37" r="1.7" fill={INK} />
        </>
      )}

      {/* face */}
      <circle cx="28" cy="27.2" r="1.3" fill={INK} />
      <circle cx="36" cy="27.2" r="1.3" fill={INK} />
      {role === 'accounting' && (
        <g fill="none" stroke="#2b2236" strokeWidth="1.3">
          <circle cx="28" cy="27.2" r="3.6" />
          <circle cx="36" cy="27.2" r="3.6" />
          <path d="M31.6 27 L32.4 27" />
        </g>
      )}
      <path
        d={boss ? 'M27.4 32.4 Q32 36.2 36.6 32.4' : 'M28.6 32.6 Q32 35 35.4 32.6'}
        fill="none" stroke="#7a3b2b" strokeWidth="1.5" strokeLinecap="round"
      />
    </svg>
  )
}

/** A Yale-style badge with blue ribbon tails. A stand-in: put an official logo at public/yale-logo.svg to replace it. */
export function YaleBadge() {
  const [custom, setCustom] = useState(true)
  return (
    <div className="yale" title="Yale School of Management">
      {custom ? (
        <img src="/yale-logo.svg" alt="Yale" onError={() => setCustom(false)} />
      ) : (
        <svg viewBox="0 0 62 78" role="img" aria-label="Yale">
          <path d="M13 44 L5 76 L19 69 L27 78 L31 46 Z" fill="#2f6fc4" />
          <path d="M49 44 L57 76 L43 69 L35 78 L31 46 Z" fill="#00356b" />
          <path d="M13 44 L5 76 L12 72.5 L18 47 Z" fill="#1d55a0" opacity="0.7" />
          <path
            d="M31 2 C40 7.5 51 8 58 8 L58 33 C58 45 46 52 31 58 C16 52 4 45 4 33 L4 8 C11 8 22 7.5 31 2 Z"
            fill="#00356b" stroke="#d4ab4f" strokeWidth="2.6" strokeLinejoin="round"
          />
          <path d="M31 8 C38 11.5 46 12.4 53 12.6 L53 33 C53 42 43.5 47 31 52 C18.5 47 9 42 9 33 L9 12.6 C16 12.4 24 11.5 31 8 Z" fill="none" stroke="#ffffff" strokeOpacity="0.35" strokeWidth="1" />
          <text x="31" y="41" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif" fontWeight="700" fontSize="33" fill="#ffffff">Y</text>
        </svg>
      )}
    </div>
  )
}
