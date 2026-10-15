import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// All /api calls are proxied to the FastAPI backend -> no CORS / localhost-vs-127.0.0.1 problems.
export default defineConfig({
  plugins:[react()],
  server:{port:5173,proxy:{'/api':{target:'http://127.0.0.1:8000',changeOrigin:true}}}
})
