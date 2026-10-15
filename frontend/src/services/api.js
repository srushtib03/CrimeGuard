import axios from "axios";

// ---- session (login) -------------------------------------------------------
const KEY = "crimeguard.session";
export const getSession = () => { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } };
export const setSession = s => localStorage.setItem(KEY, JSON.stringify(s));
export const clearSession = () => localStorage.removeItem(KEY);

export const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || "/api" });
API.interceptors.request.use(cfg => {
  const s = getSession();
  if (s?.token) cfg.headers.Authorization = `Bearer ${s.token}`;
  return cfg;
});
API.interceptors.response.use(r => r, err => {
  // expired / invalid token -> back to the login screen (but not for the login call itself)
  if (err?.response?.status === 401 && !String(err.config?.url).includes("/auth/login")) {
    clearSession();
    window.dispatchEvent(new Event("cg-auth-expired"));
  }
  return Promise.reject(err);
});

// ---- auth ------------------------------------------------------------------
export const login = (username, password, role) => API.post("/auth/login", { username, password, role });
export const getMe = () => API.get("/auth/me");

// ---- existing endpoints (unchanged) ----------------------------------------
export const getHealth = () => API.get("/health");
export const getModel = () => API.get("/model");
export const getModels = () => API.get("/models");
export const getOptions = () => API.get("/options");
export const getSummary = () => API.get("/summary");
export const getKMeans = () => API.get("/hotspots/kmeans");
export const getDBSCAN = () => API.get("/hotspots/dbscan");
export const getSHAP = () => API.get("/shap");
export const getApriori = () => API.get("/apriori");
export const predict = (data) => API.post("/predict", data);
export const getRollup = () => API.get("/olap/rollup");
export const getDrilldown = () => API.get("/olap/drilldown");
export const getSlice = (district) => API.get("/olap/slice", {params:{district}});
export const getDice = (districts, crimes) => API.get("/olap/dice", {params:{districts:districts.join(","), crimes:crimes.join(",")}});
export const getPivot = () => API.get("/olap/pivot");

// ---- new: question-driven OLAP + mining charts (Crime Branch) ---------------
export const getOlapCatalog = () => API.get("/olap/catalog");
export const askOlap = (id, params = {}) => API.get("/olap/ask", { params: { id, ...params } });
export const getMiningKMeans = () => API.get("/mining/kmeans");
export const getMiningDBSCAN = () => API.get("/mining/dbscan");
export const getMiningApriori = () => API.get("/mining/apriori");
