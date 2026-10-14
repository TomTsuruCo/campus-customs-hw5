import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend only allows the dev page origin http://localhost:5173, so keep this port fixed.
export default defineConfig({
  plugins: [react()],
  server: { host: 'localhost', port: 5173, strictPort: true },
})
