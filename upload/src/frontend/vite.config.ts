import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {plugins:[react(),tailwindcss()], server:{proxy:{'/api':{target:env.STAGING_PROXY_TARGET || 'http://127.0.0.1:8000',changeOrigin:true},'/health':{target:env.STAGING_PROXY_TARGET || 'http://127.0.0.1:8000',changeOrigin:true}}}}
})
