import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 30000 });

export const fmtUsd = (v, d = 2) =>
  v === null || v === undefined || isNaN(v)
    ? "—"
    : v.toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      });

export const fmtNum = (v, d = 2) =>
  v === null || v === undefined || isNaN(v)
    ? "—"
    : Number(v).toLocaleString("en-US", {
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      });

export const fmtPct = (v, d = 2) =>
  v === null || v === undefined || isNaN(v) ? "—" : `${v >= 0 ? "+" : ""}${Number(v).toFixed(d)}%`;
