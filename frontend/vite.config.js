import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
// In dev, proxy /api to the local FastAPI server so the frontend and API share
// an origin. In production, set VITE_API_BASE to the deployed API origin.
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/api": { target: "http://localhost:8000", changeOrigin: true },
        },
    },
});
