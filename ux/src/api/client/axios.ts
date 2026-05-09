import axios from "axios";
import { applyInterceptors } from "./interceptors";

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8100",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

applyInterceptors(axiosInstance);

export default axiosInstance;
