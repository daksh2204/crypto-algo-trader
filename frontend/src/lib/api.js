import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 60000 });

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

export const fmtInr = (v, d = 2) =>
  v === null || v === undefined || isNaN(v)
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      }).format(v);

export const fmtNum = (v, d = 2) =>
  v === null || v === undefined || isNaN(v)
    ? "—"
    : Number(v).toLocaleString("en-IN", {
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      });

export const fmtPct = (v, d = 2) =>
  v === null || v === undefined || isNaN(v) ? "—" : `${v >= 0 ? "+" : ""}${Number(v).toFixed(d)}%`;

export const shortSym = (s) => (s || "").replace("INR", "");
