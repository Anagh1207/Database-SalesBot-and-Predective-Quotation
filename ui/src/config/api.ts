// In development: points to local backend
// In production (Vercel): set VITE_API_BASE to your Railway backend URL
//   e.g. https://your-backend.railway.app
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "");
