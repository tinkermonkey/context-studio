import axios from "axios";
import { applyInterceptors } from "./interceptors";

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8100",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
  // Serialize arrays as repeated keys (`ids=a&ids=b`), which is what FastAPI
  // list query params expect; axios' default is `ids[]=a&ids[]=b`.
  paramsSerializer: { indexes: null },
});

applyInterceptors(axiosInstance);

export default axiosInstance;
